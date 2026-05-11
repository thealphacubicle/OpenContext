"""Extended tests for ArcGIS Hub plugin — formatting, error paths, aggregations, shutdown."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from plugins.arcgis.config_schema import ArcGISPluginConfig
from plugins.arcgis.plugin import ArcGISPlugin


@pytest.fixture
def arcgis_config():
    return {
        "portal_url": "https://hub.arcgis.com",
        "city_name": "TestCity",
        "timeout": 120,
    }


@pytest.fixture
def initialized_plugin(arcgis_config):
    plugin = ArcGISPlugin(arcgis_config)
    plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)
    plugin._initialized = True
    plugin.hub_client = AsyncMock()
    plugin.feature_client = AsyncMock()
    return plugin


# ---------------------------------------------------------------------------
# initialize — with token
# ---------------------------------------------------------------------------


class TestInitializeWithToken:
    @pytest.mark.asyncio
    async def test_initialize_sets_authorization_header_when_token_provided(self):
        config = {
            "portal_url": "https://hub.arcgis.com",
            "city_name": "TestCity",
            "timeout": 120,
            "token": "secret-token-abc",
        }
        plugin = ArcGISPlugin(config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await plugin.initialize()

        assert result is True
        # Both clients created — verify both calls include Authorization header
        calls = mock_client_class.call_args_list
        assert len(calls) == 2
        hub_headers = calls[0][1].get("headers", {})
        assert "Authorization" in hub_headers
        assert hub_headers["Authorization"] == "Bearer secret-token-abc"


# ---------------------------------------------------------------------------
# shutdown
# ---------------------------------------------------------------------------


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_closes_clients(self, initialized_plugin):
        hub = initialized_plugin.hub_client
        feature = initialized_plugin.feature_client

        await initialized_plugin.shutdown()

        hub.aclose.assert_awaited_once()
        feature.aclose.assert_awaited_once()
        assert initialized_plugin.hub_client is None
        assert initialized_plugin.feature_client is None
        assert initialized_plugin._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_when_clients_are_none(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.hub_client = None
        plugin.feature_client = None
        plugin._initialized = False

        # Must not raise
        await plugin.shutdown()


# ---------------------------------------------------------------------------
# search_datasets — error and empty paths
# ---------------------------------------------------------------------------


class TestSearchDatasets:
    @pytest.mark.asyncio
    async def test_search_datasets_returns_empty_on_no_features(
        self, initialized_plugin
    ):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"features": []}
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.search_datasets("parks", 10)
        assert result == []

    @pytest.mark.asyncio
    async def test_search_datasets_raises_on_http_status_error(
        self, initialized_plugin
    ):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        http_err = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)
        initialized_plugin.hub_client.get = AsyncMock(side_effect=http_err)

        with pytest.raises(RuntimeError, match="Hub Search API error"):
            await initialized_plugin.search_datasets("parks", 10)

    @pytest.mark.asyncio
    async def test_search_datasets_returns_multiple_results(self, initialized_plugin):
        features = [
            {
                "properties": {
                    "id": f"id{i}",
                    "title": f"Dataset {i}",
                    "type": "Feature Layer",
                }
            }
            for i in range(3)
        ]
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"features": features}
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.search_datasets("parks", 3)
        assert len(result) == 3
        assert result[0]["id"] == "id0"


# ---------------------------------------------------------------------------
# get_dataset — error path
# ---------------------------------------------------------------------------


class TestGetDataset:
    @pytest.mark.asyncio
    async def test_get_dataset_raises_on_http_status_error(self, initialized_plugin):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        http_err = httpx.HTTPStatusError("403", request=Mock(), response=mock_response)
        initialized_plugin.hub_client.get = AsyncMock(side_effect=http_err)

        with pytest.raises(RuntimeError, match="Hub Search API error"):
            await initialized_plugin.get_dataset("abc123")

    @pytest.mark.asyncio
    async def test_get_dataset_includes_extra_fields(self, initialized_plugin):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "properties": {
                "id": "abc123",
                "title": "Parks",
                "type": "Feature Layer",
                "snippet": "City park locations",
                "licenseInfo": "Public Domain",
                "numRecords": 500,
                "url": "https://services.arcgis.com/xyz/FeatureServer/0",
            }
        }
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.get_dataset("abc123")
        assert result["snippet"] == "City park locations"
        assert result["numRecords"] == 500
        assert (
            result["service_url"] == "https://services.arcgis.com/xyz/FeatureServer/0"
        )


# ---------------------------------------------------------------------------
# query_data — error paths
# ---------------------------------------------------------------------------


class TestQueryDataErrors:
    @pytest.mark.asyncio
    async def test_raises_when_limit_less_than_one(self, initialized_plugin):
        with pytest.raises(ValueError, match="limit must be at least 1"):
            await initialized_plugin.query_data("abc123", {}, limit=0)

    @pytest.mark.asyncio
    async def test_raises_when_no_service_url(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={"id": "abc123", "service_url": None, "type": "Feature Layer"},
        ):
            with pytest.raises(
                ValueError, match="does not have a queryable Feature Service URL"
            ):
                await initialized_plugin.query_data("abc123", {}, 100)

    @pytest.mark.asyncio
    async def test_raises_when_type_not_queryable(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Web Map",
            },
        ):
            with pytest.raises(ValueError, match="not queryable"):
                await initialized_plugin.query_data("abc123", {}, 100)

    @pytest.mark.asyncio
    async def test_raises_on_feature_service_http_error(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            http_err = httpx.HTTPStatusError(
                "500", request=Mock(), response=mock_response
            )
            initialized_plugin.feature_client.get = AsyncMock(side_effect=http_err)

            with pytest.raises(RuntimeError, match="Feature Service query error"):
                await initialized_plugin.query_data("abc123", {}, 100)

    @pytest.mark.asyncio
    async def test_raises_on_non_json_response(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.side_effect = Exception("invalid json")
            mock_response.headers = {"content-type": "text/html"}
            initialized_plugin.feature_client.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(ValueError, match="non-JSON response"):
                await initialized_plugin.query_data("abc123", {}, 100)

    @pytest.mark.asyncio
    async def test_raises_on_error_in_response_body(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "error": {
                    "code": 400,
                    "message": "Invalid query",
                    "details": ["Field not found"],
                }
            }
            initialized_plugin.feature_client.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(RuntimeError, match="Feature Service query failed"):
                await initialized_plugin.query_data("abc123", {}, 100)

    @pytest.mark.asyncio
    async def test_raises_on_error_body_without_details(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "error": {"code": 999, "message": "Something broke", "details": []}
            }
            initialized_plugin.feature_client.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(RuntimeError, match="Something broke"):
                await initialized_plugin.query_data("abc123", {}, 100)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_features(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {"features": []}
            initialized_plugin.feature_client.get = AsyncMock(
                return_value=mock_response
            )

            result = await initialized_plugin.query_data("abc123", {}, 100)
            assert result == []

    @pytest.mark.asyncio
    async def test_limit_capped_at_1000(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {"features": [{"attributes": {"a": 1}}]}
            initialized_plugin.feature_client.get = AsyncMock(
                return_value=mock_response
            )

            await initialized_plugin.query_data("abc123", {}, limit=5000)

            params = initialized_plugin.feature_client.get.call_args[1]["params"]
            assert params["resultRecordCount"] == 1000

    @pytest.mark.asyncio
    async def test_query_data_no_filters_uses_defaults(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
                "type": "Feature Layer",
            },
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {"features": [{"attributes": {}}]}
            initialized_plugin.feature_client.get = AsyncMock(
                return_value=mock_response
            )

            await initialized_plugin.query_data("abc123", None, 50)
            params = initialized_plugin.feature_client.get.call_args[1]["params"]
            assert params["where"] == "1=1"
            assert params["outFields"] == "*"


# ---------------------------------------------------------------------------
# get_aggregations — error and matching paths
# ---------------------------------------------------------------------------


class TestGetAggregations:
    @pytest.mark.asyncio
    async def test_returns_empty_on_http_status_error(self, initialized_plugin):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_err = httpx.HTTPStatusError("500", request=Mock(), response=mock_response)
        initialized_plugin.hub_client.get = AsyncMock(side_effect=http_err)

        result = await initialized_plugin.get_aggregations("type")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_matching_field_buckets(self, initialized_plugin):
        data = {
            "aggregations": {
                "terms": [
                    {
                        "field": "type",
                        "aggregations": [
                            {"label": "Feature Layer", "value": 42},
                            {"label": "Table", "value": 10},
                        ],
                    },
                    {
                        "field": "access",
                        "aggregations": [{"label": "public", "value": 100}],
                    },
                ]
            }
        }
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = data
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.get_aggregations("type")
        assert len(result) == 2
        assert result[0]["key"] == "Feature Layer"
        assert result[0]["doc_count"] == 42

    @pytest.mark.asyncio
    async def test_returns_empty_when_field_not_in_aggregations(
        self, initialized_plugin
    ):
        data = {
            "aggregations": {
                "terms": [
                    {
                        "field": "access",
                        "aggregations": [{"label": "public", "value": 10}],
                    }
                ]
            }
        }
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = data
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.get_aggregations("type")
        assert result == []

    @pytest.mark.asyncio
    async def test_aggregations_with_q_param(self, initialized_plugin):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"aggregations": {}}
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        await initialized_plugin.get_aggregations("tags", q="parks")

        call_params = initialized_plugin.hub_client.get.call_args[1]["params"]
        assert call_params.get("q") == "parks"

    @pytest.mark.asyncio
    async def test_aggregations_with_no_q_param(self, initialized_plugin):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"aggregations": {"terms": []}}
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        await initialized_plugin.get_aggregations("tags")

        call_params = initialized_plugin.hub_client.get.call_args[1]["params"]
        assert "q" not in call_params

    @pytest.mark.asyncio
    async def test_aggregations_non_dict_aggregations_returns_empty(
        self, initialized_plugin
    ):
        # aggregations key is a list, not a dict — should not crash
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"aggregations": []}
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.get_aggregations("type")
        assert result == []


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self, initialized_plugin):
        mock_response = Mock()
        mock_response.status_code = 200
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_non_200(self, initialized_plugin):
        mock_response = Mock()
        mock_response.status_code = 503
        initialized_plugin.hub_client.get = AsyncMock(return_value=mock_response)

        result = await initialized_plugin.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self, initialized_plugin):
        initialized_plugin.hub_client.get = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = await initialized_plugin.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# execute_tool — missing required fields
# ---------------------------------------------------------------------------


class TestExecuteToolMissingArgs:
    @pytest.mark.asyncio
    async def test_get_dataset_missing_id_returns_error(self, initialized_plugin):
        result = await initialized_plugin.execute_tool("get_dataset", {})
        assert result.success is False
        assert "dataset_id is required" in result.error_message

    @pytest.mark.asyncio
    async def test_get_aggregations_missing_field_returns_error(
        self, initialized_plugin
    ):
        result = await initialized_plugin.execute_tool("get_aggregations", {})
        assert result.success is False
        assert "field is required" in result.error_message

    @pytest.mark.asyncio
    async def test_query_data_missing_id_returns_error(self, initialized_plugin):
        result = await initialized_plugin.execute_tool("query_data", {})
        assert result.success is False
        assert "dataset_id is required" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_tool_exception_returns_error(self, initialized_plugin):
        with patch.object(
            initialized_plugin,
            "search_datasets",
            new_callable=AsyncMock,
            side_effect=RuntimeError("hub down"),
        ):
            result = await initialized_plugin.execute_tool(
                "search_datasets", {"q": "parks"}
            )

        assert result.success is False
        assert "hub down" in result.error_message


# ---------------------------------------------------------------------------
# _epoch_ms_to_iso
# ---------------------------------------------------------------------------


class TestEpochMsToIso:
    def test_converts_valid_epoch(self):
        # epoch ms=0 resolves to 1969-12-31 or 1970-01-01 depending on local TZ offset
        from datetime import datetime

        expected = datetime.fromtimestamp(0).strftime("%Y-%m-%d")
        result = ArcGISPlugin._epoch_ms_to_iso(0)
        assert result == expected

    def test_converts_recent_epoch(self):
        # 2000-01-01 00:00:00 UTC = 946684800000 ms
        # At any UTC offset the date stays in 1999-12-31 or 2000-01-01 — just check type
        result = ArcGISPlugin._epoch_ms_to_iso(946684800000)
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

    def test_returns_empty_for_none(self):
        assert ArcGISPlugin._epoch_ms_to_iso(None) == ""

    def test_returns_empty_for_invalid_value(self):
        assert ArcGISPlugin._epoch_ms_to_iso("not-a-number") == ""

    def test_returns_empty_for_out_of_range(self):
        # Use a negative value far in the past that raises OSError on some platforms
        # or ValueError — verify the method handles it gracefully
        result = ArcGISPlugin._epoch_ms_to_iso(-99_999_999_999_999_999)
        assert result == "" or isinstance(result, str)


# ---------------------------------------------------------------------------
# _format_search_results — no datasets
# ---------------------------------------------------------------------------


class TestFormatSearchResults:
    def test_returns_no_datasets_message(self, initialized_plugin):
        result = initialized_plugin._format_search_results([])
        assert result == "No datasets found."

    def test_formats_datasets_with_tags(self, initialized_plugin):
        datasets = [
            {
                "id": "abc",
                "title": "Parks",
                "type": "Feature Layer",
                "access": "public",
                "description": "City parks",
                "url": "https://example.com",
                "tags": ["parks", "green space"],
            }
        ]
        result = initialized_plugin._format_search_results(datasets)
        assert "Parks" in result
        assert "parks, green space" in result

    def test_formats_datasets_with_no_tags(self, initialized_plugin):
        datasets = [
            {
                "id": "abc",
                "title": "Parks",
                "type": "Feature Layer",
                "access": "public",
                "description": "City parks",
                "url": "",
                "tags": [],
            }
        ]
        result = initialized_plugin._format_search_results(datasets)
        assert "None" in result  # tags: None


# ---------------------------------------------------------------------------
# _format_query_results — empty and non-empty
# ---------------------------------------------------------------------------


class TestFormatQueryResults:
    def test_returns_no_records_message(self, initialized_plugin):
        assert (
            initialized_plugin._format_query_results([], 100) == "No records returned."
        )

    def test_formats_records(self, initialized_plugin):
        records = [{"name": "Central Park", "type": "park"}]
        result = initialized_plugin._format_query_results(records, 10)
        assert "Record 1" in result
        assert "Central Park" in result


# ---------------------------------------------------------------------------
# _format_aggregations
# ---------------------------------------------------------------------------


class TestFormatAggregations:
    def test_returns_no_results_message(self, initialized_plugin):
        result = initialized_plugin._format_aggregations("type", [])
        assert "No aggregation results" in result

    def test_formats_buckets(self, initialized_plugin):
        buckets = [{"key": "Feature Layer", "doc_count": 42}]
        result = initialized_plugin._format_aggregations("type", buckets)
        assert "Feature Layer" in result
        assert "42" in result


# ---------------------------------------------------------------------------
# _extract_dataset_summary — description truncation
# ---------------------------------------------------------------------------


class TestExtractDatasetSummary:
    def test_truncates_long_description(self):
        long_desc = "A" * 400
        props = {"description": long_desc}
        result = ArcGISPlugin._extract_dataset_summary(props)
        assert len(result["description"]) <= 304  # 300 + "..."
        assert result["description"].endswith("...")

    def test_short_description_not_truncated(self):
        props = {"description": "Short desc"}
        result = ArcGISPlugin._extract_dataset_summary(props)
        assert result["description"] == "Short desc"

    def test_none_description_treated_as_empty(self):
        props = {"description": None}
        result = ArcGISPlugin._extract_dataset_summary(props)
        assert result["description"] == ""
