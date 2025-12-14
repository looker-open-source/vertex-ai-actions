import json
import os
import requests
from flask import Response
from icon import icon_data_uri
import logging
import markdown
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

    logging.info('returning integrations json')
    return Response(json.dumps(response), status=200, mimetype='application/json')

# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-form-endpoint
def action_form(request):
    """Return form endpoint data for action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    request_json = request.get_json()
    form_params = request_json['form_params']
    logging.info(form_params)

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
        'name': 'model_selection',
        'label': 'Model Version',
        'description': 'Select the Gemini model version to use.',
        'type': 'select',
        'required': True,
        'default': 'gemini-2.5-flash',
        'options': [{'name': 'gemini-2.5-flash', 'label': 'Gemini 2.5 Flash (Fast)'},
                    {'name': 'gemini-2.5-flash-lite', 'label': 'Gemini 2.5 Flash Lite (Fast)'},
                    {'name': 'gemini-1.5-pro', 'label': 'Gemini 1.5 Pro (Reasoning)'}],
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

    logging.info('returning form json: {}'.format(json.dumps(response)))
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
    logging.info(action_params)
    logging.info(form_params)

    temperature = 0.2 if 'temperature' not in form_params else safe_cast(
        form_params['temperature'], float, 0.0, 1.0, 0.2)
    max_output_tokens = OUTPUT_TOKEN_LIMIT if 'max_output_tokens' not in form_params else safe_cast(
        form_params['max_output_tokens'], int, 1, OUTPUT_TOKEN_LIMIT, OUTPUT_TOKEN_LIMIT)
    top_k = 40 if 'top_k' not in form_params else safe_cast(
        form_params['top_k'], int, 1, 40, 40)
    top_p = 0.8 if 'top_p' not in form_params else safe_cast(
        form_params['top_p'], float, 0.0, 1.0, 0.8)
    
    model_name = form_params.get('model_selection', os.environ.get('MODEL_VARIANT', 'gemini-2.5-flash'))

    # placeholder for model error email response
    body = 'There was a problem running the model. Please try again with less data. '
    summary = ''
    row_chunks = 200  # mumber of rows to summarize together
    
    email_css = """
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; }
        .container { max-width: 800px; margin: 0 auto; padding: 0; background-color: #fff; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background-color: #4285f4; color: white; padding: 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; font-weight: 500; }
        .content { padding: 30px; }
        .summary-card { background-color: #f8f9fa; border-left: 5px solid #4285f4; padding: 20px; margin-bottom: 25px; border-radius: 4px; }
        .summary-title { font-weight: bold; color: #1a73e8; margin-bottom: 12px; font-size: 1.1em; text-transform: uppercase; letter-spacing: 0.5px; }
        .batch-results { font-size: 0.9em; color: #555; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px; }
        .batch-item { background: #fdfdfd; padding: 15px; border: 1px solid #e0e0e0; margin-bottom: 15px; border-radius: 6px; }
        .batch-title { font-weight: 600; color: #555; margin-bottom: 8px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 0.9em; }
        th { background-color: #f1f3f4; font-weight: 600; text-align: left; padding: 12px 8px; border-bottom: 2px solid #ddd; }
        td { padding: 10px 8px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f8f9fa; }
        .error-box { background-color: #fce8e6; color: #c5221f; padding: 15px; border-radius: 4px; border: 1px solid #faddd9; margin-bottom: 20px; }
    </style>
    """

    try:
        all_data = sanitize_and_load_json_str(
            attachment['data'])
        if form_params['row_or_all'] == 'row':
            row_chunks = 1  # run function on each row individually

        summary = model_with_limit_and_backoff(
            all_data, question, row_chunks, temperature, max_output_tokens, top_k, top_p, model_name)

        content_html = ""

        # if row, zip prompt_result with all_data and send html table
        if form_params['row_or_all'] == 'row':
            for i in range(len(all_data)):
                all_data[i]['prompt_result'] = summary[i]
            content_html = list_to_html(all_data)

        # if all, send summary on top of all_data
        if form_params['row_or_all'] == 'all':
            if len(summary) == 1:
                content_html += '<div class="summary-card"><div class="summary-title">Summary</div>{}</div>'.format(
                    markdown.markdown(summary[0]))
            else:
                reduced_summary = reduce(
                    '\n'.join(summary), temperature, max_output_tokens, top_k, top_p, model_name)
                content_html += '<div class="summary-card"><div class="summary-title">Executive Summary</div>{}</div>'.format(
                    markdown.markdown(reduced_summary))
                
                content_html += '<div class="batch-results"><h3>Detailed Analysis Batches</h3>'
                for idx, s in enumerate(summary):
                    content_html += '<div class="batch-item"><div class="batch-title">Batch {}</div>{}</div>'.format(
                        idx + 1, markdown.markdown(s))
                content_html += '</div>'

            content_html += '<br><h3>Source Data</h3>' + list_to_html(all_data)
        
        # Assemble final body with template
        body = """
        <html>
        <head>{}</head>
        <body>
            <div class="container">
                <div class="header"><h1>Generative AI Report</h1></div>
                <div class="content">
                    {}
                </div>
            </div>
        </body>
        </html>
        """.format(email_css, content_html)

    except Exception as e:
        error_msg = 'Gemini API Error: ' + str(e)
        logging.error(error_msg)
        body = """
        <html>
        <head>{}</head>
        <body>
            <div class="container">
                <div class="header"><h1>Generative AI Report</h1></div>
                <div class="content">
                    <div class="error-box">{}</div>
                    <p>There was a problem running the model. Please try again with less data or check the logs.</p>
                </div>
            </div>
        </body>
        </html>
        """.format(email_css, error_msg)

    if body == '':
        body = 'No response from model. Try asking a more specific question.'

    try:
        send_email(form_params['email'], 'Your GenAI Report from Looker', body)
    except Exception as e:
        error = handle_error('Email Error: ' + str(e), 400)
        return error

    return Response(status=200, mimetype='application/json')

def send_email(recipient, subject, html_content):
    """Sends email using either SendGrid or Mailgun based on env vars"""
    sender = os.environ.get('EMAIL_SENDER', 'noreply@vertex-ai-action.com')
    
    # Check for SendGrid
    if os.environ.get('SENDGRID_API_KEY'):
        logging.info("Sending email via SendGrid...")
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": "Bearer {}".format(os.environ.get('SENDGRID_API_KEY')),
            "Content-Type": "application/json"
        }
        data = {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {"email": sender},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_content}]
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logging.info('SendGrid status code: {}'.format(response.status_code))
        
    # Check for Mailgun
    elif os.environ.get('MAILGUN_API_TOKEN'):
        logging.info("Sending email via Mailgun...")
        url = "https://api.mailgun.net/v3/{}/messages".format(os.environ.get('MAILGUN_DOMAIN'))
        auth = ("api", os.environ.get('MAILGUN_API_TOKEN'))
        data = {
            "from": sender,
            "to": recipient,
            "subject": subject,
            "html": html_content
        }
        response = requests.post(url, auth=auth, data=data)
        response.raise_for_status()
        logging.info('Mailgun status code: {}'.format(response.status_code))
        
    else:
        raise Exception("No email provider configured. Please set SENDGRID_API_KEY or MAILGUN_API_TOKEN.")


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
