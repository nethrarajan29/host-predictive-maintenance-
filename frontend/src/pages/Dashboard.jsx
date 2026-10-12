import React, { useState } from 'react';
import {
  Thermometer,
  Activity,
  Zap,
  Calendar,
  ShieldAlert,
  Gauge,
  Volume2,
  ShieldCheck,
  Cpu,
  Plus,
  Wrench,
  DollarSign,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Info,
  Radio,
  CheckCircle2,
  X
} from 'lucide-react';
import GaugeCard from '../components/GaugeCard';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';
import LiveChart from '../components/LiveChart';
import SensorTable from '../components/SensorTable';
import { isValidPlcId, formatPlcDisplay, getPlcNumber, isPlcMatch } from '../utils/plcValidation';
import { postAddPlc } from '../services/api';

const SENSOR_METADATA = {
  Motor_Temp: { tag_id: 'T101', name: 'Motor Temperature', unit: '°C', normal: '< 70.0 °C', warning: '70.0 - 85.0 °C', critical: '> 85.0 °C', warnThresh: 70.0, critThresh: 85.0 },
  Temperature: { tag_id: 'T101', name: 'Motor Temperature', unit: '°C', normal: '< 70.0 °C', warning: '70.0 - 85.0 °C', critical: '> 85.0 °C', warnThresh: 70.0, critThresh: 85.0 },
  Vibration_X: { tag_id: 'T102', name: 'Vibration RMS', unit: 'mm/s', normal: '< 0.50 mm/s', warning: '0.50 - 1.50 mm/s', critical: '> 1.50 mm/s', warnThresh: 0.50, critThresh: 1.50 },
  Vibration: { tag_id: 'T102', name: 'Vibration RMS', unit: 'mm/s', normal: '< 0.50 mm/s', warning: '0.50 - 1.50 mm/s', critical: '> 1.50 mm/s', warnThresh: 0.50, critThresh: 1.50 },
  Motor_Current: { tag_id: 'T103', name: 'Motor Current', unit: 'A', normal: '< 10.0 A', warning: '10.0 - 15.0 A', critical: '> 15.0 A', warnThresh: 10.0, critThresh: 15.0 },
  Pressure_Inlet: { tag_id: 'T104', name: 'Inlet Pressure', unit: 'bar', normal: '4.0 - 6.0 bar', warning: '3.0 - 4.0 or 6.0 - 7.0 bar', critical: '< 3.0 or > 7.0 bar', warnThresh: 6.0, critThresh: 7.0 },
  Pressure: { tag_id: 'T104', name: 'Inlet Pressure', unit: 'bar', normal: '4.0 - 6.0 bar', warning: '3.0 - 4.0 or 6.0 - 7.0 bar', critical: '< 3.0 or > 7.0 bar', warnThresh: 6.0, critThresh: 7.0 },
  Noise: { tag_id: 'T105', name: 'Acoustic Noise', unit: 'dB', normal: '< 55.0 dB', warning: '55.0 - 70.0 dB', critical: '> 70.0 dB', warnThresh: 55.0, critThresh: 70.0 },
};

const Dashboard = ({
  plcsList,
  selectedPlc,
  setSelectedPlc,
  selectedTag,
  setSelectedTag,
  currentData,
  historyData,
  logs,
  setActiveTab,
  onPlcAdded
}) => {
  const [showAddPlcModal, setShowAddPlcModal] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [addPlcForm, setAddPlcForm] = useState({
    plc_id: '',
    name: '',
    deg_init: 0.05,
    base_load: 0.60,
    temp_offset: 0.0,
    vib_offset: 0.0
  });
  const [addPlcError, setAddPlcError] = useState('');

  const health = currentData?.machine_health ?? 100;
  const statusStr = currentData?.machine_status || 'Healthy';
  const conditionStr = currentData?.machine_condition || 'Healthy';
  const anomalyStr = currentData?.anomaly_status || 'Normal';
  const failureRisk = currentData?.failure_risk_pct ?? 0.0;
  const confidence = currentData?.prediction_confidence ?? 95.0;

  // Active sensor specifications & live status
  const currentTagKey = selectedTag || 'Motor_Temp';
  const activeMeta = SENSOR_METADATA[currentTagKey] || SENSOR_METADATA.Motor_Temp;
  const activeSensorVal = currentData?.sensor_details?.[currentTagKey]?.val ?? (
    currentTagKey === 'Motor_Temp' || currentTagKey === 'Temperature' ? currentData?.temperature :
    currentTagKey === 'Vibration_X' || currentTagKey === 'Vibration' ? currentData?.vibration :
    currentTagKey === 'Motor_Current' ? currentData?.motor_current :
    currentTagKey === 'Pressure_Inlet' || currentTagKey === 'Pressure' ? currentData?.pressure :
    currentTagKey === 'Noise' ? currentData?.noise : '--'
  );
  const activeSensorStatus = currentData?.sensor_details?.[currentTagKey]?.status || (
    activeSensorVal === '--' ? 'NORMAL' :
    Number(activeSensorVal) > activeMeta.critThresh ? 'CRITICAL' :
    Number(activeSensorVal) > activeMeta.warnThresh ? 'WARNING' : 'NORMAL'
  );
  const activeSensorIntegrity = currentData?.sensor_details?.[currentTagKey]?.integrity || 'NORMAL';
  const activeSensorTimestamp = currentData?.timestamp || new Date().toLocaleTimeString();

  const isPlcSelected = (pId) => {
    if (!isValidPlcId(pId) || !isValidPlcId(selectedPlc)) return false;
    return isPlcMatch(pId, selectedPlc);
  };

  const getGaugeColor = (s) => {
    switch (s) {
      case 'Healthy':
        return '#22C55E';
      case 'Slight Wear':
        return '#2563EB';
      case 'Moderate Wear':
        return '#F59E0B';
      case 'Warning':
        return '#D97706';
      case 'Critical':
        return '#EF4444';
      default:
        return '#22C55E';
    }
  };

  const statusColor = getGaugeColor(statusStr);

  const getPlcDesc = (id) => {
    const num = typeof id === 'number' && !isNaN(id) ? id : 1;
    switch (num) {
      case 1: return 'Healthy Baseline Unit';
      case 2: return 'High Operating Load';
      case 3: return 'Bearing Degradation Unit';
      case 4: return 'Elevated Thermal Stress';
      case 5: return 'Normal Variation';
      default: return `Turbine Motor Unit #${num}`;
    }
  };

  // Filter plcsList strictly to only valid PLC IDs
  const validPlcsList = (plcsList || [])
    .filter((p) => p && isValidPlcId(p.plc_id))
    .map((p) => ({
      ...p,
      plc_id: formatPlcDisplay(p.plc_id),
      plc_id_num: getPlcNumber(p.plc_id),
    }));

  const displayPlcs = validPlcsList.length > 0 ? validPlcsList : [1, 2, 3, 4, 5].map((id) => ({
    plc_id: `PLC_${String(id).padStart(2, '0')}`,
    plc_id_num: id,
    temperature: currentData?.plc_id === id ? currentData.temperature : 62.0,
    vibration: currentData?.plc_id === id ? currentData.vibration : 0.2,
    motor_current: currentData?.plc_id === id ? currentData.motor_current : 8.0,
    pressure: currentData?.plc_id === id ? currentData.pressure : 5.0,
    noise: currentData?.plc_id === id ? currentData.noise : 42.0,
    predicted_rul_days: currentData?.plc_id === id ? currentData.predicted_rul_days : 200,
    machine_status: currentData?.plc_id === id ? currentData.machine_status : 'Healthy',
    anomaly_status: currentData?.plc_id === id ? currentData.anomaly_status : 'Normal',
  }));

  // Handle Adding New PLC
  const handleAddPlc = async (e) => {
    e.preventDefault();
    setAddPlcError('');
    try {
      const payload = {
        plc_id: addPlcForm.plc_id ? formatPlcDisplay(addPlcForm.plc_id) : undefined,
        name: addPlcForm.name || undefined,
        deg_init: parseFloat(addPlcForm.deg_init) || 0.05,
        base_load: parseFloat(addPlcForm.base_load) || 0.60,
        temp_offset: parseFloat(addPlcForm.temp_offset) || 0.0,
        vib_offset: parseFloat(addPlcForm.vib_offset) || 0.0
      };
      const res = await postAddPlc(payload);
      if (res && res.status === 'success') {
        setShowAddPlcModal(false);
        setAddPlcForm({
          plc_id: '',
          name: '',
          deg_init: 0.05,
          base_load: 0.60,
          temp_offset: 0.0,
          vib_offset: 0.0
        });
        if (setSelectedPlc && res.plc_id) {
          setSelectedPlc(res.plc_id);
        }
        if (onPlcAdded) onPlcAdded(res.plc_id);
      } else if (res && res.status === 'exists') {
        setAddPlcError(res.message || 'PLC ID already exists.');
      }
    } catch (err) {
      console.error('Failed to add PLC:', err);
      setAddPlcError('Failed to add PLC. Please check ID format.');
    }
  };

  // Human-Readable Alert Derivation
  const alertData = currentData?.concise_alert || {
    title: `${statusStr === 'Critical' ? '🔴' : failureRisk > 35 ? '🟠' : '🟢'} ${formatPlcDisplay(selectedPlc)} — ${currentData?.probable_issue || 'Normal Operation'}`,
    rul_text: currentData?.predicted_rul_days ? (currentData.predicted_rul_days >= 28 ? `~${Math.round(currentData.predicted_rul_days / 7)} weeks` : `${currentData.predicted_rul_days} days`) : '--',
    action_text: currentData?.rul_deadline_text || 'Monitor normally',
    energy_text: currentData?.excess_energy_pct ? `+${currentData.excess_energy_pct}% above baseline` : 'Normal baseline',
    savings_text: currentData?.potential_savings && currentData.potential_savings > 0 ? `₹${currentData.potential_savings.toLocaleString()}` : '₹0 (Monitor)',
    recommendation: currentData?.financial_decision || (statusStr === 'Critical' ? 'Maintain immediately' : 'Schedule preventive maintenance'),
    priority: currentData?.maintenance_priority || (statusStr === 'Critical' ? 'Critical' : 'Low')
  };

  const getPriorityBadgeClass = (p) => {
    switch (p) {
      case 'Critical': return 'bg-red-100 text-red-800 border-red-300';
      case 'Urgent':
      case 'High': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'Medium': return 'bg-amber-100 text-amber-800 border-amber-300';
      default: return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    }
  };

  return (
    <div className="space-y-5">
      {/* Dynamic Multi-PLC and Tag Selector Toolbar */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-200 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">Select PLC:</span>
            <select
              value={formatPlcDisplay(selectedPlc)}
              onChange={(e) => setSelectedPlc(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 text-xs font-bold rounded-lg focus:ring-blue-500 focus:border-blue-500 px-3 py-2 cursor-pointer shadow-sm"
            >
              {displayPlcs
                .filter((p) => p && isValidPlcId(p.plc_id))
                .map((p) => {
                  const pKey = formatPlcDisplay(p.plc_id);
                  const pNum = getPlcNumber(pKey);
                  return (
                    <option key={pKey} value={pKey}>
                      {pKey} — {getPlcDesc(pNum)}
                    </option>
                  );
                })}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">Select Tag:</span>
            <select
              value={selectedTag || 'Motor_Temp'}
              onChange={(e) => setSelectedTag && setSelectedTag(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 text-xs font-bold rounded-lg focus:ring-blue-500 focus:border-blue-500 px-3 py-2 cursor-pointer shadow-sm"
            >
              <option value="Motor_Temp">Motor_Temp (Temperature °C)</option>
              <option value="Vibration_X">Vibration_X (Vibration RMS mm/s)</option>
              <option value="Motor_Current">Motor_Current (Motor Current A)</option>
              <option value="Pressure_Inlet">Pressure_Inlet (Inlet Pressure bar)</option>
              <option value="Noise">Noise (Acoustic Noise dB)</option>
            </select>
          </div>

          <button
            onClick={() => setShowAddPlcModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold rounded-lg border border-indigo-200 transition shadow-2xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add PLC</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>MQTT: <strong>CONNECTED</strong></span>
            <span className="text-gray-400">|</span>
            <span className="font-mono text-[11px]">Topic: plc/{formatPlcDisplay(selectedPlc)}/{selectedTag || 'Motor_Temp'}</span>
          </div>

          <div className="flex items-center space-x-2 bg-blue-50 text-blue-800 px-3 py-1.5 rounded-lg border border-blue-200 text-xs font-semibold">
            <span>Active Stream:</span>
            <span className="font-mono font-bold bg-blue-600 text-white px-2 py-0.5 rounded text-[11px]">
              {formatPlcDisplay(selectedPlc)} + {selectedTag || 'Motor_Temp'}
            </span>
          </div>
        </div>
      </div>

      {/* ACTIVE SENSOR LIVE TELEMETRY & SPECIFICATION INSPECTOR */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-200">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-gray-100 gap-3">
          <div className="flex items-center space-x-3">
            <div className={`p-2.5 rounded-xl ${
              activeSensorStatus === 'CRITICAL' ? 'bg-red-100 text-red-700' :
              activeSensorStatus === 'WARNING' ? 'bg-amber-100 text-amber-700' :
              'bg-emerald-100 text-emerald-700'
            }`}>
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Live Sensor Inspector</span>
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-bold">
                  {activeMeta.tag_id}
                </span>
                <span className="text-xs text-gray-400">•</span>
                <span className="font-mono text-xs font-bold text-indigo-700">{formatPlcDisplay(selectedPlc)}</span>
              </div>
              <h3 className="text-base font-black text-gray-900 flex items-center gap-2">
                <span>{activeMeta.name} ({currentTagKey})</span>
              </h3>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="bg-slate-50 px-3.5 py-2 rounded-xl border border-gray-200">
              <span className="text-[10px] text-gray-500 font-semibold uppercase block">Live Reading</span>
              <span className="text-lg font-black font-mono text-gray-900">
                {activeSensorVal} <span className="text-xs font-normal text-gray-600">{activeMeta.unit}</span>
              </span>
            </div>

            <div className="bg-slate-50 px-3.5 py-2 rounded-xl border border-gray-200">
              <span className="text-[10px] text-gray-500 font-semibold uppercase block">Status</span>
              <span className={`text-xs font-black uppercase px-2 py-0.5 rounded inline-block mt-0.5 ${
                activeSensorStatus === 'CRITICAL' ? 'bg-red-100 text-red-700 border border-red-200' :
                activeSensorStatus === 'WARNING' ? 'bg-amber-100 text-amber-700 border border-amber-200' :
                'bg-emerald-100 text-emerald-700 border border-emerald-200'
              }`}>
                {activeSensorStatus}
              </span>
            </div>

            <div className="bg-slate-50 px-3.5 py-2 rounded-xl border border-gray-200">
              <span className="text-[10px] text-gray-500 font-semibold uppercase block">Sensor Integrity</span>
              <span className={`text-xs font-black uppercase px-2 py-0.5 rounded inline-block mt-0.5 ${
                activeSensorIntegrity === 'SUSPECT' ? 'bg-amber-100 text-amber-800 border border-amber-300' :
                'bg-emerald-100 text-emerald-800 border border-emerald-300'
              }`}>
                {activeSensorIntegrity === 'SUSPECT' ? '⚠️ SUSPECT' : '✓ NORMAL (VERIFIED)'}
              </span>
            </div>

            <div className="bg-slate-50 px-3.5 py-2 rounded-xl border border-gray-200 text-right">
              <span className="text-[10px] text-gray-500 font-semibold uppercase block">Timestamp</span>
              <span className="text-xs font-mono font-bold text-gray-700">
                {activeSensorTimestamp}
              </span>
            </div>
          </div>
        </div>

        {/* Operating Ranges Row */}
        <div className="mt-3 pt-2 grid grid-cols-1 sm:grid-cols-4 gap-2.5 text-xs">
          <div className="p-2.5 rounded-lg bg-emerald-50/60 border border-emerald-200/80">
            <span className="text-[10px] font-bold text-emerald-800 uppercase block">Normal Range</span>
            <span className="font-mono font-bold text-emerald-900">{activeMeta.normal}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-amber-50/60 border border-amber-200/80">
            <span className="text-[10px] font-bold text-amber-800 uppercase block">Warning Range</span>
            <span className="font-mono font-bold text-amber-900">{activeMeta.warning}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-rose-50/60 border border-rose-200/80">
            <span className="text-[10px] font-bold text-rose-800 uppercase block">Critical Range</span>
            <span className="font-mono font-bold text-rose-900">{activeMeta.critical}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-blue-50/60 border border-blue-200/80">
            <span className="text-[10px] font-bold text-blue-800 uppercase block">MQTT Telemetry Topic</span>
            <span className="font-mono font-bold text-blue-900 truncate block">plc/{formatPlcDisplay(selectedPlc)}/{currentTagKey}</span>
          </div>
        </div>
      </div>

      {/* MULTI-MACHINE REAL-TIME OVERVIEW GRID (Digital Twin SCADA View) */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-gray-900">Multi-PLC Industrial Digital Twin Overview</h2>
          </div>
          <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2.5 py-1 rounded border">
            {displayPlcs.length} Active PLCs | Topic: plc/# | Broker: 127.0.0.1:1883
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
          {displayPlcs
            .filter((p) => p && isValidPlcId(p.plc_id))
            .map((p) => {
              const pKey = formatPlcDisplay(p.plc_id);
              const isSelected = isPlcSelected(pKey);
              const pStatus = p.machine_status || 'Healthy';
              const pRul = p.predicted_rul_days ?? '--';
              const pAnomaly = p.anomaly_status === 'Anomaly Detected';
              const pNum = getPlcNumber(pKey);
              const pIssue = p.main_issue || getPlcDesc(pNum);
              const pRisk = typeof p.failure_risk_pct === 'number'
                ? p.failure_risk_pct.toFixed(1)
                : (pStatus === 'Critical' ? '79.5' : pStatus === 'Warning' ? '43.4' : '4.5');
              const pIntegrity = p.sensor_integrity || 'NORMAL';

            return (
              <div
                key={pKey}
                onClick={() => setSelectedPlc(pKey)}
                className={`cursor-pointer rounded-xl p-3 border transition-all duration-200 ${
                  isSelected
                    ? 'border-indigo-600 bg-indigo-50/40 shadow-md ring-2 ring-indigo-500/20'
                    : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center space-x-1.5">
                    <span className={`w-2.5 h-2.5 rounded-full ${isSelected ? 'bg-indigo-600 animate-pulse' : 'bg-gray-400'}`}></span>
                    <span className="font-bold text-sm text-gray-900">{pKey}</span>
                  </div>
                  <StatusBadge status={pStatus} />
                </div>

                <div className="text-[11px] font-semibold text-gray-600 mb-2 truncate" title={pIssue}>
                  {pIssue}
                </div>

                {/* All 5 Transducer Readings + Failure Risk Probability */}
                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-gray-600 border-t border-b border-gray-100 py-1.5 mb-2">
                  <div>Temp: <span className="font-bold text-gray-900">{p.temperature ?? '--'}°C</span></div>
                  <div>Vib: <span className="font-bold text-gray-900">{p.vibration ?? '--'}</span></div>
                  <div>Curr: <span className="font-bold text-gray-900">{p.motor_current ?? '--'}A</span></div>
                  <div>Press: <span className="font-bold text-gray-900">{p.pressure ?? '--'}b</span></div>
                  <div>Noise: <span className="font-bold text-gray-900">{p.noise ?? '--'}dB</span></div>
                  <div>Risk: <span className="font-bold text-rose-600">{pRisk}%</span></div>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <div>
                    <span className="text-gray-400 text-[10px] block">RF RUL</span>
                    <span className="font-bold font-mono text-indigo-700">{pRul} Days</span>
                  </div>
                  <div className="text-right">
                    <span className="text-gray-400 text-[10px] block">Sensor Integrity</span>
                    <span className={`font-bold text-[10px] ${pIntegrity === 'SUSPECT' ? 'text-amber-600' : 'text-emerald-600'}`}>
                      {pIntegrity === 'SUSPECT' ? '⚠️ SUSPECT' : '✓ NORMAL'}
                    </span>
                  </div>
                </div>

                <div className="mt-1.5 pt-1.5 border-t border-gray-100 text-[10px] text-gray-500 flex items-center justify-between">
                  <span>Maint: <span className="font-semibold text-gray-700">{pStatus === 'Critical' ? 'Urgent Action' : pStatus === 'Warning' ? 'Scheduled Soon' : 'Routine'}</span></span>
                  <span className={`${pAnomaly ? 'text-rose-600 font-semibold' : 'text-gray-400'}`}>{pAnomaly ? '⚠️ Anomaly' : '✓ Normal'}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* HUMAN-READABLE PREDICTIVE MAINTENANCE ALERT CARD (Requirements 2, 8, 10, 18, 20) */}
      <div className={`rounded-xl p-4 border transition-all ${
        alertData.priority === 'Critical'
          ? 'bg-red-50/80 border-red-300 shadow-sm'
          : alertData.priority === 'High'
          ? 'bg-orange-50/80 border-orange-300 shadow-sm'
          : alertData.priority === 'Medium'
          ? 'bg-amber-50/80 border-amber-300'
          : 'bg-emerald-50/80 border-emerald-300'
      }`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">{alertData.priority === 'Critical' ? '🔴' : alertData.priority === 'High' ? '🟠' : alertData.priority === 'Medium' ? '🟡' : '🟢'}</span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-sm sm:text-base text-gray-900">
                  {formatPlcDisplay(selectedPlc)} — {currentData?.probable_issue || 'Normal Operation'}
                </span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getPriorityBadgeClass(alertData.priority)}`}>
                  {alertData.priority} Urgency
                </span>
              </div>
              <p className="text-xs text-gray-600 mt-0.5">
                {currentData?.issue_detail || 'Monitored multi-sensor telemetry within normal operating envelope.'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 text-xs">
            <div className="bg-white/90 px-3 py-1.5 rounded-lg border border-gray-200 shadow-2xs font-mono">
              <span className="text-gray-400 text-[10px] block">RUL</span>
              <span className="font-bold text-blue-700">{alertData.rul_text}</span>
            </div>
            <div className="bg-white/90 px-3 py-1.5 rounded-lg border border-gray-200 shadow-2xs font-mono">
              <span className="text-gray-400 text-[10px] block">Action</span>
              <span className="font-bold text-gray-800">{alertData.action_text}</span>
            </div>
            <div className="bg-white/90 px-3 py-1.5 rounded-lg border border-gray-200 shadow-2xs font-mono">
              <span className="text-gray-400 text-[10px] block">Energy</span>
              <span className="font-bold text-amber-700">{alertData.energy_text}</span>
            </div>
            <div className="bg-white/90 px-3 py-1.5 rounded-lg border border-gray-200 shadow-2xs font-mono">
              <span className="text-gray-400 text-[10px] block">Potential Saving</span>
              <span className="font-bold text-emerald-700">{alertData.savings_text}</span>
            </div>
            {setActiveTab && (
              <button
                onClick={() => setActiveTab('maintenance')}
                className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg shadow-sm transition text-xs flex items-center gap-1.5 cursor-pointer"
              >
                <Wrench className="w-3.5 h-3.5" />
                <span>Optimize Maintenance</span>
              </button>
            )}
          </div>
        </div>

        {/* Expandable "View Analysis" Section (Requirement 18 & 20) */}
        <div className="mt-3 pt-2.5 border-t border-gray-200/70">
          <button
            onClick={() => setShowAnalysis(!showAnalysis)}
            className="flex items-center space-x-1.5 text-xs font-bold text-indigo-700 hover:text-indigo-900 cursor-pointer"
          >
            <Info className="w-3.5 h-3.5" />
            <span>{showAnalysis ? 'Hide Analysis Details' : 'View Analysis Details (Why this recommendation?)'}</span>
            {showAnalysis ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {showAnalysis && (
            <div className="mt-2.5 pt-2 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
              {(currentData?.transparency_points && currentData.transparency_points.length > 0
                ? currentData.transparency_points
                : [
                    `Current temperature is ${currentData?.temperature ?? 62}°C`,
                    `Vibration RMS is ${currentData?.vibration ?? 0.2} mm/s`,
                    `Motor current is ${currentData?.motor_current ?? 8.0} A`,
                    `Failure probability is evaluated at ${currentData?.failure_risk_pct ?? 0}%`,
                    `Predicted RUL is ${currentData?.predicted_rul_days ?? 200} days`
                  ]
              ).map((pt, idx) => (
                <div key={idx} className="bg-white/90 px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-700 shadow-2xs flex items-start space-x-2">
                  <span className="text-indigo-600 font-bold shrink-0">•</span>
                  <span>{pt}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top Banner / System State Summary for Selected PLC */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-200 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${conditionStr === 'Critical' ? 'bg-red-100 text-red-700' : conditionStr === 'Warning' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-gray-500 font-semibold uppercase tracking-wider">{formatPlcDisplay(selectedPlc)} Machine Condition</div>
            <div className="text-sm font-bold text-gray-900 flex items-center gap-2">
              <span>{conditionStr}</span>
              <span className="text-gray-300">•</span>
              <span className={`text-xs font-semibold ${anomalyStr === 'Anomaly Detected' ? 'text-red-600 font-bold' : 'text-emerald-600'}`}>
                {anomalyStr === 'Anomaly Detected' ? '⚠️ Anomaly Detected (Isolation Forest)' : '✓ Normal Operation'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <div>
            <span className="text-xs text-gray-500 block">Failure Risk (Probability)</span>
            <span className={`text-base font-bold font-mono ${failureRisk > 50 ? 'text-red-600' : failureRisk > 25 ? 'text-amber-600' : 'text-emerald-600'}`}>
              {failureRisk.toFixed(1)}% <span className="text-[10px] font-normal text-gray-500">Prob</span>
            </span>
          </div>

          <div>
            <span className="text-xs text-gray-500 block">RUL Confidence</span>
            <span className="text-base font-bold font-mono text-blue-600">
              {confidence.toFixed(1)}%
            </span>
          </div>

          <div className="hidden sm:block max-w-xs">
            <span className="text-xs text-gray-500 block">Recommendation</span>
            <span className="text-xs font-bold text-gray-800 bg-gray-100 px-2 py-0.5 rounded border border-gray-200 block truncate" title={currentData?.recommendation || currentData?.financial_decision || 'Continue routine monitoring'}>
              {currentData?.recommendation || currentData?.financial_decision || 'Continue routine monitoring'}
            </span>
          </div>

          <div>
            <span className="text-xs text-gray-500 block">Active ML Model</span>
            <span className="text-xs font-bold text-gray-800 bg-gray-100 px-2.5 py-1 rounded border border-gray-200 block">
              {currentData?.model_used || 'Random Forest Regressor'}
            </span>
          </div>
        </div>
      </div>

      {/* Row 1: Health Gauge and Sensor + RUL Metric Cards for Selected PLC */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 items-stretch">
        <div className="lg:col-span-1 min-w-[200px]">
          <GaugeCard value={health} statusColor={statusColor} />
        </div>

        <MetricCard
          title="Remaining Useful Life"
          value={currentData?.predicted_rul_days ?? '--'}
          unit="Days"
          icon={Calendar}
          valueColor="text-blue-600"
        />

        <MetricCard
          title="Machine Stage"
          badgeComponent={<StatusBadge status={currentData?.machine_status || 'Healthy'} />}
        />

        <MetricCard
          title="Temperature"
          value={currentData?.temperature ?? '--'}
          unit="°C"
          icon={Thermometer}
        />

        <MetricCard
          title="Vibration RMS"
          value={currentData?.vibration ?? '--'}
          unit="mm/s"
          icon={Activity}
        />

        <MetricCard
          title="Motor Current"
          value={currentData?.motor_current ?? '--'}
          unit="A"
          icon={Zap}
        />

        <MetricCard
          title="Pressure"
          value={currentData?.pressure ?? '--'}
          unit="bar"
          icon={Gauge}
        />
      </div>

      {/* Row 2: Live Sensor Graph */}
      <LiveChart
        historyData={historyData}
        selectedPlc={selectedPlc}
        setSelectedPlc={setSelectedPlc}
        selectedTag={selectedTag}
        setSelectedTag={setSelectedTag}
        plcsList={displayPlcs}
      />

      {/* Row 3: Recent Sensor Readings Table */}
      <SensorTable logs={logs} />

      {/* ADD PLC MODAL */}
      {showAddPlcModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-r from-indigo-600 to-blue-700 p-4 text-white flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Plus className="w-5 h-5 text-white" />
                <h3 className="text-sm font-bold">Add New Industrial PLC Unit</h3>
              </div>
              <button onClick={() => setShowAddPlcModal(false)} className="text-white/80 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddPlc} className="p-5 space-y-4 text-xs">
              {addPlcError && (
                <div className="bg-red-50 border border-red-200 text-red-700 p-2.5 rounded-lg text-xs font-semibold">
                  {addPlcError}
                </div>
              )}

              <div>
                <label className="text-[11px] font-bold text-gray-700 block mb-1">
                  PLC Identifier (e.g. PLC_06 or leave blank for auto)
                </label>
                <input
                  type="text"
                  placeholder="Auto-generate (e.g. PLC_06)"
                  value={addPlcForm.plc_id}
                  onChange={(e) => setAddPlcForm({ ...addPlcForm, plc_id: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold text-gray-700 block mb-1">
                  Machine Description / Unit Role
                </label>
                <input
                  type="text"
                  placeholder="e.g. Auxiliary Booster Pump"
                  value={addPlcForm.name}
                  onChange={(e) => setAddPlcForm({ ...addPlcForm, name: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-bold text-gray-700 block mb-1">Initial Degradation (0-1)</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0.0"
                    max="0.9"
                    value={addPlcForm.deg_init}
                    onChange={(e) => setAddPlcForm({ ...addPlcForm, deg_init: e.target.value })}
                    className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-gray-700 block mb-1">Base Load (0.1 - 1.0)</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="1.0"
                    value={addPlcForm.base_load}
                    onChange={(e) => setAddPlcForm({ ...addPlcForm, base_load: e.target.value })}
                    className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 font-mono"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-gray-200 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowAddPlcModal(false)}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg shadow-sm transition"
                >
                  Register PLC
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
