
import click
import coloredlogs, logging
import os, sys
import yaml

from stackdiac.stackd import sd, ProcessException

logger = logging.getLogger(__name__)

coloredlogs.install(level='DEBUG' if os.environ.get("DEBUG") else 'INFO', fmt='%(asctime)s %(levelname)s %(message)s')

@click.command()
def run():
    click.echo("stackd is workin")

@click.command()
def run_all():
    click.echo("stackd is workin")


@click.command()
@click.option("-p", "--path", default=".", show_default=True, help="project directory")
@click.option("-B", "--no-binaries", is_flag=True, help="do not download binaries")
def update(path, no_binaries:bool, **kwargs):
    sd.root = path
    sd.configure()
    if not no_binaries:
        sd.download_binaries()
    sd.update()


    

@click.group()
def cli():
    pass


from .create import create
from .build import build
from .ui import ui

cli.add_command(create)
cli.add_command(build)
cli.add_command(update)
cli.add_command(ui)


@click.command(context_settings={"ignore_unknown_options": True}, name="tg")
@click.option("-b", "--build", is_flag=True, help="deprecated, always building")
@click.argument("target")
@click.argument("terragrunt_options", nargs=-1)
def tg(target, terragrunt_options, **kwargs):
    sd.configure()
    sd.build()
    try:
        sd.terragrunt(target, [*terragrunt_options], **kwargs)
    except ProcessException as e:
        logger.error(f"terragrunt failed: {e}")
        sys.exit(1)
    
cli.add_command(tg)

@click.command(context_settings={"ignore_unknown_options": True}, name="op")
@click.option("-b", "--build", is_flag=True, help="deprecated, always building")
@click.argument("target")
def op(target, build:bool, **kwargs):
    sd.configure()
    sd.build()
    sd.run_operation(target=target, **kwargs)

cli.add_command(op)