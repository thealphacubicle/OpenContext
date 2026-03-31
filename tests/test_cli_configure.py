"""Tests for CLI configure command — file-writing helpers and config generation."""

import yaml


# ---------------------------------------------------------------------------
# _write_config
# ---------------------------------------------------------------------------


class TestWriteConfig:
    def test_writes_valid_yaml(self, tmp_path):
        from cli.commands.configure import _write_config

        data = {
            "server_name": "Boston OpenData MCP Server",
            "organization": "City of Boston",
            "plugins": {
                "ckan": {
                    "enabled": True,
                    "base_url": "https://data.boston.gov",
                    "city_name": "Boston",
                    "timeout": 120,
                },
            },
            "aws": {
                "region": "us-east-1",
                "lambda_name": "boston-opendata-mcp-staging",
                "lambda_memory": 512,
                "lambda_timeout": 120,
            },
            "logging": {"level": "INFO", "format": "json"},
        }

        path = _write_config(tmp_path, data)

        assert path.exists()
        assert path.name == "config.yaml"

        with open(path) as f:
            content = f.read()
        assert content.startswith("---\n")

        parsed = yaml.safe_load(content)
        assert parsed["server_name"] == "Boston OpenData MCP Server"
        assert parsed["plugins"]["ckan"]["enabled"] is True
        assert parsed["aws"]["lambda_memory"] == 512

    def test_overwrites_existing(self, tmp_path):
        from cli.commands.configure import _write_config

        (tmp_path / "config.yaml").write_text("old: data")
        _write_config(tmp_path, {"server_name": "new"})

        parsed = yaml.safe_load((tmp_path / "config.yaml").read_text())
        assert parsed["server_name"] == "new"
        assert "old" not in parsed


# ---------------------------------------------------------------------------
# _write_tfvars
# ---------------------------------------------------------------------------


class TestWriteTfvars:
    def test_writes_all_fields(self, tmp_path):
        from cli.commands.configure import _write_tfvars

        path = _write_tfvars(
            tmp_path,
            env="prod",
            lambda_name="boston-opendata-mcp-prod",
            region="us-east-1",
            custom_domain="data-mcp.boston.gov",
        )

        assert path.exists()
        assert path.name == "prod.tfvars"

        content = path.read_text()
        assert 'lambda_name   = "boston-opendata-mcp-prod"' in content
        assert 'stage_name    = "prod"' in content
        assert 'aws_region    = "us-east-1"' in content
        assert 'config_file   = "config.yaml"' in content
        assert 'custom_domain = "data-mcp.boston.gov"' in content

    def test_empty_custom_domain(self, tmp_path):
        from cli.commands.configure import _write_tfvars

        path = _write_tfvars(
            tmp_path,
            env="staging",
            lambda_name="test-mcp-staging",
            region="us-west-2",
            custom_domain="",
        )

        content = path.read_text()
        assert 'custom_domain = ""' in content

    def test_staging_filename(self, tmp_path):
        from cli.commands.configure import _write_tfvars

        path = _write_tfvars(tmp_path, "staging", "func", "us-east-1", "")
        assert path.name == "staging.tfvars"

    def test_tfvars_roundtrip_with_load(self, tmp_path):
        """Written tfvars can be parsed back by load_tfvars."""
        from cli.commands.configure import _write_tfvars

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)

        _write_tfvars(tf_dir, "staging", "my-func", "us-east-1", "example.com")

        from unittest.mock import patch

        with patch("cli.utils.get_terraform_dir", return_value=tf_dir):
            from cli.utils import load_tfvars

            result = load_tfvars("staging")
            assert result["lambda_name"] == "my-func"
            assert result["stage_name"] == "staging"
            assert result["custom_domain"] == "example.com"


# ---------------------------------------------------------------------------
# _load_example_defaults
# ---------------------------------------------------------------------------


class TestLoadExampleDefaults:
    def test_loads_from_config_example(self, tmp_path):
        from cli.commands.configure import _load_example_defaults

        example = tmp_path / "config-example.yaml"
        example.write_text(
            yaml.dump(
                {
                    "organization": "Default Org",
                    "plugins": {"ckan": {"base_url": "https://default.gov"}},
                    "aws": {"region": "us-east-1"},
                }
            )
        )

        result = _load_example_defaults(tmp_path)
        assert result["organization"] == "Default Org"
        assert result["plugins"]["ckan"]["base_url"] == "https://default.gov"

    def test_returns_empty_when_missing(self, tmp_path):
        from cli.commands.configure import _load_example_defaults

        assert _load_example_defaults(tmp_path) == {}


# ---------------------------------------------------------------------------
# Plugin config structure
# ---------------------------------------------------------------------------


class TestPluginConfigStructure:
    """Verify _prompt_plugin_config returns the right keys for each plugin."""

    def _mock_ask(self, return_value):
        """Create a mock questionary question that returns return_value on .ask()."""
        from unittest.mock import MagicMock

        q = MagicMock()
        q.ask.return_value = return_value
        return q

    def test_ckan_config_keys(self):
        from unittest.mock import patch

        with patch("cli.commands.configure.questionary") as mock_q:
            mock_q.text.return_value = self._mock_ask("test-value")
            mock_q.text.side_effect = [
                self._mock_ask("https://data.example.gov"),
                self._mock_ask("https://data.example.gov"),
                self._mock_ask("TestCity"),
                self._mock_ask("120"),
            ]

            from cli.commands.configure import _prompt_plugin_config

            result = _prompt_plugin_config("CKAN", {})
            assert result["enabled"] is True
            assert "base_url" in result
            assert "portal_url" in result
            assert "city_name" in result
            assert "timeout" in result
            assert result["timeout"] == 120

    def test_socrata_config_keys(self):
        from unittest.mock import patch

        with patch("cli.commands.configure.questionary") as mock_q:
            mock_q.text.side_effect = [
                self._mock_ask("https://data.example.gov"),
                self._mock_ask("my-token"),
                self._mock_ask("120"),
            ]

            from cli.commands.configure import _prompt_plugin_config

            result = _prompt_plugin_config("Socrata", {})
            assert result["enabled"] is True
            assert "base_url" in result
            assert result["app_token"] == "my-token"
            assert "timeout" in result

    def test_socrata_optional_token_omitted(self):
        from unittest.mock import patch

        with patch("cli.commands.configure.questionary") as mock_q:
            mock_q.text.side_effect = [
                self._mock_ask("https://data.example.gov"),
                self._mock_ask(""),
                self._mock_ask("120"),
            ]

            from cli.commands.configure import _prompt_plugin_config

            result = _prompt_plugin_config("Socrata", {})
            assert "app_token" not in result

    def test_arcgis_config_keys(self):
        from unittest.mock import patch

        with patch("cli.commands.configure.questionary") as mock_q:
            mock_q.text.side_effect = [
                self._mock_ask("https://hub.arcgis.com"),
                self._mock_ask("TestCity"),
                self._mock_ask("120"),
            ]

            from cli.commands.configure import _prompt_plugin_config

            result = _prompt_plugin_config("ArcGIS", {})
            assert result["enabled"] is True
            assert "portal_url" in result
            assert "city_name" in result
            assert "timeout" in result
