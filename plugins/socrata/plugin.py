"""Socrata plugin implementation for OpenContext.

This plugin provides access to Socrata-based open data portals (e.g., Chicago,
NYC, Seattle) using the Discovery API for catalog search and SODA3 for data access.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.interfaces import DataPlugin, PluginType, ToolDefinition, ToolResult
from plugins.socrata.config_schema import SocrataPluginConfig
from plugins.socrata.soql_validator import SoQLValidator

logger = logging.getLogger(__name__)

DISCOVERY_API_BASE = "https://api.us.socrata.com"


class SocrataPlugin(DataPlugin):
    """Plugin for accessing Socrata-based open data portals.

    Uses two HTTP clients: Discovery API (catalog search) and SODA3 (data access).
    """

    plugin_name = "socrata"
    plugin_type = PluginType.OPEN_DATA
    plugin_version = "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Socrata plugin with configuration.

        Args:
            config: Plugin configuration dictionary
        """
        super().__init__(config)
        self.plugin_config = SocrataPluginConfig(**config)
        self.discovery_client: Optional[httpx.AsyncClient] = None
        self.soda_client: Optional[httpx.AsyncClient] = None

    def _get_domain(self) -> str:
        """Extract hostname from base_url for Discovery API domains parameter."""
        parsed = urlparse(self.plugin_config.base_url)
        return parsed.netloc or parsed.path or ""

    async def initialize(self) -> bool:
        """Initialize Socrata plugin and test connection.

        Returns:
            True if initialization succeeded
        """
        try:
            if (
                not self.plugin_config.app_token
                or not self.plugin_config.app_token.strip()
            ):
                logger.error("Socrata app token is required")
                return False

            headers = {"X-App-Token": self.plugin_config.app_token}

            self.discovery_client = httpx.AsyncClient(
                base_url=DISCOVERY_API_BASE,
                headers=headers,
                timeout=self.plugin_config.timeout,
            )

            self.soda_client = httpx.AsyncClient(
                base_url=self.plugin_config.portal_url,
                headers=headers,
                timeout=self.plugin_config.timeout,
            )

            # Test connectivity via health check
            if await self.health_check():
                self._initialized = True
                logger.info(
                    f"Socrata plugin initialized successfully for {self.plugin_config.city_name}"
                )
                return True
            else:
                logger.error("Socrata API connection test failed")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize Socrata plugin: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown plugin and close HTTP clients."""
        if self.discovery_client:
            await self.discovery_client.aclose()
            self.discovery_client = None
        if self.soda_client:
            await self.soda_client.aclose()
            self.soda_client = None
        self._initialized = False
        logger.info("Socrata plugin shut down")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_not_exception_type((RuntimeError, httpx.HTTPStatusError)),
    )
    async def _call_discovery_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call Socrata Discovery API.

        Args:
            params: Query parameters (domains is always included)

        Returns:
            Discovery API response

        Raises:
            RuntimeError: On HTTP errors
        """
        if not self.discovery_client:
            raise RuntimeError("Plugin not initialized")

        domain = self._get_domain()
        params = {**params, "domains": domain}

        try:
            response = await self.discovery_client.get("/api/catalog/v1", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                body = e.response.json()
                msg = body.get("message", str(body))
                raise RuntimeError(
                    f"Discovery API error on {self.plugin_config.city_name} OpenData portal: {msg} (HTTP {status_code})"
                ) from e
            except (ValueError, TypeError):
                pass
            raise RuntimeError(
                f"Discovery API error on {self.plugin_config.city_name} OpenData portal (HTTP {status_code})"
            ) from e

        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_not_exception_type((RuntimeError, httpx.HTTPStatusError)),
    )
    async def _call_soda_api(
        self, method: str, path: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Call SODA3 API on portal domain.

        Args:
            method: HTTP method (GET or POST)
            path: API path (e.g., /api/views/{id}.json)
            **kwargs: Additional request arguments

        Returns:
            JSON response

        Raises:
            RuntimeError: On HTTP errors
        """
        if not self.soda_client:
            raise RuntimeError("Plugin not initialized")

        portal = f"{self.plugin_config.city_name} OpenData portal"

        try:
            if method.upper() == "GET":
                response = await self.soda_client.get(path, **kwargs)
            else:
                response = await self.soda_client.post(path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                body = e.response.json()
                msg = body.get("message", str(body))
                raise RuntimeError(
                    f"Error on {portal}: {msg} (HTTP {status_code})"
                ) from e
            except (ValueError, TypeError):
                pass
            raise RuntimeError(f"Error on {portal} (HTTP {status_code})") from e

        return response.json()

    def get_tools(self) -> List[ToolDefinition]:
        """Get list of tools provided by Socrata plugin.

        Returns:
            List of tool definitions
        """
        return [
            ToolDefinition(
                name="search_datasets",
                description=(
                    f"Search for datasets in {self.plugin_config.city_name}'s open data portal. "
                    f"Returns dataset IDs needed for get_dataset, get_schema, and query_dataset. "
                    f"Limit is optional (default: 10)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional, default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="get_dataset",
                description=(
                    f"Get metadata for a specific dataset from {self.plugin_config.city_name}'s open data portal "
                    f"(name, description, row count, etc.). Returns metadata only—no column info. "
                    f"For column names and types, use get_schema instead."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset 4x4 ID (e.g., wc4w-4jew)",
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
            ToolDefinition(
                name="get_schema",
                description=(
                    f"Get column schema for a dataset in {self.plugin_config.city_name}'s open data portal. "
                    f"Returns column field names (not display names), data types, and descriptions—all directly usable in SoQL. "
                    f"Call before query_dataset to construct valid SoQL. "
                    f"Note: schemas may include computed region columns (:@computed_region_...) at the end; these are noisy and generally not useful for queries."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset 4x4 ID",
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
            ToolDefinition(
                name="query_dataset",
                description=(
                    f"Query data from a dataset in {self.plugin_config.city_name}'s open data portal using SoQL. "
                    f"Use get_schema first to get column names. "
                    f"SoQL gotchas: GROUP BY is required whenever using COUNT() or any aggregation; "
                    f"LIMIT caps returned rows (can affect aggregation results); "
                    f"boolean fields use = true / = false, not = 'Y' or = 1; "
                    f"for conditional counts use SUM(CASE WHEN col = true THEN 1 ELSE 0 END)."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset 4x4 ID",
                        },
                        "soql_query": {
                            "type": "string",
                            "description": (
                                "SoQL query. Examples: "
                                "Simple filter: SELECT * WHERE year > 2020 LIMIT 50; "
                                "Aggregation (GROUP BY required): SELECT category, COUNT(*) GROUP BY category; "
                                "Multi-column: SELECT region, SUM(amount) GROUP BY region; "
                                "Conditional aggregation: SELECT type, SUM(CASE WHEN arrest = true THEN 1 ELSE 0 END) GROUP BY type"
                            ),
                        },
                    },
                    "required": ["dataset_id", "soql_query"],
                },
            ),
            ToolDefinition(
                name="list_categories",
                description=(
                    f"Typical workflow: list_categories → search_datasets → get_dataset → get_schema → query_dataset. "
                    f"List all dataset categories on {self.plugin_config.city_name}'s open data portal. "
                    f"Categories include dataset counts per category. Use results to inform which search terms to pass to search_datasets."
                ),
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="execute_sql",
                description="""Execute raw SoQL query (advanced). Similar to CKAN execute_sql.
Use for complex SoQL queries. Security: Only SELECT allowed.
Use get_schema first for column names.""",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset 4x4 ID",
                        },
                        "soql": {
                            "type": "string",
                            "description": "SoQL SELECT statement",
                        },
                    },
                    "required": ["dataset_id", "soql"],
                },
            ),
        ]

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            ToolResult with content and success flag
        """
        try:
            if tool_name == "search_datasets":
                query = arguments.get("query", "")
                limit = arguments.get("limit", 10)
                datasets = await self.search_datasets(query, limit)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_search_results(datasets),
                        }
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
                    content=[
                        {
                            "type": "text",
                            "text": self._format_dataset(dataset),
                        }
                    ],
                    success=True,
                )

            elif tool_name == "get_schema":
                dataset_id = arguments.get("dataset_id")
                if not dataset_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="dataset_id is required",
                    )
                schema = await self.get_schema(dataset_id)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_schema(schema),
                        }
                    ],
                    success=True,
                )

            elif tool_name == "query_dataset":
                dataset_id = arguments.get("dataset_id")
                soql_query = arguments.get("soql_query")
                if not dataset_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="dataset_id is required",
                    )
                if not soql_query:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="soql_query is required",
                    )
                data = await self._query_dataset(dataset_id, soql_query)
                display_limit = self._parse_soql_limit(soql_query, default=100)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_query_results(
                                data, limit=display_limit
                            ),
                        }
                    ],
                    success=True,
                )

            elif tool_name == "list_categories":
                categories = await self._list_categories()
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_categories(categories),
                        }
                    ],
                    success=True,
                )

            elif tool_name == "execute_sql":
                dataset_id = arguments.get("dataset_id")
                soql = arguments.get("soql")
                if not dataset_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="dataset_id is required",
                    )
                if not soql:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="soql is required",
                    )
                result = await self.execute_sql(dataset_id, soql)
                if result.get("error"):
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message=result.get("message", "SoQL execution failed"),
                    )
                records = result.get("records", [])
                fields = result.get("fields", [])
                formatted_text = self._format_sql_results(records, fields)
                return ToolResult(
                    content=[{"type": "text", "text": formatted_text}],
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

    async def search_datasets(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for datasets matching a query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of dataset metadata dictionaries
        """
        response = await self._call_discovery_api({"q": query, "limit": limit})
        return response.get("results", [])

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Get detailed metadata for a specific dataset.

        Args:
            dataset_id: Dataset 4x4 ID

        Returns:
            Dataset metadata dictionary
        """
        return await self._call_soda_api("GET", f"/api/views/{dataset_id}.json")

    async def get_schema(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Get column schema for a dataset.

        Args:
            dataset_id: Dataset 4x4 ID

        Returns:
            List of column definitions
        """
        metadata = await self._call_soda_api("GET", f"/api/views/{dataset_id}.json")
        return metadata.get("columns", [])

    def _parse_soql_limit(
        self, soql_query: str, default: int = 100, max_val: Optional[int] = None
    ) -> int:
        """Parse LIMIT value from SoQL query."""
        if "LIMIT" not in soql_query.upper():
            return default
        parts = soql_query.upper().split("LIMIT")
        if len(parts) < 2:
            return default
        try:
            val = int(parts[-1].strip().split()[0])
            if max_val is not None:
                val = min(val, max_val)
            return max(1, val)
        except (ValueError, IndexError):
            return default

    async def _query_dataset(
        self, dataset_id: str, soql_query: str
    ) -> List[Dict[str, Any]]:
        """Query data using SoQL.

        Args:
            dataset_id: Dataset 4x4 ID
            soql_query: SoQL query string

        Returns:
            List of row objects
        """
        page_size = self._parse_soql_limit(soql_query, default=100, max_val=50000)

        body = {
            "query": soql_query,
            "page": {"pageNumber": 1, "pageSize": page_size},
        }
        result = await self._call_soda_api(
            "POST",
            f"/api/v3/views/{dataset_id}/query.json",
            json=body,
        )
        if isinstance(result, list):
            return result
        rows = result.get("rows", result.get("results", []))
        return rows if isinstance(rows, list) else []

    async def execute_sql(self, dataset_id: str, soql: str) -> Dict[str, Any]:
        """Execute raw SoQL query with security validation.

        Args:
            dataset_id: Dataset 4x4 ID
            soql: SoQL SELECT statement

        Returns:
            Dictionary with success flag, records, fields, or error message
        """
        is_valid, error = SoQLValidator.validate_query(soql)
        if not is_valid:
            return {"error": True, "message": error}

        logger.info("Executing SoQL", extra={"soql": soql[:500]})

        try:
            records = await self._query_dataset(dataset_id, soql)
            fields: List[Dict[str, Any]] = []
            if records:
                for key in records[0].keys():
                    if key != "_id":
                        fields.append({"id": key})

            return {
                "success": True,
                "records": records,
                "fields": fields,
            }
        except Exception as e:
            logger.error(f"SoQL execution failed: {e}", exc_info=True)
            return {"error": True, "message": str(e)}

    async def _list_categories(self) -> List[Dict[str, Any]]:
        """List categories with dataset counts.

        The Socrata Discovery API's facets parameter does not return facets for
        many portals (e.g., Chicago). Fall back to deriving categories from
        domain_category in each result's classification.
        """
        response = await self._call_discovery_api({"facets": "categories"})
        facets = response.get("facets", {})
        categories = facets.get("categories", [])
        if isinstance(categories, list) and categories:
            return categories
        if isinstance(categories, dict) and categories:
            return list(categories.items())

        # Fallback: derive from domain_category in search results
        # (facets are often empty for domain-scoped catalog requests)
        category_counts: Dict[str, int] = {}
        offset = 0
        limit = 500
        while True:
            page = await self._call_discovery_api({"limit": limit, "offset": offset})
            results = page.get("results", [])
            if not results:
                break
            for item in results:
                classification = item.get("classification", {})
                domain_cat = classification.get("domain_category")
                if domain_cat and isinstance(domain_cat, str):
                    category_counts[domain_cat] = category_counts.get(domain_cat, 0) + 1
            if len(results) < limit:
                break
            offset += limit

        return [
            {"name": name, "count": count}
            for name, count in sorted(category_counts.items())
        ]

    async def query_data(
        self,
        resource_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query data from a dataset (DataPlugin contract).

        Args:
            resource_id: Dataset 4x4 ID
            filters: Optional filters (field: value pairs) compiled to SoQL WHERE
            limit: Maximum number of records

        Returns:
            List of data records
        """
        where_parts = []
        if filters:
            for field, value in filters.items():
                if isinstance(value, str):
                    escaped = value.replace("'", "''")
                    where_parts.append(f"{field} = '{escaped}'")
                elif value is None:
                    where_parts.append(f"{field} IS NULL")
                else:
                    where_parts.append(f"{field} = {value}")
        where_clause = " AND ".join(where_parts)
        soql = f"SELECT * LIMIT {limit}"
        if where_clause:
            soql = f"SELECT * WHERE {where_clause} LIMIT {limit}"
        return await self._query_dataset(resource_id, soql)

    async def health_check(self) -> bool:
        """Check if Socrata API is accessible.

        Returns:
            True if healthy
        """
        try:
            await self._call_discovery_api({"limit": 1})
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def _format_search_results(self, datasets: List[Dict[str, Any]]) -> str:
        """Format search results for user display."""
        if not datasets:
            return f"No datasets found in {self.plugin_config.city_name}'s open data portal."

        lines = [
            f"Found {len(datasets)} dataset(s) in {self.plugin_config.city_name}'s open data portal:\n"
        ]

        for i, item in enumerate(datasets, 1):
            resource = item.get("resource", item)
            name = resource.get("name", "Untitled")
            dataset_id = resource.get("id", "unknown")
            description = (
                (resource.get("description") or "")[:100] + "..."
                if resource.get("description")
                else "No description"
            )
            category = resource.get("category", "")
            permalink = resource.get("permalink", "")
            if not permalink and dataset_id:
                permalink = f"{self.plugin_config.portal_url}/d/{dataset_id}"

            lines.append(f"{i}. {name}")
            lines.append(f"   ID: {dataset_id}")
            lines.append(f"   Description: {description}")
            if category:
                lines.append(f"   Category: {category}")
            lines.append(f"   Portal: {permalink}")
            lines.append("")

        lines.append(
            f"View all datasets at: {self.plugin_config.portal_url}\n"
            f"Use get_dataset tool with dataset_id to get more details."
        )

        return "\n".join(lines)

    def _format_dataset(self, dataset: Dict[str, Any]) -> str:
        """Format dataset metadata for user display."""
        name = dataset.get("name", "Untitled")
        dataset_id = dataset.get("id", dataset.get("viewId", "unknown"))
        description = dataset.get("description", "No description")
        row_count = dataset.get("rowCount", "N/A")
        updated = dataset.get(
            "rowsUpdatedAt", dataset.get("metadata_updated_at", "N/A")
        )
        tags = dataset.get("tags", [])
        category = dataset.get("category", "")
        license_info = dataset.get("license", {})

        lines = [
            f"Dataset: {name}",
            f"ID: {dataset_id}",
            f"Description: {description}",
            f"Row count: {row_count}",
            f"Last updated: {updated}",
            "",
            f"Portal URL: {self.plugin_config.portal_url}/d/{dataset_id}",
            "",
        ]

        if tags:
            lines.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
        if category:
            lines.append(f"Category: {category}")
        if license_info:
            lines.append(f"License: {license_info}")

        lines.append("")
        lines.append(
            f"Use get_schema with dataset_id='{dataset_id}' to get column info, "
            f"then query_dataset to query data."
        )

        return "\n".join(lines)

    def _format_schema(self, columns: List[Dict[str, Any]]) -> str:
        """Format schema information for user display."""
        if not columns:
            return "No schema information available."

        lines = ["Schema fields (use these for SoQL queries):"]
        for col in columns:
            field_name = col.get("fieldName", col.get("id", col.get("name", "unknown")))
            display_name = col.get("name", col.get("displayName", ""))
            data_type = col.get("dataTypeName", col.get("type", "unknown"))
            description = col.get("description", "")

            lines.append(f"  • {field_name} ({data_type})")
            if display_name and display_name != field_name:
                lines.append(f"    Display: {display_name}")
            if description:
                lines.append(f"    {description}")

        return "\n".join(lines)

    def _format_query_results(
        self, records: List[Dict[str, Any]], limit: int = 100
    ) -> str:
        """Format query results for user display."""
        if not records:
            return "No records found matching the query."

        lines = [
            f"Found {len(records)} record(s) (showing first {min(limit, len(records))}):\n"
        ]

        for i, record in enumerate(records[:limit], 1):
            lines.append(f"Record {i}:")
            for key, value in record.items():
                if key != "_id":
                    lines.append(f"  {key}: {value}")
            lines.append("")

        if len(records) > limit:
            lines.append(f"... and {len(records) - limit} more record(s)")

        return "\n".join(lines)

    def _format_sql_results(
        self, records: List[Dict[str, Any]], fields: List[Dict[str, Any]]
    ) -> str:
        """Format SQL/SoQL query results for user display.

        Args:
            records: List of record dictionaries
            fields: List of field metadata dictionaries

        Returns:
            Formatted string representation of results
        """
        if not records:
            return "No records found matching the SoQL query."

        lines = [f"SQL Query Results: {len(records)} record(s)\n"]

        if fields:
            field_names = [field.get("id", "unknown") for field in fields]
            lines.append(f"Fields: {', '.join(field_names)}\n")

        for i, record in enumerate(records[:10], 1):
            lines.append(f"Record {i}:")
            for key, value in record.items():
                if key != "_id":
                    lines.append(f"  {key}: {value}")
            lines.append("")

        if len(records) > 10:
            lines.append(f"... and {len(records) - 10} more record(s)")

        return "\n".join(lines)

    def _format_categories(self, categories: List[Any]) -> str:
        """Format categories for user display."""
        if not categories:
            return f"No categories found on {self.plugin_config.city_name}'s open data portal."

        lines = [f"Categories on {self.plugin_config.city_name}'s open data portal:\n"]

        for i, cat in enumerate(categories, 1):
            if isinstance(cat, dict):
                name = cat.get("name", cat.get("label", str(cat)))
                count = cat.get("count", cat.get("count", ""))
                lines.append(f"  {i}. {name}: {count} dataset(s)")
            else:
                lines.append(f"  {i}. {cat}")

        return "\n".join(lines)
