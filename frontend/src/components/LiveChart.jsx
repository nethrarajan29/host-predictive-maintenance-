import React, { useState, useRef } from 'react';
import Plot from 'react-plotly.js';
import { isValidPlcId, formatPlcDisplay } from '../utils/plcValidation';

export function calculateAdaptiveYRange(dataArray, minClamp, maxClamp, minSpan, type, rangeRef) {
  if (!dataArray || dataArray.length === 0) {
    return [minClamp, maxClamp];
  }

  const rawMin = Math.min(...dataArray);
  const rawMax = Math.max(...dataArray);

  let targetMin, targetMax;

  if (type === 'temperature') {
    targetMin = Math.floor(rawMin - 1.0);
    targetMax = Math.ceil(rawMax + 1.0);
  } else if (type === 'vibration') {
    targetMin = rawMin - 0.15;
    targetMax = rawMax + 0.15;
  } else if (type === 'current') {
    targetMin = rawMin - 0.5;
    targetMax = rawMax + 0.5;
  } else if (type === 'pressure') {
    targetMin = rawMin - 0.5;
    targetMax = rawMax + 0.5;
  } else if (type === 'noise') {
    targetMin = Math.floor(rawMin - 2.0);
    targetMax = Math.ceil(rawMax + 2.0);
  } else if (type === 'rul') {
    targetMin = rawMin - 40.0;
    targetMax = rawMax + 40.0;
  } else {
    targetMin = rawMin - 1.0;
    targetMax = rawMax + 1.0;
  }

  if (targetMax - targetMin < minSpan) {
    const mid = (targetMax + targetMin) / 2;
    targetMin = mid - minSpan / 2;
    targetMax = mid + minSpan / 2;
  }

  targetMin = Math.max(minClamp, targetMin);
  targetMax = Math.min(maxClamp, targetMax);

  if (targetMax - targetMin < minSpan) {
    if (targetMin === minClamp) {
      targetMax = Math.min(maxClamp, targetMin + minSpan);
    } else if (targetMax === maxClamp) {
      targetMin = Math.max(minClamp, targetMax - minSpan);
    }
  }

  // 15% Hysteresis check
  if (rangeRef && rangeRef.current) {
    const [cMin, cMax] = rangeRef.current;
    const cSpan = cMax - cMin;
    const thresh = 0.15 * cSpan;

    if (rawMin > cMin + thresh && rawMax < cMax - thresh) {
      return rangeRef.current;
    }
  }

  const res = [Math.round(targetMin * 100) / 100, Math.round(targetMax * 100) / 100];
  if (rangeRef) {
    rangeRef.current = res;
  }
  return res;
}

const LiveChart = ({
  historyData,
  selectedPlc = 'PLC_01',
  setSelectedPlc,
  selectedTag = 'Motor_Temp',
  setSelectedTag,
  plcsList = [],
}) => {
  const [isDeviationView, setIsDeviationView] = useState(false);
  const [timeRange, setTimeRange] = useState(50); // 15 | 30 | 50 | 100
  const currentRangeRef = useRef(null);

  const displayPlc = formatPlcDisplay(selectedPlc);
  const currentTag = selectedTag || 'Motor_Temp';

  const tagOptions = [
    { value: 'Motor_Temp', label: 'Motor_Temp (Temperature °C)' },
    { value: 'Vibration_X', label: 'Vibration_X (Vibration RMS mm/s)' },
    { value: 'Vibration', label: 'Vibration (Vibration RMS mm/s)' },
    { value: 'Motor_Current', label: 'Motor_Current (Motor Current A)' },
    { value: 'Pressure_Inlet', label: 'Pressure_Inlet (Inlet Pressure bar)' },
    { value: 'Noise', label: 'Noise (Acoustic Noise dB)' },
  ];

  const metricConfigs = {
    Motor_Temp: {
      label: 'Motor Temperature (°C)',
      key: 'temperature_trend',
      fieldName: 'Motor_Temp',
      altFieldName: 'temperature',
      color: '#2563EB',
      unit: '°C',
      minClamp: 20,
      maxClamp: 120,
      minSpan: 6,
      type: 'temperature',
      dtick: 5,
      minorDtick: 1,
    },
    Temperature: {
      label: 'Motor Temperature (°C)',
      key: 'temperature_trend',
      fieldName: 'Motor_Temp',
      altFieldName: 'temperature',
      color: '#2563EB',
      unit: '°C',
      minClamp: 20,
      maxClamp: 120,
      minSpan: 6,
      type: 'temperature',
      dtick: 5,
      minorDtick: 1,
    },
    Vibration_X: {
      label: 'Vibration RMS (mm/s)',
      key: 'vibration_trend',
      fieldName: 'Vibration_X',
      altFieldName: 'vibration',
      color: '#7C3AED',
      unit: 'mm/s',
      minClamp: 0,
      maxClamp: 8,
      minSpan: 0.5,
      type: 'vibration',
      dtick: 0.5,
      minorDtick: 0.1,
    },
    Vibration: {
      label: 'Vibration RMS (mm/s)',
      key: 'vibration_trend',
      fieldName: 'Vibration_X',
      altFieldName: 'vibration',
      color: '#7C3AED',
      unit: 'mm/s',
      minClamp: 0,
      maxClamp: 8,
      minSpan: 0.5,
      type: 'vibration',
      dtick: 0.5,
      minorDtick: 0.1,
    },
    Motor_Current: {
      label: 'Motor Current (A)',
      key: 'motor_current_trend',
      fieldName: 'Motor_Current',
      altFieldName: 'motor_current',
      color: '#059669',
      unit: 'A',
      minClamp: 0,
      maxClamp: 30,
      minSpan: 2,
      type: 'current',
      dtick: 2,
      minorDtick: 0.5,
    },
    Pressure_Inlet: {
      label: 'Inlet Pressure (bar)',
      key: 'pressure_trend',
      fieldName: 'Pressure_Inlet',
      altFieldName: 'pressure',
      color: '#D97706',
      unit: 'bar',
      minClamp: 0,
      maxClamp: 15,
      minSpan: 1.5,
      type: 'pressure',
      dtick: 2,
      minorDtick: 0.5,
    },
    Pressure: {
      label: 'Inlet Pressure (bar)',
      key: 'pressure_trend',
      fieldName: 'Pressure_Inlet',
      altFieldName: 'pressure',
      color: '#D97706',
      unit: 'bar',
      minClamp: 0,
      maxClamp: 15,
      minSpan: 1.5,
      type: 'pressure',
      dtick: 2,
      minorDtick: 0.5,
    },
    Noise: {
      label: 'Acoustic Noise (dB)',
      key: 'noise_trend',
      fieldName: 'Noise',
      altFieldName: 'noise',
      color: '#E11D48',
      unit: 'dB',
      minClamp: 20,
      maxClamp: 110,
      minSpan: 10,
      type: 'noise',
      dtick: 10,
      minorDtick: 2,
    },
  };

  const getMetricTrend = (hData, tag, cfg) => {
    if (!hData) return { actual: [], timestamps: [], predicted_future: [] };
    const records = Array.isArray(hData) ? hData : (hData.history || []);

    const formatTs = (ts, index, total) => {
      if (!ts) return `T-${total - index}`;
      const str = String(ts).trim();
      const parts = str.split(' ');
      return parts.length > 1 ? parts[1] : parts[0];
    };

    // If historyData has top-level actual & predicted_future and selected_tag matches
    if (
      hData.selected_tag &&
      (hData.selected_tag === tag ||
       hData.selected_tag.toLowerCase() === tag.toLowerCase()) &&
      Array.isArray(hData.actual) &&
      hData.actual.length > 0
    ) {
      const rawTs = hData.timestamps || records.map((r) => r.timestamp || r.Timestamp || '');
      const timestamps = rawTs.map((t, idx) => formatTs(t, idx, rawTs.length));
      return {
        actual: hData.actual,
        timestamps,
        predicted_future: hData.predicted_future || [],
      };
    }

    // If historyData has a trend object matching cfg.key
    if (hData[cfg.key] && Array.isArray(hData[cfg.key].actual) && hData[cfg.key].actual.length > 0) {
      const actual = hData[cfg.key].actual;
      const rawTs = hData[cfg.key].timestamps || hData.timestamps || records.map((r) => r.timestamp || r.Timestamp || '');
      const timestamps = rawTs.map((t, idx) => formatTs(t, idx, rawTs.length));
      return {
        actual,
        timestamps,
        predicted_future: hData[cfg.key].predicted_future || [],
      };
    }

    // Fallback: extract from raw history records
    if (Array.isArray(records) && records.length > 0) {
      const actual = records.map((r) => {
        const val =
          r[cfg.fieldName] ??
          r[cfg.altFieldName] ??
          r[cfg.fieldName?.toLowerCase()] ??
          r[cfg.altFieldName?.toLowerCase()];
        return val !== undefined && val !== null ? Number(val) : 0;
      });
      const timestamps = records.map((r, idx) =>
        formatTs(r.timestamp || r.Timestamp, idx, records.length)
      );
      const lastVal = actual.length > 0 ? actual[actual.length - 1] : 0;
      const predicted_future = Array.from({ length: 5 }, () => lastVal);
      return { actual, timestamps, predicted_future };
    }

    return { actual: [], timestamps: [], predicted_future: [] };
  };

  const config = metricConfigs[currentTag] || metricConfigs.Motor_Temp;
  const trend = getMetricTrend(historyData, currentTag, config);

  const rawXHist = trend.timestamps && trend.timestamps.length === trend.actual.length
    ? trend.timestamps
    : trend.actual.map((_, i) => `T${i + 1}`);

  // Deduplicate timestamps so Plotly category axis never collapses identical ticks
  const labelCounts = {};
  const xHist = rawXHist.map((label) => {
    labelCounts[label] = (labelCounts[label] || 0) + 1;
    return labelCounts[label] > 1 ? `${label} (#${labelCounts[label]})` : label;
  });

  const xFuture = trend.actual.length > 0
    ? trend.predicted_future.map((_, i) => `+${i + 1}s`)
    : [];

  // Local deviation view calculation
  const baseline = trend.actual.length > 0 ? trend.actual[0] : 0;
  const yActual = isDeviationView ? trend.actual.map((v) => roundDec(v - baseline, 2)) : trend.actual;
  const yPredicted = isDeviationView ? trend.predicted_future.map((v) => roundDec(v - baseline, 2)) : trend.predicted_future;

  // Slice to selected time-range
  const slicedXHist = timeRange && timeRange < xHist.length ? xHist.slice(-timeRange) : xHist;
  const slicedYActual = timeRange && timeRange < yActual.length ? yActual.slice(-timeRange) : yActual;

  // Connect prediction line to the last actual historical data point
  const lastHistX = slicedXHist.length > 0 ? slicedXHist[slicedXHist.length - 1] : null;
  const lastHistY = slicedYActual.length > 0 ? slicedYActual[slicedYActual.length - 1] : null;
  const fullFutureX = lastHistX && xFuture.length > 0 ? [lastHistX, ...xFuture] : xFuture;
  const fullFutureY = lastHistY !== null && yPredicted.length > 0 ? [lastHistY, ...yPredicted] : yPredicted;

  const adaptiveYRange = calculateAdaptiveYRange(
    slicedYActual,
    isDeviationView ? -10 : config.minClamp,
    isDeviationView ? 30 : config.maxClamp,
    isDeviationView ? 4 : config.minSpan,
    config.type,
    currentRangeRef
  );

  const yAxisTitle = isDeviationView ? `Δ ${config.label} (vs Baseline ${baseline} ${config.unit})` : config.label;
  const hoverFmt = `%{y:.2f} ${config.unit}<extra></extra>`;

  function roundDec(val, dec = 2) {
    return Math.round(val * Math.pow(10, dec)) / Math.pow(10, dec);
  }

  // Dynamic discovered PLCs options strictly filtered to valid PLC IDs
  const rawPlcList = plcsList && plcsList.length > 0 ? plcsList : ['PLC_01', 'PLC_02', 'PLC_03', 'PLC_04', 'PLC_05'];
  const plcOptions = Array.from(
    new Set(
      rawPlcList
        .map((p) => (typeof p === 'string' ? p : p?.plc_id))
        .filter((id) => isValidPlcId(id))
        .map((id) => formatPlcDisplay(id))
    )
  );

  return (
    <div className="industrial-card p-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-gray-200 mb-2 gap-2">
        <div>
          <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <span>{displayPlc} — {currentTag} Live MQTT Stream</span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
              {config.unit}
            </span>
          </h2>
          <p className="text-xs text-gray-500">
            Real-time incoming telemetry (Solid line) &amp; ML predictive projection (Dashed line) for {displayPlc}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Purely Local Deviation View Toggle */}
          <div className="flex items-center space-x-1 bg-gray-100 p-0.5 rounded-lg border border-gray-200">
            <button
              onClick={() => {
                currentRangeRef.current = null;
                setIsDeviationView(false);
              }}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${!isDeviationView ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Absolute
            </button>
            <button
              onClick={() => {
                currentRangeRef.current = null;
                setIsDeviationView(true);
              }}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${isDeviationView ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Δ Deviation
            </button>
          </div>

          {/* Connected PLC Selector */}
          <div className="flex items-center space-x-1.5">
            <label className="text-xs font-semibold text-gray-600">PLC:</label>
            <select
              value={displayPlc}
              onChange={(e) => {
                currentRangeRef.current = null;
                if (setSelectedPlc) setSelectedPlc(e.target.value);
              }}
              className="bg-gray-50 border border-gray-300 text-gray-900 text-xs rounded-lg focus:ring-blue-500 focus:border-blue-500 block px-2.5 py-1.5 font-bold cursor-pointer"
            >
              {plcOptions.map((pVal) => (
                <option key={pVal} value={pVal}>
                  {pVal}
                </option>
              ))}
            </select>
          </div>

          {/* Connected Tag Selector */}
          <div className="flex items-center space-x-1.5">
            <label className="text-xs font-semibold text-gray-600">Tag:</label>
            <select
              value={currentTag}
              onChange={(e) => {
                currentRangeRef.current = null;
                if (setSelectedTag) setSelectedTag(e.target.value);
              }}
              className="bg-gray-50 border border-gray-300 text-gray-900 text-xs rounded-lg focus:ring-blue-500 focus:border-blue-500 block px-2.5 py-1.5 font-bold cursor-pointer"
            >
              {tagOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Time Range Selector */}
          <div className="flex items-center space-x-1.5">
            <label className="text-xs font-semibold text-gray-600">Range:</label>
            <select
              value={timeRange}
              onChange={(e) => {
                currentRangeRef.current = null;
                setTimeRange(Number(e.target.value));
              }}
              className="bg-gray-50 border border-gray-300 text-gray-900 text-xs rounded-lg focus:ring-blue-500 focus:border-blue-500 block px-2.5 py-1.5 font-bold cursor-pointer"
            >
              <option value={15}>Last 15 Samples</option>
              <option value={30}>Last 30 Samples</option>
              <option value={50}>Last 50 Samples</option>
              <option value={100}>All (100 Samples)</option>
            </select>
          </div>
        </div>
      </div>

      <div className="w-full h-[360px]">
        <Plot
          data={[
            {
              x: slicedXHist,
              y: slicedYActual,
              type: 'scatter',
              mode: 'lines+markers',
              name: isDeviationView
                ? `Δ Actual (${displayPlc} ${currentTag})`
                : `Actual Reading (${displayPlc} ${currentTag})`,
              line: { color: config.color, width: 2.5, shape: 'spline', smoothing: 0.45 },
              marker: { size: 5, color: config.color },
              hovertemplate: hoverFmt,
            },
            {
              x: fullFutureX,
              y: fullFutureY,
              type: 'scatter',
              mode: 'lines',
              name: isDeviationView
                ? `Δ Predicted (${displayPlc} ${currentTag})`
                : `Predicted Future (${displayPlc} ${currentTag})`,
              line: { color: '#F59E0B', width: 2.5, dash: 'dash', shape: 'spline', smoothing: 0.45 },
              marker: { size: 4, color: '#F59E0B' },
              hovertemplate: hoverFmt,
            },
          ]}
          layout={{
            autosize: true,
            height: 350,
            uirevision: `${displayPlc}_${currentTag}_${isDeviationView}`,
            transition: { duration: 250, easing: 'cubic-in-out' },
            margin: { l: 50, r: 20, t: 40, b: 50 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: '#FAFAFA',
            xaxis: {
              title: { text: 'Timestamp (HH:MM:SS)', font: { size: 11, color: '#6B7280' } },
              gridcolor: '#E5E7EB',
              zeroline: false,
              autorange: true,
              type: 'category',
            },
            yaxis: {
              title: { text: yAxisTitle, font: { size: 11, color: '#6B7280' } },
              gridcolor: '#E5E7EB',
              zeroline: isDeviationView,
              zerolinecolor: '#9CA3AF',
              zerolinewidth: 1.5,
              range: adaptiveYRange,
              dtick: config.dtick,
              minor: { showgrid: true, gridcolor: '#F3F4F6', dtick: config.minorDtick },
              autorange: false,
            },
            legend: {
              orientation: 'h',
              y: 1.15,
              x: 1,
              xanchor: 'right',
              font: { size: 11, color: '#374151' },
            },
          }}
          useResizeHandler={true}
          style={{ width: '100%', height: '100%' }}
          config={{ displayModeBar: false, responsive: true }}
        />
      </div>
    </div>
  );
};

export default LiveChart;
