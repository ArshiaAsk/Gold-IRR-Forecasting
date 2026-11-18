"""
Streamlit smoke tests: the app runs, all four tabs render their key content,
the demo reacts to the date selector, and missing artifacts produce a message.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "streamlit_app.py"

TEXT_ATTRS = (
    "title", "header", "subheader", "markdown", "caption",
    "info", "warning", "error", "success", "text",
)


def all_text(at: AppTest) -> str:
    parts = []
    for attr in TEXT_ATTRS:
        for element in getattr(at, attr, []):
            value = getattr(element, "value", "")
            if isinstance(value, str):
                parts.append(value)
    for element in at.metric:
        parts.append(f"{element.label} {element.value}")
    return "\n".join(parts)


@pytest.fixture(scope="module")
def at() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=180).run()


def test_app_runs_without_exception(at):
    assert not at.exception, [e.value for e in at.exception]


def test_four_tabs(at):
    assert [t.label for t in at.tabs] == ["Findings", "Data", "Model demo", "About"]


def test_findings_tab_reads_results(at):
    text = all_text(at)
    assert "Hold-out (V2)" in text
    assert "Sensitivity: V1 / V2 / V3" in text
    assert "Legacy features vs stationary features" in text
    assert "Economic reality: long/flat strategies" in text
    assert "no demonstrated edge" in text.lower()


def test_data_tab(at):
    text = all_text(at)
    assert "Devaluation note" in text
    assert "Most of the rial gain is the rial" in text
    assert "not redistributed" in text
    assert "USD/IRR" in text


def test_model_demo_tab(at):
    text = all_text(at)
    assert "Model prediction" in text
    assert "Persistence" in text
    assert "No demonstrated predictive edge" in text
    assert len(at.metric) >= 3


def test_about_tab(at):
    text = all_text(at)
    assert "Units." in text
    assert "TGJU" in text
    assert "docs/SERVING_DESIGN.md" in text


def test_demo_reacts_to_date_selector():
    at = AppTest.from_file(str(APP_PATH), default_timeout=180).run()
    selector = at.selectbox[0]
    assert len(selector.options) > 20
    selector.select(selector.options[10]).run()
    assert not at.exception, [e.value for e in at.exception]
    realized = [m for m in at.metric if m.label.startswith("Realized")]
    assert realized and realized[0].value != "n/a"


def test_missing_artifacts_give_a_message(tmp_path):
    import streamlit_app as app_module

    bundle, error = app_module.get_bundle(str(tmp_path))
    assert bundle is None
    assert "Model artifacts are missing" in error
    assert str(tmp_path) in error
