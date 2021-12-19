# idel_utils.py

import os
import json

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

# Sample continuationToken
"""
{
    "StackName": "<STACK_NAME_HERE>",
    "StackId": "<STACK_ID_HERE>",
    "StackDesire": "<CREATE_COMPLETE|UPDATE_COMPLETE|DELETE_COMPLETE>",
    "Block": "<Number>",
    "Status": "<DONE|WAITING>",
    "Occurrence": "<None|Number>",
    "Sequence": "<Number>"
}
"""
sample_continuation_token = {
    "StackName": None,
    "StackId": None,
    "StackDesire": None,
    "Block": None,
    "Status": None,
    "Occurrence": None,
    "Sequence": None
}

def get_user_params(job_data):
    """Decodes the JSON user parameters and validates the required properties.

    Args:
        job_data: The job data structure containing the UserParameters string which should be a valid JSON structure

    Returns:
        The JSON parameters decoded as a dictionary.

    Raises:
        Exception: The JSON can't be decoded or a property is missing.

    """

    try:
        # Get the user parameters which contain the stack, artifact and file settings
        user_parameters = job_data['actionConfiguration']['configuration']['UserParameters']
        # VMQ - workaround
        user_parameters = user_parameters.replace('\n', ' ')
        decoded_parameters = json.loads(user_parameters)

    except Exception as e:
        # We're expecting the user parameters to be encoded as JSON
        # so we can pass multiple values. If the JSON can't be decoded
        # then fail the job with a helpful message.
        raise Exception('UserParameters could not be decoded as JSON: '+str(e))

    return decoded_parameters

def get_sample_continuation_token():
    return sample_continuation_token.copy()

def build_continuation_token(stack_name=None, stack_id=None, stack_desire=None, block=None, status=None, occurrence=None, sequence=None):
    continuation_token = sample_continuation_token.copy()
    continuation_token['StackName'] = stack_name
    continuation_token['StackId'] = stack_id
    continuation_token['StackDesire'] = stack_desire
    continuation_token['Block'] = block
    continuation_token['Status'] = status
    continuation_token['Occurrence'] = occurrence
    continuation_token['Sequence'] = sequence
    return continuation_token

def stack_action_corresponding_statuses(action, stack_status):
    ret = 'COMPLETE|IN_PROGRESS|UNKNOWN'
    if ((action=='deploy') and (stack_status in ['UPDATE_COMPLETE', 'CREATE_COMPLETE'])) or ((action=='delete') and (stack_status in ['DELETE_COMPLETE'])):
        ret = 'COMPLETE'
    elif ((action=='deploy') and (stack_status in ['UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS', 'CREATE_IN_PROGRESS'])) or ((action=='delete') and (stack_status in ['DELETE_IN_PROGRESS'])):
        ret = 'IN_PROGRESS'
    else:
        ret = 'UNKNOWN'
    return ret

def stack_desire_corresponding_statuses(desire, stack_status):
    ret = None
    if (stack_status==desire):
        # Done is True that means be able to process new block in next function
        ret = True
    elif (desire=='CREATE_COMPLETE' and stack_status=='CREATE_IN_PROGRESS'):
        ret = False
    elif (desire=='UPDATE_COMPLETE' and stack_status in ['UPDATE_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS']):
        ret = False
    elif (desire=='DELETE_COMPLETE' and stack_status=='DELETE_IN_PROGRESS'):
        ret = False
    else:
        # Unhandled statuses
        # Exception
        ret = None

    return ret

def get_environment_variables():
    return {
        'LOGGING_LEVEL': os.environ['LOGGING_LEVEL'],
        'SECRET_NAME': os.environ['SECRET_NAME'],
        'ARTIFACT_DIR': os.environ['ARTIFACT_DIR'],
        'CHANGES_FILE': os.environ['CHANGES_FILE'],
        'WAITING_OCCURRENCE': os.environ['WAITING_OCCURRENCE'],
        'CFN_WAITER_CONFIG': os.environ['CFN_WAITER_CONFIG']
    }

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

def validate_inventory(data_inventory):
    """
    """
    # Inventory
    if ('Inventory' not in data_inventory):
        raise Exception('Broken inventory file: Missing \'Inventory\' item.')
    elif (0==len(data_inventory['Inventory'])):
        raise Exception('Broken inventory file: \'Inventory\' item is empty.')

    return True

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
