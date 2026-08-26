"""Where configuration actually comes from.

`.env.example` says to copy it and fill in your values. For five variables that
was false: they were read with `os.getenv`, and pydantic-settings parses the env
file into the Settings object without ever touching `os.environ`. Setting a seed
password there did nothing, silently, because `extra="ignore"` swallows the key —
so someone could believe they had replaced a demo credential and had not.

These tests pin both halves: the file is honoured, and the real process
environment still outranks it, which is what every deployment relies on.
"""
from __future__ import annotations

import pytest

from config import Settings

FIVE = [
    "RUN_MIGRATIONS_ON_STARTUP",
    "SEED_ON_STARTUP",
    "SEED_ADMIN_PASSWORD",
    "SEED_OWNER_PASSWORD",
    "SUPERADMIN_PASSWORD",
]


def _write_env(tmp_path, **values: str):
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    return path


def test_all_five_are_settings_fields():
    """If any drops back to os.getenv, .env silently stops working for it again."""
    for name in FIVE:
        assert name in Settings.model_fields, f"{name} must be read through Settings"


def test_the_env_file_is_honoured(tmp_path):
    env = _write_env(
        tmp_path,
        RUN_MIGRATIONS_ON_STARTUP="true",
        SEED_ON_STARTUP="true",
        SEED_ADMIN_PASSWORD="from-file-admin",
        SEED_OWNER_PASSWORD="from-file-owner",
        SUPERADMIN_PASSWORD="from-file-super",
    )

    settings = Settings(_env_file=str(env))

    assert settings.RUN_MIGRATIONS_ON_STARTUP is True
    assert settings.SEED_ON_STARTUP is True
    assert settings.SEED_ADMIN_PASSWORD.get_secret_value() == "from-file-admin"
    assert settings.SEED_OWNER_PASSWORD.get_secret_value() == "from-file-owner"
    assert settings.SUPERADMIN_PASSWORD.get_secret_value() == "from-file-super"


def test_the_process_environment_outranks_the_file(tmp_path, monkeypatch):
    """Render and CI pass real environment variables. They must keep winning."""
    env = _write_env(
        tmp_path,
        SEED_ON_STARTUP="true",
        SEED_ADMIN_PASSWORD="from-file",
    )
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "from-process-env")

    settings = Settings(_env_file=str(env))

    assert settings.SEED_ON_STARTUP is False
    assert settings.SEED_ADMIN_PASSWORD.get_secret_value() == "from-process-env"


def test_the_defaults_are_the_safe_ones():
    """Nothing runs migrations or seeds unless it was asked to."""
    settings = Settings(_env_file=None)

    assert settings.RUN_MIGRATIONS_ON_STARTUP is False
    assert settings.SEED_ON_STARTUP is False
    # No working default: a default that works is a default that ships.
    assert settings.SUPERADMIN_PASSWORD.get_secret_value() == ""


def test_a_password_never_prints_itself(tmp_path):
    """A traceback or a stray log line must not carry a credential out."""
    env = _write_env(tmp_path, SEED_ADMIN_PASSWORD="super-secret-value")
    settings = Settings(_env_file=str(env))

    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)
    assert "super-secret-value" not in repr(settings.SEED_ADMIN_PASSWORD)
    assert "super-secret-value" not in str(settings.SEED_ADMIN_PASSWORD)
    # Still readable when deliberately asked for.
    assert settings.SEED_ADMIN_PASSWORD.get_secret_value() == "super-secret-value"


@pytest.mark.asyncio
async def test_production_refuses_to_seed_with_the_demo_passwords(monkeypatch):
    """render.yaml had SEED_ON_STARTUP=true and set neither password.

    An empty user table on production would have created two super admins with
    the credentials committed to this repository. Nothing stopped it but the fact
    that users already existed.
    """
    import config
    import seeds.seed as seed_module

    # seed() resolves `settings` at call time from the cached singleton, so the
    # singleton is what has to look like production.
    monkeypatch.setattr(config.settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError, match="demo passwords"):
        await seed_module.seed()
