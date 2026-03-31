"""Pydantic configuration schema for Socrata plugin."""

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SocrataPluginConfig(BaseModel):
    """Configuration schema for Socrata plugin.

    This schema validates Socrata plugin configuration from config.yaml.
    """

    enabled: bool = Field(default=False, description="Whether plugin is enabled")
    base_url: str = Field(
        ..., description="Portal URL (e.g., https://data.example.gov)"
    )
    portal_url: str = Field(
        ..., description="Public portal URL (e.g., https://data.example.gov)"
    )
    city_name: str = Field(..., description="Name of the city/organization")
    app_token: str = Field(
        ..., description="Socrata app token (required for SODA3 API)"
    )
    timeout: float = Field(
        default=30.0, ge=1.0, le=300.0, description="HTTP request timeout in seconds"
    )

    @field_validator("base_url", "portal_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is well-formed."""
        if not v:
            raise ValueError("URL cannot be empty")
        try:
            result = urlparse(v)
            if not result.scheme or not result.netloc:
                raise ValueError("URL must include scheme (http/https) and hostname")
            if result.scheme not in ("http", "https"):
                raise ValueError("URL scheme must be http or https")
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        return v.rstrip("/")

    @field_validator("app_token")
    @classmethod
    def validate_app_token(cls, v: str) -> str:
        """Validate that app token is non-empty."""
        if not v or not v.strip():
            raise ValueError(
                "Socrata requires a free app token. Register at https://dev.socrata.com/register"
            )
        return v.strip()

    model_config = ConfigDict(extra="forbid")  # Reject unknown fields
