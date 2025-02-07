import requests
import json
import os
from flask import request, Response
from icon import icon_data_uri
from utils import authenticate, handle_error, list_to_html, safe_cast, sanitize_and_load_json_str, store_state


BASE_DOMAIN = 'https://{}-{}.cloudfunctions.net/{}-'.format(os.environ.get(
    'REGION'), os.environ.get('PROJECT'), os.environ.get('ACTION_NAME'))
auth_url = (
        f"https://one-line--ofuat.sandbox.my.salesforce.com/services/oauth2/authorize?response_type=code"
        f"&client_id=3MVG9IUPIoRCZley1WC3YN5_t76aAzWV3gHHRnhm3Nn.MEqnhwJPkihZRAq_JLx8U6LQKP5Liz9lyLsni1nPb"
        f"&redirect_uri=https://one-line--ofuat.sandbox.my.salesforce.com/services/oauth2/token"
    )

# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#actions-list-endpoint
def action_list(request):
    """Return action hub list endpoint data for action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    response = {
        'label': 'Becky\'s Campaign Creator',
        'integrations': [{
            'name': os.environ.get('ACTION_NAME'),
            'label': os.environ.get('ACTION_LABEL'),
            'supported_action_types': ['query'],
            "icon_data_uri": icon_data_uri,
            'form_url': BASE_DOMAIN + 'form',
            'url': BASE_DOMAIN + 'execute',
            'supported_formats': ['json'],
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
        }]
    }

    print('returning integrations json')
    return Response(json.dumps(response), status=200, mimetype='application/json')

# todo add a def to handle the oauth login to be deployed as a cloud function
# steps:
# 1. get authentication code using the services/oauth2/authorize endpoint in SF
# 2. get the access token using the services/oauth2/token endpoint in SF
# 3. store the access token in the state_url using the utils.py store_state function

# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-form-endpoint
def action_form(request):
    """Return form endpoint data for action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    request_json = request.get_json()
    print(f"request_json: {request_json}")
    form_params = request_json['form_params']
    print(form_params)
    response_login = [    {
        'name': 'login',
        'type': 'oauth_link',
        'label': 'Log in',
        'description': 'Log in to your Salesforce account.',
        'oauth_url': auth_url,  # todo add url for the oauth login cloud function
    }]
    response_form = [{
        'name': 'campaign_name',
        'label': 'Campaigneee Name',
        'description': 'Identifying name of the campaign',
        'type': 'text',
        'required': True
    },
        {
        'name': 'start_date',
        'label': 'Start Date',
        'description': "Start date of the campaign",
        'type': 'text',
        'required': True
    },
        {
        'name': 'end_date',
        'label': 'End Date',
        'description': "End date of the campaign",
        'type': 'text',
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
    response = response_form
    # TODO add a logic if request_json have a token key (user is authenticated)
    # then set response to response_form, else set response to response_login
    print('returning form json: {}'.format(json.dumps(response)))
    return Response(json.dumps(response), status=200, mimetype='application/json')


# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-execute-endpoint
def action_execute(request):
    """Process form input and send data to Salesforce to create a new campaign"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth
    request_json = request.get_json()
    form_params = request_json['form_params']
    print(form_params)

    campaign_name = form_params['campaign_name']
    start_date = form_params['start_date']
    end_date = form_params['end_date']
    campaign_status = form_params['campaign_status']
    campaign_type = form_params['campaign_type']
    print(campaign_name)
    print(start_date)
    print(end_date)
    print(campaign_status)
    print(campaign_type)

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



    # todo set token = request_json['token'] for authorising the request to SF in the header here
    headers = {
        "Authorization": f"Bearer 00DBA0000011Ivd!AQEAQNRNdW8dgT7tTQ6.NkgQr.377mAo0fKFhembqzu3D2XT_nDjS11MG4.SpLCRxcMeMTxvNbZjYdZSu7BpMVZ_ig3HUGpy",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=payload)

    if response.status_code in [200, 201]:
        return Response(status=200, mimetype="application/json")
    else:
        return Response(status=response.status_code, mimetype="application/json")