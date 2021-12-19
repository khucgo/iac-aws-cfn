import os
import logging

from idel_iac import IdelIaC

NAME = 'IaC Deployment Engine Lambda'
VERSION = '0.1.4'

logger = logging.getLogger()
logger.setLevel(logging.os.environ['LOGGING_LEVEL'])

def lambda_handler(event, context):
    """The Lambda function handler

    Args:
        event: The event passed by Lambda
        context: The context passed by Lambda

    """
    logger.info('{} version {}'.format(NAME, VERSION))
    logger.info('Function begin.')
    logger.debug('event: {}'.format(str(event)))
    logger.debug('context: {}'.format(str(context)))

    iac_handler = IdelIaC(event, context)
    iac_handler.process()

    logger.info('Function complete.')
    return True
