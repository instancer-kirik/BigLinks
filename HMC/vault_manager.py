import os
import json
import subprocess
from pathlib import Path
from DEV.workspace import Workspace
import tempfile
import logging
class Vault:
    def __init__(self, name, path, cccore):
        self.name = name
        self.cccore = cccore
        self.path = Path(path)
        self.workspaces = {}
        self.config_file = self.path / '.vault_config.json'
        self.index_file = self.path / '.vault_index.json'
        logging.info(f"Initializing Vault: {name} at {path}")
        self.load_config()
        self.load_index()
       
    def load_config(self):
        logging.info(f"Loading config for vault: {self.name}")
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                self.workspaces = config.get('workspaces', {})
            logging.info(f"Config loaded for vault: {self.name}")
        else:
            logging.warning(f"Config file not found for vault: {self.name}. Creating new config.")
            self.workspaces = {}
            self.save_config()
        
    def save_config(self):
        logging.info(f"Saving config for vault: {self.name}")
        config = {
            'name': self.name,
            'workspaces': self.workspaces
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info(f"Config saved for vault: {self.name}")

    def add_workspace(self, workspace_name):
        if workspace_name not in self.workspaces:
            self.workspaces[workspace_name] = {}
            self.save_config()
            return True
        return False

    def remove_workspace(self, workspace_name):
        if workspace_name in self.workspaces:
            del self.workspaces[workspace_name]
            self.save_config()
            return True
        return False

    def get_workspace_names(self):
        return list(self.workspaces.keys())

    def load_index(self):
        logging.info(f"Loading index for vault: {self.name}")
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
            logging.info(f"Index loaded for vault: {self.name}")
        else:
            logging.warning(f"Index file not found for vault: {self.name}. Updating index.")
            self.update_index()

    def update_index(self):
        try:
            self.update_index_nix()
        except FileNotFoundError:
            logging.warning("Nix not found. Falling back to Python indexing.")
            self.update_index_python()

    def update_index_nix(self):
        script_path = Path(__file__).parent.parent / 'NITTY_GRITTY' / 'index.nix'
        cmd = [
            str(self.cccore.env_manager.nix_portable_path),
            "nix-shell",
            str(script_path),
            "--run",
            f"index-vault {self.path}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            self.index = json.loads(result.stdout)
            self.save_index()
        else:
            raise RuntimeError(f"Error updating index: {result.stderr}")

    def update_index_python(self):
        self.index = {'files': []}
        for root, _, files in os.walk(self.path):
            for file in files:
                if file.endswith(('.md', '.txt', '.png', '.jpg', '.jpeg', '.gif')):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(self.path)
                    stat = file_path.stat()
                    self.index['files'].append({
                        'path': str(rel_path),
                        'mtime': stat.st_mtime,
                        'size': stat.st_size,
                        'type': 'image' if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) else 'document'
                    })
        self.save_index()

    def save_index(self):
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)

    def get_file_info(self, rel_path):
        return next((f for f in self.index['files'] if f['path'] == rel_path), None)

class VaultManager:
    def __init__(self, settings_manager, cccore):
        self.settings_manager = settings_manager
        self.cccore = cccore
        self.app_config_dir = Path.home() / ".computinator_code"
        self.app_config_dir.mkdir(exist_ok=True)
        self.vaults_config_file = self.app_config_dir / "vaults_config.json"
        self.vaults = {}
        self.current_vault = None
        logging.info(f"VaultManager initialized. Config file: {self.vaults_config_file}")
        self.load_vaults()
        self.ensure_default_vault()
        logging.info(f"VaultManager initialized with {len(self.vaults)} vaults.")
        
    def load_vaults(self):
        logging.info("Loading vaults...")
        if os.path.exists(self.vaults_config_file):
            with open(self.vaults_config_file, 'r') as f:
                config = json.load(f)
                for name, path in config.get('vaults', {}).items():
                    logging.info(f"Loading vault: {name} at {path}")
                    try:
                        self.vaults[name] = Vault(name, path, self.cccore)
                        logging.info(f"Successfully loaded vault: {name}")
                    except Exception as e:
                        logging.error(f"Failed to load vault {name}: {str(e)}")
                default_vault_name = config.get('default')
                if default_vault_name in self.vaults:
                    self.current_vault = self.vaults[default_vault_name]
                    logging.info(f"Set current vault to: {default_vault_name}")
        else:
            logging.warning("Vaults config file not found.")
        
        self.cleanup_temp_vaults()
        
        if not self.vaults:
            logging.info("No vaults found after loading. Ensuring default vaults.")
            self.ensure_default_vaults()
        elif not self.current_vault:
            self.set_current_vault(next(iter(self.vaults)))

    def ensure_default_vault(self):
        if not self.vaults:
            logging.info("No vaults found. Creating default vault.")
            default_path = self.app_config_dir / "default_vault"
            self.add_vault_directory(str(default_path), "Default Vault")
        
        if not self.current_vault:
            self.set_current_vault(next(iter(self.vaults)))
        
        logging.info(f"Current vault set to: {self.current_vault.name if self.current_vault else 'None'}")

    def add_vault_directory(self, path, name=None):
        logging.info(f"Adding vault directory: {path} with name: {name}")
        if name is None:
            name = os.path.basename(path)

        counter = 1
        original_name = name
        while name in self.vaults:
            name = f"{original_name}_{counter}"
            counter += 1

        path = Path(path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created vault directory: {path}")
        
        try:
            new_vault = Vault(name, str(path), self.cccore)
            self.vaults[name] = new_vault
            self.save_vaults_config()
            logging.info(f"Successfully added new vault: {name} at {path}")
            return name
        except Exception as e:
            logging.error(f"Failed to create vault {name} at {path}: {str(e)}")
            return None

    def set_current_vault(self, name):
        if name not in self.vaults:
            logging.warning(f"Vault '{name}' does not exist.")
            return False
        
        self.current_vault = self.vaults[name]
        self.save_vaults_config()
        logging.info(f"Current vault set to: {name}")
        return True

    def ensure_default_vaults(self):
        logging.info("Ensuring default vaults...")
        if not self.vaults:
            logging.info("No vaults found. Creating default vault.")
            local_default_path = self.app_config_dir / "default_vault"
            local_default_name = self.add_vault_directory(str(local_default_path), "Default Vault")
            
            if local_default_name:
                logging.info(f"Created default vault: {local_default_name}")
                self.set_current_vault(local_default_name)
            else:
                logging.error("Failed to create default vault.")
        else:
            logging.info(f"Existing vaults found: {list(self.vaults.keys())}")
            if not self.current_vault:
                self.set_current_vault(next(iter(self.vaults)))

    def get_nix_store_path(self):
        try:
            # First, try using nix-portable
            nix_portable_path = self.cccore.env_manager.nix_portable_path
            if nix_portable_path.exists():
                result = subprocess.run([str(nix_portable_path), "nix-env", "-q"], capture_output=True, text=True)
                if result.returncode == 0:
                    return Path("/nix/store/computinator-vault")
            
            # If nix-portable fails, try system-installed Nix
            result = subprocess.run(["nix-env", "-q"], capture_output=True, text=True)
            if result.returncode == 0:
                return Path("/nix/store/computinator-vault")
        except Exception as e:
            logging.warning(f"Failed to get Nix store path: {e}")
        return None

    def get_config_file_path(self):
        return str(self.vaults_config_file)
    
    def get_current_vault_path(self):
        return self.current_vault.path if self.current_vault else None
    
    def open_vault_config_file(self):
        config_file_path = self.get_config_file_path()
        if os.path.exists(config_file_path):
            os.startfile(config_file_path)
        else:
            logging.warning(f"Vault config file not found at {config_file_path}")

    def load_current_vault(self):
        current_vault_name = self.vaults.get("default")
        if current_vault_name and current_vault_name in self.vaults:
            self.current_vault = self.vaults[current_vault_name]
            self.initialize_vault(self.current_vault)

    def initialize_vault(self, vault):
        logging.info(f"Initializing vault: {vault.name} at {vault.path}")
        if not os.path.exists(vault.path):
            os.makedirs(vault.path)
            logging.info(f"Created vault directory: {vault.path}")
        vault.load_config()
        vault.load_index()
        logging.info(f"Successfully initialized vault: {vault.name} at {vault.path}")

    def save_vaults_config(self):
        logging.info("Saving vaults configuration...")
        config = {
            'vaults': {name: str(vault.path) for name, vault in self.vaults.items()},
            'default': self.current_vault.name if self.current_vault else None
        }
        with open(self.vaults_config_file, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info("Vaults configuration saved successfully")

    def remove_vault_directory(self, name):
        if name not in self.vaults:
            logging.warning(f"Vault '{name}' does not exist.")
            return False
        
        del self.vaults[name]
        if self.current_vault and self.current_vault.name == name:
            self.current_vault = None
        self.save_vaults_config()
        logging.info(f"Removed vault: {name}")
        return True
    
    def rename_vault(self, old_name, new_name):
        if old_name in self.vaults and new_name not in self.vaults:
            vault = self.vaults.pop(old_name)
            vault.name = new_name
            self.vaults[new_name] = vault
            if self.current_vault and self.current_vault.name == old_name:
                self.current_vault = vault
            self.save_vaults_config()
            return True
        return False

    def set_default_vault(self, name):
        if name not in self.vaults:
            logging.warning(f"Vault '{name}' does not exist.")
            return False
        
        self.current_vault = self.vaults[name]
        self.save_vaults_config()
        self.initialize_vault(self.current_vault)
        logging.info(f"Set default vault to: {name}")
        return True

    def switch_vault(self, name):
        if name in self.vaults:
            self.current_vault = self.vaults[name]
            self.initialize_vault(self.current_vault)
            self.save_vaults_config()
            logging.info(f"Switched to vault: {name}")
            return True
        logging.warning(f"Vault '{name}' does not exist.")
        return False

    def get_current_vault(self):
        return self.current_vault
    
    def get_vaults(self):
        return list(self.vaults.keys())

    def get_vault_dirs(self):
        return [vault.path for vault in self.vaults.values()]

    def get_vault_name(self, path):
        for name, vault in self.vaults.items():
            if vault.path == path:
                return name
        return None 
    def get_vault_by_path(self, path):
        for vault in self.vaults.values():
            if vault.path == path:
                return vault
        return None
    def get_current_vault(self):
        if self.current_vault and isinstance(self.current_vault, Vault):
            return self.current_vault
        else:
            logging.warning("Current vault is not set or is not a Vault object.")
            return None

    def get_fileset(self, name):
        return self.current_vault.get_fileset(name) if self.current_vault else []

    def get_all_filesets(self):
        return self.current_vault.get_all_filesets() if self.current_vault else []

    def get_config(self, key, default=None):
        return self.settings_manager.get_value(key, default)

    def set_config(self, key, value):
        self.settings_manager.set_value(key, value)
    def set_current_vault(self, name):
        logging.info(f"Setting current vault to: {name}")
        if name not in self.vaults:
            logging.warning(f"Vault '{name}' does not exist.")
            return False
        
        self.current_vault = self.vaults[name]
        self.save_vaults_config()
        self.initialize_vault(self.current_vault)
        logging.info(f"Successfully set current vault to: {name}")
        return True
    def get_index(self):
        return self.current_vault.get_index() if self.current_vault else {}

    def is_vault_set(self):
        return self.current_vault is not None

    def open_vault(self, path):
        if os.path.exists(path):
            name = self.get_vault_name(path)
            if name:
                return self.switch_vault(name)
        return False

    def update_vault_index(self):
        if self.current_vault:
            self.current_vault.update_index()
    def cleanup_temp_vaults(self):
        temp_vaults = [name for name in list(self.vaults.keys()) if name.startswith("temp_vault")]
        for name in temp_vaults:
            del self.vaults[name]
        self.save_vaults_config()
        logging.info(f"Cleaned up {len(temp_vaults)} temporary vaults")