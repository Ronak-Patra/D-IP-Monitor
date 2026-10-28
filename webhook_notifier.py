import json
import urllib.request
import urllib.parse
import urllib.error
import socket
import threading
import time
from queue import Queue
from datetime import datetime, timezone
from PyQt6.QtCore import QObject, pyqtSignal

class WebhookNotifier(QObject):
    """
    Asynchronous Webhook notifier supporting Discord, Slack, Telegram,
    and Microsoft Teams / Generic webhooks.
    Guarantees strict FIFO (First-In, First-Out) chronological ordering
    and offline network buffering so DOWN alerts are always delivered before UP alerts
    without race conditions, even during internet or router outages.
    """
    notification_completed = pyqtSignal(bool, str) # success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = Queue()
        self._is_running = True
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def send_notification_async(self, webhook_url: str, webhook_type: str, host_ip: str, host_desc: str, is_down: bool, downtime: str = ""):
        """Submits an async webhook notification task into the strict FIFO queue."""
        if not webhook_url:
            return
        event_time = datetime.now()
        self._queue.put((webhook_url, webhook_type, host_ip, host_desc, is_down, downtime, event_time))

    def stop(self):
        """Stops the worker thread cleanly."""
        self._is_running = False
        self._queue.put(None)

    def _process_queue(self):
        while self._is_running:
            try:
                item = self._queue.get(timeout=0.5)
            except Exception:
                continue

            if item is None:
                break

            webhook_url, webhook_type, host_ip, host_desc, is_down, downtime, event_time = item
            
            # Persistent FIFO dispatch with offline network buffering
            # If the network or internet drops, the event remains at the head of the queue
            # until connectivity is restored, preserving strict chronological delivery.
            max_retries = 120 # Up to ~5 minutes of offline buffering per event
            attempt = 0

            while self._is_running and attempt < max_retries:
                attempt += 1
                success, result_msg, retryable = self._dispatch_webhook(
                    webhook_url, webhook_type, host_ip, host_desc, is_down, downtime, event_time
                )
                
                if success:
                    self.notification_completed.emit(True, result_msg)
                    # Inter-message throttle to respect Discord/Slack rate limits (500ms)
                    time.sleep(0.5)
                    break
                
                if not retryable:
                    # Permanent client error (HTTP 400, 401, 403, 404, invalid URL, etc.)
                    # Do not hold up the queue for invalid configuration
                    self.notification_completed.emit(False, result_msg)
                    break

                # Retryable network/server error: wait briefly before retrying while network is offline
                for _ in range(25): # 2.5 seconds in 100ms steps so stop() exits promptly
                    if not self._is_running:
                        break
                    time.sleep(0.1)
            else:
                if attempt >= max_retries:
                    self.notification_completed.emit(False, f"Webhook expired after max retries for {host_ip}")

            self._queue.task_done()

    def _dispatch_webhook(self, webhook_url: str, webhook_type: str, host_ip: str, host_desc: str, is_down: bool, downtime: str, event_time: datetime):
        """
        Dispatches a single webhook request.
        Returns: tuple (success: bool, message: str, retryable: bool)
        """
        now_str = event_time.strftime("%Y-%m-%d %H:%M:%S")
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
                        "timestamp": event_time.astimezone(timezone.utc).isoformat()
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
                text_msg = f"*{title}*\n\n{desc.replace('**', '*')}"
                if "chat_id=" in webhook_url:
                    sep = "&" if "?" in webhook_url else "?"
                    full_url = f"{webhook_url}{sep}text={urllib.parse.quote_plus(text_msg)}&parse_mode=Markdown"
                    req = urllib.request.Request(full_url, headers={"User-Agent": "D-IP-Monitor/2.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        pass
                    return True, f"Telegram notification sent for {host_ip} ({status_text})", False
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
            with urllib.request.urlopen(req, timeout=6) as resp:
                code = resp.getcode()
                if 200 <= code < 300:
                    return True, f"Webhook sent for {host_ip}: {status_text} ({webhook_type})", False
                else:
                    return False, f"Webhook response status {code} for {host_ip}", False

        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_sec = 2.0
                try:
                    retry_sec = float(e.headers.get("Retry-After", 2.0))
                except Exception:
                    pass
                time.sleep(min(retry_sec, 5.0))
                return False, f"Webhook rate limited (HTTP 429) for {host_ip}", True
            elif 400 <= e.code < 500:
                # Permanent configuration error
                return False, f"Webhook rejected (HTTP {e.code}): {e.reason}", False
            else:
                # 5xx server error (temporary Discord/Slack glitch)
                return False, f"Webhook server error (HTTP {e.code}): {e.reason}", True
        except (urllib.error.URLError, socket.error, TimeoutError, ConnectionError, OSError) as e:
            # Network down / DNS lookup failure / host unreachable (temporary network outage)
            return False, f"Network offline / unreachable for {host_ip}: {e}", True
        except Exception as e:
            return False, f"Webhook error for {host_ip}: {e}", False
