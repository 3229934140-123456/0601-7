import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from utils.config_manager import config
from modules.logger_module import logger

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False


class Scheduler:
    def __init__(self):
        self.task_name = "scheduler"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tasks: Dict[str, Callable] = {}
        self._last_run_times: Dict[str, datetime] = {}

    def register_task(self, name: str, task_func: Callable, schedule_rule: Optional[str] = None) -> None:
        self._tasks[name] = task_func
        logger.info(f"注册任务: {name}", self.task_name)

    def run_task(self, name: str) -> Dict:
        if name not in self._tasks:
            logger.error(f"任务不存在: {name}", self.task_name)
            return {'success': False, 'error': 'Task not found'}

        logger.info(f"执行任务: {name}", self.task_name)
        try:
            result = self._tasks[name]()
            self._last_run_times[name] = datetime.now()
            logger.info(f"任务完成: {name}", self.task_name)
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"任务失败: {name} - {e}", self.task_name)
            return {'success': False, 'error': str(e)}

    def run_all_tasks(self) -> Dict:
        logger.task_start(self.task_name)
        results = {}
        for name in self._tasks:
            results[name] = self.run_task(name)
        logger.task_end(self.task_name, True, f"执行了 {len(results)} 个任务")
        return results

    def start_scheduler(self) -> bool:
        if not SCHEDULE_AVAILABLE:
            logger.warning("schedule库未安装, 无法使用定时任务", self.task_name)
            return False

        if self._running:
            logger.warning("调度器已在运行", self.task_name)
            return False

        interval = config.get('schedule.interval_hours', 6)
        schedule.every(interval).hours.do(self._scheduled_run)

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info(f"调度器已启动, 每 {interval} 小时执行一次", self.task_name)
        return True

    def stop_scheduler(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("调度器已停止", self.task_name)

    def _run_loop(self) -> None:
        while self._running:
            schedule.run_pending()
            time.sleep(60)

    def _scheduled_run(self) -> None:
        logger.info("定时任务触发", self.task_name)
        self.run_all_tasks()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def task_names(self) -> List[str]:
        return list(self._tasks.keys())

    def get_last_run_time(self, task_name: str) -> Optional[datetime]:
        return self._last_run_times.get(task_name)


scheduler = Scheduler()
