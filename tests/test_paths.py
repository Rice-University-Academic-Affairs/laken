import pytest

from laken.paths import format_table_name, parse_table_name, require_qualified_table_name


class TestParseTableName:
    def test_bare_name_defaults_to_dbo(self):
        assert parse_table_name("products") == ("dbo", "products")

    def test_qualified_name(self):
        assert parse_table_name("marketing.products") == ("marketing", "products")

    def test_four_part_name(self):
        assert parse_table_name("MyWorkspace.Sales_LH.marketing.products") == (
            "marketing",
            "products",
        )

    def test_three_part_name_raises(self):
        with pytest.raises(ValueError):
            parse_table_name("workspace.lakehouse.table")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_table_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_table_name("   ")


class TestRequireQualifiedTableName:
    def test_bare_name_raises(self):
        with pytest.raises(ValueError, match="schema.table"):
            require_qualified_table_name("products")

    def test_qualified_name(self):
        assert require_qualified_table_name("marketing.products") == ("marketing", "products")

    def test_four_part_name(self):
        assert require_qualified_table_name("MyWorkspace.Sales_LH.marketing.products") == (
            "marketing",
            "products",
        )


class TestFormatTableName:
    def test_formats_schema_and_table(self):
        assert format_table_name("marketing", "products") == "marketing.products"
