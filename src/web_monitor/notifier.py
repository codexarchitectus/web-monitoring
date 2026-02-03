import asyncio
import logging
import smtplib
from email.message import EmailMessage

from web_monitor.models import AppConfig, CheckResult, SiteConfig, SiteStatus

logger = logging.getLogger(__name__)


def _build_down_email(
    site: SiteConfig, result: CheckResult, previous: SiteStatus | None, config: AppConfig
) -> EmailMessage:
    status_detail = ""
    if result.status_code is not None:
        status_detail = f"HTTP Status: {result.status_code} (expected {site.expected_status})\n"

    previous_info = ""
    if previous and previous.is_up:
        previous_info = (
            f"\nThis site was previously UP since {previous.last_change_time.isoformat()} UTC."
        )

    body = (
        f"Site: {site.name}\n"
        f"URL: {site.url}\n"
        f"Status: DOWN\n"
        f"Time: {result.timestamp.isoformat()} UTC\n"
        f"{status_detail}"
        f"Error: {result.error_message}\n"
        f"{previous_info}"
    )

    msg = EmailMessage()
    msg["Subject"] = f"[DOWN] {site.name} is unreachable"
    msg["From"] = config.email.from_address
    msg["To"] = ", ".join(config.email.to_addresses)
    msg.set_content(body)
    return msg


def _build_recovery_email(
    site: SiteConfig, result: CheckResult, previous: SiteStatus | None, config: AppConfig
) -> EmailMessage:
    downtime_info = ""
    if previous and not previous.is_up:
        duration = result.timestamp - previous.last_change_time
        minutes = int(duration.total_seconds() / 60)
        downtime_info = (
            f"Downtime duration: ~{minutes} minutes\n"
            f"\nThis site was DOWN since {previous.last_change_time.isoformat()} UTC."
        )

    body = (
        f"Site: {site.name}\n"
        f"URL: {site.url}\n"
        f"Status: UP\n"
        f"Time: {result.timestamp.isoformat()} UTC\n"
        f"{downtime_info}"
    )

    msg = EmailMessage()
    msg["Subject"] = f"[RECOVERED] {site.name} is back up"
    msg["From"] = config.email.from_address
    msg["To"] = ", ".join(config.email.to_addresses)
    msg.set_content(body)
    return msg


def _send_email(msg: EmailMessage, config: AppConfig) -> None:
    email_cfg = config.email
    try:
        if email_cfg.use_tls:
            with smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port) as server:
                server.starttls()
                server.login(email_cfg.smtp_user, email_cfg.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port) as server:
                server.login(email_cfg.smtp_user, email_cfg.smtp_password)
                server.send_message(msg)
        logger.info("Sent email: %s", msg["Subject"])
    except Exception:
        logger.exception("Failed to send email: %s", msg["Subject"])


async def send_down_email(
    site: SiteConfig, result: CheckResult, previous: SiteStatus | None, config: AppConfig
) -> None:
    msg = _build_down_email(site, result, previous, config)
    await asyncio.to_thread(_send_email, msg, config)


async def send_recovery_email(
    site: SiteConfig, result: CheckResult, previous: SiteStatus | None, config: AppConfig
) -> None:
    msg = _build_recovery_email(site, result, previous, config)
    await asyncio.to_thread(_send_email, msg, config)
