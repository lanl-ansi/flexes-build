import json
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

def load_config(config_path=None):
    default = PACKAGE_DIR.joinpath('default_config.json')
    with default.open() as f:
        config = json.load(f)

    user_config = Path(config_path) if config_path is not None else PACKAGE_DIR.joinpath('config.json')
    if user_config.exists():
        with user_config.open() as f:
            user = json.load(f)

        for key, value in user.items():
            config[key] = value

    return config


def load_message_schema(message_schema_path=None):
    message_schema = Path(message_schema_path) if message_schema_path is not None else PACKAGE_DIR.joinpath('message_schema.json')
    with message_schema.open() as f:
        schema = json.load(f)
    return schema
