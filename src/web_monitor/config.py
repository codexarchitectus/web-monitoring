import os
import re
from pathlib import Path

import yaml

from web_monitor.models import AppConfig

ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _substitute_env_vars(value: str) -> str:
    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"Environment variable {var_name} is not set")
        return env_value

    return ENV_VAR_PATTERN.sub(replace, value)


def _walk_and_substitute(obj: object) -> object:
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _walk_and_substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_substitute(item) for item in obj]
    return obj


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)

    substituted = _walk_and_substitute(raw)
    return AppConfig.model_validate(substituted)
