import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { MetricPanel } from '../components/Common';
import type { AnalyticalReport, MetricsResponse, ModelInfoResponse } from '../types/api';
import './Overview.css';

function fmt(v: number | null | undefined, isPercent = true): string {
  if (v == null) return 'N/A';
  return isPercent ? `${(v * 100).toFixed(2)}%` : String(v);
}

function parseAnalyticalReport(content: string): AnalyticalReport {
  const validJson = content.replace(/(^|[:,\[\]\s])(-?Infinity|NaN)(?=[,\]\}\s])/g, '$1null');
  return JSON.parse(validJson) as AnalyticalReport;
}

function NetworkViz() {
  return (
    <div className="network-viz" aria-label="Network topology visualization" aria-hidden="true">
      <svg viewBox="0 0 600 360" xmlns="http://www.w3.org/2000/svg" className="nv-svg">
        {/* Grid */}
        {Array.from({ length: 13 }, (_, i) => (
          <line key={`vg${i}`} x1={i * 50} y1="0" x2={i * 50} y2="360" stroke="#1e1e1e" strokeWidth="0.5" />
        ))}
        {Array.from({ length: 8 }, (_, i) => (
          <line key={`hg${i}`} x1="0" y1={i * 50} x2="600" y2={i * 50} stroke="#1e1e1e" strokeWidth="0.5" />
        ))}
        {/* Frame */}
        <rect x="1" y="1" width="598" height="358" fill="none" stroke="#292929" strokeWidth="1" />
        {/* Corner marks */}
        <path d="M1,1 L16,1 M1,1 L1,16" stroke="#FF3038" strokeWidth="1.5" fill="none" />
        <path d="M599,1 L584,1 M599,1 L599,16" stroke="#FF3038" strokeWidth="1.5" fill="none" />
        <path d="M1,359 L1,344 M1,359 L16,359" stroke="#FF3038" strokeWidth="1.5" fill="none" />
        <path d="M599,359 L584,359 M599,359 L599,344" stroke="#FF3038" strokeWidth="1.5" fill="none" />

        {/* Network nodes */}
        {[
          [300, 180], [150, 90], [450, 90], [100, 240], [500, 240], [250, 300], [350, 300],
          [200, 160], [400, 160], [300, 80],
        ].map(([cx, cy], i) => (
          <g key={i}>
            <circle cx={cx} cy={cy} r={i === 0 ? 10 : 6} fill="#0A0A0A" stroke={i === 0 ? '#FF3038' : '#292929'} strokeWidth={i === 0 ? 1.5 : 1} />
            <circle cx={cx} cy={cy} r={i === 0 ? 14 : 9} fill="none" stroke={i === 0 ? 'rgba(255,48,56,0.2)' : '#161616'} strokeWidth="1" />
          </g>
        ))}

        {/* Edges */}
        {[
          [[300,180],[150,90]], [[300,180],[450,90]], [[300,180],[100,240]],
          [[300,180],[500,240]], [[300,180],[250,300]], [[300,180],[350,300]],
          [[150,90],[200,160]], [[450,90],[400,160]], [[300,80],[300,180]],
        ].map(([[x1,y1],[x2,y2]], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="#1e1e1e" strokeWidth="1" strokeDasharray={i % 3 === 0 ? '4,4' : '2,6'} />
        ))}

        {/* Red alert edge */}
        <line x1="300" y1="180" x2="100" y2="240" stroke="rgba(255,48,56,0.5)" strokeWidth="1.5" strokeDasharray="3,5" />

        {/* Labels */}
        <text x="300" y="345" textAnchor="middle" fill="#505050" fontFamily="monospace" fontSize="9" letterSpacing="4">
          NID-X / LIVE INTRUSION DETECTOR TELEMETRY
        </text>
      </svg>
    </div>
  );
}

export default function Overview() {
  const [stats, setStats] = useState<any>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [latestUserEvaluation, setLatestUserEvaluation] = useState<AnalyticalReport | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [st, md, mt] = await Promise.all([
        api.overviewStats().catch(() => null),
        api.modelInfo().catch(() => null),
        api.metrics().catch(() => null),
      ]);
      setStats(st);
      setModelInfo(md);
      setMetrics(mt);
      try {
        const reportList = await api.reports();
        const latestEvaluationReport = reportList.reports
          .filter(report => report.available
            && report.type === 'json'
            && report.report_id.startsWith('analytical_report_')
            && report.report_id.endsWith('_json'))
          .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))[0];
        if (latestEvaluationReport) {
          const reportText = await api.fetchReportText(latestEvaluationReport.report_id);
          setLatestUserEvaluation(parseAnalyticalReport(reportText));
        } else {
          setLatestUserEvaluation(null);
        }
        setEvaluationError(null);
      } catch (e) {
        setLatestUserEvaluation(null);
        setEvaluationError(e instanceof Error ? e.message : 'Could not load uploaded-data evaluation');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const modelVer = modelInfo?.model_version ?? 'N/A';
  const datasetStatus = stats?.total_flows_analyzed > 0
    ? `${stats.total_flows_analyzed.toLocaleString()} FLOWS ANALYZED`
    : (modelInfo?.available ? 'MODEL READY — AWAITING UPLOAD' : 'STANDBY');

  const isSampleMetrics = !!(metrics?.is_sample_data || stats?.metrics?.is_sample_data);

  const latestBatch = stats?.latest_batch;
  const latestBatchThreat = latestBatch?.summary?.threat_level ?? (stats?.total_attacks_detected > 0 ? 'ANOMALIES DETECTED' : 'NORMAL');
  const latestFilename = latestBatch?.summary?.filename ?? (latestBatch?.batch_id ? `Batch ${latestBatch.batch_id.slice(0, 8)}` : 'None');
  const uploadedEvaluation = latestUserEvaluation?.evaluation_metrics?.has_ground_truth
    ? latestUserEvaluation.evaluation_metrics
    : null;
  const displayedMetrics = uploadedEvaluation ?? (isSampleMetrics ? null : metrics);
  const evaluatedAt = uploadedEvaluation
    ? latestUserEvaluation?.timestamp
    : isSampleMetrics ? undefined : metrics?.evaluated_at;

  return (
    <div className="overview-page">
      {/* Editorial hero */}
      <section className="overview-hero" aria-label="Hero">
        <div className="hero-left">
          <div className="hero-tag tag font-mono">OPERATIONAL TELEMETRY & INTRUSION DETECTION</div>
          <h1 className="hero-headline font-display">
            <span className="hero-line">NETWORKS</span>
            <span className="hero-line">UNDER</span>
            <span className="hero-line"><span className="text-red">WATCH.</span></span>
          </h1>
          <p className="hero-copy">
            Machine learning network traffic surveillance. Ingest network packet captures,
            inspect real-time anomaly probabilities, and triage security incidents with measurable evidence.
          </p>
          <div className="hero-cta">
            <Link to="/traffic" className="btn btn-primary">Analyze Traffic</Link>
            <Link to="/performance" className="btn btn-secondary">View Model Performance</Link>
            <Link to="/alerts" className="btn btn-secondary">Alerts</Link>
            <Link to="/reports" className="btn btn-secondary">Reports</Link>
            <button className="btn btn-secondary" onClick={loadAll} title="Refresh telemetry">
              ↻ REFRESH
            </button>
          </div>
          <div className="hero-meta font-mono">
            <div className="meta-item">
              <span className="meta-label">Active Model</span>
              <span className="meta-value">{modelVer}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Traffic Ingest Status</span>
              <span className={`meta-value ${stats?.total_flows_analyzed > 0 ? 'text-red' : ''}`}>{datasetStatus}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Pending Alerts</span>
              <span className={`meta-value ${(stats?.unack_alerts ?? 0) > 0 ? 'text-red' : ''}`}>
                {(stats?.unack_alerts ?? 0).toLocaleString()} UNACK
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Latest Threat Level</span>
              <span className="meta-value">{latestBatchThreat}</span>
            </div>
          </div>
        </div>

        <div className="hero-right">
          <NetworkViz />
        </div>
      </section>

      {/* Live Ingested Traffic Metrics Strip */}
      <section style={{ padding: '0 var(--sp-8) var(--sp-6)' }} aria-label="Live Telemetry">
        <div className="panel" style={{ marginBottom: 'var(--sp-6)' }}>
          <div className="panel-header">
            <span className="panel-title">LIVE INGESTED TRAFFIC TELEMETRY</span>
            <span className="tag font-mono">LATEST INGESTION: {latestFilename}</span>
          </div>
          <div className="grid-4">
            <MetricPanel
              label="Total Flows Analyzed"
              value={stats ? stats.total_flows_analyzed.toLocaleString() : '—'}
              sub="Across all uploaded captures"
            />
            <MetricPanel
              label="Malicious Flows"
              value={stats ? stats.total_attacks_detected.toLocaleString() : '—'}
              sub="Classified intrusions"
              red={stats?.total_attacks_detected > 0}
            />
            <MetricPanel
              label="Attack Ratio"
              value={stats ? `${(stats.overall_attack_rate * 100).toFixed(2)}%` : '—'}
              sub="Share of suspicious flows"
              red={stats?.overall_attack_rate > 0.1}
            />
            <MetricPanel
              label="Active Alerts"
              value={stats ? stats.unack_alerts.toLocaleString() : '—'}
              sub="Pending incident triage"
              red={stats?.unack_alerts > 0}
            />
          </div>
        </div>

        {/* Model Evaluation & Performance Strip */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">EVALUATION METRICS</span>
            <span className="tag font-mono">
              {uploadedEvaluation && latestUserEvaluation
                ? `USER DATA: ${latestUserEvaluation.filename}`
                : evaluatedAt
                  ? `EVALUATED AT: ${new Date(evaluatedAt).toLocaleString()}`
                  : 'NO USER DATA EVALUATED'}
            </span>
          </div>
          {isSampleMetrics && !uploadedEvaluation && (
            <div style={{
              padding: 'var(--sp-2) var(--sp-3)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-xs)',
              color: 'var(--c-text-mute)',
              marginBottom: 'var(--sp-4)',
            }}>
              Upload and analyze your own network traffic CSV to display evaluation metrics here.
            </div>
          )}
          {evaluationError && (
            <p role="alert" style={{ color: 'var(--c-red)', fontSize: 'var(--fs-xs)', margin: '0 0 var(--sp-3)' }}>
              Could not load uploaded-data evaluation: {evaluationError}
            </p>
          )}
          <div className="grid-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}>
            <MetricPanel
              label="Accuracy"
              value={fmt(displayedMetrics?.accuracy)}
              sub="Correct classifications"
            />
            <MetricPanel
              label="Precision"
              value={fmt(displayedMetrics?.precision)}
              sub="Positive predictive value"
            />
            <MetricPanel
              label="Recall / Detection Rate"
              value={fmt(displayedMetrics?.recall)}
              sub="True positive sensitivity"
            />
            <MetricPanel
              label="F1-Score"
              value={fmt(displayedMetrics?.f1_score)}
              sub="Harmonic mean of precision & recall"
            />
            <MetricPanel
              label="ROC-AUC"
              value={fmt(displayedMetrics?.roc_auc)}
              sub="Discrimination capacity"
            />
            <MetricPanel
              label="PR-AUC (AP)"
              value={fmt(displayedMetrics?.pr_auc, false)}
              sub="Average precision"
            />
            <MetricPanel
              label="False Positive Rate"
              value={fmt(displayedMetrics?.false_positive_rate)}
              sub="False alarms on benign traffic"
              red
            />
            <MetricPanel
              label="Ingestion Batches"
              value={stats ? stats.total_batches.toLocaleString() : '—'}
              sub="Processed CSV batches"
            />
            <MetricPanel
              label="Resolved Incidents"
              value={stats ? stats.resolved_alerts.toLocaleString() : '—'}
              sub="Triaged and closed alerts"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
