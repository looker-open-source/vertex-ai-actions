import hmac
import json
import os
from flask import Response


# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#authentication
# authenticate all requests from Looker by evaluating authorization token
def authenticate(request):
    """Validates auth token secret set in request header"""
    if request.method != 'POST' or 'authorization' not in request.headers:
        error = 'Request must be POST with auth token'
        response = {'looker': {'success': False, 'message': error}}
        print(response)
        return Response(json.dumps(response), status=401, mimetype='application/json')
    else:
        expected_auth_header = 'Token token="{}"'.format(
            os.environ.get('LOOKER_AUTH_TOKEN'))
        submitted_auth = request.headers['authorization']
        if hmac.compare_digest(expected_auth_header, submitted_auth):
            return Response(status=200)

        else:
            error = 'Incorrect token'
            response = {'looker': {'success': False, 'message': error}}
            print(response)
            return Response(json.dumps(response), status=403, mimetype='application/json')


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
