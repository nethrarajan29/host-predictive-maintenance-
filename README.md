# AI-Based Industrial Predictive Maintenance & SCADA Platform
## Multi-Domain Feature Engineering & Machine Learning Benchmark

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18%2B-61DAFB.svg)](https://react.dev/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.4%2B-F7931E.svg)](https://scikit-learn.org/)
[![License MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end industrial **Digital Twin SCADA & Predictive Maintenance Platform** engineered for rotating machinery (turbine motors, centrifugal pumps, compressors). The system models multi-sensor physical wear, extracts multi-domain time-series features (**Statistical Time-Domain**, **Discrete Fourier Transform / FFT**, and **Automated TSFresh**), and benchmarks multi-model anomaly classification alongside continuous **Remaining Useful Life (RUL)** regression.

---

## 👥 1. Team Architecture & Responsibilities

The system integrates 4 specialized modular engineering deliverables:

```
                             Raw SCADA Sensor Telemetry
                     (Temperature, Vibration, Current, Pressure, Noise)
                                          │
                               Rolling Windows (W=30, S=15)
                                          │
               ┌──────────────────────────┼──────────────────────────┐
               ▼                          ▼                          ▼
       👩 Person 1                👩 Person 2                👩 Person 3
       Time-Domain Features       Frequency (FFT) Features   TSFresh Features
       • Mean, RMS, Skew, Kurt,   • FFT Magnitude Spectrum   • 3,885 Candidates
         Peak-to-Peak, Crest      • Dominant Freq & Energy   • Benjamini-Hochberg FDR
       • time_features.py         • frequency_features.py    • tsfresh_features.py
               │                          │                          │
               └──────────────────────────┼──────────────────────────┘
                                          │
                                          ▼
                                  👩 Person 4 (Lead)
                                  ML Pipeline & Final Integration
                                  • Multi-Domain Feature Fusion (135 Features)
                                  • Multi-Model Benchmark (RF, GB, Logistic)
                                  • Cross-Domain Feature Importance Attribution
                                  • ml_pipeline.py & Full-Stack SCADA Integration
```

| Person | Focus Area | Deliverable Script | Key Generated Artifacts | Domain Importance Share |
| :--- | :--- | :--- | :--- | :---: |
| **Person 1** | **Time-Domain Statistics** | `time_features.py` | `data/time_features.csv`, `data/time_features_summary.csv` | **61.98%** |
| **Person 2** | **FFT & Frequency Analysis**| `frequency_features.py` | `data/frequency_features.csv`, `outputs/frequency/*.png` | **26.81%** |
| **Person 3** | **TSFresh Feature Selection** | `tsfresh_features.py` | `data/tsfresh_features_selected.csv`, `outputs/tsfresh/*.png` | **11.20%** |
| **Person 4** | **ML Integration & Benchmark** | `ml_pipeline.py` | `models/rf_classifier.joblib`, `outputs/evaluation/*.png` | **Unified Lead** |

---

## 📊 2. Machine Learning Benchmark Results

Evaluated on 115 holdout test windows (55 Normal vs. 60 Anomalous machine operation states) using 5-fold stratified cross-validation:

| Model Architecture | Accuracy | Precision | Recall (Sensitivity) | F1-Score | ROC-AUC | 5-Fold CV Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest Classifier** (★ Best) | **95.65%** | **96.61%** | **95.00%** | **95.80%** | **0.9976** | **98.70% ± 1.06%** |
| **Gradient Boosting Classifier** | **96.52%** | **96.67%** | **96.67%** | **96.67%** | **0.9648** | **98.91% ± 0.69%** |
| **Baseline (Logistic Regression)** | **96.52%** | **96.67%** | **96.67%** | **96.67%** | **0.9942** | **98.26% ± 1.63%** |

### Confusion Matrix (Random Forest):
- **True Normal (TN)**: 53 (96.4% Specificity)
- **False Alarm (FP)**: 2 (3.6% False Positive Rate)
- **Missed Anomaly (FN)**: 3 (5.0% False Negative Rate)
- **True Anomaly (TP)**: 57 (95.0% Recall / Sensitivity)

---

## 🔍 3. Which Features Drive Anomaly Detection?

Cross-domain feature importance demonstrates how mechanical and electrical degradation manifests in telemetry:

| Rank | Feature Identifier | Domain Origin | Importance (MDI) | Physical & Engineering Meaning |
| :---: | :--- | :--- | :---: | :--- |
| **1** | `TIME__Noise__max` | Time Domain (Person 1) | **0.0909** | Extreme acoustic chatter spikes when mechanical bearings lose lubrication |
| **2** | `FREQ__Noise__mean_power_spectrum` | Frequency FFT (Person 2) | **0.0779** | Wideband acoustic energy expansion under turbulent cavitation |
| **3** | `FREQ__Motor_Current__fft_peak_amplitude` | Frequency FFT (Person 2) | **0.0493** | Electrical current harmonic surge at rotational frequency |
| **4** | `TIME__Noise__peak_to_peak` | Time Domain (Person 1) | **0.0492** | Sound pressure amplitude oscillation range |
| **5** | `TIME__Noise__std` | Time Domain (Person 1) | **0.0394** | Acoustic noise volatility expansion |
| **6** | `TIME__Motor_Current__max` | Time Domain (Person 1) | **0.0391** | Peak electrical motor load under mechanical resistance |
| **7** | `TIME__Motor_Current__std` | Time Domain (Person 1) | **0.0387** | Phase current fluctuation variance |
| **8** | `TIME__Noise__shape_factor` | Time Domain (Person 1) | **0.0296** | Waveform distortion relative to mean sound level |
| **9** | `FREQ__Motor_Current__spectral_energy` | Frequency FFT (Person 2) | **0.0293** | Total harmonic power drawn by stator |
| **10** | `TSFRESH__Motor_Current__fft_agg__skew` | TSFresh (Person 3) | **0.0293** | Nonlinear spectral asymmetry collapse during bearing failure |

---

## 🗜️ 4. Compactness & Storage Efficiency

The repository was engineered for maximum performance with minimal disk footprint:

| Metric | Before Optimization | After Optimization | Improvement |
| :--- | :---: | :---: | :---: |
| **Total Repo Size (clean)** | ~650 MB | **~32 MB** | **> 95% Space Saved** |
| **Model Artifact Size** | 143.5 MB (duplicates) | **~16.9 MB** (compressed) | **88.2% Reduction** |
| **Redundant Clone Folders** | 3 copies (620 MB) | **0 (Consolidated Root)** | **100% Elimination** |
| **Duplicate Datasets** | 2 copies (11.3 MB) | **1 Canonical File** | **50% Elimination** |

---

## 🚀 5. Quick Start Guide (Run on Any Computer)

This project is packaged so **any team member or evaluator can run it in seconds with just Python** — no Node.js or npm installation is required because the production frontend is pre-compiled and served directly by FastAPI.

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/rithanyau24-nyunus222/predictive-newweek3.git
cd predictive-newweek3

# Install Python requirements
pip install -r requirements.txt
```

### 2. Launch the System (1-Click)
- **Windows (Double-Click)**: Simply double-click [`start_app.bat`](file:///c:/Users/ritha/OneDrive/Desktop/Predweek3/start_app.bat)
- **Or from Terminal**:
  ```bash
  python main.py
  ```

### 3. Open in Browser
- **Direct HTTP (Instant Load)**: 👉 **`http://127.0.0.1:8000`**
- **Secure HTTPS (With SSL)**: 👉 **`https://127.0.0.1:8443`**

### 4. Running Individual Team Feature Pipelines (Optional)
```bash
# Person 1: Extract Time-Domain Features
python time_features.py

# Person 2: Extract FFT & Spectral Features
python frequency_features.py

# Person 3: Extract & Filter TSFresh Features
python tsfresh_features.py

# Person 4 (Lead): Train Models, Benchmark & Evaluate
python ml_pipeline.py
```

### 5. Frontend React Development (Optional)
If you wish to modify the React dashboard source code:
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## 📡 6. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/status` | System telemetry status, active PLCs, and model metadata |
| `GET` | `/api/current` | Real-time multi-sensor readings, health index, RUL prediction |
| `GET` | `/api/ml/metrics` | Person 4 classification benchmarks, ROC-AUC, domain contributions |
| `GET` | `/api/features/summary` | Top discriminative features from Person 1 and Person 2 |
| `GET` | `/api/model` | RUL regression performance metrics (MAE, RMSE, R²) |
| `POST` | `/api/predict` | Point inference for custom sensor inputs |
| `POST` | `/api/control` | Simulation clock control (`start`, `pause`, `next`, `reset`) |
