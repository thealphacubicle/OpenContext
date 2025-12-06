# CKAN Plugin

Plugin for accessing CKAN-based open data portals.

## Configuration

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

## Tools

- `ckan.search_datasets` - Search for datasets
- `ckan.get_dataset` - Get dataset metadata
- `ckan.query_data` - Query data from a resource
- `ckan.get_schema` - Get schema for a resource

## Examples

**Search datasets:**
```
Search for datasets about housing
```

**Get dataset:**
```
Get details about dataset "311-service-requests"
```

**Query data:**
```
Query resource abc123 with filters status='Open', limit 50
```

## CKAN API

This plugin uses CKAN's Action API:
- `/api/3/action/package_search` - Search datasets
- `/api/3/action/package_show` - Get dataset
- `/api/3/action/datastore_search` - Query data

See [CKAN API documentation](https://docs.ckan.org/en/latest/api/) for details.

