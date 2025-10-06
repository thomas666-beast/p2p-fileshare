import json
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.default_config = {
            "node": {
                "host": "localhost",
                "port": 8080,
                "share_dir": "./shared",
                "key": "default_password_123456",  # Longer default key
                "max_connections": 10
            },
            "client": {
                "default_host": "localhost",
                "default_port": 8080,
                "download_dir": "./downloads",
                "key": "default_password_123456",  # Longer default key
                "timeout": 30
            },
            "proxy": {
                "enabled": False,
                "type": "socks5",  # socks5, socks4, http
                "host": "127.0.0.1",
                "port": 9050,  # Default Tor port
                "username": "",
                "password": ""
            },
            "tor": {
                "enabled": False,
                "control_port": 9051,
                "password": ""
            },
            "logging": {
                "level": "INFO",
                "file": "p2p_fileshare.log",
                "max_size_mb": 10
            }
        }
        self.config = self.default_config.copy()
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                self._deep_update(self.config, user_config)
                print(f"✓ Loaded configuration from {self.config_path}")
            except Exception as e:
                print(f"✗ Error loading config file: {e}. Using defaults.")
        else:
            self.create_default_config()

    def create_default_config(self) -> None:
        """Create default configuration file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.default_config, f, indent=2)
            print(f"✓ Created default configuration at {self.config_path}")
            print("⚠ Please edit the 'key' in the config file for security!")
        except Exception as e:
            print(f"✗ Error creating config file: {e}")

    def _deep_update(self, target: Dict, source: Dict) -> None:
        """Recursively update nested dictionaries"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        try:
            return self.config.get(section, {}).get(key, default)
        except (KeyError, AttributeError):
            return default

    def set(self, section: str, key: str, value: Any) -> None:
        """Set a configuration value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def save(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✓ Configuration saved to {self.config_path}")
        except Exception as e:
            print(f"✗ Error saving config: {e}")

    def get_proxy_config(self) -> Optional[Dict]:
        """Get proxy configuration if enabled"""
        if not self.get('proxy', 'enabled', False):
            return None

        return {
            'proxy_type': self.get('proxy', 'type', 'socks5'),
            'addr': self.get('proxy', 'host', '127.0.0.1'),
            'port': self.get('proxy', 'port', 9050),
            'username': self.get('proxy', 'username', ''),
            'password': self.get('proxy', 'password', '')
        }

    def get_node_config(self) -> Dict:
        """Get node configuration"""
        return self.config.get('node', {})

    def get_client_config(self) -> Dict:
        """Get client configuration"""
        return self.config.get('client', {})

    def validate_key(self, key: str) -> bool:
        """Validate that key meets requirements"""
        return len(key) >= 8 if key else False
