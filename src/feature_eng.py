import pandas as pd
import numpy as np
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Sequence

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import config
from src.utils import logger

# Frozen Stage 3 feature set (docs/EVAL_PROTOCOL.md §3). Every entry is
# stationary or dimensionless; no raw price level is present.
STATIONARY_FEATURE_COLUMNS = [
    'gold_ret_lag1', 'gold_ret_lag2', 'gold_ret_lag3', 'gold_ret_lag5',
    'usd_ret_lag0', 'usd_ret_lag1', 'usd_ret_lag2', 'usd_ret_lag5',
    'ounce_ret_lag1', 'ounce_ret_lag2', 'ounce_ret_lag5',
    'oil_ret_lag1', 'oil_ret_lag5',
    'rsi_14', 'macd_norm', 'macd_signal_norm',
    'bb_pctb_20', 'bb_bandwidth_20',
    'price_sma_7', 'price_sma_20', 'price_sma_60',
    'rv_5', 'rv_20',
]

# --- Serving contract (docs/SERVING_DESIGN.md) -------------------------------
# The model consumes 30 consecutive feature rows (metadata `sequence_length`).
SERVING_SEQUENCE_LENGTH = 30
# Longest lookback in STATIONARY_FEATURE_COLUMNS: price_sma_60. Row 59 is the
# first row with a complete 60-row window, so the first feature row is index 59.
LONGEST_WINDOW_ROWS = 60
MIN_HISTORY_ROWS = (LONGEST_WINDOW_ROWS - 1) + SERVING_SEQUENCE_LENGTH  # 89
MAX_HISTORY_ROWS = 5000
# |ln(p_t / p_t-1)| above this is a unit/row error, not a return. Observed
# maximum in the bundled sample and the local full series is 0.1777.
MAX_ABS_LOG_JUMP = 0.5

RAW_PRICE_COLUMNS = ['Gold_IRR', 'USD_IRR', 'Ounce_USD', 'Oil_USD']


class InputError(ValueError):
    """A rejected serving input. ``code`` is stable and documented."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ModelInput:
    """The result of turning raw daily rows into one model input window."""

    X: np.ndarray                 # (SERVING_SEQUENCE_LENGTH, n_features)
    feature_frame: pd.DataFrame   # the same rows, indexed by date
    last_date: pd.Timestamp
    last_close: float
    n_rows_input: int
    n_feature_rows: int
    n_rows_dropped: int
    feature_columns: List[str]


def _as_frame(rows) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame(list(rows))


def _frame_dates(df: pd.DataFrame) -> pd.Series:
    if 'Date' in df.columns:
        raw = df['Date']
    elif 'date' in df.columns:
        raw = df['date']
    elif isinstance(df.index, pd.DatetimeIndex):
        raw = pd.Series(df.index, index=df.index)
    else:
        raise InputError('missing_column', "input needs a 'Date' column or a DatetimeIndex")
    try:
        return pd.to_datetime(raw)
    except (ValueError, TypeError) as exc:
        raise InputError('invalid_date', f"unparseable date: {exc}") from exc


def prepare_model_input(
    rows,
    seq_len: int = SERVING_SEQUENCE_LENGTH,
    min_rows: int = MIN_HISTORY_ROWS,
    max_rows: int = MAX_HISTORY_ROWS,
    max_jump: float = MAX_ABS_LOG_JUMP,
    reject_block: bool = True,
) -> ModelInput:
    """
    Turn raw daily rows into the model's (seq_len, 23) input window.

    This is the thin serving adapter. It validates the raw-row contract, then
    calls :func:`add_stationary_features` — the same function training and
    evaluation use — so no feature can be computed differently in serving.
    It is causal: the output depends only on the supplied rows and never on a
    row after the last one.

    Args:
        rows: DataFrame (or iterable of dicts) with a date and the four raw
            price columns, one row per trading day.
        seq_len: Model sequence length (from the artifact metadata).
        min_rows: Minimum input rows (derived: 89).
        max_rows: Maximum input rows.
        max_jump: Reject |log change| above this.
        reject_block: Reject rows in the TGJU mis-dated block (see design §2.2).

    Raises:
        InputError: with a documented ``code``; see docs/SERVING_DESIGN.md §2.
    """
    df = _as_frame(rows)
    n = len(df)
    if n == 0:
        raise InputError('empty_rows', f"rows must contain at least {min_rows} daily rows")
    if n < min_rows:
        raise InputError('too_few_rows', f"need at least {min_rows} rows, got {n}")
    if n > max_rows:
        raise InputError('too_many_rows', f"at most {max_rows} rows, got {n}")

    missing = [c for c in RAW_PRICE_COLUMNS if c not in df.columns]
    if missing:
        raise InputError('missing_column', f"missing column(s): {', '.join(missing)}")

    dates = _frame_dates(df)
    dupes = dates[dates.duplicated()].unique()
    if len(dupes):
        shown = ', '.join(str(pd.Timestamp(d).date()) for d in dupes[:5])
        raise InputError('duplicate_dates', f"duplicate date(s): {shown}")

    dates = dates.reset_index(drop=True)
    bad_order = np.flatnonzero((dates.diff() <= pd.Timedelta(0)).to_numpy())
    if len(bad_order):
        i = int(bad_order[0])
        raise InputError(
            'unsorted_dates',
            f"dates must be strictly increasing; first violation at index {i}",
        )

    prices = df[RAW_PRICE_COLUMNS].apply(pd.to_numeric, errors='coerce').astype(float)
    finite = np.isfinite(prices.values)
    if not finite.all():
        i, j = np.argwhere(~finite)[0]
        raise InputError(
            'non_finite_value',
            f"non-finite value in column {RAW_PRICE_COLUMNS[j]} at index {int(i)}",
        )
    if (prices.values <= 0).any():
        i, j = np.argwhere(prices.values <= 0)[0]
        raise InputError(
            'non_positive_price',
            f"non-positive price in column {RAW_PRICE_COLUMNS[j]} at index {int(i)}",
        )

    jumps = np.log(prices.values)
    jumps = np.abs(np.diff(jumps, axis=0))
    if (jumps > max_jump).any():
        i, j = np.argwhere(jumps > max_jump)[0]
        raise InputError(
            'implausible_jump',
            f"abs log change of {RAW_PRICE_COLUMNS[j]} at index {int(i) + 1} is "
            f"{jumps[i, j]:.4f}, above the {max_jump} limit",
        )

    if reject_block:
        start = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_START)
        end = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_END)
        in_block = (dates >= start) & (dates <= end)
        if in_block.any():
            raise InputError(
                'block_dates_unsupported',
                f"rows dated {start.date()}..{end.date()} are not servable: the V2 "
                "date repair needs the global vintage, which a raw-row request "
                f"cannot supply. Start after {end.date()}.",
            )

    frame = prices.copy()
    frame.index = pd.DatetimeIndex(dates.values, name='Date')
    features = add_stationary_features(frame)
    valid = features.dropna()
    if len(valid) < seq_len:
        raise InputError(
            'too_few_rows',
            f"need at least {min_rows} rows for {seq_len} feature rows, got {n} "
            f"({len(valid)} usable feature rows)",
        )

    window = valid.iloc[-seq_len:]
    return ModelInput(
        X=window[STATIONARY_FEATURE_COLUMNS].to_numpy(dtype=float),
        feature_frame=window.copy(),
        last_date=pd.Timestamp(valid.index[-1]),
        last_close=float(prices['Gold_IRR'].iloc[-1]),
        n_rows_input=n,
        n_feature_rows=int(len(valid)),
        n_rows_dropped=int(len(features) - len(valid)),
        feature_columns=list(STATIONARY_FEATURE_COLUMNS),
    )


def add_stationary_features(df):
    """
    Compute the frozen Stage 3 stationary feature set.

    This is the single source of truth for both training and serving. It is a
    pure function of the rows up to and including each row's date: every
    rolling window, EMA and lag is causal, and no column is a raw price level.

    Args:
        df: Frame indexed by date with columns Gold_IRR, USD_IRR, Ounce_USD,
            Oil_USD, sorted ascending.

    Returns:
        DataFrame with exactly ``STATIONARY_FEATURE_COLUMNS``; rows with an
        insufficient warm-up contain NaN and are dropped by the caller.
    """
    required = ['Gold_IRR', 'USD_IRR', 'Ounce_USD', 'Oil_USD']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"add_stationary_features missing columns: {missing}")

    gold = df['Gold_IRR'].astype(float)
    usd = df['USD_IRR'].astype(float)
    ounce = df['Ounce_USD'].astype(float)
    oil = df['Oil_USD'].astype(float)

    gold_ret = np.log(gold).diff()
    usd_ret = np.log(usd).diff()
    ounce_ret = np.log(ounce).diff()
    oil_ret = np.log(oil).diff()

    out = pd.DataFrame(index=df.index)
    # Own and USD returns: row t is the return at the prediction close.
    out['gold_ret_lag1'] = gold_ret
    out['gold_ret_lag2'] = gold_ret.shift(1)
    out['gold_ret_lag3'] = gold_ret.shift(2)
    out['gold_ret_lag5'] = gold_ret.shift(4)
    out['usd_ret_lag0'] = usd_ret
    out['usd_ret_lag1'] = usd_ret.shift(1)
    out['usd_ret_lag2'] = usd_ret.shift(2)
    out['usd_ret_lag5'] = usd_ret.shift(4)
    # Global bars: the bar dated t is not complete at the Iranian close of t,
    # so the last usable bar is t-1 (docs/EVAL_PROTOCOL.md §2.1).
    out['ounce_ret_lag1'] = ounce_ret.shift(1)
    out['ounce_ret_lag2'] = ounce_ret.shift(2)
    out['ounce_ret_lag5'] = ounce_ret.shift(4)
    out['oil_ret_lag1'] = oil_ret.shift(1)
    out['oil_ret_lag5'] = oil_ret.shift(4)

    # Technical indicators, all price-normalised or bounded.
    out['rsi_14'] = FeatureEngineer.calculate_rsi(gold, period=14)
    ema12 = gold.ewm(span=12, adjust=False).mean()
    ema26 = gold.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    out['macd_norm'] = macd / gold
    out['macd_signal_norm'] = macd_signal / gold

    sma20 = gold.rolling(window=20).mean()
    sd20 = gold.rolling(window=20).std()
    upper = sma20 + 2 * sd20
    lower = sma20 - 2 * sd20
    width = upper - lower
    out['bb_pctb_20'] = (gold - lower) / width
    out['bb_bandwidth_20'] = width / sma20

    out['price_sma_7'] = gold / gold.rolling(window=7).mean() - 1
    out['price_sma_20'] = gold / sma20 - 1
    out['price_sma_60'] = gold / gold.rolling(window=60).mean() - 1

    out['rv_5'] = gold_ret.rolling(window=5).std()
    out['rv_20'] = gold_ret.rolling(window=20).std()

    return out[STATIONARY_FEATURE_COLUMNS]


class FeatureEngineer:
    def __init__(self):
        """
        Initialize the Feature Engineer.
        """
        self.processed_dir = config.paths.DATA_PROCESSED_DIR

    @staticmethod
    def calculate_rsi(series, period=14):
        """
        Calculate Relative Strength Index (RSI).
        """
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def add_technical_indicators(self, df):
        """
        Add technical indicators (SMA, EMA, MACD, RSI, Bollinger Bands).
        """
        df = df.copy()
        
        # Simple Moving Averages
        df['SMA_7'] = df['Gold_IRR'].rolling(window=7).mean()
        df['SMA_30'] = df['Gold_IRR'].rolling(window=30).mean()

        # MACD (12, 26, 9)
        exp1 = df['Gold_IRR'].ewm(span=12, adjust=False).mean()
        exp2 = df['Gold_IRR'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # RSI
        df['RSI_14'] = self.calculate_rsi(df['Gold_IRR'], period=14)

        # Bollinger Bands (20, 2)
        sma_20 = df['Gold_IRR'].rolling(window=20).mean()
        std_20 = df['Gold_IRR'].rolling(window=20).std()
        df['Bollinger_Upper'] = sma_20 + (std_20 * 2)
        df['Bollinger_Lower'] = sma_20 - (std_20 * 2)

        return df

    def create_features(self, df):
        """
        Main method to create all features including Log Returns and Lags.
        """
        logger.info("Starting feature engineering...")
        
        # 1. Add Technical Indicators (based on absolute price)
        df = self.add_technical_indicators(df)

        # 2. Calculate Log Returns (The core feature for Phase 3 Model)
        # Log Return = ln(Price_t / Price_t-1)
        df['Gold_LogRet'] = np.log(df['Gold_IRR'] / df['Gold_IRR'].shift(1))
        df['USD_LogRet'] = np.log(df['USD_IRR'] / df['USD_IRR'].shift(1))
        
        # Global market returns (Handle zeros/NaNs if necessary)
        if 'Ounce_USD' in df.columns:
            df['Ounce_LogRet'] = np.log(df['Ounce_USD'] / df['Ounce_USD'].shift(1))
        if 'Oil_USD' in df.columns:
            df['Oil_LogRet'] = np.log(df['Oil_USD'] / df['Oil_USD'].shift(1))

        # 3. Create Lags (Past values used to predict future)
        # We lag the Log Returns because they are stationary
        lags = [1, 2, 3, 7]
        for lag in lags:
            df[f'Gold_LogRet_Lag_{lag}'] = df['Gold_LogRet'].shift(lag)
            df[f'USD_LogRet_Lag_{lag}'] = df['USD_LogRet'].shift(lag)
            if 'Ounce_LogRet' in df.columns:
                df[f'Ounce_LogRet_Lag_{lag}'] = df['Ounce_LogRet'].shift(lag)
        
        # 4. Create Target Variable
        # We want to predict the NEXT day's log return of Gold
        df['Target_Next_LogRet'] = df['Gold_LogRet'].shift(-1)
        
        # Also keep next day price for backtesting convenience (optional but useful)
        df['Target_Next_Price'] = df['Gold_IRR'].shift(-1)

        # 5. Clean up
        # Drop NaN values generated by rolling windows and shifting
        initial_len = len(df)
        df.dropna(inplace=True)
        final_len = len(df)
        
        logger.info(f"✅ Feature engineering complete. Rows: {initial_len} -> {final_len}")
        return df

    def save_processed_data(self, df, filename="advanced_gold_features.csv"):
        """Save the processed dataset with features to disk."""
        path = os.path.join(self.processed_dir, filename)
        df.to_csv(path)
        logger.info(f"Processed data saved to {path}")



if __name__ == "__main__":
    # Load CSV directly from path
    df = pd.read_csv(
        "data/raw/final_gold_dataset.csv",
        index_col="Date",
        parse_dates=True
    )
    df.sort_index(inplace=True)

    engineer = FeatureEngineer()
    df_features = engineer.create_features(df)
    engineer.save_processed_data(df_features)
    print(df_features.head())
    print(f"Shape: {df_features.shape}")
