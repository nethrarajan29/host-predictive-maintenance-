import React, { useState, useEffect, useCallback } from 'react';
import {
  Cpu,
  Activity,
  Layers,
  Wrench,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronRight,
  ShieldCheck,
  RefreshCw,
  Sliders,
  Filter,
  ArrowRight,
  PlusCircle,
  FileCheck,
  Zap,
  Gauge,
  Thermometer,
  Radio,
  ExternalLink,
  HelpCircle,
  X
} from 'lucide-react';
import {
  getAssets,
  getAssetHealth,
  getAssetTimeline,
  getAssetMaintenance,
  postAssetMaintenance,
  postAssetMaintenanceOutcome,
} from '../services/api';

export default function DigitalThread({ selectedPlc = 'PLC_01', plcsList = [] }) {
  // Asset state
  const [assets, setAssets] = useState([]);
  const [selectedAssetId, setSelectedAssetId] = useState('COMP-001');
  const [healthSnapshot, setHealthSnapshot] = useState(null);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [maintenanceRecords, setMaintenanceRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Timeline filters
  const [timelineFilter, setTimelineFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');

  // Modals state
  const [showMaintModal, setShowMaintModal] = useState(false);
  const [showOutcomeModal, setShowOutcomeModal] = useState(false);
  const [targetMaintId, setTargetMaintId] = useState(null);

  // Form states for new maintenance
  const [maintForm, setMaintForm] = useState({
    maintenance_type: 'Preventive Bearing Lubrication & Alignment',
    reason: 'Condition-based maintenance trigger from AI reliability engine',
    triggered_by: 'Predictive Maintenance Engine',
    technician: 'Lead PDM Specialist Marcus V.',
    finding: 'Slight lubricant breakdown and minor high-frequency vibration harmonic',
    action_performed: 'Flushed bearing cavity, replaced with synthetic high-grade grease, performed dynamic rotor balance',
    parts_replaced: 'Synthetic Grease SHC 100, Viton Seal Pack',
    downtime_hours: 2.0,
    cost: 450.0,
    before_health: 75.0,
    before_rul: 60,
    notes: 'Service completed on schedule. Awaiting closed-loop operational verification.',
  });

  // Form states for outcome recording
  const [outcomeForm, setOutcomeForm] = useState({
    after_health: 98.0,
    after_rul: 240,
    notes: 'Post-service baseline verified: vibration dropped to 0.18 mm/s, temperature stable at 62.0°C.',
    status: 'COMPLETED',
  });

  // Fetch all assets on mount
  useEffect(() => {
    async function loadAssetsCatalog() {
      try {
        const res = await getAssets();
        if (res && res.assets && res.assets.length > 0) {
          setAssets(res.assets);
          // Match with passed selectedPlc if possible
          const matched = res.assets.find((a) => a.plc_id === selectedPlc);
          if (matched) {
            setSelectedAssetId(matched.asset_id);
          } else {
            setSelectedAssetId(res.assets[0].asset_id);
          }
        }
      } catch (err) {
        console.error('Failed to load assets catalog:', err);
      }
    }
    loadAssetsCatalog();
  }, [selectedPlc]);

  // Fetch full digital thread details for the selected asset
  const fetchThreadData = useCallback(async (assetId = selectedAssetId) => {
    if (!assetId) return;
    try {
      setRefreshing(true);
      const [hRes, tRes, mRes] = await Promise.all([
        getAssetHealth(assetId).catch(() => null),
        getAssetTimeline(assetId, timelineFilter, severityFilter, 100).catch(() => null),
        getAssetMaintenance(assetId).catch(() => null),
      ]);

      if (hRes) setHealthSnapshot(hRes);
      if (tRes && tRes.events) setTimelineEvents(tRes.events);
      if (mRes && mRes.maintenance_records) setMaintenanceRecords(mRes.maintenance_records);
    } catch (err) {
      console.error('Error fetching digital thread details:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedAssetId, timelineFilter, severityFilter]);

  useEffect(() => {
    fetchThreadData(selectedAssetId);
    const interval = setInterval(() => {
      fetchThreadData(selectedAssetId);
    }, 4000);
    return () => clearInterval(interval);
  }, [fetchThreadData, selectedAssetId]);

  // Handle Maintenance Submission
  const handleCreateMaintenance = async (e) => {
    e.preventDefault();
    try {
      await postAssetMaintenance(selectedAssetId, maintForm);
      setShowMaintModal(false);
      await fetchThreadData(selectedAssetId);
    } catch (err) {
      alert(`Failed to log maintenance: ${err.message}`);
    }
  };

  // Handle Outcome Submission
  const handleRecordOutcome = async (e) => {
    e.preventDefault();
    if (!targetMaintId) return;
    try {
      await postAssetMaintenanceOutcome(selectedAssetId, targetMaintId, outcomeForm);
      setShowOutcomeModal(false);
      setTargetMaintId(null);
      await fetchThreadData(selectedAssetId);
    } catch (err) {
      alert(`Failed to record outcome: ${err.message}`);
    }
  };

  const getSeverityBadge = (sev) => {
    const s = String(sev || '').toUpperCase();
    if (s === 'CRITICAL') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-700 border border-red-300">CRITICAL</span>;
    }
    if (s === 'WARNING') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-300">WARNING</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700 border border-blue-200">INFO</span>;
  };

  const getEventTypeIcon = (type) => {
    const t = String(type || '').toUpperCase();
    switch (t) {
      case 'ANOMALY':
        return <AlertTriangle className="w-4 h-4 text-amber-600" />;
      case 'DRIFT':
        return <Activity className="w-4 h-4 text-purple-600" />;
      case 'PREDICTION':
        return <Cpu className="w-4 h-4 text-blue-600" />;
      case 'MAINTENANCE':
        return <Wrench className="w-4 h-4 text-emerald-600" />;
      case 'ALERT':
        return <Radio className="w-4 h-4 text-red-600" />;
      default:
        return <Gauge className="w-4 h-4 text-slate-500" />;
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Header & Asset Selector Bar */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-50 text-blue-700 rounded-lg border border-blue-200">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-gray-900 tracking-tight">Asset Digital Thread</h1>
              <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold rounded-full flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Traceable Lifecycle</span>
              </span>
            </div>
            <p className="text-xs text-gray-500">Complete industrial provenance: Sensors → Telemetry → ML & Drift → Maintenance → Outcomes</p>
          </div>
        </div>

        {/* Asset Dropdown & Actions */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Asset:</span>
            <select
              value={selectedAssetId}
              onChange={(e) => setSelectedAssetId(e.target.value)}
              className="bg-slate-50 border border-gray-300 text-gray-900 text-xs rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2 font-semibold shadow-sm"
            >
              {assets.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.asset_id} ({a.plc_id}) - {a.asset_name}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => fetchThreadData(selectedAssetId)}
            className="flex items-center space-x-1.5 px-3 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-300 rounded-lg text-xs font-semibold transition"
            title="Refresh Digital Thread"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-blue-600' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setShowMaintModal(true)}
            className="flex items-center space-x-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>Log Maintenance</span>
          </button>
        </div>
      </div>

      {/* 2. Asset Overview & Identity Card */}
      {healthSnapshot && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center justify-between">
              <span>Asset Provenance</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-200 font-mono">
                {healthSnapshot.asset_id}
              </span>
            </div>
            <div>
              <div className="text-base font-bold text-gray-900">{healthSnapshot.asset_name}</div>
              <div className="text-xs text-gray-500">{healthSnapshot.asset_type}</div>
            </div>
            <div className="space-y-1.5 pt-2 border-t border-gray-100 text-xs">
              <div className="flex justify-between text-gray-600">
                <span>PLC Binding:</span>
                <span className="font-semibold text-gray-900">{healthSnapshot.plc_id}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Location:</span>
                <span className="font-semibold text-gray-900">{healthSnapshot.location}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>OEM / Model:</span>
                <span className="font-semibold text-gray-900">{healthSnapshot.manufacturer} {healthSnapshot.model}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Commissioned:</span>
                <span className="font-semibold text-gray-900">{healthSnapshot.install_date}</span>
              </div>
            </div>
          </div>

          {/* Machine Health Card */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center justify-between">
              <span>Dynamic Health Index</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                healthSnapshot.health >= 80 ? 'bg-emerald-100 text-emerald-800' :
                healthSnapshot.health >= 60 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
              }`}>
                {healthSnapshot.status}
              </span>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-gray-900 tracking-tight">{healthSnapshot.health}%</span>
              <span className="text-xs text-gray-500">Live Operating Score</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  healthSnapshot.health >= 80 ? 'bg-emerald-500' : healthSnapshot.health >= 60 ? 'bg-amber-500' : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, healthSnapshot.health))}%` }}
              />
            </div>
            <div className="pt-2 border-t border-gray-100 text-xs text-gray-500 flex justify-between">
              <span>Last Maintenance:</span>
              <span className="font-medium text-gray-800">{healthSnapshot.last_maintenance_date || 'None'}</span>
            </div>
          </div>

          {/* AI Prognostics & RUL */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center justify-between">
              <span>Prognostics & RUL</span>
              <Cpu className="w-3.5 h-3.5 text-blue-600" />
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-extrabold text-blue-700 tracking-tight">{healthSnapshot.rul_days}</span>
              <span className="text-xs text-gray-500">Estimated Days Remaining</span>
            </div>
            <div className="space-y-1 pt-1 text-xs">
              <div className="flex justify-between text-gray-600">
                <span>Model Confidence:</span>
                <span className="font-semibold text-emerald-700">{healthSnapshot.ai_health.confidence_pct}%</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Primary Regressor:</span>
                <span className="font-mono text-[11px] text-gray-800">{healthSnapshot.ai_health.model_used}</span>
              </div>
            </div>
          </div>

          {/* AI Reliability & Drift Bridge */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center justify-between">
              <span>Drift & Reliability</span>
              <Activity className="w-3.5 h-3.5 text-purple-600" />
            </div>
            <div className="flex items-center space-x-2">
              <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                healthSnapshot.ai_health.drift.overall_status === 'HEALTHY'
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  : healthSnapshot.ai_health.drift.overall_status === 'WARNING'
                  ? 'bg-amber-100 text-amber-800 border border-amber-200'
                  : 'bg-red-100 text-red-800 border border-red-200'
              }`}>
                {healthSnapshot.ai_health.drift.overall_status} DRIFT
              </span>
              <span className="text-xs text-gray-500 font-mono">
                PSI: {Number(healthSnapshot.ai_health.drift.overall_drift_score || 0).toFixed(3)}
              </span>
            </div>
            <p className="text-xs text-gray-600 line-clamp-2" title={healthSnapshot.ai_health.drift.reason}>
              {healthSnapshot.ai_health.drift.reason}
            </p>
            <div className="pt-2 border-t border-gray-100 flex justify-between text-xs text-gray-500">
              <span>Anomaly Status:</span>
              <span className="font-semibold text-gray-800">{healthSnapshot.ai_health.anomaly_status}</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Component & Sensor Topology Tree */}
      {healthSnapshot && healthSnapshot.components && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div>
              <h2 className="text-sm font-bold text-gray-900 tracking-tight flex items-center space-x-2">
                <Sliders className="w-4 h-4 text-blue-600" />
                <span>Physical Component & Sensor Topology</span>
              </h2>
              <p className="text-xs text-gray-500">Structured telemetry binding across physical machine sub-assemblies</p>
            </div>
            <span className="text-xs text-gray-500 font-medium">
              {healthSnapshot.components.length} Sub-Assemblies Active
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {healthSnapshot.components.map((comp) => (
              <div key={comp.component_id} className="bg-slate-50 border border-gray-200 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono text-gray-400">{comp.component_id}</span>
                    <h3 className="text-xs font-bold text-gray-900">{comp.component_name}</h3>
                  </div>
                  <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                    comp.criticality === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                    comp.criticality === 'HIGH' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {comp.criticality}
                  </span>
                </div>
                <div className="text-[11px] text-gray-600">{comp.component_type}</div>

                {/* Sensors under this component */}
                <div className="space-y-1.5 pt-2 border-t border-gray-200">
                  <div className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Instrumentation</div>
                  {comp.sensors && comp.sensors.map((sens) => (
                    <div key={sens.sensor_id} className="flex items-center justify-between bg-white border border-gray-200 rounded px-2.5 py-1.5 text-xs">
                      <div className="flex items-center space-x-1.5">
                        <Thermometer className="w-3 h-3 text-gray-500" />
                        <span className="font-semibold text-gray-800">{sens.tag_name}</span>
                        <span className="text-[10px] text-gray-400">({sens.sensor_type})</span>
                      </div>
                      <div className="font-mono font-bold text-blue-700">
                        {sens.live_value !== null && sens.live_value !== undefined
                          ? `${sens.live_value} ${sens.unit}`
                          : <span className="text-gray-400">--</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Chronological Lifecycle Timeline (Core Digital Thread) */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-gray-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-gray-900 tracking-tight flex items-center space-x-2">
              <Clock className="w-4 h-4 text-blue-600" />
              <span>Asset Lifecycle Timeline</span>
            </h2>
            <p className="text-xs text-gray-500">Immutable chronological history of telemetry checkpoints, model inferences, drift detections, and maintenance events</p>
          </div>

          {/* Filter Chips */}
          <div className="flex flex-wrap items-center gap-1.5">
            {['ALL', 'TELEMETRY', 'PREDICTION', 'ANOMALY', 'DRIFT', 'MAINTENANCE', 'ALERT'].map((ft) => (
              <button
                key={ft}
                onClick={() => setTimelineFilter(ft)}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                  timelineFilter === ft
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {ft}
              </button>
            ))}
          </div>
        </div>

        {/* Timeline Events List */}
        <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
          {timelineEvents.length === 0 ? (
            <div className="text-center py-10 text-gray-400 text-xs">
              No lifecycle events recorded for the selected filter criteria.
            </div>
          ) : (
            timelineEvents.map((evt, idx) => (
              <div
                key={evt.event_id || idx}
                className="flex items-start space-x-3 p-3 bg-slate-50 border border-gray-200 rounded-lg hover:bg-slate-100/80 transition"
              >
                <div className="p-2 bg-white rounded border border-gray-200 shadow-2xs mt-0.5">
                  {getEventTypeIcon(evt.event_type)}
                </div>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-gray-900">{evt.source}</span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-gray-200 text-gray-700">
                        {evt.event_type}
                      </span>
                      {getSeverityBadge(evt.severity)}
                    </div>
                    <span className="text-[11px] font-mono text-gray-500">{evt.timestamp}</span>
                  </div>

                  <p className="text-xs text-gray-700 font-medium">{evt.description}</p>

                  {/* Metadata tags */}
                  {(evt.component_id || evt.sensor_id || (evt.metadata && Object.keys(evt.metadata).length > 0)) && (
                    <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-gray-500">
                      {evt.component_id && (
                        <span className="bg-white border border-gray-200 px-1.5 py-0.5 rounded text-[10px] font-mono text-gray-600">
                          Comp: {evt.component_id}
                        </span>
                      )}
                      {evt.sensor_id && (
                        <span className="bg-white border border-gray-200 px-1.5 py-0.5 rounded text-[10px] font-mono text-gray-600">
                          Sensor: {evt.sensor_id}
                        </span>
                      )}
                      {evt.metric_value !== null && evt.metric_value !== undefined && (
                        <span className="bg-white border border-gray-200 px-1.5 py-0.5 rounded text-[10px] font-mono text-blue-700 font-bold">
                          Value: {evt.metric_value}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 5. Closed-Loop Maintenance History & Outcome Feedback */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-gray-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-gray-900 tracking-tight flex items-center space-x-2">
              <Wrench className="w-4 h-4 text-emerald-600" />
              <span>Closed-Loop Maintenance History & Verification</span>
            </h2>
            <p className="text-xs text-gray-500">Traceable actions, parts replaced, before-vs-after health, and post-service outcome validation</p>
          </div>

          <button
            onClick={() => setShowMaintModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>New Maintenance Record</span>
          </button>
        </div>

        {/* Maintenance Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-600 border-collapse">
            <thead className="bg-slate-50 text-gray-700 font-bold uppercase text-[10px] tracking-wider border-b border-gray-200">
              <tr>
                <th className="py-2.5 px-3">Maintenance ID</th>
                <th className="py-2.5 px-3">Date / Technician</th>
                <th className="py-2.5 px-3">Type & Reason</th>
                <th className="py-2.5 px-3">Action & Parts</th>
                <th className="py-2.5 px-3">Before vs After</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {maintenanceRecords.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-6 text-gray-400">
                    No maintenance records logged for this asset yet.
                  </td>
                </tr>
              ) : (
                maintenanceRecords.map((m) => (
                  <tr key={m.maintenance_id} className="hover:bg-slate-50/70 transition">
                    <td className="py-3 px-3 font-mono font-semibold text-gray-900">{m.maintenance_id}</td>
                    <td className="py-3 px-3 space-y-0.5">
                      <div className="font-semibold text-gray-800">{m.timestamp}</div>
                      <div className="text-[11px] text-gray-500">{m.technician || 'Unassigned'}</div>
                    </td>
                    <td className="py-3 px-3 space-y-0.5">
                      <div className="font-semibold text-gray-900">{m.maintenance_type}</div>
                      <div className="text-[11px] text-gray-500 line-clamp-1">{m.reason}</div>
                    </td>
                    <td className="py-3 px-3 space-y-0.5">
                      <div className="font-medium text-gray-800 line-clamp-1">{m.action_performed || 'Inspection performed'}</div>
                      <div className="text-[11px] text-blue-600 font-mono">
                        {m.parts_replaced || (m.parts && m.parts.map((p) => p.part_name).join(', ')) || 'No parts replaced'}
                      </div>
                    </td>
                    <td className="py-3 px-3 space-y-1">
                      <div className="flex items-center space-x-1.5 text-[11px]">
                        <span className="text-gray-500">Health:</span>
                        <span className="font-bold text-gray-700">{m.before_health ?? '--'}%</span>
                        <ArrowRight className="w-3 h-3 text-gray-400" />
                        <span className="font-bold text-emerald-700">{m.after_health ? `${m.after_health}%` : 'Pending'}</span>
                      </div>
                      <div className="flex items-center space-x-1.5 text-[11px]">
                        <span className="text-gray-500">RUL:</span>
                        <span className="font-bold text-gray-700">{m.before_rul ?? '--'}d</span>
                        <ArrowRight className="w-3 h-3 text-gray-400" />
                        <span className="font-bold text-blue-700">{m.after_rul ? `${m.after_rul}d` : 'Pending'}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        m.status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                      }`}>
                        {m.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      {!m.outcome_verified ? (
                        <button
                          onClick={() => {
                            setTargetMaintId(m.maintenance_id);
                            setShowOutcomeModal(true);
                          }}
                          className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded text-xs font-semibold border border-blue-200 transition"
                        >
                          Verify Outcome
                        </button>
                      ) : (
                        <span className="inline-flex items-center space-x-1 text-emerald-700 text-xs font-semibold">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Verified</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL 1: Log Maintenance Action */}
      {showMaintModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-5 space-y-4 border border-gray-200">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center space-x-2">
                <Wrench className="w-5 h-5 text-blue-600" />
                <h3 className="text-sm font-bold text-gray-900">Log Maintenance Action ({selectedAssetId})</h3>
              </div>
              <button onClick={() => setShowMaintModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateMaintenance} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Maintenance Type</label>
                <input
                  type="text"
                  required
                  value={maintForm.maintenance_type}
                  onChange={(e) => setMaintForm({ ...maintForm, maintenance_type: e.target.value })}
                  className="w-full bg-slate-50 border border-gray-300 rounded p-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Reason / Trigger</label>
                <input
                  type="text"
                  required
                  value={maintForm.reason}
                  onChange={(e) => setMaintForm({ ...maintForm, reason: e.target.value })}
                  className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Technician</label>
                  <input
                    type="text"
                    value={maintForm.technician}
                    onChange={(e) => setMaintForm({ ...maintForm, technician: e.target.value })}
                    className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Downtime (Hours)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={maintForm.downtime_hours}
                    onChange={(e) => setMaintForm({ ...maintForm, downtime_hours: parseFloat(e.target.value) })}
                    className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Action Performed</label>
                <textarea
                  rows={2}
                  value={maintForm.action_performed}
                  onChange={(e) => setMaintForm({ ...maintForm, action_performed: e.target.value })}
                  className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                />
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Parts Replaced</label>
                <input
                  type="text"
                  value={maintForm.parts_replaced}
                  onChange={(e) => setMaintForm({ ...maintForm, parts_replaced: e.target.value })}
                  className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowMaintModal(false)}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 shadow-xs"
                >
                  Save Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Record Closed-Loop Maintenance Outcome */}
      {showOutcomeModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 space-y-4 border border-gray-200">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center space-x-2">
                <FileCheck className="w-5 h-5 text-emerald-600" />
                <h3 className="text-sm font-bold text-gray-900">Record Post-Maintenance Outcome</h3>
              </div>
              <button onClick={() => setShowOutcomeModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-gray-500">
              Complete the closed-loop cycle: verify how the physical maintenance affected health index and remaining useful life.
            </p>

            <form onSubmit={handleRecordOutcome} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">After Health (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    step="0.5"
                    required
                    value={outcomeForm.after_health}
                    onChange={(e) => setOutcomeForm({ ...outcomeForm, after_health: parseFloat(e.target.value) })}
                    className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">After RUL (Days)</label>
                  <input
                    type="number"
                    min="1"
                    max="500"
                    required
                    value={outcomeForm.after_rul}
                    onChange={(e) => setOutcomeForm({ ...outcomeForm, after_rul: parseInt(e.target.value) })}
                    className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Outcome Verification Notes</label>
                <textarea
                  rows={3}
                  required
                  value={outcomeForm.notes}
                  onChange={(e) => setOutcomeForm({ ...outcomeForm, notes: e.target.value })}
                  className="w-full bg-slate-50 border border-gray-300 rounded p-2"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowOutcomeModal(false)}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-emerald-600 text-white rounded font-semibold hover:bg-emerald-700 shadow-xs"
                >
                  Confirm Outcome
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
