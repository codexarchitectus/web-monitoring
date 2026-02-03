from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from web_monitor.main import Monitor
from web_monitor.models import (
    AppConfig,
    CheckResult,
    EmailConfig,
    GlobalConfig,
    SiteConfig,
    SiteStatus,
)


@pytest.fixture
def site():
    return SiteConfig(name="test-site", url="https://example.com", expected_status=200)


@pytest.fixture
def make_config(tmp_path, site):
    def _make(confirm_down_after=3):
        return AppConfig(
            **{
                "global": GlobalConfig(
                    check_interval_seconds=60,
                    timeout_seconds=5,
                    db_path=str(tmp_path / "test.db"),
                    log_level="DEBUG",
                    confirm_down_after=confirm_down_after,
                ),
                "email": EmailConfig(
                    smtp_host="smtp.test.com",
                    smtp_port=587,
                    smtp_user="test@test.com",
                    smtp_password="secret",
                    use_tls=True,
                    from_address="test@test.com",
                    to_addresses=["oncall@test.com"],
                ),
                "sites": [site],
            }
        )

    return _make


def _fail_result(site_name="test-site"):
    return CheckResult(
        site_name=site_name,
        url="https://example.com",
        is_up=False,
        status_code=503,
        error_message="Expected 200, got 503",
    )


def _ok_result(site_name="test-site"):
    return CheckResult(
        site_name=site_name,
        url="https://example.com",
        is_up=True,
        status_code=200,
    )


def _up_status(site_name="test-site"):
    return SiteStatus(
        site_name=site_name,
        url="https://example.com",
        is_up=True,
        last_status_code=200,
        last_check_time=datetime(2026, 1, 1, tzinfo=UTC),
        last_change_time=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _down_status(site_name="test-site"):
    return SiteStatus(
        site_name=site_name,
        url="https://example.com",
        is_up=False,
        last_status_code=503,
        last_check_time=datetime(2026, 1, 1, tzinfo=UTC),
        last_change_time=datetime(2026, 1, 1, tzinfo=UTC),
        error_message="Expected 200, got 503",
    )


@patch("web_monitor.main.send_down_email", new_callable=AsyncMock)
@patch("web_monitor.main.check_site", new_callable=AsyncMock)
async def test_down_alert_after_threshold(mock_check, mock_down_email, make_config, site):
    """Site must fail N consecutive times before a down alert fires."""
    config = make_config(confirm_down_after=3)
    monitor = Monitor(config)
    await monitor.db.init()

    try:
        # Seed an initial "up" status
        await monitor.db.update_site_status(_ok_result(), False)

        mock_check.return_value = _fail_result()

        # First two failures: no alert
        for _ in range(2):
            monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
            await monitor._tick()
        mock_down_email.assert_not_called()

        # Third failure: alert fires
        monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
        await monitor._tick()
        mock_down_email.assert_called_once()
    finally:
        await monitor.db.close()


@patch("web_monitor.main.send_down_email", new_callable=AsyncMock)
@patch("web_monitor.main.check_site", new_callable=AsyncMock)
async def test_success_resets_failure_counter(mock_check, mock_down_email, make_config, site):
    """A success in the middle of failures resets the counter."""
    config = make_config(confirm_down_after=3)
    monitor = Monitor(config)
    await monitor.db.init()

    try:
        await monitor.db.update_site_status(_ok_result(), False)

        # Two failures
        mock_check.return_value = _fail_result()
        for _ in range(2):
            monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
            await monitor._tick()

        # One success — resets counter
        mock_check.return_value = _ok_result()
        monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
        await monitor._tick()

        # Two more failures — still below threshold (counter was reset)
        mock_check.return_value = _fail_result()
        for _ in range(2):
            monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
            await monitor._tick()

        mock_down_email.assert_not_called()
    finally:
        await monitor.db.close()


@patch("web_monitor.main.send_recovery_email", new_callable=AsyncMock)
@patch("web_monitor.main.check_site", new_callable=AsyncMock)
async def test_recovery_sends_immediately(mock_check, mock_recovery_email, make_config, site):
    """Recovery email is sent on the first successful check after being down."""
    config = make_config(confirm_down_after=3)
    monitor = Monitor(config)
    await monitor.db.init()

    try:
        # Seed a "down" status in DB
        await monitor.db.update_site_status(_fail_result(), True)

        mock_check.return_value = _ok_result()
        monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
        await monitor._tick()

        mock_recovery_email.assert_called_once()
    finally:
        await monitor.db.close()


@patch("web_monitor.main.send_down_email", new_callable=AsyncMock)
@patch("web_monitor.main.check_site", new_callable=AsyncMock)
async def test_confirm_down_after_one_preserves_current_behavior(
    mock_check, mock_down_email, make_config, site
):
    """With confirm_down_after=1, a single failure triggers the alert."""
    config = make_config(confirm_down_after=1)
    monitor = Monitor(config)
    await monitor.db.init()

    try:
        await monitor.db.update_site_status(_ok_result(), False)

        mock_check.return_value = _fail_result()
        monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
        await monitor._tick()

        mock_down_email.assert_called_once()
    finally:
        await monitor.db.close()


@patch("web_monitor.main.send_down_email", new_callable=AsyncMock)
@patch("web_monitor.main.check_site", new_callable=AsyncMock)
async def test_site_status_stays_up_during_accumulation(
    mock_check, mock_down_email, make_config, site
):
    """site_status.is_up remains True while failures are below threshold."""
    config = make_config(confirm_down_after=3)
    monitor = Monitor(config)
    await monitor.db.init()

    try:
        await monitor.db.update_site_status(_ok_result(), False)

        mock_check.return_value = _fail_result()
        for _ in range(2):
            monitor._next_run[site.name] = datetime(2000, 1, 1, tzinfo=UTC)
            await monitor._tick()

        status = await monitor.db.get_site_status(site.name)
        assert status.is_up is True
    finally:
        await monitor.db.close()
