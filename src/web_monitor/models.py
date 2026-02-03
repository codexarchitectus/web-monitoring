from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GlobalConfig(BaseModel):
    check_interval_seconds: int = 60
    timeout_seconds: int = 10
    db_path: str = "/var/lib/web-monitor/checks.db"
    log_level: str = "INFO"
    confirm_down_after: int = 1


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    use_tls: bool = True
    from_address: str
    to_addresses: list[str]


class SiteConfig(BaseModel):
    name: str
    url: str
    check_interval_seconds: int | None = None
    expected_status: int = 200


class AppConfig(BaseModel):
    global_: GlobalConfig = Field(alias="global", default_factory=GlobalConfig)
    email: EmailConfig
    sites: list[SiteConfig]

    model_config = {"populate_by_name": True}


class CheckResult(BaseModel):
    site_name: str
    url: str
    is_up: bool
    status_code: int | None = None
    response_time_ms: float | None = None
    error_message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SiteStatus(BaseModel):
    site_name: str
    url: str
    is_up: bool
    last_status_code: int | None = None
    last_check_time: datetime
    last_change_time: datetime
    error_message: str | None = None
