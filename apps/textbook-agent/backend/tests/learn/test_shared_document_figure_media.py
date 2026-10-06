from __future__ import annotations

from types import SimpleNamespace

import pytest
from tests.learn.test_shared_document_adapter import _identity, _stored

import learn.generation.shared_document_adapter as adapter
from document.shared_lesson.media import SharedFigureMediaError
from learn.generation.shared_document_adapter import (
    SharedDocumentLearnMappingError,
    realize_shared_document_for_learn,
)
from learn.generation.shared_document_execution import (
    _figure_fields_from_media,
    _with_figure_media,
)


def _media(**overrides):
    base = {
        "figure_node_id": "figure-1",
        "status": "ready",
        "asset_url": "https://storage.example.test/figure.png",
        "alt_text": "Media alt",
    }
    return SimpleNamespace(**{**base, **overrides})


def _figure(media_list):
    stored = _stored()
    result = realize_shared_document_for_learn(
        stored,
        expected_identity=_identity(stored),
        subject="Science",
        figure_media=media_list,
    )
    return next(n for n in result.document.nodes if n.kind == "figure")


def test_figure_with_media_carries_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_bound_figure_media", lambda m, _d: m)
    figure = _figure([_media()])
    assert figure.asset_id == "https://storage.example.test/figure.png"
    # Authored alt text wins over media alt; media alt wins over caption.
    assert figure.alt == "A labeled diagram"


def test_figure_media_alt_used_when_authored_alt_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_bound_figure_media", lambda m, _d: m)
    stored = _stored()
    node = stored.document.sections[0].nodes[2]
    assert node.kind == "figure"
    node_alt = adapter._ordinary_node(
        node.model_copy(
            update={"accessibility": node.accessibility.model_copy(update={"alt_text": ""})}
        ),
        {"figure-1": _media()},
    )
    assert node_alt["alt"] == "Media alt"


def test_figure_without_media_has_no_url_and_caption_alt_fallback() -> None:
    stored = _stored()
    node = stored.document.sections[0].nodes[2]
    plain = adapter._ordinary_node(
        node.model_copy(
            update={
                "display": node.display.model_copy(update={"asset_id": None}),
                "accessibility": node.accessibility.model_copy(update={"alt_text": ""}),
            }
        )
    )
    assert plain["asset_id"] is None
    assert plain["alt"] == "A figure"


def test_unverified_media_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_m, _d):
        raise SharedFigureMediaError("not bound")

    monkeypatch.setattr(adapter, "verify_bound_figure_media", _boom)
    with pytest.raises(SharedDocumentLearnMappingError, match="binding failed"):
        _figure([_media()])


@pytest.mark.parametrize(
    "overrides", [{"status": "failed"}, {"asset_url": "gs://bucket/figure.png"}]
)
def test_unusable_media_rejected(monkeypatch: pytest.MonkeyPatch, overrides) -> None:
    monkeypatch.setattr(adapter, "verify_bound_figure_media", lambda m, _d: m)
    with pytest.raises(SharedDocumentLearnMappingError, match="not ready"):
        _figure([_media(**overrides)])


def test_quality_warning_media_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_bound_figure_media", lambda m, _d: m)
    assert _figure([_media(status="ready_with_quality_warning")]).asset_id.startswith("https://")


def test_existing_lesson_figure_patch_adds_media_only_to_imageless_figures() -> None:
    document = {
        "nodes": [
            {"id": "figure-1", "kind": "figure", "asset_id": None, "caption": "Cap", "alt": "Cap"},
            {"id": "figure-2", "kind": "figure", "asset_id": "keep", "caption": "x", "alt": "x"},
            {"id": "p", "kind": "paragraph", "text": "t"},
        ]
    }
    fields = _figure_fields_from_media(
        [_media(), _media(figure_node_id="figure-2"), _media(figure_node_id="f3", status="failed")]
    )
    assert "f3" not in fields
    patched = _with_figure_media(document, fields)
    assert patched["nodes"][0]["asset_id"] == "https://storage.example.test/figure.png"
    assert patched["nodes"][0]["alt"] == "Media alt"
    assert patched["nodes"][1]["asset_id"] == "keep"
    assert document["nodes"][0]["asset_id"] is None
