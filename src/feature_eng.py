import pandas as pd
import numpy as np
import os
import sys

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
