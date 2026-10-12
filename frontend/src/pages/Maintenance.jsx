import React from 'react';
import CostOptimizationSection from '../components/CostOptimizationSection';
import MaintenanceDashboard from '../components/MaintenanceDashboard';

const Maintenance = ({
  plcsList,
  selectedPlc,
  setSelectedPlc,
  currentData,
  maintenanceData,
  historyData,
  onPlcAdded
}) => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-gray-200">
        <div>
          <h1 className="text-base font-bold text-gray-900">
            Engineer Maintenance Decision Support & Cost-Energy Optimization
          </h1>
          <p className="text-xs text-gray-500">
            RUL-driven intelligent maintenance policy, financial cost-benefit optimization & 3-phase energy monitoring
          </p>
        </div>
      </div>

      {/* NEW SECTION: Maintenance Cost Optimization & Energy-Aware Predictive Maintenance */}
      <CostOptimizationSection
        selectedPlc={selectedPlc}
        setSelectedPlc={setSelectedPlc}
        plcsList={plcsList}
        currentData={currentData}
        onPlcAdded={onPlcAdded}
      />

      {/* PRESERVED EXISTING SECTION: RUL Trends & Machine Health Telemetry Extrapolation */}
      <div className="pt-4 border-t border-gray-200">
        <div className="mb-3">
          <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
            RUL Degradation Trajectories & Physical Telemetry Trends
          </h2>
          <p className="text-xs text-gray-500">
            Monitored parameter degradation history and 20-step trend extrapolations for {selectedPlc}
          </p>
        </div>
        <MaintenanceDashboard maintenanceData={maintenanceData} historyData={historyData} />
      </div>
    </div>
  );
};

export default Maintenance;
