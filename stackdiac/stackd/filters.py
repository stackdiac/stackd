
import json
from typing import Any
import yaml


def from_yaml(src) -> dict[str, Any]:
    return yaml.safe_load(src)

def to_json(data, **kwargs) -> str:
    return json.dumps(data, **kwargs)