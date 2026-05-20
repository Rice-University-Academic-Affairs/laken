import pytest

from laken.paths import format_table_name, parse_table_name


class TestParseTableName:
    def test_bare_name_defaults_to_dbo(self):
        assert parse_table_name("products") == ("dbo", "products")

    def test_qualified_name(self):
        assert parse_table_name("marketing.products") == ("marketing", "products")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_table_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_table_name("   ")


class TestFormatTableName:
    def test_formats_schema_and_table(self):
        assert format_table_name("marketing", "products") == "marketing.products"
