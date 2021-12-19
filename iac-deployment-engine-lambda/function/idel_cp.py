# idel_cp.py
import os
import boto3
import logging

class IdelCodePipeline:
    """
    """
    boto3_client = None
    logger = None

    def __init__(self):
        # Setup logging
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.os.environ['LOGGING_LEVEL'])

        # Setup boto3 client
        self.boto3_client = boto3.client('codepipeline')

        # Log DEBUG
        self.logger.debug('Init class {}'.format(self.__str__()))

        return

    #
    def continue_job_later(self, job, continuation_token, message):
        """Notify CodePipeline of a continuing job

        This will cause CodePipeline to invoke the function again with the
        supplied continuation token.

        Use the continuation token to keep track of any job execution state
        This data will be available when a new job is scheduled to continue the current execution

        Args:
            job: The JobID
            message: A message to be logged relating to the job status
            continuation_token: The continuation token
                Eg: continuation_token = json.dumps({'previous_job_id': job})

        Raises:
            Exception: Any exception thrown by .put_job_success_result()

        """

        self.logger.info('Put job continuation: {}'.format(str(message)))
        self.boto3_client.put_job_success_result(jobId=job, continuationToken=continuation_token)

    #
    def put_job_success(self, job_id, message):
        """Notify CodePipeline of a successful job

        Args:
            job: The CodePipeline job ID
            message: A message to be logged relating to the job status

        Raises:
            Exception: Any exception thrown by .put_job_success_result()

        """

        self.logger.info('Put job success: {}'.format(str(message)))
        self.boto3_client.put_job_success_result(jobId=job_id)

    #
    def put_job_failure(self, job_id, message):
        """Notify CodePipeline of a failed job

        Args:
            job: The CodePipeline job ID
            message: A message to be logged relating to the job status

        Raises:
            Exception: Any exception thrown by .put_job_failure_result()

        """

        self.logger.info('Put job failure: {}'.format(str(message)))
        self.boto3_client.put_job_failure_result(jobId=job_id, failureDetails={'message': message, 'type': 'JobFailed'})
