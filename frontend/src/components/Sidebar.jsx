import React from 'react';
import { LayoutDashboard, LineChart, Cpu, Wrench, Play, Pause, SkipForward, RotateCcw, Sliders, Wifi, WifiOff, Activity, Layers } from 'lucide-react';
import StatusBadge from './StatusBadge';

const Sidebar = ({ activeTab, setActiveTab, currentData, backendStatus, onControlAction, speed, setSpeed, autoPlay }) => {
  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col justify-between h-[calc(100vh-49px)] shadow-sm shrink-0">
      <div className="p-4 space-y-6">
        {/* Title */}
        <div>
          <h1 className="text-base font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-blue-600" />
            <span>AI Predictive Maintenance</span>
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">Enterprise PDM System v2.4</p>
        </div>

        {/* Navigation Tabs */}
        <nav className="space-y-1">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'dashboard'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Live Monitoring</span>
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'analytics'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <LineChart className="w-4 h-4" />
            <span>Analytics</span>
          </button>
          <button
            onClick={() => setActiveTab('maintenance')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'maintenance'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <Wrench className="w-4 h-4" />
            <span>Maintenance</span>
          </button>
          <button
            onClick={() => setActiveTab('evaluation')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'evaluation'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>Model Evaluation</span>
          </button>
          <button
            onClick={() => setActiveTab('drift')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'drift'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <Activity className="w-4 h-4 text-blue-600" />
            <span>Sensor Reliability & Drift</span>
          </button>
          <button
            onClick={() => setActiveTab('digital_thread')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'digital_thread'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <Layers className="w-4 h-4 text-blue-600" />
            <span>Asset Digital Thread</span>
          </button>
        </nav>

        {/* Machine Status Box */}
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">Machine Status</div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-800">Operational Stage</span>
            <StatusBadge status={currentData?.machine_status || 'Healthy'} />
          </div>
          <div className="flex items-center justify-between text-xs text-gray-600 pt-1 border-t border-gray-200">
            <span>Health Index</span>
            <span className="font-bold text-gray-900">{currentData?.machine_health ?? 100}%</span>
          </div>
        </div>

        {/* Simulation Controls */}
        <div className="space-y-3 pt-2 border-t border-gray-200">
          <div className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center space-x-1">
            <Sliders className="w-3.5 h-3.5 text-gray-500" />
            <span>Simulation Controls</span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => onControlAction('start')}
              className={`flex items-center justify-center space-x-1 py-1.5 px-2 rounded text-xs font-semibold transition ${
                autoPlay ? 'bg-emerald-600 text-white shadow-sm' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Play className="w-3.5 h-3.5" />
              <span>Start</span>
            </button>
            <button
              onClick={() => onControlAction('pause')}
              className={`flex items-center justify-center space-x-1 py-1.5 px-2 rounded text-xs font-semibold transition ${
                !autoPlay ? 'bg-amber-600 text-white shadow-sm' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Pause className="w-3.5 h-3.5" />
              <span>Pause</span>
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => onControlAction('next')}
              className="flex items-center justify-center space-x-1 py-1.5 px-2 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-semibold border border-blue-200"
            >
              <SkipForward className="w-3.5 h-3.5" />
              <span>Next</span>
            </button>
            <button
              onClick={() => onControlAction('reset')}
              className="flex items-center justify-center space-x-1 py-1.5 px-2 rounded bg-gray-100 text-gray-700 hover:bg-gray-200 text-xs font-semibold"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>

          {/* Speed Slider */}
          <div className="space-y-1 pt-2">
            <div className="flex justify-between text-xs text-gray-600">
              <span>Speed</span>
              <span className="font-semibold text-gray-900">{speed}s</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="3.0"
              step="0.1"
              value={speed}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setSpeed(val);
                onControlAction('set_speed', val);
              }}
              className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
          </div>

          {/* Auto Play Toggle */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-gray-600">Auto Play</span>
            <button
              onClick={() => onControlAction(autoPlay ? 'pause' : 'start')}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                autoPlay ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  autoPlay ? 'translate-x-4' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Footer Backend Connection Status */}
      <div className="p-4 border-t border-gray-200 bg-gray-50/50">
        <div className="flex items-center space-x-2 text-xs">
          {backendStatus ? (
            <Wifi className="w-4 h-4 text-emerald-600" />
          ) : (
            <WifiOff className="w-4 h-4 text-red-600" />
          )}
          <div className="flex flex-col">
            <span className="font-semibold text-gray-800">
              {backendStatus ? 'Backend Connected' : 'Disconnected'}
            </span>
            <span className="text-[10px] text-gray-500">REST API (1s Polling)</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
