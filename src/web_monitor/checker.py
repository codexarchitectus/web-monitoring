import logging
import time

import httpx

from web_monitor.models import CheckResult, SiteConfig

logger = logging.getLogger(__name__)


async def check_site(site: SiteConfig, timeout: float) -> CheckResult:
    """Check if a site is reachable. Never raises."""
    try:
        async with httpx.AsyncClient() as client:
            start = time.monotonic()
            response = await client.get(site.url, timeout=timeout, follow_redirects=True)
            elapsed_ms = (time.monotonic() - start) * 1000

        is_up = response.status_code == site.expected_status
        error = None if is_up else f"Expected {site.expected_status}, got {response.status_code}"

        return CheckResult(
            site_name=site.name,
            url=site.url,
            is_up=is_up,
            status_code=response.status_code,
            response_time_ms=round(elapsed_ms, 2),
            error_message=error,
        )
    except Exception as exc:
        logger.warning("Check failed for %s: %s", site.name, exc)
        return CheckResult(
            site_name=site.name,
            url=site.url,
            is_up=False,
            error_message=str(exc),
        )
