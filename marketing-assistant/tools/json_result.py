"""JSON string helper for tool returns."""

from __future__ import annotations

import json
from typing import Any


def json_result(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)
