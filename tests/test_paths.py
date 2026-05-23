import pytest

from laken.table_names import (
    TableRef,
    format_table_name,
    parse_table_name,
    parse_table_ref,
    spark_table_name,
)


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

    def test_three_part_name_raises(self):
        with pytest.raises(ValueError, match="schema.table"):
            parse_table_name("MyWorkspace.Sales_LH.products")

    def test_four_part_name_raises(self):
        with pytest.raises(ValueError, match="schema.table"):
            parse_table_name("MyWorkspace.Sales_LH.marketing.products")


class TestParseTableRef:
    def test_bare_name(self):
        assert parse_table_ref("products") == TableRef(schema="dbo", table="products")

    def test_qualified_name(self):
        assert parse_table_ref("marketing.products") == TableRef(
            schema="marketing", table="products"
        )


class TestSparkTableName:
    def test_bare_table(self):
        assert spark_table_name(TableRef(schema="dbo", table="products")) == "products"

    def test_qualified_table(self):
        assert spark_table_name(TableRef(schema="marketing", table="products")) == (
            "marketing.products"
        )


class TestFormatTableName:
    def test_formats_schema_and_table(self):
        assert format_table_name("marketing", "products") == "marketing.products"
