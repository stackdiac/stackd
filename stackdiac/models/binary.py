import io
import os
import stat
import time
import zipfile

import requests
from pydantic import BaseModel
from typing import Any, Union



import logging
logger = logging.getLogger(__name__)


class Binary(BaseModel):
    """
    terraform, terragrunt binaries
    """
    #from .stackd import Stackd
    

    binary: str | None = None
    url: str | None = None
    extract: str | None = None
    version: str = "unconfigured_version"
    

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.binary}:{self.version}>"

    @property
    def abspath(self) -> str:
        from ..stackd.sdmod import sd
        return os.path.abspath(os.path.join(sd.root, "bin", self.binary))

    def download(self) -> None:
        """
        Download the binary from the URL, extract if necessary, and save to a file.
        """
        # Send a GET request to the URL and extract the binary from the response content
        url = self.url.format(version=self.version)
        response = requests.get(url, stream=True)
        start_time = time.time()

        logger.info(f"{self} downloading from {url}")
        
        if self.extract:
            # If the binary is within a zip archive, extract it
            zip_archive = zipfile.ZipFile(io.BytesIO(response.content))
            binary_content = zip_archive.read(self.extract)
        else:
            # If the binary is not within a zip archive, simply use the response content
            binary_content = response.content
        
        # Save the binary to a file in the `os.path.join(self.stackd.datapath, "bin")` folder
        os.makedirs(os.path.dirname(self.abspath), exist_ok=True)
        
        with open(self.abspath, "wb") as f:
            f.write(binary_content)

        # Log the download size and time using the logger
        download_time = time.time() - start_time
        download_size = len(binary_content)
        os.chmod(self.abspath, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        logger.info(f"{self} binary downloaded from {url} ({download_size} bytes) and saved to {self.abspath} in {download_time:.2f} seconds")


class Binaries(BaseModel):
    terraform: Binary = Binary(binary="terraform", 
        url="https://releases.hashicorp.com/terraform/{version}/terraform_{version}_linux_amd64.zip", 
        extract="terraform", version="1.4.4")
    terragrunt: Binary = Binary(binary="terragrunt", 
        url="https://github.com/gruntwork-io/terragrunt/releases/download/v{version}/terragrunt_linux_amd64",
        version="0.45.0")