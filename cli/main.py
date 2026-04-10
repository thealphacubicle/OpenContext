import typer

from cli.commands.architecture import architecture
from cli.commands.authenticate import authenticate
from cli.commands.configure import configure
from cli.commands.cost import app as cost_app
from cli.commands.deploy import deploy
from cli.commands.destroy import destroy
from cli.commands.domain import domain
from cli.commands.logs import logs
from cli.commands.plugin import plugin_app
from cli.commands.security import app as security_app
from cli.commands.serve import app as serve_app
from cli.commands.status import status
from cli.commands.test import app as test_app
from cli.commands.upgrade import app as upgrade_app
from cli.commands.validate import app as validate_app

app = typer.Typer(
    name="opencontext",
    help="OpenContext CLI — configure, deploy, and manage your MCP server.",
    no_args_is_help=True,
    add_completion=False,
)

app.command()(authenticate)
app.command()(configure)
app.command()(deploy)
app.command()(status)
app.command()(domain)
app.command()(destroy)
app.command()(logs)
app.command()(architecture)

app.add_typer(serve_app, name="serve")
app.add_typer(validate_app, name="validate")
app.add_typer(test_app, name="test")
app.add_typer(upgrade_app, name="upgrade")
app.add_typer(plugin_app, name="plugin")
app.add_typer(cost_app, name="cost")
app.add_typer(security_app, name="security")

if __name__ == "__main__":
    app()
