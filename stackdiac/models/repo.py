from jinja2 import Environment, FileSystemLoader
from jinja2.ext import do
from pydantic import BaseModel, Extra, Field
from typing import Union, Any, List, Optional
import os, logging, git, filecmp, shutil, yaml
from urllib.parse import urlparse
import os



logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class InstallItem(BaseModel):
    src: Optional[str]
    dest: Optional[str]

    def get_srcdst(self):
        return (self.src, self.dest or self.src)


class RepoConfig(BaseModel):
    kind: str
    install: Optional[List[InstallItem]]

class Repo(BaseModel):
    url: str # git repo url
    tag: str = "latest" # desired tag
    branch: str = "main"    
    name: str
    local: bool = False
    _jinja_env: Environment | None = None
    

    class Config:
        arbitrary_types_allowed = True
        allow_mutation = True
        extra = Extra.allow

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.name}>"

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    @property
    def templates_dir(self) -> str | None:
        d = os.path.join(self.repo_dir, "templates")
        if os.path.isdir(d):
            return d
        else:
            return None

    def _get_jinja_env(self):
        if self.templates_dir:
            return Environment(loader=FileSystemLoader(self.templates_dir), extensions=[do])
        else:
            return None
    
    def get_jinja_env(self):
        """
        caches environment in self._jinja_env
        """
        if not self._jinja_env:
            self._jinja_env = self._get_jinja_env()
        return self._jinja_env

    @property
    def repo_dir(self):
        from stackdiac.stackd import sd
        if self.local:
            return os.path.join(sd.root, self.url)
        else:
            return os.path.join(sd.root, "repo", self.name)

    def checkout(self):
        if self.local:
            logger.debug(f"{self} local repo, skipping checkout")
            return
        # check if target directory already exists and is a Git repository
        os.makedirs(self.repo_dir, exist_ok=True)

        if os.path.isdir(f"{self.repo_dir}/.git"):
            # open existing repository
            repo = git.Repo(self.repo_dir)
            # fetch latest changes from remote
            repo.remotes.origin.fetch()
        else:
            # clone new repository
            repo = git.Repo.clone_from(
                self.url,
                to_path=self.repo_dir,
                depth=1,  # clone only the latest commit
                env={"GIT_ASKPASS": "/usr/bin/true"},  # disable prompt for password
                branch=self.branch,
            )
            logger.debug(f"cloned {repo}")

        # checkout specified or latest tag
        tags = repo.tags
        if not tags:
            raise ValueError(f"No tags found in repository {self}")
        
        if self.tag in [str(t) for t in tags]:
            repo.git.checkout(self.tag)
        else:
            raise ValueError(f"Tag '{self.tag}' not found in repository")
            
    
    def copyfiles(self, source, dest):
        source_path = os.path.join(self.repo_dir, source)
        dest_path = os.path.join(os.getcwd(), dest)
        if os.path.exists(source_path):
            if os.path.isdir(source_path):
                for root, dirs, files in os.walk(source_path):
                    rel_root = os.path.relpath(root, source_path)
                    dest_dir = os.path.join(dest_path, rel_root)
                    os.makedirs(dest_dir, exist_ok=True)
                    for file in files:
                        src_file = os.path.join(root, file)
                        dst_file = os.path.join(dest_dir, file)
                        if not os.path.exists(dst_file) or not filecmp.cmp(src_file, dst_file):
                            shutil.copy2(src_file, dst_file)
                            logger.debug(f"Copied {src_file} to {dst_file}")
            else:
                if not os.path.exists(dest_path) or not filecmp.cmp(source_path, dest_path):
                    shutil.copy2(source_path, dest_path)
                    logger.debug(f"Copied {source_path} to {dest_path}")
        else:
            raise ValueError(f"Source path '{source_path}' not found in repository")

    def install(self):
        """
        Load repo config from stack.yaml file in repo root,
        and perform any installation steps specified.
        """
        stack_yaml = os.path.join(self.repo_dir, "stackd.yaml")
        if not os.path.exists(stack_yaml):
            logger.debug(f"No stackd.yaml found in {self.repo_dir}")
            return


        repo_config = RepoConfig.parse_obj(yaml.safe_load(open(stack_yaml).read()))

        if repo_config.kind != "repo":
            logger.debug(f"Repo {self.url} is not a repo kind")
            return

        if not repo_config.install:
            logger.info(f"No install steps specified in stackd.yaml for repo {self.url}")
            return

        for item in repo_config.install:
            if item.copy:
                self.copyfiles(*item.get_srcdst())
