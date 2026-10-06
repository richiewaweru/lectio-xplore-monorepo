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
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _d: m)
    figure = _figure([_media()])
    assert figure.asset_id == "https://storage.example.test/figure.png"
    # Authored alt text wins over media alt; media alt wins over caption.
    assert figure.alt == "A labeled diagram"


def test_figure_media_alt_used_when_authored_alt_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _d: m)
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

    monkeypatch.setattr(adapter, "verify_bound_media_outcome", _boom)
    with pytest.raises(SharedDocumentLearnMappingError, match="binding failed"):
        _figure([_media()])


@pytest.mark.parametrize(
    "overrides", [{"status": "failed"}, {"asset_url": "gs://bucket/figure.png"}]
)
def test_unusable_media_rejected(monkeypatch: pytest.MonkeyPatch, overrides) -> None:
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _d: m)
    with pytest.raises(SharedDocumentLearnMappingError, match="not ready"):
        _figure([_media(**overrides)])


def test_quality_warning_media_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _d: m)
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


class _FakeSession:
    def __init__(self, run) -> None:
        self.run = run
        self.queries = 0
        self.flushes = 0

    async def scalar(self, _stmt):
        self.queries += 1
        return self.run

    async def flush(self) -> None:
        self.flushes += 1


async def test_backfill_fills_imageless_figures_once_then_no_further_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import document.shared_lesson.media as media_mod
    import document.shared_lesson.repository as repo_mod
    from learn.generation.shared_document_execution import backfill_figure_media

    stored = SimpleNamespace(status="ready", document=object())

    async def _load(_session, **_kw):
        return stored

    monkeypatch.setattr(repo_mod, "load_shared_lesson_document", _load)
    monkeypatch.setattr(media_mod, "bind_durable_media_outcome", lambda _out, _d: _media())
    monkeypatch.setattr(media_mod, "verify_bound_media_outcome", lambda m, _d: m)
    item = SimpleNamespace(
        id="w1",
        replaces_work_item_id=None,
        stage="media_generation",
        item_key="media:figure-1",
        status="ready",
        output_json={"kind": "figure"},
    )
    session = _FakeSession(SimpleNamespace(work_items=[item]))
    nodes = [
        {"id": "figure-1", "kind": "figure", "asset_id": None, "caption": "Cap", "alt": "Cap"},
        {"id": "figure-2", "kind": "figure", "asset_id": None, "caption": "Edited", "alt": "Mine"},
    ]
    editable = SimpleNamespace(
        document_json={"nodes": nodes},
        shared_document_run_id="run-1",
        shared_document_id="doc-1",
        shared_document_revision=1,
    )
    assert await backfill_figure_media(session, editable=editable) is True
    first = editable.document_json["nodes"]
    assert first[0]["asset_id"] == "https://storage.example.test/figure.png"
    assert first[0]["alt"] == "Media alt"
    assert first[1]["asset_id"] is None  # no media for it; edits untouched
    assert first[1]["alt"] == "Mine"
    assert session.flushes == 1

    # Second load: figure-2 still lacks an image so one cheap query may run,
    # but nothing is written.
    before = editable.document_json
    assert await backfill_figure_media(session, editable=editable) is False
    assert editable.document_json is before
    assert session.flushes == 1

    # Fully imaged lesson: no query at all.
    editable.document_json = {"nodes": [{**first[0]}]}
    queries = session.queries
    assert await backfill_figure_media(session, editable=editable) is False
    assert session.queries == queries


def _unavailable_outcome(figure_node_id: str = "figure-1"):
    from document.shared_lesson.media import bind_durable_media_outcome, unavailable_figure_result
    from tests.document.test_shared_lesson_media import _document, _work

    outcome = unavailable_figure_result(
        _work(),
        error_code="provider_http_403",
        reason="The figure service was unavailable for this figure.",
        attempts=3,
    )
    bound = bind_durable_media_outcome(outcome.model_dump(mode="json"), _document())
    return bound.model_copy(update={"figure_node_id": figure_node_id})


def test_unavailable_figure_ships_a_placeholder_node(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _d: m)
    figure = _figure([_unavailable_outcome()])
    assert figure.status == "unavailable"
    assert figure.unavailable_reason == "The figure service was unavailable for this figure."
    assert figure.asset_id is None
    assert figure.caption
    assert figure.alt == "A labeled diagram"


def test_unavailable_figure_alt_falls_back_to_outcome_alt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _stored()
    node = stored.document.sections[0].nodes[2]
    blank = node.model_copy(
        update={"accessibility": node.accessibility.model_copy(update={"alt_text": ""})}
    )
    outcome = _unavailable_outcome()
    out = adapter._ordinary_node(blank, {"figure-1": outcome})
    assert out["alt"] == outcome.alt_text
    assert "asset_id" not in out


def test_unavailable_patch_marks_figure_and_ready_replaces_it() -> None:
    document = {
        "nodes": [
            {"id": "figure-1", "kind": "figure", "asset_id": None, "caption": "Cap", "alt": ""},
        ]
    }
    outcome = _unavailable_outcome()
    fields = _figure_fields_from_media([outcome])
    patched = _with_figure_media(document, fields)
    node = patched["nodes"][0]
    assert node["status"] == "unavailable"
    assert node["unavailable_reason"] == outcome.reason
    assert node["asset_id"] is None
    assert document["nodes"][0].get("status") is None
    # Idempotent: nothing changes the second time.
    assert _with_figure_media(patched, fields) is patched
    # A later ready asset replaces the placeholder and clears the marker.
    ready = _figure_fields_from_media([_media()])
    upgraded = _with_figure_media(patched, ready)["nodes"][0]
    assert upgraded["asset_id"] == "https://storage.example.test/figure.png"
    assert "status" not in upgraded and "unavailable_reason" not in upgraded


def test_publish_divergence_check_ignores_unavailable_markers() -> None:
    from learn.publishing.shared_document_publish import _without_figure_media

    plain = {"f": {"kind": "figure", "caption": "Cap"}}
    marked = {
        "f": {
            "kind": "figure",
            "caption": "Cap",
            "status": "unavailable",
            "unavailable_reason": "r",
            "alt": "a",
            "asset_id": None,
        }
    }
    assert _without_figure_media(plain) == _without_figure_media(marked)
