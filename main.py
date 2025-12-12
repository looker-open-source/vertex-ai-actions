import json
import os
import requests
from flask import Response
from icon import icon_data_uri
from utils import authenticate, handle_error, list_to_html, safe_cast, sanitize_and_load_json_str
from gemini_api import model_with_limit_and_backoff, reduce

BASE_DOMAIN = 'https://{}-{}.cloudfunctions.net/{}-'.format(os.environ.get(
    'REGION'), os.environ.get('PROJECT'), os.environ.get('ACTION_NAME'))
OUTPUT_TOKEN_LIMIT = int(os.environ.get('OUTPUT_TOKEN_LIMIT', '8192'))

def action_list(request):
    """Return action hub list endpoint data for action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    response = {
        'label': 'Looker Vertex AI',
        'integrations': [{
            'name': os.environ.get('ACTION_NAME'),
            'label': os.environ.get('ACTION_LABEL'),
            'supported_action_types': ['query'],
            'icon_data_uri': icon_data_uri,
            'form_url': 'https://' + request.host.rstrip('/') + '/form' if os.environ.get('GEN2_ROUTER') == 'true' else BASE_DOMAIN + 'form',
            'url': 'https://' + request.host.rstrip('/') + '/execute' if os.environ.get('GEN2_ROUTER') == 'true' else BASE_DOMAIN + 'execute',
            'supported_formats': ['json'],
            'supported_formattings': ['formatted'],
            'supported_visualization_formattings': ['noapply'],
            'params': []
        }]
    }

    print('returning integrations json')
    return Response(json.dumps(response), status=200, mimetype='application/json')

# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-form-endpoint
def action_form(request):
    """Return form endpoint data for action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    request_json = request.get_json()
    form_params = request_json['form_params']
    print(form_params)

    default_question = 'Can you summarize the following dataset in 10 bullet points?'
    if 'question' in form_params:
        default_question = form_params['question']

    default_row_or_all = 'all'
    if 'row_or_all' in form_params:
        default_row_or_all = form_params['row_or_all']

    default_params = 'yes'
    if 'default_params' in form_params:
        default_params = form_params['default_params']

    # step 1 - select a prompt
    response = [{
        'name': 'email',
        'label': 'Email Address',
        'description': 'Where should the results be emailed?',
        'type': 'text',
        'required': True,
    },
        {
        'name': 'question',
        'label': 'Type your AI prompt',
        'description': 'Type your prompt to generate a model response.',
        'type': 'textarea',
        'required': True,
        "default":  default_question
    },
        {
        'name': 'row_or_all',
        'label': 'Run per row or all results?',
        'description': "Choose whether to run the model on all the results together, or, individually per row.",
        'type': 'select',
        'required': True,
        "default":  default_row_or_all,
        'options': [{'name': 'all', 'label': 'All Results'},
                    {'name': 'row', 'label': 'Per Row'}],
    },
        {
        'name': 'default_params',
        'label': 'Default Parameters?',
        'description': "Select 'no' to customize text model parameters.",
        'type': 'select',
        'required': True,
        "default":  default_params,
        'options': [{'name': 'yes', 'label': 'Yes'},
                    {'name': 'no', 'label': 'No'}],
        'interactive': True  # dynamic field for model specific options
    }]

    # step 2 - optional - customize model params used by both models
    if ('default_params' in form_params and form_params['default_params'] == 'no'):
        response.extend([{
            'name': 'temperature',
            'label': 'Temperature',
            'description': 'The temperature is used for sampling during the response generation, which occurs when topP and topK are applied (Acceptable values = 0.0–1.0)',
            'type': 'text',
            'default': '0.2',
        },
            {
            'name': 'max_output_tokens',
            'label': 'Max Output Tokens',
            'description': 'Maximum number of tokens that can be generated in the response (Acceptable values = 1 - {})'.format(OUTPUT_TOKEN_LIMIT),
            'type': 'text',
            'default': str(OUTPUT_TOKEN_LIMIT),
        },
            {
            'name': 'top_k',
            'label': 'Top-k',
            'description': 'Top-k changes how the model selects tokens for output. Specify a lower value for less random responses and a higher value for more random responses. (Acceptable values = 1-40)',
            'type': 'text',
            'default': '40',
        },
            {
            'name': 'top_p',
            'label': 'Top-p',
            'description': 'Top-p changes how the model selects tokens for output. Specify a lower value for less random responses and a higher value for more random responses. (Acceptable values = 0.0–1.0)',
            'type': 'text',
            'default': '0.8',
        }
        ])

    print('returning form json: {}'.format(json.dumps(response)))
    return Response(json.dumps(response), status=200, mimetype='application/json')

def action_execute(request):
    """Generate a response from Vertex AI triggered via a Looker action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    request_json = request.get_json()
    attachment = request_json['attachment']
    action_params = request_json['data']
    form_params = request_json['form_params']
    question = form_params['question']
    print(action_params)
    print(form_params)

    temperature = 0.2 if 'temperature' not in form_params else safe_cast(
        form_params['temperature'], float, 0.0, 1.0, 0.2)
    max_output_tokens = OUTPUT_TOKEN_LIMIT if 'max_output_tokens' not in form_params else safe_cast(
        form_params['max_output_tokens'], int, 1, OUTPUT_TOKEN_LIMIT, OUTPUT_TOKEN_LIMIT)
    top_k = 40 if 'top_k' not in form_params else safe_cast(
        form_params['top_k'], int, 1, 40, 40)
    top_p = 0.8 if 'top_p' not in form_params else safe_cast(
        form_params['top_p'], float, 0.0, 1.0, 0.8)

    # placeholder for model error email response
    body = 'There was a problem running the model. Please try again with less data. '
    summary = ''
    row_chunks = 200  # mumber of rows to summarize together
    try:
        all_data = sanitize_and_load_json_str(
            attachment['data'])
        if form_params['row_or_all'] == 'row':
            row_chunks = 1  # run function on each row individually

        summary = model_with_limit_and_backoff(
            all_data, question, row_chunks, temperature, max_output_tokens, top_k, top_p)

        # if row, zip prompt_result with all_data and send html table
        if form_params['row_or_all'] == 'row':
            for i in range(len(all_data)):
                all_data[i]['prompt_result'] = summary[i]
            body = list_to_html(all_data)

        # if all, send summary on top of all_data
        if form_params['row_or_all'] == 'all':
            if len(summary) == 1:
                body = 'Prompt Result:<br><strong>{}</strong><br><br><br>'.format(
                    summary[0].replace('\n', '<br>'))
            else:
                reduced_summary = reduce(
                    '\n'.join(summary), temperature, max_output_tokens, top_k, top_p)
                body = 'Final Prompt Result:<br><strong>{}</strong><br><br>'.format(
                    reduced_summary.replace('\n', '<br>'))
                body += '<br><br><strong>Batch Prompt Result:</strong><br>'
                body += '<br><br><strong>Batch Prompt Result:</strong><br>'.join(
                    summary).replace('\n', '<br>') + '<br><br><br>'

            body += list_to_html(all_data)

    except Exception as e:
        body += 'Gemini API Error: ' + e.message
        print(body)

    if body == '':
        body = 'No response from model. Try asking a more specific question.'

    try:
        # todo - make email prettier
        response = requests.post(
            "https://api.mailgun.net/v3/{}/messages".format(os.environ.get('MAILGUN_DOMAIN')),
            auth=("api", os.environ.get('MAILGUN_API_TOKEN')),
            data={"from": os.environ.get('EMAIL_SENDER'),
                  "to": form_params['email'],
                  "subject": 'Your GenAI Report from Looker',
                  "html": body})

        response.raise_for_status()
        print('Message status code: {}'.format(response.status_code))
    except Exception as e:
        error = handle_error('Mailgun Error: ' + str(e), 400)
        return error

    return Response(status=200, mimetype='application/json')


def action_handler(request):
    """Router for Gen 2 Single Function Deployment"""
    path = request.path
    # specific check for list to handle root path
    if path == '/' or 'list' in path: 
        return action_list(request)
    elif 'form' in path:
        return action_form(request)
    elif 'execute' in path:
        return action_execute(request)
    else:
        return Response('Not Found', status=404)
