

import os
from typing import Any
from jinja2 import Environment
from pydantic import BaseModel, parse_obj_as
import yaml
from deepmerge import always_merger

import logging
logger = logging.getLogger(__name__)


class SpecModel(BaseModel):
    path: str
    relpath: str | None = None
    source: str | None = None
    rendered: str | None = None
    data: dict[str, Any] = {}    
    jinja_template: bool = False # flag for ui

class Spec(SpecModel):
    jinja_env: Any | None = None
    merge_from: Any | None = None

    class Config:
        arbitrary_types_allowed = True        
        

    def __init__(self, jinja_env: Environment = None, **data: Any) -> None:
        super().__init__(**data)
        self.jinja_env = jinja_env
        self.jinja_template = jinja_env is not None
        self.relpath = os.path.relpath(self.path)
        

    def render(self, **kwargs):
        """
        loading jinja-templated yaml file if jinja_env is provided
        or raw data else
        """
        logger.debug(f"rendering {self.path} with {kwargs}")
        self.source = open(self.path).read()
     
        if self.jinja_env:
            self.rendered = self.jinja_env.from_string(open(self.path).read()).render(**kwargs)            
        else:
            self.rendered = self.source

        self.data = {}

        if self.merge_from:        
            self.data = always_merger.merge(self.data, self.merge_from)
            
        self.data = always_merger.merge(self.data, yaml.safe_load(self.rendered))
        

    def parse_obj_as(self, obj_type, **kwargs):        
        self.render(**kwargs)
        obj = parse_obj_as(obj_type, self.data)
        obj.spec = self
        return obj