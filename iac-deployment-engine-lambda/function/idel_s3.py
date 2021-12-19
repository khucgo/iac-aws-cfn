# idel_s3.py

from boto3.session import Session
import botocore
import os
import logging
import zipfile
import glob

class IdelS3:
    boto3_client = None
    logger = None

    def __init__(self, credential):
        # Setup logging
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.os.environ['LOGGING_LEVEL'])

        # Setup S3 session
        self.setup_s3_client(credential)

        # Log DEBUG
        self.logger.debug('Init class {}'.format(self.__str__()))

        return

    #
    def setup_s3_client(self, credential):
        """Creates an S3 client

        Uses the credentials passed in the event by CodePipeline. These
        credentials can be used to access the artifact bucket.

        Args:
            job_data: The job data structure

        Returns:
            An S3 client with the appropriate credentials

        """
        key_id = credential['accessKeyId']
        key_secret = credential['secretAccessKey']
        session_token = credential['sessionToken']

        session = Session(aws_access_key_id=key_id,
            aws_secret_access_key=key_secret,
            aws_session_token=session_token)
        self.boto3_client = session.client('s3', config=botocore.client.Config(signature_version='s3v4'))
        return

    #
    def download_artifact(self, s3_bucket, s3_object, af_dir):
        """Gets the artifact

        Downloads the artifact from the S3 artifact store to a temporary file
        then extracts the zip and returns the path containing the CloudFormation
        templates and changes.

        Args:
            s3_bucket:
            s3_object:
            af_dir: artifact dir

        Returns:
            The path to the deployment materials

        Raises:
            Exception: Any exception thrown while downloading the artifact or unzipping it

        """
        self.logger.info('Download artifact from S3.')

        af_tmp = '/tmp/af_tmp.zip'

        self.boto3_client.download_file(s3_bucket, s3_object, af_tmp)
        af = zipfile.ZipFile(af_tmp)
        af.extractall(af_dir)
        af.close()
        os.remove(af_tmp)

        # log debug
        self.logger.debug('Listing...')
        for filename in glob.iglob(af_dir + '**/**', recursive=True):
            self.logger.debug(filename)
        self.logger.debug('End listing.')

        return af_dir
