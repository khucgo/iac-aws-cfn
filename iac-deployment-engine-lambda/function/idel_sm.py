import os
import boto3
import json
import logging

class IdelSecretsManager:
    """To play with SecretsManager service through boto3
    """
    boto3_client = None
    logger = None

    def __init__(self):
        # Setup logging
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.os.environ['LOGGING_LEVEL'])

        # Setup boto3 client
        self.boto3_client = boto3.client('secretsmanager')

        # Log DEBUG
        self.logger.debug('Init class {}'.format(self.__str__()))

        return

    #
    def get_secret(self, secret_name):
        """
        """
        self.logger.debug('secret_name: {}'.format(secret_name))

        secret = self.boto3_client.get_secret_value(
            SecretId=secret_name
        )
        self.logger.debug('secret: {}'.format(str(secret)))

        secret_data = json.loads(secret['SecretString'])

        return secret_data
