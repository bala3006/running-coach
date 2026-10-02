import json

import keyring

SERVICE_NAME = "running-coach"


def get_credential(name: str) -> dict | None:
    value = keyring.get_password(SERVICE_NAME, name)
    return json.loads(value) if value else None


def set_credential(name: str, value: dict) -> None:
    keyring.set_password(SERVICE_NAME, name, json.dumps(value))


def delete_credential(name: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, name)
    except keyring.errors.PasswordDeleteError:
        pass
