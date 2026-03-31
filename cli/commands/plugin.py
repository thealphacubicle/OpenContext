from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.table import Table

from cli.utils import console, get_project_root

plugin_app = typer.Typer()

KNOWN_PLUGINS = {
    "ckan": "CKAN",
    "socrata": "Socrata",
    "arcgis": "ArcGIS",
}

PLUGIN_KEY_FIELDS: dict[str, list[str]] = {
    "ckan": ["base_url", "city_name"],
    "socrata": ["base_url"],
    "arcgis": ["portal_url", "city_name"],
}


@plugin_app.command("list")
def plugin_list() -> None:
    """List all plugins and their configuration status."""
    project_root = get_project_root()
    config_path = project_root / "config.yaml"

    if not config_path.exists():
        console.print(
            "[red]config.yaml not found.[/red]\n"
            "Run [bold]opencontext configure[/bold] to create one."
        )
        raise typer.Exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    plugins_cfg = config.get("plugins", {})

    table = Table(title="OpenContext Plugins", show_lines=True)
    table.add_column("Plugin", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Key Config")
    table.add_column("Type")

    for key, display_name in KNOWN_PLUGINS.items():
        plugin_data = plugins_cfg.get(key, {})
        is_enabled = isinstance(plugin_data, dict) and plugin_data.get("enabled", False)

        if is_enabled:
            status_cell = "[green]Enabled[/green]"
            key_fields = PLUGIN_KEY_FIELDS.get(key, [])
            key_values = ", ".join(
                f"{f}={plugin_data.get(f, '—')}"
                for f in key_fields
                if plugin_data.get(f)
            )
            config_cell = key_values or "—"
        else:
            status_cell = "[dim]Disabled[/dim]"
            config_cell = "—"

        table.add_row(display_name, status_cell, config_cell, "Built-in")

    # Show any custom plugins not in the known list
    for key, plugin_data in plugins_cfg.items():
        if key not in KNOWN_PLUGINS:
            is_enabled = isinstance(plugin_data, dict) and plugin_data.get("enabled", False)
            status_cell = "[green]Enabled[/green]" if is_enabled else "[dim]Disabled[/dim]"
            config_cell = "—"
            if is_enabled and isinstance(plugin_data, dict):
                pairs = [
                    f"{k}={v}" for k, v in plugin_data.items()
                    if k != "enabled" and v
                ][:3]
                config_cell = ", ".join(pairs) or "—"
            table.add_row(key, status_cell, config_cell, "Custom")

    console.print()
    console.print(table)
    console.print()
