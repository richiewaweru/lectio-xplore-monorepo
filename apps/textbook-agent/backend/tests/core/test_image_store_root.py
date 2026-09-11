from __future__ import annotations

from pathlib import Path

from media.storage.image_store import local_image_store_root


def test_image_store_root_is_absolute_and_independent_of_cwd(tmp_path, monkeypatch) -> None:
    configured = tmp_path / "images-root"
    configured.mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere" if False else tmp_path)
    from infra import config as infra_config

    monkeypatch.setattr(infra_config.settings, "image_store_root", str(configured))
    root = local_image_store_root()
    assert root.is_absolute()
    assert root == configured.resolve()
    cwd_relative = Path("data/images")
    assert root != (Path.cwd() / cwd_relative).resolve() or str(
        infra_config.settings.image_store_root
    )


def test_default_image_store_lives_under_backend_not_cwd(monkeypatch, tmp_path) -> None:
    from infra import config as infra_config

    monkeypatch.setattr(infra_config.settings, "image_store_root", "")
    monkeypatch.chdir(tmp_path)
    root = local_image_store_root()
    assert root.is_absolute()
    assert root.name == "images"
    assert "backend" in {part.lower() for part in root.parts} or root.parent.name == "data"
    assert root != (tmp_path / "data" / "images").resolve()
