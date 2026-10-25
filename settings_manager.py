import configparser
import os
import json # Used for saving/loading the list of IpMonitor objects

class SettingsManager:
    """
    Manages loading and saving application settings (from settings.ini)
    and the list of monitored IP addresses (from monitored_ips.json).
    Ensures settings and IP list persistence across application sessions.
    """
    def __init__(self, config_file="settings.ini", ip_list_file="monitored_ips.json"):
        import sys
        if not os.path.isabs(config_file):
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(app_dir, config_file)

        if not os.path.isabs(ip_list_file):
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            ip_list_file = os.path.join(app_dir, ip_list_file)

        self.config_file = config_file
        self.ip_list_file = ip_list_file
        self.config = configparser.ConfigParser(interpolation=None)

        # Define default application settings. These are used if no config file exists
        # or if specific keys are missing from the file.
        self.default_settings = {
            "EMAIL": {
                "smtp_server": "",
                "smtp_port": "587",
                "sender_email": "",
                "recipient_email": "",
                "username": "",
                "password": "", # Store password (consider more secure methods for production)
                "enable_ssl": "True", # Stored as string, converted to bool on load
                "enable_email_alerts": "True", # Stored as string, converted to bool on load
            },
            "ALERTS": {
                "enable_popups": "True",
                "mute_sound_alerts": "False",
                "enable_sound_alerts": "True",
            },
            "MONITORING": {
                "ping_interval": "10",
                "unreachable_threshold": "3",
            },
            "LOGGING": {
                "log_directory": os.path.join(os.path.expanduser("~"), "Documents", "IPMonitorLogs"),
                "enable_file_logging": "True",
                "enable_hourly_log": "True",
            },
            "WEBHOOK": {
                "enable_webhooks": "False",
                "webhook_url": "",
                "webhook_type": "Discord",
                "webhook_url_discord": "",
                "webhook_url_slack": "",
                "webhook_url_teams": "",
                "webhook_url_telegram": "",
                "webhook_url_generic": "",
            },
            "UI": {
                "dark_mode": "True",
                "dashboard_position": "top",
                "enable_floating_hud": "False",
                "visible_columns": "0,1,2,3,4,5,6,7,8,9",
                "start_with_windows": "False",
                "minimize_to_tray": "True",
            },
        }
        self._load_settings()

    def _load_settings(self):
        """
        Loads settings from the config file. If the file or specific sections/keys
        are missing, it applies the default settings.
        """
        self.config.read(self.config_file, encoding='utf-8')
        # Apply defaults for any missing sections or keys
        for section, options in self.default_settings.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, default_value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, default_value)

    def save_settings(self):
        """
        Saves the current config state to settings.ini file,
        overwriting all current values.
        """
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
            
        

    def load_settings(self):
        """Loads settings from the settings.ini file."""
        # Read the file first to populate self.config
        self.config.read(self.config_file, encoding='utf-8')
        # Then, apply defaults for any missing sections/keys
        for section, keys in self.default_settings.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, default_value in keys.items():
                if not self.config.has_option(section, key):
                    # Store default values as strings
                    self.config.set(section, key, str(default_value))

    def set_setting(self, section: str, key: str, value: str):
        """
        Sets or updates a setting in the config. Always writes the value.
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

    def get_webhook_url_for_platform(self, platform: str) -> str:
        """Retrieves individual webhook URL for the specified platform."""
        key = self._get_webhook_platform_key(platform)
        url = self.get_setting("WEBHOOK", key)
        if not url:
            # Fallback to legacy single webhook_url if platform matches current_type
            current_type = self.get_setting("WEBHOOK", "webhook_type") or "Discord"
            if platform.lower() == current_type.lower():
                url = self.get_setting("WEBHOOK", "webhook_url") or ""
        return url or ""

    def set_webhook_url_for_platform(self, platform: str, url: str):
        """Persists individual webhook URL for the specified platform."""
        key = self._get_webhook_platform_key(platform)
        self.set_setting("WEBHOOK", key, url)

    def _get_webhook_platform_key(self, platform: str) -> str:
        p = (platform or "").lower()
        if "discord" in p:
            return "webhook_url_discord"
        elif "slack" in p:
            return "webhook_url_slack"
        elif "teams" in p:
            return "webhook_url_teams"
        elif "telegram" in p:
            return "webhook_url_telegram"
        else:
            return "webhook_url_generic"
        

    # --- IP List Management (existing methods) ---
    def save_ip_monitors(self, ip_monitors: list):
        """
        Saves the list of `IpMonitor` objects to a JSON file.
        Converts `IpMonitor` objects to dictionaries for serialization.
        """
        # Import IpMonitor here to avoid potential circular import issues
        from ip_monitor import IpMonitor # Assuming IpMonitor has a to_dict() method

        # Convert list of IpMonitor objects to a list of dictionaries for JSON serialization
        data_to_save = [monitor.to_dict() for monitor in ip_monitors]
        with open(self.ip_list_file, 'w') as f:
            json.dump(data_to_save, f, indent=4) # Dump with indentation for readability

    def get_setting(self, section: str, key: str, type_hint=None):
        """
        Retrieves a setting from the config, with an optional type hint for conversion.
            Converts the setting to the specified type (e.g., bool, int, float) if type_hint is provided.
        """
        value = self.config.get(section, key, raw=True, fallback=self.default_settings.get(section, {}).get(key, None))

        # Convert value if needed
        if type_hint is not None:
            if type_hint is bool:
                return str(value).lower() == 'true'
            elif type_hint is int:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
            elif type_hint is float:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
        return value



    def load_ip_monitors(self) -> list:
        """
        Loads the list of `IpMonitor` objects from the JSON file ('monitored_ips.json').
        Dictionaries loaded from JSON are converted back to `IpMonitor` objects using `from_dict()`.
        Handles cases where the file doesn't exist or is corrupted.
        """
        # Import IpMonitor here to avoid potential circular import issues
        from ip_monitor import IpMonitor # Assuming IpMonitor has a from_dict() method

        if not os.path.exists(self.ip_list_file):
            return [] # Return an empty list if the IP list file does not exist

        with open(self.ip_list_file, 'r') as f:
            try:
                data = json.load(f) # Load JSON data from file
                # Convert list of dictionaries back to a list of IpMonitor objects
                return [IpMonitor.from_dict(item) for item in data]
            except json.JSONDecodeError as e:
                print(f"Error decoding IP monitors JSON file: {e}. Returning empty list.")
                return []
            except Exception as e:
                print(f"An unexpected error occurred while loading IP monitors: {e}.")
                return []
