import json

import pytest

from laken.workspace import TableMetadataStore


def test_load_returns_empty_tables_when_missing(tmp_path):
    store = TableMetadataStore(tmp_path / "tables.json")
    assert store.load() == {"tables": {}}


def test_load_treats_corrupt_json_as_empty(tmp_path):
    path = tmp_path / "tables.json"
    path.write_text("{not json", encoding="utf-8")
    store = TableMetadataStore(path)
    with pytest.raises(json.JSONDecodeError):
        store.load()


def test_load_treats_missing_tables_key_as_empty(tmp_path):
    path = tmp_path / "tables.json"
    path.write_text('{"other": 1}', encoding="utf-8")
    store = TableMetadataStore(path)
    assert store.load() == {"tables": {}}


def test_save_writes_via_tmp_and_remove_clears_entry(tmp_path):
    path = tmp_path / "metadata" / "tables.json"
    store = TableMetadataStore(path)
    store.upsert("products", {"state": "mirror"})
    assert path.is_file()
    assert not (path.parent / "tables.json.tmp").exists()
    assert store.table("products") == {"state": "mirror"}
    store.remove("products")
    assert store.table("products") is None
