"""Command line interface for refpapers."""

import click
import sys


# #### for subcommands
# @click.group()
# def cli():
#     pass
# ## then replace @click.command with @cli.command

# @click.argument('vararg', type=str, nargs=-1)
# @click.option('--flag', is_flag=True, help="")
# @click.option('--enum', type=click.Choice(choices))
@click.command()
def main(args=None):
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
