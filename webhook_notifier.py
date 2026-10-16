import json
import urllib.request
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal

class WebhookNotifier(QObject):
    """
    Asynchronous Webhook notifier supporting Discord, Slack, Telegram,
    and Microsoft Teams / Generic webhooks.
    """
    notification_completed = pyqtSignal(bool, str) # success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=4)

    def send_notification_async(self, webhook_url: str, webhook_type: str, host_ip: str, host_desc: str, is_down: bool, downtime: str = ""):
        """Submits an async webhook notification task."""
        if not webhook_url:
            return
        self._pool.submit(self._dispatch_webhook, webhook_url, webhook_type, host_ip, host_desc, is_down, downtime)

    def _dispatch_webhook(self, webhook_url: str, webhook_type: str, host_ip: str, host_desc: str, is_down: bool, downtime: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_text = "DOWN 🔴" if is_down else "RECOVERED 🟢"
        title = f"[D IP Monitor] Host {host_ip} is {status_text}"

        if is_down:
            desc = f"**Host:** {host_ip} ({host_desc})\n**Status:** Unreachable\n**Timestamp:** {now_str}"
            color_int = 15746887 # Red #ef4444
            slack_color = "#ef4444"
        else:
            duration_info = f"\n**Downtime:** {downtime}" if downtime else ""
            desc = f"**Host:** {host_ip} ({host_desc})\n**Status:** Reachable Again{duration_info}\n**Timestamp:** {now_str}"
            color_int = 2278730 # Green #22c55e
            slack_color = "#22c55e"

        payload = {}
        headers = {"Content-Type": "application/json", "User-Agent": "D-IP-Monitor/2.0"}

        try:
            w_type = webhook_type.lower()
            if "discord" in w_type:
                payload = {
                    "username": "D IP Monitor",
                    "embeds": [{
                        "title": title,
                        "description": desc,
                        "color": color_int,
                        "footer": {"text": "D IP Monitor System Alert"},
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }]
                }
            elif "slack" in w_type:
                payload = {
                    "text": title,
                    "attachments": [{
                        "color": slack_color,
                        "title": title,
                        "text": desc.replace("**", "*")
                    }]
                }
            elif "teams" in w_type:
                payload = {
                    "@type": "MessageCard",
                    "@context": "http://schema.org/extensions",
                    "themeColor": "EF4444" if is_down else "22C55E",
                    "summary": title,
                    "sections": [{
                        "activityTitle": title,
                        "activitySubtitle": now_str,
                        "text": desc.replace("**", "")
                    }]
                }
            elif "telegram" in w_type:
                # Telegram requires bot URL format: https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=<MSG>
                # Or user provides complete webhook URL
                text_msg = f"*{title}*\n\n{desc.replace('**', '*')}"
                if "chat_id=" in webhook_url:
                    sep = "&" if "?" in webhook_url else "?"
                    full_url = f"{webhook_url}{sep}text={urllib.parse.quote_plus(text_msg)}&parse_mode=Markdown"
                    req = urllib.request.Request(full_url, headers={"User-Agent": "D-IP-Monitor/2.0"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        pass
                    self.notification_completed.emit(True, f"Telegram notification sent for {host_ip}")
                    return
                else:
                    payload = {"text": text_msg, "parse_mode": "Markdown"}
            else:
                # Generic JSON webhook
                payload = {
                    "app": "D IP Monitor",
                    "event": "HOST_DOWN" if is_down else "HOST_UP",
                    "ip": host_ip,
                    "description": host_desc,
                    "downtime": downtime,
                    "timestamp": now_str
                }

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(webhook_url, data=data_bytes, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                code = resp.getcode()
                if 200 <= code < 300:
                    self.notification_completed.emit(True, f"Webhook sent for {host_ip} ({webhook_type})")
                else:
                    self.notification_completed.emit(False, f"Webhook response status {code} for {host_ip}")

        except Exception as e:
            self.notification_completed.emit(False, f"Webhook error for {host_ip}: {e}")
