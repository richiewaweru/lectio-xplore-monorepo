"""Visual QC summary projected from the persisted Print page-document state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from media.qc.visual_qc import visual_qc_enabled


def visual_quality_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    """Expose the persisted visual QC markers needed by native viewers/retry UI."""
    raw = state.get("page_document_v2")
    page = dict(raw) if isinstance(raw, Mapping) else {}
    block_execution = page.get("block_execution")
    flagged: list[dict[str, Any]] = []
    failed: list[str] = []
    figure_count = 0
    reviewed_count = 0
    if isinstance(block_execution, Mapping):
        for outcome in block_execution.values():
            if not isinstance(outcome, Mapping) or str(outcome.get("object") or "") != "figure":
                continue
            figure_count += 1
            request_id = str(outcome.get("request_id") or "")
            content = outcome.get("content") if isinstance(outcome.get("content"), Mapping) else {}
            asset = content.get("asset") if isinstance(content, Mapping) and isinstance(content.get("asset"), Mapping) else {}
            asset_status = str(asset.get("status") or "")
            error = outcome.get("error")
            visual_error = isinstance(error, Mapping) and str(error.get("code") or "") in {
                "VISUAL_DISPATCH",
                "VISUAL_COMPLETION",
            }
            if (
                asset_status == "failed"
                or str(outcome.get("status") or "") in {"failed", "failed_recoverable"}
                or visual_error
            ) and request_id:
                failed.append(request_id)
            qc = outcome.get("visual_qc")
            if not isinstance(qc, Mapping):
                # Older successful completions archived the active QC verdict
                # instead of retaining it. Treat an archived flagged verdict
                # as unresolved until a later accepted verdict is persisted.
                history = outcome.get("visual_qc_history")
                if isinstance(history, list):
                    for candidate in reversed(history):
                        if isinstance(candidate, Mapping):
                            qc = candidate
                            break
            if isinstance(qc, Mapping) and str(qc.get("status") or "").strip():
                reviewed_count += 1
            if isinstance(qc, Mapping) and str(qc.get("status") or "") == "flagged_quality":
                flagged.append(
                    {
                        "request_id": request_id,
                        "block_id": str(outcome.get("block_id") or "") or None,
                        "status": "flagged_quality",
                        "asset_status": asset_status or str(outcome.get("status") or ""),
                        "reasons": [str(item) for item in (qc.get("reasons") or []) if str(item).strip()],
                        "correction_hint": str(qc.get("correction_hint") or "") or None,
                    }
                )
    # "ready" is a claim that quality review ran and passed. With figures
    # present but QC disabled or no verdict persisted, say so honestly.
    reviewed = visual_qc_enabled() and reviewed_count > 0
    if flagged:
        status = "ready_with_quality_warning"
    elif failed:
        status = "failed"
    elif figure_count and not reviewed:
        status = "unreviewed"
    else:
        status = "ready"
    return {
        "status": status,
        "unreviewed_count": max(figure_count - reviewed_count, 0) if figure_count else 0,
        "flagged": flagged,
        "flagged_count": len(flagged),
        "failed_request_ids": sorted(set(failed)),
        "retryable": bool(flagged or failed),
    }


__all__ = ["visual_quality_summary"]
