"""Tests for CLI configure command — file-writing helpers and config generation."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
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


# ---------------------------------------------------------------------------
# _ensure_state_bucket
# ---------------------------------------------------------------------------


def _make_client_error(code: str) -> "botocore.exceptions.ClientError":  # noqa: F821
    """Build a ClientError using whatever ClientError class is in sys.modules."""
    import sys

    ClientError = sys.modules["botocore.exceptions"].ClientError
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "HeadBucket")


class TestEnsureStateBucket:
    """Unit tests for _ensure_state_bucket — all S3 calls are mocked."""

    # ------------------------------------------------------------------
    # Scenario 1: bucket already exists
    # ------------------------------------------------------------------

    def test_existing_bucket_returns_early_without_create(self, capsys):
        """head_bucket succeeds → create_bucket is never called."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        # head_bucket returns normally (bucket exists)
        mock_s3.head_bucket.return_value = {}

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("my-bucket", "us-east-1")

        mock_s3.create_bucket.assert_not_called()
        mock_s3.put_bucket_versioning.assert_not_called()
        mock_s3.put_bucket_encryption.assert_not_called()

    def test_existing_bucket_prints_already_exists_message(self, capsys):
        """When the bucket exists the function prints a status line containing the name."""

        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {}

        output_lines: list[str] = []
        # console.print is a rich Console — capture via patching
        with (
            patch("cli.commands.configure.boto3.client", return_value=mock_s3),
            patch(
                "cli.commands.configure.console.print",
                side_effect=lambda *a, **kw: output_lines.append(str(a[0])),
            ),
        ):
            _ensure_state_bucket("my-state-bucket", "us-east-1")

        assert any("my-state-bucket" in line for line in output_lines), (
            f"Expected bucket name in output, got: {output_lines}"
        )
        assert any("already exists" in line for line in output_lines), (
            f"Expected 'already exists' in output, got: {output_lines}"
        )

    # ------------------------------------------------------------------
    # Scenario 2: bucket missing in us-east-1
    # ------------------------------------------------------------------

    def test_missing_bucket_us_east_1_creates_without_location_constraint(self):
        """404 ClientError in us-east-1 → create_bucket called with no LocationConstraint."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("new-bucket", "us-east-1")

        mock_s3.create_bucket.assert_called_once_with(Bucket="new-bucket")
        # No CreateBucketConfiguration kwarg
        _, kwargs = mock_s3.create_bucket.call_args
        assert "CreateBucketConfiguration" not in kwargs

    def test_missing_bucket_us_east_1_no_such_bucket_code(self):
        """NoSuchBucket error code is also treated as missing → bucket is created."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("NoSuchBucket")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("new-bucket", "us-east-1")

        mock_s3.create_bucket.assert_called_once()

    def test_missing_bucket_us_east_1_enables_versioning(self):
        """After creating the bucket in us-east-1, versioning is enabled."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("new-bucket", "us-east-1")

        mock_s3.put_bucket_versioning.assert_called_once_with(
            Bucket="new-bucket",
            VersioningConfiguration={"Status": "Enabled"},
        )

    def test_missing_bucket_us_east_1_enables_aes256_encryption(self):
        """After creating the bucket in us-east-1, AES256 server-side encryption is set."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("new-bucket", "us-east-1")

        mock_s3.put_bucket_encryption.assert_called_once()
        _, kwargs = mock_s3.put_bucket_encryption.call_args
        rules = kwargs["ServerSideEncryptionConfiguration"]["Rules"]
        assert len(rules) == 1
        assert (
            rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
        )

    def test_missing_bucket_us_east_1_call_order(self):
        """create_bucket → put_bucket_versioning → put_bucket_encryption (in that order)."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("ordered-bucket", "us-east-1")

        method_names = [c[0] for c in mock_s3.method_calls]
        create_idx = method_names.index("create_bucket")
        versioning_idx = method_names.index("put_bucket_versioning")
        encryption_idx = method_names.index("put_bucket_encryption")

        assert create_idx < versioning_idx < encryption_idx, (
            f"Expected create < versioning < encryption, got indices "
            f"{create_idx}, {versioning_idx}, {encryption_idx}"
        )

    # ------------------------------------------------------------------
    # Scenario 3: bucket missing in non-us-east-1
    # ------------------------------------------------------------------

    def test_missing_bucket_non_us_east_1_creates_with_location_constraint(self):
        """In us-west-2, create_bucket must include CreateBucketConfiguration."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("west-bucket", "us-west-2")

        mock_s3.create_bucket.assert_called_once_with(
            Bucket="west-bucket",
            CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
        )

    def test_missing_bucket_eu_west_1_uses_correct_region_constraint(self):
        """LocationConstraint must match the region argument exactly."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("eu-bucket", "eu-west-1")

        _, kwargs = mock_s3.create_bucket.call_args
        assert kwargs["CreateBucketConfiguration"]["LocationConstraint"] == "eu-west-1"

    def test_missing_bucket_non_us_east_1_still_enables_versioning_and_encryption(self):
        """Versioning and encryption are enabled regardless of region."""
        from cli.commands.configure import _ensure_state_bucket

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = _make_client_error("404")

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            _ensure_state_bucket("west-bucket", "us-west-2")

        mock_s3.put_bucket_versioning.assert_called_once()
        mock_s3.put_bucket_encryption.assert_called_once()

    # ------------------------------------------------------------------
    # Scenario 4: non-404 ClientError is re-raised
    # ------------------------------------------------------------------

    def test_permission_denied_error_is_reraised(self):
        """A 403 AccessDenied ClientError must propagate — never swallowed."""
        import sys

        from cli.commands.configure import _ensure_state_bucket

        ClientError = sys.modules["botocore.exceptions"].ClientError
        access_denied = _make_client_error("403")

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = access_denied

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            with pytest.raises(ClientError):
                _ensure_state_bucket("locked-bucket", "us-east-1")

        mock_s3.create_bucket.assert_not_called()

    def test_unknown_client_error_is_reraised(self):
        """Any unrecognised error code (e.g. 500) is re-raised unchanged."""
        import sys

        from cli.commands.configure import _ensure_state_bucket

        ClientError = sys.modules["botocore.exceptions"].ClientError
        server_error = _make_client_error("500")

        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = server_error

        with patch("cli.commands.configure.boto3.client", return_value=mock_s3):
            with pytest.raises(ClientError):
                _ensure_state_bucket("any-bucket", "us-east-1")

    # ------------------------------------------------------------------
    # Scenario 5: _ensure_state_bucket called before terraform init
    # ------------------------------------------------------------------

    @patch("cli.commands.configure.subprocess.run")
    @patch("cli.commands.configure.run_cmd")
    @patch("cli.commands.configure.get_project_root")
    @patch("cli.commands.configure.get_terraform_dir")
    @patch("cli.commands.configure.questionary")
    def test_ensure_bucket_called_before_terraform_init(
        self,
        mock_q,
        mock_tf_dir,
        mock_root,
        mock_run_cmd,
        mock_subproc,
        tmp_path,
    ):
        """_ensure_state_bucket must be invoked before terraform init runs."""
        from cli.commands.configure import configure

        tf_dir = tmp_path / "terraform" / "aws"
        tf_dir.mkdir(parents=True)
        # No .terraform dir → init will run
        mock_root.return_value = tmp_path
        mock_tf_dir.return_value = tf_dir

        def _make_q_helper(responses: list):
            it = iter(responses)

            def _side(*a, **kw):
                m = MagicMock()
                m.ask.return_value = next(it)
                return m

            return _side

        mock_q.select.side_effect = _make_q_helper(
            ["Start from scratch", "staging", "CKAN"]
        )
        mock_q.text.side_effect = _make_q_helper(
            [
                "Org",
                "City",
                "https://data.example.gov",
                "https://data.example.gov",
                "City",
                "120",
                "us-east-1",
                "city-mcp-staging",
                "512",
                "120",
            ]
        )
        mock_q.confirm.side_effect = _make_q_helper([False])

        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        call_order: list[str] = []

        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {}  # bucket exists — no creation

        def _record_s3_call(*a, **kw):
            call_order.append("ensure_state_bucket")
            return mock_s3

        def _record_run_cmd(cmd, **kw):
            call_order.append("run_cmd:" + " ".join(str(c) for c in cmd))
            return MagicMock(returncode=0)

        mock_run_cmd.side_effect = _record_run_cmd

        with patch("cli.commands.configure.boto3.client", side_effect=_record_s3_call):
            configure()

        # The first recorded event must be the S3 client creation (bucket check),
        # which happens inside _ensure_state_bucket, before any terraform commands.
        assert "ensure_state_bucket" in call_order, (
            "boto3.client was never called — _ensure_state_bucket may not have run"
        )
        init_indices = [i for i, e in enumerate(call_order) if "init" in e]
        bucket_index = call_order.index("ensure_state_bucket")

        if init_indices:
            first_init = min(init_indices)
            assert bucket_index < first_init, (
                f"_ensure_state_bucket (index {bucket_index}) must run before "
                f"terraform init (index {first_init}). Order: {call_order}"
            )


# ---------------------------------------------------------------------------
# --state-bucket flag
# ---------------------------------------------------------------------------


def _make_q_helper(responses: list):
    """Return a side_effect function that returns MagicMocks with .ask() values."""
    it = iter(responses)

    def _side(*a, **kw):
        m = MagicMock()
        m.ask.return_value = next(it)
        return m

    return _side


def _run_configure_wizard(tmp_path, extra_kwargs: dict | None = None):
    """Run the configure wizard with a standard CKAN flow.

    extra_kwargs are forwarded to configure() (e.g. state_bucket="custom-bucket").
    Returns the list of run_cmd call_args_list items as strings.
    """
    from cli.commands.configure import configure

    tf_dir = tmp_path / "terraform" / "aws"
    tf_dir.mkdir(parents=True)

    mock_s3 = MagicMock()
    mock_s3.head_bucket.return_value = {}

    with (
        patch("cli.commands.configure.get_project_root", return_value=tmp_path),
        patch("cli.commands.configure.get_terraform_dir", return_value=tf_dir),
        patch("cli.commands.configure.boto3.client", return_value=mock_s3),
        patch("cli.commands.configure.questionary") as mock_q,
        patch("cli.commands.configure.subprocess.run") as mock_subproc,
        patch("cli.commands.configure.run_cmd") as mock_run_cmd,
    ):
        mock_q.select.side_effect = _make_q_helper(
            ["Start from scratch", "staging", "CKAN"]
        )
        mock_q.text.side_effect = _make_q_helper(
            [
                "Org",
                "City",
                "https://data.example.gov",
                "https://data.example.gov",
                "City",
                "120",
                "us-east-1",
                "city-mcp-staging",
                "512",
                "120",
            ]
        )
        mock_q.confirm.side_effect = _make_q_helper([False])
        mock_subproc.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="  default\n", stderr=""
        )
        mock_run_cmd.return_value = MagicMock(returncode=0)

        configure(**(extra_kwargs or {}))

        return mock_run_cmd.call_args_list, mock_s3


class TestStateBucketFlag:
    """Tests for the --state-bucket CLI option on configure()."""

    def test_default_bucket_passed_to_ensure_state_bucket(self, tmp_path):
        """When --state-bucket is not provided, _ensure_state_bucket uses the default name."""
        from cli.commands.configure import TERRAFORM_STATE_BUCKET

        _, mock_s3 = _run_configure_wizard(tmp_path)

        # boto3.client is called inside _ensure_state_bucket; head_bucket receives
        # the bucket name via the Bucket kwarg.
        mock_s3.head_bucket.assert_called_once_with(Bucket=TERRAFORM_STATE_BUCKET)

    def test_custom_bucket_passed_to_ensure_state_bucket(self, tmp_path):
        """When --state-bucket is provided, _ensure_state_bucket receives the custom name."""
        custom = "my-custom-tf-state"
        _, mock_s3 = _run_configure_wizard(tmp_path, {"state_bucket": custom})

        mock_s3.head_bucket.assert_called_once_with(Bucket=custom)

    def test_default_bucket_passes_backend_config_to_init(self, tmp_path):
        """With the default bucket, terraform init includes -backend-config for bucket and region."""
        from cli.commands.configure import TERRAFORM_STATE_BUCKET

        calls, _ = _run_configure_wizard(tmp_path)
        init_calls = [c for c in calls if "init" in str(c)]
        assert init_calls, "Expected at least one terraform init call"
        cmd_args = init_calls[0][0][0]
        assert any(
            f"-backend-config=bucket={TERRAFORM_STATE_BUCKET}" in arg
            for arg in cmd_args
        ), f"Expected -backend-config=bucket in terraform init; got: {cmd_args}"
        assert any("-backend-config=region=" in arg for arg in cmd_args), (
            f"Expected -backend-config=region in terraform init; got: {cmd_args}"
        )

    def test_custom_bucket_adds_backend_config_to_init(self, tmp_path):
        """With a custom bucket, terraform init is called WITH -backend-config=bucket=<name>."""
        custom = "my-custom-tf-state"
        calls, _ = _run_configure_wizard(tmp_path, {"state_bucket": custom})
        init_calls = [c for c in calls if "init" in str(c)]
        assert init_calls, "Expected at least one terraform init call"
        cmd_args = init_calls[0][0][0]
        assert any(f"-backend-config=bucket={custom}" in arg for arg in cmd_args), (
            f"Expected -backend-config=bucket={custom} in a terraform init call; "
            f"init calls were: {init_calls}"
        )
        assert any("-backend-config=region=" in arg for arg in cmd_args), (
            f"Expected -backend-config=region in terraform init; got: {cmd_args}"
        )
