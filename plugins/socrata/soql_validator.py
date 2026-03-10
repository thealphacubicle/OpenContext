"""SoQL validator for Socrata plugin.

Provides security validation for SoQL queries to prevent injection
and destructive operations.
"""

import re
from typing import Optional, Tuple


class SoQLValidator:
    """Validates SoQL queries for security before execution."""

    MAX_SOQL_LENGTH = 50000
    FORBIDDEN_KEYWORDS = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "GRANT",
        "REVOKE",
        "TRUNCATE",
        "EXECUTE",
        "EXEC",
        "CALL",
        "DECLARE",
        "SET",
    ]

    @staticmethod
    def validate_query(soql: str) -> Tuple[bool, Optional[str]]:
        """Validate SoQL security. Returns (is_valid, error_message).

        Args:
            soql: SoQL query string to validate

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
            If is_valid is True, error_message is None.
            If is_valid is False, error_message contains the reason.
        """
        # 1. Basic checks
        if not soql or not isinstance(soql, str):
            return False, "SoQL must be non-empty string"
        soql = soql.strip()
        if len(soql) > SoQLValidator.MAX_SOQL_LENGTH:
            return (
                False,
                f"SoQL too long (max {SoQLValidator.MAX_SOQL_LENGTH})",
            )

        # 2. Block forbidden keywords (check before SELECT check to get specific error messages)
        for keyword in SoQLValidator.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{keyword}\b", soql, re.IGNORECASE):
                return False, f"Forbidden keyword: {keyword}"

        # 3. Must start with SELECT
        soql_upper = soql.upper().strip()
        if not soql_upper.startswith("SELECT"):
            return False, "Only SELECT queries allowed"

        # 4. Block dangerous patterns
        patterns = [
            (r";\s*(?:SELECT|DROP|DELETE|INSERT)", "Multiple statements detected"),
            (r"--.*(?:DROP|DELETE)", "Dangerous comment detected"),
        ]
        for pattern, msg in patterns:
            if re.search(pattern, soql, re.IGNORECASE):
                return False, msg

        # 5. Block multiple statements (semicolon with content after it)
        if ";" in soql:
            parts = soql.split(";", 1)
            if len(parts) > 1 and parts[1].strip():
                return False, "Multiple statements not allowed"

        return True, None
