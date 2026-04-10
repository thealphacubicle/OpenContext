"""WHERE clause validator for ArcGIS Feature Service queries.

Provides light sanitization of SQL WHERE clauses to prevent
injection of destructive operations.
"""

import re


class WhereValidator:
    """Validates WHERE clause strings for Feature Service queries."""

    FORBIDDEN_KEYWORDS = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "EXEC",
        "EXECUTE",
    ]

    @classmethod
    def validate(cls, where: str) -> str:
        """Validate and sanitize a WHERE clause string.

        Args:
            where: SQL WHERE clause string

        Returns:
            The original WHERE clause if valid, or "1=1" if empty/None

        Raises:
            ValueError: If the clause contains forbidden SQL keywords
        """
        if not where:
            return "1=1"

        where = where.strip()
        if not where:
            return "1=1"

        where_upper = where.upper()
        for keyword in cls.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{keyword}\b", where_upper):
                raise ValueError(
                    f"Forbidden keyword '{keyword}' detected in WHERE clause"
                )

        return where
