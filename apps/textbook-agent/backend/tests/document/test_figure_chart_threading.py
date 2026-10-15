"""A backbone figure's `chart` declaration is copied by code to the media visual."""

from __future__ import annotations

from curriculum.backbone.models import BackboneFigure
from tests.curriculum.test_backbone_figure_chart import OAKFIELD
from tests.document.test_figure_data_routing import FIG2, _lesson_1_work_order


def test_chart_reaches_the_media_visual() -> None:
    work = _lesson_1_work_order(OAKFIELD, visual_mode="diagram")
    visual = work.work_order.visual
    expected = BackboneFigure.model_validate(OAKFIELD).chart_dict()
    assert expected is not None
    assert visual.chart == expected
    assert visual.chart["kind"] == "combo"
    assert visual.chart["bars"] == {
        "key": "rainfall_mm",
        "label": "Rainfall (mm)",
        "min": 0.0,
        "max": 20.0,
    }
    assert visual.data == OAKFIELD["data"]


def test_figure_without_chart_has_no_chart_on_the_visual() -> None:
    work = _lesson_1_work_order(FIG2, visual_mode="diagram")
    assert work.work_order.visual.chart is None
    assert "chart" not in work.work_order.visual.model_dump()
