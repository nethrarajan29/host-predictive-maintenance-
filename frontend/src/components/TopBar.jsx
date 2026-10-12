import React, { useState, useEffect } from 'react';
import { Cpu, Database, Activity, Clock, ShieldCheck } from 'lucide-react';

const TopBar = ({ backendStatus, statusData }) => {
  const [timeStr, setTimeStr] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeStr(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="bg-slate-900 text-white px-6 py-3 shadow-md flex items-center justify-between text-xs sm:text-sm font-medium border-b border-slate-800">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          <span className="bg-blue-600 text-white px-2 py-0.5 rounded text-xs font-bold tracking-wide">MACHINE</span>
          <span className="font-semibold text-slate-100">{statusData?.machine_id || 'MCH-802X'}</span>
        </div>
        <div className="hidden md:flex items-center space-x-1.5 text-slate-300">
          <Cpu className="w-4 h-4 text-blue-400" />
          <span>{statusData?.machine_name || 'Turbine Motor Unit A1'}</span>
        </div>
        <div className="hidden lg:flex items-center space-x-1.5 text-slate-400">
          <Database className="w-4 h-4 text-slate-400" />
          <span>{statusData?.data_source || 'Synthetic Sensor Stream'}</span>
        </div>
      </div>

      <div className="flex items-center space-x-6">
        <div className="hidden sm:flex items-center space-x-1.5 text-slate-300">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>{statusData?.model || 'Random Forest Regressor'}</span>
        </div>

        <div className="flex items-center space-x-1.5 text-slate-300 font-mono">
          <Clock className="w-4 h-4 text-slate-400" />
          <span>{timeStr}</span>
        </div>
        <div className="flex items-center space-x-2 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">
          <span className={`w-2.5 h-2.5 rounded-full ${backendStatus ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></span>
          <span className="text-xs font-semibold text-slate-200">{backendStatus ? 'SYSTEM ONLINE' : 'DISCONNECTED'}</span>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
