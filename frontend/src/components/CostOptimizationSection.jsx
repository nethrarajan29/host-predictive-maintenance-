import React, { useState, useEffect } from 'react';
import {
  DollarSign,
  Zap,
  Wrench,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Plus,
  Settings,
  RefreshCw,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Activity,
  Clock,
  Calendar,
  Layers,
  Cpu,
  Info,
  Sliders,
  Check,
  X
} from 'lucide-react';
import Plot from 'react-plotly.js';
import StatusBadge from './StatusBadge';
import { isValidPlcId, formatPlcDisplay, getPlcNumber, isPlcMatch } from '../utils/plcValidation';
import {
  getMaintenanceOptimization,
  getMaintenanceConfig,
  postMaintenanceConfig,
  postAddPlc
} from '../services/api';

const CostOptimizationSection = ({
  selectedPlc = 'PLC_01',
  setSelectedPlc,
  plcsList = [],
  currentData,
  onPlcAdded
}) => {
  const [loading, setLoading] = useState(false);
  const [optData, setOptData] = useState(null);
  const [config, setConfig] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showAddPlcModal, setShowAddPlcModal] = useState(false);
  const [showWhyDetails, setShowWhyDetails] = useState(true);

  // Configuration Form State
  const [configForm, setConfigForm] = useState({
    labour_cost: 2500,
    spare_parts_cost: 3500,
    inspection_cost: 1200,
    service_cost: 800,
    other_expenses: 0,
    repair_replacement_cost: 14000,
    downtime_cost: 8000,
    production_loss: 5000,
    emergency_labour_cost: 4000,
    electricity_rate: 8.0,
    nominal_voltage: 415.0,
    power_factor: 0.85,
    operating_hours_per_day: 24.0,
    rul_critical_days: 3.0,
    rul_urgent_days: 7.0,
    rul_schedule_days: 15.0,
    rul_plan_days: 30.0
  });

  // Add PLC Form State
  const [addPlcForm, setAddPlcForm] = useState({
    plc_id: '',
    name: '',
    deg_init: 0.05,
    base_load: 0.60,
    temp_offset: 0.0,
    vib_offset: 0.0
  });
  const [addPlcError, setAddPlcError] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);

  // Fetch optimization data
  const fetchOptimizationData = async (plcId = selectedPlc) => {
    try {
      setLoading(true);
      const data = await getMaintenanceOptimization(plcId);
      if (data) {
        setOptData(data);
        if (data.config) {
          setConfig(data.config);
          setConfigForm((prev) => ({ ...prev, ...data.config }));
        }
      }
    } catch (err) {
      console.error('Failed to load maintenance optimization data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOptimizationData(selectedPlc);
  }, [selectedPlc]);

  // Handle saving cost configuration
  const handleSaveConfig = async (e) => {
    e.preventDefault();
    try {
      setSavingConfig(true);
      const res = await postMaintenanceConfig(configForm);
      if (res && res.config) {
        setConfig(res.config);
        setShowConfigModal(false);
        await fetchOptimizationData(selectedPlc);
      }
    } catch (err) {
      console.error('Failed to save config:', err);
    } finally {
      setSavingConfig(false);
    }
  };

  // Reset config defaults
  const handleResetConfigDefaults = () => {
    setConfigForm({
      labour_cost: 2500,
      spare_parts_cost: 3500,
      inspection_cost: 1200,
      service_cost: 800,
      other_expenses: 0,
      repair_replacement_cost: 14000,
      downtime_cost: 8000,
      production_loss: 5000,
      emergency_labour_cost: 4000,
      electricity_rate: 8.0,
      nominal_voltage: 415.0,
      power_factor: 0.85,
      operating_hours_per_day: 24.0,
      rul_critical_days: 3.0,
      rul_urgent_days: 7.0,
      rul_schedule_days: 15.0,
      rul_plan_days: 30.0
    });
  };

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
        await fetchOptimizationData(res.plc_id || selectedPlc);
        if (onPlcAdded) onPlcAdded(res.plc_id);
      } else if (res && res.status === 'exists') {
        setAddPlcError(res.message || 'PLC ID already exists.');
      }
    } catch (err) {
      console.error('Failed to add PLC:', err);
      setAddPlcError('Failed to add PLC. Please check ID format.');
    }
  };

  const cards = optData?.summary_cards || {
    machines_requiring_maintenance: 0,
    critical_plcs: 0,
    average_rul: 200,
    estimated_maintenance_cost: 0,
    expected_failure_cost: 0,
    potential_cost_savings: 0,
    energy_inefficiency_pct: 0,
    additional_energy_cost_daily: 0
  };

  const selectedDecision = optData?.selected_plc_decision;
  const plcsTable = optData?.plcs_maintenance_table || [];
  const costChartData = optData?.cost_chart_data || [];
  const energyChartData = optData?.energy_chart_data || [];

  const getPriorityBadgeClass = (priority) => {
    switch (priority) {
      case 'Critical':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'Urgent':
      case 'High':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'Medium':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      default:
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    }
  };

  const getPriorityDot = (priority) => {
    switch (priority) {
      case 'Critical': return '🔴';
      case 'Urgent':
      case 'High': return '🟠';
      case 'Medium': return '🟡';
      default: return '🟢';
    }
  };

  return (
    <div className="space-y-6">
      {/* SECTION HEADER & CONTROL TOOLBAR */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-200 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-gradient-to-br from-indigo-500 to-blue-600 rounded-xl text-white shadow-sm">
            <DollarSign className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900">
              Maintenance Cost Optimization & Energy-Aware PDM Engine
            </h2>
            <p className="text-xs text-gray-500">
              Financial cost-benefit analysis, electrical energy anomaly attribution, and multi-PLC prioritization
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Add PLC Button */}
          <button
            onClick={() => setShowAddPlcModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold rounded-lg border border-indigo-200 transition shadow-2xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add PLC</span>
          </button>

          {/* Cost & Energy Config Button */}
          <button
            onClick={() => setShowConfigModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-gray-50 hover:bg-gray-100 text-gray-700 text-xs font-bold rounded-lg border border-gray-300 transition shadow-2xs cursor-pointer"
          >
            <Settings className="w-3.5 h-3.5 text-gray-500" />
            <span>Cost & Energy Config</span>
          </button>

          {/* Refresh Button */}
          <button
            onClick={() => fetchOptimizationData(selectedPlc)}
            disabled={loading}
            className="flex items-center space-x-1 px-2.5 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-lg transition cursor-pointer"
            title="Refresh Analysis"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* 8 DYNAMIC DASHBOARD SUMMARY CARDS (Requirement 13) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        {/* Card 1: Machines Requiring Maintenance */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Maint. Required</span>
            <Wrench className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div>
            <div className="text-xl font-black text-gray-900 font-mono">
              {cards.machines_requiring_maintenance}
            </div>
            <span className="text-[10px] text-amber-700 font-medium">of {cards.total_plcs || 5} PLCs</span>
          </div>
        </div>

        {/* Card 2: Critical PLCs */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Critical PLCs</span>
            <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
          </div>
          <div>
            <div className={`text-xl font-black font-mono ${cards.critical_plcs > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
              {cards.critical_plcs}
            </div>
            <span className="text-[10px] text-gray-500 font-medium">Immediate action</span>
          </div>
        </div>

        {/* Card 3: Average RUL */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Average RUL</span>
            <Calendar className="w-3.5 h-3.5 text-blue-500" />
          </div>
          <div>
            <div className="text-xl font-black text-blue-700 font-mono">
              {Math.round(cards.average_rul)} <span className="text-xs font-normal text-gray-500">Days</span>
            </div>
            <span className="text-[10px] text-gray-500 font-medium">Across active units</span>
          </div>
        </div>

        {/* Card 4: Estimated Maintenance Cost */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Est. Maint Cost</span>
            <DollarSign className="w-3.5 h-3.5 text-indigo-500" />
          </div>
          <div>
            <div className="text-xl font-black text-indigo-900 font-mono">
              ₹{cards.estimated_maintenance_cost.toLocaleString()}
            </div>
            <span className="text-[10px] text-gray-500 font-medium">Planned service</span>
          </div>
        </div>

        {/* Card 5: Expected Failure Cost */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Expected Failure</span>
            <AlertCircle className="w-3.5 h-3.5 text-red-500" />
          </div>
          <div>
            <div className="text-xl font-black text-red-700 font-mono">
              ₹{cards.expected_failure_cost.toLocaleString()}
            </div>
            <span className="text-[10px] text-red-600 font-medium">Risk exposure</span>
          </div>
        </div>

        {/* Card 6: Potential Cost Savings */}
        <div className="bg-white p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/20 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800">Net Savings</span>
            <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <div>
            <div className="text-xl font-black text-emerald-700 font-mono">
              ₹{cards.potential_cost_savings.toLocaleString()}
            </div>
            <span className="text-[10px] text-emerald-700 font-medium">Preventive gain</span>
          </div>
        </div>

        {/* Card 7: Energy Inefficiency */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Energy Excess</span>
            <Zap className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div>
            <div className={`text-xl font-black font-mono ${cards.energy_inefficiency_pct > 10 ? 'text-amber-600' : 'text-gray-900'}`}>
              +{cards.energy_inefficiency_pct.toFixed(1)}%
            </div>
            <span className="text-[10px] text-gray-500 font-medium">Above baseline</span>
          </div>
        </div>

        {/* Card 8: Additional Energy Cost */}
        <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-500 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Daily Energy Loss</span>
            <Zap className="w-3.5 h-3.5 text-orange-500" />
          </div>
          <div>
            <div className="text-xl font-black text-orange-700 font-mono">
              ₹{cards.additional_energy_cost_daily.toLocaleString()}<span className="text-[10px] font-normal text-gray-500">/day</span>
            </div>
            <span className="text-[10px] text-gray-500 font-medium">@ ₹{config?.electricity_rate || 8}/kWh</span>
          </div>
        </div>
      </div>

      {/* SELECTED PLC DECISION SPOTLIGHT (Requirements 2, 8, 10, 18, 20) */}
      {selectedDecision && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {/* Header Strip with Priority & Concise Alert */}
          <div className={`px-5 py-3.5 border-b flex flex-wrap items-center justify-between gap-3 ${
            selectedDecision.priority === 'Critical'
              ? 'bg-red-50 border-red-200'
              : selectedDecision.priority === 'High'
              ? 'bg-orange-50 border-orange-200'
              : selectedDecision.priority === 'Medium'
              ? 'bg-amber-50 border-amber-200'
              : 'bg-emerald-50 border-emerald-200'
          }`}>
            <div className="flex items-center space-x-3">
              <span className="text-xl">{getPriorityDot(selectedDecision.priority)}</span>
              <div>
                <span className="text-[11px] font-extrabold uppercase tracking-wider text-gray-600">
                  {selectedDecision.plc_id} Predictive Decision Summary
                </span>
                <h3 className="text-base font-black text-gray-900 flex items-center gap-2">
                  <span>{selectedDecision.main_issue}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-bold border ${getPriorityBadgeClass(selectedDecision.priority)}`}>
                    {selectedDecision.priority} Priority
                  </span>
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="bg-white px-3 py-1 rounded-lg border border-gray-200 shadow-2xs">
                <span className="text-gray-400 text-[10px] block">RUL</span>
                <span className="font-bold text-blue-700">{selectedDecision.rul_recommendation?.time_short}</span>
              </div>
              <div className="bg-white px-3 py-1 rounded-lg border border-gray-200 shadow-2xs">
                <span className="text-gray-400 text-[10px] block">Energy</span>
                <span className="font-bold text-amber-700">{selectedDecision.concise_alert?.energy_text}</span>
              </div>
              <div className="bg-white px-3 py-1 rounded-lg border border-gray-200 shadow-2xs">
                <span className="text-gray-400 text-[10px] block">Potential Saving</span>
                <span className="font-bold text-emerald-700">{selectedDecision.concise_alert?.savings_text}</span>
              </div>
            </div>
          </div>

          {/* THE 3 CORE QUESTIONS (Requirement: "The final system should answer three questions clearly") */}
          <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-4 border-b border-gray-100">
            {/* Question 1: What is wrong with the machine? */}
            <div className="bg-gray-50/70 p-4 rounded-xl border border-gray-200 flex flex-col justify-between">
              <div>
                <div className="flex items-center space-x-2 text-indigo-700 mb-2">
                  <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-800 flex items-center justify-center text-xs font-bold font-mono">1</span>
                  <h4 className="text-xs font-extrabold uppercase tracking-wider text-gray-700">What is wrong with the machine?</h4>
                </div>
                <div className="text-sm font-bold text-gray-900 leading-snug">
                  {selectedDecision.q1_what_is_wrong}
                </div>
                <p className="text-xs text-gray-600 mt-1 leading-relaxed">
                  {selectedDecision.issue_detail}
                </p>
              </div>
              <div className="mt-3 pt-2 border-t border-gray-200 text-[11px] text-gray-500 font-mono">
                Condition: <span className="font-semibold text-gray-800">{selectedDecision.machine_status}</span> ({selectedDecision.machine_health}% Health)
              </div>
            </div>

            {/* Question 2: When should I maintain it? */}
            <div className="bg-gray-50/70 p-4 rounded-xl border border-gray-200 flex flex-col justify-between">
              <div>
                <div className="flex items-center space-x-2 text-blue-700 mb-2">
                  <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-800 flex items-center justify-center text-xs font-bold font-mono">2</span>
                  <h4 className="text-xs font-extrabold uppercase tracking-wider text-gray-700">When should I maintain it?</h4>
                </div>
                <div className="text-sm font-bold text-gray-900 leading-snug">
                  {selectedDecision.rul_recommendation?.predicted_time_str}
                </div>
                <div className="mt-2 bg-blue-50 border border-blue-200 text-blue-900 text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-blue-600 shrink-0" />
                  <span>Action: {selectedDecision.rul_recommendation?.recommended_deadline_str}</span>
                </div>
              </div>
              <div className="mt-3 pt-2 border-t border-gray-200 text-[11px] text-gray-500 font-mono">
                Predicted RUL: <span className="font-bold text-blue-700">{selectedDecision.predicted_rul_days} Days</span> ({selectedDecision.rul_recommendation?.rul_category})
              </div>
            </div>

            {/* Question 3: Why should I maintain it now? */}
            <div className="bg-gray-50/70 p-4 rounded-xl border border-gray-200 flex flex-col justify-between">
              <div>
                <div className="flex items-center space-x-2 text-emerald-700 mb-2">
                  <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-xs font-bold font-mono">3</span>
                  <h4 className="text-xs font-extrabold uppercase tracking-wider text-gray-700">Why should I maintain it now?</h4>
                </div>
                <p className="text-xs font-medium text-gray-800 leading-relaxed">
                  {selectedDecision.q3_why_now}
                </p>
                <div className="mt-2 text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-lg">
                  {selectedDecision.cost_optimization?.financial_recommendation}
                </div>
              </div>
              <div className="mt-3 pt-2 border-t border-gray-200 text-[11px] text-gray-500 flex justify-between font-mono">
                <span>Preventive: ₹{selectedDecision.cost_optimization?.preventive_cost?.toLocaleString()}</span>
                <span>Expected Fail: ₹{selectedDecision.cost_optimization?.expected_failure_cost?.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* EXPANDABLE TRANSPARENCY SECTION ("Why this recommendation?") */}
          <div className="px-5 py-3 bg-gray-50/50 flex flex-col space-y-2">
            <button
              onClick={() => setShowWhyDetails(!showWhyDetails)}
              className="flex items-center justify-between text-xs font-bold text-gray-700 hover:text-gray-900 cursor-pointer"
            >
              <div className="flex items-center space-x-2">
                <Info className="w-4 h-4 text-blue-600" />
                <span>Why this recommendation? (Engineering & Financial Attribution)</span>
              </div>
              {showWhyDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showWhyDetails && (
              <div className="pt-2 pb-1 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {(selectedDecision.transparency_points || []).map((pt, idx) => (
                  <div key={idx} className="bg-white px-3 py-2 rounded-lg border border-gray-200 text-xs text-gray-700 flex items-start space-x-2 shadow-2xs">
                    <span className="text-indigo-600 font-bold shrink-0">•</span>
                    <span>{pt}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TWO CHARTS: MAINTENANCE COST COMPARISON + ENERGY MONITORING (Requirements 14 & 15) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1: Preventive Maintenance Cost vs Expected Failure Cost */}
        <div className="industrial-card p-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider flex items-center space-x-1.5">
                <BarChart3 className="w-4 h-4 text-indigo-600" />
                <span>Preventive Maintenance Cost vs Expected Failure Cost</span>
              </h3>
              <p className="text-[11px] text-gray-500">
                Comparing planned servicing vs probability-weighted failure impact for each PLC
              </p>
            </div>
          </div>

          <div className="w-full h-64">
            <Plot
              data={[
                {
                  x: costChartData.map((d) => d.plc_id),
                  y: costChartData.map((d) => d.preventive_cost),
                  name: 'Preventive Cost (₹)',
                  type: 'bar',
                  marker: { color: '#3B82F6' },
                  hovertemplate: '<b>%{x}</b><br>Preventive: ₹%{y:,.0f}<extra></extra>'
                },
                {
                  x: costChartData.map((d) => d.plc_id),
                  y: costChartData.map((d) => d.expected_failure_cost),
                  name: 'Expected Failure Cost (₹)',
                  type: 'bar',
                  marker: {
                    color: costChartData.map((d) => (d.is_cost_effective ? '#EF4444' : '#9CA3AF'))
                  },
                  hovertemplate: '<b>%{x}</b><br>Failure Cost: ₹%{y:,.0f}<extra></extra>'
                }
              ]}
              layout={{
                autosize: true,
                height: 240,
                barmode: 'group',
                margin: { l: 50, r: 15, t: 20, b: 35 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: '#FAFAFA',
                xaxis: {
                  title: { text: 'Machine / PLC', font: { size: 10, color: '#6B7280' } },
                  gridcolor: '#E5E7EB'
                },
                yaxis: {
                  title: { text: 'Cost (₹)', font: { size: 10, color: '#6B7280' } },
                  gridcolor: '#E5E7EB'
                },
                legend: {
                  orientation: 'h',
                  y: 1.15,
                  x: 1,
                  xanchor: 'right',
                  font: { size: 10 }
                }
              }}
              useResizeHandler={true}
              style={{ width: '100%', height: '100%' }}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>

        {/* Chart 2: Energy Monitoring & Baseline Comparison */}
        <div className="industrial-card p-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider flex items-center space-x-1.5">
                <Zap className="w-4 h-4 text-amber-500" />
                <span>3-Phase Electrical Energy Consumption & Baseline</span>
              </h3>
              <p className="text-[11px] text-gray-500">
                Daily energy consumption (kWh/day) compared against healthy operational baseline
              </p>
            </div>
          </div>

          <div className="w-full h-64">
            <Plot
              data={[
                {
                  x: energyChartData.map((d) => d.plc_id),
                  y: energyChartData.map((d) => d.baseline_energy),
                  name: 'Normal Baseline (kWh/day)',
                  type: 'bar',
                  marker: { color: '#10B981' },
                  hovertemplate: '<b>%{x}</b><br>Baseline: %{y:.1f} kWh/day<extra></extra>'
                },
                {
                  x: energyChartData.map((d) => d.plc_id),
                  y: energyChartData.map((d) => d.current_energy),
                  name: 'Current Consumption (kWh/day)',
                  type: 'bar',
                  marker: {
                    color: energyChartData.map((d) => (d.excess_pct > 10 ? '#F59E0B' : '#60A5FA'))
                  },
                  hovertemplate: '<b>%{x}</b><br>Current: %{y:.1f} kWh/day (+%{text}%)<extra></extra>',
                  text: energyChartData.map((d) => d.excess_pct)
                }
              ]}
              layout={{
                autosize: true,
                height: 240,
                barmode: 'group',
                margin: { l: 50, r: 15, t: 20, b: 35 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: '#FAFAFA',
                xaxis: {
                  title: { text: 'Machine / PLC', font: { size: 10, color: '#6B7280' } },
                  gridcolor: '#E5E7EB'
                },
                yaxis: {
                  title: { text: 'Energy (kWh/day)', font: { size: 10, color: '#6B7280' } },
                  gridcolor: '#E5E7EB'
                },
                legend: {
                  orientation: 'h',
                  y: 1.15,
                  x: 1,
                  xanchor: 'right',
                  font: { size: 10 }
                }
              }}
              useResizeHandler={true}
              style={{ width: '100%', height: '100%' }}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>
      </div>

      {/* PLC-WISE MAINTENANCE TABLE (Requirements 11 & 12) */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center justify-between gap-3 bg-gray-50/50">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-600" />
              <span>PLC-Wise Predictive Maintenance & Cost Optimization Register</span>
            </h3>
            <p className="text-xs text-gray-500">
              Ranked dynamically by maintenance urgency, operational risk, and financial cost-benefit
            </p>
          </div>
          <span className="text-xs text-gray-600 bg-white px-2.5 py-1 rounded border border-gray-200 font-mono">
            {plcsTable.length} Monitored PLCs
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-600">
            <thead className="bg-gray-50 text-[10px] uppercase font-bold text-gray-500 tracking-wider border-b border-gray-200">
              <tr>
                <th className="py-3 px-4">PLC Unit</th>
                <th className="py-3 px-3">Health</th>
                <th className="py-3 px-4">Main Issue</th>
                <th className="py-3 px-3">RUL</th>
                <th className="py-3 px-3">Failure Risk</th>
                <th className="py-3 px-3">Energy Status</th>
                <th className="py-3 px-3">Maint. Cost</th>
                <th className="py-3 px-3">Expected Failure</th>
                <th className="py-3 px-3">Potential Saving</th>
                <th className="py-3 px-3">Priority</th>
                <th className="py-3 px-4">Recommendation</th>
                <th className="py-3 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {plcsTable.map((row) => {
                const isSelected = isPlcMatch(row.plc_id, selectedPlc);
                return (
                  <tr
                    key={row.plc_id}
                    onClick={() => setSelectedPlc && setSelectedPlc(row.plc_id)}
                    className={`transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-50/60 font-semibold'
                        : 'hover:bg-gray-50/80'
                    }`}
                  >
                    <td className="py-3 px-4 font-bold text-gray-900 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <span>{getPriorityDot(row.priority)}</span>
                        <span>{row.plc_id}</span>
                      </div>
                      <span className="text-[10px] text-gray-400 block font-normal">{row.name?.split('(')[1]?.replace(')', '') || ''}</span>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap">
                      <StatusBadge status={row.machine_status} />
                      <span className="text-[10px] text-gray-400 block mt-0.5">{row.machine_health}%</span>
                    </td>

                    <td className="py-3 px-4 text-gray-800 font-medium max-w-[160px] truncate" title={row.main_issue}>
                      {row.main_issue}
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap font-mono">
                      <span className="font-bold text-blue-700">{row.predicted_rul_days} d</span>
                      <span className="text-[10px] text-gray-400 block">{row.rul_time_str}</span>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap font-mono font-bold">
                      <span className={row.failure_risk_pct > 50 ? 'text-red-600' : row.failure_risk_pct > 25 ? 'text-amber-600' : 'text-emerald-600'}>
                        {row.failure_risk_pct?.toFixed(1)}%
                      </span>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${
                        row.excess_energy_pct > 15
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : row.excess_energy_pct > 8
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      }`}>
                        +{row.excess_energy_pct?.toFixed(1)}%
                      </span>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap font-mono text-gray-700">
                      ₹{row.preventive_cost?.toLocaleString()}
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap font-mono text-gray-900 font-medium">
                      ₹{row.expected_failure_cost?.toLocaleString()}
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap font-mono font-bold">
                      <span className={row.potential_savings > 0 ? 'text-emerald-700' : 'text-gray-400'}>
                        {row.potential_savings > 0 ? `+₹${row.potential_savings?.toLocaleString()}` : '₹0'}
                      </span>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getPriorityBadgeClass(row.priority)}`}>
                        {row.priority}
                      </span>
                    </td>

                    <td className="py-3 px-4 max-w-[180px] truncate text-gray-700" title={row.recommendation}>
                      {row.recommendation}
                    </td>

                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedPlc && setSelectedPlc(row.plc_id);
                        }}
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                          isSelected
                            ? 'bg-indigo-600 text-white shadow-2xs'
                            : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                        }`}
                      >
                        {isSelected ? 'Active' : 'Inspect'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* COST & ENERGY CONFIGURATION MODAL (Requirement 4 & 9) */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden max-h-[90vh] flex flex-col">
            <div className="bg-gradient-to-r from-gray-900 to-slate-800 p-4 text-white flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Sliders className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-bold">Cost & Energy Optimization Configuration</h3>
              </div>
              <button onClick={() => setShowConfigModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveConfig} className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
              {/* Preventive Maintenance Costs */}
              <div>
                <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-2 pb-1 border-b border-gray-200 flex items-center justify-between">
                  <span>1. Preventive Maintenance Cost Components (₹)</span>
                  <span className="text-indigo-600 font-mono">
                    Total: ₹{(
                      Number(configForm.labour_cost || 0) +
                      Number(configForm.spare_parts_cost || 0) +
                      Number(configForm.inspection_cost || 0) +
                      Number(configForm.service_cost || 0) +
                      Number(configForm.other_expenses || 0)
                    ).toLocaleString()}
                  </span>
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Labour Cost (₹)</label>
                    <input
                      type="number"
                      value={configForm.labour_cost}
                      onChange={(e) => setConfigForm({ ...configForm, labour_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Spare Parts (₹)</label>
                    <input
                      type="number"
                      value={configForm.spare_parts_cost}
                      onChange={(e) => setConfigForm({ ...configForm, spare_parts_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Inspection Cost (₹)</label>
                    <input
                      type="number"
                      value={configForm.inspection_cost}
                      onChange={(e) => setConfigForm({ ...configForm, inspection_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Service Fee (₹)</label>
                    <input
                      type="number"
                      value={configForm.service_cost}
                      onChange={(e) => setConfigForm({ ...configForm, service_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Other Expenses (₹)</label>
                    <input
                      type="number"
                      value={configForm.other_expenses}
                      onChange={(e) => setConfigForm({ ...configForm, other_expenses: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Failure Impact Components */}
              <div>
                <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-2 pb-1 border-b border-gray-200 flex items-center justify-between">
                  <span>2. Potential Failure Impact Components (₹)</span>
                  <span className="text-red-600 font-mono">
                    Total: ₹{(
                      Number(configForm.repair_replacement_cost || 0) +
                      Number(configForm.downtime_cost || 0) +
                      Number(configForm.production_loss || 0) +
                      Number(configForm.emergency_labour_cost || 0)
                    ).toLocaleString()}
                  </span>
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Repair/Replacement (₹)</label>
                    <input
                      type="number"
                      value={configForm.repair_replacement_cost}
                      onChange={(e) => setConfigForm({ ...configForm, repair_replacement_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Downtime Cost (₹)</label>
                    <input
                      type="number"
                      value={configForm.downtime_cost}
                      onChange={(e) => setConfigForm({ ...configForm, downtime_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Production Loss (₹)</label>
                    <input
                      type="number"
                      value={configForm.production_loss}
                      onChange={(e) => setConfigForm({ ...configForm, production_loss: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Emergency Labour (₹)</label>
                    <input
                      type="number"
                      value={configForm.emergency_labour_cost}
                      onChange={(e) => setConfigForm({ ...configForm, emergency_labour_cost: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Energy & Electricity Parameters */}
              <div>
                <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-2 pb-1 border-b border-gray-200">
                  3. Electrical Energy Specifications (Assumptions)
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Electricity Rate (₹/kWh)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={configForm.electricity_rate}
                      onChange={(e) => setConfigForm({ ...configForm, electricity_rate: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Nominal Voltage (V AC)</label>
                    <input
                      type="number"
                      value={configForm.nominal_voltage}
                      onChange={(e) => setConfigForm({ ...configForm, nominal_voltage: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Power Factor (cos φ)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.5"
                      max="1.0"
                      value={configForm.power_factor}
                      onChange={(e) => setConfigForm({ ...configForm, power_factor: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Daily Operating Hours</label>
                    <input
                      type="number"
                      step="1"
                      min="1"
                      max="24"
                      value={configForm.operating_hours_per_day}
                      onChange={(e) => setConfigForm({ ...configForm, operating_hours_per_day: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* RUL Thresholds */}
              <div>
                <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-2 pb-1 border-b border-gray-200">
                  4. RUL-Based Maintenance Urgency Thresholds (Days)
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Critical (&lt; Days)</label>
                    <input
                      type="number"
                      value={configForm.rul_critical_days}
                      onChange={(e) => setConfigForm({ ...configForm, rul_critical_days: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono text-red-600 font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Urgent (&lt; Days)</label>
                    <input
                      type="number"
                      value={configForm.rul_urgent_days}
                      onChange={(e) => setConfigForm({ ...configForm, rul_urgent_days: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono text-orange-600 font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Schedule (&lt; Days)</label>
                    <input
                      type="number"
                      value={configForm.rul_schedule_days}
                      onChange={(e) => setConfigForm({ ...configForm, rul_schedule_days: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono text-amber-600 font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-gray-600 block mb-1">Plan (&le; Days)</label>
                    <input
                      type="number"
                      value={configForm.rul_plan_days}
                      onChange={(e) => setConfigForm({ ...configForm, rul_plan_days: parseFloat(e.target.value) || 0 })}
                      className="w-full bg-gray-50 border border-gray-300 rounded px-2.5 py-1.5 font-mono text-blue-600 font-bold"
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 border-t border-gray-200 flex items-center justify-between">
                <button
                  type="button"
                  onClick={handleResetConfigDefaults}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition"
                >
                  Reset Defaults
                </button>
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={() => setShowConfigModal(false)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingConfig}
                    className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg shadow-sm transition flex items-center space-x-1.5"
                  >
                    {savingConfig ? (
                      <span>Saving...</span>
                    ) : (
                      <>
                        <Check className="w-4 h-4" />
                        <span>Save & Recalculate</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD PLC MODAL (Requirement 17) */}
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
                  PLC Identifier (e.g. PLC_06, PLC_07 or leave blank for auto)
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
                  placeholder="e.g. Secondary Compressor Unit"
                  value={addPlcForm.name}
                  onChange={(e) => setAddPlcForm({ ...addPlcForm, name: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-bold text-gray-700 block mb-1">Initial Wear (0.0 - 1.0)</label>
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-bold text-gray-700 block mb-1">Temp Offset (°C)</label>
                  <input
                    type="number"
                    step="1.0"
                    value={addPlcForm.temp_offset}
                    onChange={(e) => setAddPlcForm({ ...addPlcForm, temp_offset: e.target.value })}
                    className="w-full bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-gray-700 block mb-1">Vibration Offset (mm/s)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={addPlcForm.vib_offset}
                    onChange={(e) => setAddPlcForm({ ...addPlcForm, vib_offset: e.target.value })}
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

export default CostOptimizationSection;
