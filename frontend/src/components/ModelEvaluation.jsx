import React, { useState } from 'react';
import Plot from 'react-plotly.js';
import { Sparkles, Cpu, BarChart2, TrendingUp, Layers, CheckCircle2, Award, Zap, Activity } from 'lucide-react';

const ModelEvaluation = ({ modelData }) => {
  const [activeTab, setActiveTab] = useState('classification'); // 'classification' | 'rul'

  const metrics = modelData || {};
  const mlClassification = metrics.mlClassification || {};
  const featuresSummary = metrics.featuresSummary || {};

  const {
    algorithm = 'Random Forest Regressor',
    mae = 27.19,
    rmse = 37.67,
    r2_score = 0.8746,
    dataset_size = 91250,
    train_size = 73000,
    test_size = 18250,
    feature_importance = [
      { feature: 'Vibration', importance: 0.42 },
      { feature: 'Temperature', importance: 0.28 },
      { feature: 'Motor_Current', importance: 0.16 },
      { feature: 'Pressure', importance: 0.09 },
      { feature: 'Noise', importance: 0.05 },
    ],
    scatter_plot = { actual: [50, 100, 150, 200, 250], predicted: [49, 102, 148, 203, 247] },
    residuals = [-1, 2, -2, 3, -3, 0, 1, -1, 2],
  } = metrics;

  // Multi-Model Anomaly Classification Benchmark metrics
  const benchmarkModels = mlClassification.models_benchmarked || {
    'Random Forest Classifier': {
      accuracy: 0.9565,
      precision: 0.9661,
      recall: 0.9500,
      f1_score: 0.9580,
      roc_auc: 0.9976,
      cv_accuracy_mean: 0.9870,
      cv_accuracy_std: 0.0106,
      confusion_matrix: [[53, 2], [3, 57]]
    },
    'Gradient Boosting Classifier': {
      accuracy: 0.9652,
      precision: 0.9667,
      recall: 0.9667,
      f1_score: 0.9667,
      roc_auc: 0.9648,
      cv_accuracy_mean: 0.9891,
      cv_accuracy_std: 0.0069,
      confusion_matrix: [[53, 2], [2, 58]]
    },
    'Baseline (Logistic Regression)': {
      accuracy: 0.9652,
      precision: 0.9667,
      recall: 0.9667,
      f1_score: 0.9667,
      roc_auc: 0.9942,
      cv_accuracy_mean: 0.9826,
      cv_accuracy_std: 0.0163,
      confusion_matrix: [[53, 2], [2, 58]]
    }
  };

  const cleanDomainLabel = (label = '') => {
    const str = String(label).replace(/\s*\(Person\s*\d+[^)]*\)/gi, '').trim();
    if (str.toLowerCase().includes('time')) return 'Time-Domain Analysis';
    if (str.toLowerCase().includes('freq') || str.toLowerCase().includes('fft')) return 'Frequency-Domain Analysis (FFT)';
    if (str.toLowerCase().includes('tsfresh')) return 'TSFresh Feature Engineering';
    return str || 'Sensor Domain';
  };

  const rawDomainShares = mlClassification.domain_importance_share_percent || {
    'Time-Domain Analysis': 61.98,
    'Frequency-Domain Analysis (FFT)': 26.81,
    'TSFresh Feature Engineering': 11.20
  };

  const domainShares = Object.entries(rawDomainShares).reduce((acc, [key, val]) => {
    acc[cleanDomainLabel(key)] = val;
    return acc;
  }, {});

  const rawTop10Features = mlClassification.top_10_features || [
    { feature: 'TIME__Noise__max', domain: 'Time-Domain Analysis', importance: 0.0909 },
    { feature: 'FREQ__Noise__mean_power_spectrum', domain: 'Frequency-Domain Analysis (FFT)', importance: 0.0779 },
    { feature: 'FREQ__Motor_Current__fft_peak_amplitude', domain: 'Frequency-Domain Analysis (FFT)', importance: 0.0493 },
    { feature: 'TIME__Noise__peak_to_peak', domain: 'Time-Domain Analysis', importance: 0.0492 },
    { feature: 'TIME__Noise__std', domain: 'Time-Domain Analysis', importance: 0.0394 },
    { feature: 'TIME__Motor_Current__max', domain: 'Time-Domain Analysis', importance: 0.0391 },
    { feature: 'TIME__Motor_Current__std', domain: 'Time-Domain Analysis', importance: 0.0387 },
    { feature: 'TIME__Noise__shape_factor', domain: 'Time-Domain Analysis', importance: 0.0296 },
    { feature: 'FREQ__Motor_Current__spectral_energy', domain: 'Frequency-Domain Analysis (FFT)', importance: 0.0293 },
    { feature: 'TSFRESH__Motor_Current__fft_aggregated__skew', domain: 'TSFresh Feature Engineering', importance: 0.0293 }
  ];

  const top10Features = rawTop10Features.map((f) => ({
    ...f,
    domain: cleanDomainLabel(f.domain)
  }));

  const rfConfusion = benchmarkModels['Random Forest Classifier']?.confusion_matrix || [[53, 2], [3, 57]];

  return (
    <div className="space-y-6">
      {/* Tab Switcher */}
      <div className="flex space-x-2 border-b border-gray-200 pb-3">
        <button
          onClick={() => setActiveTab('classification')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'classification'
              ? 'bg-blue-600 text-white shadow'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          🏆 Multi-Domain Anomaly Classification (Time + FFT + TSFresh)
        </button>
        <button
          onClick={() => setActiveTab('rul')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'rul'
              ? 'bg-blue-600 text-white shadow'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          ⏱️ RUL Regression Model (Random Forest 365-Day Lifespan)
        </button>
      </div>

      {activeTab === 'classification' ? (
        <div className="space-y-6">
          {/* Technical Feature Engineering & Model Architecture Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <span className="text-[10px] font-bold tracking-wider text-blue-700 uppercase block">Statistical Telemetry</span>
              <h3 className="text-sm font-bold text-gray-900 mt-1">Time-Domain Analysis</h3>
              <p className="text-xs text-gray-600 mt-1">65 Statistical Metrics (Mean, RMS, Crest Factor, Skewness, Kurtosis)</p>
              <div className="mt-3 text-xs font-semibold text-blue-800 bg-white/80 py-1 px-2 rounded border border-blue-100 inline-block">
                Importance Share: <strong>62.0%</strong>
              </div>
            </div>

            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
              <span className="text-[10px] font-bold tracking-wider text-emerald-700 uppercase block">Spectral Decomposition</span>
              <h3 className="text-sm font-bold text-gray-900 mt-1">Frequency-Domain Analysis (FFT)</h3>
              <p className="text-xs text-gray-600 mt-1">45 Spectral Metrics (FFT Peak, Dominant Freq, Spectral Energy, PSD)</p>
              <div className="mt-3 text-xs font-semibold text-emerald-800 bg-white/80 py-1 px-2 rounded border border-emerald-100 inline-block">
                Importance Share: <strong>26.8%</strong>
              </div>
            </div>

            <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
              <span className="text-[10px] font-bold tracking-wider text-purple-700 uppercase block">Automated Extraction</span>
              <h3 className="text-sm font-bold text-gray-900 mt-1">TSFresh Feature Engineering</h3>
              <p className="text-xs text-gray-600 mt-1">25 Top FDR-Selected Features (FFT Skewness, Complexity, Recurrence)</p>
              <div className="mt-3 text-xs font-semibold text-purple-800 bg-white/80 py-1 px-2 rounded border border-purple-100 inline-block">
                Importance Share: <strong>11.2%</strong>
              </div>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <span className="text-[10px] font-bold tracking-wider text-amber-700 uppercase block">Ensemble Classification</span>
              <h3 className="text-sm font-bold text-gray-900 mt-1">Model Integration & Benchmarking</h3>
              <p className="text-xs text-gray-600 mt-1">135 Fused Features across 575 Windows, Multi-Model Benchmark</p>
              <div className="mt-3 text-xs font-semibold text-amber-800 bg-white/80 py-1 px-2 rounded border border-amber-100 inline-block">
                Best Test Acc: <strong>96.5%</strong>
              </div>
            </div>
          </div>

          {/* Benchmark Table */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-gray-200 mb-4">
              <div>
                <h3 className="text-sm font-bold text-gray-900">Multi-Model Anomaly Classification Benchmark</h3>
                <p className="text-xs text-gray-500">Evaluated on 115 holdout windows (55 Normal vs. 60 Anomalous)</p>
              </div>
              <span className="bg-emerald-100 text-emerald-800 text-xs font-bold px-3 py-1 rounded-full border border-emerald-300 flex items-center gap-1">
                <Award className="w-3.5 h-3.5" /> Best Model: Random Forest (ROC-AUC = 0.9976)
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider border-b border-gray-200">
                  <tr>
                    <th className="py-2.5 px-3">Model Architecture</th>
                    <th className="py-2.5 px-3">Accuracy</th>
                    <th className="py-2.5 px-3">Precision</th>
                    <th className="py-2.5 px-3">Recall</th>
                    <th className="py-2.5 px-3">F1-Score</th>
                    <th className="py-2.5 px-3">ROC-AUC</th>
                    <th className="py-2.5 px-3">5-Fold CV Accuracy</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {Object.entries(benchmarkModels).map(([mName, res]) => (
                    <tr key={mName} className={mName.includes('Random Forest') ? 'bg-blue-50/40 font-semibold' : ''}>
                      <td className="py-2.5 px-3 text-gray-900 flex items-center gap-1.5">
                        {mName.includes('Random Forest') && <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />}
                        {mName}
                      </td>
                      <td className="py-2.5 px-3 text-emerald-700 font-bold">{(res.accuracy * 100).toFixed(2)}%</td>
                      <td className="py-2.5 px-3">{(res.precision * 100).toFixed(2)}%</td>
                      <td className="py-2.5 px-3">{(res.recall * 100).toFixed(2)}%</td>
                      <td className="py-2.5 px-3 font-bold text-blue-700">{(res.f1_score * 100).toFixed(2)}%</td>
                      <td className="py-2.5 px-3 font-bold text-purple-700">{res.roc_auc.toFixed(4)}</td>
                      <td className="py-2.5 px-3 text-gray-600">
                        {(res.cv_accuracy_mean * 100).toFixed(2)}% ± {(res.cv_accuracy_std * 100).toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Visualizations: Confusion Matrix & Domain Share */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Confusion Matrix */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider pb-3 border-b border-gray-200 mb-4">
                Random Forest Confusion Matrix (Holdout Test Set)
              </h3>
              <div className="flex flex-col items-center justify-center p-4">
                <div className="grid grid-cols-2 gap-3 w-full max-w-xs">
                  <div className="bg-emerald-50 border-2 border-emerald-400 p-4 rounded-xl text-center">
                    <span className="text-[10px] text-emerald-700 font-bold uppercase tracking-wider block">True Normal</span>
                    <span className="text-2xl font-black text-emerald-900 mt-1 block">{rfConfusion[0][0]}</span>
                    <span className="text-[10px] text-emerald-600">96.4% Correct</span>
                  </div>
                  <div className="bg-amber-50 border-2 border-amber-300 p-4 rounded-xl text-center">
                    <span className="text-[10px] text-amber-700 font-bold uppercase tracking-wider block">False Alarm (FP)</span>
                    <span className="text-2xl font-black text-amber-900 mt-1 block">{rfConfusion[0][1]}</span>
                    <span className="text-[10px] text-amber-600">3.6% Error</span>
                  </div>
                  <div className="bg-red-50 border-2 border-red-300 p-4 rounded-xl text-center">
                    <span className="text-[10px] text-red-700 font-bold uppercase tracking-wider block">Missed Anomaly (FN)</span>
                    <span className="text-2xl font-black text-red-900 mt-1 block">{rfConfusion[1][0]}</span>
                    <span className="text-[10px] text-red-600">5.0% Error</span>
                  </div>
                  <div className="bg-blue-50 border-2 border-blue-400 p-4 rounded-xl text-center">
                    <span className="text-[10px] text-blue-700 font-bold uppercase tracking-wider block">True Anomaly</span>
                    <span className="text-2xl font-black text-blue-900 mt-1 block">{rfConfusion[1][1]}</span>
                    <span className="text-[10px] text-blue-600">95.0% Correct</span>
                  </div>
                </div>
                <p className="text-[11px] text-gray-500 mt-4 text-center">
                  Balanced performance: High anomaly sensitivity (95.0% Recall) and minimal false alarms (96.4% Specificity).
                </p>
              </div>
            </div>

            {/* Domain Share Pie Chart */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider pb-3 border-b border-gray-200 mb-2">
                Cross-Domain Feature Contribution
              </h3>
              <div className="w-full h-64">
                <Plot
                  data={[
                    {
                      values: Object.values(domainShares),
                      labels: Object.keys(domainShares),
                      type: 'pie',
                      hole: 0.55,
                      marker: {
                        colors: ['#3B82F6', '#10B981', '#8B5CF6']
                      },
                      textinfo: 'label+percent',
                      textposition: 'outside',
                      hoverinfo: 'label+percent+value',
                    }
                  ]}
                  layout={{
                    autosize: true,
                    height: 240,
                    margin: { l: 20, r: 20, t: 10, b: 20 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    showlegend: false
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
              <p className="text-[11px] text-gray-500 text-center">
                Time-Domain statistics capture baseline shifts (62.0%), while Frequency FFT metrics (26.8%) capture acoustic & vibrational harmonics.
              </p>
            </div>
          </div>

          {/* Top 10 Features Table */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider pb-3 border-b border-gray-200 mb-4">
              Top 10 Most Discriminative Engineered Features Overall
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider border-b border-gray-200">
                  <tr>
                    <th className="py-2.5 px-3">Rank</th>
                    <th className="py-2.5 px-3">Feature Name</th>
                    <th className="py-2.5 px-3">Feature Domain</th>
                    <th className="py-2.5 px-3">Relative Importance (MDI)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {top10Features.map((f, idx) => (
                    <tr key={f.feature} className="hover:bg-gray-50">
                      <td className="py-2 px-3 font-bold text-gray-700">#{idx + 1}</td>
                      <td className="py-2 px-3 font-mono text-[11px] text-blue-800">{f.feature}</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          f.domain.includes('Time') ? 'bg-blue-100 text-blue-800' :
                          f.domain.includes('Frequency') ? 'bg-emerald-100 text-emerald-800' :
                          'bg-purple-100 text-purple-800'
                        }`}>
                          {f.domain}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-bold text-gray-900">
                        {typeof f.importance === 'number' ? f.importance.toFixed(4) : f.importance}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* RUL Regression Diagnostics (Existing View) */
        <div className="space-y-6">
          <div className="industrial-card p-6 bg-white shadow-sm border border-gray-200 rounded-xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-gray-200 mb-6 gap-4">
              <div className="flex items-center space-x-3">
                <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
                  <Cpu className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900">Random Forest RUL Prediction Model</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Trained & evaluated on 91,250-record dataset (80/20 train/test split, 5 sensor features)
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg text-emerald-800 text-xs font-semibold">
                <Sparkles className="w-4 h-4 text-emerald-600" />
                <span>Algorithm: <strong>Random Forest Regressor</strong></span>
              </div>
            </div>

            {/* KPI Cards for Random Forest */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200">
                <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">Active Algorithm</span>
                <span className="text-xs font-bold text-gray-900 mt-1 block truncate">Random Forest</span>
              </div>

              <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200">
                <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">Dataset Size</span>
                <span className="text-base font-bold text-gray-900 mt-1 block">{(dataset_size || 91250).toLocaleString()} rows</span>
              </div>

              <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200">
                <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">Train/Test Split</span>
                <span className="text-base font-bold text-gray-900 mt-1 block">{(train_size || 73000).toLocaleString()} / {(test_size || 18250).toLocaleString()}</span>
              </div>

              <div className="bg-blue-50/60 p-3.5 rounded-lg border border-blue-200">
                <span className="text-[11px] font-bold text-blue-700 uppercase tracking-wider block">MAE</span>
                <span className="text-xl font-bold text-blue-900 mt-1 block">
                  {typeof mae === 'number' ? mae.toFixed(2) : mae} <span className="text-xs font-normal text-blue-600">Days</span>
                </span>
              </div>

              <div className="bg-blue-50/60 p-3.5 rounded-lg border border-blue-200">
                <span className="text-[11px] font-bold text-blue-700 uppercase tracking-wider block">RMSE</span>
                <span className="text-xl font-bold text-blue-900 mt-1 block">
                  {typeof rmse === 'number' ? rmse.toFixed(2) : rmse} <span className="text-xs font-normal text-blue-600">Days</span>
                </span>
              </div>

              <div className="bg-emerald-50/60 p-3.5 rounded-lg border border-emerald-200">
                <span className="text-[11px] font-bold text-emerald-700 uppercase tracking-wider block">R² Score</span>
                <span className="text-xl font-bold text-emerald-900 mt-1 block">
                  {typeof r2_score === 'number' ? r2_score.toFixed(4) : r2_score}
                </span>
              </div>
            </div>
          </div>

          {/* 3 Diagnostic Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="industrial-card p-4 bg-white shadow-sm border border-gray-200">
              <div className="flex items-center space-x-2 pb-3 border-b border-gray-200 mb-2">
                <BarChart2 className="w-4 h-4 text-blue-600" />
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Feature Importance (RUL Regressor)
                </h3>
              </div>
              <div className="w-full h-64">
                <Plot
                  data={[
                    {
                      x: (feature_importance || []).map((f) => f.importance),
                      y: (feature_importance || []).map((f) => f.feature),
                      type: 'bar',
                      orientation: 'h',
                      marker: { color: '#2563EB' },
                    },
                  ]}
                  layout={{
                    autosize: true,
                    height: 240,
                    margin: { l: 100, r: 20, t: 10, b: 35 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: '#FAFAFA',
                    xaxis: { title: { text: 'Relative Importance Score', font: { size: 10, color: '#6B7280' } }, gridcolor: '#F3F4F6' },
                    yaxis: { automargin: true, font: { size: 11, color: '#111827' } },
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
            </div>

            <div className="industrial-card p-4 bg-white shadow-sm border border-gray-200">
              <div className="flex items-center space-x-2 pb-3 border-b border-gray-200 mb-2">
                <TrendingUp className="w-4 h-4 text-blue-600" />
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Prediction vs Actual (RUL Regressor)
                </h3>
              </div>
              <div className="w-full h-64">
                <Plot
                  data={[
                    {
                      x: scatter_plot?.actual || [],
                      y: scatter_plot?.predicted || [],
                      mode: 'markers',
                      type: 'scatter',
                      marker: { color: '#2563EB', size: 6, opacity: 0.7 },
                      name: 'Test Holdout',
                    },
                    {
                      x: [0, 365],
                      y: [0, 365],
                      mode: 'lines',
                      type: 'scatter',
                      line: { color: '#EF4444', dash: 'dash', width: 1.5 },
                      name: 'Ideal Fit (1:1)',
                    },
                  ]}
                  layout={{
                    autosize: true,
                    height: 240,
                    margin: { l: 45, r: 15, t: 10, b: 35 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: '#FAFAFA',
                    xaxis: { title: { text: 'Actual RUL (Days)', font: { size: 10, color: '#6B7280' } }, gridcolor: '#F3F4F6' },
                    yaxis: { title: { text: 'Predicted RUL (Days)', font: { size: 10, color: '#6B7280' } }, gridcolor: '#F3F4F6' },
                    legend: { orientation: 'h', y: 1.15, x: 1, xanchor: 'right', font: { size: 10 } },
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
            </div>

            <div className="industrial-card p-4 bg-white shadow-sm border border-gray-200">
              <div className="flex items-center space-x-2 pb-3 border-b border-gray-200 mb-2">
                <Layers className="w-4 h-4 text-blue-600" />
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Residual Error Distribution (RUL Regressor)
                </h3>
              </div>
              <div className="w-full h-64">
                <Plot
                  data={[
                    {
                      x: residuals || [],
                      type: 'histogram',
                      marker: { color: '#22C55E' },
                      opacity: 0.85,
                    },
                  ]}
                  layout={{
                    autosize: true,
                    height: 240,
                    margin: { l: 45, r: 15, t: 10, b: 35 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: '#FAFAFA',
                    xaxis: { title: { text: 'Residual Error (Actual - Pred in Days)', font: { size: 10, color: '#6B7280' } }, gridcolor: '#F3F4F6' },
                    yaxis: { title: { text: 'Frequency', font: { size: 10, color: '#6B7280' } }, gridcolor: '#F3F4F6' },
                  }}
                  useResizeHandler={true}
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: false, responsive: true }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelEvaluation;
