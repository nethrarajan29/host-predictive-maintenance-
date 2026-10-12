import React, { useEffect, useState, useRef } from 'react';
import {
  AlertOctagon,
  AlertTriangle,
  X,
  Wrench,
  RotateCcw,
  Volume2,
  VolumeX,
  Flame,
  Activity,
  Zap,
  Gauge,
  Volume1,
  CheckCircle,
} from 'lucide-react';

const CriticalAlertModal = ({
  currentData,
  maintenanceData,
  onNavigateToMaintenance,
  onResetSimulation,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isAcknowledged, setIsAcknowledged] = useState(false);

  const prevStageRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioIntervalRef = useRef(null);

  const isCritical =
    currentData?.machine_status === 'Critical' ||
    currentData?.machine_condition === 'Critical' ||
    currentData?.machine_status === 'Failure' ||
    (currentData?.machine_health !== undefined && currentData?.machine_health <= 15.0);

  // Trigger alert popup whenever entering Critical state
  useEffect(() => {
    if (isCritical) {
      if (prevStageRef.current !== 'Critical' && prevStageRef.current !== 'Failure') {
        setIsOpen(true);
        setIsAcknowledged(false);
      }
    } else {
      // Machine has returned to normal/reset
      setIsOpen(false);
      setIsAcknowledged(false);
    }
    prevStageRef.current = currentData?.machine_status;
  }, [isCritical, currentData?.machine_status]);

  // Web Audio synthetic alarm pulse
  const playAlarmTone = () => {
    if (isMuted) return;
    try {
      if (!audioContextRef.current) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
          audioContextRef.current = new AudioContext();
        }
      }
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume();
      }
      if (audioContextRef.current) {
        const ctx = audioContextRef.current;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, ctx.currentTime); // A5
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.25); // Drop to A4

        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.28);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      }
    } catch (e) {
      // Audio playback blocked or unavailable
    }
  };

  useEffect(() => {
    if (isOpen && isCritical && !isMuted && !isAcknowledged) {
      playAlarmTone();
      audioIntervalRef.current = setInterval(playAlarmTone, 2000);
    } else {
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
        audioIntervalRef.current = null;
      }
    }
    return () => {
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
      }
    };
  }, [isOpen, isCritical, isMuted, isAcknowledged]);

  if (!isCritical) return null;

  const health = currentData?.machine_health ?? 12.0;
  const rul = currentData?.predicted_rul_days ?? 10;
  const failureRisk = currentData?.failure_risk_pct ?? 88.5;
  const anomaly = currentData?.anomaly_status || 'Anomaly Detected';
  const recAction =
    maintenanceData?.recommended_action ||
    'Immediate mechanical overhaul & bearing replacement required. Critical thermal and vibration thresholds breached.';

  return (
    <>
      {/* Floating persistent sticky alert banner if modal dismissed but still Critical */}
      {!isOpen && isCritical && (
        <div className="fixed top-14 left-0 right-0 z-40 bg-red-600 text-white px-4 py-2.5 shadow-lg flex items-center justify-between animate-pulse">
          <div className="flex items-center space-x-3 max-w-[1600px] mx-auto w-full">
            <AlertOctagon className="w-5 h-5 text-white animate-bounce shrink-0" />
            <span className="text-xs sm:text-sm font-bold uppercase tracking-wide">
              CRITICAL MACHINE ALERT: Health at {health}% | Predicted RUL: {rul} Days | Failure Risk: {failureRisk.toFixed(1)}%
            </span>
            <div className="ml-auto flex items-center space-x-3">
              <button
                onClick={() => setIsOpen(true)}
                className="bg-white text-red-700 px-3 py-1 rounded text-xs font-bold hover:bg-red-50 shadow-sm transition"
              >
                View Critical Alert
              </button>
              <button
                onClick={onNavigateToMaintenance}
                className="bg-red-800 text-white px-3 py-1 rounded text-xs font-semibold hover:bg-red-900 transition flex items-center gap-1"
              >
                <Wrench className="w-3.5 h-3.5" /> Maintenance Plan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Backdrop & Pop-up Dialog */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border-2 border-red-500 overflow-hidden transform animate-in zoom-in-95 duration-200">
            {/* Header with flashing red alert strip */}
            <div className="bg-gradient-to-r from-red-600 via-red-700 to-rose-700 p-5 text-white flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="p-2.5 bg-white/20 rounded-xl backdrop-blur-xs animate-pulse">
                  <AlertOctagon className="w-7 h-7 text-white" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold uppercase tracking-widest bg-red-900/60 px-2.5 py-0.5 rounded-full border border-white/20">
                      Emergency Level 4
                    </span>
                    <span className="text-xs text-red-100 font-mono">SCADA Ref: MCH-802X</span>
                  </div>
                  <h2 className="text-lg font-black tracking-tight mt-0.5">
                    CRITICAL MACHINE STAGE REACHED
                  </h2>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setIsMuted(!isMuted)}
                  title={isMuted ? 'Unmute alert tone' : 'Mute alert tone'}
                  className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition"
                >
                  {isMuted ? <VolumeX className="w-5 h-5 text-red-200" /> : <Volume2 className="w-5 h-5" />}
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5 bg-[#FBFBFC]">
              {/* Summary Warning Callout */}
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start space-x-3">
                <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                <div className="text-xs text-red-900 space-y-1">
                  <p className="font-bold text-sm text-red-800">
                    Immediate Mechanical Intervention Required
                  </p>
                  <p className="leading-relaxed">
                    The predictive maintenance diagnostics have detected imminent physical failure risk. Sensor telemetry has exceeded safe baseline thresholds and accumulated physical wear is collapsing machine health.
                  </p>
                </div>
              </div>

              {/* Critical Telemetry KPI Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs">
                  <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                    Health Index
                  </span>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-2xl font-black text-red-600 font-mono">
                      {health.toFixed(1)}%
                    </span>
                  </div>
                  <span className="text-[10px] text-red-600 font-medium font-mono">
                    Critical ($\le 15\%$)
                  </span>
                </div>

                <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs">
                  <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                    Remaining Useful Life
                  </span>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-2xl font-black text-blue-700 font-mono">
                      {rul}
                    </span>
                    <span className="text-xs text-gray-500 font-sans">Days</span>
                  </div>
                  <span className="text-[10px] text-amber-600 font-medium">
                    Impending Shutdown
                  </span>
                </div>

                <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs">
                  <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                    Failure Risk
                  </span>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-2xl font-black text-red-600 font-mono">
                      {failureRisk.toFixed(1)}%
                    </span>
                  </div>
                  <span className="text-[10px] text-red-600 font-medium">
                    Extreme Probability
                  </span>
                </div>

                <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-2xs">
                  <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                    Isolation Forest
                  </span>
                  <div className="mt-1">
                    <span className="inline-block text-xs font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-300">
                      {anomaly}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-500">
                    Outlier Detected
                  </span>
                </div>
              </div>

              {/* Live Excursion Sensor Readings */}
              <div className="bg-white p-4 rounded-xl border border-gray-200 space-y-2">
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider">
                  Live Sensor Excursion Snapshot
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                  <div className="bg-gray-50 p-2 rounded border border-gray-100 flex items-center space-x-2">
                    <Flame className="w-4 h-4 text-orange-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-gray-400 block">Temperature</span>
                      <span className="font-mono font-bold text-gray-800">
                        {currentData?.temperature ?? '--'} °C
                      </span>
                    </div>
                  </div>

                  <div className="bg-gray-50 p-2 rounded border border-gray-100 flex items-center space-x-2">
                    <Activity className="w-4 h-4 text-red-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-gray-400 block">Vibration</span>
                      <span className="font-mono font-bold text-gray-800">
                        {currentData?.vibration ?? '--'} mm/s
                      </span>
                    </div>
                  </div>

                  <div className="bg-gray-50 p-2 rounded border border-gray-100 flex items-center space-x-2">
                    <Zap className="w-4 h-4 text-amber-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-gray-400 block">Current</span>
                      <span className="font-mono font-bold text-gray-800">
                        {currentData?.motor_current ?? '--'} A
                      </span>
                    </div>
                  </div>

                  <div className="bg-gray-50 p-2 rounded border border-gray-100 flex items-center space-x-2">
                    <Gauge className="w-4 h-4 text-blue-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-gray-400 block">Pressure</span>
                      <span className="font-mono font-bold text-gray-800">
                        {currentData?.pressure ?? '--'} bar
                      </span>
                    </div>
                  </div>

                  <div className="bg-gray-50 p-2 rounded border border-gray-100 flex items-center space-x-2">
                    <Volume1 className="w-4 h-4 text-purple-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-gray-400 block">Noise</span>
                      <span className="font-mono font-bold text-gray-800">
                        {currentData?.noise ?? '--'} dB
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recommended Action Box */}
              <div className="bg-amber-50/80 border border-amber-200 rounded-xl p-3.5 flex items-start space-x-3">
                <Wrench className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-bold text-amber-900 uppercase tracking-wider block">
                    Prescribed Maintenance Action
                  </span>
                  <p className="text-xs text-amber-800 mt-0.5 leading-relaxed font-medium">
                    {recAction}
                  </p>
                </div>
              </div>
            </div>

            {/* Modal Footer / Action Buttons */}
            <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center space-x-2 w-full sm:w-auto">
                <button
                  onClick={() => {
                    setIsAcknowledged(true);
                    setIsOpen(false);
                  }}
                  className="px-4 py-2 bg-white border border-gray-300 text-gray-700 hover:bg-gray-100 text-xs font-bold rounded-xl transition shadow-2xs w-full sm:w-auto"
                >
                  Acknowledge & Close
                </button>
                <button
                  onClick={() => {
                    if (onResetSimulation) {
                      onResetSimulation();
                      setIsOpen(false);
                    }
                  }}
                  className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 text-xs font-bold rounded-xl transition flex items-center justify-center gap-1.5 w-full sm:w-auto"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Reset Simulation
                </button>
              </div>

              <button
                onClick={() => {
                  if (onNavigateToMaintenance) {
                    onNavigateToMaintenance();
                  }
                  setIsOpen(false);
                }}
                className="w-full sm:w-auto px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-xl transition shadow-sm hover:shadow-md flex items-center justify-center gap-2"
              >
                <Wrench className="w-4 h-4" /> Open Maintenance Plan
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default CriticalAlertModal;
