# idel_clients.py
import os
import botocore
import boto3
import logging
import urllib3
import json

NOTHING = 'nothing'

class IdelClients:
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
    def setup_boto3_client(self, service, credential):
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
