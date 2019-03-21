import json
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

def load_config(config_path='config.json'):
    default = PACKAGE_DIR.joinpath('default_config.json')
    with default.open() as f:
        config = json.load(f)

    user_config = PACKAGE_DIR.joinpath(config_path)
    if user_config.exists():
        with user_config.open() as f:
            user = json.load(f)

        for key, value in user.items():
            config[key] = value

    return config


def load_message_schema(message_schema_path='message_schema.json'):
    message_schema = PACKAGE_DIR.joinpath(message_schema_path)
    with message_schema.open() as f:
        schema = json.load(f)
    return schema
