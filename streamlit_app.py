"""
Streamlit demo for the honest gold-in-IRR model.

Four tabs, all offline:

* **Findings** — every number is read from ``results/*.json``.
* **Data** — the bundled 200-row sample only.
* **Model demo** — one sample date, through the same feature function the
  model was trained and evaluated with.
* **About** — units, data-source caveat, docs.

There is no API call and no network access. The model has no demonstrated
predictive edge (docs/RESULTS.md); the UI says so instead of hiding it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.predictor import ArtifactMissing, load_bundle  # noqa: E402
from src.feature_eng import MIN_HISTORY_ROWS, prepare_model_input  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results"
SAMPLE_PATH = PROJECT_ROOT / "data" / "sample" / "gold_sample.csv"
GRAMS_PER_OUNCE = 31.1034768

st.set_page_config(
    page_title="Gold in IRR — honest next-day model",
    page_icon="·",
    layout="wide",
)

CAVEAT = (
    "This model has **no demonstrated predictive edge**. Its log-return accuracy "
    "is indistinguishable from a zero-return benchmark, and the economic test "
    "finds no value over buy-and-hold. The demo exists to show the pipeline, "
    "not to forecast. See `docs/RESULTS.md`."
)


# --- Cached loaders ---------------------------------------------------------


@st.cache_resource
def get_bundle(models_dir: str | None = None):
    """Load the model, scalers and metadata once. Returns (bundle, error)."""
    try:
        return (load_bundle(Path(models_dir)) if models_dir else load_bundle()), None
    except ArtifactMissing as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 - surface any load failure as text
        return None, f"Could not load the model: {exc}"


@st.cache_data
def read_json(path: str):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def read_sample(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date")
    return df.reset_index(drop=True)


# --- Helpers ----------------------------------------------------------------


def _pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _require(path: Path, label: str):
    data = read_json(str(path))
    if data is None:
        st.warning(f"{label} is missing (`{path.relative_to(PROJECT_ROOT)}`). "
                   "The Findings tab needs the committed result files.")
    return data


def _metrics_table(block: dict, title: str) -> None:
    if not block:
        return
    st.markdown(f"**{title}**")
    df = pd.DataFrame(block).T
    cols = [c for c in ["n", "rmse", "mae", "r2_zero", "dir_acc",
                        "dm_p_one_sided", "boot_r2_lo", "boot_r2_hi",
                        "std_pred", "std_actual", "corr"] if c in df.columns]
    st.dataframe(df[cols].astype(float).round(6))
    st.caption(
        "`r2_zero` is measured against a zero-return benchmark; `dir_acc` is "
        "directional accuracy; `dm_p_one_sided` is the Diebold–Mariano p-value "
        "against persistence. Undefined values are blank."
    )


# --- Tab 1: Findings --------------------------------------------------------


def tab_findings() -> None:
    st.header("Findings")
    st.markdown(CAVEAT)

    v2 = _require(RESULTS_DIR / "eval_V2.json", "`results/eval_V2.json`")
    v1 = _require(RESULTS_DIR / "eval_V1.json", "`results/eval_V1.json`")
    v3 = _require(RESULTS_DIR / "eval_V3.json", "`results/eval_V3.json`")
    bt = _require(RESULTS_DIR / "backtest.json", "`results/backtest.json`")

    if v2:
        verdict = (v2.get("edge_verdict") or {}).get("finding")
        st.subheader("Headline: walk-forward and hold-out")
        if verdict:
            st.info(f"Pre-registered verdict: **{verdict}**.")
        _metrics_table(v2.get("walkforward", {}), "Walk-forward (pooled folds)")
        _metrics_table(v2.get("holdout", {}), "Hold-out (scored once)")

    st.subheader("Sensitivity: V1 / V2 / V3")
    rows = []
    for name, payload in (("V1", v1), ("V2", v2), ("V3", v3)):
        if not payload:
            continue
        lstm = (payload.get("holdout") or {}).get("lstm_stationary")
        if not lstm:
            continue
        rows.append({
            "variant": name,
            "holdout_n": lstm.get("n"),
            "rmse": lstm.get("rmse"),
            "r2_zero": lstm.get("r2_zero"),
            "dir_acc": lstm.get("dir_acc"),
            "dm_p_one_sided": lstm.get("dm_p_one_sided"),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows).set_index("variant").astype(float).round(6))
        st.caption(
            "V1 keeps the raw dates, V2 relabels the 2023-10 → 2025-08 block, "
            "V3 excludes it. The verdict is the same in all three."
        )

    st.subheader("Legacy features vs stationary features")
    if v2:
        hold = v2.get("holdout", {})
        pair = {k: hold[k] for k in ("lstm_legacy", "lstm_stationary") if k in hold}
        _metrics_table(pair, "Hold-out, same rows, same architecture")
        st.caption(
            "`lstm_legacy` uses the old 15 raw-level features (absolute prices, "
            "MACD in Rial); `lstm_stationary` uses the frozen dimensionless set."
        )

    st.subheader("Economic reality: long/flat strategies")
    if bt:
        strategies = bt.get("strategies", {})
        costs = bt.get("metadata", {}).get("costs", {})
        table = {}
        for scenario, by_strategy in strategies.items():
            table[scenario] = {
                name: metrics.get("total_return")
                for name, metrics in by_strategy.items()
            }
        if table:
            df = pd.DataFrame(table).T
            df.index = [f"{i} ({costs.get(i, 0) * 100:.2f}%/side)" for i in df.index]
            st.dataframe((df * 100).round(2).rename_axis("cost scenario"))
            st.caption("Total return in percent over the hold-out. "
                       "S0 = buy and hold, S1 = always long after one entry, "
                       "S2 = long when the model predicts up, S3 = long/short.")
        economic_verdict = bt.get("verdict", {})
        if economic_verdict.get("finding"):
            st.info(f"Pre-registered verdict: **{economic_verdict['finding']}**.")
        gold_usd = bt.get("gold_in_usd", {})
        nominal = strategies.get("C0", {}).get("S0", {}).get("total_return")
        if nominal is not None and gold_usd.get("total_return") is not None:
            st.markdown(
                f"Over the traded period, nominal gold in IRR returned "
                f"**{_pct(nominal)}** while gold in USD returned "
                f"**{_pct(gold_usd['total_return'])}**. The gap is the rial, "
                "not the gold."
            )


# --- Tab 2: Data ------------------------------------------------------------


def tab_data() -> None:
    st.header("Data")
    if not SAMPLE_PATH.exists():
        st.error(f"The bundled sample is missing (`{SAMPLE_PATH.relative_to(PROJECT_ROOT)}`).")
        return

    df = read_sample(str(SAMPLE_PATH))
    st.markdown(
        f"The repository bundles the **last {len(df)} rows** of the merged dataset "
        f"({df['Date'].min().date()} → {df['Date'].max().date()}). The full series is "
        "not redistributed (decision D14)."
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Gold_IRR"], name="Gold, Rial/g"))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["USD_IRR"], name="USD/IRR"))
    fig.update_layout(
        title="Gold per gram and USD/IRR (Rial, log scale)",
        yaxis_type="log", yaxis_title="Rial", xaxis_title="Date",
        height=380, margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    usd = df.copy()
    usd["gold_usd_per_g"] = usd["Gold_IRR"] / usd["USD_IRR"]
    usd["ounce_usd_per_g"] = usd["Ounce_USD"] / GRAMS_PER_OUNCE
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=usd["Date"], y=usd["gold_usd_per_g"],
                              name="Domestic gold / USD rate (USD/g)"))
    fig2.add_trace(go.Scatter(x=usd["Date"], y=usd["ounce_usd_per_g"],
                              name="Global ounce / 31.1035 (USD/g)"))
    fig2.update_layout(
        title="Gold in USD: domestic-implied vs global",
        yaxis_title="USD per gram", xaxis_title="Date",
        height=380, margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig2, use_container_width=True)

    first, last = df.iloc[0], df.iloc[-1]
    st.subheader("Devaluation note")
    st.markdown(
        f"Over the sample, gold in Rial moved {_pct(last['Gold_IRR'] / first['Gold_IRR'] - 1)} "
        f"and USD/IRR moved {_pct(last['USD_IRR'] / first['USD_IRR'] - 1)}. "
        f"In USD the same gold moved "
        f"{_pct((last['Gold_IRR'] / last['USD_IRR']) / (first['Gold_IRR'] / first['USD_IRR']) - 1)}. "
        "Most of the rial gain is the rial, not the metal — which is why the "
        "economic section reports gold in USD as well."
    )
    st.caption(
        "Numbers above are computed from the bundled sample, not from the "
        "backtest period, and will differ from `results/backtest.json`."
    )


# --- Tab 3: Model demo ------------------------------------------------------


def tab_demo() -> None:
    st.header("Model demo")
    st.warning(
        "**No demonstrated predictive edge.** The numbers below are a pipeline "
        "demonstration, not a forecast."
    )

    bundle, error = get_bundle()
    if bundle is None:
        st.warning(
            "Model artifacts are missing, so the demo cannot run.\n\n"
            f"`{error}`\n\n"
            "Expected `models/gold_lstm_stationary_v2.keras` and its two scalers."
        )
        return
    if not SAMPLE_PATH.exists():
        st.warning("The bundled sample is missing, so there is no history to run.")
        return

    df = read_sample(str(SAMPLE_PATH))
    if len(df) < MIN_HISTORY_ROWS:
        st.warning(
            f"The sample has {len(df)} rows; the model needs at least "
            f"{MIN_HISTORY_ROWS}."
        )
        return

    eligible = df["Date"].iloc[MIN_HISTORY_ROWS - 1:]
    chosen = st.selectbox(
        "Prediction date (the last row of the input window)",
        options=list(eligible.dt.date),
        index=len(eligible) - 1,
    )
    position = int(df.index[df["Date"].dt.date == chosen][0])
    history = df.iloc[: position + 1]

    try:
        model_input = prepare_model_input(history, seq_len=bundle.sequence_length)
        log_return = bundle.predict_log_return(model_input.X)
    except Exception as exc:  # noqa: BLE001 - show the reason, not a stack trace
        st.error(f"Prediction failed: {exc}")
        return

    realized = None
    if position + 1 < len(df):
        realized = float(
            np.log(df["Gold_IRR"].iloc[position + 1] / df["Gold_IRR"].iloc[position])
        )

    last_close = float(df["Gold_IRR"].iloc[position])
    st.markdown(
        f"Input: **{model_input.n_rows_input} rows**, "
        f"{model_input.n_feature_rows} usable feature rows, window "
        f"{model_input.feature_frame.index[0].date()} → "
        f"{model_input.feature_frame.index[-1].date()}."
    )

    cols = st.columns(3)
    cols[0].metric("Model prediction", _pct(np.expm1(log_return)),
                   help="Next-trading-day log return, inverse-transformed with scaler_y.")
    cols[1].metric("Persistence", _pct(0.0),
                   help="The zero-return benchmark the model must beat.")
    if realized is not None:
        cols[2].metric("Realized (next row in sample)", _pct(np.expm1(realized)))
    else:
        cols[2].metric("Realized", "n/a", help="No next row in the sample.")

    table = pd.DataFrame({
        "strategy": ["Model", "Persistence"] + (["Realized"] if realized is not None else []),
        "log_return": [log_return, 0.0] + ([realized] if realized is not None else []),
    })
    table["simple_return_%"] = (np.expm1(table["log_return"]) * 100).round(4)
    table["implied_price_irr"] = (last_close * np.exp(table["log_return"])).round(0)
    st.dataframe(table, hide_index=True)
    st.caption(
        "The implied price is persistence-equivalent: the model's prediction is "
        "near-constant, so it barely moves the last close. It is not a forecast."
    )

    st.markdown(
        f"Last close: **{last_close:,.0f} Rial/g**. "
        f"Model `{bundle.model_id}`, variant `{bundle.metadata['variant']}`, "
        f"seed `{bundle.metadata['seed']}`, trained "
        f"{bundle.metadata['training_window'][0]} → "
        f"{bundle.metadata['training_window'][1]}."
    )


# --- Tab 4: About -----------------------------------------------------------


def tab_about() -> None:
    st.header("About")
    st.markdown(
        """
**Units.** Prices are in **Rial (IRR)**, not Toman: `Gold_IRR` is 18-karat gold
per gram (`geram18`), `USD_IRR` is Rial per US dollar, `Ounce_USD` is the global
gold ounce in dollars, `Oil_USD` is Brent in dollars. One billion Rial is about
555 US dollars at the sample's exchange rate.

**Data source.** The Iranian series come from TGJU. Redistribution permission
is **pending**, so only a 200-row sample is bundled and the full series is not in
the repository (decision D14). The sample does not overlap the mis-dated block
that the loader corrects.

**What this is.** A negative result, served honestly: one feature function shared
by training, evaluation and serving; no confidence interval; no price headline;
no trading signal.
"""
    )
    bundle, error = get_bundle()
    if bundle is None:
        st.warning(f"Model artifacts are missing: {error}")
    else:
        st.subheader("Served artifact")
        meta = bundle.metadata
        values = [
            meta.get("artifact"), meta.get("variant"), meta.get("feature_spec"),
            meta.get("sequence_length"), len(meta.get("feature_columns", [])),
            meta.get("seed"), meta.get("architecture"), meta.get("git_commit"),
            " → ".join(meta.get("training_window", [])),
            " → ".join(meta.get("validation_window", [])),
            " → ".join(meta.get("holdout_window", [])),
        ]
        st.dataframe(pd.DataFrame({
            "field": ["artifact", "variant", "feature_spec", "sequence_length",
                      "n_features", "seed", "architecture", "git_commit",
                      "training_window", "validation_window", "holdout_window"],
            "value": ["" if v is None else str(v) for v in values],
        }), hide_index=True)

    st.subheader("Documents")
    st.markdown(
        """
| Path | Contents |
|---|---|
| `docs/RESULTS.md` | Stage 3 and 4 results, plain-language reading |
| `docs/EVAL_PROTOCOL.md` | Pre-registered evaluation protocol |
| `docs/BACKTEST_PROTOCOL.md` | Pre-registered economic protocol |
| `docs/DATA_INTEGRITY.md` | Data audit, the mis-dated block, units |
| `docs/SERVING_DESIGN.md` | This service's contract |
| `docs/DECISIONS.md` | D1–D28 and the gates |
"""
    )


# --- Main -------------------------------------------------------------------


def main() -> None:
    st.title("Gold in IRR — honest next-day model")
    tabs = st.tabs(["Findings", "Data", "Model demo", "About"])
    with tabs[0]:
        tab_findings()
    with tabs[1]:
        tab_data()
    with tabs[2]:
        tab_demo()
    with tabs[3]:
        tab_about()


if __name__ == "__main__":
    main()
