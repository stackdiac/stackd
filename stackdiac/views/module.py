import os
from urllib.parse import urlparse
from pydantic import BaseModel, parse_obj_as
import logging
from typing import Any
from deepmerge import always_merger

import yaml, hvac
from stackdiac.models.backend import Backend
from stackdiac.models.spec import Spec, SpecModel

from stackdiac.models.operation import Operation

from .stack import Stack, StackModel, Module
from .secret import Secret

logger = logging.getLogger(__name__)

@api_app.post("/secret/{cluster_name}/{stack_name}/{module_name}/{secret_name}", operation_id="write_module_secret", response_model=Secret,
              tags=["secrets"])
async def write_module_secret(cluster_name:str, stack_name:str, module_name:str, secret_name:str, 
                              secret_type:str, secret:dict) -> Secret: