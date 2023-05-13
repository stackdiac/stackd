import logging
from typing import Any
from pydantic import BaseModel, parse_obj_as
from deepmerge import always_merger
from mergedeep import merge



logger = logging.getLogger(__name__)


class Backend(BaseModel):
    """
    Backend configuration.
    use backend.config.key to change state location
    """
    name: str | None = None
    config: dict[str, Any] = {}

    def dict(self, **kwargs):        
        if self.name == "local":
            self.config = {}
        return super().dict(**kwargs)


    def build(self, sd, stack, module, cluster, cluster_stack, **kwargs):
        
        _backend = Backend(config={
                "key": f"{cluster.name}/{module.get_namespace(stack)}",
            })
        for bk in [sd.conf, cluster, cluster_stack, stack, module]:
            if bk.backend:
                if bk.backend.name:
                    _backend.name = bk.backend.name
                _backend.config = always_merger.merge(_backend.config, bk.backend.config)
            
            
        
        #logger.debug(f"{self} building backend {self.name} {self.config} <- {_backend}")
        return _backend.dict()