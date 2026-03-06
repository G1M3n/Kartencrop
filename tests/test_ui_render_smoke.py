from pathlib import Path
from types import SimpleNamespace

from kartencrop.tiles import Bounds
from kartencrop.ui_models import OfmUIConfig
from kartencrop.ui_render import render_summary
from kartencrop.ui_shared import SOURCE_OFM


def test_render_summary_runs_without_name_error(monkeypatch) -> None:
    calls: dict[str, list[str]] = {"warning": []}

    fake_st = SimpleNamespace(
        session_state=SimpleNamespace(output_directory="C:/tmp"),
        subheader=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
        code=lambda *args, **kwargs: None,
        warning=lambda message: calls["warning"].append(message),
    )

    import kartencrop.ui_render as ui_render
    import kartencrop.ui_shared as ui_shared

    monkeypatch.setattr(ui_render, "st", fake_st)
    monkeypatch.setattr(ui_shared, "st", fake_st)

    render_summary(
        OfmUIConfig(
            source=SOURCE_OFM,
            zoom=8,
            cycle="latest",
            render_mode="single",
            chart_type="aero",
            start_x=0,
            start_y=0,
            coverage_search=0,
            radius=0,
            area_strategy="bounds",
            use_detected_range=False,
            bounds=Bounds(min_x=0, max_x=10, min_y=0, max_y=10),
            summary=["Test"],
        ),
        Path("output.png"),
    )

    assert calls["warning"]
