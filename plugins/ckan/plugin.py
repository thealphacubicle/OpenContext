"""CKAN plugin implementation for OpenContext.

This plugin provides access to CKAN-based open data portals.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.interfaces import DataPlugin, PluginType, ToolDefinition, ToolResult
from plugins.ckan.config_schema import CKANPluginConfig

logger = logging.getLogger(__name__)


class CKANPlugin(DataPlugin):
    """Plugin for accessing CKAN-based open data portals.

    This plugin implements the DataPlugin interface and provides tools for
    searching datasets, retrieving dataset metadata, and querying data.
    """

    plugin_name = "ckan"
    plugin_type = PluginType.OPEN_DATA
    plugin_version = "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize CKAN plugin with configuration.

        Args:
            config: Plugin configuration dictionary
        """
        super().__init__(config)
        self.plugin_config = CKANPluginConfig(**config)
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> bool:
        """Initialize CKAN plugin and test connection.

        Returns:
            True if initialization succeeded
        """
        try:
            # Create HTTP client
            headers = {}
            if self.plugin_config.api_key:
                headers["Authorization"] = self.plugin_config.api_key

            self.client = httpx.AsyncClient(
                base_url=self.plugin_config.base_url,
                headers=headers,
                timeout=self.plugin_config.timeout,
            )

            # Test connection
            response = await self._call_ckan_api("status_show", {})
            if response.get("success"):
                self._initialized = True
                logger.info(
                    f"CKAN plugin initialized successfully for {self.plugin_config.city_name}"
                )
                return True
            else:
                logger.error("CKAN API connection test failed")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize CKAN plugin: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown plugin and close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
        self._initialized = False
        logger.info("CKAN plugin shut down")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_ckan_api(
        self, action: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call CKAN API action.

        Args:
            action: CKAN action name (e.g., "package_search")
            data: Action parameters

        Returns:
            CKAN API response
        """
        if not self.client:
            raise RuntimeError("Plugin not initialized")

        url = f"/api/3/action/{action}"
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_tools(self) -> List[ToolDefinition]:
        """Get list of tools provided by CKAN plugin.

        Returns:
            List of tool definitions
        """
        return [
            ToolDefinition(
                name="search_datasets",
                description=f"Search for datasets in {self.plugin_config.city_name}'s open data portal",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="get_dataset",
                description=f"Get detailed information about a specific dataset from {self.plugin_config.city_name}'s open data portal",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset ID or name",
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
            ToolDefinition(
                name="query_data",
                description=f"Query data from a specific resource in {self.plugin_config.city_name}'s open data portal",
                input_schema={
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "Resource ID to query",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Optional filters (field: value pairs)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of records (default: 100)",
                            "default": 100,
                        },
                    },
                    "required": ["resource_id"],
                },
            ),
            ToolDefinition(
                name="get_schema",
                description=f"Get schema information for a resource in {self.plugin_config.city_name}'s open data portal",
                input_schema={
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "Resource ID",
                        },
                    },
                    "required": ["resource_id"],
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
                limit = arguments.get("limit", 20)
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

            elif tool_name == "query_data":
                resource_id = arguments.get("resource_id")
                if not resource_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="resource_id is required",
                    )
                filters = arguments.get("filters", {})
                limit = arguments.get("limit", 100)
                data = await self.query_data(resource_id, filters, limit)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_query_results(data, limit),
                        }
                    ],
                    success=True,
                )

            elif tool_name == "get_schema":
                resource_id = arguments.get("resource_id")
                if not resource_id:
                    return ToolResult(
                        content=[],
                        success=False,
                        error_message="resource_id is required",
                    )
                schema = await self.get_schema(resource_id)
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": self._format_schema(schema),
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
                error_message=f"Tool execution failed: {str(e)}",
            )

    async def search_datasets(
        self, query: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for datasets matching a query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of dataset metadata dictionaries
        """
        response = await self._call_ckan_api(
            "package_search", {"q": query, "rows": limit}
        )
        return response.get("result", {}).get("results", [])

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Get detailed metadata for a specific dataset.

        Args:
            dataset_id: Dataset ID or name

        Returns:
            Dataset metadata dictionary
        """
        response = await self._call_ckan_api("package_show", {"id": dataset_id})
        return response.get("result", {})

    async def query_data(
        self,
        resource_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query data from a specific resource.

        Args:
            resource_id: Resource ID
            filters: Optional filters (field: value pairs)
            limit: Maximum number of records

        Returns:
            List of data records
        """
        params = {"resource_id": resource_id, "limit": limit}

        # Convert filters to CKAN filter format
        if filters:
            for field, value in filters.items():
                params[f"filters[{field}]"] = value

        response = await self._call_ckan_api("datastore_search", params)
        return response.get("result", {}).get("records", [])

    async def get_schema(self, resource_id: str) -> Dict[str, Any]:
        """Get schema information for a resource.

        Args:
            resource_id: Resource ID

        Returns:
            Schema information dictionary
        """
        # Get schema by calling datastore_search with limit=0
        response = await self._call_ckan_api(
            "datastore_search", {"resource_id": resource_id, "limit": 0}
        )
        return response.get("result", {}).get("fields", [])

    async def health_check(self) -> bool:
        """Check if CKAN API is accessible.

        Returns:
            True if healthy
        """
        try:
            response = await self._call_ckan_api("status_show", {})
            return response.get("success", False)
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

        for i, dataset in enumerate(datasets, 1):
            title = dataset.get("title", "Untitled")
            dataset_id = dataset.get("id", "unknown")
            notes = dataset.get("notes", "")[:100] + "..." if dataset.get("notes") else "No description"

            lines.append(f"{i}. {title}")
            lines.append(f"   ID: {dataset_id}")
            lines.append(f"   Description: {notes}")
            lines.append(f"   Portal: {self.plugin_config.portal_url}/dataset/{dataset_id}")
            lines.append("")

        lines.append(
            f"View all datasets at: {self.plugin_config.portal_url}\n"
            f"Use get_dataset tool with a dataset ID to get more details."
        )

        return "\n".join(lines)

    def _format_dataset(self, dataset: Dict[str, Any]) -> str:
        """Format dataset metadata for user display."""
        title = dataset.get("title", "Untitled")
        dataset_id = dataset.get("id", "unknown")
        notes = dataset.get("notes", "No description")
        organization = dataset.get("organization", {}).get("title", "Unknown")
        resources = dataset.get("resources", [])

        lines = [
            f"Dataset: {title}",
            f"ID: {dataset_id}",
            f"Organization: {organization}",
            f"Description: {notes}",
            "",
            f"Portal URL: {self.plugin_config.portal_url}/dataset/{dataset_id}",
            "",
        ]

        if resources:
            lines.append(f"Resources ({len(resources)}):")
            for i, resource in enumerate(resources, 1):
                res_name = resource.get("name", "Unnamed")
                res_id = resource.get("id", "unknown")
                res_format = resource.get("format", "unknown")
                lines.append(f"  {i}. {res_name} ({res_format})")
                lines.append(f"     Resource ID: {res_id}")
                lines.append(
                    f"     Use query_data tool with resource_id='{res_id}' to query this data"
                )
        else:
            lines.append("No resources available for this dataset.")

        return "\n".join(lines)

    def _format_query_results(
        self, records: List[Dict[str, Any]], limit: int
    ) -> str:
        """Format query results for user display."""
        if not records:
            return "No records found matching the query."

        lines = [
            f"Found {len(records)} record(s) (showing up to {limit}):\n"
        ]

        # Show first few records as examples
        for i, record in enumerate(records[:5], 1):
            lines.append(f"Record {i}:")
            for key, value in record.items():
                if key != "_id":  # Skip internal ID
                    lines.append(f"  {key}: {value}")
            lines.append("")

        if len(records) > 5:
            lines.append(f"... and {len(records) - 5} more record(s)")

        return "\n".join(lines)

    def _format_schema(self, fields: List[Dict[str, Any]]) -> str:
        """Format schema information for user display."""
        if not fields:
            return "No schema information available."

        lines = ["Schema fields:"]
        for field in fields:
            field_id = field.get("id", "unknown")
            field_type = field.get("type", "unknown")
            field_info = field.get("info", {})
            description = field_info.get("label", "") if field_info else ""

            lines.append(f"  • {field_id} ({field_type})")
            if description:
                lines.append(f"    {description}")

        return "\n".join(lines)

