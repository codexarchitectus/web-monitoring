from datetime import datetime
from unittest.mock import patch

from web_monitor.models import CheckResult, SiteStatus
from web_monitor.notifier import _build_down_email, _build_recovery_email, send_down_email


def test_build_down_email(site_config, app_config):
    result = CheckResult(
        site_name="test-site",
        url="https://example.com/health",
        is_up=False,
        status_code=503,
        error_message="Expected 200, got 503",
        timestamp=datetime(2026, 2, 3, 12, 0, 0),
    )
    previous = SiteStatus(
        site_name="test-site",
        url="https://example.com/health",
        is_up=True,
        last_status_code=200,
        last_check_time=datetime(2026, 2, 3, 11, 59, 0),
        last_change_time=datetime(2026, 2, 1, 8, 0, 0),
    )

    msg = _build_down_email(site_config, result, previous, app_config)

    assert msg["Subject"] == "[DOWN] test-site is unreachable"
    assert msg["From"] == "test@test.com"
    assert "oncall@test.com" in msg["To"]
    body = msg.get_content()
    assert "DOWN" in body
    assert "503" in body
    assert "previously UP" in body


def test_build_recovery_email(site_config, app_config):
    result = CheckResult(
        site_name="test-site",
        url="https://example.com/health",
        is_up=True,
        status_code=200,
        timestamp=datetime(2026, 2, 3, 12, 5, 0),
    )
    previous = SiteStatus(
        site_name="test-site",
        url="https://example.com/health",
        is_up=False,
        last_status_code=503,
        last_check_time=datetime(2026, 2, 3, 12, 4, 0),
        last_change_time=datetime(2026, 2, 3, 12, 0, 0),
    )

    msg = _build_recovery_email(site_config, result, previous, app_config)

    assert msg["Subject"] == "[RECOVERED] test-site is back up"
    body = msg.get_content()
    assert "UP" in body
    assert "5 minutes" in body
    assert "DOWN since" in body


def test_build_down_email_no_previous(site_config, app_config):
    result = CheckResult(
        site_name="test-site",
        url="https://example.com/health",
        is_up=False,
        error_message="Connection refused",
        timestamp=datetime(2026, 2, 3, 12, 0, 0),
    )

    msg = _build_down_email(site_config, result, None, app_config)
    body = msg.get_content()
    assert "DOWN" in body
    assert "previously UP" not in body


@patch("web_monitor.notifier._send_email")
async def test_send_down_email_calls_send(mock_send, site_config, app_config):
    result = CheckResult(
        site_name="test-site",
        url="https://example.com/health",
        is_up=False,
        error_message="timeout",
        timestamp=datetime(2026, 2, 3, 12, 0, 0),
    )
    await send_down_email(site_config, result, None, app_config)
    mock_send.assert_called_once()
