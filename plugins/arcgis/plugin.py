"""ArcGIS Hub plugin implementation for OpenContext.

This plugin provides access to ArcGIS Hub open data catalogs
via the OGC API - Records (Hub Search API) and ArcGIS Feature Services.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from core.interfaces import DataPlugin, PluginType, ToolDefinition, ToolResult
from plugins.arcgis.config_schema import ArcGISPluginConfig
from plugins.arcgis.where_validator import WhereValidator

logger = logging.getLogger(__name__)


class ArcGISPlugin(DataPlugin):
    """Plugin for accessing ArcGIS Hub open data catalogs.

    This plugin implements the DataPlugin interface and provides tools for
    searching datasets, retrieving dataset metadata, querying Feature Services,
    and exploring catalog aggregations.
    """

    plugin_name = "arcgis"
    plugin_type = PluginType.OPEN_DATA
    plugin_version = "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.plugin_config: Optional[ArcGISPluginConfig] = None
        self.hub_client: Optional[httpx.AsyncClient] = None
        self.feature_client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> bool:
        try:
            self.plugin_config = ArcGISPluginConfig(**self.config)

            headers = {"Accept": "application/json"}
            feature_headers = {}
            if self.plugin_config.token:
                headers["Authorization"] = f"Bearer {self.plugin_config.token}"
                feature_headers["Authorization"] = f"Bearer {self.plugin_config.token}"

            self.hub_client = httpx.AsyncClient(
                base_url=self.plugin_config.portal_url,
                headers=headers,
                timeout=self.plugin_config.timeout,
            )

            self.feature_client = httpx.AsyncClient(
                headers=feature_headers,
                timeout=self.plugin_config.timeout,
            )

            response = await self.hub_client.get("/api/search/v1/collections")
            response.raise_for_status()

            self._initialized = True
            logger.info(
                f"ArcGIS Hub plugin initialized successfully for "
                f"{self.plugin_config.city_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize ArcGIS Hub plugin: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        if self.hub_client:
            await self.hub_client.aclose()
            self.hub_client = None
        if self.feature_client:
            await self.feature_client.aclose()
            self.feature_client = None
        self._initialized = False
        logger.info("ArcGIS Hub plugin shut down")

    def get_tools(self) -> List[ToolDefinition]:
        city = self.plugin_config.city_name if self.plugin_config else "Unknown"
        return [
            ToolDefinition(
                name="search_datasets",
                description=f"Search for datasets in {city}'s ArcGIS Hub catalog",
                input_schema={
                    "type": "object",
                    "properties": {
                        "q": {
                            "type": "string",
                            "description": "Full-text search query",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                    },
                    "required": ["q"],
                },
            ),
            ToolDefinition(
                name="get_dataset",
                description="Get metadata for a specific ArcGIS Hub dataset by ID",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "32-char hex Hub item ID",
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
            ToolDefinition(
                name="get_aggregations",
                description=(
                    "Get facet counts for a field across the ArcGIS Hub catalog. "
                    "Useful for exploring available categories, types, or tags."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "description": (
                                'Field to aggregate (e.g. "type", "tags", '
                                '"categories", "owner", "access")'
                            ),
                        },
                        "q": {
                            "type": "string",
                            "description": "Optional search query to scope the aggregation",
                        },
                    },
                    "required": ["field"],
                },
            ),
            ToolDefinition(
                name="query_data",
                description=(
                    "Query records from an ArcGIS Feature Service. Provide the Hub "
                    "dataset ID — the plugin resolves the Feature Service URL "
                    "automatically (two-hop). Use get_dataset first to confirm the "
                    "dataset has a queryable service URL."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Hub item ID (same as get_dataset)",
                        },
                        "where": {
                            "type": "string",
                            "description": "SQL WHERE clause for filtering",
                            "default": "1=1",
                        },
                        "out_fields": {
                            "type": "string",
                            "description": "Comma-separated field names to return",
                            "default": "*",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of records (default: 100)",
                            "default": 100,
                            "maximum": 1000,
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
        ]

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolResult:
        try:
            if tool_name == "search_datasets":
                q = arguments.get("q", "")
                limit = arguments.get("limit", 10)
                datasets = await self.search_datasets(q, limit)
                return ToolResult(
                    content=[
                        {"type": "text", "text": self._format_search_results(datasets)}
                    ],
                    success=True,
                )

            elif tool_name == "get_dataset":
                dataset_id = arguments.get("dataset_id")
                if not dataset_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="dataset_id is required",
                    )
                dataset = await self.get_dataset(dataset_id)
                return ToolResult(
                    content=[{"type": "text", "text": self._format_dataset(dataset)}],
                    success=True,
                )

            elif tool_name == "get_aggregations":
                field = arguments.get("field")
                if not field:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="field is required",
                    )
                q = arguments.get("q")
                buckets = await self.get_aggregations(field, q)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_aggregations(field, buckets),
                        }
                    ],
                    success=True,
                )

            elif tool_name == "query_data":
                dataset_id = arguments.get("dataset_id")
                if not dataset_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="dataset_id is required",
                    )
                where = arguments.get("where", "1=1")
                out_fields = arguments.get("out_fields", "*")
                limit = arguments.get("limit", 100)
                filters = {"where": where, "out_fields": out_fields}
                records = await self.query_data(dataset_id, filters, limit)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_query_results(records, limit),
                        }
                    ],
                    success=True,
                )

            else:
                return ToolResult(
                    content=[],
                    success=False,
                    error_message=f"Unknown tool: {tool_name}",
                )

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return ToolResult(
                content=[],
                success=False,
                error_message=str(e) if str(e) else "Tool execution failed",
            )

    # ── DataPlugin abstract method implementations ──────────────────────

    async def search_datasets(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        try:
            response = await self.hub_client.get(
                "/api/search/v1/collections/all/items",
                params={"q": query, "limit": limit},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Hub Search API error (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            ) from e

        data = response.json()
        features = data.get("features", [])
        if not features:
            return []

        results = []
        for feature in features:
            props = feature.get("properties", {})
            results.append(self._extract_dataset_summary(props))
        return results

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        try:
            response = await self.hub_client.get(
                f"/api/search/v1/collections/all/items/{dataset_id}",
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Hub Search API error (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            ) from e

        feature = response.json()
        props = feature.get("properties", {})

        result = self._extract_dataset_summary(props)
        result.update(
            {
                "snippet": props.get("snippet", ""),
                "licenseInfo": props.get("licenseInfo", ""),
                "spatialReference": props.get("spatialReference", ""),
                "geometryType": props.get("geometryType", ""),
                "additionalResources": props.get("additionalResources", []),
                "numRecords": props.get("numRecords", None),
                "service_url": props.get("url", ""),
            }
        )
        return result

    async def query_data(
        self,
        resource_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        dataset = await self.get_dataset(resource_id)
        service_url = dataset.get("service_url")
        if not service_url:
            raise ValueError(
                f"Dataset {resource_id} does not have a queryable Feature Service URL"
            )

        where_clause = filters.get("where", "1=1") if filters else "1=1"
        where_clause = WhereValidator.validate(where_clause)
        out_fields = filters.get("out_fields", "*") if filters else "*"

        service_url = self._ensure_layer_url(service_url)
        query_url = f"{service_url}/query"
        params = {
            "where": where_clause,
            "outFields": out_fields,
            "resultRecordCount": min(limit, 1000),
            "f": "json",
            "returnGeometry": "false",
        }

        try:
            response = await self.feature_client.get(query_url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Feature Service query error (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            ) from e

        data = response.json()
        features = data.get("features", [])
        if not features:
            return []

        return [f.get("attributes", {}) for f in features]

    # ── Aggregations (standalone helper, not a DataPlugin method) ───────

    async def get_aggregations(
        self, field: str, q: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"fields": field}
        if q:
            params["q"] = q

        try:
            response = await self.hub_client.get(
                "/api/search/v1/collections/all/aggregations", params=params
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Hub Aggregations API error (HTTP {e.response.status_code}): "
                f"{e.response.text}"
            )
            return []

        data = response.json()
        buckets = data.get("aggregations", {}).get(field, {}).get("buckets", [])
        return buckets

    # ── Health check ────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            response = await self.hub_client.get("/api/search/v1/collections")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    # ── Private helpers ─────────────────────────────────────────────────

    @staticmethod
    def _ensure_layer_url(service_url: str) -> str:
        """Append /0 if the URL points at a FeatureServer or MapServer root
        without a layer index (e.g. .../FeatureServer -> .../FeatureServer/0).
        """
        stripped = service_url.rstrip("/")
        if re.search(r"/(FeatureServer|MapServer)$", stripped, re.IGNORECASE):
            return f"{stripped}/0"
        return stripped

    @staticmethod
    def _epoch_ms_to_iso(epoch_ms: Any) -> str:
        if epoch_ms is None:
            return ""
        try:
            return datetime.fromtimestamp(int(epoch_ms) / 1000).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            return ""

    @staticmethod
    def _extract_dataset_summary(props: Dict[str, Any]) -> Dict[str, Any]:
        description = props.get("description", "") or ""
        if len(description) > 300:
            description = description[:300] + "..."

        return {
            "id": props.get("id", ""),
            "title": props.get("title", ""),
            "description": description,
            "type": props.get("type", ""),
            "url": props.get("url", ""),
            "access": props.get("access", ""),
            "owner": props.get("owner", ""),
            "created": ArcGISPlugin._epoch_ms_to_iso(props.get("created")),
            "modified": ArcGISPlugin._epoch_ms_to_iso(props.get("modified")),
            "tags": props.get("tags", []),
            "extent": props.get("extent", []),
        }

    def _format_search_results(self, datasets: List[Dict[str, Any]]) -> str:
        if not datasets:
            return "No datasets found."

        lines = [f"Found {len(datasets)} dataset(s):\n"]

        for i, ds in enumerate(datasets, 1):
            tags = ", ".join(ds.get("tags", [])) if ds.get("tags") else "None"
            lines.append(f"{i}. {ds.get('title', 'Untitled')}")
            lines.append(f"   ID: {ds.get('id', 'unknown')}")
            lines.append(f"   Type: {ds.get('type', 'unknown')}")
            lines.append(f"   Access: {ds.get('access', 'unknown')}")
            lines.append(f"   Description: {ds.get('description', 'No description')}")
            lines.append(f"   URL: {ds.get('url', '')}")
            lines.append(f"   Tags: {tags}")
            lines.append("")

        return "\n".join(lines)

    def _format_dataset(self, dataset: Dict[str, Any]) -> str:
        tags = ", ".join(dataset.get("tags", [])) if dataset.get("tags") else "None"
        lines = [
            f"Dataset: {dataset.get('title', 'Untitled')}",
            f"ID: {dataset.get('id', 'unknown')}",
            f"Type: {dataset.get('type', 'unknown')}",
            f"Access: {dataset.get('access', 'unknown')}",
            f"Owner: {dataset.get('owner', 'unknown')}",
            f"Created: {dataset.get('created', '')}",
            f"Modified: {dataset.get('modified', '')}",
            f"Description: {dataset.get('description', 'No description')}",
            f"Snippet: {dataset.get('snippet', '')}",
            f"License: {dataset.get('licenseInfo', '')}",
            f"Spatial Reference: {dataset.get('spatialReference', '')}",
            f"Geometry Type: {dataset.get('geometryType', '')}",
            f"Number of Records: {dataset.get('numRecords', 'N/A')}",
            f"Tags: {tags}",
            f"Extent: {dataset.get('extent', [])}",
            f"Additional Resources: {dataset.get('additionalResources', [])}",
            f"URL: {dataset.get('url', '')}",
            f"Service URL (use for query_data): {dataset.get('service_url', '')}",
        ]
        return "\n".join(lines)

    def _format_query_results(self, records: List[Dict[str, Any]], limit: int) -> str:
        if not records:
            return "No records returned."

        lines = [f"Returned {len(records)} record(s) (limit: {limit}):\n"]

        for i, record in enumerate(records, 1):
            lines.append(f"Record {i}:")
            for key, value in record.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        return "\n".join(lines)

    def _format_aggregations(self, field: str, buckets: List[Dict[str, Any]]) -> str:
        if not buckets:
            return f"No aggregation results for '{field}'."

        lines = [f"Aggregations for '{field}':\n"]
        for bucket in buckets:
            lines.append(
                f"  {bucket.get('key', 'unknown')}: "
                f"{bucket.get('doc_count', 0)} dataset(s)"
            )

        return "\n".join(lines)
