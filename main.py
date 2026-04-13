"""Google Cloud Functions gen2 entry module.

Cloud Functions Python loads `mcp_http` from this file (see Terraform `entry_point`).
The deployment zip must place this file at the archive root next to `core/`, `server/`, etc.

AWS Lambda uses `server.adapters.aws_lambda.lambda_handler` instead; this file is unused there.
"""

from server.adapters.gcp_functions import mcp_http  # noqa: F401
