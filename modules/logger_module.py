import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional
from utils.config_manager import config


class Logger:
    _instance = None
    _logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger is None:
            self._init_logger()

    def _init_logger(self) -> None:
        self._logger = logging.getLogger('movie_tracker')
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        log_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(module)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        self._logger.addHandler(console_handler)

        log_file = os.path.join(config.log_dir, 'tracker.log')
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)
        self._logger.addHandler(file_handler)

        task_log_dir = os.path.join(config.log_dir, 'tasks')
        os.makedirs(task_log_dir, exist_ok=True)

    def debug(self, message: str, module: str = "general") -> None:
        self._logger.debug(f"[{module}] {message}")

    def info(self, message: str, module: str = "general") -> None:
        self._logger.info(f"[{module}] {message}")

    def warning(self, message: str, module: str = "general") -> None:
        self._logger.warning(f"[{module}] {message}")

    def error(self, message: str, module: str = "general") -> None:
        self._logger.error(f"[{module}] {message}")

    def critical(self, message: str, module: str = "general") -> None:
        self._logger.critical(f"[{module}] {message}")

    def task_start(self, task_name: str) -> str:
        task_id = datetime.now().strftime('%Y%m%d_%H%M%S') + f"_{task_name}"
        self.info(f"任务开始: {task_name}", task_name)
        return task_id

    def task_end(self, task_name: str, success: bool, details: str = "") -> None:
        status = "成功" if success else "失败"
        msg = f"任务结束: {task_name} - {status}"
        if details:
            msg += f" - {details}"
        if success:
            self.info(msg, task_name)
        else:
            self.error(msg, task_name)

    def get_recent_logs(self, lines: int = 100, level: Optional[str] = None) -> list:
        log_file = os.path.join(config.log_dir, 'tracker.log')
        if not os.path.exists(log_file):
            return []

        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        if level:
            level_upper = level.upper()
            all_lines = [l for l in all_lines if f'[{level_upper}]' in l]

        return all_lines[-lines:]

    def clear_logs(self) -> None:
        log_file = os.path.join(config.log_dir, 'tracker.log')
        if os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('')


logger = Logger()
