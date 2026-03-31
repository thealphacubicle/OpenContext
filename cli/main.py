import typer

from cli.commands.authenticate import authenticate
from cli.commands.configure import configure
from cli.commands.deploy import deploy
from cli.commands.destroy import destroy
from cli.commands.domain import domain
from cli.commands.logs import logs
from cli.commands.status import status

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

if __name__ == "__main__":
    app()
