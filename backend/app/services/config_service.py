from __future__ import annotations

from pathlib import Path

import yaml
from sqlmodel import Session

from app.config import AppConfig, read_config_file, validate_runtime, write_config_file
from app.models import ConfigHistory


class ConfigService:
    def __init__(self, config_path: Path, env_settings: object) -> None:
        self.config_path = config_path
        self.env_settings = env_settings
        self.saved_config = read_config_file(config_path)
        validate_runtime(self.saved_config, env_settings)
        self.runtime_config = self.saved_config.model_copy(deep=True)

    def get_config(self) -> AppConfig:
        return self.saved_config

    def get_runtime_config(self) -> AppConfig:
        return self.runtime_config

    def reload(self) -> AppConfig:
        self.saved_config = read_config_file(self.config_path)
        validate_runtime(self.saved_config, self.env_settings)
        return self.saved_config

    def update_config(
        self,
        session: Session,
        *,
        new_config: AppConfig,
        apply_immediately: bool,
        changed_by: str,
    ) -> AppConfig:
        validate_runtime(new_config, self.env_settings)
        write_config_file(new_config, self.config_path)
        self.saved_config = new_config.model_copy(deep=True)
        history = ConfigHistory(
            apply_immediately=apply_immediately,
            changed_by=changed_by,
            config_yaml=yaml.safe_dump(new_config.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        )
        session.add(history)
        session.commit()
        if apply_immediately:
            self.runtime_config = new_config.model_copy(deep=True)
        return self.saved_config
