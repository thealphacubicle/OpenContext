"""Tests for Socrata SoQL validator."""

from plugins.socrata.soql_validator import SoQLValidator


class TestSoQLValidator:
    """Test SoQLValidator.validate_query."""

    def test_valid_select_passes(self):
        """Valid SELECT query passes validation."""
        is_valid, error = SoQLValidator.validate_query("SELECT * LIMIT 10")
        assert is_valid is True
        assert error is None

    def test_valid_select_with_where_passes(self):
        """Valid SELECT with WHERE passes validation."""
        is_valid, error = SoQLValidator.validate_query(
            "SELECT name, count WHERE year > 2020 LIMIT 50"
        )
        assert is_valid is True
        assert error is None

    def test_empty_string_fails(self):
        """Empty string fails validation."""
        is_valid, error = SoQLValidator.validate_query("")
        assert is_valid is False
        assert "non-empty" in error

    def test_forbidden_keyword_delete_fails(self):
        """DELETE keyword fails validation."""
        is_valid, error = SoQLValidator.validate_query("DELETE FROM users")
        assert is_valid is False
        assert "DELETE" in error

    def test_forbidden_keyword_insert_fails(self):
        """INSERT keyword fails validation."""
        is_valid, error = SoQLValidator.validate_query("INSERT INTO t VALUES (1)")
        assert is_valid is False
        assert "INSERT" in error

    def test_must_start_with_select_fails(self):
        """Query not starting with SELECT fails."""
        is_valid, error = SoQLValidator.validate_query("UPDATE users SET x=1")
        assert is_valid is False
        # UPDATE is caught by forbidden keywords; FROM alone would hit SELECT check
        assert "UPDATE" in error or "SELECT" in error

    def test_too_long_fails(self):
        """Query exceeding max length fails."""
        long_query = "SELECT * " + "x" * SoQLValidator.MAX_SOQL_LENGTH
        is_valid, error = SoQLValidator.validate_query(long_query)
        assert is_valid is False
        assert "too long" in error

    def test_multiple_statements_fails(self):
        """Multiple statements (semicolon with content after) fail."""
        # Use SELECT twice to trigger multiple-statements check (not forbidden keywords)
        is_valid, error = SoQLValidator.validate_query(
            "SELECT * LIMIT 1; SELECT * LIMIT 1"
        )
        assert is_valid is False
        assert "Multiple statements" in error
