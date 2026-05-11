"""Security tests for SSRF protection in the ArcGIS plugin.

Covers _validate_feature_url (static method) and the integration path through
query_data() to confirm the guard fires before any Feature Service HTTP call.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from plugins.arcgis.config_schema import ArcGISPluginConfig
from plugins.arcgis.plugin import ArcGISPlugin


# ── Fixtures ───────────────────────────────────────────────────────────────────

ARCGIS_CONFIG = {
    "portal_url": "https://hub.arcgis.com",
    "city_name": "TestCity",
    "timeout": 120,
}

PORTAL_URL = "https://hub.arcgis.com"


# ── _validate_feature_url ──────────────────────────────────────────────────────


class TestValidateFeatureUrl:
    """Unit tests for ArcGISPlugin._validate_feature_url static method.

    The method is called without instantiating the class.
    """

    @pytest.mark.parametrize(
        ("service_url", "portal_url"),
        [
            (
                "https://services.arcgis.com/abc/arcgis/rest/services/Foo/FeatureServer",
                "https://hub.arcgis.com",
            ),
            (
                "https://tiles.arcgis.com/tiles/xyz/arcgis/rest/services/Bar/FeatureServer",
                "https://hub.arcgis.com",
            ),
            (
                "https://custom-portal.citygov.com/service",
                "https://custom-portal.citygov.com",
            ),
            (
                "http://services.arcgis.com/abc/FeatureServer",
                "https://hub.arcgis.com",
            ),
        ],
        ids=[
            "services-arcgis-com",
            "tiles-arcgis-com",
            "custom-portal-matches-netloc",
            "http-scheme-arcgis-com",
        ],
    )
    def test_allowed_url_passes(self, service_url, portal_url):
        """URLs within *.arcgis.com or the configured portal host are accepted."""
        result = ArcGISPlugin._validate_feature_url(service_url, portal_url)
        assert result == service_url

    @pytest.mark.parametrize(
        ("service_url", "portal_url", "expected_fragment"),
        [
            (
                "http://169.254.169.254/latest/meta-data/iam/",
                "https://hub.arcgis.com",
                "not within allowed domains",
            ),
            (
                "https://evil.com/steal",
                "https://hub.arcgis.com",
                "not within allowed domains",
            ),
            (
                "https://notarcgis.com/arcgis/rest/services/Foo/FeatureServer",
                "https://hub.arcgis.com",
                "not within allowed domains",
            ),
            (
                "file:///etc/passwd",
                "https://hub.arcgis.com",
                "invalid scheme",
            ),
            (
                "ftp://services.arcgis.com/abc",
                "https://hub.arcgis.com",
                "invalid scheme",
            ),
            (
                "https://internal.vpc.local/service",
                "https://hub.arcgis.com",
                "not within allowed domains",
            ),
            (
                "https://169.254.169.254.evil.com/steal",
                "https://hub.arcgis.com",
                "not within allowed domains",
            ),
        ],
        ids=[
            "aws-metadata-endpoint",
            "arbitrary-external-host",
            "arcgis-looking-path-wrong-host",
            "file-scheme",
            "ftp-scheme",
            "internal-vpc-host",
            "ip-embedded-in-subdomain",
        ],
    )
    def test_disallowed_url_raises_value_error(
        self, service_url, portal_url, expected_fragment
    ):
        """URLs outside allowed domains or with disallowed schemes raise ValueError."""
        with pytest.raises(ValueError, match=expected_fragment):
            ArcGISPlugin._validate_feature_url(service_url, portal_url)


# ── query_data SSRF integration ────────────────────────────────────────────────


class TestQueryDataSSRF:
    """Integration-style tests verifying SSRF guard in query_data().

    The feature_client HTTP call must never be made when the URL is rejected.
    """

    @pytest.fixture()
    def plugin(self):
        """ArcGISPlugin with plugin_config pre-set and a mock feature_client."""
        p = ArcGISPlugin(ARCGIS_CONFIG)
        p.plugin_config = ArcGISPluginConfig(**ARCGIS_CONFIG)
        mock_feature_client = AsyncMock()
        p.feature_client = mock_feature_client
        return p

    @pytest.mark.asyncio
    async def test_aws_metadata_url_raises_before_http(self, plugin):
        """AWS metadata service URL raises ValueError; feature_client is never called."""
        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Malicious",
                "type": "Feature Layer",
                "service_url": "http://169.254.169.254/latest/meta-data/",
            },
        ):
            with pytest.raises(ValueError, match="not within allowed domains"):
                await plugin.query_data("abc123", {"where": "1=1"}, 100)

        plugin.feature_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_arbitrary_external_url_raises_before_http(self, plugin):
        """Arbitrary external host raises ValueError; feature_client is never called."""
        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Malicious",
                "type": "Feature Layer",
                "service_url": "https://evil.com/steal",
            },
        ):
            with pytest.raises(ValueError, match="not within allowed domains"):
                await plugin.query_data("abc123", {"where": "1=1"}, 100)

        plugin.feature_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_service_url_reaches_feature_client(self, plugin):
        """A valid arcgis.com service URL passes validation and calls the Feature Service."""
        valid_url = "https://services.arcgis.com/abc/FeatureServer/0"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "features": [
                {"attributes": {"name": "Park A", "status": "Open"}},
            ]
        }
        plugin.feature_client.get = AsyncMock(return_value=mock_response)

        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Parks",
                "type": "Feature Layer",
                "service_url": valid_url,
            },
        ):
            records = await plugin.query_data("abc123", {"where": "1=1"}, 100)

        plugin.feature_client.get.assert_called_once()
        assert len(records) == 1
        assert records[0]["name"] == "Park A"
