import click
import logging
import os
import uvicorn
from stackdiac.stackd import sd
from stackdiac.api import app

logger = logging.getLogger(__name__)


@click.command()
@click.option("-H", "--host", help="host http server listen to", default="0.0.0.0", show_default=True)
@click.option("-P", "--port", help="port http server listen to", default=8000, show_default=True)
def ui(host, port, **kwargs):
    sd.configure()
    uvicorn.run(app, host=host, port=port)