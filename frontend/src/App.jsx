import React, { useState, useEffect, useRef } from 'react';
import TopBar from './components/TopBar';
import Sidebar from './components/Sidebar';
import CriticalAlertModal from './components/CriticalAlertModal';
import Dashboard from './pages/Dashboard';
import Analytics from './pages/Analytics';
import Maintenance from './pages/Maintenance';
import Evaluation from './pages/Evaluation';
import DriftMonitoring from './pages/DriftMonitoring';
import DigitalThread from './pages/DigitalThread';
import {
  getStatus,
  getPlcsData,
  getCurrentData,
  getHistoryData,
  getModelMetrics,
  getMlMetrics,
  getFeaturesSummary,
  getRecentLogs,
  getMaintenanceData,
  postControlAction,
} from './services/api';
import { isValidPlcId, formatPlcDisplay, getPlcNumber, isPlcMatch } from './utils/plcValidation';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedPlc, setSelectedPlc] = useState('PLC_01');
  const [selectedTag, setSelectedTag] = useState('Motor_Temp');
  const [tagsList, setTagsList] = useState([]);
  const [backendStatus, setBackendStatus] = useState(true);
  const [statusData, setStatusData] = useState(null);
  const [plcsList, setPlcsList] = useState([]);
  const [currentData, setCurrentData] = useState(null);
  const [historyData, setHistoryData] = useState(null);
  const [modelData, setModelData] = useState(null);
  const [maintenanceData, setMaintenanceData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [speed, setSpeed] = useState(1.0);
  const [autoPlay, setAutoPlay] = useState(false);

  const consecutiveFailuresRef = useRef(0);

  const fetchAllData = async (plcId = selectedPlc, tag = selectedTag) => {
    try {
      const validPlc = formatPlcDisplay(plcId);
      const [pRes, cRes, hRes, lRes, mRes] = await Promise.all([
        getPlcsData().catch(() => null),
        getCurrentData(validPlc).catch(() => null),
        getHistoryData(validPlc, tag).catch(() => null),
        getRecentLogs(validPlc).catch(() => null),
        getMaintenanceData(validPlc).catch(() => null),
      ]);

      if (pRes && Array.isArray(pRes.plcs)) {
        const cleanList = pRes.plcs
          .filter((p) => p && isValidPlcId(p.plc_id))
          .map((p) => ({
            ...p,
            plc_id: formatPlcDisplay(p.plc_id),
            plc_id_num: getPlcNumber(p.plc_id),
          }))
          .sort((a, b) => (a.plc_id_num || 0) - (b.plc_id_num || 0));
        setPlcsList(cleanList);
      }
      if (cRes) setCurrentData(cRes);
      if (hRes) setHistoryData(hRes);
      if (lRes && lRes.logs) setLogs(lRes.logs);
      if (mRes) setMaintenanceData(mRes);

      setBackendStatus(true);
      consecutiveFailuresRef.current = 0;
    } catch (err) {
      consecutiveFailuresRef.current += 1;
      if (consecutiveFailuresRef.current >= 3) {
        setBackendStatus(false);
      }
    }
  };

  // Initial fetch
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const sData = await getStatus();
        setStatusData(sData);
        setBackendStatus(true);
        consecutiveFailuresRef.current = 0;
      } catch (err) {
        setBackendStatus(false);
      }

      try {
        const [mData, mlData, fData] = await Promise.all([
          getModelMetrics().catch(() => null),
          getMlMetrics().catch(() => null),
          getFeaturesSummary().catch(() => null),
        ]);
        setModelData({
          ...(mData || {}),
          mlClassification: mlData,
          featuresSummary: fData,
        });
      } catch (err) {
        console.error('Failed to load model metrics:', err);
      }
    };

    fetchInitialData();
  }, []);

  const getWsUrl = () => {
    if (typeof window !== 'undefined') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      if (window.location.port === '5173' || window.location.port === '3000') {
        return 'ws://127.0.0.1:8000/ws/telemetry';
      }
      return `${proto}//${window.location.host}/ws/telemetry`;
    }
    return 'ws://127.0.0.1:8000/ws/telemetry';
  };

  // Real-time WebSocket connection for instant MQTT telemetry updates
  useEffect(() => {
    let ws = null;
    let reconnectTimer = null;
    let isMounted = true;

    const connectWebSocket = () => {
      try {
        const wsUrl = getWsUrl();
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (!isMounted) return;
          console.log('Connected to real-time telemetry WebSocket');
          setBackendStatus(true);
          consecutiveFailuresRef.current = 0;
          try {
            ws.send(JSON.stringify({ action: 'select_plc', plc_id: selectedPlc }));
          } catch (_) {}
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'telemetry') {
              const record = msg.data;
              const recPlcId = record?.plc_id || msg.plc_id;

              // Requirement 3 & 8: Never create a PLC card when plc_id is null, undefined, empty, NaN, or missing
              if (!isValidPlcId(recPlcId)) {
                return;
              }

              const normPlcId = formatPlcDisplay(recPlcId);
              const normPlcNum = getPlcNumber(normPlcId);

              // Update PLCs summary list dynamically without hardcoding
              setPlcsList((prev) => {
                const list = Array.isArray(prev) ? prev.filter((p) => p && isValidPlcId(p.plc_id)) : [];
                const idx = list.findIndex((p) => isPlcMatch(p.plc_id, normPlcId));
                const updatedItem = {
                  plc_id: normPlcId,
                  plc_id_num: normPlcNum,
                  temperature: record.temperature,
                  vibration: record.vibration,
                  motor_current: record.motor_current,
                  pressure: record.pressure,
                  noise: record.noise,
                  predicted_rul_days: record.predicted_rul_days,
                  machine_status: record.machine_status,
                  anomaly_status: record.anomaly_status,
                };
                if (idx >= 0) {
                  list[idx] = { ...list[idx], ...updatedItem };
                } else {
                  list.push(updatedItem);
                }
                return list.sort((a, b) => (a.plc_id_num || 0) - (b.plc_id_num || 0));
              });

              // Strict Isolation: Only update active dashboard views if message matches selected PLC
              if (isPlcMatch(normPlcId, selectedPlc)) {
                setCurrentData((prev) => ({
                  ...(prev || {}),
                  ...record,
                  plc_id: normPlcId,
                }));

                setHistoryData((prev) => {
                  const existingHistory = prev && Array.isArray(prev.history) ? [...prev.history] : [];
                  existingHistory.push(record);
                  if (existingHistory.length > 100) existingHistory.shift();

                  const temps = existingHistory.map((r) => r.Motor_Temp ?? r.temperature);
                  const vibs = existingHistory.map((r) => r.Vibration_X ?? r.vibration);
                  const currs = existingHistory.map((r) => r.Motor_Current ?? r.motor_current);
                  const presses = existingHistory.map((r) => r.Pressure_Inlet ?? r.pressure);
                  const noises = existingHistory.map((r) => r.Noise ?? r.noise);
                  const timestamps = existingHistory.map((r) => r.timestamp);

                  // Extract values for the active selected tag
                  const tagValueMap = {
                    Motor_Temp: temps,
                    Temperature: temps,
                    Vibration_X: vibs,
                    Vibration: vibs,
                    Motor_Current: currs,
                    Pressure_Inlet: presses,
                    Pressure: presses,
                    Noise: noises
                  };
                  const activeTagVals = tagValueMap[selectedTag] || temps;

                  return {
                    ...(prev || {}),
                    plc_id: selectedPlc,
                    selected_tag: selectedTag,
                    actual: activeTagVals,
                    history: existingHistory,
                    timestamps,
                    temperature_trend: {
                      actual: temps,
                      predicted_future: prev?.temperature_trend?.predicted_future || [],
                      timestamps,
                    },
                    vibration_trend: {
                      actual: vibs,
                      predicted_future: prev?.vibration_trend?.predicted_future || [],
                      timestamps,
                    },
                    motor_current_trend: {
                      actual: currs,
                      predicted_future: prev?.motor_current_trend?.predicted_future || [],
                      timestamps,
                    },
                    pressure_trend: {
                      actual: presses,
                      predicted_future: prev?.pressure_trend?.predicted_future || [],
                      timestamps,
                    },
                    noise_trend: {
                      actual: noises,
                      predicted_future: prev?.noise_trend?.predicted_future || [],
                      timestamps,
                    },
                  };
                });
              }
            } else if (msg.type === 'init') {
              if (isPlcMatch(msg.plc_id, selectedPlc) && msg.data) {
                setCurrentData(msg.data);
                if (msg.history && Array.isArray(msg.history) && msg.history.length > 0) {
                  const temps = msg.history.map((r) => r.Motor_Temp ?? r.temperature);
                  const vibs = msg.history.map((r) => r.Vibration_X ?? r.vibration);
                  const currs = msg.history.map((r) => r.Motor_Current ?? r.motor_current);
                  const presses = msg.history.map((r) => r.Pressure_Inlet ?? r.pressure);
                  const noises = msg.history.map((r) => r.Noise ?? r.noise);
                  const timestamps = msg.history.map((r) => r.timestamp);
                  setHistoryData((prev) => ({
                    ...(prev || {}),
                    plc_id: msg.plc_id,
                    history: msg.history,
                    timestamps,
                    temperature_trend: { actual: temps, predicted_future: prev?.temperature_trend?.predicted_future || [], timestamps },
                    vibration_trend: { actual: vibs, predicted_future: prev?.vibration_trend?.predicted_future || [], timestamps },
                    motor_current_trend: { actual: currs, predicted_future: prev?.motor_current_trend?.predicted_future || [], timestamps },
                    pressure_trend: { actual: presses, predicted_future: prev?.pressure_trend?.predicted_future || [], timestamps },
                    noise_trend: { actual: noises, predicted_future: prev?.noise_trend?.predicted_future || [], timestamps },
                  }));
                }
              }
            }
          } catch (e) {
            console.error('Error parsing WebSocket telemetry message:', e);
          }
        };

        ws.onclose = () => {
          if (!isMounted) return;
          reconnectTimer = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };
      } catch (err) {
        if (!isMounted) return;
        reconnectTimer = setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    return () => {
      isMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [selectedPlc]);

  // Polling loop (secondary fallback)
  useEffect(() => {
    let isSubscribed = true;
    let timerId = null;

    const pollData = async () => {
      try {
        const [pRes, cRes, hRes, lRes, mRes] = await Promise.all([
          getPlcsData().catch(() => null),
          getCurrentData(selectedPlc).catch(() => null),
          getHistoryData(selectedPlc, selectedTag).catch(() => null),
          getRecentLogs(selectedPlc).catch(() => null),
          getMaintenanceData(selectedPlc).catch(() => null),
        ]);

        if (!isSubscribed) return;

        if (pRes || cRes) {
          setBackendStatus(true);
          consecutiveFailuresRef.current = 0;
        } else {
          consecutiveFailuresRef.current += 1;
          if (consecutiveFailuresRef.current >= 3) {
            setBackendStatus(false);
          }
        }

        if (pRes && Array.isArray(pRes.plcs)) {
          const cleanList = pRes.plcs
            .filter((p) => p && isValidPlcId(p.plc_id))
            .map((p) => ({
              ...p,
              plc_id: formatPlcDisplay(p.plc_id),
              plc_id_num: getPlcNumber(p.plc_id),
            }))
            .sort((a, b) => (a.plc_id_num || 0) - (b.plc_id_num || 0));
          setPlcsList(cleanList);
        }
        if (cRes) setCurrentData(cRes);
        if (hRes) setHistoryData(hRes);
        if (lRes && lRes.logs) setLogs(lRes.logs);
        if (mRes) setMaintenanceData(mRes);

      } catch (err) {
        if (!isSubscribed) return;
        consecutiveFailuresRef.current += 1;
        if (consecutiveFailuresRef.current >= 3) {
          setBackendStatus(false);
        }
      } finally {
        if (isSubscribed) {
          timerId = setTimeout(pollData, 1500);
        }
      }
    };

    pollData();

    return () => {
      isSubscribed = false;
      if (timerId) clearTimeout(timerId);
    };
  }, [selectedPlc, selectedTag]);

  const handleControlAction = async (action, speedVal = 1.0) => {
    try {
      console.log(`Executing control action '${action}'...`);
      const res = await postControlAction(action, speedVal);
      if (action === 'set_speed') setSpeed(speedVal);
      if (action === 'start') setAutoPlay(true);
      if (action === 'pause') setAutoPlay(false);

      if (res && typeof res.auto_play === 'boolean') {
        setAutoPlay(res.auto_play);
      }

      // Immediately refresh all data state on start/next/reset
      if (action === 'start' || action === 'next' || action === 'reset') {
        await fetchAllData(selectedPlc, selectedTag);
      }
    } catch (err) {
      console.error(`Failed to execute control action '${action}':`, err);
    }
  };

  const isCritical = currentData?.machine_status === 'Critical';

  return (
    <div className="flex h-screen bg-slate-50 font-sans text-gray-800 overflow-hidden">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentData={currentData}
        backendStatus={backendStatus}
        onControlAction={handleControlAction}
        speed={speed}
        setSpeed={setSpeed}
        autoPlay={autoPlay}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar
          backendStatus={backendStatus}
          statusData={statusData}
          activeTab={activeTab}
          speed={speed}
          autoPlay={autoPlay}
          onControl={handleControlAction}
        />

        <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          {activeTab === 'dashboard' && (
            <Dashboard
              plcsList={plcsList}
              selectedPlc={selectedPlc}
              setSelectedPlc={setSelectedPlc}
              selectedTag={selectedTag}
              setSelectedTag={setSelectedTag}
              currentData={currentData}
              historyData={historyData}
              logs={logs}
              setActiveTab={setActiveTab}
              onPlcAdded={async (newId) => {
                await fetchAllData(newId || selectedPlc, selectedTag);
              }}
            />
          )}

          {activeTab === 'analytics' && (
            <Analytics currentData={currentData} historyData={historyData} logs={logs} />
          )}

          {activeTab === 'maintenance' && (
            <Maintenance
              plcsList={plcsList}
              selectedPlc={selectedPlc}
              setSelectedPlc={setSelectedPlc}
              currentData={currentData}
              maintenanceData={maintenanceData}
              historyData={historyData}
              onPlcAdded={async (newId) => {
                await fetchAllData(newId || selectedPlc, selectedTag);
              }}
            />
          )}

          {activeTab === 'evaluation' && <Evaluation modelData={modelData} />}

          {activeTab === 'drift' && (
            <DriftMonitoring
              selectedPlc={selectedPlc}
              plcsList={plcsList}
              setSelectedPlc={setSelectedPlc}
            />
          )}

          {activeTab === 'digital_thread' && (
            <DigitalThread
              selectedPlc={selectedPlc}
              plcsList={plcsList}
            />
          )}
        </main>
      </div>

      <CriticalAlertModal isVisible={isCritical} currentData={currentData} />
    </div>
  );
}

export default App;
