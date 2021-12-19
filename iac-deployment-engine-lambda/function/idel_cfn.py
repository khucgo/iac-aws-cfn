# idel_cfn.py
import os
import botocore
import boto3
import logging
import urllib3
import json

CFN_WAITER_CONFIG = json.loads(os.environ['CFN_WAITER_CONFIG'])

class IdelCloudFormation:
    boto3_client = None
    logger = None
    role_arn = None

    def __init__(self):
        # Setup logging
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.os.environ['LOGGING_LEVEL'])

        # Log DEBUG
        self.logger.debug('Init class {}'.format(self.__str__()))

        return

    #
    def setup_boto3_client(self, credential):
        """Set up boto3 client within credentials of target AWS environment
        """
        logging.debug('Setting up boto3 low-level client for CloudFormation.')
        logging.debug('credential: {}'.format(str(credential)))
        self.boto3_client = boto3.client(
            'cloudformation',
            aws_access_key_id=credential['ACCESS_KEY_ID'],
            aws_secret_access_key=credential['SECRET_ACCESS_KEY'],
            region_name=credential['REGION']
        )

        if ('ROLE_NAME' in credential) and (credential['ROLE_NAME']):
            self.set_cfn_role_arn('arn:aws:iam::'+credential['ACCOUNT_NUMBER']+':role/'+credential['ROLE_NAME'])

        logging.debug('Finish setting up boto3 low-level client for CloudFormation.')

        return

    #
    def set_cfn_role_arn(self, role_arn):
        self.role_arn = role_arn
        return

    #
    def get_stack(self, stack_name):
        """ Describe stack

        Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html?highlight=cloudformation#CloudFormation.Client.describe_stacks
        """


        stacks = self.boto3_client.describe_stacks(StackName=stack_name)
        stack = stacks['Stacks'][0]

        self.logger.info('Get stack: {}'.format(stack_name))
        self.logger.info('Stack status: {}'.format(stack['StackStatus']))

        return stack

    #
    def get_stack_status(self, stack_name):
        """Get the status of an existing CloudFormation stack

        List of statuses: <'CREATE_IN_PROGRESS'|'CREATE_FAILED'|'CREATE_COMPLETE'|'ROLLBACK_IN_PROGRESS'|'ROLLBACK_FAILED'|'ROLLBACK_COMPLETE'|'DELETE_IN_PROGRESS'|'DELETE_FAILED'|'DELETE_COMPLETE'|'UPDATE_IN_PROGRESS'|'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'|'UPDATE_COMPLETE'|'UPDATE_ROLLBACK_IN_PROGRESS'|'UPDATE_ROLLBACK_FAILED'|'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS'|'UPDATE_ROLLBACK_COMPLETE'|'REVIEW_IN_PROGRESS'|'IMPORT_IN_PROGRESS'|'IMPORT_COMPLETE'|'IMPORT_ROLLBACK_IN_PROGRESS'|'IMPORT_ROLLBACK_FAILED'|'IMPORT_ROLLBACK_COMPLETE'>

        Reference: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-describing-stacks.html#w2ab1c23c15c17c11 > `Stack status codes`
        """
        self.logger.info('Get stack status: {}'.format(stack_name))

        stack = self.get_stack(stack_name)
        return stack['Stacks'][0]['StackStatus']

    #
    def stack_exists(self, stack_name):
        """Check if a stack exists or not

        Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html?highlight=cloudformation#CloudFormation.Client.describe_stacks
        """
        try:
            self.boto3_client.describe_stacks(StackName=stack_name)
            self.logger.info('Stack exists: {}'.format(stack_name))
            return True
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                self.logger.info('Stack NOT exist: {}'.format(stack_name))
                return False
            else:
                raise e

    #
    def update_stack(self, stack_name, template_body, parameters=[], capabilities=[], tags=[]):
        """Start a CloudFormation stack update
        Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html?highlight=cloudformation#CloudFormation.Client.update_stack
        """
        self.logger.info('Update stack: {}'.format(stack_name))

        result = {}
        try:
            params = {}
            params['StackName'] = stack_name
            params['TemplateBody'] = template_body
            params['Parameters'] = parameters
            params['Capabilities'] = capabilities
            params['Tags'] = tags
            if (self.role_arn):
                params['RoleARN'] = self.role_arn

            result = self.boto3_client.update_stack(**params)

            result['WaitResult'] = self.waiter(result['StackId'], 'stack_update_complete')

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Message'] == 'No updates are to be performed.':
                self.logger.error('No updates are to be performed.')
                return False
            else:
                raise Exception('Error updating CloudFormation stack "{0}"'.format(stack_name), e)

        result['Desire'] = 'UPDATE_COMPLETE'
        return result

    #
    def create_stack(self, stack_name, template_body, parameters=[], capabilities=[], tags=[]):
        """Starts a new CloudFormation stack creation

        Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html?highlight=cloudformation#CloudFormation.Client.create_stack
        """
        self.logger.info('Create stack: {}'.format(stack_name))

        result = {}
        try:
            params = {}
            params['StackName'] = stack_name
            params['TemplateBody'] = template_body
            params['Parameters'] = parameters
            params['Capabilities'] = capabilities
            params['Tags'] = tags
            if (self.role_arn):
                params['RoleARN'] = self.role_arn

            result = self.boto3_client.create_stack(**params)

            result['WaitResult'] = self.waiter(result['StackId'], 'stack_create_complete')

        except botocore.exceptions.ClientError as e:
            raise Exception('Error creating CloudFormation stack "{0}"'.format(stack_name), e)

        result['Desire'] = 'CREATE_COMPLETE'
        return result

    #
    def delete_stack(self, stack_name):
        """
        """
        self.logger.info('Delete stack: {}'.format(stack_name))

        is_existed = self.stack_exists(stack_name)
        if (not is_existed):
            return is_existed

        # Get stack_id
        stack = self.get_stack(stack_name)
        stack_id = stack['StackId']
        self.logger.info('Stack {} exists with id {}'.format(stack_name, stack_id))

        result = {}
        result['StackId'] = stack_id
        try:
            params = {}
            params['StackName'] = stack_id
            if (self.role_arn):
                params['RoleARN'] = self.role_arn

            self.boto3_client.delete_stack(**params)

            result['WaitResult'] = self.waiter(result['StackId'], 'stack_delete_complete')

        except botocore.exceptions.ClientError as e:
            raise Exception('Error deleting CloudFormation stack "{0}"'.format(stack_name), e)

        result['Desire'] = 'DELETE_COMPLETE'
        return result

    #
    def waiter(self, stack_name, wait_for):
        """
        """
        self.logger.info('Wait for stack {} to be {}'.format(stack_name, wait_for))
        try:
            waiter = self.boto3_client.get_waiter(wait_for)
            waiter.wait(
                StackName=stack_name,
                WaiterConfig=CFN_WAITER_CONFIG
            )
            self.logger.info('Wait is over. DESIRABLE. Desired: {}'.format(wait_for))
            return True
        except botocore.exceptions.WaiterError as e:
            self.logger.info('Wait is over. UN-DESIRABLE. Desired: {}'.format(wait_for))
            return e
            # raise Exception('Error waiting for CloudFormation stack "{0}"'.format(stack_name), e)
