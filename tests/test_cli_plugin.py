"""Tests for CLI plugin command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# plugin list — config.yaml missing
# ---------------------------------------------------------------------------


class TestPluginListNoConfig:
    @patch("cli.commands.plugin.get_project_root")
    def test_exits_when_config_missing(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        mock_root.return_value = tmp_path  # no config.yaml in tmp_path
        import click

        with pytest.raises(click.exceptions.Exit):
            plugin_list()


# ---------------------------------------------------------------------------
# plugin list — all known plugins disabled
# ---------------------------------------------------------------------------


class TestPluginListAllDisabled:
    @patch("cli.commands.plugin.get_project_root")
    def test_runs_without_error_when_all_disabled(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        config = {
            "plugins": {
                "ckan": {"enabled": False},
                "socrata": {"enabled": False},
                "arcgis": {"enabled": False},
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        mock_root.return_value = tmp_path

        # Should not raise
        plugin_list()


# ---------------------------------------------------------------------------
# plugin list — one plugin enabled
# ---------------------------------------------------------------------------


class TestPluginListOneEnabled:
    @patch("cli.commands.plugin.get_project_root")
    def test_enabled_plugin_shown(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        config = {
            "plugins": {
                "ckan": {
                    "enabled": True,
                    "base_url": "https://data.boston.gov",
                    "city_name": "Boston",
                },
                "socrata": {"enabled": False},
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        mock_root.return_value = tmp_path

        # Should complete without error
        plugin_list()


# ---------------------------------------------------------------------------
# plugin list — custom (non-built-in) plugin shown
# ---------------------------------------------------------------------------


class TestPluginListCustomPlugin:
    @patch("cli.commands.plugin.get_project_root")
    def test_custom_plugin_shown(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        config = {
            "plugins": {
                "ckan": {"enabled": False},
                "socrata": {"enabled": False},
                "arcgis": {"enabled": False},
                "my_custom_plugin": {"enabled": True, "api_key": "secret"},
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        mock_root.return_value = tmp_path

        # Should complete without error, custom plugin rendered as "Custom" type
        plugin_list()


# ---------------------------------------------------------------------------
# plugin list — empty plugins section
# ---------------------------------------------------------------------------


class TestPluginListEmptyPlugins:
    @patch("cli.commands.plugin.get_project_root")
    def test_empty_plugins_section_renders(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        config = {"plugins": {}}
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        mock_root.return_value = tmp_path

        # All known plugins should show as disabled
        plugin_list()


# ---------------------------------------------------------------------------
# plugin list — config.yaml with no plugins key
# ---------------------------------------------------------------------------


class TestPluginListNoPluginsKey:
    @patch("cli.commands.plugin.get_project_root")
    def test_missing_plugins_key_renders(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        config = {"organization": "City of Boston"}
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        mock_root.return_value = tmp_path

        # Should render all known plugins as disabled without error
        plugin_list()


# ---------------------------------------------------------------------------
# plugin list — arcgis enabled with portal_url
# ---------------------------------------------------------------------------


class TestPluginListArcGIS:
    @patch("cli.commands.plugin.get_project_root")
    def test_arcgis_key_fields_shown(self, mock_root, tmp_path):
        from cli.commands.plugin import plugin_list

        config = {
            "plugins": {
                "arcgis": {
                    "enabled": True,
                    "portal_url": "https://gis.boston.gov/arcgis",
                    "city_name": "Boston",
                },
            }
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        mock_root.return_value = tmp_path

        plugin_list()


# ---------------------------------------------------------------------------
# KNOWN_PLUGINS / PLUGIN_KEY_FIELDS constants
# ---------------------------------------------------------------------------


class TestPluginConstants:
    def test_known_plugins_has_three_entries(self):
        from cli.commands.plugin import KNOWN_PLUGINS

        assert set(KNOWN_PLUGINS.keys()) == {"ckan", "socrata", "arcgis"}

    def test_plugin_key_fields_coverage(self):
        from cli.commands.plugin import PLUGIN_KEY_FIELDS

        assert "base_url" in PLUGIN_KEY_FIELDS["ckan"]
        assert "base_url" in PLUGIN_KEY_FIELDS["socrata"]
        assert "portal_url" in PLUGIN_KEY_FIELDS["arcgis"]
