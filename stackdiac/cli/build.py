
import click
import logging
import os
from stackdiac.stackd import stackd
from stackdiac.stackd import sd

logger = logging.getLogger(__name__)


@click.command()
@click.option("-t", "--target", help="build only target cluster:[stack]", default=None, show_default=True)
def build(target, **kwargs):
    only = target
    if only:
        ondata = only.split(":")
        if len(ondata) == 1:
            cluster = only
            stack = "all"
        elif len(ondata) == 2:
            cluster, stack = ondata
        else:
            raise ValueError("only can be cluster or cluster:stack")
    else:
        cluster = "all"
        stack = "all"
    sd.configure()
    sd.build(cluster=cluster, stack=stack, **kwargs)
    
