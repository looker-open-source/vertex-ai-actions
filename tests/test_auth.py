import json
import pytest
from flask import Flask, request

import main
import utils

app = Flask(__name__)


@pytest.mark.parametrize(
    'env_token,auth_header',
    [
        (None, 'Token token="None"'),
        ('', 'Token token=""'),
        ('   ', 'Token token="   "'),
        ('\t\t', 'Token token="\t\t"'),
        ('\t\n', 'Token token="any"'),
    ],
)
@pytest.mark.parametrize(
    'handler_name',
    ['authenticate', 'action_list', 'action_form', 'action_execute'],
)
def test_fail_closed_when_token_missing_or_blank(
    monkeypatch, mocker, env_token, auth_header, handler_name
):
    if env_token is None:
        monkeypatch.delenv('LOOKER_AUTH_TOKEN', raising=False)
    else:
        monkeypatch.setenv('LOOKER_AUTH_TOKEN', env_token)

    mock_model = mocker.patch('main.model_with_limit_and_backoff')
    mock_email = mocker.patch('main.send_email')

    handler = utils.authenticate if handler_name == 'authenticate' else getattr(main, handler_name)
    with app.test_request_context(
        '/',
        method='POST',
        headers={'Authorization': auth_header},
    ):
        resp = handler(request)

    assert resp.status_code == 500
    body = json.loads(resp.get_data(as_text=True))
    assert body == {'looker': {'success': False, 'message': 'Server auth not configured'}}
    mock_model.assert_not_called()
    mock_email.assert_not_called()


@pytest.mark.parametrize(
    'method,headers',
    [
        ('GET', {'Authorization': 'Token token="super-secret"'}),
        ('POST', {}),
    ],
)
@pytest.mark.parametrize(
    'handler_name',
    ['authenticate', 'action_list', 'action_form', 'action_execute'],
)
def test_rejects_non_post_or_missing_authorization_header(
    monkeypatch, mocker, method, headers, handler_name
):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'super-secret')
    mock_model = mocker.patch('main.model_with_limit_and_backoff')
    mock_email = mocker.patch('main.send_email')

    handler = utils.authenticate if handler_name == 'authenticate' else getattr(main, handler_name)
    with app.test_request_context('/', method=method, headers=headers):
        resp = handler(request)

    assert resp.status_code == 401
    body = json.loads(resp.get_data(as_text=True))
    assert body == {
        'looker': {'success': False, 'message': 'Request must be POST with auth token'}
    }
    mock_model.assert_not_called()
    mock_email.assert_not_called()


@pytest.mark.parametrize(
    'bad_header',
    [
        'Token token="wrong-secret"',
        'Token token="t\u00f6k\u00ebn"',
        'Bearer super-secret',
    ],
)
@pytest.mark.parametrize(
    'handler_name',
    ['authenticate', 'action_list', 'action_form', 'action_execute'],
)
def test_rejects_incorrect_or_non_ascii_token(
    monkeypatch, mocker, bad_header, handler_name
):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'super-secret')
    mock_model = mocker.patch('main.model_with_limit_and_backoff')
    mock_email = mocker.patch('main.send_email')

    handler = utils.authenticate if handler_name == 'authenticate' else getattr(main, handler_name)
    with app.test_request_context(
        '/',
        method='POST',
        headers={'Authorization': bad_header},
    ):
        resp = handler(request)

    assert resp.status_code == 403
    body = json.loads(resp.get_data(as_text=True))
    assert body == {'looker': {'success': False, 'message': 'Incorrect token'}}
    mock_model.assert_not_called()
    mock_email.assert_not_called()


def test_authenticate_rejects_unicode_beyond_latin1_without_type_error(monkeypatch):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'super-secret')

    class DummyRequest:
        method = 'POST'
        headers = {'authorization': 'Token token="\u79d8\u5bc6"'}

    resp = utils.authenticate(DummyRequest())
    assert resp.status_code == 403
    body = json.loads(resp.get_data(as_text=True))
    assert body == {'looker': {'success': False, 'message': 'Incorrect token'}}


def test_valid_token_succeeds_across_auth_and_handlers(monkeypatch, mocker):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'super-secret')
    monkeypatch.setenv('ACTION_NAME', 'vertex-ai')
    monkeypatch.setenv('ACTION_LABEL', 'Vertex AI')
    monkeypatch.setenv('GEN2_ROUTER', 'true')

    auth_headers = {'Authorization': 'Token token="super-secret"'}

    with app.test_request_context('/', method='POST', headers=auth_headers):
        assert utils.authenticate(request).status_code == 200
        list_resp = main.action_list(request)
        assert list_resp.status_code == 200
        list_data = json.loads(list_resp.get_data(as_text=True))
        assert list_data['integrations'][0]['name'] == 'vertex-ai'

    with app.test_request_context(
        '/form',
        method='POST',
        headers=auth_headers,
        json={'form_params': {}},
    ):
        form_resp = main.action_form(request)
        assert form_resp.status_code == 200
        form_data = json.loads(form_resp.get_data(as_text=True))
        assert any(field['name'] == 'model_selection' for field in form_data)

    mocker.patch('main.model_with_limit_and_backoff', return_value=['Summary text'])
    mock_email = mocker.patch('main.send_email')
    with app.test_request_context(
        '/execute',
        method='POST',
        headers=auth_headers,
        json={
            'attachment': {'data': '[{"col": "val"}]'},
            'data': {},
            'form_params': {
                'email': 'user@example.com',
                'question': 'Summarize',
                'row_or_all': 'all',
            },
        },
    ):
        exec_resp = main.action_execute(request)
        assert exec_resp.status_code == 200
        mock_email.assert_called_once()
