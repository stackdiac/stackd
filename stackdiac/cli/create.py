
import click
import logging
import os, sys
import yaml

from stackdiac.stackd import sd
from stackdiac import models

logger = logging.getLogger(__name__)

@click.command()
@click.option("-p", "--path", default=".", show_default=True, help="Target directory to create IAC in")
@click.option("-n", "--name", help="Project code name", required=True)
@click.option("-t", "--title", help="Project visible name")
@click.option("-d", "--domain", help="Project domain", required=True)
@click.option("-f", "--force", help="Owerwrite existing project", is_flag=True)
@click.option("--vault-address", help="Vault address")
def create(path, force:bool, **kwargs):
    abspath = os.path.abspath(path)
    cfile = os.path.join(abspath, "stackd.yaml")
    if os.path.isfile(cfile) and not force:
        logger.error(f"Configuration file exists at {cfile}. Cannot initialize project here.\nUse -f/--force to owerwrite")
        sys.exit(1)

    cfg = models.get_initial_config(**kwargs)

    logger.info(f"initializing {kwargs['name']} in {abspath}")

    if not os.path.isdir(abspath):
        os.makedirs(abspath)
        logger.debug(f"created directory {abspath}")

    with open(cfile, "w") as f:
        f.write(yaml.dump(cfg.dict(exclude_none=True, exclude_unset=True)))
        logger.info(f"saved project at {cfile}")
    
    os.makedirs(os.path.join(abspath, "cluster"), exist_ok=True)

    if len(os.listdir(os.path.join(abspath, "cluster"))) == 0:
        logger.info("no clusters added")

    sd.root = abspath
    sd.configure()
    sd.initialize()
    sd.download_binaries()
    sd.update()
