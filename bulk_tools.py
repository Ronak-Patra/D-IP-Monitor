import csv
import json
import re

class BulkManager:
    """Manages CSV/TXT import & export and full .dipm profile backup & restore."""

    @staticmethod
    def export_hosts_to_csv(ip_monitors: list, file_path: str):
        """Exports the monitored hosts table to a clean CSV file."""
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "IP Address", "Description", "Category / Tag", "Status",
                "Packet Loss (%)", "Response Time (ms)", "Uptime", "Downtime",
                "Email Alerts", "Popup Alerts", "Sound Alerts", "Webhook Alerts"
            ])
            for m in ip_monitors:
                writer.writerow([
                    m.ip_address,
                    m.description,
                    getattr(m, 'tag', 'General'),
                    m.status,
                    f"{m.packet_loss:.1f}",
                    f"{m.response_time:.1f}",
                    m.uptime,
                    m.downtime,
                    m.enable_email_alerts_for_ip,
                    m.enable_popup_alerts_for_ip,
                    m.enable_sound_alerts_for_ip,
                    getattr(m, 'enable_webhook_alerts_for_ip', True)
                ])

    @staticmethod
    def import_hosts_from_file(file_path: str) -> list:
        """
        Parses CSV or TXT file and returns a list of tuples: (ip, description, tag).
        Supports flexible formats:
          - IP
          - IP, Description
          - IP, Description, Tag
        """
        imported_hosts = []
        ip_regex = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            parts = [p.strip() for p in re.split(r"[,;\t]", line_str)]
            ip = parts[0]

            # Skip header line if first column is "IP" or "IP Address"
            if ip.lower() in ("ip", "ip address", "host", "hostname"):
                continue

            desc = parts[1] if len(parts) > 1 and parts[1] else ip
            tag = parts[2] if len(parts) > 2 and parts[2] else "General"

            imported_hosts.append((ip, desc, tag))

        return imported_hosts

    @staticmethod
    def export_profile_dipm(file_path: str, settings_dict: dict, ip_monitors: list):
        """Exports the full application state to a portable .dipm file."""
        profile_data = {
            "version": "2.0",
            "app": "D IP Monitor",
            "settings": settings_dict,
            "hosts": [m.to_dict() for m in ip_monitors]
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=4)

    @staticmethod
    def import_profile_dipm(file_path: str) -> tuple:
        """
        Loads and validates a .dipm backup profile.
        Returns: (settings_dict, list_of_host_dicts)
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "hosts" not in data:
            raise ValueError("Invalid .dipm profile format.")

        settings_dict = data.get("settings", {})
        hosts_data = data.get("hosts", [])
        return settings_dict, hosts_data
