# idel_iac.py

import os
import json
import traceback
import logging
import yaml
from yaml import load, dump, Loader, Dumper
from logdecorator import log_on_start, log_on_end, log_on_error, log_exception

import idel_utils
from idel_s3 import IdelS3
from idel_cp import IdelCodePipeline
from idel_cfn import IdelCloudFormation
from idel_sm import IdelSecretsManager
from idel_clients import IdelClients

# Constants
STR_CFN = 'cfn'
STR_AWS = 'aws'
STR_DEPLOY = 'deploy'
STR_DELETE = 'delete'
CHANGE_MODE_CHANGE = 'change'
CHANGE_MODE_PROVISION = 'provision'
CHANGE_MODE_DESTROY = 'destroy'
CHANGE_MODE_ON = 'on'
CHANGE_MODE_OFF = 'off'
INVENTORY_FILE = '.inventory.yaml'
STATUS_DONE = 'DONE'
STATUS_WAITING = 'WAITING'
ARTIFACT_DIR = os.environ['ARTIFACT_DIR']
CHANGES_FILE = os.environ['CHANGES_FILE']
SECRET_NAME = os.environ['SECRET_NAME']
WAITING_OCCURRENCE = int(os.environ['WAITING_OCCURRENCE'])

class IdelIaC:
    #
    logger = None
    event = None
    context = None
    secret = None

    # handlers
    cp_handler = None
    sm_handler = None
    s3_handler = None
    cfn_handler = None

    # codepipeline variables
    cp_job_id = None
    cp_job_data = None
    cp_user_params = None
    cp_artifact = None
    cp_artifact_s3 = None

    def __init__(self, event, context):
        # Setup logging
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.os.environ['LOGGING_LEVEL'])

        self.event = event
        self.context = context

        self.s3_handler = IdelS3(event['CodePipeline.job']['data']['artifactCredentials'])
        self.cp_handler = IdelCodePipeline()
        self.cfn_handler = IdelCloudFormation()
        self.sm_handler = IdelSecretsManager()

        # Log
        self.logger.info('Finish instantiating class: {}'.format(self.__str__()))

        return

    @log_on_start(logging.INFO, "Start processing.")
    @log_on_end(logging.INFO, "End processing.")
    def process(self):
        """Main function
        """
        try:
            # Extract the CodePipeline Job
            self.cp_job_id = self.event['CodePipeline.job']['id']
            self.cp_job_data = self.event['CodePipeline.job']['data']
            self.cp_user_params = idel_utils.get_user_params(self.cp_job_data)
            self.cp_artifact = self.cp_job_data['inputArtifacts'][0]

            # LOGGING
            self.logger.info('Pipeline execution ID: {}'.format(self.cp_user_params['Pipeline']['ExecutionId']))

            # Download artifact
            self.s3_handler.download_artifact(
                s3_bucket=self.cp_artifact['location']['s3Location']['bucketName'],
                s3_object=self.cp_artifact['location']['s3Location']['objectKey'],
                af_dir=ARTIFACT_DIR
            )

            # Get secret
            self.secret = self.sm_handler.get_secret(SECRET_NAME)

            # Set up boto3 handler for CloudFormation
            self.cfn_handler.setup_boto3_client(self.secret)

            # Selective decision based on continuation data
            continuation = self.get_continuation_token()

            # If Status is STATUS_WAITING and Occurrence is over WAITING_OCCURRENCE times
            # throw exception then exit pipeline
            if (STATUS_WAITING==continuation['Status']) and (WAITING_OCCURRENCE<int(continuation['Occurrence'])):
                raise Exception('Waiting too much. Exit!')

            # Get changes deployment script
            changes = self.get_changes()

            # New or still?
            if (continuation['Status']==STATUS_DONE):
                # Previous block is done
                # it's time to process new block
                self.process_new_block(continuation, changes)

            elif (continuation['Status']==STATUS_WAITING):
                # Previous block is not done yet
                # so we are going to get the status
                self.process_old_block(continuation, changes)

            else:
                self.cp_handler.put_job_failure(self.cp_job_id, 'Unknown status')

        except Exception as e:
            # If any other exceptions which we didn't expect are raised
            # then fail the job and log the exception message.
            self.logger.info('Function failed due to exception.')
            self.logger.error(e)
            traceback.print_exc()

            self.cp_handler.put_job_failure(self.cp_job_id, 'Function exception: ' + str(e))

        return None

    @log_on_start(logging.INFO, "Start getting changes deployment script.")
    @log_on_end(logging.INFO, "End getting changes deployment script. Return: (Omitted. Please run debug.)")
    @log_on_end(logging.DEBUG, "End getting changes deployment script. Return: {result!r}")
    def get_changes(self):
        """Get list of changes
        Then convert Template reference path to TemplateBody
        """
        with open(ARTIFACT_DIR+CHANGES_FILE, encoding='utf-8') as file:
            raw_data_changes = file.read()
        data_changes = yaml.load(raw_data_changes, Loader=Loader)
        idel_utils.validate_changes(data_changes)

        change_mode = data_changes['Mode']

        raw_data_inventory = None
        data_inventory = None

        if (change_mode in [CHANGE_MODE_PROVISION, CHANGE_MODE_DESTROY, CHANGE_MODE_ON, CHANGE_MODE_OFF]):
            with open(ARTIFACT_DIR+INVENTORY_FILE, encoding='utf-8') as file:
                raw_data_inventory = file.read()
            data_inventory = yaml.load(raw_data_inventory, Loader=Loader)
            idel_utils.validate_inventory(data_inventory)

        # LOGGING
        self.logger.info('Change mode: {}'.format(change_mode))
        if ('Description' in data_changes):
            self.logger.info('Change\'s overall description: {}'.format(str(data_changes['Description'])))

        if (not raw_data_inventory):
            changes = data_changes['Changes']
        else:
            changes = data_inventory['Inventory']
            if (change_mode in [CHANGE_MODE_DESTROY,CHANGE_MODE_OFF]):
                changes.reverse()

        # Decorate changes
        decorated_changes = list()
        for i, change in enumerate(changes):
            self.logger.debug('i: {}'.format(i))

            # Eliminate inappropriate objects
            if (idel_utils.skip_object(change_mode, change)):
                continue

            # `cfn` blocks: force `Action` property
            if (change['Object']==STR_CFN):
                if ('Action' not in change):
                    change['Action'] = ''
                change['Action'] = idel_utils.override_cfn_action(change_mode, change['Action'])

            # `cfn` blocks in modes: provision/change/on
            # we need to convert the referred relative path template to string (Body)
            if (change['Object']==STR_CFN) and (change['Action']==STR_DEPLOY):
                with open(ARTIFACT_DIR+change['Template'], encoding='utf-8') as file:
                    template_body = file.read()
                change['TemplateBody'] = template_body

            decorated_changes.append(change)
        # /Decorate changes

        self.logger.info('Processing [{}] objects.'.format(len(decorated_changes)))
        return decorated_changes

    @log_on_start(logging.INFO, "Start getting continuation token.")
    @log_on_end(logging.INFO, "End getting continuation token. Return: {result!r}")
    def get_continuation_token(self):
        if 'continuationToken' in self.cp_job_data:
            # Sequence run
            continuation = json.loads(self.cp_job_data['continuationToken'])

            self.logger.info('Round #{}'.format(str(int(continuation['Sequence'])+1)))

        else:
            # First run
            # Fake continuationToken
            continuation = idel_utils.build_continuation_token(
                block='-1',
                status=STATUS_DONE,
                sequence=0
            )

            self.logger.info('First round!')
            self.logger.info('Environment variables: {}'.format(str(idel_utils.get_environment_variables())))

        return continuation

    @log_on_start(logging.INFO, "Old block is DONE. Going to process NEW change block.")
    @log_on_start(logging.DEBUG, "Old block is DONE. Going to process NEW change block: continuation: {continuation!r} | changes: {changes!r}")
    def process_new_block(self, continuation, changes):
        """
        """
        target_block_order = int(continuation['Block'])+1

        # Check: out of block?
        if (target_block_order+1 > len(changes)):
            # Yes. Out of block
            self.logger.info('There is NO more block to process.')
            self.cp_handler.put_job_success(self.cp_job_id, 'Job is complete.')

        else:
            # there is block to process
            # then process and get result
            self.logger.info('There is more block to process.')

            change = changes[target_block_order]
            self.logger.info('Do process. Change: {}'.format(str(change)))

            if ('Description' in change):
                self.logger.info('Description: {}'.format(change['Description']))

            case = self.process_new_block_case(change['Object'])
            run_result = case(change)

            # Prepare data for another run to continue the pipeline.
            self.continue_pipeline(target_block_order, continuation, change, run_result)

        return None

    #
    def process_new_block_case(self, case):
        run_cases = {
            STR_CFN: self.process_new_block_cfn,
            STR_AWS: self.process_new_block_aws
        }
        return run_cases[case]

    @log_on_start(logging.INFO, "Start processing NEW CloudFormation change block.")
    @log_on_end(logging.INFO, "End processing NEW CloudFormation change block. Return: {result!r}")
    def process_new_block_cfn(self, change):
        """
        """
        self.logger.info('Stack: {}'.format(change['Stack']))

        stack_result = {}
        if (change['Action']==STR_DEPLOY):
            parameters = []
            if ('Params' in change):
                params = change['Params']
                if (isinstance(params, dict)):
                    for key in params:
                        parameters.append({
                            'ParameterKey': str(key),
                            'ParameterValue': str(params[key])
                        })
                elif (isinstance(params, list)):
                    for param in params:
                        parameters.append({
                            'ParameterKey': str(param['Name']),
                            'ParameterValue': str(param['Value'])
                        })
                else:
                    self.logger.warn('Invalid format of parameters.')

            capabilities = []
            if ('Caps' in change):
                for cap in change['Caps']:
                    capabilities.append(cap)

            if self.cfn_handler.stack_exists(change['Stack']):
                stack_result = self.cfn_handler.update_stack(
                    stack_name=change['Stack'],
                    template_body=change['TemplateBody'],
                    parameters=parameters,
                    capabilities=capabilities
                )
            else:
                stack_result = self.cfn_handler.create_stack(
                    stack_name=change['Stack'],
                    template_body=change['TemplateBody'],
                    parameters=parameters,
                    capabilities=capabilities
                )

        elif (change['Action']==STR_DELETE):
            stack_result = self.cfn_handler.delete_stack(change['Stack'])

        else:
            raise Exception('Unknown action.')

        # Parse the result then process next
        parsed_result = self.cfn_parse_waiter_result(stack_result, change['Stack'])

        return parsed_result

    @log_on_start(logging.INFO, "Start processing NEW AWS change block.")
    @log_on_end(logging.INFO, "End processing NEW AWS change block. Return: {result!r}")
    def process_new_block_aws(self, change):
        """
        """
        self.logger.info('Action: {}'.format(change['Action']))

        aws_client = IdelClients()
        aws_client.setup_boto3_client(change['Service'], self.secret)

        try:
            result = aws_client.dynamic_call(change['Action'], change['Params'])
        except Exception as error:
            raise error

        # Just send AWS API request and do not mind the response
        return {
            'Done': True,
            'Result': result
        }

    @log_on_start(logging.INFO, "Old block is still in progress. Going to process OLD change block.")
    @log_on_start(logging.DEBUG, "Old block is still in progress. Going to process OLD change block: continuation: {continuation!r} | changes: {changes!r}")
    def process_old_block(self, continuation, changes):
        """
        """
        block_order = int(continuation['Block'])
        change = changes[block_order]
        self.logger.info('Do process. Change: {}'.format(str(change)))

        run_result = {}
        # cfn
        if (change['Object']==STR_CFN) and ('StackName' in continuation) and (change['Stack']==continuation['StackName']):
            run_result = self.process_old_block_cfn(continuation, change)

        # Prepare data for another run to continue the pipeline.
        self.continue_pipeline(block_order, continuation, change, run_result)

        return None

    @log_on_start(logging.INFO, "Start processing OLD CloudFormation change block.")
    @log_on_end(logging.INFO, "End processing OLD CloudFormation change block. Return: {result!r}")
    def process_old_block_cfn(self, continuation, change):
        """
        For CloudFormation only

        Output:
        {
            'StackName': '<from change>',
            'StackId': <Stack Id generated by AWS>,
            'WaitResult': <True|Waiter exception>,
            'Done': <True|False>
        }
        """
        # Get stack and its status
        stack = self.cfn_handler.get_stack(continuation['StackId'])
        stack_status = stack['StackStatus']

        stack_result = {}
        stack_result['StackName'] = continuation['StackName']
        stack_result['StackId'] = continuation['StackId']
        stack_result['Desire'] = continuation['StackDesire']

        # Check corresponding statuses
        result = idel_utils.stack_action_corresponding_statuses(change['Action'], stack_status)
        if (result=='COMPLETE'):
            stack_result['Done'] = True
            parsed_result = stack_result
        elif (result=='IN_PROGRESS'):
            # wait
            wait_for = 'stack_'+continuation['StackDesire'].lower()
            stack_result['WaitResult'] = self.cfn_handler.waiter(stack_name=continuation['StackId'], wait_for=wait_for)

            parsed_result = self.cfn_parse_waiter_result(stack_result)

        else:
            # Exception then exit
            raise Exception('Error manipulating CloudFormation stack {0} with id {1}'.format(continuation['StackName'], continuation['StackId']))

        return parsed_result

    @log_on_start(logging.INFO, "Start parsing wait result. Input: {stack_result!r}")
    @log_on_end(logging.INFO, "End parsing wait result. Return: {result!r}")
    def cfn_parse_waiter_result(self, stack_result, stack_name=None):
        """Since CloudFormation Waiter does not clearly return, we need to parse it

        Input:
            JSON:
            {
                'StackName': '<from change>',
                'StackId': <Stack Id generated by AWS>,
                'WaitResult': <True|Waiter exception>
            }
            if WaitResult is True then everything is good
            else we need to get stack status to see if it is good

            OR BOOLEAN: False

        Output:
            {
                'StackName': '<from change>',
                'StackId': <Stack Id generated by AWS>,
                'WaitResult': <True|Waiter exception>,
                'Done': <True|False>
            }
        """
        if (False==stack_result):
            return {
                'StackName': stack_name,
                'StackId': None,
                'WaitResult': True,
                'Done': True
            }

        if (stack_name):
            stack_result['StackName'] = stack_name

        if (True==stack_result['WaitResult']):
            stack_result['Done'] = True
        else:
            stack = self.cfn_handler.get_stack(stack_result['StackId'])
            stack_result['Done'] = idel_utils.stack_desire_corresponding_statuses(stack_result['Desire'], stack['StackStatus'])
            if (None==stack_result['Done']):
                # Un-handled statuses so we throw exception
                raise Exception('Error manipulating CloudFormation stack {0} (Id: {1})'.format(stack_result['StackName'], stack_result['StackId']), stack_result['WaitResult'])

        return stack_result

    @log_on_start(logging.INFO, "Start preparing for next run.")
    @log_on_start(logging.DEBUG, "Start preparing for next run: block_order: {block_order:d} | continuation: {continuation!r} | change: {change!r} | run_result: {run_result!r}")
    def continue_pipeline(self, block_order, continuation, change, run_result):
        """
        """
        if (not run_result):
            raise Exception('Unexpected exception. :)')

        # build continuationToken to continue
        next_continuation = idel_utils.build_continuation_token(
            block=block_order,
            sequence=int(continuation['Sequence'])+1
        )
        if (run_result['Done']):
            next_continuation['Status'] = STATUS_DONE
            next_continuation['Occurrence'] = None
        else:
            next_continuation['Status'] = STATUS_WAITING
            if (continuation['Occurrence']):
                next_continuation['Occurrence'] = int(continuation['Occurrence'])+1
            else:
                next_continuation['Occurrence'] = 1

        # cfn
        if ('Stack' in change):
            next_continuation['StackName'] = change['Stack']
        if ('StackId' in run_result):
            next_continuation['StackId'] = run_result['StackId']
        if ('Desire' in run_result):
            next_continuation['StackDesire'] = run_result['Desire']

        # continue
        self.cp_handler.continue_job_later(self.cp_job_id, json.dumps(next_continuation), 'Still in progress...')

        return None

    @log_on_start(logging.INFO, "exit_pipeline() | start | success: {success:b}")
    def exit_pipeline(self, success):
        """For debugging
        """
        if (success):
            self.cp_handler.put_job_success(self.cp_job_id, 'Exit!')
        else:
            self.cp_handler.put_job_failure(self.cp_job_id, 'Exit!')

        exit()
