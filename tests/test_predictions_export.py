"""The opt-in per-row predictions export."""
import pandas as pd

from src.evaluate import _write_predictions


def test_write_predictions_layout(tmp_path):
    idx = pd.to_datetime(["2026-01-05", "2026-01-06"])
    y_true = pd.Series([0.01, -0.02], index=idx)
    predictions = {
        "persistence": pd.Series([0.0, 0.0], index=idx),
        "lstm_stationary": pd.Series([0.001, -0.003], index=idx),
    }

    out = tmp_path / "predictions"
    _write_predictions(str(out), "V2", "holdout", predictions, y_true)

    path = out / "V2_holdout.csv"
    assert path.is_file()
    frame = pd.read_csv(path)
    assert list(frame.columns) == [
        "variant", "sample", "model", "date", "y_true", "y_pred",
    ]
    assert len(frame) == 4
    assert set(frame["model"]) == {"persistence", "lstm_stationary"}
    assert frame.loc[frame["model"] == "lstm_stationary", "y_pred"].tolist() == [0.001, -0.003]
    assert frame["y_true"].tolist()[:2] == [0.01, -0.02]


def test_write_predictions_skips_empty(tmp_path):
    _write_predictions(str(tmp_path), "V2", "holdout",
                       {"empty": pd.Series(dtype=float)}, pd.Series(dtype=float))
    assert not (tmp_path / "V2_holdout.csv").exists()
