import os
import json
import joblib
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

class Predictor:
    """
    RUL Predictor and Anomaly Detector engine powered exclusively by Random Forest Regressor
    and Isolation Forest.
    """
    def __init__(self, models_dir=None):
        if models_dir is None:
            curr_dir = os.path.dirname(os.path.abspath(__file__))
            m1 = os.path.join(curr_dir, "models")
            m2 = os.path.join(os.path.dirname(curr_dir), "models")
            models_dir = m1 if os.path.exists(m1) else (m2 if os.path.exists(m2) else m1)
        self.models_dir = models_dir
        
        # Load scaler
        scaler_path = os.path.join(self.models_dir, "scaler.pkl")
        self.scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None
        
        # Load Random Forest RUL model
        rf_path = os.path.join(self.models_dir, "rf_rul_model.pkl")
        if not os.path.exists(rf_path):
            rf_path = os.path.join(self.models_dir, "random_forest_model.pkl")
            
        self.model = None
        if os.path.exists(rf_path):
            try:
                self.model = joblib.load(rf_path)
            except Exception as e:
                print(f"Warning: Failed to load RF model: {e}")
                    
        self.models = {"Random Forest Regressor": self.model}
        self.best_model_name = "Random Forest Regressor"
        self.active_model_name = "Random Forest Regressor"
        self.available_models = ["Random Forest Regressor"]
        
        # Load Isolation Forest for Anomaly Detection
        iso_path = os.path.join(self.models_dir, "isolation_forest.pkl")
        if not os.path.exists(iso_path):
            iso_path = os.path.join(self.models_dir, "isolation_forest_model.pkl")
        self.iso_forest = joblib.load(iso_path) if os.path.exists(iso_path) else None
        
        # Load metrics metadata
        self.comparison_data = None
        for cf in ["model_metrics.json", "model_comparison.json"]:
            cp = os.path.join(self.models_dir, cf)
            if os.path.exists(cp):
                try:
                    with open(cp, "r") as f:
                        self.comparison_data = json.load(f)
                    break
                except Exception as e:
                    print(f"Warning: Failed to load metrics metadata: {e}")

    def _resolve_model(self, model_name=None):
        """Resolves active Random Forest model instance."""
        return self.model, "Random Forest Regressor"

    def predict_rul(self, temperature, vibration, current, pressure=5.0, noise=42.0, model_name=None, return_model_info=False, return_full_info=False):
        """
        Predicts Remaining Useful Life (RUL) in Days using Random Forest Regressor.
        Calculates prediction confidence and uncertainty interval.
        """
        active_model_name = "Random Forest Regressor"
        if not self.model or not self.scaler:
            if return_full_info:
                return 0, active_model_name, 0.0, 50.0, (0, 0)
            elif return_model_info:
                return 0, active_model_name, 0.0
            return 0
            
        df = pd.DataFrame({
            "Temperature": [float(temperature)],
            "Vibration": [float(vibration)],
            "Motor_Current": [float(current)],
            "Pressure": [float(pressure) if pressure is not None else 5.0],
            "Noise": [float(noise) if noise is not None else 42.0]
        })
        
        X_scaled = self.scaler.transform(df)
        raw_pred = float(self.model.predict(X_scaled)[0])
        int_rul = max(0, int(round(raw_pred)))
        
        # Calculate Prediction Confidence & Uncertainty interval
        pred_std = 15.0
        if hasattr(self.model, "estimators_") and self.model.estimators_:
            try:
                # Subsample up to 20 trees for instant standard deviation calculation
                sample_trees = self.model.estimators_[:20]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tree_preds = [float(t.predict(X_scaled)[0]) for t in sample_trees]
                pred_std = float(np.std(tree_preds))
            except Exception:
                pred_std = 15.0
        
        rel_uncertainty = pred_std / max(20.0, raw_pred)
        confidence_pct = round(max(50.0, min(98.5, 100.0 - (rel_uncertainty * 60.0))), 1)
        ci_lower = max(0, int(round(raw_pred - 1.96 * pred_std)))
        ci_upper = int(round(raw_pred + 1.96 * pred_std))
        
        if return_full_info:
            return int_rul, active_model_name, raw_pred, confidence_pct, (ci_lower, ci_upper)
        elif return_model_info:
            return int_rul, active_model_name, raw_pred
        return int_rul

    def detect_anomaly(self, temperature, vibration, current, pressure=5.0, noise=42.0):
        """
        Detects machine anomalies using Isolation Forest on 5 sensor inputs.
        Returns is_anomaly, anomaly_status ('Normal' vs 'Anomaly Detected'), and anomaly_score.
        """
        if not self.iso_forest or not self.scaler:
            return {"is_anomaly": False, "anomaly_status": "Normal", "anomaly_score": 0.0}
        
        df = pd.DataFrame({
            "Temperature": [float(temperature)],
            "Vibration": [float(vibration)],
            "Motor_Current": [float(current)],
            "Pressure": [float(pressure) if pressure is not None else 5.0],
            "Noise": [float(noise) if noise is not None else 42.0]
        })
        
        X_scaled = self.scaler.transform(df)
        pred = self.iso_forest.predict(X_scaled)[0]
        raw_score = float(self.iso_forest.decision_function(X_scaled)[0])
        
        is_anomaly = bool(pred == -1)
        status = "Anomaly Detected" if is_anomaly else "Normal"
        
        return {
            "is_anomaly": is_anomaly,
            "anomaly_status": status,
            "anomaly_score": round(raw_score, 3)
        }

    def get_comparison_data(self):
        """Returns model evaluation metadata."""
        return self.comparison_data

    def get_metrics_data(self):
        """Returns Random Forest metrics metadata."""
        return self.comparison_data


def filter_displayed_rul(raw_prediction, prev_displayed_rul=None, health=100.0):
    """
    Temporal smoothing filter for displayed Remaining Useful Life (RUL).
    - Monotonic non-increasing.
    - Smoothly decrements (1-3 days per step based on ML prediction and degradation rate).
    - Preserves gradual day-by-day degradation while tracking raw Random Forest predictions closely.
    - Converges smoothly to 0 when machine reaches terminal state (health = 0%).
    """
    raw_val = float(raw_prediction)
    h_val = float(health)
    
    if prev_displayed_rul is None:
        val_float = max(0.0, raw_val)
    else:
        prev_float = float(prev_displayed_rul)
        if prev_float <= 0.0:
            return 0.0, 0

        # Dynamic decay target blending day-advance with Random Forest model prediction
        time_decay_target = prev_float - 1.0
        blended = 0.85 * time_decay_target + 0.15 * raw_val
        
        # If health is at terminal 0%, accelerate smooth convergence to 0 without instant hard jump
        if h_val <= 0.0:
            blended = min(blended, prev_float - 2.0)

        # Enforce smooth non-freezing monotonic upper bound (max decrement 0.51 to 3.0 per step)
        min_step_decrement = 0.51
        max_step_decrement = 3.0
        
        target_decrement = prev_float - blended
        clamped_decrement = max(min_step_decrement, min(max_step_decrement, target_decrement))
        
        val_float = max(0.0, prev_float - clamped_decrement)
        
    int_rul = max(0, int(round(val_float)))
    return val_float, int_rul


def get_future_trend(history_values, steps=20):
    """
    Extrapolates the next steps values based on polynomial trend fitting.
    Ensures seamless connection at index 0 to history_values[-1] with growing future uncertainty.
    """
    if len(history_values) < 2:
        return [history_values[-1]] * steps if history_values else [0] * steps
        
    x = np.arange(len(history_values))
    y = np.array(history_values)
    last_val = float(y[-1])
    
    # Fit recent trend (degree 2 polynomial if enough points, else linear)
    window = min(30, len(history_values))
    deg = 2 if window >= 10 else 1
    try:
        coef = np.polyfit(x[-window:], y[-window:], deg)
        poly1d_fn = np.poly1d(coef)
    except:
        coef = np.polyfit(x, y, 1)
        poly1d_fn = np.poly1d(coef)
        
    future_x = np.arange(len(history_values) - 1, len(history_values) - 1 + steps)
    base_future = poly1d_fn(future_x)
    
    # Offset base_future so future_y[0] matches last_val exactly for seamless connection
    offset = last_val - base_future[0]
    base_future = base_future + offset
    
    # Estimate noise / standard deviation from recent residuals
    recent_residuals = y[-window:] - poly1d_fn(x[-window:])
    std_dev = float(np.std(recent_residuals)) if len(recent_residuals) > 1 else 0.5
    std_dev = max(0.15, min(std_dev, 2.5))
    
    # Project into future with growing uncertainty fan
    np.random.seed(42)
    future_y = [round(last_val, 2)]
    for i in range(1, steps):
        uncertainty_factor = (i / steps) * 0.75
        noise = float(np.random.normal(0, std_dev * uncertainty_factor))
        future_y.append(round(float(base_future[i] + noise), 2))
        
    return future_y


# Backward compatibility alias
PredictiveMaintenanceModel = Predictor
