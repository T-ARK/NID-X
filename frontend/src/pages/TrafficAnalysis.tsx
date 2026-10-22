import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader, EmptyState, LoadingState, ErrorState } from '../components/Common';
import { api } from '../services/api';
import type { CSVPredictResponse } from '../types/api';

type UploadState = 'idle' | 'loading' | 'success' | 'error';
type ActiveTab = 'report' | 'charts' | 'records';

export default function TrafficAnalysis() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>('idle');
  const [result, setResult] = useState<CSVPredictResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [search, setSearch] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('report');
  const [isDemoSample, setIsDemoSample] = useState(false);
  const [selectedFigure, setSelectedFigure] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File | null) => {
    if (!f) return;
    if (!f.name.endsWith('.csv')) {
      setError('Only CSV files are supported.');
      setState('error');
      return;
    }
    setFile(f);
    setIsDemoSample(false);
    setState('idle');
    setError('');
    setResult(null);
  };

  const handleLoadSample = async () => {
    setState('loading');
    setError('');
    try {
      const sampleFile = await api.getSampleDataset();
      setFile(sampleFile);
      setIsDemoSample(true);
      setState('idle');
      setResult(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch demonstration sample dataset.');
      setState('error');
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setState('loading');
    setError('');
    try {
      const res = await api.predictCsv(file);
      setResult(res);
      setState('success');
      if (res.charts && res.charts.length > 0) {
        setSelectedFigure(res.charts[0].url);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
      setState('error');
    }
  };

  const filteredPredictions = (result?.predictions ?? []).filter(p => {
    if (!search) return true;
    return p.predicted_label.toLowerCase().includes(search.toLowerCase());
  });

  const downloadCsv = () => {
    if (!result) return;
    const headers = ['row_index', 'predicted_label', 'predicted_class', 'probability', 'timestamp'];
    const rows = result.predictions.map(p =>
      [p.row_index, p.predicted_label, p.predicted_class, p.probability ?? '', p.timestamp].join(',')
    );
    const blob = new Blob([headers.join(',') + '\n' + rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nidx_predictions_${result.batch_id.slice(0, 8)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadReportJson = () => {
    if (!result?.analytical_report) return;
    const blob = new Blob([JSON.stringify(result.analytical_report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nidx_analytical_report_${result.batch_id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadReportMd = () => {
    if (!result?.analytical_report) return;
    const r = result.analytical_report;
    const content = `# NID-X Network Traffic Analytical Report
Batch Identifier: ${r.batch_id}
Analyzed File: ${r.filename}
Timestamp: ${r.timestamp}
Threat Level: ${r.overall_threat_level}

## Executive Summary
- Total Flows Ingested: ${r.total_records.toLocaleString()}
- Attacks Detected: ${r.attack_count.toLocaleString()} (${(r.attack_rate * 100).toFixed(2)}%)
- Benign Flows: ${r.benign_count.toLocaleString()}
- Model Version: ${r.model_version}

## Recommendations
${r.recommendations.map(x => `- ${x}`).join('\n')}
`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nidx_analytical_report_${result.batch_id.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const report = result?.analytical_report;
  const evalMetrics = result?.evaluation;
  const charts = result?.charts ?? [];

  return (
    <div className="page" style={{ padding: 'var(--sp-8)' }}>
      <PageHeader
        title="Traffic Analysis & Intelligence"
        sub="Upload network-flow captures to generate threat visualizations, model classifications, and analytical reports strictly from your data."
      />

      {/* ── Ingest Panel ─────────────────────────────────────────────────────── */}
      {/* Only shown when we don't have results yet */}
      {state !== 'success' && (
        <div className="panel" style={{ marginBottom: 'var(--sp-6)' }}>
          <div className="panel-header">
            <span className="panel-title">INGEST TRAFFIC CAPTURE</span>
            <span className="tag font-mono">MAX 50 MB / CSV ONLY</span>
          </div>

          {/* Two-choice layout when no file is staged */}
          {!file ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 'var(--sp-6)', alignItems: 'start' }}>
              {/* Left: Upload your own */}
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 'var(--sp-3)', letterSpacing: '0.06em' }}>
                  OPTION A — YOUR OWN DATASET
                </div>
                <div
                  className={`upload-zone${dragOver ? ' drag-over' : ''}`}
                  onClick={() => fileRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={e => {
                    e.preventDefault();
                    setDragOver(false);
                    handleFile(e.dataTransfer.files[0] ?? null);
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label="Upload CSV file"
                  onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
                  style={{ minHeight: 100 }}
                >
                  <div className="upload-label" style={{ fontSize: 'var(--fs-xs)' }}>
                    DROP CSV HERE OR CLICK TO BROWSE
                  </div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".csv"
                    style={{ display: 'none' }}
                    onChange={e => handleFile(e.target.files?.[0] ?? null)}
                    aria-label="Choose CSV file"
                  />
                </div>
                <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginTop: 'var(--sp-2)', fontFamily: 'var(--font-mono)', lineHeight: 1.7 }}>
                  CIC-IDS2017, UNSW-NB15, or any network flow CSV.
                </p>
              </div>

              {/* Divider */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 'var(--sp-8)' }}>
                <div style={{ width: 1, height: 40, background: 'var(--c-border)' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', padding: 'var(--sp-2)' }}>OR</span>
                <div style={{ width: 1, height: 40, background: 'var(--c-border)' }} />
              </div>

              {/* Right: Sample data */}
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 'var(--sp-3)', letterSpacing: '0.06em' }}>
                  OPTION B — BUNDLED SAMPLE DEMO DATA
                </div>
                <div style={{
                  border: '1px solid var(--c-border)',
                  padding: 'var(--sp-4)',
                  background: 'var(--c-bg)',
                  minHeight: 100,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  gap: 'var(--sp-3)',
                }}>
                  <p style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', margin: 0, lineHeight: 1.7 }}>
                    300-row synthetic sample (used to train the bundled demo model).
                    Results will <strong style={{ color: '#E5A000' }}>NOT</strong> update the global metrics.
                  </p>
                  <button
                    className="btn btn-secondary"
                    onClick={handleLoadSample}
                    disabled={state === 'loading'}
                    style={{ alignSelf: 'flex-start' }}
                    title="Fetches sample_flows.csv on demand — does not auto-load on startup"
                  >
                    {state === 'loading' ? 'LOADING...' : 'LOAD SAMPLE DEMO DATA'}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* File staged — show confirm/clear bar */
            <div>
              <div style={{
                background: 'var(--c-bg)',
                border: '1px solid var(--c-border)',
                padding: 'var(--sp-3) var(--sp-4)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-xs)',
                color: 'var(--c-text)',
                marginBottom: 'var(--sp-4)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}>
                <span>
                  <strong>{file.name}</strong> — {(file.size / 1024).toFixed(1)} KB
                  {isDemoSample && (
                    <span style={{ color: '#00F0FF', marginLeft: 10 }}>[DEMO SAMPLE — results will not update global metrics]</span>
                  )}
                </span>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '3px 10px', fontSize: '10px' }}
                  onClick={() => { setFile(null); setIsDemoSample(false); setState('idle'); setError(''); }}
                >
                  ✕ CLEAR FILE
                </button>
              </div>
              <div style={{ display: 'flex', gap: 'var(--sp-3)', alignItems: 'center', flexWrap: 'wrap' }}>
                <button
                  className="btn btn-primary"
                  onClick={handleUpload}
                  disabled={state === 'loading'}
                  aria-busy={state === 'loading'}
                >
                  {state === 'loading' ? 'ANALYZING UPLOADED DATA...' : 'ANALYZE TRAFFIC DATA'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* State Feedback */}
      {state === 'loading' && (
        <LoadingState label="Computing flow metrics, threat probabilities, and rendering charts..." />
      )}
      {state === 'error' && <ErrorState message={error} onRetry={handleUpload} />}

      {/* Analysis Output Section */}
      {state === 'success' && result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
          {/* Cross-Module Propagation Bar */}
          <div style={{
            background: 'var(--c-bg-card, #101010)',
            border: '1px solid var(--c-border)',
            padding: 'var(--sp-3) var(--sp-4)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--sp-3)',
          }}>
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--c-red)', fontWeight: 'bold' }}>
                ● ANALYSIS COMPLETE
                {isDemoSample && (
                  <span style={{ color: '#E5A000', marginLeft: 10, fontWeight: 400 }}>
                    [DEMO SAMPLE — global metrics not updated]
                  </span>
                )}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--c-text-mute)', marginTop: 2 }}>
                Batch {result.batch_id.slice(0, 8)}: {result.total_records.toLocaleString()} flows analyzed ({result.attack_count.toLocaleString()} threats detected).
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)', flexWrap: 'wrap' }}>
              <Link to="/" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)' }}>
                OVERVIEW ↗
              </Link>
              <Link to="/performance" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)' }}>
                MODEL PERFORMANCE ↗
              </Link>
              <Link to="/alerts" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)' }}>
                ALERTS ({result.attack_count}) ↗
              </Link>
              <Link to="/reports" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)' }}>
                REPORTS & CHARTS ↗
              </Link>
              <button
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)', borderColor: 'var(--c-border)' }}
                onClick={() => { setResult(null); setFile(null); setIsDemoSample(false); setState('idle'); setError(''); setSearch(''); }}
                title="Return to empty state and analyze a new file"
              >
                ✕ CLEAR RESULTS
              </button>
            </div>
          </div>
          {/* Executive Metrics Overview */}
          <div className="grid-4">
            <div className="metric-panel">
              <div className="metric-label">Total Ingested Flows</div>
              <div className="metric-value">{result.total_records.toLocaleString()}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-label">Malicious Flows</div>
              <div className="metric-value red">{result.attack_count.toLocaleString()}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-label">Benign Flows</div>
              <div className="metric-value">{result.benign_count.toLocaleString()}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-label">Attack Percentage</div>
              <div className={`metric-value${result.attack_rate > 0.1 ? ' red' : ''}`}>
                {(result.attack_rate * 100).toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Threat Posture Banner */}
          <div style={{
            background: 'var(--c-bg-sec)',
            border: `1px solid ${result.attack_rate > 0.15 ? 'var(--c-red)' : 'var(--c-border)'}`,
            padding: 'var(--sp-4)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 'var(--sp-3)',
          }}>
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 2 }}>
                OVERALL THREAT ASSESSMENT
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-lg)',
                fontWeight: 'bold',
                color: result.attack_rate > 0.15 ? 'var(--c-red)' : 'var(--c-text)',
              }}>
                {result.overall_threat_level ?? (result.attack_rate > 0 ? 'ANOMALIES DETECTED' : 'LOW RISK')}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-3)', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
              <span>BATCH: <span style={{ color: 'var(--c-text)' }}>{result.batch_id.slice(0, 8)}</span></span>
              <span>MODEL: <span style={{ color: 'var(--c-text)' }}>{result.model_version ?? 'N/A'}</span></span>
              <span>INFERENCE: <span style={{ color: 'var(--c-text)' }}>{result.inference_ms ?? 0} ms</span></span>
            </div>
          </div>

          {/* Warnings Bar */}
          {result.warnings.length > 0 && (
            <div style={{
              background: 'rgba(255,48,56,0.06)',
              border: '1px solid var(--c-red)',
              padding: 'var(--sp-3)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-xs)',
              color: 'var(--c-text-sec)',
            }}>
              {result.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}

          {/* Navigation Tabs */}
          <div style={{ display: 'flex', gap: 'var(--sp-2)', borderBottom: '1px solid var(--c-border)' }}>
            <button
              className={`btn ${activeTab === 'report' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ borderRadius: '0', borderBottom: 'none' }}
              onClick={() => setActiveTab('report')}
            >
              ANALYTICAL REPORT
            </button>
            <button
              className={`btn ${activeTab === 'charts' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ borderRadius: '0', borderBottom: 'none' }}
              onClick={() => setActiveTab('charts')}
            >
              GRAPHS & CHARTS ({charts.length})
            </button>
            <button
              className={`btn ${activeTab === 'records' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ borderRadius: '0', borderBottom: 'none' }}
              onClick={() => setActiveTab('records')}
            >
              FLOW AUDIT LOG ({filteredPredictions.length.toLocaleString()})
            </button>
          </div>

          {/* TAB 1: Analytical Report */}
          {activeTab === 'report' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)' }}>
              {/* Report Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--sp-3)' }}>
                <button className="btn btn-secondary" onClick={downloadReportMd}>
                  DOWNLOAD REPORT (MARKDOWN)
                </button>
                <button className="btn btn-secondary" onClick={downloadReportJson}>
                  DOWNLOAD REPORT (JSON)
                </button>
                <button className="btn btn-secondary" onClick={downloadCsv}>
                  EXPORT PREDICTIONS (CSV)
                </button>
              </div>

              {/* Severity Breakdown & TCP Flags */}
              <div className="grid-2">
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">SEVERITY TIER BREAKDOWN</span>
                  </div>
                  <table style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)' }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: 'var(--sp-2)' }}>Tier</th>
                        <th style={{ textAlign: 'left', padding: 'var(--sp-2)' }}>Probability</th>
                        <th style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>Count</th>
                        <th style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ padding: 'var(--sp-2)', color: 'var(--c-red)', fontWeight: 'bold' }}>CRITICAL</td>
                        <td style={{ padding: 'var(--sp-2)' }}>≥ 85%</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>{report?.critical_count ?? 0}</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>
                          {(((report?.critical_count ?? 0) / result.total_records) * 100).toFixed(1)}%
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: 'var(--sp-2)', color: '#FF6B72' }}>HIGH</td>
                        <td style={{ padding: 'var(--sp-2)' }}>70% – 84.9%</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>{report?.high_count ?? 0}</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>
                          {(((report?.high_count ?? 0) / result.total_records) * 100).toFixed(1)}%
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: 'var(--sp-2)', color: '#E5A000' }}>MEDIUM</td>
                        <td style={{ padding: 'var(--sp-2)' }}>50% – 69.9%</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>{report?.medium_count ?? 0}</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>
                          {(((report?.medium_count ?? 0) / result.total_records) * 100).toFixed(1)}%
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: 'var(--sp-2)', color: 'var(--c-text-mute)' }}>BENIGN</td>
                        <td style={{ padding: 'var(--sp-2)' }}>&lt; 50%</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>{report?.low_count ?? 0}</td>
                        <td style={{ textAlign: 'right', padding: 'var(--sp-2)' }}>
                          {(((report?.low_count ?? 0) / result.total_records) * 100).toFixed(1)}%
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">NETWORK PROTOCOL FLAGS PROFILE</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-3)', padding: 'var(--sp-2)' }}>
                    {Object.entries(report?.tcp_flags ?? {}).map(([flag, count]) => (
                      <div key={flag} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', padding: 'var(--sp-3)', textAlign: 'center' }}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>{flag}</div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-md)', fontWeight: 'bold', color: count > 0 ? 'var(--c-text)' : 'var(--c-text-mute)' }}>
                          {count.toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Ground-Truth Evaluation Metrics (if available in uploaded CSV) */}
              {evalMetrics && (
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">GROUND-TRUTH MODEL VALIDATION ON UPLOADED DATA</span>
                    <span className="tag font-mono">LABEL: {evalMetrics.label_column}</span>
                  </div>
                  <div className="grid-4" style={{ marginBottom: 'var(--sp-4)' }}>
                    <div className="metric-panel">
                      <div className="metric-label">Accuracy</div>
                      <div className="metric-value">{(evalMetrics.accuracy * 100).toFixed(2)}%</div>
                    </div>
                    <div className="metric-panel">
                      <div className="metric-label">Precision</div>
                      <div className="metric-value">{(evalMetrics.precision * 100).toFixed(2)}%</div>
                    </div>
                    <div className="metric-panel">
                      <div className="metric-label">Recall</div>
                      <div className="metric-value">{(evalMetrics.recall * 100).toFixed(2)}%</div>
                    </div>
                    <div className="metric-panel">
                      <div className="metric-label">F1-Score</div>
                      <div className="metric-value">{(evalMetrics.f1_score * 100).toFixed(2)}%</div>
                    </div>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', display: 'flex', gap: 'var(--sp-4)', flexWrap: 'wrap' }}>
                    <span>True Positives (TP): <strong style={{ color: 'var(--c-text)' }}>{evalMetrics.true_positives.toLocaleString()}</strong></span>
                    <span>False Positives (FP): <strong style={{ color: 'var(--c-red)' }}>{evalMetrics.false_positives.toLocaleString()}</strong></span>
                    <span>True Negatives (TN): <strong style={{ color: 'var(--c-text)' }}>{evalMetrics.true_negatives.toLocaleString()}</strong></span>
                    <span>False Negatives (FN): <strong style={{ color: 'var(--c-red)' }}>{evalMetrics.false_negatives.toLocaleString()}</strong></span>
                    <span>FPR: <strong style={{ color: 'var(--c-text)' }}>{(evalMetrics.false_positive_rate * 100).toFixed(2)}%</strong></span>
                  </div>
                </div>
              )}

              {/* Security Recommendations */}
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">ACTIONABLE SECURITY RECOMMENDATIONS</span>
                </div>
                <ul style={{ paddingLeft: 'var(--sp-5)', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-sec)', lineHeight: 1.9 }}>
                  {report?.recommendations.map((rec, i) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* TAB 2: Graphs & Charts Gallery */}
          {activeTab === 'charts' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)' }}>
              {charts.length === 0 ? (
                <EmptyState title="No Figures Generated" desc="Charts are compiled during analysis." />
              ) : (
                <>
                  {/* Selector Bar */}
                  <div style={{ display: 'flex', gap: 'var(--sp-2)', flexWrap: 'wrap' }}>
                    {charts.map(c => (
                      <button
                        key={c.id}
                        className={`btn ${selectedFigure === c.url ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setSelectedFigure(c.url)}
                      >
                        {c.title.toUpperCase()}
                      </button>
                    ))}
                  </div>

                  {/* High-res Figure Display */}
                  {selectedFigure && (
                    <div className="panel" style={{ textAlign: 'center', padding: 'var(--sp-4)' }}>
                      <img
                        src={selectedFigure}
                        alt="Network traffic analytical chart"
                        style={{
                          maxWidth: '100%',
                          maxHeight: '650px',
                          border: '1px solid var(--c-border)',
                          backgroundColor: '#050505',
                        }}
                      />
                      <div style={{ marginTop: 'var(--sp-3)', display: 'flex', justifyContent: 'center', gap: 'var(--sp-4)' }}>
                        <a
                          href={selectedFigure}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-secondary"
                        >
                          OPEN FULL SIZE
                        </a>
                        <a
                          href={selectedFigure}
                          download
                          className="btn btn-secondary"
                        >
                          DOWNLOAD CHART
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Thumbnails Grid */}
                  <div className="grid-3" style={{ marginTop: 'var(--sp-4)' }}>
                    {charts.map(c => (
                      <div
                        key={c.id}
                        className="panel"
                        style={{
                          cursor: 'pointer',
                          borderColor: selectedFigure === c.url ? 'var(--c-red)' : 'var(--c-border)',
                        }}
                        onClick={() => setSelectedFigure(c.url)}
                      >
                        <div className="panel-header">
                          <span className="panel-title" style={{ fontSize: 'var(--fs-xs)' }}>{c.title}</span>
                        </div>
                        <img
                          src={c.url}
                          alt={c.title}
                          style={{ width: '100%', height: '140px', objectFit: 'contain', backgroundColor: '#050505' }}
                        />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 3: Flow Records & Predictions Table */}
          {activeTab === 'records' && (
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">CLASSIFIED FLOW AUDIT TRAIL</span>
                <span className="font-mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
                  {filteredPredictions.length.toLocaleString()} / {result.total_records.toLocaleString()} rows
                </span>
              </div>

              <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
                <input
                  className="input"
                  style={{ maxWidth: 300 }}
                  placeholder="FILTER BY LABEL..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  aria-label="Filter predictions"
                />
                <button className="btn btn-secondary" onClick={downloadCsv}>
                  EXPORT FILTERED CSV
                </button>
              </div>

              {filteredPredictions.length === 0 ? (
                <EmptyState title="No Matching Flows" desc="Adjust search filters." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Classification</th>
                        <th>Class ID</th>
                        <th>Threat Confidence</th>
                        <th>Detection Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPredictions.slice(0, 500).map(p => (
                        <tr key={p.row_index}>
                          <td className="font-mono">{p.row_index}</td>
                          <td>
                            <span className={`badge${p.predicted_class === 1 ? ' badge-attack' : ' badge-benign'}`}>
                              {p.predicted_label}
                            </span>
                          </td>
                          <td className="font-mono">{p.predicted_class}</td>
                          <td className="font-mono">
                            {p.probability != null ? (
                              <span style={{ color: p.probability >= 0.7 ? 'var(--c-red)' : 'var(--c-text)' }}>
                                {(p.probability * 100).toFixed(2)}%
                              </span>
                            ) : (
                              'N/A'
                            )}
                          </td>
                          <td className="font-mono">{new Date(p.timestamp).toLocaleTimeString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredPredictions.length > 500 && (
                    <p className="font-mono text-mute" style={{ fontSize: 'var(--fs-xs)', padding: 'var(--sp-3)', textAlign: 'center' }}>
                      Showing first 500 rows. Use export button for full records.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {state === 'idle' && !file && (
        <EmptyState
          title="AWAITING TRAFFIC CAPTURE"
          desc="Select an option above: upload your own network-flow CSV, or load the bundled sample demo data to explore the pipeline."
        />
      )}
    </div>
  );
}
