# settings_manager.py
from PyQt6.QtCore import QSettings
import os

from PyQt6.QtCore import QSettings
import os

class SettingsManager:
    def __init__(self):
        self.settings =  QSettings("instance.select", "Computinator Code")
        self.ensure_vault_path()

    def get_value(self, key, default=None):
        return self.settings.value(key, default)  # Changed from getValue to value

    def set_value(self, key, value):
        self.settings.setValue(key, value)

    def save_layout(self, main_window):
        self.set_value("geometry", main_window.saveGeometry())
        self.set_value("windowState", main_window.saveState())

    def load_layout(self, main_window):
        geometry = self.get_value("geometry")
        window_state = self.get_value("windowState")
        if geometry:
            main_window.restoreGeometry(geometry)
        if window_state:
            main_window.restoreState(window_state)

    def get_vault_path(self):
        return self.get_value("vault_path", "")

    def set_vault_path(self, path):
        self.set_value("vault_path", path)

    def ensure_vault_path(self):
        vault_path = self.get_vault_path()
        if not vault_path:
            # Set a default vault path if not set
            default_vault_path = os.path.join(os.path.expanduser("~"), "ComputinatorVault")
            self.set_value("vault_path", default_vault_path)
            vault_path = default_vault_path
        if not os.path.exists(vault_path):
            os.makedirs(vault_path)

    # Add other settings-related methods as needed