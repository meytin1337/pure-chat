from pathlib import Path
from platformdirs import user_data_dir, user_config_dir

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
