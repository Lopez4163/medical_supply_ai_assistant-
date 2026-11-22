from __future__ import annotations

import argparse

import pytest

from scripts import e2e_database


def test_test_database_url_accepts_exact_isolated_database(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+psycopg://user:password@127.0.0.1:55432/medical_supply_test"
    monkeypatch.setenv("TEST_DATABASE_URL", database_url)

    assert e2e_database.test_database_url() == database_url


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql+psycopg://user:password@127.0.0.1:55432/medical_supply_development?anything=/medical_supply_test",
        "postgresql+psycopg://user:password@127.0.0.1:55432/medical_supply_development",
        "postgresql+psycopg://user:password@127.0.0.1:55432/",
        "not a database url",
        "",
    ),
)
def test_test_database_url_rejects_non_isolated_or_malformed_urls(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", database_url)

    with pytest.raises(SystemExit, match="medical_supply_test"):
        e2e_database.test_database_url()


def test_validate_command_rejects_before_database_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://user:password@127.0.0.1:55432/medical_supply_development?anything=/medical_supply_test",
    )
    monkeypatch.setattr(
        e2e_database,
        "parse_args",
        lambda: argparse.Namespace(command="validate", created_since=None),
    )
    database_operations: list[object] = []
    monkeypatch.setattr(
        e2e_database.asyncio,
        "run",
        lambda operation: database_operations.append(operation),
    )

    with pytest.raises(SystemExit, match="medical_supply_test"):
        e2e_database.main()

    assert database_operations == []
