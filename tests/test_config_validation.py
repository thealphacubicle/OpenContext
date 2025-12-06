"""Tests for configuration validation."""

import pytest
import yaml
from core.validators import (
    ConfigurationError,
    get_enabled_plugin_config,
    load_and_validate_config,
    validate_plugin_count,
)


def test_validate_plugin_count_single_enabled():
    """Test validation passes with one plugin enabled."""
    config = {
        "plugins": {
            "ckan": {"enabled": True},
        }
    }
    enabled, count = validate_plugin_count(config)
    assert count == 1
    assert enabled == ["ckan"]


def test_validate_plugin_count_multiple_enabled():
    """Test validation fails with multiple plugins enabled."""
    config = {
        "plugins": {
            "ckan": {"enabled": True},
            "custom_plugin": {"enabled": True},
        }
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_plugin_count(config)
    assert "Multiple Plugins Enabled" in str(exc_info.value)


def test_validate_plugin_count_none_enabled():
    """Test validation fails with no plugins enabled."""
    config = {
        "plugins": {
            "ckan": {"enabled": False},
        }
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_plugin_count(config)
    assert "No Plugins Enabled" in str(exc_info.value)


def test_get_enabled_plugin_config():
    """Test getting enabled plugin config."""
    config = {
        "plugins": {
            "ckan": {"enabled": True, "base_url": "https://data.example.com"},
        }
    }
    plugin_name, plugin_config = get_enabled_plugin_config(config)
    assert plugin_name == "ckan"
    assert plugin_config["base_url"] == "https://data.example.com"


def test_get_enabled_plugin_config_multiple():
    """Test getting enabled plugin config fails with multiple enabled."""
    config = {
        "plugins": {
            "ckan": {"enabled": True},
            "custom_plugin": {"enabled": True},
        }
    }
    with pytest.raises(ConfigurationError):
        get_enabled_plugin_config(config)

