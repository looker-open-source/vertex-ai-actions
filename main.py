import requests
import json
import os
import base64
from flask import request, Response, redirect
from icon import icon_data_uri
import utils

BASE_DOMAIN = f"https://{os.environ.get('REGION')}-{os.environ.get('PROJECT')}.cloudfunctions.net/{os.environ.get('ACTION_NAME')}-"

# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#actions-list-endpoint
def action_list(request):
    """Return action hub list endpoint data for action"""
    auth = utils.authenticate(request)
    if auth.status_code != 200:
        return auth

    response = {
        'label': 'POC Action Hub',
        'integrations': [
            {
                'name': os.environ.get('ACTION_NAME'),
                'label': os.environ.get('ACTION_LABEL'),
                'supported_action_types': ['query', 'cell', 'dashboard'],
                "icon_data_uri": "https://pics.freeicons.io/uploads/icons/png/18502552271551942822-512.png",
                'form_url': BASE_DOMAIN + 'form',
                'url': BASE_DOMAIN + 'execute',
                'supported_formats': ['json', 'csv_zip'],
                'required_fields': [{"any_tag": ["sfdc_lead_id"]}],
                'supported_formattings': ['formatted'],
                'supported_visualization_formattings': ['noapply'],
                'params': [
                    {
                        'description': "Salesforce domain name, e.g. https://MyDomainName.my.salesforce.com",
                        'label': "Salesforce domain",
                        'name': "salesforce_domain",
                        'required': True,
                        'sensitive': False
                    }
                ],
                'uses_oauth': True
            }
        ]
    }

    print('returning integrations json')
    return Response(json.dumps(response), status=200, mimetype='application/json')

# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-form-endpoint
def action_form(request):
    """Return form endpoint data for action"""
    auth = utils.authenticate(request)
    if auth.status_code != 200:
        return auth

    response = [{
            'name': 'campaign_name',
            'label': 'Campaign Name',
            'description': 'Identifying name of the campaign',
            'type': 'text',
            'required': True
        },
            {
            'name': 'start_date',
            'label': 'Start Date',
            'description': "Start date of the campaign",
            'type': 'date',
            'required': True
        },
            {
            'name': 'end_date',
            'label': 'End Date',
            'description': "End date of the campaign",
            'type': 'date',
            'required': True
        },
            {
            'name': 'campaign_status',
            'label': 'Campaign Status',
            'description': "Status of the campaign",
            'type': 'text',
            'required': True
        },
            {
            'name': 'campaign_type',
            'label': 'Campaign Type',
            'description': "Type of the campaign",
            'type': 'text',
            'required': True
        }
    ]
    print(f'returning form json: {json.dumps(response)}')
    return Response(json.dumps(response), status=200, mimetype='application/json')




# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-execute-endpoint
def action_execute(request):
    """Process form input and send data to Salesforce to create a new campaign"""
    auth = utils.authenticate(request)
    if auth.status_code != 200:
        return auth
    request_json = request.get_json()
    form_params = request_json['form_params']

    # get token using username/password
    url = 'https://one-line--ofuat.sandbox.my.salesforce.com/services/oauth2/token'
    client_id = os.environ.get('SALESFORCE_CLIENT_ID')
    client_secret = os.environ.get('SALESFORCE_CLIENT_SECRET')
    username = os.environ.get('SALESFORCE_USERNAME')
    password = os.environ.get('SALESFORCE_PASSWORD')

    payload = {'grant_type': 'password',
    'client_id': client_id,
    'client_secret': client_secret,
    'username': username,
    'password': password}
    headers = {}

    print(f'payload: {payload}')
    response = requests.request("POST", url, headers=headers, data=payload, timeout = 10)
    print(f'response: {response.json()}')
    token = response.json()['access_token']

    try:
        campaign_name = form_params['campaign_name']
        start_date = form_params['start_date']
        end_date = form_params['end_date']
        campaign_status = form_params['campaign_status']
        campaign_type = form_params['campaign_type']
    except KeyError as e:
        return utils.handle_error(f"Missing required parameter: {e}", 400)

    # create campaign via api
    url = "https://one-line--ofuat.sandbox.my.salesforce.com/services/data/v63.0/composite/sobjects"
    payload = json.dumps({
        "allOrNone": False,
        "records": [
            {
                "attributes": {"type": "Campaign"},
                "Name": campaign_name,
                "StartDate" : start_date,
                "EndDate" : end_date,
                "Status" : campaign_status,
                "Type" : campaign_type
            }
        ]
    })

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print(f'create campaign payload: {payload}')
    print(f'create campaign headers: {headers}')
    response = requests.post(url, headers=headers, data=payload, timeout=10)
    print(f'create campaign response: {response.json()}')
    print(f'create campaign response status: {response.status_code}')
    if response.status_code in [200, 201] and response.json()[0]['success']:
        return Response(status=200, mimetype="application/json")
    else:
        return Response(status=response.status_code, mimetype="application/json", response=json.dumps(response.json()))