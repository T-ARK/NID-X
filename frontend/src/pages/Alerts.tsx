import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { PageHeader, EmptyState, LoadingState, ErrorState } from '../components/Common';
import type { AlertRecord, AlertsResponse } from '../types/api';

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [unackOnly, setUnackOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{
    total_alerts: number;
    unack_alerts: number;
    resolved_alerts: number;
    attack_alerts: number;
  } | null>(null);
  const [batchId, setBatchId] = useState<string>('');
  const [clearing, setClearing] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res: AlertsResponse = await api.alerts(page, pageSize, unackOnly, batchId || undefined);
      setAlerts(res.alerts);
      setTotal(res.total);
      if (res.summary) setSummary(res.summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, unackOnly, batchId]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleAcknowledge = async (id: string) => {
    setActionLoading(id);
    try {
      await api.acknowledgeAlert(id);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: 1 } : a));
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(null);
    }
  };

  const handleResolve = async (id: string) => {
    setActionLoading(id);
    try {
      await api.resolveAlert(id);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: 1, resolved: 1 } : a));
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(null);
    }
  };

  const handleClearLog = async () => {
    if (!window.confirm('Clear all stored alerts and history? This resets the audit log for clean testing.')) return;
    setClearing(true);
    try {
      await api.clearAuditLog();
      await fetchAlerts();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to clear audit log');
    } finally {
      setClearing(false);
    }
  };

  const filteredAlerts = alerts.filter(a => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.predicted_class.toLowerCase().includes(q) ||
      (a.batch_id && a.batch_id.toLowerCase().includes(q)) ||
      (a.source_type && a.source_type.toLowerCase().includes(q)) ||
      a.id.toLowerCase().includes(q)
    );
  });

  const unackCount = alerts.filter(a => a.acknowledged === 0).length;
  const attackCount = alerts.filter(a => a.predicted_class.toUpperCase().includes('ATTACK') || a.predicted_class === '1').length;
  const resolvedCount = alerts.filter(a => a.resolved === 1).length;

  return (
    <div className="page" style={{ padding: 'var(--sp-8)' }}>
      <PageHeader
        title="Alert Management"
        sub="Telemetry of anomalous network flow detections persisted in the local SQLite audit log."
      />

      {/* Metrics Row */}
      <div className="grid-4" style={{ marginBottom: 'var(--sp-6)' }}>
        <div className="metric-panel">
          <div className="metric-label">Stored Events</div>
          <div className="metric-value">{summary ? summary.total_alerts.toLocaleString() : total.toLocaleString()}</div>
          <div className="metric-sub">SQLite event records</div>
        </div>
        <div className="metric-panel">
          <div className="metric-label">Attack Predictions</div>
          <div className="metric-value red">{summary ? summary.attack_alerts.toLocaleString() : '—'}</div>
          <div className="metric-sub">Malicious detections</div>
        </div>
        <div className="metric-panel">
          <div className="metric-label">Unacknowledged</div>
          <div className={`metric-value${(summary?.unack_alerts ?? 0) > 0 ? ' red' : ''}`}>
            {summary ? summary.unack_alerts.toLocaleString() : '—'}
          </div>
          <div className="metric-sub">Pending security triage</div>
        </div>
        <div className="metric-panel">
          <div className="metric-label">Resolved Incidents</div>
          <div className="metric-value">{summary ? summary.resolved_alerts.toLocaleString() : '—'}</div>
          <div className="metric-sub">Triaged & documented</div>
        </div>
      </div>

      {/* Filter and Control Bar */}
      <div className="panel" style={{ marginBottom: 'var(--sp-6)' }}>
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 'var(--sp-3)',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', gap: 'var(--sp-3)', flex: 1, minWidth: 260 }}>
            <input
              className="input"
              style={{ maxWidth: 320 }}
              placeholder="SEARCH CLASS, BATCH ID..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              aria-label="Filter alerts"
            />
            <button
              className={`btn ${unackOnly ? 'btn-danger' : 'btn-secondary'}`}
              onClick={() => { setUnackOnly(u => !u); setPage(1); }}
            >
              {unackOnly ? 'SHOW ALL ALERTS' : 'UNACKNOWLEDGED ONLY'}
            </button>
          </div>

          <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)' }}>
            <span style={{ color: 'var(--c-text-mute)' }}>PAGE SIZE:</span>
            <select
              className="input"
              style={{ width: 80, padding: '4px 8px' }}
              value={pageSize}
              onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}
              aria-label="Page size"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <button className="btn btn-secondary" onClick={fetchAlerts} style={{ padding: '6px 12px' }}>
              ↻ REFRESH
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleClearLog}
              disabled={clearing}
              style={{ padding: '6px 12px', color: 'var(--c-red)' }}
              title="Reset alerts audit table"
            >
              {clearing ? 'CLEARING...' : 'CLEAR LOG'}
            </button>
          </div>
        </div>
      </div>

      {/* Notice Banner */}
      <div style={{
        background: 'rgba(255,48,56,0.06)',
        border: '1px solid var(--c-border)',
        padding: 'var(--sp-3) var(--sp-4)',
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-xs)',
        color: 'var(--c-text-sec)',
        marginBottom: 'var(--sp-6)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--sp-3)',
      }}>
        <span style={{ color: 'var(--c-red)', fontSize: '14px' }}>⚠</span>
        <span>
          <strong>OPERATIONAL NOTICE:</strong> Machine learning predictions represent statistical flow anomalies, not verified security breaches. Confirm via packet capture or firewall telemetry before applying blocking rules.
        </span>
      </div>

      {/* Table Content */}
      {loading ? (
        <LoadingState label="Fetching alert audit log..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchAlerts} />
      ) : filteredAlerts.length === 0 ? (
        <EmptyState
          title="NO ALERTS FOUND"
          desc={search ? "No events matched your search query." : "No suspicious flow alerts have been logged yet. Upload a network traffic CSV to execute inference."}
        />
      ) : (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Audit Log / Anomaly Events</span>
            <span className="font-mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
              Page {page} of {Math.max(1, Math.ceil(total / pageSize))}
            </span>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp (UTC)</th>
                  <th>Classification</th>
                  <th>Confidence</th>
                  <th>Severity</th>
                  <th>Source</th>
                  <th>Batch / Job</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map(a => {
                  const isAttack = a.predicted_class.toUpperCase().includes('ATTACK') || a.predicted_class === '1';
                  return (
                    <tr key={a.id}>
                      <td style={{ color: 'var(--c-text-mute)' }}>
                        {new Date(a.timestamp).toLocaleString()}
                      </td>
                      <td>
                        <span className={`badge ${isAttack ? 'badge-attack' : 'badge-benign'}`}>
                          {isAttack ? '⚡ ' : '○ '}{a.predicted_class}
                        </span>
                      </td>
                      <td>
                        {a.score != null ? `${(a.score * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '10px',
                          color: a.severity === 'HIGH' ? 'var(--c-red)' : 'var(--c-text-mute)',
                          fontWeight: 600,
                        }}>
                          {a.severity}
                        </span>
                      </td>
                      <td style={{ color: 'var(--c-text-mute)' }}>
                        {a.source_type ?? 'api'}
                      </td>
                      <td style={{ color: 'var(--c-text-mute)' }}>
                        {a.batch_id ? a.batch_id.slice(0, 8) : '—'}
                      </td>
                      <td>
                        {a.resolved === 1 ? (
                          <span style={{ color: '#686868', fontSize: '10px' }}>✓ RESOLVED</span>
                        ) : a.acknowledged === 1 ? (
                          <span style={{ color: 'var(--c-text-sec)', fontSize: '10px' }}>◉ ACKED</span>
                        ) : (
                          <span style={{ color: 'var(--c-red)', fontSize: '10px', fontWeight: 600 }}>● UNACKED</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          {a.acknowledged === 0 && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '10px' }}
                              onClick={() => handleAcknowledge(a.id)}
                              disabled={actionLoading === a.id}
                            >
                              ACK
                            </button>
                          )}
                          {a.resolved === 0 && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '10px' }}
                              onClick={() => handleResolve(a.id)}
                              disabled={actionLoading === a.id}
                            >
                              RESOLVE
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Bar */}
          <div className="pagination" style={{ justifyContent: 'space-between', padding: 'var(--sp-3) var(--sp-2)' }}>
            <span style={{ color: 'var(--c-text-mute)' }}>
              Showing {filteredAlerts.length} of {total} records
            </span>
            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button
                className="btn btn-secondary"
                style={{ padding: '4px 10px' }}
                disabled={page <= 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
              >
                ◀ PREV
              </button>
              <button
                className="btn btn-secondary"
                style={{ padding: '4px 10px' }}
                disabled={page * pageSize >= total}
                onClick={() => setPage(p => p + 1)}
              >
                NEXT ▶
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
