# Web Monitor

Async Python service that periodically checks website availability, tracks up/down state in SQLite, and sends email notifications when sites go down or recover.

## Installation

### Requirements

- Python 3.11+
- Network access to monitored sites
- SMTP server for email notifications

### From source

```bash
git clone <repo-url> web-monitoring
cd web-monitoring
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

For development (includes pytest, ruff):

```bash
pip install -e ".[dev]"
```

### Systemd setup

Copy the service file and create the required directories:

```bash
sudo cp systemd/web-monitor.service /etc/systemd/system/
sudo mkdir -p /etc/web-monitor /var/lib/web-monitor
```

Copy and edit your configuration:

```bash
sudo cp config/config.example.yaml /etc/web-monitor/config.yaml
sudo editor /etc/web-monitor/config.yaml
```

Create an environment file for secrets:

```bash
sudo touch /etc/web-monitor/env
sudo chmod 600 /etc/web-monitor/env
echo 'SMTP_PASSWORD=your-password-here' | sudo tee /etc/web-monitor/env
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now web-monitor
```

## Configuration

The service reads a YAML config file. By default it looks at `/etc/web-monitor/config.yaml`. Override with the `-c` flag:

```bash
web-monitor -c /path/to/config.yaml
```

### Example configuration

```yaml
global:
  check_interval_seconds: 60
  timeout_seconds: 10
  db_path: "/var/lib/web-monitor/checks.db"
  log_level: "INFO"

email:
  smtp_host: "smtp.example.com"
  smtp_port: 587
  smtp_user: "alerts@example.com"
  smtp_password: "${SMTP_PASSWORD}"
  use_tls: true
  from_address: "alerts@example.com"
  to_addresses:
    - "oncall@example.com"

sites:
  - name: "production-app"
    url: "https://app.example.com/health"
    check_interval_seconds: 30
    expected_status: 200

  - name: "docs-site"
    url: "https://docs.example.com"
```

### Global settings

| Field | Default | Description |
|-------|---------|-------------|
| `check_interval_seconds` | `60` | Default interval between checks for each site |
| `timeout_seconds` | `10` | HTTP request timeout |
| `db_path` | `/var/lib/web-monitor/checks.db` | Path to the SQLite database |
| `log_level` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Email settings

| Field | Default | Description |
|-------|---------|-------------|
| `smtp_host` | *(required)* | SMTP server hostname |
| `smtp_port` | `587` | SMTP server port |
| `smtp_user` | *(required)* | SMTP authentication username |
| `smtp_password` | *(required)* | SMTP password (supports `${ENV_VAR}` syntax) |
| `use_tls` | `true` | Use STARTTLS |
| `from_address` | *(required)* | Sender email address |
| `to_addresses` | *(required)* | List of recipient email addresses |

### Site settings

| Field | Default | Description |
|-------|---------|-------------|
| `name` | *(required)* | Unique identifier for the site |
| `url` | *(required)* | URL to check |
| `check_interval_seconds` | global value | Per-site override for check interval |
| `expected_status` | `200` | HTTP status code that indicates the site is up |

### Environment variable substitution

Any string value in the config can reference environment variables using `${VAR_NAME}` syntax. The service will substitute these at startup. If a referenced variable is not set, the service exits with an error.

This is primarily useful for keeping secrets out of the config file:

```yaml
smtp_password: "${SMTP_PASSWORD}"
```

When running under systemd, set variables in `/etc/web-monitor/env`:

```
SMTP_PASSWORD=your-smtp-password
```

## Notifications

### Down notification

Sent when a site transitions from UP to DOWN:

```
Subject: [DOWN] production-app is unreachable

Site: production-app
URL: https://app.example.com/health
Status: DOWN
Time: 2026-02-03T12:00:00 UTC
HTTP Status: 503 (expected 200)
Error: Expected 200, got 503

This site was previously UP since 2026-02-01T08:00:00 UTC.
```

### Recovery notification

Sent when a site transitions from DOWN to UP:

```
Subject: [RECOVERED] production-app is back up

Site: production-app
URL: https://app.example.com/health
Status: UP
Time: 2026-02-03T12:05:00 UTC
Downtime duration: ~5 minutes

This site was DOWN since 2026-02-03T12:00:00 UTC.
```

No email is sent on the first check (initial state is recorded silently) or when the state stays the same between checks.

## Troubleshooting

### Service won't start

**Check the logs:**

```bash
sudo journalctl -u web-monitor -e
```

**"Environment variable X is not set"** — The config references `${X}` but the variable isn't defined. Add it to `/etc/web-monitor/env` and restart.

**"No such file or directory" for config** — The default path is `/etc/web-monitor/config.yaml`. Verify the file exists or pass `-c` with the correct path.

**Permission denied on db_path** — The service runs with `ProtectHome=true` and `ProtectSystem=strict`. The database must be under a writable path listed in `ReadWritePaths` in the unit file (default: `/var/lib/web-monitor`). Create the directory:

```bash
sudo mkdir -p /var/lib/web-monitor
sudo chown root:root /var/lib/web-monitor
```

### Sites always reported as DOWN

**Check the URL manually:**

```bash
curl -sS -o /dev/null -w "%{http_code}" https://app.example.com/health
```

**Wrong expected_status** — If the site returns a redirect (301/302) or a non-200 success code, set `expected_status` to match.

**Timeout too low** — Slow endpoints may not respond within `timeout_seconds`. Increase the global or per-site timeout.

**DNS resolution failure** — The service needs DNS access. Check that the host running the service can resolve the monitored URLs. Enable `DEBUG` logging to see the full error:

```yaml
global:
  log_level: "DEBUG"
```

### Emails not being sent

**Enable debug logging** to see SMTP errors:

```yaml
global:
  log_level: "DEBUG"
```

Then check the journal:

```bash
sudo journalctl -u web-monitor -e | grep -i email
```

**Common SMTP issues:**

- **Authentication failed** — Verify `smtp_user` and `smtp_password`. If using Gmail, you need an [App Password](https://support.google.com/accounts/answer/185833), not your account password.
- **Connection refused** — Check `smtp_host` and `smtp_port`. Port 587 uses STARTTLS (`use_tls: true`), port 465 uses implicit SSL (not supported — use 587).
- **Firewall blocking outbound SMTP** — Verify the host can reach the SMTP server: `nc -zv smtp.example.com 587`.

**Email failures don't crash the service.** The check loop continues running; only a log entry is written when sending fails.

### Database issues

**Inspecting the database:**

```bash
sqlite3 /var/lib/web-monitor/checks.db
```

View current site states:

```sql
SELECT site_name, is_up, last_check_time, last_change_time, error_message
FROM site_status;
```

View recent check history:

```sql
SELECT site_name, timestamp, status_code, response_time_ms, is_up
FROM check_log
ORDER BY timestamp DESC
LIMIT 20;
```

**Database growing too large** — The `check_log` table grows over time. The `prune_old_logs` method exists in the codebase but is not called automatically. To clean up manually:

```sql
DELETE FROM check_log WHERE timestamp < '2026-01-01T00:00:00';
VACUUM;
```

**Corrupted database** — Stop the service, delete the `.db` file, and restart. The schema is recreated automatically. Current site states will be lost (first check after restart will establish baseline state without sending notifications).

### Service restarts frequently

Check exit reason:

```bash
sudo systemctl status web-monitor
sudo journalctl -u web-monitor --since "1 hour ago"
```

The service is configured with `Restart=always` and `RestartSec=5`. Database errors cause the service to exit (and systemd restarts it). If the database path is unwritable, this creates a restart loop — fix the permissions as described above.

### Running manually for debugging

Stop the service and run directly to see output in real time:

```bash
sudo systemctl stop web-monitor
source .venv/bin/activate
SMTP_PASSWORD=your-password web-monitor -c /etc/web-monitor/config.yaml
```

Or with debug logging:

```bash
# Edit config to set log_level: "DEBUG", then:
SMTP_PASSWORD=your-password web-monitor -c /etc/web-monitor/config.yaml
```
