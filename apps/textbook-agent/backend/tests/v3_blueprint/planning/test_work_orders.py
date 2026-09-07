"""Phase 04: exact work orders + Lectio contract matrix."""

from __future__ import annotations

import pytest

from contracts.lectio import get_component_card
from v3_blueprint.planning.canonical_plan import build_canonical_execution_plan
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from v3_blueprint.planning.work_orders import (
    PROMPT_INVENTORY,
    assert_writer_cannot_change_component,
    build_component_contract_matrix,
    compile_exact_work_orders,
)
from tests.v3_blueprint.planning.test_intent_plan import SUBJECT_FIXTURES, _intent_plan_for_subject


def test_component_contract_matrix_covers_planner_selectable() -> None:
    matrix = build_component_contract_matrix()
    assert len(matrix) >= 20
    by_id = {row["component_id"]: row for row in matrix}
    assert "comparison-grid" in by_id
    assert by_id["comparison-grid"]["has_field_contracts"] or by_id["comparison-grid"]["section_field"]
    assert by_id["diagram-block"]["writer_excluded"] is True
    assert by_id["diagram-block"]["generatable"] is False
    assert by_id["explanation-block"]["generatable"] is True


def test_exact_work_orders_from_canonical_plan() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    canonical, _ = build_canonical_execution_plan(plan, generation_id="gen-wo")
    orders = compile_exact_work_orders(canonical)
    assert orders
    for order in orders:
        assert order.locked_component_id == order.component_id
        assert order.plan_hash == canonical.plan_hash
        assert order.component_card["component_id"] == order.component_id
        assert "field_contracts" in order.component_card
        # No sibling components on the order.
        assert order.component_id in {b.component_id for b in canonical.blocks}


def test_writer_cannot_change_component_id() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[1])
    plan = intent_plan_to_structural_plan(intent)
    canonical, _ = build_canonical_execution_plan(plan, generation_id="gen-lock")
    order = compile_exact_work_orders(canonical)[0]
    assert_writer_cannot_change_component(order, order.component_id)
    with pytest.raises(ValueError, match="attempted to change component_id"):
        assert_writer_cannot_change_component(order, "explanation-block")


def test_malformed_comparison_grid_fails_validation() -> None:
    from v3_execution.runtime.lectio_validation import validate_lectio_field_payload

    card = get_component_card("comparison-grid")
    assert card is not None
    _payload, errors = validate_lectio_field_payload(
        "comparison_grid",
        {"not_a_real_field": True},
    )
    assert errors, "malformed comparison_grid must produce validation errors"


def test_prompt_inventory_lists_stage1_modified() -> None:
    actions = {row["prompt"]: row["action"] for row in PROMPT_INVENTORY}
    assert actions["structural-planner.md"] == "modified"
    assert actions["component-selector-v1.txt"] == "keep"
