import json
import pytest
from flask import Flask, request

import gemini_api
import main

app = Flask(__name__)

EXPECTED_ERROR_MESSAGE = (
    'Invalid model_selection. Must be one of: '
    'gemini-1.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite.'
)

INVALID_MODELS = [
    'gemini-2.5-pro',
    'projects/p/locations/us-central1/endpoints/123',
    'publishers/google/models/gemini-2.5-pro',
    '<img src=x onerror=alert(1)>',
    ' gemini-2.5-flash',
    'GEMINI-2.5-FLASH',
    '',
    None,
    123,
    ['gemini-2.5-flash'],
    True,
]


def _execute_payload(form_params):
    return {
        'attachment': {'data': '[{"metric": 10}]'},
        'data': {},
        'form_params': form_params,
    }


def test_action_form_uses_shared_model_options(monkeypatch):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')

    with app.test_request_context(
        '/form',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json={'form_params': {}},
    ):
        resp = main.action_form(request)

    assert resp.status_code == 200
    fields = json.loads(resp.get_data(as_text=True))
    model_field = next(field for field in fields if field['name'] == 'model_selection')
    assert model_field['default'] == gemini_api.DEFAULT_MODEL
    assert model_field['options'] == gemini_api.MODEL_OPTIONS


@pytest.mark.parametrize(
    'model_name',
    ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-1.5-pro'],
)
def test_action_execute_allows_valid_models(monkeypatch, mocker, model_name):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    mock_model = mocker.patch(
        'main.model_with_limit_and_backoff',
        return_value=['Valid summary'],
    )
    mock_email = mocker.patch('main.send_email')

    payload = _execute_payload(
        {
            'email': 'analyst@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
            'model_selection': model_name,
        }
    )

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    assert mock_model.call_args.args[7] == model_name
    mock_email.assert_called_once()


def test_action_execute_omitted_model_selection_uses_model_variant_or_default(
    monkeypatch, mocker
):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    monkeypatch.delenv('MODEL_VARIANT', raising=False)
    mock_model = mocker.patch(
        'main.model_with_limit_and_backoff',
        return_value=['Default summary'],
    )
    mock_email = mocker.patch('main.send_email')

    payload = _execute_payload(
        {
            'email': 'analyst@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
        }
    )

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    assert mock_model.call_args.args[7] == 'gemini-2.5-flash'
    mock_email.assert_called_once()

    mock_model.reset_mock()
    mock_email.reset_mock()
    monkeypatch.setenv('MODEL_VARIANT', 'gemini-1.5-pro')

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    assert mock_model.call_args.args[7] == 'gemini-1.5-pro'
    mock_email.assert_called_once()


def test_action_execute_rejects_invalid_env_model_variant(monkeypatch, mocker):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    monkeypatch.setenv('MODEL_VARIANT', 'gemini-2.5-pro')
    mock_gen_model = mocker.patch('gemini_api.GenerativeModel')
    mock_model = mocker.patch('main.model_with_limit_and_backoff')
    mock_email = mocker.patch('main.send_email')

    payload = _execute_payload(
        {
            'email': 'analyst@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
        }
    )

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 400
    assert json.loads(resp.get_data(as_text=True)) == {
        'looker': {'success': False, 'message': EXPECTED_ERROR_MESSAGE}
    }
    mock_gen_model.assert_not_called()
    mock_model.assert_not_called()
    mock_email.assert_not_called()


@pytest.mark.parametrize('bad_model', INVALID_MODELS)
def test_action_execute_rejects_invalid_model_selection(monkeypatch, mocker, bad_model):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    mock_gen_model = mocker.patch('gemini_api.GenerativeModel')
    mock_model = mocker.patch('main.model_with_limit_and_backoff')
    mock_reduce = mocker.patch('main.reduce')
    mock_email = mocker.patch('main.send_email')

    payload = _execute_payload(
        {
            'email': 'analyst@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
            'model_selection': bad_model,
        }
    )

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 400
    assert json.loads(resp.get_data(as_text=True)) == {
        'looker': {'success': False, 'message': EXPECTED_ERROR_MESSAGE}
    }
    mock_gen_model.assert_not_called()
    mock_model.assert_not_called()
    mock_reduce.assert_not_called()
    mock_email.assert_not_called()


@pytest.mark.parametrize('bad_model', INVALID_MODELS)
def test_gemini_api_functions_reject_invalid_models(mocker, bad_model):
    mock_init = mocker.patch('gemini_api.vertexai.init')
    mock_gen_model = mocker.patch('gemini_api.GenerativeModel')

    with pytest.raises(ValueError, match='Invalid model_selection'):
        gemini_api.model_with_limit_and_backoff(
            [{'col': 'val'}],
            'Summarize',
            200,
            0.2,
            8192,
            40,
            0.8,
            bad_model,
        )

    with pytest.raises(ValueError, match='Invalid model_selection'):
        gemini_api.reduce(
            'chunk summary',
            0.2,
            8192,
            40,
            0.8,
            bad_model,
        )

    mock_init.assert_not_called()
    mock_gen_model.assert_not_called()
