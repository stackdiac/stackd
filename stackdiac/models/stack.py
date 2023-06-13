
from urllib.parse import urlparse
from pydantic import BaseModel, parse_obj_as, Field
from deepmerge import always_merger
from copy import deepcopy
import logging, os
from typing import Any

import yaml
from stackdiac.models.backend import Backend
from stackdiac.models.spec import Spec, SpecModel

from stackdiac.models.operation import Operation
from stackdiac.models.provider import Provider

import hvac
from enum import Enum

logger = logging.getLogger(__name__)

        


class Variable(BaseModel):
    """
    terraform variable
    """
    name:str
    value: Any
    type: str = "string"

class ModuleDependency(BaseModel):
    name: str
    path: str
    abspath: str
    module_name: str
    stack_name: str

    @property
    def varname(self) -> str:
        return f"{self.stack_name}_{self.module_name}".replace("-", "_")

class ModuleSecretStatus(Enum):
    UNKNOWN = "unknown"
    NOT_EXISTS = "not_exists"
    EXISTS = "exists"
    VALID   = "valid"

class ModuleSecret(BaseModel):
    name: str | None = None
    secret_type: str | None = None
    secret_schema: dict | None = None
    required: bool = False
    status: ModuleSecretStatus = ModuleSecretStatus.UNKNOWN

    def build(self, cluster, cluster_stack, stack, sd, module, status, **kwargs):       

        if self.secret_schema is None and self.secret_type is not None:
            # extracting schema from stack.schema.components.schemas
            self.secret_schema = stack.stack_schema['components']['schemas'][self.secret_type]
            self.status = status

class ModuleSchemas(BaseModel):
    secrets: dict[str, ModuleSecret] = {}
    vars: str | None = None

    schemas: dict[str, Any] = {}

    def build(self, cluster, cluster_stack, stack, sd, module, **kwargs):        
        if self.vars:
            self.schemas["vars"] = stack.stack_schema['components']['schemas'][self.vars]

  

class Module(BaseModel):
    name: str | None = None
    source: str | None = None
    src: str | None = None
    vars: dict[str, Any] = {}
    module_vars: dict[str, Any] = {}
    built_vars: dict[str, Any] = {}
    providers: list[str] = []
    provider_overrides: dict[str, Any] = {}
    inputs: list[str] = []
    deps: list[str] = []
    tf_state_key: str | None = None
    tf_state_bucket: str | None = None
    tf_state_bucket_region: str | None = None
    tf_backend: str = "s3"
    tf_backend_config: dict[str, Any] = {}
    backend: Backend | None = None
    secrets: dict[str, ModuleSecret] = {}
    schemas: ModuleSchemas | None = None
    

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.name}>"

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.source:
            self.src = self.source            

        for name, secret in self.secrets.items():
            if secret.name is None:
                secret.name = name

    @property
    def abssrc(self) -> str:
        from stackdiac.stackd import sd
        assert self.src
        return sd.resolve_path(self.src)
        #return os.path.join(sd.root, self.src)

    @property
    def absdeps(self) -> list[str]:
        return [ os.path.join(os.path.dirname(self.abssrc), d) for d in self.deps ]
    
    
    def build_vars_file(self, sd, cluster_stack, cluster, **kwargs) -> str:
        return os.path.join(sd.root, "vars",  cluster.name, cluster_stack.name, self.name, "vars.yaml")
    
    def build_module_vars(self, sd, cluster_stack, cluster, **kwargs) -> dict[str, Any]:
        vars_file = self.build_vars_file(sd, cluster_stack, cluster)
        if os.path.exists(vars_file):
            return yaml.load(open(vars_file), Loader=yaml.FullLoader)
        else:
            return {}
   

    def build_deps(self, stack, module, cluster, deps:list[str], sd, **kwargs) -> list[ModuleDependency]:
        for d in deps:
            parts = [x for x in d.split("/") if x]
            if len(parts) == 2:
                stack_name, module_name = parts
            elif len(parts) == 1:
                module_name = parts[0]
                stack_name = stack.name
            else:
                raise Exception(f"invalid module dep {d}")
            yield ModuleDependency(
                name=d,
                path=d,
                abspath=os.path.join(sd.builddir, cluster.name, stack_name, module_name),
                module_name=module_name,
                stack_name=stack_name
            )

    @property
    def charts_root(self) -> str:
        from stackdiac.stackd import sd
        return os.path.join(sd.root, "charts")

    def get_template(self, template_name):
        from stackdiac.stackd import sd
        return sd.conf.repos["core"].get_jinja_env().get_template(template_name)

    def write(self, template_name, dest, **kwargs):
        tpl = self.get_template(template_name)
        
        with open(dest, "w") as f:
            f.write(tpl.render(**kwargs))

        # logger.debug(f"{self} writed {dest} from {tpl}")

    @property
    def remote_state_template(self) -> str:
        return f"remote_state.stackd.hcl.j2"

    
    def get_namespace(self, stack) -> str:
        return f"{stack.name}-{self.name}"

    

    def get_prefix(self, stack) -> str:
        return f"{stack.name}"

    
    def get_ingress_host(self, cluster, stack) -> str:
        from stackdiac.stackd import sd
        if self.name.startswith("in-"):
            name = self.name[3:]
        else:
            name = self.name
        return f"{stack.name}-{name}.{cluster.name}.{sd.dns_zone}"

    def build_vars(self, sd, cluster, cluster_stack, stack, **kwargs):
        
        return dict(
            prefix=self.get_prefix(stack),
            cluster_name=cluster.name,
            cluster=cluster.name,
            env=cluster.name,
            service=self.name,
            tg_abspath=self.abssrc,
            group="all", # legacy
            environment=cluster.name,
            ingress_host=self.get_ingress_host(cluster, stack),
            namespace=self.get_namespace(stack),
            charts_root=self.charts_root,
            module_secret=f"kv/{cluster.name}/module/{stack.name}/{self.name}",
            module_secret_path=f"{cluster.name}/module/{stack.name}/{self.name}",
        )

    @property
    def tg_module_src(self):
        """
            adding // before last path component to avoid terragrunt to download the module 
        """
        return f"{os.path.dirname(self.abssrc)}//{os.path.basename(self.abssrc)}"

    def get_build_dir(self, cluster, stack):
        from stackdiac.stackd import sd
        return os.path.join(sd.root, "build", cluster.name, stack.name, self.name)

    def build(self, cluster, cluster_stack, stack, sd, **kwargs):
        #from stackdiac.stackd import sd
        path = sd.resolve_module_path(self.src)
        dest = self.get_build_dir(cluster, stack)
        os.makedirs(dest, exist_ok=True)
        _vars = {
            'build_path': dest,
            'module_path': path,
            'project_root': sd.root,
        }
        
        varSources = [
            self.build_vars(sd, cluster, cluster_stack, stack, **kwargs),                      
        ]
        
        for v in varSources:
            always_merger.merge(_vars, deepcopy(v))       
        
        _build_vars = deepcopy(_vars)

        self.module_vars = self.build_module_vars(sd, cluster_stack, cluster, **kwargs)

        for v in [
                self.vars,
                sd.conf.vars,
                cluster.vars,
                cluster_stack.vars,
                cluster_stack.module_vars.get(self.name, {}),
                self.module_vars
                ]:
            always_merger.merge(_vars, deepcopy(v))

        self.built_vars = deepcopy(_vars)

        exclude_list = [
            "vault_address",
            "location",
            # "ingress_class",
            # "cluster_issuer",
            "kubernetes_version",
            "control_plane_endpoint",
            "ingress_kind",
            "mimir_url",
            "ingress_port_http",
            "ingress_port_https",
            "ingress_kind",
            # "nodes_network_ip_range",
            # "subdomain",
        ]
        # exclude_list = []
        # get all vars named from _build_vars.keys()


        def get_vars_list() -> list[Variable]:
            for k in _build_vars.keys():
                v = _vars[k]
                if k in exclude_list:
                    continue
                if isinstance(v, dict):
                    var_type = "map"
                elif isinstance(v, list):
                    var_type = "list"
                elif isinstance(v, bool):
                    var_type = "bool"
                elif isinstance(v, int):
                    var_type = "number"
                elif isinstance(v, str):
                    var_type = "string"
                else:
                    logger.warn(f"unknown type for var {k}={v} (type={type(v)})")
                    var_type = "string"
                yield Variable(name=k, value=v, type=var_type)
        
        bk = self.backend or Backend()

        # building secrets
        vault_module_secrets = []
        if self.secrets:
            try:
                resp = sd.vault.kv.v2.list_secrets(path=self.built_vars["module_secret_path"], mount_point='kv')
            except hvac.exceptions.InvalidPath:
                pass
            else:
                vault_module_secrets = resp["data"]["keys"]          


        for s in self.secrets.values():
            
            status = ModuleSecretStatus.EXISTS if s.name in vault_module_secrets else ModuleSecretStatus.NOT_EXISTS
            s.build(cluster, cluster_stack, stack, sd, module=self, status=status, **kwargs)
        
        # building schemas

        if self.schemas:
            self.schemas.build(cluster, cluster_stack, stack, sd, module=self, **kwargs)

        if not self.module_vars and self.schemas and self.schemas.vars:
            
            for v in self.schemas.schemas["vars"]["properties"].keys():                
                _v = self.built_vars.get(v, self.schemas.schemas["vars"]["properties"][v].get("default", None))
            
                if _v:
                    self.module_vars[v] = _v
        
        ctx = dict(module=self, cluster=cluster, stackd=sd, vars=_vars, 
            inputs=list(self.build_deps(stack=stack, cluster=cluster, module=self, deps=self.inputs, sd=sd, **kwargs)),
            module_deps=[ d.abspath for d in list(self.build_deps(stack=stack, cluster=cluster, module=self, 
                deps=self.deps, sd=sd, **kwargs)) ],
            vars_list=list(get_vars_list()),
            tf_backend=bk.build(sd, stack, self, cluster, cluster_stack, **kwargs),
             **kwargs)
        
        self.write("terragrunt.root.j2", os.path.join(dest, "terragrunt.hcl"), **ctx)        
        self.write("variables.tf.j2", os.path.join(dest, "_variables.tf"), **ctx)
        
        providers_data = { n: p.dict() for n, p in sd.providers.items() }
        always_merger.merge(providers_data, self.provider_overrides)

        versions = [ parse_obj_as(Provider, v) for k, v in providers_data.items() if k in self.providers ]

        self.write("versions.tf.j2", os.path.join(dest, "_versions.tf"), **dict(versions=versions, **ctx))

        self.write("vars.tfvars.json.j2", os.path.join(dest, "vars.tfvars.json"), **dict(versions=versions, **ctx))
        self.write("vars.tfvars.json.j2", os.path.join(dest, "vars.ansible.json"), **dict(vars=dict(stackd=ctx["vars"])))
        self.write("vars.tfvars.json.j2", os.path.join(dest, "vars.stackd.json"), **dict(vars=dict(_stackd=ctx["vars"])))

        # logger.debug(f"{self} building module {self.name} in {stack.name} from {path} to {dest}")
        sd.counters.modules += 1

         
class StackModel(BaseModel):
    name: str | None = None
    src: str | None = None
    example_vars: dict[str, Any] = {}  
    operations: dict[str, Operation] = {}
    modules: dict[str, Module]
    vars: dict[str, Any] = {}
    backend: Backend | None = None
    spec: SpecModel | None = None
    stack_schema: Any = Field({}, alias="schema")


class Stack(StackModel):
    spec: Spec | None = None

    class Config:
        orm_mode = True
        exclude = {'cluster'}
   

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
               
        for module_name, module in self.modules.items():
            module.name = module_name
        

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.name}>"


    def build(self, **kwargs):
        for module in self.modules.values():
            module.build(stack=self, **kwargs)