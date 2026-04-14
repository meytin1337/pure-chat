from pathlib import Path
from typing import Dict
from platformdirs import user_data_dir, user_config_dir
import tomllib
import tomli_w
from pure_chat.console import console

APP_NAME = "pure-chat"
APP_AUTHOR = "Mats Heemeyer"


def database_path() -> Path:
    """Returns the path to the SQLite database in the Data directory."""
    data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "storage.db"


def config_path(filename) -> Path:
    """Returns the path to the config file in the Config directory."""
    conf_dir = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    conf_dir.mkdir(parents=True, exist_ok=True)
    return conf_dir / filename


def load_config() -> Dict:
    config_file = config_path("config.toml")
    config = {}
    if config_file.exists():
        with open(config_file, "rb") as f:
            config = tomllib.load(f)
    return config


def write_config(key, value):
    file_path = config_path("config.toml")

    data = {}
    if file_path.exists():
        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            console.print(f"Error reading existing file: {e}", style="bold red")
            return

    data[key] = value
    try:
        with open(file_path, "wb") as f:
            tomli_w.dump(data, f)
        console.print(f"API key has been written to {file_path}")
    except Exception as e:
        console.print(f"An error occurred while saving: {e}", style="bold red")
