import json
import os
from flask import Response
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from icon import icon_data_uri
from utils import authenticate, handle_error, safe_cast
from palm_api import predict_llm


BASE_DOMAIN = 'https://{}-{}.cloudfunctions.net/{}-'.format(os.environ.get(
    'REGION'), os.environ.get('PROJECT'), os.environ.get('ACTION_NAME'))


# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#actions-list-endpoint
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
            "icon_data_uri": icon_data_uri,
            'form_url': BASE_DOMAIN + 'form',
            'url': BASE_DOMAIN + 'execute',
            'supported_formats': ['json'],
            'supported_formattings': ['formatted'],
            'supported_visualization_formattings': ['noapply'],
            'params': [
                {'name': 'email', 'label': 'Email',
                    'user_attribute_name': 'email', 'required': True},
                {'name': 'user_id', 'label': 'User ID',
                    'user_attribute_name': 'id', 'required': True}
            ]
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

    default_params = 'yes'
    if 'default_params' in form_params:
        default_params = form_params['default_params']

    # step 1 - select a prompt
    response = [{
        'name': 'question',
        'label': 'Type your AI prompt',
        'description': 'Type your prompt to generate a model response.',
        'type': 'textarea',
        'required': True,
        "default":  default_question
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

    # step 2 - optional - customize model params
    if 'default_params' in form_params and form_params['default_params'] == 'no':
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
            'description': 'Maximum number of tokens that can be generated in the response (Acceptable values = 1–1024)',
            'type': 'text',
            'default': '1024',
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


# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-execute-endpoint
def action_execute(request):
    """Generate a response from Generative AI Studio from a Looker action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    request_json = request.get_json()
    attachment = request_json['attachment']
    action_params = request_json['data']
    form_params = request_json['form_params']
    print(action_params)
    print(form_params)
    # print(attachment['data'])  # in json format

    temperature = 0.2 if 'temperature' not in form_params else safe_cast(
        form_params['temperature'], float, 0.0, 1.0, 0.2)
    max_output_tokens = 1024 if 'max_output_tokens' not in form_params else safe_cast(
        form_params['max_output_tokens'], int, 1, 1024, 1024)
    top_k = 40 if 'top_k' not in form_params else safe_cast(
        form_params['top_k'], int, 1, 40, 40)
    top_p = 0.8 if 'top_p' not in form_params else safe_cast(
        form_params['top_p'], float, 0.0, 1.0, 0.8)
    preamble = '''
        I am an analyst using a business intelligence tool to prompt AI to derive insights on my data. I will create queries to ask different questions about my first-party data. This may include sales data, customer data, marketing data, retention data, internal HR data, etc. I will provide you the results of these queries in the form of a CSV payload. Responses should be comprehensive with different metrics, insights and inferences made about the data. Please include insights that would be difficult to capture by the naked eye reading a chart or data table. 
        Outputs from the your model will likely be used in executive presentations, internal emails, customer facing emails & collateral, or added as notes in a BI tool or CRM application. 
        '''
    prompt = preamble + form_params['question'] + '\n' + attachment['data']
    token_count = len(
        (preamble + form_params['question']).split()) + len(attachment['data'].split(','))
    print('Prompt contains {} tokens'.format(token_count))
    # max input token for text-bison: 8,192
    # todo - split large data into chunks

    # placeholder for model error email response
    body = 'There was a problem running the model. Please try again with less data. '

    try:
        insights = predict_llm(
            temperature, max_output_tokens, top_k, top_p, prompt)
        body = insights.text.replace('\n', '<br>')
    except Exception as e:
        body += 'PaLM API Error: ' + e.message
        print(body)

    if body == '':
        body = 'No response from model. Try asking a more specific question.'

    try:
        # todo - make email prettier
        message = Mail(
            from_email=os.environ.get('EMAIL_SENDER'),
            to_emails=action_params['email'],
            subject='Your GenAI Report from Looker',
            html_content='<strong>{}</strong>'.format(body)
        )

        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print('Message status code: {}'.format(response.status_code))
    except Exception as e:
        error = handle_error('SendGrid Error: ' + e.message, 400)
        return error

    return Response(status=200, mimetype='application/json')
