import uuid
from datetime import datetime, timedelta

class IpMonitor:
    """
    Represents a single IP address being monitored.
    Stores its details, status, and ping statistics.
    This class handles the core data structure for each monitored IP,
    including unique ID, status, ping stats, and per-IP alert preferences.
    """

    def __init__(self, ip_address: str, description: str, tag: str = "General"):
        self.id = str(uuid.uuid4())  # Generate a unique identifier for this monitor instance
        self.ip_address = ip_address
        self.description = description
        self.tag = tag if tag else "General"
        self.status = "Unknown"  # Initial status of the IP (e.g., "Unknown", "Reachable", "Unreachable")
        self.packet_loss = 0.0   # Percentage of lost packets (0, 5, 10, 15, 20...100%)
        self.total_pings = 0     # Total number of ping attempts for this IP
        self.failed_pings = 0    # Number of failed ping attempts for this IP
        self.unreachable_start_time = None  # Timestamp (datetime object) when the IP last became unreachable
        self.reachable_start_time = None # Timestamp (datetime object) when the IP last became reachable
        self.response_time = 0.0 # Latest response time in milliseconds
        self.latency_history = [] # Rolling buffer of last 30 ping response times
        self.ping_history = [] # Rolling buffer of last 20 ping results (True=success, False=fail) for 5% step loss

        # Flags to prevent duplicate email/popup alerts for the same status change
        self.email_sent_unreachable = False
        self.email_sent_reachable = False
        self.popup_shown_unreachable = False
        self.popup_shown_reachable = False

        # Per-IP settings for enabling/disabling alerts, independent of global settings
        self.enable_email_alerts_for_ip = True
        self.enable_popup_alerts_for_ip = True
        self.enable_sound_alerts_for_ip = True # Per-IP sound alert setting
        self.enable_webhook_alerts_for_ip = True # Per-IP webhook alert setting

    def add_latency_sample(self, latency: float):
        """Adds a response time sample, keeping only the last 30 samples."""
        self.latency_history.append(latency)
        if len(self.latency_history) > 30:
            self.latency_history.pop(0)

    def add_ping_sample(self, is_reachable: bool):
        """
        Records ping attempt in rolling buffer of 20 samples and recalculates packet loss.
        Each sample represents 5% loss (0%, 5%, 10%, 15%, 20%, 25%, 30%... 100%).
        """
        self.ping_history.append(is_reachable)
        if len(self.ping_history) > 20:
            self.ping_history.pop(0)

        failed_count = sum(1 for success in self.ping_history if not success)
        total_samples = len(self.ping_history)
        if total_samples == 0:
            self.packet_loss = 0.0
        else:
            raw_loss = (failed_count / total_samples) * 100.0
            # Snap to strict 5% intervals (0, 5, 10, 15, 20, 25, 30... 100)
            self.packet_loss = float(round(raw_loss / 5.0) * 5.0)

    def to_dict(self) -> dict:
        """
        Converts the IpMonitor object's attributes into a dictionary.
        This is used for serialization (saving) to a JSON file.
        datetime objects are converted to ISO format strings for JSON compatibility.
        """
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "description": self.description,
            "tag": self.tag,
            "status": self.status,
            "packet_loss": self.packet_loss,
            "ping_history": self.ping_history,
            "total_pings": self.total_pings,
            "failed_pings": self.failed_pings,
            "unreachable_start_time": self.unreachable_start_time.isoformat() if self.unreachable_start_time else None,
            "reachable_start_time": self.reachable_start_time.isoformat() if self.reachable_start_time else None, # Save reachable time
            "response_time": self.response_time, # Save response time
            "latency_history": self.latency_history, # Save rolling latency history
            "email_sent_unreachable": self.email_sent_unreachable,
            "email_sent_reachable": self.email_sent_reachable,
            "popup_shown_unreachable": self.popup_shown_unreachable,
            "popup_shown_reachable": self.popup_shown_reachable,
            "enable_email_alerts_for_ip": self.enable_email_alerts_for_ip,
            "enable_popup_alerts_for_ip": self.enable_popup_alerts_for_ip,
            "enable_sound_alerts_for_ip": self.enable_sound_alerts_for_ip, # Save sound alert setting
            "enable_webhook_alerts_for_ip": getattr(self, "enable_webhook_alerts_for_ip", True), # Save webhook alert setting
        }

    @classmethod
    def from_dict(cls, data: dict):
        """
        Reconstructs an IpMonitor object from a dictionary.
        This is used for deserialization (loading) from a JSON file,
        reconstructing the IP monitor objects when the app starts.
        """
        # Create a basic monitor object with essential data and optional tag
        monitor = IpMonitor(data['ip_address'], data['description'], tag=data.get('tag', 'General'))

        # Populate all other attributes from the dictionary, providing defaults for robustness
        monitor.id = data.get('id', str(uuid.uuid4())) # Use existing ID or generate a new one if missing
        monitor.status = data.get('status', "Unknown")
        monitor.packet_loss = float(round(data.get('packet_loss', 0.0) / 5.0) * 5.0)
        monitor.total_pings = data.get('total_pings', 0)
        monitor.failed_pings = data.get('failed_pings', 0)
        monitor.latency_history = [max(0.5, s) if s == 0.0 else s for s in data.get('latency_history', [])]
        monitor.ping_history = data.get('ping_history', [])

        # Convert ISO format string back to datetime object
        monitor.unreachable_start_time = datetime.fromisoformat(data['unreachable_start_time']) if data.get('unreachable_start_time') else None
        monitor.reachable_start_time = datetime.fromisoformat(data['reachable_start_time']) if data.get('reachable_start_time') else None # Load reachable time
        monitor.response_time = data.get('response_time', 0.0) # Load response time

        monitor.email_sent_unreachable = data.get('email_sent_unreachable', False)
        monitor.email_sent_reachable = data.get('email_sent_reachable', False)
        monitor.popup_shown_unreachable = data.get('popup_shown_unreachable', False)
        monitor.popup_shown_reachable = data.get('popup_shown_reachable', False)
        monitor.enable_email_alerts_for_ip = data.get('enable_email_alerts_for_ip', True)
        monitor.enable_popup_alerts_for_ip = data.get('enable_popup_alerts_for_ip', True)
        monitor.enable_sound_alerts_for_ip = data.get('enable_sound_alerts_for_ip', True) # Load sound alert setting
        monitor.enable_webhook_alerts_for_ip = data.get('enable_webhook_alerts_for_ip', True) # Load webhook alert setting
        return monitor

    @property
    def downtime(self) -> str:
        """
        Calculates and returns the downtime duration as a human-readable string
        if the IP is currently unreachable.
        """
        if self.status == "Unreachable" and self.unreachable_start_time:
            duration = datetime.now() - self.unreachable_start_time
            return self._format_duration(duration)
        return "0s"

    @property
    def uptime(self) -> str:
        """
        Calculates and returns the uptime duration as a human-readable string
        if the IP is currently reachable.
        """
        if self.status == "Reachable" and self.reachable_start_time:
            duration = datetime.now() - self.reachable_start_time
            return self._format_duration(duration)
        return "0s"


    def _format_duration(self, duration: timedelta) -> str:
        """Helper to format timedelta objects into a human-readable string."""
        total_seconds = int(duration.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d {hours}h"
