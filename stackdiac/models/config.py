from pydantic import BaseModel, Field
from typing import Union, Any, List, Optional
import os, logging, git, filecmp, shutil, yaml
from urllib.parse import urlparse
import requests
import io
import zipfile
import time
import os
import stat

from stackdiac.models.backend import Backend
from stackdiac.models.provider import Provider

from .repo import Repo
from .binary import Binaries, Binary
from .spec import Spec, SpecModel

from stackdiac.api import app as api_app

logger = logging.getLogger(__name__)

class Project(BaseModel):
    name: str
    title: Union[str, None] = None
    vault_address: Union[str, None] = None
    domain: str

# class Globals(BaseModel):
#     dns_zone: str
#     vault_address: str
#     tf_state_bucket: str
#     project: str


class ConfigModel(BaseModel):
    kind: str = "stackd"
    project: Project
    vars: dict = {}
    clusters_dir: str = "cluster"
    repos: dict[str, Repo] = {}
    binaries: Binaries
    backend: Backend | None = None
    providers: dict[str, Any] = {}
    spec: SpecModel | None = None


class Config(ConfigModel):
    spec: Spec | None = None
    
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        

@api_app.get("/config", operation_id="get_config", response_model=Config)
async def _api_get_config() -> Config:
    from stackdiac.stackd import sd
    return sd.conf


def get_initial_config(name: str, domain: str, 
    vault_address: Union[str, None], **kwargs) -> Config:
    return Config(
        backend=Backend(),
        project = Project(
            name = name,
            domain = domain,
            vault_address = vault_address,
            title = kwargs.get("title", None),
        ),
        vars = dict(
            dns_zone = domain,
            project = name,
            vault_address = vault_address,
        ),
        repos = dict(
            root=Repo(
                url="./", local=True,
                name="root", 
                ),
            core=Repo(
                url="https://github.com/stackdiac/core.git",
                #url="../../core", local=True,
                name="core", 
                tag="0.0.1-dev9",
                branch="dev"),

        ),
        binaries = dict(
            terraform = Binary(
                url = "https://releases.hashicorp.com/terraform/{version}/terraform_{version}_linux_amd64.zip",
                binary = "terraform",
                extract = "terraform",
                version="1.4.4",
            ),
            terragrunt = Binary(
                version = "0.45.2",
                url = "https://github.com/gruntwork-io/terragrunt/releases/download/v{version}/terragrunt_linux_amd64",
                binary = "terragrunt",
            ),
        )
    )


