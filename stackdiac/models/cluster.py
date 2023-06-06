
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

class ClusterStackModel(BaseModel):
    name: str | None = None
    cluster_name: str | None = None
    src: str | None = None
    vars: dict[str, Any] = {}
    module_vars: dict[str, Any] = {}
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
        
        self.cluster_name = cluster.name

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


@api_app.get("/clusters/", operation_id="get_clusters", response_model=list[ClusterModel], tags=["cluster"])
async def _api_get_clusters() -> list[Cluster]:    
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    logger.debug(f"get_clusters: {sd.clusters['data'].dict()}")
    return list(sd.clusters.values())

@api_app.get("/build/{cluster_name}", operation_id="build_cluster", response_model=ClusterModel, tags=["cluster"])
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

@api_app.get("/cluster/{cluster_name}", operation_id="read_cluster", response_model=ClusterModel, tags=["cluster"])
async def read_cluster(cluster_name:str) -> Cluster:
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

@api_app.get("/stack/{cluster_name}/{stack_name}", operation_id="read_cluster_stack", response_model=ClusterStackModel, tags=["stack"])
async def read_cluster_stack(cluster_name:str, stack_name:str) -> ClusterStack:
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
    try:
        return cluster.stacks[stack_name]
    except KeyError:
        raise Exception(f"Stack {stack_name} not found in cluster {cluster_name}")
    
@api_app.get("/module/{cluster_name}/{stack_name}/{module_name}", operation_id="cluster_stack_module", response_model=Module, tags=["modules"])
async def build_module(cluster_name:str, stack_name:str, module_name:str) -> Module:
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
    try:
        return cluster.stacks[stack_name].stack.modules[module_name]
    except KeyError:
        raise Exception(f"Module {module_name} not found in stack {stack_name} in cluster {cluster_name}")
    
@api_app.post("/vars/{cluster_name}/{stack_name}/{module_name}", operation_id="write_module_vars", tags=["modules"])
async def write_module_vars(cluster_name:str, stack_name:str, module_name:str, vars:dict) -> Module:
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    cluster = sd.clusters[cluster_name]
    cluster.build(sd=sd)
    sd.counters.stop()
    logger.info(f"build_cluster: {cluster_name} {sd.counters}")
    vars_file = cluster.stacks[stack_name].stack.modules[module_name].build_vars_file(cluster=cluster, sd=sd,
                                                                                    module=cluster.stacks[stack_name].stack.modules[module_name],
                                                                                    cluster_stack=cluster.stacks[stack_name])
    if not os.path.isdir(os.path.dirname(vars_file)):
        os.makedirs(os.path.dirname(vars_file))
        logger.info(f"write_module_vars: {vars_file} created")

    with open(vars_file, "w") as f:
        yaml.dump(vars, f)

    cluster.build(sd=sd)
    return cluster.stacks[stack_name].stack.modules[module_name]

    
@api_app.get("/secret/{cluster_name}/{stack_name}/{module_name}", operation_id="list_module_secrets", tags=["secrets"])
async def list_module_secrets(cluster_name:str, stack_name:str, module_name:str) -> list[Secret]:
    """
    module secrets list
    """
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    cluster = sd.clusters[cluster_name]
    cluster.build(sd=sd)
    sd.counters.stop()
    logger.info(f"build_cluster: {cluster_name} {sd.counters}")
    try:
        m = cluster.stacks[stack_name].stack.modules[module_name]
    except KeyError:
        raise Exception(f"Module {module_name} not found in stack {stack_name} in cluster {cluster_name}")
    
    try:
        resp = sd.vault.kv.v2.list_secrets(path=m.built_vars["module_secret_path"], mount_point='kv')
    except hvac.exceptions.InvalidPath as e:
        logger.error(f"list_module_secrets: {e}")
        return []
    
    def _get_secrets():
        for k in resp["data"]["keys"]:
            rr = sd.vault.kv.v2.read_secret_version(path=f"{m.built_vars['module_secret_path']}/{k}", mount_point='kv')
            logger.debug(f"list_module_secrets: {rr}")
            data = dict(
                module_name=module_name,
                name=k,
                stack_name=stack_name,
                cluster_name=cluster_name,                
                **rr["data"])
            
            if rr["data"]["metadata"]["custom_metadata"] and rr["data"]["metadata"]["custom_metadata"].get("schema", False):
                data["secret_type"] = rr["data"]["metadata"]["custom_metadata"]["schema"]
                data["secret_schema"] = cluster.stacks[stack_name].stack.stack_schema['components']['schemas'][data["secret_type"]]
   
            yield data

    return list(_get_secrets())

@api_app.get("/secret/{cluster_name}/{stack_name}/{module_name}/{secret_name}", operation_id="read_module_secret", response_model=Secret, tags=["secrets"])
async def read_module_secret(cluster_name:str, stack_name:str, module_name:str, secret_name:str) -> Secret:
    """
    module secrets list
    """
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    cluster = sd.clusters[cluster_name]
    cluster.build(sd=sd)
    sd.counters.stop()
    logger.info(f"build_cluster: {cluster_name} {sd.counters}")
    try:
        m = cluster.stacks[stack_name].stack.modules[module_name]
    except KeyError:
        raise Exception(f"Module {module_name} not found in stack {stack_name} in cluster {cluster_name}")
    
    resp = sd.vault.kv.v2.read_secret_version(path=f'{m.built_vars["module_secret_path"]}/{secret_name}', mount_point='kv')
    
    data = dict(
                module_name=module_name,
                name=secret_name,
                stack_name=stack_name,
                cluster_name=cluster_name,
                **resp["data"])
    
    logger.info("read_module_secret: %s", resp)

    if resp["data"]["metadata"]["custom_metadata"].get("schema", False):
        data["secret_type"] = resp["data"]["metadata"]["custom_metadata"]["schema"]
        data["secret_schema"] = cluster.stacks[stack_name].stack.stack_schema['components']['schemas'][data["secret_type"]]
        
    return data

    
    

@api_app.post("/secret/{cluster_name}/{stack_name}/{module_name}/{secret_name}", operation_id="write_module_secret", response_model=Secret,
              tags=["secrets"])
async def write_module_secret(cluster_name:str, stack_name:str, module_name:str, secret_name:str, 
                              secret_type:str, secret:dict) -> Secret:
    """
    module secrets list
    """
    from stackdiac.stackd import Stackd
    sd = Stackd()
    sd.configure()
    cluster = sd.clusters[cluster_name]
    cluster.build(sd=sd)
    sd.counters.stop()
    logger.info(f"build_cluster: {cluster_name} {sd.counters}")
    try:
        m = cluster.stacks[stack_name].stack.modules[module_name]
    except KeyError:
        raise Exception(f"Module {module_name} not found in stack {stack_name} in cluster {cluster_name}")
    
    data = secret
    resp = sd.vault.kv.v2.create_or_update_secret(path=f'{m.built_vars["module_secret_path"]}/{secret_name}', mount_point='kv', 
                                                  secret=secret)    
    logger.info(f"saved secret to {m.built_vars['module_secret_path']}/{secret_name} version: {resp['data']['version']}")
    logger.debug(f"saved secret to {m.built_vars['module_secret_path']}/{secret_name} version: {resp} data: {data} secret: {secret} <<<")

    resp = sd.vault.kv.v2.read_secret_version(path=f'{m.built_vars["module_secret_path"]}/{secret_name}', mount_point='kv')    

    if not resp["data"]["metadata"]["custom_metadata"] or ("schema" not in resp["data"]["metadata"]["custom_metadata"]):
        sd.vault.kv.v2.update_metadata(path=f'{m.built_vars["module_secret_path"]}/{secret_name}', mount_point='kv', 
                                                        custom_metadata=dict(schema=secret_type))
        logger.info(f"saved secret metadata to {m.built_vars['module_secret_path']}/{secret_name} version: {resp['data']['version']}")
        resp = sd.vault.kv.v2.read_secret_version(path=f'{m.built_vars["module_secret_path"]}/{secret_name}', mount_point='kv')

    return dict(
                module_name=module_name,
                name=secret_name,
                stack_name=stack_name,
                cluster_name=cluster_name,
                secret_type=secret_type,
                **resp["data"])