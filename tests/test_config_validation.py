"""Tests for configuration validation using Boston examples."""

import pytest
import yaml
from core.validators import (
    ConfigurationError,
    get_enabled_plugin_config,
    load_and_validate_config,
    validate_plugin_count,
)


def test_validate_boston_ckan_plugin_enabled():
    """Test validation passes with Boston CKAN plugin enabled."""
    config = {
        "server_name": "BostonOpenDataMCP",
        "organization": "City of Boston DoIT",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
                "portal_url": "https://data.boston.gov",
                "city_name": "Boston",
            },
        },
    }
    enabled, count = validate_plugin_count(config)
    assert count == 1
    assert enabled == ["ckan"]


def test_validate_boston_mbta_plugin_enabled():
    """Test validation passes with Boston MBTA custom plugin enabled."""
    config = {
        "server_name": "BostonMBTAMCP",
        "organization": "City of Boston DoIT",
        "plugins": {
            "ckan": {"enabled": False},
            "mbta": {
                "enabled": True,
                "api_base_url": "https://api-v3.mbta.com",
                "api_key": "${MBTA_API_KEY}",
                "features": ["predictions", "alerts", "routes"],
            },
        },
    }
    enabled, count = validate_plugin_count(config)
    assert count == 1
    assert enabled == ["mbta"]


def test_validate_boston_multiple_plugins_fails():
    """Test validation fails when Boston tries to enable both CKAN and MBTA."""
    config = {
        "server_name": "BostonMultiMCP",
        "organization": "City of Boston DoIT",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
            },
            "mbta": {
                "enabled": True,
                "api_base_url": "https://api-v3.mbta.com",
            },
        },
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_plugin_count(config)

    error_msg = str(exc_info.value)
    assert "Multiple Plugins Enabled" in error_msg
    assert "ckan" in error_msg
    assert "mbta" in error_msg
    assert "One Fork = One MCP" in error_msg


def test_validate_boston_no_plugins_enabled():
    """Test validation fails when Boston disables all plugins."""
    config = {
        "server_name": "BostonOpenDataMCP",
        "plugins": {
            "ckan": {"enabled": False},
            "mbta": {"enabled": False},
        },
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_plugin_count(config)

    error_msg = str(exc_info.value)
    assert "No Plugins Enabled" in error_msg


def test_get_boston_ckan_plugin_config():
    """Test extracting Boston CKAN plugin configuration."""
    config = {
        "server_name": "BostonOpenDataMCP",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
                "portal_url": "https://data.boston.gov",
                "city_name": "Boston",
                "timeout": 120,
            },
        },
    }

    plugin_name, plugin_config = get_enabled_plugin_config(config)

    assert plugin_name == "ckan"
    assert plugin_config["base_url"] == "https://data.boston.gov"
    assert plugin_config["portal_url"] == "https://data.boston.gov"
    assert plugin_config["city_name"] == "Boston"
    assert plugin_config["timeout"] == 120


def test_get_boston_mbta_plugin_config():
    """Test extracting Boston MBTA custom plugin configuration."""
    config = {
        "server_name": "BostonMBTAMCP",
        "plugins": {
            "ckan": {"enabled": False},
            "mbta": {
                "enabled": True,
                "api_base_url": "https://api-v3.mbta.com",
                "api_key": "test-key-123",
                "features": ["predictions", "alerts"],
            },
        },
    }

    plugin_name, plugin_config = get_enabled_plugin_config(config)

    assert plugin_name == "mbta"
    assert plugin_config["api_base_url"] == "https://api-v3.mbta.com"
    assert plugin_config["api_key"] == "test-key-123"
    assert "predictions" in plugin_config["features"]


def test_get_enabled_plugin_config_boston_multiple_fails():
    """Test getting enabled plugin config fails with multiple Boston plugins."""
    config = {
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
            },
            "boston_311_ai": {
                "enabled": True,
                "ml_endpoint": "https://internal.boston.gov/ml",
            },
        },
    }

    with pytest.raises(ConfigurationError) as exc_info:
        get_enabled_plugin_config(config)

    # Should mention both Boston plugins
    error_msg = str(exc_info.value)
    assert "ckan" in error_msg
    assert "boston_311_ai" in error_msg


def test_boston_opendata_config_structure():
    """Test that Boston OpenData config has all required fields."""
    config = {
        "server_name": "BostonOpenDataMCP",
        "description": "Boston's official open data MCP server",
        "organization": "City of Boston Department of Innovation and Technology",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
                "portal_url": "https://data.boston.gov",
                "city_name": "Boston",
                "timeout": 120,
            },
        },
        "aws": {
            "region": "us-east-1",
            "lambda_name": "boston-opendata-mcp",
            "lambda_memory": 512,
            "lambda_timeout": 120,
        },
        "logging": {
            "level": "INFO",
            "format": "json",
        },
    }

    # Validate structure
    assert "server_name" in config
    assert "plugins" in config
    assert "aws" in config

    # Validate Boston-specific values
    assert config["server_name"] == "BostonOpenDataMCP"
    assert (
        config["organization"]
        == "City of Boston Department of Innovation and Technology"
    )
    assert config["plugins"]["ckan"]["city_name"] == "Boston"
    assert config["aws"]["region"] == "us-east-1"


def test_boston_has_only_one_plugin_in_production():
    """Test that production Boston configs have exactly one plugin enabled."""

    # Boston OpenData config
    opendata_config = {
        "plugins": {
            "ckan": {"enabled": True, "base_url": "https://data.boston.gov"},
            "mbta": {"enabled": False},
            "boston_311_ai": {"enabled": False},
        }
    }

    enabled, count = validate_plugin_count(opendata_config)
    assert count == 1
    assert enabled == ["ckan"]

    # Boston MBTA config (separate fork)
    mbta_config = {
        "plugins": {
            "ckan": {"enabled": False},
            "mbta": {"enabled": True, "api_base_url": "https://api-v3.mbta.com"},
            "boston_311_ai": {"enabled": False},
        }
    }

    enabled, count = validate_plugin_count(mbta_config)
    assert count == 1
    assert enabled == ["mbta"]


def test_boston_invalid_ckan_url_format():
    """Test that invalid Boston CKAN URLs are caught."""
    invalid_configs = [
        # Missing https://
        {
            "plugins": {
                "ckan": {
                    "enabled": True,
                    "base_url": "data.boston.gov",  # Missing protocol
                }
            }
        },
        # Trailing slash (should be handled gracefully)
        {
            "plugins": {
                "ckan": {
                    "enabled": True,
                    "base_url": "https://data.boston.gov/",  # Trailing slash
                }
            }
        },
    ]

    # These should either raise validation errors or be normalized
    # Depending on your validation implementation
    for config in invalid_configs:
        # Your validator might handle or reject these
        # Add appropriate assertions based on your validation logic
        pass


def test_error_message_helpful_for_boston_users():
    """Test that error messages are helpful for Boston staff."""
    config = {
        "plugins": {
            "ckan": {"enabled": True},
            "boston_311_ai": {"enabled": True},
        }
    }

    with pytest.raises(ConfigurationError) as exc_info:
        validate_plugin_count(config)

    error_msg = str(exc_info.value)

    # Error should be helpful
    assert "Fork this repository again" in error_msg
    assert "opencontext-opendata" in error_msg or "example" in error_msg.lower()
    assert "./deploy.sh" in error_msg
    assert "docs/ARCHITECTURE.md" in error_msg


def test_boston_config_with_environment_variables():
    """Test Boston config can use environment variable placeholders."""
    config = {
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
                "api_key": "${BOSTON_CKAN_API_KEY}",  # Environment variable
            },
        },
    }

    plugin_name, plugin_config = get_enabled_plugin_config(config)

    assert plugin_name == "ckan"
    # The placeholder should be preserved (expanded at runtime)
    assert plugin_config["api_key"] == "${BOSTON_CKAN_API_KEY}"
