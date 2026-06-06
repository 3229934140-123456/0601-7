import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional, Callable, Any
from utils.config_manager import config
from modules.logger_module import logger

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class NotificationModule:
    def __init__(self):
        self.task_name = "notification"
        self.retry_count = config.get('schedule.retry_count', 3)
        self.retry_delay = config.get('schedule.retry_delay_seconds', 30)

    def run(self, notifications: Optional[List[Dict]] = None) -> Dict:
        logger.task_start(self.task_name)
        stats = {'total': 0, 'sent': 0, 'failed': 0}

        try:
            if notifications is None:
                notifications = []

            stats['total'] = len(notifications)

            for notif in notifications:
                success = self.send_notification(
                    title=notif.get('title', ''),
                    message=notif.get('message', ''),
                    channels=notif.get('channels'),
                )
                if success:
                    stats['sent'] += 1
                else:
                    stats['failed'] += 1

            logger.task_end(self.task_name, True,
                           f"发送{stats['sent']}/{stats['total']}条通知")
            return stats

        except Exception as e:
            logger.error(f"通知任务失败: {str(e)}", self.task_name)
            logger.task_end(self.task_name, False, str(e))
            return stats

    def send_notification(self, title: str, message: str,
                         channels: Optional[List[str]] = None) -> bool:
        if not config.get('notification.enabled', True):
            return False

        if channels is None:
            channels = []
            channel_config = config.get('notification.channels', {})
            for ch, enabled in channel_config.items():
                if enabled:
                    channels.append(ch)

        if not channels:
            logger.warning("没有配置通知渠道", self.task_name)
            return False

        all_success = True
        for channel in channels:
            try:
                self._send_with_retry(channel, title, message)
            except Exception as e:
                logger.error(f"{channel} 通知发送失败: {e}", self.task_name)
                all_success = False

        return all_success

    def _send_with_retry(self, channel: str, title: str, message: str) -> None:
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                if channel == 'console':
                    self._send_console(title, message)
                elif channel == 'email':
                    self._send_email(title, message)
                elif channel == 'bark':
                    self._send_bark(title, message)
                elif channel == 'wechat':
                    self._send_wechat(title, message)
                else:
                    logger.warning(f"未知的通知渠道: {channel}", self.task_name)
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"{channel} 第{attempt}次发送失败: {e}, "
                    f"等待{self.retry_delay}秒后重试",
                    self.task_name
                )
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay)

        if last_error:
            raise last_error

    def _send_console(self, title: str, message: str) -> None:
        print("\n" + "="*50)
        print(f"📺 影视追踪提醒")
        print(f"标题: {title}")
        if message:
            print(f"内容: {message}")
        print("="*50 + "\n")
        logger.info(f"控制台通知: {title}", self.task_name)

    def _send_email(self, title: str, message: str) -> None:
        email_config = config.get('notification.email', {})
        smtp_server = email_config.get('smtp_server', '')
        smtp_port = email_config.get('smtp_port', 465)
        sender = email_config.get('sender', '')
        password = email_config.get('password', '')
        recipients = email_config.get('recipients', [])

        if not all([smtp_server, sender, password, recipients]):
            logger.warning("邮件配置不完整", self.task_name)
            return

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[影视追踪] {title}"
        msg.attach(MIMEText(message, 'plain', 'utf-8'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()

        try:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
            logger.info(f"邮件通知已发送: {title}", self.task_name)
        finally:
            server.quit()

    def _send_bark(self, title: str, message: str) -> None:
        bark_config = config.get('notification.bark', {})
        bark_url = bark_config.get('url', '')

        if not bark_url:
            logger.warning("Bark URL未配置", self.task_name)
            return

        import urllib.parse
        encoded_title = urllib.parse.quote(title)
        encoded_body = urllib.parse.quote(message)

        url = f"{bark_url}/{encoded_title}/{encoded_body}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            logger.info(f"Bark通知已发送: {title}", self.task_name)
        except requests.RequestException as e:
            raise Exception(f"Bark请求失败: {e}")

    def _send_wechat(self, title: str, message: str) -> None:
        logger.warning("微信通知待实现", self.task_name)

    def notify_new_episodes(self, new_episodes: List[Dict]) -> bool:
        if not new_episodes:
            return False

        title = f"新剧集更新 ({len(new_episodes)}集)"
        lines = []
        for ep in new_episodes[:10]:
            lines.append(f"- {ep['title']} S{ep['season']:02d}E{ep['episode']:02d}: {ep.get('ep_title', '')}")
        if len(new_episodes) > 10:
            lines.append(f"... 还有 {len(new_episodes) - 10} 集")

        message = "\n".join(lines)
        return self.send_notification(title, message)

    def notify_today_reminder(self, today_eps: List[Dict]) -> bool:
        if not today_eps:
            return False

        title = f"今日追剧提醒 ({len(today_eps)}集)"
        lines = []
        for ep in today_eps:
            lines.append(f"- {ep['title']} S{ep['season']:02d}E{ep['episode']:02d}")
        message = "\n".join(lines)
        return self.send_notification(title, message)

    def notify_weekly_report(self, summary: Dict) -> bool:
        title = "影视追踪周报"
        lines = [
            f"[本周总结]",
            f"新增影视: {summary.get('new_items', 0)} 部",
            f"观看进度: {summary.get('watched_episodes', 0)} 集",
            f"订阅剧集: {summary.get('subscribed_shows', 0)} 部",
            f"下周公映: {summary.get('upcoming_episodes', 0)} 集",
        ]
        message = "\n".join(lines)
        return self.send_notification(title, message)


notifier = NotificationModule()
