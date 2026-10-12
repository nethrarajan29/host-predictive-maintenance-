# PredictX — Data Drift & Model Reliability Monitoring Architecture

## 1. Executive Summary & Core Objective

In production predictive maintenance (PdM) systems, machine learning models do not operate in a static world. As rotating machinery (turbines, pumps, compressors) undergoes mechanical wear, load shifts, lubrication degradation, seasonal ambient variations, or sensor electrical drift, the statistical distributions of incoming telemetry diverge from the data on which the models were originally trained.

The **PredictX AI Reliability Layer** provides continuous, automated monitoring to answer the critical operational question:

> **"Can we still trust the data and predictions being produced by our predictive maintenance system?"**

```
                  Raw SCADA / Simulator Sensor Telemetry
                                    │
                                MQTT / Kafka
                                    │
                         process_mqtt_telemetry()
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
   Existing ML Pipeline                             New Drift Engine
   • Isolation Forest (Anomaly)                     (drift_engine.py)
   • Random Forest (RUL)                            ├── Baseline Comparison
   • Maintenance Engine                             ├── Data Drift (PSI, KS-Test)
            │                                       ├── Prediction Drift (RUL, Anomaly Rate)
            │                                       ├── Data Quality (Missing, Stuck, Range)
            │                                       └── Model Health (HEALTHY/WARNING/CRITICAL)
            │                                               │
            └───────────────────────┬───────────────────────┘
                                    ▼
                     Relational Database Persistence
                     (drift_monitoring.db / SQLite / PostgreSQL)
                                    │
                     FastAPI Endpoints (/api/drift/*)
                                    │
                     React Dashboard ("AI Reliability")
```

---

## 2. Theoretical Concepts: Data Drift vs. Prediction Drift vs. Data Quality

### A. Data Drift (Covariate Shift)
- **Definition**: A change in the joint statistical distribution of input sensor features $P(X)$ over time, while the underlying conditional probability $P(Y \mid X)$ may or may not remain unchanged.
- **Physical Meaning**: *"The machine's operational environment, mechanical load, or sensor behavior has changed."*
- **Examples**:
  - Vibration RMS distribution shifts higher due to gradual bearing flaking or unbalance.
  - Temperature distribution expands due to stator cooling fan blockage or higher ambient summer temperatures.
  - Acoustic noise spectrum shifts into higher frequency harmonics due to cavitation.

### B. Prediction Drift (Model Output Shift)
- **Definition**: A significant shift in the distribution of the model's outputs $P(\hat{Y})$ over rolling inference windows.
- **Physical Meaning**: *"The model's output forecasts (Remaining Useful Life days, failure probability, anomaly flagging frequency) have fundamentally changed."*
- **Examples**:
  - Baseline historical RUL average is $220\text{–}250$ days, but the rolling window average collapses to $35\text{–}60$ days.
  - Isolation Forest anomaly rate surges from nominal $2\%$ to $>25\%$.

### C. Data Quality & Transducer Health
- **Definition**: Measurement pipeline anomalies that represent sensor hardware failure, communications loss, or electrical disconnection rather than true machine physics.
- **Checks**:
  1. **Excessive Missingness / Packet Loss**: Percentage of null or non-finite readings exceeding tolerance limits ($>2\%$ warning, $>10\%$ critical).
  2. **Stuck / Frozen Sensor**: Zero or negligible variance ($\sigma < 0.001$) over consecutive telemetry packets (indicating a dead transducer, ADC freeze, or disconnected analog channel).
  3. **Physical Bound Violations**: Sensor readings outside plausibility limits (e.g., negative temperatures in operating motors, pressure exceeding $100\text{ bar}$).

---

## 3. Reference Baseline vs. Current Inference Window

```
   ┌────────────────────────────────────────────────────────┐
   │               REFERENCE BASELINE (LOCKED)              │
   │  • Derived from historical normal operating data       │
   │  • Stores 5 quantile bin edges & smoothed frequencies  │
   │  • NEVER auto-updated silently (prevents drift masking)│
   └──────────────────────────┬─────────────────────────────┘
                              │ Compares against
                              ▼
   ┌────────────────────────────────────────────────────────┐
   │               CURRENT TELEMETRY WINDOW (W=50)          │
   │  • Rolling buffer of latest 50 SCADA sensor packets    │
   │  • Evaluated periodically every 10 steps per PLC       │
   └────────────────────────────────────────────────────────┘
```

- **Why the baseline must NOT auto-update automatically**: If a monitoring system continuously absorbs new drifted data into its baseline, it will gradually normalize degraded or faulty machine behavior, completely blinding plant engineers to progressive failures.

---

## 4. Statistical Drift Detection Algorithms

### 1. Population Stability Index (PSI)
PSI measures the divergence between the reference baseline probability distribution $E$ (Expected) and the current inference window distribution $A$ (Actual):

$$\text{PSI} = \sum_{i=1}^{k} \left( A_i - E_i \right) \times \ln\left( \frac{A_i}{E_i} \right)$$

- **Laplace Pseudocount Smoothing**: To prevent division by zero or extreme logarithmic penalties with small sample windows ($N = 30\text{–}100$), probabilities are smoothed via Laplace pseudocounts:
  $$A_i = \frac{C_i + 1}{N + k}$$
- **Industry Standard Interpretation**:
  - $\text{PSI} < 0.10$: **Stable / No Drift** (Normal)
  - $0.10 \le \text{PSI} < 0.25$: **Moderate Drift** (Warning)
  - $\text{PSI} \ge 0.25$: **Significant / Severe Drift** (Critical)

### 2. Two-Sample Kolmogorov-Smirnov (KS) Test
The two-sample KS test evaluates whether the current continuous sensor readings and the baseline samples originate from the same continuous distribution:

$$D = \sup_x \left| F_{\text{baseline}}(x) - F_{\text{current}}(x) \right|$$

- Computed using pure, vectorized NumPy empirical cumulative distribution function (ECDF) differences with asymptotic Kolmogorov series $p$-values.
- Significance level $\alpha = 0.05$ ($p < 0.05$ indicates statistically significant distribution change).

### 3. 1st Wasserstein Distance (Earth Mover's Distance)
Measures the minimal work required to transform the baseline distribution into the current distribution:

$$W_1(u, v) = \int_{-\infty}^{\infty} \left| F_u(x) - F_v(x) \right| dx$$

---

## 5. Model Health Status Synthesis & Decision Logic

| Health Status | Decision Criteria | Operational Interpretation |
| :--- | :--- | :--- |
| **`HEALTHY`** | Data Drift = NORMAL, Prediction Drift = NORMAL, Data Quality = NORMAL | All telemetry, model forecasts, and sensor transducers match baseline expectations. |
| **`WARNING`** | Any metric = WARNING, or $0.10 \le \text{PSI}_{\text{avg}} < 0.25$, or missingness between $2\%\text{–}10\%$ | Early physical wear, load adjustment, or seasonal shift. Recommend physical inspection before retraining. |
| **`CRITICAL`** | Any metric = CRITICAL, or $\text{PSI}_{\text{avg}} \ge 0.25$, or stuck sensor, or missingness $\ge 10\%$ | Severe distribution divergence or transducer failure. Model predictions are no longer reliable. Immediate maintenance required. |

---

## 6. Database Schema (`drift_monitoring.db`)

The database persistence layer is implemented with zero external dependencies using Python's standard library `sqlite3` and is structured for multi-asset / multi-PLC isolation:

1. `drift_monitoring_runs`: Master evaluation run records (`run_id`, `plc_id`, `timestamp`, `overall_status`, `data_drift_status`, `prediction_drift_status`, `data_quality_status`, `overall_drift_score`, `summary`, `reason`, `recommendation`).
2. `drift_feature_results`: Per-feature statistical tests (`feature_name`, `baseline_mean`, `current_mean`, `psi_score`, `ks_statistic`, `ks_pvalue`, `wasserstein_distance`, `drift_status`, `explanation`).
3. `prediction_drift_results`: Model behavior metrics (`target_name`, `baseline_mean`, `current_mean`, `psi_score`, `drift_status`, `details`).
4. `data_quality_results`: Data quality checks (`feature_name`, `missing_pct`, `is_stuck`, `stuck_value`, `out_of_range_count`, `quality_status`, `issue_description`).
5. `drift_alerts`: Operational reliability alert history with anti-spam cooldown (`plc_id`, `alert_type`, `severity`, `title`, `message`, `recommendation`, `resolved`).

---

## 7. REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/drift/status` | Real-time high-level reliability status, PSI scores, and recommendations |
| `GET` | `/api/drift/summary` | Summary evaluation for a specific PLC (`?plc_id=PLC_01`) |
| `GET` | `/api/drift/features` | Per-sensor statistical test breakdown (PSI, KS p-value, Wasserstein) |
| `GET` | `/api/drift/predictions` | Prediction drift results (RUL distribution shift, anomaly flag rate) |
| `GET` | `/api/drift/data-quality` | Data quality diagnostics (missingness %, stuck transducers) |
| `GET` | `/api/drift/history` | Chronological series of historical evaluation runs |
| `GET` | `/api/drift/alerts` | Active and historical reliability alert events |
| `GET` | `/api/drift/baseline` | Locked baseline metadata, quantiles, and sample sizes |
| `POST` | `/api/drift/baseline/rebuild` | Intentional administrator trigger to rebuild baseline from historical data |
| `POST` | `/api/drift/simulate-drift` | Controlled demonstration sandbox trigger (safe simulation) |
| `POST` | `/api/drift/check` | Trigger immediate on-demand drift evaluation |

---

## 8. Frontend Dashboard Integration ("AI Reliability")

Integrated directly into the PredictX React SCADA dashboard:
- **Dedicated Sidebar Item**: "AI Reliability & Drift" with real-time status indicator.
- **Top Metric Cards**: Overall Model Health, Input Data Drift PSI, Output Prediction Drift PSI, Data Quality Index.
- **Diagnosis Banner**: Natural language root-cause explanation and domain-specific recommendation.
- **Detail Tabs**:
  1. **Feature Drift Matrix**: Comprehensive table with baseline vs current statistics, PSI ratings, KS p-values, and physical explanations.
  2. **Prediction Drift & Anomaly Trend**: RUL forecast shifts and Isolation Forest anomaly frequency tracking.
  3. **Data Quality Diagnostics**: Stuck sensor flags, missing packet percentages, and physical out-of-range counts.
  4. **Historical Drift Timeline**: Time-series log of reliability runs across assets.
  5. **Reliability Alerts Log**: Real-time event log with cooldown suppression.
  6. **Interactive Demo Sandbox**: One-click controlled demonstration panel for project reviews and stakeholder presentations.

---

## 9. Controlled Demonstration Sandbox Modes

The demonstration sandbox allows presenting drift scenarios during reviews without corrupting the reference baseline dataset:

1. **`normal`**: Restores normal baseline telemetry (Status: `HEALTHY`).
2. **`mild_vibration_drift`**: Shifts Vibration RMS from $0.20$ to $0.55\text{ mm/s}$ ($\text{PSI} \approx 0.18$, Status: `WARNING`).
3. **`severe_thermal_drift`**: Induces simultaneous Temperature ($95^\circ\text{C}$), Noise ($75\text{ dB}$), and Vibration surge ($\text{PSI} > 0.40$, Status: `CRITICAL`).
4. **`stuck_sensor`**: Simulates a frozen transducer at constant $72.10^\circ\text{C}$ with zero variance (Status: `CRITICAL`).
5. **`missing_data`**: Injects $25\%$ missing telemetry nulls (Status: `CRITICAL`).
6. **`prediction_drift`**: Simulates model RUL collapse down to $35\text{ days}$ (Status: `CRITICAL`).
7. **`reset`**: Clears all sandbox overrides and resumes live telemetry monitoring.

---

## 10. Retraining & Continuous Maintenance Workflow

When drift is detected, PredictX recommends a structured MLOps retraining workflow:

```
                      Drift Alert (WARNING / CRITICAL)
                                    │
                                    ▼
                     1. Data Quality Verification
                     • Check sensor wiring & transducers
                     • Confirm no stuck/frozen values or packet loss
                                    │
                                    ▼
                     2. Physical Regime Assessment
                     • Confirm whether machine entered a new valid load regime
                     • Or if mechanical wear requires physical repair
                                    │
                                    ▼
                     3. Human-in-the-Loop Review
                     • Plant maintenance engineer approves retraining
                                    │
                                    ▼
                     4. Pipeline Re-execution
                     • Run time_features.py, frequency_features.py, tsfresh_features.py
                     • Run ml_pipeline.py to retrain and benchmark models
                     • Rebuild reference baseline via POST /api/drift/baseline/rebuild
```
