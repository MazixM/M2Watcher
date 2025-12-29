"""
Konfiguracja aplikacji M2Watcher
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

CONFIG_DIR = Path.home() / ".m2watcher"
CONFIG_FILE = CONFIG_DIR / "config.json"


class Config:
    """Klasa zarządzająca konfiguracją aplikacji"""
    
    DEFAULT_CONFIG = {
        "check_interval": 2.0,
        "network_check_samples": 5,
        "network_threshold": 1000,
        "debug": False,
        "sound_enabled": True,
        "sound_wait_for_input": True,
        "show_status": True,
        "discord": {
            "enabled": False,
            "bot_token": "",
            "guild_id": "",
            "user_id": "",
            "channel_id": ""
        }
    }
    
    def __init__(self):
        self._config = self.DEFAULT_CONFIG.copy()
        self._load_config()
    
    def _load_config(self) -> None:
        """Ładuje konfigurację z pliku"""
        CONFIG_DIR.mkdir(exist_ok=True)
        
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge z domyślną konfiguracją
                    self._config = {**self.DEFAULT_CONFIG, **loaded_config}
            except Exception as e:
                print(f"Błąd podczas ładowania konfiguracji: {e}")
    
    def save_config(self) -> None:
        """Zapisuje konfigurację do pliku"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Błąd podczas zapisywania konfiguracji: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Pobiera wartość konfiguracji"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Ustawia wartość konfiguracji"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

