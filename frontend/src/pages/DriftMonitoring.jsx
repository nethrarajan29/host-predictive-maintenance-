import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Activity,
  Cpu,
  Layers,
  Database,
  Sliders,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  Radio,
  FileCheck,
  Zap,
  Info
} from 'lucide-react';
import {
  getDriftSummary,
  getDriftHistory,
  getDriftAlerts,
  getDriftBaseline,
  getSensorReliability,
  postSimulateDrift,
  postTriggerDriftCheck,
  postRebuildBaseline
} from '../services/api';

const DriftMonitoring = ({ selectedPlc = 'PLC_01', plcsList = [], setSelectedPlc }) => {
  const [activeTab, setActiveTab] = useState('features');
  const [driftData, setDriftData] = useState(null);
  const [sensorRelData, setSensorRelData] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [alertsData, setAlertsData] = useState([]);
  const [baselineInfo, setBaselineInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeDemoMode, setActiveDemoMode] = useState('normal');
  const [actionMessage, setActionMessage] = useState(null);

  const fetchDriftState = async () => {
    try {
      setLoading(true);
      const [summary, hist, alerts, baseline, rel] = await Promise.all([
        getDriftSummary(selectedPlc).catch(() => null),
        getDriftHistory(selectedPlc, 30).catch(() => ({ history: [] })),
        getDriftAlerts(selectedPlc, 20).catch(() => ({ alerts: [] })),
        getDriftBaseline().catch(() => null),
        getSensorReliability(selectedPlc).catch(() => null)
      ]);

      if (summary) setDriftData(summary);
      if (hist && Array.isArray(hist.history)) setHistoryData(hist.history);
      if (alerts && Array.isArray(alerts.alerts)) setAlertsData(alerts.alerts);
      if (baseline) setBaselineInfo(baseline);
      if (rel) setSensorRelData(rel);
    } catch (err) {
      console.error('Error fetching drift state:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDriftState();
    const interval = setInterval(fetchDriftState, 4000);
    return () => clearInterval(interval);
  }, [selectedPlc]);

  const handleSimulateDemo = async (mode) => {
    try {
      setActionLoading(true);
      setActiveDemoMode(mode);
      const res = await postSimulateDrift(selectedPlc, mode);
      if (res && res.evaluation) {
        setDriftData(res.evaluation);
      }
      setActionMessage({
        type: 'success',
        text: `Sandbox mode '${mode.replace(/_/g, ' ')}' activated for ${selectedPlc}.`
      });
      setTimeout(() => setActionMessage(null), 4000);
      await fetchDriftState();
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: `Failed to set demo mode: ${err.message}`
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleTriggerCheck = async () => {
    try {
      setActionLoading(true);
      const res = await postTriggerDriftCheck(selectedPlc);
      if (res) setDriftData(res);
      setActionMessage({ type: 'success', text: 'On-demand drift evaluation completed.' });
      setTimeout(() => setActionMessage(null), 3000);
      await fetchDriftState();
    } catch (err) {
      console.error('Failed to trigger check:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRebuildBaseline = async () => {
    if (!window.confirm('Rebuild baseline distribution from historical sensor dataset? This will update reference quantile bins.')) {
      return;
    }
    try {
      setActionLoading(true);
      const res = await postRebuildBaseline();
      setActionMessage({ type: 'success', text: `Baseline rebuilt successfully (ID: ${res.baseline_id}).` });
      setTimeout(() => setActionMessage(null), 4000);
      await fetchDriftState();
    } catch (err) {
      setActionMessage({ type: 'error', text: `Baseline rebuild failed: ${err.message}` });
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500 text-white shadow-sm ring-1 ring-rose-600 animate-pulse">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>DRIFT DETECTED (CRITICAL)</span>
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500 text-white shadow-sm ring-1 ring-amber-600">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>DRIFT DETECTED (WARNING)</span>
          </span>
        );
      case 'INSUFFICIENT_DATA':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-slate-500 text-white shadow-sm ring-1 ring-slate-600">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>INSUFFICIENT DATA</span>
          </span>
        );
      case 'HEALTHY':
      case 'NORMAL':
      default:
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-600 text-white shadow-sm ring-1 ring-emerald-700">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>NORMAL</span>
          </span>
        );
    }
  };

  const getPsiTag = (psi) => {
    const val = parseFloat(psi || 0);
    if (val >= 0.25) {
      return <span className="text-rose-600 font-bold font-mono">PSI {val.toFixed(3)} (Critical)</span>;
    }
    if (val >= 0.10) {
      return <span className="text-amber-600 font-bold font-mono">PSI {val.toFixed(3)} (Moderate)</span>;
    }
    return <span className="text-emerald-600 font-bold font-mono">PSI {val.toFixed(3)} (Stable)</span>;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header & Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-gray-900 flex items-center space-x-2">
              <Activity className="w-6 h-6 text-blue-600" />
              <span>AI Reliability & Data/Model Drift Monitoring</span>
            </h1>
            {driftData && getStatusBadge(driftData.overall_status)}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Real-time statistical distribution tracking (PSI & KS-Test), prediction behavior shift, and telemetry data quality diagnostics.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* PLC Selector */}
          <div className="flex items-center space-x-2 bg-gray-50 p-1.5 rounded-lg border border-gray-200">
            <span className="text-xs font-semibold text-gray-500 pl-1">PLC:</span>
            <select
              value={selectedPlc}
              onChange={(e) => setSelectedPlc && setSelectedPlc(e.target.value)}
              className="bg-white border border-gray-300 text-xs font-bold rounded px-2.5 py-1 text-gray-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {plcsList && plcsList.length > 0 ? (
                plcsList.map((p) => (
                  <option key={p.plc_id} value={p.plc_id}>
                    {p.plc_id} ({p.name || 'Turbine Unit'})
                  </option>
                ))
              ) : (
                ['PLC_01', 'PLC_02', 'PLC_03', 'PLC_04', 'PLC_05'].map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))
              )}
            </select>
          </div>

          <button
            onClick={handleTriggerCheck}
            disabled={actionLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200 text-xs font-semibold hover:bg-blue-100 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
            <span>Evaluate Now</span>
          </button>

          <button
            onClick={handleRebuildBaseline}
            disabled={actionLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 border border-gray-200 text-xs font-semibold hover:bg-gray-200 transition disabled:opacity-50"
          >
            <Database className="w-3.5 h-3.5 text-gray-600" />
            <span>Rebuild Baseline</span>
          </button>
        </div>
      </div>

      {actionMessage && (
        <div
          className={`p-3 rounded-lg text-xs font-semibold border flex items-center justify-between ${
            actionMessage.type === 'error'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          <span>{actionMessage.text}</span>
          <button onClick={() => setActionMessage(null)} className="text-gray-400 hover:text-gray-600">
            &times;
          </button>
        </div>
      )}

      {/* Top 4 KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Data Drift */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">Data Drift (Inputs)</span>
            <Layers className="w-4 h-4 text-blue-500" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <div className="text-2xl font-black text-gray-900 font-mono">
              {driftData?.overall_drift_score !== undefined ? driftData.overall_drift_score.toFixed(3) : '0.000'}
            </div>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded ${
                driftData?.data_drift_status === 'CRITICAL'
                  ? 'bg-rose-100 text-rose-700'
                  : driftData?.data_drift_status === 'WARNING'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-emerald-100 text-emerald-700'
              }`}
            >
              {driftData?.data_drift_status || 'NORMAL'}
            </span>
          </div>
          <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
            <span>Drifted Features:</span>
            <span className="font-bold text-gray-800">
              {driftData?.drifted_features_count ?? 0} / {driftData?.total_features_monitored ?? 5}
            </span>
          </div>
        </div>

        {/* Card 2: Prediction Drift */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">Prediction Drift (Outputs)</span>
            <Cpu className="w-4 h-4 text-purple-500" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <div className="text-2xl font-black text-gray-900 font-mono">
              {driftData?.rul_psi !== undefined ? `PSI ${driftData.rul_psi.toFixed(3)}` : 'PSI 0.000'}
            </div>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded ${
                driftData?.prediction_drift_status === 'CRITICAL'
                  ? 'bg-rose-100 text-rose-700'
                  : driftData?.prediction_drift_status === 'WARNING'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-emerald-100 text-emerald-700'
              }`}
            >
              {driftData?.prediction_drift_status || 'NORMAL'}
            </span>
          </div>
          <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
            <span>Anomaly Output Rate:</span>
            <span className="font-bold text-gray-800">{driftData?.anomaly_rate_current ?? 0.0}%</span>
          </div>
        </div>

        {/* Card 3: Data Quality */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">Data Quality</span>
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <div className="text-2xl font-black text-gray-900 font-mono">
              {driftData?.missing_pct_overall !== undefined ? `${driftData.missing_pct_overall.toFixed(1)}%` : '0.0%'}
            </div>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded ${
                driftData?.data_quality_status === 'CRITICAL'
                  ? 'bg-rose-100 text-rose-700'
                  : driftData?.data_quality_status === 'WARNING'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-emerald-100 text-emerald-700'
              }`}
            >
              {driftData?.data_quality_status || 'NORMAL'}
            </span>
          </div>
          <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
            <span>Frozen / Stuck Sensors:</span>
            <span className="font-bold text-gray-800">{driftData?.stuck_sensors_count ?? 0}</span>
          </div>
        </div>

        {/* Card 4: Baseline Reference */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">Reference Baseline</span>
            <FileCheck className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-2 text-sm font-bold text-gray-900 truncate">
            {baselineInfo?.baseline_id || 'BL-ACTIVE'}
          </div>
          <div className="mt-1 text-xs text-gray-500 flex items-center justify-between">
            <span>Normal Samples:</span>
            <span className="font-bold text-gray-800 font-mono">{baselineInfo?.sample_count ?? 9125}</span>
          </div>
          <div className="mt-1 text-xs text-gray-400 truncate">
            Locked: {baselineInfo?.created_at || 'Historical Dataset'}
          </div>
        </div>
      </div>

      {/* Root Cause & Recommendation Banner */}
      <div className="bg-slate-900 text-white rounded-xl p-5 shadow-sm border border-slate-800 space-y-3">
        <div className="flex items-center space-x-2">
          <Info className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            System Reliability & Operational Diagnosis
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="bg-slate-800/80 p-3.5 rounded-lg border border-slate-700/80 space-y-1">
            <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Identified Root Cause:</span>
            <p className="text-slate-200 leading-relaxed font-medium">
              {driftData?.reason || 'All telemetry distributions and data quality metrics conform to reference baseline.'}
            </p>
          </div>
          <div className="bg-slate-800/80 p-3.5 rounded-lg border border-slate-700/80 space-y-1">
            <span className="text-blue-400 font-semibold uppercase tracking-wider text-[10px]">Actionable Recommendation:</span>
            <p className="text-slate-200 leading-relaxed font-medium">
              {driftData?.recommendation || 'No maintenance intervention or model retraining required. Continuous SCADA streaming normal.'}
            </p>
          </div>
        </div>
      </div>

      {/* Detail Navigation Tabs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 bg-gray-50/70 px-4 py-2 flex flex-wrap gap-2">
          {[
            { id: 'features', label: 'Feature Drift Matrix (PSI & KS)', icon: Layers },
            { id: 'predictions', label: 'Prediction Drift & Anomaly Trend', icon: Cpu },
            { id: 'quality', label: 'Data Quality & Stuck Transducers', icon: ShieldCheck },
            { id: 'history', label: 'Historical Drift Timeline', icon: Activity },
            { id: 'alerts', label: 'Reliability Alerts Log', icon: AlertTriangle },
            { id: 'sandbox', label: 'Demo Sandbox Controller', icon: Sliders }
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-bold transition ${
                  activeTab === tab.id
                    ? 'bg-white text-blue-700 shadow-sm border border-gray-200'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="p-5">
          {/* TAB 1: FEATURES MATRIX */}
          {activeTab === 'features' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-gray-900">Per-Sensor Distribution Shift & Statistical Tests</h3>
                <span className="text-xs text-gray-500 font-medium">
                  Evaluation Method: Population Stability Index (PSI) & 2-Sample Kolmogorov-Smirnov Test
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border border-gray-200 rounded-lg overflow-hidden">
                  <thead className="bg-gray-50 text-gray-600 font-bold uppercase tracking-wider border-b border-gray-200">
                    <tr>
                      <th className="py-2.5 px-3">Sensor Feature</th>
                      <th className="py-2.5 px-3">Baseline (Mean ± Std)</th>
                      <th className="py-2.5 px-3">Current Window (Mean ± Std)</th>
                      <th className="py-2.5 px-3">PSI Score</th>
                      <th className="py-2.5 px-3">KS p-value</th>
                      <th className="py-2.5 px-3">Wasserstein Dist</th>
                      <th className="py-2.5 px-3">Drift Status</th>
                      <th className="py-2.5 px-3">Physical Explanation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {driftData?.features && driftData.features.length > 0 ? (
                      driftData.features.map((f, idx) => (
                        <tr key={idx} className="hover:bg-gray-50/80 transition">
                          <td className="py-3 px-3 font-bold text-gray-900">{f.feature_name}</td>
                          <td className="py-3 px-3 font-mono text-gray-600">
                            {f.baseline_mean.toFixed(2)} ± {f.baseline_std.toFixed(2)}
                          </td>
                          <td className="py-3 px-3 font-mono text-gray-900 font-semibold">
                            {f.current_mean.toFixed(2)} ± {f.current_std.toFixed(2)}
                          </td>
                          <td className="py-3 px-3">{getPsiTag(f.psi_score)}</td>
                          <td className="py-3 px-3 font-mono text-gray-600">
                            p={f.ks_pvalue !== undefined ? f.ks_pvalue.toFixed(4) : '1.000'}
                          </td>
                          <td className="py-3 px-3 font-mono text-gray-600">
                            {f.wasserstein_distance !== undefined ? f.wasserstein_distance.toFixed(3) : '0.000'}
                          </td>
                          <td className="py-3 px-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                f.drift_status === 'CRITICAL'
                                  ? 'bg-rose-100 text-rose-700'
                                  : f.drift_status === 'WARNING'
                                  ? 'bg-amber-100 text-amber-700'
                                  : f.drift_status === 'INSUFFICIENT_DATA'
                                  ? 'bg-slate-200 text-slate-700'
                                  : 'bg-emerald-100 text-emerald-700'
                              }`}
                            >
                              {f.status_label || f.drift_status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-gray-600 text-[11px] max-w-xs">{f.explanation}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="8" className="py-6 text-center text-gray-400">
                          No feature drift data available for this PLC yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="bg-blue-50/60 p-3 rounded-lg border border-blue-100 text-xs text-blue-900 flex items-start space-x-2">
                <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Data Drift vs. Equipment Failure:</strong> PSI &lt; 0.10 indicates Normal distribution; 0.10 ≤ PSI &lt; 0.25 indicates moderate Drift Detected (Warning); PSI ≥ 0.25 indicates severe Drift Detected (Critical). Statistical data drift reflects a change in incoming sensor distributions (such as operating load changes, ambient shifts, or sensor calibration offset) and triggers investigation—it does not automatically prove physical equipment failure.
                </span>
              </div>
            </div>
          )}

          {/* TAB 2: PREDICTION DRIFT */}
          {activeTab === 'predictions' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-900">Machine Learning Output Behavior Drift</h3>
              <p className="text-xs text-gray-500">
                Monitors whether the downstream model's predictions (RUL regression and Isolation Forest anomaly flagging) have deviated from historical baseline distributions.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {driftData?.predictions && driftData.predictions.length > 0 ? (
                  driftData.predictions.map((p, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-xl p-4 border border-gray-200 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-gray-900 text-xs uppercase tracking-wide">{p.target_name}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-bold ${
                            p.drift_status === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-700'
                              : p.drift_status === 'WARNING'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {p.drift_status}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-white p-2.5 rounded-lg border border-gray-200">
                          <span className="text-gray-500 text-[10px] uppercase font-semibold">Baseline Mean</span>
                          <div className="text-lg font-bold text-gray-800 font-mono mt-0.5">
                            {p.baseline_mean.toFixed(1)} {p.target_name.includes('rul') ? 'Days' : '%'}
                          </div>
                        </div>
                        <div className="bg-white p-2.5 rounded-lg border border-gray-200">
                          <span className="text-gray-500 text-[10px] uppercase font-semibold">Current Window Mean</span>
                          <div className="text-lg font-bold text-blue-700 font-mono mt-0.5">
                            {p.current_mean.toFixed(1)} {p.target_name.includes('rul') ? 'Days' : '%'}
                          </div>
                        </div>
                      </div>

                      <div className="text-xs text-gray-600 bg-white p-2.5 rounded-lg border border-gray-200">
                        {p.details}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="col-span-2 text-center text-gray-400 py-6">No prediction drift records loaded.</div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: DATA QUALITY & SENSOR RELIABILITY */}
          {activeTab === 'quality' && (
            <div className="space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-gray-900">
                    Sensor Reliability & Data Quality Diagnostics ({selectedPlc})
                  </h3>
                  <p className="text-xs text-gray-500">
                    Evaluates missing readings, stale data, repeated/stuck values, abnormal spikes, and out-of-range readings. Prevents unreliable readings from silently contaminating ML predictions while preserving raw readings for audit.
                  </p>
                </div>
                {sensorRelData && (
                  <div className="flex items-center space-x-3 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 text-xs">
                    <span className="text-gray-600 font-medium">Overall Sensor Reliability Score:</span>
                    <span className="font-bold text-blue-700 font-mono text-sm">
                      {sensorRelData.overall_reliability_pct}% ({sensorRelData.reliability_grade})
                    </span>
                  </div>
                )}
              </div>

              {/* Per-Sensor Window Quality Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {driftData?.data_quality && driftData.data_quality.length > 0 ? (
                  driftData.data_quality.map((q, idx) => (
                    <div key={idx} className="bg-gray-50 rounded-xl p-4 border border-gray-200 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-bold text-gray-900 text-xs">{q.feature_name}</span>
                          <span className="ml-2 text-[10px] font-mono text-gray-500">({selectedPlc})</span>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            q.quality_status === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-700'
                              : q.quality_status === 'WARNING'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {q.quality_status}
                        </span>
                      </div>

                      <div className="space-y-1.5 text-xs text-gray-700">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Reliability Score:</span>
                          <span className="font-mono font-bold text-blue-700">
                            {q.reliability_score !== undefined ? `${q.reliability_score.toFixed(1)}%` : '98.5%'}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Missing Readings:</span>
                          <span className="font-mono font-semibold">
                            {q.missing_count ?? 0} ({q.missing_pct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Repeated / Stuck:</span>
                          <span className={`font-semibold ${q.is_stuck ? 'text-rose-600 font-bold' : 'text-emerald-600'}`}>
                            {q.is_stuck ? `STUCK (${q.stuck_value?.toFixed(2)})` : `Normal (${q.repeated_count ?? 1}x max)`}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Abnormal Spikes:</span>
                          <span className={`font-mono ${q.spike_count > 0 ? 'text-amber-700 font-bold' : ''}`}>
                            {q.spike_count ?? 0} event(s)
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Out-of-Range:</span>
                          <span className={`font-mono ${q.out_of_range_count > 0 ? 'text-rose-600 font-bold' : ''}`}>
                            {q.out_of_range_count} samples
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Comm / Stale Status:</span>
                          <span className={`font-semibold ${q.is_stale ? 'text-rose-600 font-bold' : 'text-emerald-600'}`}>
                            {q.is_stale ? 'STALE / TIMEOUT' : 'ACTIVE'}
                          </span>
                        </div>
                      </div>

                      <div className="text-[11px] text-gray-600 pt-1.5 border-t border-gray-200">
                        <strong>Why Flagged / Status:</strong> {q.issue_description}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="col-span-3 text-center text-gray-400 py-6">No data quality diagnostics available.</div>
                )}
              </div>

              {/* Raw vs. Validated Reading Audit & Fault vs. Degradation Attribution Table */}
              {sensorRelData?.sensors && sensorRelData.sensors.length > 0 && (
                <div className="space-y-3 pt-2">
                  <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                    Raw Reading Audit & Sensor Fault vs. Machine Degradation Attribution
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border border-gray-200 rounded-lg overflow-hidden">
                      <thead className="bg-gray-50 text-gray-600 font-bold uppercase tracking-wider border-b border-gray-200">
                        <tr>
                          <th className="py-2.5 px-3">PLC / Sensor</th>
                          <th className="py-2.5 px-3">Raw Reading (Audit)</th>
                          <th className="py-2.5 px-3">Validated Reading (ML Safe)</th>
                          <th className="py-2.5 px-3">Physical Bounds</th>
                          <th className="py-2.5 px-3">Reliability Score</th>
                          <th className="py-2.5 px-3">Attribution (Sensor Fault vs. Machine Wear)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {sensorRelData.sensors.map((s, idx) => (
                          <tr key={idx} className="hover:bg-gray-50/80 transition">
                            <td className="py-2.5 px-3">
                              <div className="font-bold text-gray-900">{s.sensor_name}</div>
                              <div className="text-[10px] font-mono text-gray-500">{s.plc_id} • {s.channel_id}</div>
                            </td>
                            <td className="py-2.5 px-3 font-mono text-gray-700">
                              {s.raw_reading} {s.unit}
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-blue-700">
                              {s.validated_reading} {s.unit}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-gray-500">
                              [{s.lower_bound} – {s.upper_bound}] {s.unit}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="font-mono font-bold text-gray-900">{s.base_reliability}%</span>
                              <span className="ml-1.5 text-[10px] text-gray-500">({s.snr_db} dB SNR)</span>
                            </td>
                            <td className="py-2.5 px-3 text-[11px] text-gray-700 max-w-md">
                              <div className="font-semibold text-gray-900">{s.diagnosis_type?.replace(/_/g, ' ')}</div>
                              <div className="text-gray-600">{s.distinction_explanation}</div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="bg-amber-50/70 p-3 rounded-lg border border-amber-200 text-xs text-amber-900 flex items-start space-x-2">
                    <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <span>
                      <strong>Evidence & Safe Prediction Policy:</strong> {sensorRelData.methodology_note}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: HISTORICAL TIMELINE */}
          {activeTab === 'history' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-900">Chronological Reliability History ({selectedPlc})</h3>

              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-left text-xs border border-gray-200 rounded-lg overflow-hidden">
                  <thead className="bg-gray-50 text-gray-600 font-bold uppercase tracking-wider sticky top-0">
                    <tr>
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3">Overall Status</th>
                      <th className="py-2.5 px-3">Data Drift Score (PSI)</th>
                      <th className="py-2.5 px-3">Drifted Feats</th>
                      <th className="py-2.5 px-3">RUL PSI</th>
                      <th className="py-2.5 px-3">Missing %</th>
                      <th className="py-2.5 px-3">Reason / Insight</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {historyData && historyData.length > 0 ? (
                      historyData.map((h, idx) => (
                        <tr key={idx} className="hover:bg-gray-50/80 transition">
                          <td className="py-2 px-3 font-mono text-gray-600">{h.timestamp}</td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                h.overall_status === 'CRITICAL'
                                  ? 'bg-rose-100 text-rose-700'
                                  : h.overall_status === 'WARNING'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-emerald-100 text-emerald-700'
                              }`}
                            >
                              {h.overall_status}
                            </span>
                          </td>
                          <td className="py-2 px-3 font-mono font-bold text-gray-800">
                            {h.overall_drift_score?.toFixed(3) ?? '0.000'}
                          </td>
                          <td className="py-2 px-3 font-mono">{h.drifted_features_count ?? 0}</td>
                          <td className="py-2 px-3 font-mono">{h.rul_psi?.toFixed(3) ?? '0.000'}</td>
                          <td className="py-2 px-3 font-mono">{h.missing_pct_overall?.toFixed(1) ?? '0.0'}%</td>
                          <td className="py-2 px-3 text-gray-600 text-[11px] truncate max-w-sm">{h.reason}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="7" className="py-6 text-center text-gray-400">
                          No historical runs logged yet. Runs will accumulate automatically as telemetry streams.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 5: ALERTS LOG */}
          {activeTab === 'alerts' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-gray-900">Drift & Reliability Alert Events</h3>

              <div className="space-y-2.5 max-h-96 overflow-y-auto">
                {alertsData && alertsData.length > 0 ? (
                  alertsData.map((a, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border text-xs flex items-start justify-between gap-3 ${
                        a.severity === 'CRITICAL'
                          ? 'bg-rose-50/70 border-rose-200'
                          : 'bg-amber-50/70 border-amber-200'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              a.severity === 'CRITICAL' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                            }`}
                          >
                            {a.severity}
                          </span>
                          <span className="font-bold text-gray-900">{a.title}</span>
                          <span className="text-gray-400 font-mono text-[10px]">{a.timestamp}</span>
                        </div>
                        <p className="text-gray-700">{a.message}</p>
                        {a.recommendation && (
                          <p className="text-blue-700 font-medium text-[11px]">Action: {a.recommendation}</p>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-gray-400 py-8 bg-gray-50 rounded-lg border border-dashed border-gray-200">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                    <p className="text-xs font-semibold text-gray-700">No Active Reliability Alerts</p>
                    <p className="text-[11px] text-gray-400">All monitored assets within nominal statistical thresholds.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 6: DEMO SANDBOX CONTROLLER */}
          {activeTab === 'sandbox' && (
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 space-y-1">
                <div className="flex items-center space-x-2 font-bold">
                  <Sliders className="w-4 h-4 text-amber-600" />
                  <span>Interactive Review Demonstration Sandbox</span>
                </div>
                <p className="text-amber-800">
                  Use this sandbox panel to demonstrate controlled distribution shifts for review and evaluation. These tests operate exclusively on active evaluation windows without corrupting reference baseline weights.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <button
                  onClick={() => handleSimulateDemo('normal')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'normal'
                      ? 'bg-emerald-50 border-emerald-400 ring-2 ring-emerald-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>1. Normal Baseline State</span>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Conforms to normal operating baseline. Health status: HEALTHY.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('mild_vibration_drift')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'mild_vibration_drift'
                      ? 'bg-amber-50 border-amber-400 ring-2 ring-amber-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>2. Mild Vibration Drift</span>
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Shifts Vibration RMS from 0.20 to ~0.55 mm/s. Status: WARNING.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('severe_thermal_drift')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'severe_thermal_drift'
                      ? 'bg-rose-50 border-rose-400 ring-2 ring-rose-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>3. Severe Thermal Drift</span>
                    <ShieldAlert className="w-4 h-4 text-rose-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Multi-feature surge (Temp 95°C, Noise 75dB, Vib 0.85). Status: CRITICAL.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('stuck_sensor')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'stuck_sensor'
                      ? 'bg-rose-50 border-rose-400 ring-2 ring-rose-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>4. Frozen / Stuck Sensor</span>
                    <Zap className="w-4 h-4 text-purple-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Simulates zero variance transducer at 72.10°C. Status: CRITICAL.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('missing_data')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'missing_data'
                      ? 'bg-rose-50 border-rose-400 ring-2 ring-rose-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>5. High Packet Loss / Nulls</span>
                    <XCircle className="w-4 h-4 text-rose-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Injects 25% missing telemetry nulls. Status: CRITICAL.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('prediction_drift')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'prediction_drift'
                      ? 'bg-purple-50 border-purple-400 ring-2 ring-purple-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>6. Model Prediction Drift</span>
                    <Cpu className="w-4 h-4 text-purple-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Simulates collapse in predicted RUL days and anomaly flags. Status: CRITICAL.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('abnormal_spike')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'abnormal_spike'
                      ? 'bg-amber-50 border-amber-400 ring-2 ring-amber-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>7. Abnormal Sensor Spike</span>
                    <Activity className="w-4 h-4 text-amber-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Injects sudden transient step spikes on Vibration &amp; Current. Status: WARNING.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('out_of_range')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'out_of_range'
                      ? 'bg-rose-50 border-rose-400 ring-2 ring-rose-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>8. Out-of-Range Transducer</span>
                    <AlertTriangle className="w-4 h-4 text-rose-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Injects readings outside physical bounds (185°C, 18.5 bar). Status: CRITICAL.</p>
                </button>

                <button
                  onClick={() => handleSimulateDemo('insufficient_data')}
                  disabled={actionLoading}
                  className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                    activeDemoMode === 'insufficient_data'
                      ? 'bg-slate-100 border-slate-400 ring-2 ring-slate-500'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-bold text-xs text-gray-900 flex items-center justify-between">
                    <span>9. Insufficient Data Window</span>
                    <HelpCircle className="w-4 h-4 text-slate-600" />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">Simulates cold-start window (&lt; 5 samples). Status: INSUFFICIENT DATA.</p>
                </button>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => handleSimulateDemo('reset')}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-lg bg-gray-900 text-white text-xs font-bold hover:bg-black transition"
                >
                  Reset All Demonstration Overrides
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DriftMonitoring;
