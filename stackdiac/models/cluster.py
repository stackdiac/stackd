
import os
from urllib.parse import urlparse
from pydantic import BaseModel, parse_obj_as
import logging
from typing import Any
from deepmerge import always_merger

import yaml
from stackdiac.models.backend import Backend
from stackdiac.models.spec import Spec, SpecModel

from stackdiac.models.operation import Operation

from .stack import Stack, StackModel

logger = logging.getLogger(__name__)

class ClusterStackModel(BaseModel):
    name: str | None = None
    src: str | None = None
    vars: dict[str, Any] = {}
    stack: StackModel | None = None
    override: dict[str, Any] = {}
    backend: Backend | None = None
    operations: Any = {}
    

class ClusterStack(ClusterStackModel):
    stack: Stack | None = None

    class Config:
        arbitrary_types_allowed = True
        exclude = ["stack"]

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.name}>"

    def build(self, cluster, sd, **kwargs):

        #from stackdiac.stackd import sd
        

        if self.src is None:
            self.src = self.name

        # src is url with repo in scheme
        parsed_src = urlparse(self.src)
        if not parsed_src.scheme:
            parsed_src = urlparse(f"root:{self.src}") # add root repo
        if len(self.src.split("/")) == 1:
            parsed_src = urlparse(f"{parsed_src.scheme}:stack/{self.src}") # add stack dir

        repo = sd.conf.repos[parsed_src.scheme]

        if self.src.endswith(".yaml"):
            path = os.path.join(repo.repo_dir, parsed_src.path.lstrip("/"))           
        else:
            path = os.path.join(repo.repo_dir, parsed_src.path.lstrip("/"), "stack.yaml")
            

        url = parsed_src.geturl()

        stack_dir = os.path.dirname(path)

        self.stack = Spec(path=path, 
                        merge_from=always_merger.merge({"name": self.name}, self.override), 
                        jinja_env=sd.get_jinja_env(stack_dir)).parse_obj_as(Stack, stackd=sd, cluster=cluster)

      
     #   logger.debug(f"{self} stack: {self.stack}")
        self.stack.build(cluster_stack=self, cluster=cluster, sd=sd, **kwargs)
        cluster.built_stacks[self.name] = self.stack

        sd.counters.stacks += 1

class ClusterModel(BaseModel):
    name: str
    vars: dict[str, Any] = {}
    stacks: dict[str, ClusterStackModel] = {}    
    backend: Backend | None = None
    spec: SpecModel | None = None

class Cluster(ClusterModel):   
    stacks: dict[str, ClusterStack] = {}    
    built_stacks: dict[str, Stack] = {}
    spec: Spec | None = None


    class Config:        
        exceptions = True
        exclude = {"built_stacks"}

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        for sname, s in self.stacks.items():
            # s.cluster = self
            s.name = sname


    def build(self, sd, stack="all", **kwargs):
        sd.counters.clusters += 1
        if stack == "all":
            for s in self.stacks.values():
                s.build(cluster=self, sd=sd, **kwargs)
        else:
            s = self.stacks[stack]
            s.build(cluster=self, sd=sd, **kwargs)
        

from stackdiac.api import app as api_app


@api_app.get("/clusters/", operation_id="get_clusters", response_model=list[ClusterModel])
async def _api_get_clusters() -> list[Cluster]:    
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    logger.debug(f"get_clusters: {sd.clusters['data'].dict()}")
    return list(sd.clusters.values())

@api_app.get("/build/{cluster_name}", operation_id="build_cluster", response_model=ClusterModel)
async def build_cluster(cluster_name:str) -> Cluster:
    """
    cluster.stacks will setup while bulding
    """
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    cluster = sd.clusters[cluster_name]
    cluster.build(sd=sd)
    sd.counters.stop()
    logger.info(f"build_cluster: {cluster_name} {sd.counters}")
    return cluster