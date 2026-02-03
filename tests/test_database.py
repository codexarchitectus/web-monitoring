from datetime import datetime

import pytest

from web_monitor.models import CheckResult


async def test_save_and_get_status(db):
    result = CheckResult(
        site_name="test-site",
        url="https://example.com",
        is_up=True,
        status_code=200,
        response_time_ms=42.5,
        timestamp=datetime(2026, 2, 3, 12, 0, 0),
    )
    await db.save_check(result)
    await db.update_site_status(result, state_changed=False)

    status = await db.get_site_status("test-site")
    assert status is not None
    assert status.site_name == "test-site"
    assert status.is_up is True
    assert status.last_status_code == 200


async def test_get_nonexistent_status(db):
    status = await db.get_site_status("nonexistent")
    assert status is None


async def test_state_change_updates_change_time(db):
    result1 = CheckResult(
        site_name="test-site",
        url="https://example.com",
        is_up=True,
        status_code=200,
        timestamp=datetime(2026, 2, 3, 12, 0, 0),
    )
    await db.save_check(result1)
    await db.update_site_status(result1, state_changed=False)

    status1 = await db.get_site_status("test-site")
    original_change_time = status1.last_change_time

    # Same state, no change
    result2 = CheckResult(
        site_name="test-site",
        url="https://example.com",
        is_up=True,
        status_code=200,
        timestamp=datetime(2026, 2, 3, 12, 1, 0),
    )
    await db.save_check(result2)
    await db.update_site_status(result2, state_changed=False)

    status2 = await db.get_site_status("test-site")
    assert status2.last_change_time == original_change_time

    # State change
    result3 = CheckResult(
        site_name="test-site",
        url="https://example.com",
        is_up=False,
        status_code=503,
        timestamp=datetime(2026, 2, 3, 12, 2, 0),
    )
    await db.save_check(result3)
    await db.update_site_status(result3, state_changed=True)

    status3 = await db.get_site_status("test-site")
    assert status3.is_up is False
    assert status3.last_change_time != original_change_time


async def test_prune_old_logs(db):
    old_result = CheckResult(
        site_name="test-site",
        url="https://example.com",
        is_up=True,
        status_code=200,
        timestamp=datetime(2020, 1, 1, 0, 0, 0),
    )
    await db.save_check(old_result)

    new_result = CheckResult(
        site_name="test-site",
        url="https://example.com",
        is_up=True,
        status_code=200,
        timestamp=datetime(2026, 2, 3, 12, 0, 0),
    )
    await db.save_check(new_result)

    deleted = await db.prune_old_logs(days=30)
    assert deleted == 1
