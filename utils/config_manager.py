import os
from typing import Optional
from utils.helpers import load_json, save_json, ensure_dir


class ConfigManager:
    _instance = None
    _config = None
    _data_dir_override = None
    _log_dir_override = None
    _export_dir_override = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self.load_config()

    def load_config(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config', 'settings.json'
            )
        self.config_path = config_path
        self._config = load_json(config_path, {})
        self._init_directories()

    def set_data_dir(self, dir_path: str) -> None:
        abs_path = os.path.abspath(dir_path)
        self._data_dir_override = abs_path
        ensure_dir(abs_path)
        cache_dir = os.path.join(abs_path, 'cache')
        ensure_dir(cache_dir)

    def set_log_dir(self, dir_path: str) -> None:
        self._log_dir_override = os.path.abspath(dir_path)
        ensure_dir(self._log_dir_override)

    def set_export_dir(self, dir_path: str) -> None:
        self._export_dir_override = os.path.abspath(dir_path)
        ensure_dir(self._export_dir_override)

    def _init_directories(self) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        general = self._config.get('general', {})
        for dir_key in ['data_dir', 'log_dir', 'export_dir']:
            dir_name = general.get(dir_key, dir_key.replace('_dir', ''))
            dir_path = os.path.join(base_dir, dir_name)
            ensure_dir(dir_path)

    def get(self, key_path: str, default: Optional[object] = None) -> object:
        keys = key_path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key_path: str, value: object) -> None:
        keys = key_path.split('.')
        config = self._config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    def save(self) -> None:
        save_json(self._config, self.config_path)

    @property
    def data_dir(self) -> str:
        if self._data_dir_override:
            return self._data_dir_override
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, self.get('general.data_dir', 'data'))

    @property
    def log_dir(self) -> str:
        if self._log_dir_override:
            return self._log_dir_override
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, self.get('general.log_dir', 'logs'))

    @property
    def export_dir(self) -> str:
        if self._export_dir_override:
            return self._export_dir_override
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, self.get('general.export_dir', 'exports'))


config = ConfigManager()
