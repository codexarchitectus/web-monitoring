import httpx
import pytest

from web_monitor.checker import check_site
from web_monitor.models import SiteConfig


@pytest.fixture
def site():
    return SiteConfig(name="test-site", url="https://example.com", expected_status=200)


async def test_check_site_success(httpx_mock, site):
    httpx_mock.add_response(url="https://example.com", status_code=200)
    result = await check_site(site, timeout=5)

    assert result.is_up is True
    assert result.status_code == 200
    assert result.site_name == "test-site"
    assert result.response_time_ms is not None
    assert result.error_message is None


async def test_check_site_wrong_status(httpx_mock, site):
    httpx_mock.add_response(url="https://example.com", status_code=503)
    result = await check_site(site, timeout=5)

    assert result.is_up is False
    assert result.status_code == 503
    assert "Expected 200, got 503" in result.error_message


async def test_check_site_connection_error(httpx_mock, site):
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    result = await check_site(site, timeout=5)

    assert result.is_up is False
    assert result.status_code is None
    assert result.error_message is not None


async def test_check_site_timeout(httpx_mock, site):
    httpx_mock.add_exception(httpx.ReadTimeout("Timed out"))
    result = await check_site(site, timeout=5)

    assert result.is_up is False
    assert result.status_code is None


async def test_check_site_custom_expected_status(httpx_mock):
    site = SiteConfig(name="redirect-site", url="https://example.com", expected_status=301)
    httpx_mock.add_response(url="https://example.com", status_code=301)
    result = await check_site(site, timeout=5)

    assert result.is_up is True
    assert result.status_code == 301
