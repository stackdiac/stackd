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
    command: str = "plan"

class Operation(BaseModel):
    """
    can be set in cluster config and in stack config
    selected configuration configured via cluster config
    """
    configurations: dict[str, Configuration] = {}
    configuration: str = "default"

    def run(self, sd, target, cluster, stack, **kwargs):
        logger.info(f"{self} running operation {self} {self.configuration}")
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
