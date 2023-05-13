import copy
import json
import logging, yaml, os
from jinja2 import Environment, FileSystemLoader
import time
from urllib.parse import parse_qs, urlparse

from pydantic import parse_obj_as, BaseModel
from typing import Any
import subprocess
from deepmerge import always_merger


from stackdiac import models
from stackdiac.models.provider import Provider
from ..models import spec

from . import filters

logger = logging.getLogger(__name__)

class StackdCounters(BaseModel):
    clusters: int = 0
    stacks: int = 0
    modules: int = 0
    time: float = 0.0

    start_time: float = 0.0

    def reset(self):
        self.clusters = 0
        self.stacks = 0
        self.modules = 0
        self.time = 0
        self.start_time = time.time()

    def stop(self):
        self.time = time.time() - self.start_time

    def __str__(self) -> str:
        return f"<StackdCounters clusters: {self.clusters} stacks: {self.stacks} modules: {self.modules} time: {self.time:.4f}s>"

    def stats_message(self):
        return f"clusters: {self.clusters} stacks: {self.stacks} modules: {self.modules} time: {self.time:.4f}s"
    
class ProcessException(Exception):
    pass

class StackdModel(BaseModel):
    conf: models.ConfigModel | None = None
    root: str = os.environ.get("STACKD_ROOT", ".")
    clusters: dict[str, models.ClusterModel] = {}    
    providers: dict[str, models.Provider] = {}
    
class Stackd(StackdModel):
    conf: models.Config | None = None
    counters: StackdCounters = StackdCounters()

    class Config:
        # orm_mode = True
        exceptions = True
        exclude = {"versions", "counters"}
   #     exclude = {'clusters', 'versions', 'conf'}

    @property
    def dns_zone(self) -> str:
        return self.conf.project.domain

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.root = os.path.abspath(self.root)
        if not os.path.isfile(self.config_file):
            logger.warning(f"{self} config file {self.config_file} not found. starting unconfigured.")
        else:
            logger.debug("don't forget to run configure()")

    @property
    def builddir(self):
        return os.path.join(self.root, "build")

    def parse_tunnel(self, tunnel_qs: str) -> str:
        
        spec = dict(
            ssh = {},
            remote = {},
            local = {},
        )

        # server=tun@ssh.data.production.v10.link:22223&remote=mongodb-client.state:27017&local=dp-state-db.tun:27017

        qs = parse_qs(tunnel_qs)

        spec["ssh"]["username"], server_hostport = qs["server"][0].split("@")
        spec["ssh"]["host"], spec["ssh"]["port"] = server_hostport.split(":")
        spec["ssh"]["port"] = int(spec["ssh"]["port"])

        spec["remote"]["host"], spec["remote"]["port"] = qs["remote"][0].split(":")
        spec["remote"]["port"] = int(spec["remote"]["port"])

        local_endpoint, spec["local"]["port"] = qs["local"][0].split(":")
        spec["local"]["port"] = int(spec["local"]["port"])
        spec["local"]["service"], spec["local"]["namespace"] = local_endpoint.split(".")

        
        logger.info(f"parsing tunnel {qs} {spec}")
        return json.dumps(spec)

    def tpl_readfile_func(self, jinja_env):
        def func(path: str) -> str:
            return jinja_env.get_template(path).render(stackd=self)            
        return func
  

    def configure(self):
        
        from ..models import config

        os.chdir(self.root)
        logger.debug(f"{self} chdir to {self.root}")

        self.conf = spec.Spec(path=self.config_file,
                merge_from=models.get_initial_config(name="unconfigured", domain="example.com", 
                                                        vault_address="http://127.0.0.1:9090").dict()
                                            ).parse_obj_as(config.Config)

        # with open(self.config_file) as f:
        #     conf_data = models.get_initial_config(name="unconfigured", domain="example.com", vault_address="http://127.0.0.1:9090").dict()
        #     initial = copy.deepcopy(conf_data)
        #     data = yaml.safe_load(f.read())
        #     conf_data = always_merger.merge(conf_data, data)
        #     self.conf = parse_obj_as(config.Config, conf_data)
        #    # logger.debug(f"{self} loaded config: conf: {self.conf} \n\n data: {data} \n\n initial: {initial}\n\n")

        if os.path.isfile(self.resolve_path("core:versions.yaml")):
            with open(self.resolve_path("core:versions.yaml")) as f:
                versions_data = yaml.safe_load(f.read())
                if self.conf.providers:
                    versions_data = always_merger.merge(versions_data, self.conf.dict()["providers"])
                self.providers = parse_obj_as(dict[str, models.Provider], versions_data)
                for name, v in self.providers.items():
                    v.name = name
                    
              #  logger.debug(f"{self} loaded providers: {self.providers}")

        if os.path.isdir(self.conf.clusters_dir):            
            
            for c in os.listdir(self.conf.clusters_dir):
                if c.startswith("_"): continue
                if not os.path.isfile(os.path.join(self.conf.clusters_dir, c)):
                    continue
                
                cname = os.path.splitext(c)[0]
                self.clusters[cname] = spec.Spec(path=os.path.join(self.conf.clusters_dir, c),
                        jinja_env=self.get_jinja_env(self.conf.clusters_dir), 
                        merge_from={'name': cname}).parse_obj_as(models.Cluster, stackd=self)
                
                    
        self.counters.reset()
     #   logger.debug(f"{self} loaded clusters: {tuple(self.clusters.keys())}")
        logger.info(f"{self} configured with {len(self.conf.repos)} repos {len(self.clusters)} clusters: {list(self.clusters.keys())}")

    def get_jinja_env(self, template_root):
        jinja_env = Environment(loader=FileSystemLoader(template_root), extensions=['jinja2.ext.debug'])
        jinja_env.globals['readfile'] = self.tpl_readfile_func(jinja_env)            
        jinja_env.filters['from_yaml'] = filters.from_yaml
        jinja_env.filters['to_json'] = filters.to_json
        return jinja_env


    def initialize(self):      
               
        for r in self.conf.repos.values():
            r.stackd = self

        # for b in dict(self.conf.binaries).values():
        #     b.stackd = self
        
        logger.debug("%s initializing at %s", self, os.getcwd())

        os.makedirs(self.dataroot, exist_ok=True)
        os.makedirs(self.cacheroot, exist_ok=True)

    @property
    def dataroot(self):
        return os.path.join(self.root, ".stackd")
        
    @property
    def cacheroot(self):
        return os.path.join(self.dataroot, "cache")    

    def __str__(self):
        try:
            return f"<{self.__class__.__name__} {self.conf.project.name}>"
        except AttributeError as e:
            return f"<{self.__class__.__name__} unconfigured>"

    @property
    def config_file(self):
        return os.path.join(self.root, "stackd.yaml")

    def update(self):
        logger.debug("%s performing update", self)
        for _, r in self.conf.repos.items():
            r.checkout()
            #r.install()
            logger.info(f"{r} repo synced")

    def download_binaries(self):
        assert self.conf is not None
        for b in dict(self.conf.binaries).values():
            b.download()

    def build(self, **kwargs):
        self.counters.reset()
        #logger.debug("%s performing build %s", self, kwargs)
        cluster = kwargs.pop("cluster", "all")
        if cluster == "all":
            for _, c in self.clusters.items():
                c.build(sd=self, **kwargs)
        else:
            self.clusters[cluster].build(sd=self, **kwargs)
        
        self.counters.stop()
    
        logger.info(f"{self} build {self.counters.clusters} clusters, {self.counters.stacks} stacks, {self.counters.modules} modules in {self.counters.time:.4f} seconds")

    def resolve_stack_path(self, src):
        """
        Resolve a stack path to a local path
        repo can be specified as scheme: prefix
        if not specified, stack.yaml is assumed
        """
        parsed_src = urlparse(src)
        if not parsed_src.scheme:
            parsed_src = urlparse(f"root:{src}") # add root repo
        if len(self.src.split("/")) == 1:
            parsed_src = urlparse(f"{parsed_src.scheme}:stack/{src}") # add stack dir

        repo = self.conf.repos[parsed_src.scheme]

        if self.src.endswith(".yaml"):
            path = os.path.join(repo.repo_dir, parsed_src.path.lstrip("/"))           
        else:
            path = os.path.join(repo.repo_dir, parsed_src.path.lstrip("/"), "stack.yaml")
        
        return path


    def resolve_path(self, src):
        """
        Resolve a module path to a local path
        repo can be specified as scheme: prefix
        """
        parsed_src = urlparse(src)
        if not parsed_src.scheme:
            parsed_src = urlparse(f"root:{src}") # add root repo
       
        repo = self.conf.repos[parsed_src.scheme]
        return os.path.join(repo.repo_dir, parsed_src.path)
    
    resolve_module_path = resolve_path

    def terragrunt(self, target, terragrunt_options:list[str], **kwargs):
        env = dict(
            TERRAGRUNT_WORKING_DIR=target,
            TERRAGRUNT_TFPATH=self.conf.binaries.terraform.abspath,
            TF_INPUT="false",
        )
        opts = " ".join(terragrunt_options)
        cmd = f"{self.conf.binaries.terragrunt.abspath} {opts}"
        logger.debug(f"{self} terragrunt {target} {cmd} {env}")

        process = subprocess.Popen(cmd, shell=True, env=dict(**os.environ, **env))
        process.wait()
        if process.returncode != 0:
            raise ProcessException(f"terragrunt {target} failed with {process.returncode}")

    def run_operation(self, target, **kwargs):
        """
        target is in form <cluster>/<stack>/<operation>
        running  self.terragrunt with configured module path
    
        """
        cluster, stack, operation = target.split("/")
        self.clusters[cluster].stacks[stack].build(cluster=self.clusters[cluster], sd=self, **kwargs)
        self.clusters[cluster].stacks[stack].stack.operations[operation].run(target=target, sd=self, 
            cluster=self.clusters[cluster],
            stack=self.clusters[cluster].stacks[stack],**kwargs)
