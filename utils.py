import hmac
import json
import os
import pandas as pd
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
            error = handle_error('Incorrect token', 403)
            return error


def handle_error(message, status):
    """Prints and return error message"""
    print(message)
    response = {'looker': {'success': False, 'message': message}}
    return Response(json.dumps(response), status=status, mimetype='application/json')


def safe_cast(input, to_type, min, max, default=None):
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


def list_to_html(list):
    df = pd.DataFrame(data=list)
    table = df.to_html()
    return table.replace('\n', '')
