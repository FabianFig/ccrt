"""The CLI can use a local credential without persisting it in datasets."""

from pathlib import Path

import pytest

from ccrt import cli
from ccrt.config import ucdp_api_key


def test_local_env_file_and_precedence(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("UCDP_API_KEY=local-token\nOTHER=value\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UCDP_API_KEY", raising=False)
    assert ucdp_api_key() == "local-token"
    monkeypatch.setenv("UCDP_API_KEY", "process-token")
    assert ucdp_api_key() == "process-token"


def test_only_local_file_is_read(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("UCDP_API_KEY=parent-token\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    monkeypatch.delenv("UCDP_API_KEY", raising=False)
    assert ucdp_api_key() is None
    assert ucdp_api_key(tmp_path / ".env") == "parent-token"
    with pytest.raises(FileNotFoundError, match="environment file not found"):
        ucdp_api_key(Path("missing.env"))


def test_token_is_not_interpolated_or_added_to_process(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("UCDP_API_KEY='literal-${OTHER}'\nOTHER=private\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UCDP_API_KEY", raising=False)
    monkeypatch.delenv("OTHER", raising=False)
    assert ucdp_api_key() == "literal-${OTHER}"
    import os

    assert "UCDP_API_KEY" not in os.environ
    assert "OTHER" not in os.environ


def test_fetch_cli_uses_local_file_without_network(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("UCDP_API_KEY=local-token\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UCDP_API_KEY", raising=False)
    captured = {}

    class FakeClient:
        def __init__(self, *, api_key):
            captured["key"] = api_key

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def fetch(self, **kwargs):
            captured["options"] = kwargs
            return cli.load_ucdp_csv(
                Path(__file__).resolve().parents[1] / "examples/ucdp_synthetic.csv", version="26.1"
            )

    monkeypatch.setattr(cli, "UCDPClient", FakeClient)
    assert cli.main(["fetch-ucdp", "result.json", "--version", "26.1", "--country", "645"]) == 0
    assert captured["key"] == "local-token"
    assert captured["options"]["countries"] == [645]
    assert "local-token" not in (tmp_path / "result.json").read_text()
