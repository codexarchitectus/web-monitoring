import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from web_monitor.models import CheckResult, SiteStatus

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS site_status (
    site_name       TEXT PRIMARY KEY,
    url             TEXT NOT NULL,
    is_up           INTEGER NOT NULL,
    last_status_code INTEGER,
    last_check_time TEXT NOT NULL,
    last_change_time TEXT NOT NULL,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS check_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name       TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    status_code     INTEGER,
    response_time_ms REAL,
    is_up           INTEGER NOT NULL,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_check_log_site_ts
    ON check_log (site_name, timestamp DESC);
"""


class Database:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def save_check(self, result: CheckResult) -> None:
        await self._db.execute(
            """INSERT INTO check_log
               (site_name, timestamp, status_code, response_time_ms, is_up, error_message)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result.site_name,
                result.timestamp.isoformat(),
                result.status_code,
                result.response_time_ms,
                int(result.is_up),
                result.error_message,
            ),
        )
        await self._db.commit()

    async def get_site_status(self, site_name: str) -> SiteStatus | None:
        cursor = await self._db.execute(
            "SELECT * FROM site_status WHERE site_name = ?",
            (site_name,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return SiteStatus(
            site_name=row["site_name"],
            url=row["url"],
            is_up=bool(row["is_up"]),
            last_status_code=row["last_status_code"],
            last_check_time=datetime.fromisoformat(row["last_check_time"]),
            last_change_time=datetime.fromisoformat(row["last_change_time"]),
            error_message=row["error_message"],
        )

    async def update_site_status(self, result: CheckResult, state_changed: bool) -> None:
        now = result.timestamp.isoformat()
        existing = await self.get_site_status(result.site_name)

        if existing is None:
            await self._db.execute(
                """INSERT INTO site_status
                   (site_name, url, is_up, last_status_code, last_check_time,
                    last_change_time, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.site_name,
                    result.url,
                    int(result.is_up),
                    result.status_code,
                    now,
                    now,
                    result.error_message,
                ),
            )
        else:
            change_time = now if state_changed else existing.last_change_time.isoformat()
            await self._db.execute(
                """UPDATE site_status
                   SET url = ?, is_up = ?, last_status_code = ?,
                       last_check_time = ?, last_change_time = ?, error_message = ?
                   WHERE site_name = ?""",
                (
                    result.url,
                    int(result.is_up),
                    result.status_code,
                    now,
                    change_time,
                    result.error_message,
                    result.site_name,
                ),
            )
        await self._db.commit()

    async def prune_old_logs(self, days: int = 30) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        cursor = await self._db.execute(
            "DELETE FROM check_log WHERE timestamp < ?",
            (cutoff,),
        )
        await self._db.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("Pruned %d check log entries older than %d days", deleted, days)
        return deleted
