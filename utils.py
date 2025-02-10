import hmac
import json
import os
import base64
import pandas as pd
import requests
from flask import Response


# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#authentication
# authenticate all requests from Looker by evaluating authorization token
def authenticate(request):
    """Validates auth token secret set in request header"""
    if request.method != 'POST' or 'authorization' not in request.headers:
        error = handle_error('Request must be POST with auth token', 401)
        return error
    else:
        expected_auth_header = 'Token token="{}"'.format(
            os.environ.get('LOOKER_AUTH_TOKEN'))
        submitted_auth = request.headers['authorization']
        if hmac.compare_digest(expected_auth_header, submitted_auth):
            return Response(status=200)

        else:
            error = handle_error(f'Incorrect token: {expected_auth_header}', 403)
            return error


def handle_error(message, status):
    """Prints and return error message"""
    print(message)
    response = {'looker': {'success': False, 'message': message}}
    return Response(json.dumps(response), status=status, mimetype='application/json')


def safe_cast(input, to_type, min, max, default):
    """Casts form input values to correct type and returns default if invalid"""
    try:
        value = to_type(input)
        if (value > max or value < min):
            return default
        else:
            return value
    except (ValueError, TypeError):
        return default


def sanitize_and_load_json_str(s: str, strict=False):
    json_string = s
    prev_pos = -1
    curr_pos = 0
    while curr_pos > prev_pos:
        prev_pos = curr_pos
        try:
            return json.loads(json_string, strict=strict)
        except json.JSONDecodeError as err:
            curr_pos = err.pos
            if curr_pos <= prev_pos:
                raise err
            prev_quote_index = json_string.rfind('"', 0, curr_pos)
            json_string = json_string[:prev_quote_index] + \
                "\\" + json_string[prev_quote_index:]


def list_to_html(data_list):
    """
    Converts a list of data into an HTML table.

    Args:
        data_list: The list of data to convert.

    Returns:
        A string containing the HTML table.
    """
    df = pd.DataFrame(data=data_list)
    table = df.to_html()
    return table.replace('\n', '')


def store_state(state_url, data):
    """Stores data to the provided stateUrl.

    Args:
        state_url: The URL to store the data.
        data: The data to store, as a dictionary.

    Returns:
        True if the data was stored successfully, False otherwise.
    """
    try:
        response = requests.post(state_url, json=data, timeout=10)
        response.raise_for_status()
        print(f"Successfully stored data in state: {data}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error storing data in state: {e}")
        return False

def reset_state(state_url):
    """Resets the state at the provided state URL.

    Args:
        state_url: The URL to reset the state.

    Returns:
        True if the state was reset successfully, False otherwise.
    """
    try:
        response = requests.post(state_url, json={'data': 'reset'}, timeout=10)
        response.raise_for_status()
        print("Successfully reset state")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error resetting state: {e}")
        return False

def encode_state(state_url):
    """Encodes a state URL using Base64."""
    # Encode the URL to bytes
    encoded_bytes = base64.urlsafe_b64encode(state_url.encode())
    # Convert the encoded bytes to a string
    encoded_string = encoded_bytes.decode()
    return encoded_string

def decode_state(encoded_state):
    """Decodes a state value using Base64."""
    # Decode the string to bytes
    decoded_bytes = base64.urlsafe_b64decode(encoded_state.encode())
    # Convert the decoded bytes to a string
    decoded_string = decoded_bytes.decode()
    return decoded_string
