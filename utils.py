import hmac
import json
import os
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
