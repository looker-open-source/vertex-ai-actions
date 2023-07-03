import json
import os
from flask import Response
import vertexai
from vertexai.preview.language_models import TextGenerationModel
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from icon import icon_data_uri
from utils import authenticate


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
            'supported_formats':['json'],
            'supported_formattings':['unformatted'],
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

    # step 1 - select a prompt
    response = [{
        'name': 'prompt_question',
        'label': 'Type your AI prompt',
        'description': "Choose your prompt to generate model response.",
        # 'type': 'select',
        'type': 'textarea',
        'required': True,
        "default":  'Can you summarize the following dataset in 10 bullet points?'
        # 'options': [
        #         {'name': 'Can you summarize the following dataset in 10 bullet points for our executive team?',
        #             'label': 'Can you summarize the following dataset in 10 bullet points for our executive team?'},
        #         {'name': 'AUTOML_REGRESSOR',
        #             'label': 'AutoML Regression (AUTOML_REGRESSOR)'},
        #         {'name': 'LOGISTIC_REG',
        #             'label': 'Logistic Classification (LOGISTIC_REG)'},
        #         {'name': 'LINEAR_REG',
        #             'label': 'Linear Regression (LINEAR_REG)'},
        # ],
        # 'interactive': True  # dynamic field for model specific options
    }]

    # step 2 - select model type specific parameters
    # if 'model_type' in form_params:
    #     if form_params['model_type'] == 'LINEAR_REG':
    #         response.extend([{
    #             'name': 'optimize_strategy',
    #             'label': 'Optimize Strategy',
    #             'description': 'The strategy to train linear regression models.',
    #             'type': 'select',
    #             'required': True,
    #             'default': 'AUTO_STRATEGY',
    #             'options': [{'name': 'AUTO_STRATEGY',
    #                          'label': 'Auto Strategy'},
    #                         {'name': 'BATCH_GRADIENT_DESCENT',
    #                             'label': 'Batch Gradient Descent'},
    #                         {'name': 'NORMAL_EQUATION',
    #                             'label': 'Normal Equation'}]
    #         }])
    # if form_params['model_type'] == 'LOGISTIC_REG':
    #     response.extend([{
    #         'name': 'auto_class_weights',
    #         'label': 'Auto Class Weights',
    #         'description': 'Whether to balance class labels using weights for each class in inverse proportion to the frequency of that class.',
    #         'type': 'select',
    #         'required': True,
    #         'default': 'False',
    #         'options': [{'name': True, 'label': 'True'},
    #                     {'name': False, 'label': 'False'}]
    #     }])
    # if 'AUTOML' in form_params['model_type']:
    #     response.extend([{
    #         'name': 'budget_hours',
    #         'label': 'Budget Hours',
    #         'required': True,
    #         'default': '1',
    #         'description': 'Enter the maximum number of hours to train the model (must be between 1 and 72)',
    #         'type': 'text',
    #     }])

    # step 3 - specify model name, identifier column, and target column
    # response.extend([
    #     {
    #         'name': 'model_name',
    #         'label': 'Model Name',
    #         'description': 'Model names can only contain letters, numbers, and underscores.',
    #         'type': 'text',
    #         'required': True,
    #     },
    #     {
    #         'name': 'identifier_column',
    #         'label': 'Enter your ID column',
    #         'description': 'Enter the column name of the row identifier to be excluded from the model input.',
    #         'type': 'text',
    #         'required': True,
    #     },
    #     {
    #         'name': 'target_column',
    #         'label': 'Enter your target',
    #         'description': 'Enter the column name to train the model on.',
    #         'type': 'text',
    #         'required': True,
    #     }
    # ])

    print('returning form json: {}'.format(json.dumps(response)))
    return Response(json.dumps(response), status=200, mimetype='application/json')


# https://github.com/looker-open-source/actions/blob/master/docs/action_api.md#action-execute-endpoint
def action_execute(request):
    """Create BigQuery ML model from a Looker action"""
    auth = authenticate(request)
    if auth.status_code != 200:
        return auth

    request_json = request.get_json()
    attachment = request_json['attachment']
    action_params = request_json['data']
    form_params = request_json['form_params']
    # data = json.loads(attachment['data'])
    print(action_params)
    print(form_params)
    print(attachment['data'])  # in json format

    prompt = '''
        I am an analyst using a business intelligence tool to prompt AI to derive insights on my data. I will create queries to ask different questions about my first-party data. This may include sales data, customer data, marketing data, retention data, internal HR data, etc. I will provide you the results of these queries in the form of a JSON payload. Responses should be comprehensive with different metrics, insights and inferences made about the data. Please include insights that would be difficult to capture by the naked eye reading a chart or data table. 
        Outputs from the your model will likely be used in executive presentations, internal emails, customer facing emails & collateral, or added as notes in a BI tool or CRM application.
        '''

    insights = predict_large_language_model_sample(
        0.2, 1024, 0.8, 40, prompt + form_params['prompt_question'] + attachment['data'])

    body = insights.text.replace('\n', '<br>')

    message = Mail(
        from_email=os.environ.get('EMAIL_SENDER'),
        to_emails=action_params['email'],
        subject='Your Report Summary from Looker',
        html_content='<strong>{}</strong>'.format(body)
    )

    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print('Message status code: {}'.format(response.status_code))
    except Exception as e:
        print(e.message)
        return Response(json.dumps(e.message), status=401, mimetype='application/json')

    return Response(status=200, mimetype='application/json')


def predict_large_language_model_sample(
    temperature: float,
    max_decode_steps: int,
    top_p: float,
    top_k: int,
    content: str,
    model_name: str = 'text-bison@001',
):
    """Predict using a Large Language Model."""

    vertexai.init(project=os.environ.get('PROJECT'),
                  location='us-central1')
    model = TextGenerationModel.from_pretrained(model_name)

    response = model.predict(
        content,
        temperature=temperature,
        max_output_tokens=max_decode_steps,
        top_k=top_k,
        top_p=top_p,)
    print('Response from Model: {}'.format(response))
    return response
