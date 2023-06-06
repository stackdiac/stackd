from pydantic import BaseModel
import logging
from typing import Any

logger  = logging.getLogger(__name__)

class Secret(BaseModel):
    name: str | None = None
    module_name: str | None = None
    stack_name: str | None = None
    cluster_name: str | None = None
    secret_schema: Any | None = None
    secret_type: str | None = None
    data: dict[str, Any] = {}
    metadata: dict[str, Any] | None = None