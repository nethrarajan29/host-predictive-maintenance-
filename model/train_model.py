import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
os.makedirs(MODELS_DIR, exist_ok=True)


def generate_synthetic_dataset(num_records=91250):
    np.random.seed(42)
    temp = np.random.normal(68.0, 5.0, num_records)
    vib = np.random.normal(2.5, 0.5, num_records)
    curr = np.random.normal(12.0, 1.5, num_records)
    press = np.random.normal(5.0, 0.3, num_records)
    noise = np.random.normal(42.0, 3.0, num_records)
    rul = 250 - (temp * 0.8 + vib * 25.0 + curr * 4.0 + press * 2.0 + noise * 0.5) / 4.0 + np.random.normal(0, 5, num_records)
    rul = np.clip(rul, 0, 365)
    return pd.DataFrame({
        'Temperature': temp,
        'Vibration': vib,
        'Motor_Current': curr,
        'Pressure': press,
        'Noise': noise,
        'Remaining_Useful_Life_Days': rul
    })


def train():
    print('=' * 51)
    print(' Predictive Maintenance ML Training Pipeline')
    print(' (RandomForest Regressor + IsolationForest Anomaly Detector)')
    print('=' * 51)
    
    # 1. Load Data
    print('1. Loading data...')
    dataset_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sensor_data.csv')
    if not os.path.exists(dataset_path):
        alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sensor_stream_history.csv')
        dataset_path = alt_path if os.path.exists(alt_path) else None
        
    if dataset_path and os.path.exists(dataset_path):
        df = pd.read_csv(dataset_path)
    else:
        df = generate_synthetic_dataset(num_records=91250)
        
    print(f'   Dataset size: {len(df):,} records')
    feature_cols = ['Temperature', 'Vibration', 'Motor_Current', 'Pressure', 'Noise']
    target_col = 'Remaining_Useful_Life_Days'
    
    print(f'   Input features (5): {feature_cols}')
    print(f'   Target variable: {target_col} (RUL in Days)')
    
    X = df[feature_cols]
    y = df[target_col]
    
    # 2. 80/20 Train-Test Split
    print('\\n2. Preprocessing data & 80/20 train-test split...')
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f'   Training records: {len(X_train):,}')
    print(f'   Testing records:  {len(X_test):,}')
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Save Scaler
    scaler_path = os.path.join(MODELS_DIR, 'scaler.pkl')
    joblib.dump(scaler, scaler_path)
    print(f'   Saved scaler to {scaler_path}')
    
    # 3. Train Random Forest Regressor
    print('\\n3. Training & Evaluating Random Forest Regressor:')
    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train_scaled, y_train)
    
    y_train_pred = rf_model.predict(X_train_scaled)
    y_test_pred = rf_model.predict(X_test_scaled)
    
    train_r2 = float(r2_score(y_train, y_train_pred))
    test_r2 = float(r2_score(y_test, y_test_pred))
    mae = float(mean_absolute_error(y_test, y_test_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_test_pred)))
    
    rf_path = os.path.join(MODELS_DIR, 'rf_rul_model.pkl')
    joblib.dump(rf_model, rf_path, compress=3)
    print(f'      Saved to: {rf_path}')
    print(f'      Train R^2: {train_r2:.4f} | Test R^2: {test_r2:.4f}')
    print(f'      MAE:      {mae:.2f} Days')
    print(f'      RMSE:     {rmse:.2f} Days')
    
    # Extract Feature Importances
    importances = rf_model.feature_importances_
    feature_importance_list = [
        {'feature': name, 'importance': round(float(imp), 4)}
        for name, imp in zip(feature_cols, importances)
    ]
    feature_importance_list.sort(key=lambda item: item['importance'], reverse=True)
    
    # Sample Scatter Plot data (first 500 test points)
    sample_indices = np.random.choice(len(y_test), min(500, len(y_test)), replace=False)
    scatter_actual = [round(float(val), 2) for val in y_test.iloc[sample_indices]]
    scatter_pred = [round(float(val), 2) for val in y_test_pred[sample_indices]]
    
    # Residual distribution
    residuals = [round(float(act - prd), 2) for act, prd in zip(scatter_actual, scatter_pred)]
    
    # 4. Train Isolation Forest for Anomaly Detection
    print('\n4. Training Isolation Forest for Anomaly Detection...')
    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=0.03,
        random_state=42,
        n_jobs=-1
    )
    iso_forest.fit(X_train_scaled)
    iso_path = os.path.join(MODELS_DIR, 'isolation_forest.pkl')
    joblib.dump(iso_forest, iso_path, compress=3)
    print(f'   Saved Isolation Forest to: {iso_path}')
    
    # 5. Save Metadata & Metrics JSON
    metrics_data = {
        'algorithm': 'Random Forest Regressor',
        'dataset_size': len(df),
        'train_size': len(X_train),
        'test_size': len(X_test),
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'r2_score': round(test_r2, 4),
        'train_r2_score': round(train_r2, 4),
        'feature_importance': feature_importance_list,
        'scatter_plot': {
            'actual': scatter_actual,
            'predicted': scatter_pred
        },
        'residuals': residuals
    }
    
    metrics_path = os.path.join(MODELS_DIR, 'model_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics_data, f, indent=2)
    print(f'\\n5. Saved model metrics metadata to {metrics_path}')
    
    print('\\n=== Model Training Pipeline Successfully Completed ===')
    print(f'Active Predictive Model: Random Forest Regressor')
    print(f'MAE: {mae:.2f} Days | RMSE: {rmse:.2f} Days | R2 Score: {test_r2:.4f}')
    print('Artifacts stored in models/')

if __name__ == '__main__':
    train()
