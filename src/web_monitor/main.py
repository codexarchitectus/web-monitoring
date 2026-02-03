import argparse
import asyncio
import logging
import signal
import sys
from datetime import UTC, datetime, timedelta

from web_monitor.checker import check_site
from web_monitor.config import load_config
from web_monitor.database import Database
from web_monitor.models import AppConfig
from web_monitor.notifier import send_down_email, send_recovery_email

logger = logging.getLogger("web_monitor")


class Monitor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.db = Database(config.global_.db_path)
        self._running = True
        self._next_run: dict[str, datetime] = {}
        self._failure_counts: dict[str, int] = {}

    async def run(self) -> None:
        await self.db.init()
        logger.info("Database initialized at %s", self.config.global_.db_path)

        now = datetime.now(UTC)
        for site in self.config.sites:
            self._next_run[site.name] = now

        logger.info("Monitoring %d sites", len(self.config.sites))
        try:
            while self._running:
                await self._tick()
                await asyncio.sleep(1)
        finally:
            await self.db.close()
            logger.info("Shutdown complete")

    async def _tick(self) -> None:
        now = datetime.now(UTC)
        due_sites = [s for s in self.config.sites if self._next_run.get(s.name, now) <= now]

        if not due_sites:
            return

        timeout = self.config.global_.timeout_seconds
        results = await asyncio.gather(
            *(check_site(site, timeout) for site in due_sites),
            return_exceptions=True,
        )

        for site, result in zip(due_sites, results):
            if isinstance(result, Exception):
                logger.error("Unexpected error checking %s: %s", site.name, result)
                continue

            previous = await self.db.get_site_status(site.name)
            threshold = self.config.global_.confirm_down_after
            state_changed = False

            if result.is_up:
                self._failure_counts[site.name] = 0
                if previous is not None and not previous.is_up:
                    state_changed = True
                    logger.info("RECOVERED: %s is back up", site.name)
                    await send_recovery_email(site, result, previous, self.config)
                elif previous is None:
                    logger.info("Initial check for %s: UP", site.name)
            else:
                self._failure_counts[site.name] = (
                    self._failure_counts.get(site.name, 0) + 1
                )
                if previous is None:
                    logger.info("Initial check for %s: DOWN", site.name)
                elif (
                    previous.is_up
                    and self._failure_counts[site.name] >= threshold
                ):
                    state_changed = True
                    logger.warning("DOWN: %s is unreachable", site.name)
                    await send_down_email(site, result, previous, self.config)

            await self.db.save_check(result)
            if result.is_up or state_changed or previous is None:
                await self.db.update_site_status(result, state_changed)

            interval = site.check_interval_seconds or self.config.global_.check_interval_seconds
            self._next_run[site.name] = datetime.now(UTC) + timedelta(seconds=interval)

    def stop(self) -> None:
        logger.info("Stop requested")
        self._running = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Web Monitoring Service")
    parser.add_argument(
        "-c", "--config",
        default="/etc/web-monitor/config.yaml",
        help="Path to configuration file",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    logging.basicConfig(
        level=getattr(logging, config.global_.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    monitor = Monitor(config)

    loop = asyncio.new_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, monitor.stop)

    try:
        loop.run_until_complete(monitor.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
