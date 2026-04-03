# Built-in Plugins Reference

OpenContext includes built-in plugins for CKAN, ArcGIS Hub, and Socrata open data portals.

## CKAN Plugin

For CKAN-based open data portals (e.g., data.gov, data.gov.uk).

### Configuration

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.yourcity.gov"       # CKAN API base URL
    portal_url: "https://data.yourcity.gov"     # Public portal URL
    city_name: "Your City"                      # City/organization name
    timeout: 120                                # HTTP timeout in seconds
    api_key: "${CKAN_API_KEY}"                  # Optional: API key
```

### Tools

| Tool | Description |
|------|-------------|
| `ckan__search_datasets(query, limit)` | Search for datasets |
| `ckan__get_dataset(dataset_id)` | Get dataset metadata |
| `ckan__query_data(resource_id, filters, limit)` | Query data from a resource |
| `ckan__get_schema(resource_id)` | Get schema for a resource |
| `ckan__execute_sql(sql)` | Execute PostgreSQL SELECT queries (advanced) |
| `ckan__aggregate_data(resource_id, metrics, group_by, filters, having, order_by, limit)` | Aggregate data with GROUP BY — supports `count(*)`, `sum()`, `avg()`, `min()`, `max()`, `stddev()` |

### SQL Execution

The `execute_sql` tool allows complex PostgreSQL queries (CTEs, window functions, joins). Only SELECT is allowed — INSERT, UPDATE, DELETE, DROP, and other destructive operations are blocked. Resource IDs must be valid UUIDs in double quotes: `FROM "uuid-here"`.

### CKAN API

This plugin uses CKAN's Action API:
- `/api/3/action/package_search` - Search datasets
- `/api/3/action/package_show` - Get dataset
- `/api/3/action/datastore_search` - Query data

See [CKAN API documentation](https://docs.ckan.org/en/latest/api/) for details.

---

## ArcGIS Hub Plugin

For ArcGIS Hub open data portals (e.g., hub.arcgis.com, data-yourcity.hub.arcgis.com).

### Configuration

```yaml
plugins:
  arcgis:
    enabled: true
    portal_url: "https://hub.arcgis.com"        # ArcGIS Hub portal URL
    city_name: "Your City"                       # City/organization name
    timeout: 120                                 # HTTP timeout in seconds
    token: "${ARCGIS_TOKEN}"                     # Optional: bearer token for private items
```

### Tools

| Tool | Description |
|------|-------------|
| `arcgis__search_datasets(q, limit)` | Search the Hub catalog |
| `arcgis__get_dataset(dataset_id)` | Get metadata for a Hub item (32-char hex ID) |
| `arcgis__get_aggregations(field, q)` | Facet counts for type, tags, categories, or access |
| `arcgis__query_data(dataset_id, where, out_fields, limit)` | Query a Feature Service |

### Usage Notes

- `get_dataset` returns the Hub item metadata. Check that the item has a queryable `serviceUrl` before calling `query_data`.
- `get_aggregations` accepts `field` values: `"type"`, `"tags"`, `"categories"`, `"access"`.
- `query_data` uses the ArcGIS Feature Service query interface. The `where` parameter is a SQL WHERE clause (e.g., `"population > 10000"`). Only Feature Layer, Feature Service, Map Service, and Table types are queryable.

### ArcGIS API

This plugin uses two API layers:
- **Hub Search API** (OGC API - Records) — catalog search and aggregations
- **ArcGIS Feature Service** query endpoint — data queries

---

## Socrata Plugin

For Socrata-based open data portals (e.g., data.cityofchicago.org, data.cityofnewyork.us, data.seattle.gov).

**Note:** A Socrata app token is **required**. Register for a free token at [https://dev.socrata.com/register](https://dev.socrata.com/register).

### Configuration

```yaml
plugins:
  socrata:
    enabled: true
    base_url: "https://data.yourcity.gov"
    portal_url: "https://data.yourcity.gov"
    city_name: "Your City"
    app_token: "${SOCRATA_APP_TOKEN}"   # Required
    timeout: 30                          # HTTP timeout in seconds (default: 30)
```

### Tools

| Tool | Description |
|------|-------------|
| `socrata__search_datasets(query, limit)` | Search for datasets in the portal catalog |
| `socrata__get_dataset(dataset_id)` | Get full metadata for a dataset (4x4 ID) |
| `socrata__get_schema(dataset_id)` | Get column schema for constructing SoQL queries |
| `socrata__query_dataset(dataset_id, soql_query)` | Query data using SoQL |
| `socrata__list_categories()` | List all categories with dataset counts |
| `socrata__execute_sql(dataset_id, soql)` | Execute raw SoQL SELECT (advanced) |

### Typical Workflow

```
list_categories → search_datasets → get_dataset → get_schema → query_dataset
```

### SoQL Notes

- `GROUP BY` is required whenever using `COUNT()` or any aggregation.
- Boolean fields use `= true` / `= false`, not `= 'Y'` or `= 1`.
- For conditional counts: `SUM(CASE WHEN col = true THEN 1 ELSE 0 END)`.
- `LIMIT` caps returned rows and can affect aggregation results.

### Socrata API

This plugin uses two Socrata API layers:
- **Discovery API** (api.us.socrata.com) — catalog search, categories
- **SODA3** (portal domain) — dataset metadata, schema, data queries

See [Socrata developer documentation](https://dev.socrata.com/) for details.

---

## Custom Plugins

If your portal doesn't use CKAN, ArcGIS Hub, or Socrata, you can create a custom plugin. See [Custom Plugins Guide](CUSTOM_PLUGINS.md) for instructions.

## Examples

See [examples/](../examples/) for complete configuration examples per city.
