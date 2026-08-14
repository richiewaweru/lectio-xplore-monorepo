"""Deterministic topology checkpoint/recovery contract tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from planning.whole_lesson.repository import VisualTopologyConflict
from planning.whole_lesson.visual_topology_recovery import (
    TopologyRecoveryError,
    recover_flagged_visual_topology,
    topology_cache_key,
    topology_identity_digest,
)


def test_topology_identity_and_cache_fences_include_all_versions() -> None:
    identity = topology_identity_digest(
        source_digest="source-a", labels=["A", "B"], topology_schema_version="schema/1", planner_version="planner/1"
    )
    assert identity == topology_identity_digest(
        source_digest="source-a", labels=["A", "B"], topology_schema_version="schema/1", planner_version="planner/1"
    )
    assert identity != topology_identity_digest(
        source_digest="source-b", labels=["A", "B"], topology_schema_version="schema/1", planner_version="planner/1"
    )
    assert identity != topology_identity_digest(
        source_digest="source-a", labels=["A", "B"], label_map={"l0": "B", "l1": "A"},
        topology_schema_version="schema/1", planner_version="planner/1"
    )
    assert topology_cache_key(source_digest="s", topology_digest="t", qc_version="qc/1") != topology_cache_key(
        source_digest="s", topology_digest="t", qc_version="qc/2"
    )


class _FakeRepo:
    records: dict[str, dict] = {}
    events: list[dict] = []
    completions: list[dict] = []

    def __init__(self, _session, _generation_id):
        pass

    async def append_visual_topology_event(self, *, event_type, request_id, payload=None, **_):
        self.events.append({"type": event_type, "request_id": request_id, **(payload or {})})

    async def load_visual_topology_state(self):
        return {"requests": self.records, "history": [], "events": self.events}

    async def persist_visual_topology(self, *, request_id, record, identity_digest, **_):
        existing = self.records.get(request_id)
        if existing and existing.get("identity_digest") != identity_digest:
            raise VisualTopologyConflict("mismatch")
        if existing:
            return {"record": existing, "reused": True}
        saved = {**record, "identity_digest": identity_digest}
        self.records[request_id] = saved
        return {"record": saved, "reused": False}

    async def apply_visual_completion(self, **kwargs):
        self.completions.append(kwargs)
        return SimpleNamespace(status="ready", document_revision=4)


class _FakeStore:
    def __init__(self) -> None:
        self.uploads: list[dict] = []

    async def store_image(self, **kwargs):
        self.uploads.append(kwargs)
        return f"/images/{kwargs.get('filename') or 'recovered.png'}"


def _reset_repo() -> None:
    _FakeRepo.records = {}
    _FakeRepo.events = []
    _FakeRepo.completions = []


async def _accept_qc(**_):
    return {"status": "accept", "reasons": [], "correction_hint": ""}


def _valid_topology() -> dict:
    return {
        "version": "v1",
        "layout": "flow",
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
    }


@pytest.mark.asyncio
async def test_recovery_success_reuses_topology_and_never_calls_provider(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    calls = {"planner": 0, "reader": 0, "renderer": 0}

    async def planner(**_):
        calls["planner"] += 1
        return {
            "version": "v1",
            "layout": "flow",
            "nodes": [{"id": "n1"}, {"id": "n2"}],
            "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
        }

    async def reader(**_):
        calls["reader"] += 1
        return b"internal-image"

    async def renderer(**_):
        calls["renderer"] += 1
        return {"src": "/images/recovered.png", "sha256": "asset-hash"}

    first = await recover_flagged_visual_topology(
        session=object(), generation_id="g1", request_id="r1", source_text="water cycle",
        source_digest="src", labels=[], internal_asset_key="internal/raster",
        planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=_accept_qc,
    )
    second = await recover_flagged_visual_topology(
        session=object(), generation_id="g1", request_id="r1", source_text="water cycle",
        source_digest="src", labels=[], internal_asset_key="internal/raster",
        planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=_accept_qc,
    )
    assert first["status"] == second["status"] == "ready"
    assert second["reused"] is True
    assert calls["planner"] == 1
    assert calls["reader"] == calls["renderer"] == 2
    assert not any(event.get("provider") == "xai" for event in _FakeRepo.events)


@pytest.mark.asyncio
async def test_planner_failure_does_not_persist_or_render(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    rendered = False

    async def planner(**_):
        raise TimeoutError("planner timeout")

    async def renderer(**_):
        nonlocal rendered
        rendered = True

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-timeout", source_text="x",
            source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, renderer_fn=renderer,
        )
    assert exc.value.code == "TOPOLOGY_PLANNER_FAILED"
    assert _FakeRepo.records == {}
    assert rendered is False


@pytest.mark.asyncio
async def test_default_topology_qc_rejects_unidentified_render_output(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)

    async def planner(**_):
        return {
            "version": "v1",
            "layout": "flow",
            "nodes": [{"id": "n1"}, {"id": "n2"}],
            "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
        }

    async def renderer(**_):
        return {}

    async def reader(**_):
        return b"internal-image"

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-qc",
            source_text="x", source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, reader_fn=reader, renderer_fn=renderer,
        )
    assert exc.value.code == "TOPOLOGY_QC_FAILED"
    assert _FakeRepo.records["r-qc"]["topology_sha256"]


@pytest.mark.asyncio
async def test_default_topology_qc_rejects_hash_only_render_output(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)

    async def planner(**_):
        return {
            "version": "v1",
            "layout": "flow",
            "nodes": [{"id": "n1"}, {"id": "n2"}],
            "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
        }

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return {"sha256": "audit-only"}

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-hash-only",
            source_text="x", source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, reader_fn=reader, renderer_fn=renderer,
        )
    assert exc.value.code == "TOPOLOGY_QC_FAILED"


@pytest.mark.asyncio
async def test_identity_mismatch_fails_closed_before_renderer(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _FakeRepo.records = {
        "r1": {"identity_digest": "old", "topology": {"nodes": []}, "topology_sha256": "x"}
    }
    _FakeRepo.events = []
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    rendered = False

    async def renderer(**_):
        nonlocal rendered
        rendered = True

    with pytest.raises(VisualTopologyConflict):
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r1", source_text="changed",
            source_digest="new", labels=[], internal_asset_key="k", renderer_fn=renderer,
        )
    assert rendered is False


@pytest.mark.asyncio
async def test_resumed_topology_is_revalidated_before_renderer(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _FakeRepo.records = {
        "r-corrupt": {
            "identity_digest": "placeholder",
            "topology": {
                "version": "v1",
                "layout": "flow",
                "nodes": [{"id": "n1"}, {"id": "n2"}],
                "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
                "labels": [{"id": "l9", "text_key": "l9"}],
            },
        }
    }
    _FakeRepo.events = []
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    rendered = False

    async def renderer(**_):
        nonlocal rendered
        rendered = True

    # Force the identity fence to match the stored record, so the test covers
    # the second validation pass rather than the earlier request fence.
    identity = topology_identity_digest(
        source_digest="src", labels=["Water"], label_map={"l0": "Water"},
        topology_schema_version="visual-topology/1", planner_version="v1",
    )
    _FakeRepo.records["r-corrupt"]["identity_digest"] = identity

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-corrupt",
            source_text="x", source_digest="src", labels=["Water"],
            label_map={"l0": "Water"}, internal_asset_key="k", renderer_fn=renderer,
        )
    assert exc.value.code == "TOPOLOGY_INVALID"
    assert rendered is False


@pytest.mark.asyncio
async def test_injected_qc_flag_never_completes_visual(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    completed = False

    async def planner(**_):
        return {
            "version": "v1",
            "layout": "flow",
            "nodes": [{"id": "n1"}, {"id": "n2"}],
            "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
        }

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return {"src": "/images/recovered.png", "sha256": "asset-hash"}

    async def qc(**_):
        return {"status": "flagged_quality", "reasons": ["bad geometry"]}

    async def completion(**_):
        nonlocal completed
        completed = True

    monkeypatch.setattr(_FakeRepo, "apply_visual_completion", completion)
    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-flag",
            source_text="x", source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=qc,
        )
    assert exc.value.code == "TOPOLOGY_QC_FLAGGED"
    assert completed is False


@pytest.mark.asyncio
async def test_injected_qc_malformed_verdict_fails_closed(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)

    async def planner(**_):
        return {
            "version": "v1",
            "layout": "flow",
            "nodes": [{"id": "n1"}, {"id": "n2"}],
            "edges": [{"id": "e1", "from_ref": "n1", "to_ref": "n2", "direction": "forward"}],
        }

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return {"src": "/images/recovered.png", "sha256": "asset-hash"}

    async def qc(**_):
        return None

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-qc-invalid",
            source_text="x", source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=qc,
        )
    assert exc.value.code == "TOPOLOGY_QC_FAILED"


@pytest.mark.asyncio
async def test_dispatch_routes_flagged_topology_without_visual_provider(monkeypatch):
    from planning.whole_lesson import visual_dispatch

    class Repo:
        def __init__(self, _session, _generation_id):
            pass

        async def load_page_generation_state(self):
            return {
                "block_execution": {
                    "explain:fig:everyone": {
                        "object": "figure",
                        "status": "failed_recoverable",
                        "request_id": "req-topology",
                        "block_id": "fig",
                        "visual_qc": {"status": "flagged_quality"},
                        "content": {
                            "asset": {
                                "status": "failed",
                                "request_id": "req-topology",
                                "internal_asset_key": "internal/asset.png",
                                "topology_recovery": True,
                            }
                        },
                    }
                },
                "teaching_plan": None,
                "lesson_packet": {
                    "lesson": {"objective": "Authoritative objective", "subject": "Science", "grade_level": "6"},
                    "scope": {"must_establish": [{"id": "must-1", "statement": "Water moves in a cycle"}], "terminology": ["cycle"]},
                    "anchor": {"id": "anchor-1", "description": "A puddle"},
                },
            }

        async def apply_visual_completion(self, **_):
            return {"document_revision": 2}

        async def persist_visual_dispatch_failure(self, **_):
            raise AssertionError("topology path must not persist provider failure")

        async def clear_visual_last_error(self):
            return None

    monkeypatch.setattr(visual_dispatch, "PageDocumentRepository", Repo)
    called = {"provider": 0, "recovery": 0}
    captured: dict[str, object] = {}

    async def provider(*_args, **_kwargs):
        called["provider"] += 1
        raise AssertionError("execute_visual/xAI must not run")

    async def recovery(**kwargs):
        called["recovery"] += 1
        assert kwargs["internal_asset_key"] == "internal/asset.png"
        captured["persisted_source"] = kwargs["persisted_source"]
        return {"status": "ready", "document_revision": 3}

    result = await visual_dispatch.dispatch_and_patch_from_repo(
        session=object(),
        generation_id="g1",
        execute_visual_fn=provider,
        topology_recovery_fn=recovery,
    )
    assert called == {"provider": 0, "recovery": 1}
    source = captured["persisted_source"]
    assert isinstance(source, dict)
    assert "teaching_block" in source
    assert source["lesson"]["objective"] == "Authoritative objective"
    assert source["scope"]["must_establish"][0]["statement"] == "Water moves in a cycle"
    assert source["anchor"]["description"] == "A puddle"
    assert result["topology_recovery"][0]["status"] == "ready"


@pytest.mark.asyncio
async def test_dispatch_filters_topology_block_when_request_id_is_asset_only(monkeypatch):
    from planning.whole_lesson import visual_dispatch

    class Repo:
        def __init__(self, _session, _generation_id):
            pass

        async def load_page_generation_state(self):
            return {
                "block_execution": {
                    "model:fig:everyone": {
                        "object": "figure",
                        "status": "failed_recoverable",
                        "block_id": "fig",
                        "visual_qc": {"status": "flagged_quality"},
                        "content": {
                            "asset": {
                                "status": "failed",
                                "request_id": "asset-only-request",
                                "internal_asset_key": "internal/asset.png",
                                "topology_recovery": True,
                            }
                        },
                    }
                },
                "teaching_plan": None,
                "lesson_packet": {"lesson": {"objective": "objective"}},
            }

        async def apply_visual_completion(self, **_):
            return {"document_revision": 2}

        async def persist_visual_dispatch_failure(self, **_):
            return None

        async def clear_visual_last_error(self):
            return None

    monkeypatch.setattr(visual_dispatch, "PageDocumentRepository", Repo)
    called = {"provider": 0, "recovery": 0}

    async def provider(*_args, **_kwargs):
        called["provider"] += 1
        raise AssertionError("provider must not run")

    async def recovery(**kwargs):
        called["recovery"] += 1
        assert kwargs["request_id"] == "asset-only-request"
        return {"status": "awaiting_visuals", "request_id": kwargs["request_id"]}

    result = await visual_dispatch.dispatch_and_patch_from_repo(
        session=object(), generation_id="g1", execute_visual_fn=provider,
        topology_recovery_fn=recovery,
    )
    assert called == {"provider": 0, "recovery": 1}
    assert result["topology_recovery"][0]["status"] == "awaiting_visuals"


@pytest.mark.asyncio
async def test_final_raster_bytes_are_qc_reviewed_before_upload(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    store = _FakeStore()
    raster = b"final-topology-png-bytes"
    seen: dict[str, object] = {}

    async def planner(**_):
        return _valid_topology()

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return SimpleNamespace(
            png_bytes=raster,
            metadata=SimpleNamespace(
                final_sha256="final-hash",
                renderer_version="topology-renderer/1",
                background_version="topology-background/1",
            ),
        )

    async def qc(**kwargs):
        seen["image_bytes"] = kwargs.get("image_bytes")
        seen["uploads_at_qc"] = list(store.uploads)
        return {"status": "accept", "reasons": [], "correction_hint": "ok"}

    result = await recover_flagged_visual_topology(
        session=object(), generation_id="g1", request_id="r-raster",
        source_text="x", source_digest="src", labels=[], internal_asset_key="k",
        planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=qc,
        image_store=store,
    )
    assert seen["image_bytes"] == raster
    assert seen["uploads_at_qc"] == []
    assert len(store.uploads) == 1
    assert store.uploads[0]["image_bytes"] == raster
    assert result["asset"]["src"] == "/images/r-raster.png"
    assert len(_FakeRepo.completions) == 1
    assert _FakeRepo.completions[0]["asset"]["src"] == "/images/r-raster.png"
    assert _FakeRepo.completions[0]["visual_qc"]["status"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", ["flag", "reject", "flagged_quality"])
async def test_qc_flag_or_reject_never_uploads_or_completes(monkeypatch, verdict):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    store = _FakeStore()

    async def planner(**_):
        return _valid_topology()

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return SimpleNamespace(
            png_bytes=b"png",
            metadata=SimpleNamespace(final_sha256="h", renderer_version="r", background_version="b"),
        )

    async def qc(**_):
        return {"status": verdict, "reasons": ["bad labels"]}

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-flag-bytes",
            source_text="x", source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=qc,
            image_store=store,
        )
    assert exc.value.code == "TOPOLOGY_QC_FLAGGED"
    assert store.uploads == []
    assert _FakeRepo.completions == []


@pytest.mark.asyncio
async def test_qc_error_and_malformed_verdict_fail_closed_before_upload(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    _reset_repo()
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    store = _FakeStore()

    async def planner(**_):
        return _valid_topology()

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return SimpleNamespace(
            png_bytes=b"png",
            metadata=SimpleNamespace(final_sha256="h", renderer_version="r", background_version="b"),
        )

    async def boom(**_):
        raise RuntimeError("qc unavailable")

    with pytest.raises(TopologyRecoveryError) as exc:
        await recover_flagged_visual_topology(
            session=object(), generation_id="g1", request_id="r-qc-err",
            source_text="x", source_digest="src", labels=[], internal_asset_key="k",
            planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=boom,
            image_store=store,
        )
    assert exc.value.code == "TOPOLOGY_QC_FAILED"
    assert store.uploads == []
    assert _FakeRepo.completions == []


@pytest.mark.asyncio
async def test_resumed_topology_is_revalidated_and_qc_reviewed(monkeypatch):
    from planning.whole_lesson import visual_topology_recovery as mod

    identity = topology_identity_digest(
        source_digest="src", labels=[],
        topology_schema_version="visual-topology/1", planner_version="v1",
    )
    _FakeRepo.records = {
        "r-resume": {
            "identity_digest": identity,
            "topology": _valid_topology(),
        }
    }
    _FakeRepo.events = []
    _FakeRepo.completions = []
    monkeypatch.setattr(mod, "PageDocumentRepository", _FakeRepo)
    qc_calls = {"n": 0}

    async def planner(**_):
        raise AssertionError("planner must not rerun for resumed topology")

    async def reader(**_):
        return b"internal-image"

    async def renderer(**_):
        return {"src": "/images/resumed.png", "sha256": "asset-hash"}

    async def qc(**_):
        qc_calls["n"] += 1
        return {"status": "accept"}

    result = await recover_flagged_visual_topology(
        session=object(), generation_id="g1", request_id="r-resume",
        source_text="x", source_digest="src", labels=[],
        internal_asset_key="k",
        planner_fn=planner, reader_fn=reader, renderer_fn=renderer, qc_fn=qc,
    )
    assert result["reused"] is True
    assert qc_calls["n"] == 1
    assert result["status"] == "ready"


@pytest.mark.asyncio
async def test_dispatch_injects_qc_adapter_and_returns_awaiting_visuals_on_flag(monkeypatch):
    from planning.whole_lesson import visual_dispatch
    from planning.whole_lesson.visual_topology_recovery import TopologyRecoveryError

    class Repo:
        def __init__(self, _session, _generation_id):
            pass

        async def load_page_generation_state(self):
            return {
                "block_execution": {
                    "explain:fig:everyone": {
                        "object": "figure",
                        "status": "failed_recoverable",
                        "request_id": "req-topology",
                        "block_id": "fig",
                        "visual_qc": {"status": "flagged_quality", "reasons": ["faint label"]},
                        "content": {
                            "asset": {
                                "status": "failed",
                                "request_id": "req-topology",
                                "internal_asset_key": "internal/asset.png",
                                "topology_recovery": True,
                            }
                        },
                    }
                },
                "teaching_plan": None,
                "lesson_packet": {"lesson": {"objective": "objective"}},
            }

        async def apply_visual_completion(self, **_):
            raise AssertionError("flagged topology QC must not complete")

        async def persist_visual_dispatch_failure(self, **_):
            return None

        async def clear_visual_last_error(self):
            return None

    captured: dict[str, object] = {}

    async def recover(**kwargs):
        captured.update(kwargs)
        raise TopologyRecoveryError("TOPOLOGY_QC_FLAGGED", "flagged")

    monkeypatch.setattr(visual_dispatch, "PageDocumentRepository", Repo)
    monkeypatch.setattr(visual_dispatch.topology_recovery, "recover_flagged_visual_topology", recover)

    async def provider(*_args, **_kwargs):
        raise AssertionError("execute_visual/xAI must not run")

    result = await visual_dispatch.dispatch_and_patch_from_repo(
        session=object(),
        generation_id="g1",
        execute_visual_fn=provider,
    )
    assert captured.get("qc_fn") is not None
    assert captured.get("work_order") is not None
    assert result["topology_recovery"][0]["status"] == "awaiting_visuals"
    assert result["failed"] == 1
