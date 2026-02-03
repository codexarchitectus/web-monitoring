import pytest

from web_monitor.database import Database
from web_monitor.models import AppConfig, EmailConfig, GlobalConfig, SiteConfig


@pytest.fixture
def email_config():
    return EmailConfig(
        smtp_host="smtp.test.com",
        smtp_port=587,
        smtp_user="test@test.com",
        smtp_password="secret",
        use_tls=True,
        from_address="test@test.com",
        to_addresses=["oncall@test.com"],
    )


@pytest.fixture
def site_config():
    return SiteConfig(
        name="test-site",
        url="https://example.com/health",
        expected_status=200,
    )


@pytest.fixture
def app_config(tmp_path, email_config, site_config):
    return AppConfig(
        **{
            "global": GlobalConfig(
                check_interval_seconds=60,
                timeout_seconds=5,
                db_path=str(tmp_path / "test.db"),
                log_level="DEBUG",
            ),
            "email": email_config,
            "sites": [site_config],
        }
    )


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()
