import os
import sys
import getopt
import subprocess
import yaml
from yaml import load, dump, Loader, Dumper
import datetime
import logging

import botocore
import boto3
import urllib3

NAME = 'IaC Deployment Engine Standalone'
VERSION = '0.1.4'

#
logging.basicConfig(level=logging.INFO)
logging.info('{} version {}'.format(NAME, VERSION))

# Constants
STR_CFN = 'cfn'
STR_AWS = 'aws'
STR_KUBECTL = 'kubectl'
STR_DEPLOY = 'deploy'
STR_DELETE = 'delete'
CHANGE_MODE_CHANGE = 'change'
CHANGE_MODE_PROVISION = 'provision'
CHANGE_MODE_DESTROY = 'destroy'
CHANGE_MODE_ON = 'on'
CHANGE_MODE_OFF = 'off'
INVENTORY_FILE = '.inventory.yaml'
NOTHING = 'nothing'
LOGGING_LEVEL = 'INFO'

command_help = '''
  ides.py
-p <value> : absolute or relative path to approved-deploy repository
-a <value> : aws named profile; ref: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html
-c <value> : will run `.changes.<value>.yaml` file instead of the default (`.changes.yaml`)
-t : dry-run locally
-h : print this help
'''

# Library: Get parameters
def get_params(argv):
    params = {'repo_path': '.', 'change_profile': '', 'aws_profile': '', 'dry_run': False}
    try:
        opts, args = getopt.getopt(argv,"hp:c:a:t")
        logging.debug('opts: {}'.format(opts))
        logging.debug('args: {}'.format(args))
    except getopt.GetoptError:
        logging.info(command_help)
        sys.exit(2)
    for opt, arg in opts:
        if (opt=='-h'):
            logging.info(command_help)
            sys.exit()
        elif opt in ('-p'):
            params['repo_path'] = arg
        elif opt in ('-c'):
            params['change_profile'] = arg
        elif opt in ('-a'):
            params['aws_profile'] = arg
        elif opt in ('-t'):
            params['dry_run'] = True
    logging.info('Parameters: {}'.format(str(params)))
    return params

def log_time(prefix):
    logging.info('{}: {}'.format(str(prefix), str(datetime.datetime.now())))

# Function: execute aws command
def process_aws(params, aws_command):
    log_time('Begin')
    if (not aws_command):
        log_time('End')
        return True
    if (params['aws_profile']):
        aws_command.append('--profile')
        aws_command.append(params['aws_profile'])
    logging.info('Executing command: {}'.format(' '.join(aws_command)))
    if (params['dry_run']):
        logging.info('Exit due to dry-run mode.')
        log_time('End')
        return True
    out = subprocess.Popen(aws_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    logging.info(stdout)
    logging.error(stderr)
    log_time('End')
    return True

def iac_cfn(params, item):
    wait_command = ()
    aws_command = list()
    aws_command.append('aws')
    aws_command.append('cloudformation')
    if (item['Action']=='delete'):
        aws_command.append('delete-stack')
        aws_command.append('--stack-name')
        aws_command.append(item['Stack'])
        wait_command = ['aws', 'cloudformation', 'wait', 'stack-delete-complete', '--stack-name', item['Stack']]
    elif (item['Action']=='deploy'):
        aws_command.append('deploy')
        aws_command.append('--stack-name')
        aws_command.append(item['Stack'])
        aws_command.append('--template-file')
        aws_command.append('{}/{}'.format(params['repo_path'], item['Template']))
        if ('Params' in item):
            cfn_params = item['Params']
            aws_command.append('--parameter-overrides')
            if (isinstance(cfn_params, dict)):
                for key in cfn_params:
                    aws_command.append('{}={}'.format(key, cfn_params[key]))
            elif (isinstance(cfn_params, list)):
                for cfn_param in cfn_params:
                    aws_command.append('{}={}'.format(cfn_param['Name'], cfn_param['Value']))
            else:
                raise Exception('Invalid format of parameters.')
    else:
        logging.error('Action {} is not supported.'.format(item['Action']))

    if ('Caps' in item) and (len(item['Caps'])>0):
        aws_command.append('--capabilities')
        for capability in item['Caps']:
            aws_command.append(capability)

    if ('CFN_ROLE_ARN' in os.environ) and (len(os.environ['CFN_ROLE_ARN'])):
        aws_command.append('--role-arn')
        aws_command.append(os.environ['CFN_ROLE_ARN'])

    result = process_aws(params, aws_command)
    if (wait_command and result):
        result = process_aws(params, wait_command)
    return result

# DEPRECATED
def iac_aws_cli(params, item):
    aws_command = list()
    aws_command.append('aws')
    command = item['Command']
    if (isinstance(command, str)):
        aws_command.extend(command.split())
    elif (isinstance(command, list)):
        aws_command.extend(command)
    else:
        logging.error('Exit due to syntax error!')
        return False

    result = process_aws(params, aws_command)
    return result

def iac_aws(params, item):
    if (params['dry_run']):
        if (item['Params']):
            logging.info('{}.client.{}({})'.format(item['Service'], item['Action'], item['Params']))
        else:
            logging.info('{}.client.{}()'.format(item['Service'], item['Action']))
        logging.info('Exit due to dry-run mode.')
        return True

    aws_client = AWSClients()
    aws_client.setup_boto3_client_with_profile_name(item['Service'], params['aws_profile'])

    try:
        result = aws_client.dynamic_call(item['Action'], item['Params'])
    except Exception as error:
        raise error

    # Just send AWS API request and do not mind the response
    return {
        'Done': True,
        'Result': result
    }

def iac_kubectl():
    return True

run_cases = {
    'cfn': iac_cfn,
    'aws': iac_aws,
    'kubectl': iac_kubectl
}

class AWSClients:
    session = None
    boto3_client = None
    logger = None
    role_arn = None

    def __init__(self):
        # Setup logging
        self.logger = logging.getLogger()
        self.logger.setLevel(LOGGING_LEVEL)

        # Log DEBUG
        self.logger.debug('Init class {}'.format(self.__str__()))

        return

    #
    def setup_boto3_client_with_profile_name(self, service, profile_name):
        """Set up boto3 client within credentials of target AWS environment
        """
        logging.debug('Setting up boto3 low-level client for {}.'.format(service))
        self.session = boto3.Session(profile_name=profile_name)
        self.boto3_client = self.session.client(service)
        logging.debug('Finish setting up boto3 low-level client for {}.'.format(service))

        return

    #
    def setup_boto3_client_with_credential(self, service, credential):
        """Set up boto3 client within credentials of target AWS environment
        """
        logging.debug('Setting up boto3 low-level client for {}.'.format(service))
        logging.debug('credential: {}'.format(str(credential)))
        self.boto3_client = boto3.client(
            service,
            aws_access_key_id=credential['ACCESS_KEY_ID'],
            aws_secret_access_key=credential['SECRET_ACCESS_KEY'],
            region_name=credential['REGION']
        )
        logging.debug('Finish setting up boto3 low-level client for {}.'.format(service))

        return

    #
    def dynamic_call(self, action, params):
        func = getattr(self.boto3_client, action, NOTHING)
        if (NOTHING==func):
            raise Exception('Function \'{}\' not found!'.format(action))

        result = None
        try:
            if (params):
                result = func(**params)
            else:
                result = func()
        except botocore.exceptions.ClientError as error:
            # Put your error handling logic here
            raise error
        except botocore.exceptions.ParamValidationError as error:
            raise ValueError('The parameters you provided are incorrect: {}'.format(error))

        return result

class AWSUtils:
    @staticmethod
    def validate_changes(data_changes):
        """
        """
        # Mode
        if ('Mode' not in data_changes):
            raise Exception('Broken changes file: Missing \'Mode\' item.')
        elif (data_changes['Mode'] not in [CHANGE_MODE_CHANGE, CHANGE_MODE_PROVISION, CHANGE_MODE_DESTROY, CHANGE_MODE_ON, CHANGE_MODE_OFF]):
            raise Exception('Broken changes file: \'Mode: {}\' not supported.'.format(data_changes['Mode']))
        elif (data_changes['Mode']==CHANGE_MODE_CHANGE):
            if ('Changes' not in data_changes):
                raise Exception('Broken changes file: Missing \'Changes\' item.')
            elif (0==len(data_changes['Changes'])):
                raise Exception('Broken changes file: \'Changes\' item is empty.')
        else:
            pass

        return True

    @staticmethod
    def validate_inventory(data_inventory):
        """
        """
        # Inventory
        if ('Inventory' not in data_inventory):
            raise Exception('Broken inventory file: Missing \'Inventory\' item.')
        elif (0==len(data_inventory['Inventory'])):
            raise Exception('Broken inventory file: \'Inventory\' item is empty.')

        return True

    @staticmethod
    def skip_object(change_mode, change):
        """
        If `Mode` is `change`: we do not care about the `Conditions`
        Else:
            If `cfn` objects:
                - We can omit the `Conditions`, objects will be involed when `Mode` is `provision` or `destroy`. (Original design. Backward compatibility.)
                - In case `Conditions` is declared, objects will be involed when `Mode` matches with `Conditions`.
            If `aws` objects: we must declare `Conditions` and match with `Mode`, or else the engine will skip that Object/Block.

        OR

        If `Mode` is `change`: we do not care about the `Conditions`
        Else:
            If we omit the `Conditions`:
                - Only `cfn` objects are involed when `Mode` is `provision` or `destroy`. (Original design. Backward compatibility.)
                - Others will be skipped.
            Else:
                Objects will be involed when `Mode` matches with `Conditions`.

        Return:
            - `True` means skipped
            - `False` means involved
        """
        if (change_mode!=CHANGE_MODE_CHANGE):
            if ('Conditions' not in change):
                if (change['Object']==STR_CFN) and (change_mode in [CHANGE_MODE_PROVISION,CHANGE_MODE_DESTROY]):
                    return False
                return True
            elif (change_mode not in change['Conditions']):
                return True
        return False

    @staticmethod
    def override_cfn_action(change_mode, original_action):
        """
        """
        mappings = {
            CHANGE_MODE_PROVISION: STR_DEPLOY,
            CHANGE_MODE_DESTROY: STR_DELETE,
            CHANGE_MODE_ON: STR_DEPLOY,
            CHANGE_MODE_OFF: STR_DELETE
        }

        if (change_mode not in mappings):
            return original_action

        return mappings[change_mode]

def main():
    """
    Process
    """
    # Program's parameters
    params = get_params(sys.argv[1:])

    # Read deployment script file
    if (not params['change_profile']):
        changes_file = '.changes.yaml'
    else:
        changes_file = '.changes.'+params['change_profile']+'.yaml'
    logging.info('Processing file: {}'.format(changes_file))
    with open(params['repo_path']+'/'+changes_file, encoding='utf-8') as file:
        raw_data_changes = file.read()
    data_changes = yaml.load(raw_data_changes, Loader=Loader)
    AWSUtils.validate_changes(data_changes)

    change_mode = data_changes['Mode']
    raw_data_inventory = None
    data_inventory = None

    if (change_mode in [CHANGE_MODE_PROVISION, CHANGE_MODE_DESTROY, CHANGE_MODE_ON, CHANGE_MODE_OFF]):
        with open(params['repo_path']+'/'+INVENTORY_FILE, encoding='utf-8') as file:
            raw_data_inventory = file.read()
        data_inventory = yaml.load(raw_data_inventory, Loader=Loader)
        AWSUtils.validate_inventory(data_inventory)

    # LOGGING
    logging.info('Change mode: {}'.format(change_mode))
    if ('Description' in data_changes):
        logging.info('Change''s overall description: {}'.format(str(data_changes['Description'])))

    if (not raw_data_inventory):
        changes = data_changes['Changes']
    else:
        changes = data_inventory['Inventory']
        if (change_mode in [CHANGE_MODE_DESTROY,CHANGE_MODE_OFF]):
            changes.reverse()

    # Decorate changes
    decorated_changes = list()
    for i, change in enumerate(changes):
        logging.debug('i: {}'.format(i))

        # Eliminate inappropriate objects
        if (AWSUtils.skip_object(change_mode, change)):
            continue

        # `cfn` blocks: force `Action` property
        if (change['Object']==STR_CFN):
            if ('Action' not in change):
                change['Action'] = ''
            change['Action'] = AWSUtils.override_cfn_action(change_mode, change['Action'])

        # # `cfn` blocks in modes: provision/change/on
        # # we need to convert the referred relative path template to string (Body)
        # if (change['Object']==STR_CFN) and (change['Action']==STR_DEPLOY):
        #     with open(ARTIFACT_DIR+change['Template'], encoding='utf-8') as file:
        #         template_body = file.read()
        #     change['TemplateBody'] = template_body

        decorated_changes.append(change)
    logging.info('Processing [{}] objects.'.format(len(decorated_changes)))
    # /Decorate changes

    for item in decorated_changes:
        run_case = run_cases.get(item['Object'])
        result = run_case(params, item)
        logging.info('Result: {}'.format(str(result)))

if __name__ == "__main__":
    main()
