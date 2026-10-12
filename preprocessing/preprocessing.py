import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

PRIMARY_FEATURE_COLS = ["Temperature", "Vibration", "Motor_Current", "Pressure", "Noise"]

def load_data(filepath="data/sensor_data.csv"):
    """Loads sensor dataset with fallback path resolution."""
    if not os.path.exists(filepath):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for candidate in [filepath, "data/sensor_data.csv", "datasets/sensor_data.csv"]:
            alt_path = os.path.join(base_dir, candidate)
            if os.path.exists(alt_path):
                filepath = alt_path
                break
    return pd.DataFrame(pd.read_csv(filepath))

def add_rolling_features(df, feature_cols=None, window=5):
    """
    Adds rolling mean, rolling standard deviation, and rate-of-change features
    without future-data leakage (strictly causal rolling window).
    """
    if feature_cols is None:
        feature_cols = PRIMARY_FEATURE_COLS
        
    df_feat = df.copy()
    for col in feature_cols:
        if col in df_feat.columns:
            # 1. Rolling Mean
            df_feat[f"{col}_rolling_mean"] = df_feat[col].rolling(window=window, min_periods=1).mean()
            # 2. Rolling Standard Deviation
            df_feat[f"{col}_rolling_std"] = df_feat[col].rolling(window=window, min_periods=1).std().fillna(0.0)
            # 3. Rate of Change
            df_feat[f"{col}_rate_of_change"] = df_feat[col].diff().fillna(0.0)
    return df_feat

def preprocess_data(df, is_training=True, include_engineered=False):
    """
    Preprocesses sensor data for training and inference.
    - Forward-fills missing sensor telemetry
    - Selects 5 primary sensor features (+ optional engineered features)
    - Performs 80/20 train/test split (random_state=42)
    - Fits StandardScaler ONLY on training set to eliminate data leakage
    """
    df_clean = df.copy()
    df_clean.ffill(inplace=True)
    
    feature_cols = list(PRIMARY_FEATURE_COLS)
    
    if include_engineered:
        df_clean = add_rolling_features(df_clean, feature_cols=feature_cols)
        engineered_cols = [
            f"{c}_{suffix}"
            for c in feature_cols
            for suffix in ["rolling_mean", "rolling_std", "rate_of_change"]
            if f"{c}_{suffix}" in df_clean.columns
        ]
        all_cols = feature_cols + engineered_cols
    else:
        all_cols = feature_cols
    
    # Resolve models directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    scaler_path = os.path.join(models_dir, "scaler.pkl")
    
    if is_training:
        target_col = "Remaining_Useful_Life_Days"
        X = df_clean[all_cols]
        y = df_clean[target_col]
        
        # Train/Test Split (80/20)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Feature Scaling (Fit on Train only)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Save scaler
        joblib.dump(scaler, scaler_path)
        
        return X_train_scaled, X_test_scaled, y_train, y_test
    else:
        # Inference mode
        scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None
        X = df_clean[all_cols]
        X_scaled = scaler.transform(X) if scaler else X.values
        return X_scaled


