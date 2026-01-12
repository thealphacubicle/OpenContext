# Built-in Plugins Reference

OpenContext includes a built-in plugin for CKAN-based open data portals.

## CKAN Plugin

For CKAN-based open data portals (e.g., data.boston.gov, data.gov, data.gov.uk).

### Configuration

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.yourcity.gov" # CKAN API base URL
    portal_url: "https://data.yourcity.gov" # Public portal URL
    city_name: "Your City" # City/organization name
    timeout: 120 # HTTP timeout in seconds
    api_key: "${CKAN_API_KEY}" # Optional: API key
```

### Tools

- `ckan__search_datasets(query, limit)` - Search for datasets
- `ckan__get_dataset(dataset_id)` - Get dataset metadata
- `ckan__query_data(resource_id, filters, limit)` - Query data from a resource
- `ckan__get_schema(resource_id)` - Get schema for a resource
- `ckan__execute_sql(sql)` - Execute raw PostgreSQL SELECT queries (advanced users)

### Examples

**Search datasets:**

```
Search for datasets about housing in Boston
```

**Get dataset:**

```
Get details about the "311 Service Requests" dataset
```

**Query data:**

```
Query the first 10 records from resource abc123
```

**Execute SQL (Advanced):**

```
Execute SQL: SELECT COUNT(*) FROM "resource-uuid" WHERE status = 'Open'
```

The `execute_sql` tool allows advanced users to write complex PostgreSQL queries including:

- Window functions (RANK(), ROW_NUMBER(), etc.)
- Common Table Expressions (CTEs)
- Complex aggregations
- Joins across resources

**Security:** Only SELECT queries are allowed. INSERT, UPDATE, DELETE, DROP, and other destructive operations are blocked. Resource IDs must be valid UUIDs and must be double-quoted in SQL queries.

## CKAN API

This plugin uses CKAN's Action API:

- `/api/3/action/package_search` - Search datasets
- `/api/3/action/package_show` - Get dataset
- `/api/3/action/datastore_search` - Query data
- `/api/3/action/datastore_search_sql` - Execute SQL queries (for `execute_sql` tool)

See [CKAN API documentation](https://docs.ckan.org/en/latest/api/) for details.

## SQL Execution Security

The `execute_sql` tool includes comprehensive security validation:

- **Query Type**: Only SELECT statements allowed
- **Forbidden Keywords**: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, GRANT, REVOKE, TRUNCATE, EXECUTE, EXEC, CALL, DECLARE, SET
- **Pattern Detection**: Blocks SQL injection patterns, multiple statements, dangerous comments
- **Length Limits**: Maximum query length of 50,000 characters
- **UUID Validation**: Resource IDs must be valid UUIDs in double quotes

All SQL queries are validated before execution to prevent SQL injection and destructive operations.

## Custom Plugins

If your portal doesn't use CKAN, you can create a custom plugin. See [Custom Plugins Guide](CUSTOM_PLUGINS.md) for instructions.

## Examples

See [examples/](../examples/) for complete configuration examples.
