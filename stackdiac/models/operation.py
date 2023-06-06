import os
from pydantic import BaseModel, parse_obj_as
import logging
from typing import Any
from deepmerge import always_merger


logger = logging.getLogger(__name__)

# operations:
#   deploy:
#     configurations:
#       hcloud-flannel:
#         title: "hcloud k8s; flannel cni"
#         name: hcloud-flannel
#         modules: [pki, dns-zone, nodes, inventory, kubernetes, cluster-secret, hcloud-ccm]

class Configuration(BaseModel):
    title: str | None = None
    name: str | None = None
    modules: list[str]
    command: str | list[str] = "plan"

class PipelineStep(BaseModel):
    module: str
    title: str | None = None
    command: str | list[str] = "apply"

    def run(self, sd, cluster, cluster_stack, **kwargs):
        if self.title is None:
            self.title = f"run {self.command} on {self.module}"
            
        if self.command is not list:
            self.command = self.command.split(" ")
        
        
        sd.terragrunt(target=cluster_stack.stack.modules[self.module].built_vars["build_path"], 
                      terragrunt_options=self.command, 
                      cluster=cluster, **kwargs)
        logger.info(f"finished running step <{self.title}>")


class Operation(BaseModel):    
    name: str | None = None
    configurations: dict[str, Configuration] = {}
    configuration: str = "default"

    pipeline: list[PipelineStep] = []
    

    def run(self, sd, target, cluster, cluster_stack, **kwargs):
        logger.info(f"{self} running {len(self.pipeline)} steps pipeline")

        for step in self.pipeline:
            logger.info(f"running step {step}")
            step.run(sd, cluster, cluster_stack, **kwargs)


    def run_old(self, sd, target, cluster, stack, **kwargs):
        op = self.configurations[self.configuration]
        dest = os.path.join(sd.builddir, cluster.name, stack.name)
        args = ["run-all"]
        for module in op.modules:
            args.append("--terragrunt-include-dir")
            args.append(os.path.join(dest, module))

        #args.append()
        args.append(op.command)
       # args.append("--terragrunt-strict-include")

        

        logger.debug(f"will run terragrunt with args {args} in {dest}")

        sd.terragrunt(target=dest, terragrunt_options=args, cluster=cluster, stack=stack, **kwargs)
