import React, { useRef } from 'react';
import Plot from 'react-plotly.js';
import { calculateAdaptiveYRange } from './LiveChart';

const SingleTrendPlot = ({
  title,
  yLabel,
  trendData,
  actualColor = '#2563EB',
  isFullWidth = false,
  degradationDay = null,
  minClamp = 0,
  maxClamp = 100,
  minSpan = 1,
  metricType = 'general',
  dtick = null,
  minorDtick = null
}) => {
  const actual = trendData?.actual || [];
  const predicted = trendData?.predicted_future || [];
  const rangeRef = useRef(null);

  const xHist = actual.map((_, i) => i + 1);
  const latestDay = xHist.length > 0 ? xHist[xHist.length - 1] : 1;
  const xFuture = actual.length > 0 ? predicted.map((_, i) => latestDay + i) : [];

  const visibleMin = Math.max(1, latestDay - 100);
  const visibleMax = latestDay + 20;

  const adaptiveRange = metricType === 'health'
    ? [0, 100]
    : calculateAdaptiveYRange(actual, minClamp, maxClamp, minSpan, metricType, rangeRef);

  const shapes = degradationDay ? [
    {
      type: 'line',
      x0: degradationDay,
      x1: degradationDay,
      y0: 0,
      y1: 1,
      yref: 'paper',
      line: { color: '#EF4444', width: 1.5, dash: 'dash' },
    },
  ] : [];

  const annotations = degradationDay ? [
    {
      x: degradationDay,
      y: 1.05,
      yref: 'paper',
      text: `Degradation (Day ${degradationDay})`,
      showarrow: false,
      font: { size: 9, color: '#DC2626' },
      bgcolor: '#FEE2E2',
      bordercolor: '#FCA5A5',
      borderwidth: 1,
      borderpad: 2,
    },
  ] : [];

  const yAxisConfig = {
    title: { text: yLabel, font: { size: 10, color: '#6B7280' } },
    gridcolor: '#E5E7EB',
    zeroline: false,
    range: adaptiveRange,
    autorange: false,
    ...(dtick ? { dtick: dtick } : {}),
    minor: { showgrid: true, gridcolor: '#F3F4F6', ...(minorDtick ? { dtick: minorDtick } : {}) },
  };

  return (
    <div className={`industrial-card p-4 ${isFullWidth ? 'w-full' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">{title}</h3>
        {actual.length > 0 && (
          <span className="text-[11px] text-gray-500 font-mono">
            Latest: {actual[actual.length - 1]} {yLabel}
          </span>
        )}
      </div>

      <div className="w-full h-64">
        <Plot
          data={[
            {
              x: xHist,
              y: actual,
              type: 'scatter',
              mode: 'lines+markers',
              name: 'Actual',
              line: { color: actualColor, width: 3, shape: 'spline', smoothing: 0.45 },
              marker: { size: 4, color: actualColor },
              hovertemplate: `%{y:.2f} ${yLabel}<extra></extra>`,
            },
            {
              x: xFuture,
              y: predicted,
              type: 'scatter',
              mode: 'lines',
              name: 'Predicted Future',
              line: { color: '#F59E0B', width: 2.5, dash: 'dash', shape: 'spline', smoothing: 0.45 },
              hovertemplate: `%{y:.2f} ${yLabel}<extra></extra>`,
            },
          ]}
          layout={{
            autosize: true,
            height: 240,
            uirevision: title,
            transition: { duration: 300, easing: 'cubic-in-out' },
            margin: { l: 45, r: 15, t: 25, b: 35 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: '#FAFAFA',
            xaxis: {
              title: { text: 'Day', font: { size: 10, color: '#6B7280' } },
              gridcolor: '#E5E7EB',
              zeroline: false,
              range: [visibleMin, visibleMax],
              autorange: false,
            },
            yaxis: yAxisConfig,
            shapes: shapes,
            annotations: annotations,
            legend: {
              orientation: 'h',
              y: 1.2,
              x: 1,
              xanchor: 'right',
              font: { size: 10, color: '#4B5563' },
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


const AnalyticsCharts = ({ historyData }) => {
  const healthTrend = historyData?.machine_health_trend?.actual || [];
  let degradationDay = null;
  for (let i = 0; i < healthTrend.length; i++) {
    if (healthTrend[i] < 98.0) {
      degradationDay = i + 1;
      break;
    }
  }

  return (
    <div className="space-y-4">
      {/* Multi-Sensor Grid: Temperature, Vibration, Motor Current, Pressure, Noise, Machine Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SingleTrendPlot
          title="Temperature Trend"
          yLabel="°C"
          trendData={historyData?.temperature_trend}
          actualColor="#2563EB"
          degradationDay={degradationDay}
          minClamp={55}
          maxClamp={85}
          minSpan={6}
          metricType="temperature"
          dtick={2}
          minorDtick={0.5}
        />
        <SingleTrendPlot
          title="Vibration RMS Trend"
          yLabel="mm/s"
          trendData={historyData?.vibration_trend}
          actualColor="#2563EB"
          degradationDay={degradationDay}
          minClamp={0}
          maxClamp={6}
          minSpan={1}
          metricType="vibration"
          dtick={0.5}
          minorDtick={0.1}
        />
        <SingleTrendPlot
          title="Motor Current Trend"
          yLabel="A"
          trendData={historyData?.motor_current_trend}
          actualColor="#2563EB"
          degradationDay={degradationDay}
          minClamp={5}
          maxClamp={25}
          minSpan={3}
          metricType="current"
          dtick={2}
          minorDtick={0.5}
        />
        <SingleTrendPlot
          title="Pressure Trend"
          yLabel="bar"
          trendData={historyData?.pressure_trend}
          actualColor="#2563EB"
          degradationDay={degradationDay}
          minClamp={1}
          maxClamp={12}
          minSpan={2}
          metricType="pressure"
          dtick={1}
          minorDtick={0.2}
        />
        <SingleTrendPlot
          title="Acoustic Noise Trend"
          yLabel="dB"
          trendData={historyData?.noise_trend}
          actualColor="#2563EB"
          degradationDay={degradationDay}
          minClamp={30}
          maxClamp={90}
          minSpan={10}
          metricType="noise"
          dtick={5}
          minorDtick={1}
        />
        <SingleTrendPlot
          title="Machine Health Trend"
          yLabel="%"
          trendData={historyData?.machine_health_trend}
          actualColor="#22C55E"
          degradationDay={degradationDay}
          minClamp={0}
          maxClamp={100}
          minSpan={100}
          metricType="health"
        />
      </div>


      {/* Full Width RUL Trend */}
      <SingleTrendPlot
        title="Remaining Useful Life (RUL) Trend"
        yLabel="Days"
        trendData={historyData?.rul_trend}
        actualColor="#2563EB"
        isFullWidth={true}
        degradationDay={degradationDay}
        minClamp={0}
        maxClamp={250}
        minSpan={80}
        metricType="rul"
      />
    </div>
  );
};


export default AnalyticsCharts;

