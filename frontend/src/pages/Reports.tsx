import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { PageHeader, EmptyState, LoadingState, ErrorState } from '../components/Common';
import type { ReportEntry, ReportsListResponse } from '../types/api';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function trafficFigureBatch(reportId: string): string | null {
  return reportId.match(/^figure_traffic_.+_([a-f0-9]{8})$/i)?.[1].toLowerCase() ?? null;
}

export default function Reports() {
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genMessage, setGenMessage] = useState<string | null>(null);
  const [previewFig, setPreviewFig] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<{ id: string; name: string; type: string; content: string } | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [cacheKey, setCacheKey] = useState<number>(Date.now());
  const [selectedFigureBatch, setSelectedFigureBatch] = useState('');

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res: ReportsListResponse = await api.reports();
      setReports(res.reports);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch reports');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const handleRefresh = async () => {
    setCacheKey(Date.now());
    await fetchReports();
  };

  const handlePreviewDoc = async (rep: ReportEntry) => {
    setDocLoading(true);
    try {
      const text = await api.fetchReportText(rep.report_id);
      setPreviewDoc({ id: rep.report_id, name: rep.name, type: rep.type, content: text });
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Could not load report content');
    } finally {
      setDocLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setGenMessage(null);
    try {
      const res = await api.generateReport();
      setGenMessage(res.message);
      await fetchReports();
    } catch (e) {
      setGenMessage(e instanceof Error ? e.message : 'Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const documentReports = reports.filter(r => !r.report_id.startsWith('figure_'));
  const figureReports = reports.filter(r => r.report_id.startsWith('figure_'));
  const figureBatchMap = new Map<string, { id: string; createdAt: string | null; figures: ReportEntry[] }>();
  figureReports.forEach(figure => {
    const batchId = trafficFigureBatch(figure.report_id);
    if (!batchId) return;
    const batch = figureBatchMap.get(batchId) ?? { id: batchId, createdAt: figure.created_at, figures: [] };
    batch.figures.push(figure);
    if ((figure.created_at ?? '') > (batch.createdAt ?? '')) batch.createdAt = figure.created_at;
    figureBatchMap.set(batchId, batch);
  });
  const figureBatches = Array.from(figureBatchMap.values())
    .sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''));
  const activeFigureBatch = figureBatches.find(batch => batch.id === selectedFigureBatch) ?? figureBatches[0];
  const visibleFigureReports = [
    ...figureReports.filter(figure => !trafficFigureBatch(figure.report_id)),
    ...(activeFigureBatch?.figures ?? []),
  ];

  return (
    <div className="page" style={{ padding: 'var(--sp-8)' }}>
      <PageHeader
        title="Reports & Artifacts"
        sub="Persistent evaluation telemetry, dataset audit reports, candidate benchmarks, and downloadable artifacts."
      />

      {/* Action Header Panel */}
      <div className="panel" style={{ marginBottom: 'var(--sp-6)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--sp-3)' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 4 }}>
              REPORT GENERATION ENGINE
            </div>
            <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--c-text-sec)' }}>
              Regenerate all figures, matrices, and benchmark tables from current model weights.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
            <button
              className="btn btn-secondary"
              onClick={handleRefresh}
              title="Reload report and figure registry"
            >
              ↻ REFRESH REGISTRY
            </button>
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? 'GENERATING ARTIFACTS...' : 'GENERATE ALL REPORTS'}
            </button>
          </div>
        </div>

        {genMessage && (
          <div style={{
            background: 'rgba(255,48,56,0.08)',
            border: '1px solid var(--c-border)',
            padding: 'var(--sp-2) var(--sp-3)',
            marginTop: 'var(--sp-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-xs)',
            color: 'var(--c-text-sec)',
          }}>
            {genMessage}
          </div>
        )}
      </div>

      {loading ? (
        <LoadingState label="Indexing report registry..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchReports} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
          {/* Document Reports Section */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Evaluation & Audit Documents</span>
              <span className="font-mono text-mute" style={{ fontSize: 'var(--fs-xs)' }}>
                {documentReports.filter(r => r.available).length} OF {documentReports.length} READY
              </span>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Report Name</th>
                    <th>Identifier</th>
                    <th>Format</th>
                    <th>File Size</th>
                    <th>Last Updated</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Download</th>
                  </tr>
                </thead>
                <tbody>
                  {documentReports.map(rep => (
                    <tr key={rep.report_id}>
                      <td style={{ fontWeight: 600, color: 'var(--c-text)' }}>
                        {rep.name}
                      </td>
                      <td style={{ color: 'var(--c-text-mute)' }}>
                        {rep.report_id}
                      </td>
                      <td>
                        <span className="tag">{rep.type.toUpperCase()}</span>
                      </td>
                      <td style={{ color: 'var(--c-text-mute)' }}>
                        {rep.available ? formatBytes(rep.size_bytes) : '—'}
                      </td>
                      <td style={{ color: 'var(--c-text-mute)' }}>
                        {rep.created_at ? new Date(rep.created_at).toLocaleString() : 'Not Generated'}
                      </td>
                      <td>
                        {rep.available ? (
                          <span style={{ color: 'var(--c-text)', fontSize: '11px' }}>● AVAILABLE</span>
                        ) : (
                          <span style={{ color: 'var(--c-text-mute)', fontSize: '11px' }}>○ NOT GENERATED</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {rep.available ? (
                          <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                            {(rep.type === 'md' || rep.type === 'json' || rep.type === 'csv') && (
                              <button
                                className="btn btn-secondary"
                                onClick={() => handlePreviewDoc(rep)}
                                disabled={docLoading}
                                style={{ padding: '3px 8px', fontSize: '10px' }}
                                title="View document inline in browser"
                              >
                                VIEW
                              </button>
                            )}
                            <a
                              href={api.downloadReport(rep.report_id)}
                              download={`${rep.report_id}.${rep.type}`}
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '10px' }}
                            >
                              DOWNLOAD ↗
                            </a>
                          </div>
                        ) : (
                          <button className="btn btn-secondary" disabled style={{ padding: '3px 8px', fontSize: '10px', opacity: 0.3 }}>
                            N/A
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Visual Figures Gallery Section */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Visual Evidence / Evaluation Charts</span>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
                {figureBatches.length > 1 && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', color: 'var(--c-text-mute)', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)' }}>
                    BATCH
                    <select
                      className="input"
                      aria-label="Select traffic figure batch"
                      value={activeFigureBatch?.id ?? ''}
                      onChange={event => setSelectedFigureBatch(event.target.value)}
                      style={{ width: 'auto', minWidth: 220 }}
                    >
                      {figureBatches.map((batch, index) => (
                        <option key={batch.id} value={batch.id}>
                          {index === 0 ? 'LATEST' : 'OLDER'} — {batch.id.toUpperCase()} — {batch.createdAt ? new Date(batch.createdAt).toLocaleString() : 'DATE N/A'}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <span className="font-mono text-mute" style={{ fontSize: 'var(--fs-xs)' }}>
                  {visibleFigureReports.length} SHOWN / {figureReports.length} AVAILABLE
                </span>
              </div>
            </div>

            {visibleFigureReports.length === 0 ? (
              <EmptyState
                title="NO CHARTS GENERATED"
                desc="Click 'GENERATE ALL REPORTS' above or evaluate the model to create ROC curves, confusion matrices, and feature importance charts."
              />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 'var(--sp-4)',
              }}>
                {visibleFigureReports.map(fig => (
                  <div
                    key={fig.report_id}
                    style={{
                      background: 'var(--c-bg)',
                      border: '1px solid var(--c-border)',
                      padding: 'var(--sp-3)',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 'var(--sp-2)',
                        borderBottom: '1px solid var(--c-border)',
                        paddingBottom: 'var(--sp-1)',
                      }}>
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '11px',
                          color: 'var(--c-text)',
                          fontWeight: 600,
                        }}>
                          {fig.name.replace('Figure: ', '').toUpperCase()}
                        </span>
                        <span className="tag font-mono" style={{ fontSize: '9px' }}>
                          {formatBytes(fig.size_bytes)}
                        </span>
                      </div>

                      <div
                        style={{
                          background: '#080808',
                          border: '1px solid #1c1c1c',
                          height: '180px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                          overflow: 'hidden',
                        }}
                        onClick={() => setPreviewFig(fig.report_id)}
                        title="Click to view full image"
                      >
                        <img
                          src={`${api.downloadReport(fig.report_id)}?t=${cacheKey}`}
                          alt={fig.name}
                          style={{
                            maxWidth: '100%',
                            maxHeight: '100%',
                            objectFit: 'contain',
                          }}
                        />
                      </div>
                    </div>

                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginTop: 'var(--sp-3)',
                    }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: '10px' }}
                        onClick={() => setPreviewFig(fig.report_id)}
                      >
                        ENLARGE
                      </button>
                      <a
                        href={api.downloadReport(fig.report_id)}
                        download={`${fig.report_id}.png`}
                        className="btn btn-primary"
                        style={{ padding: '4px 10px', fontSize: '10px' }}
                      >
                        SAVE PNG
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Image Preview Modal */}
      {previewFig && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.85)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--sp-6)',
          }}
          onClick={() => setPreviewFig(null)}
          role="dialog"
          aria-label="Image preview"
        >
          <div
            style={{
              background: 'var(--c-panel)',
              border: '1px solid var(--c-border)',
              maxWidth: '90vw',
              maxHeight: '90vh',
              padding: 'var(--sp-4)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--sp-3)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="font-mono uppercase" style={{ fontSize: 'var(--fs-sm)', color: 'var(--c-text)' }}>
                {previewFig}
              </span>
              <button
                className="btn btn-secondary"
                style={{ padding: '2px 8px' }}
                onClick={() => setPreviewFig(null)}
              >
                ✕ CLOSE
              </button>
            </div>
            <img
              src={`${api.downloadReport(previewFig)}?t=${cacheKey}`}
              alt="Enlarged visualization"
              style={{
                maxWidth: '85vw',
                maxHeight: '75vh',
                objectFit: 'contain',
              }}
            />
          </div>
        </div>
      )}

      {/* Document Content In-Browser Viewer Modal */}
      {previewDoc && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.85)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--sp-6)',
          }}
          onClick={() => setPreviewDoc(null)}
          role="dialog"
          aria-label="Document Preview"
        >
          <div
            style={{
              background: '#0D0D0D',
              border: '1px solid var(--c-border)',
              width: '90vw',
              maxWidth: '900px',
              maxHeight: '85vh',
              padding: 'var(--sp-5)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--sp-3)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--c-border)', paddingBottom: 'var(--sp-2)' }}>
              <div>
                <span className="font-mono uppercase text-red" style={{ fontWeight: 'bold', fontSize: 'var(--fs-sm)' }}>
                  {previewDoc.name}
                </span>
                <span className="tag font-mono" style={{ marginLeft: 8, fontSize: '10px' }}>
                  {previewDoc.type.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                <a
                  href={api.downloadReport(previewDoc.id)}
                  download={`${previewDoc.id}.${previewDoc.type}`}
                  className="btn btn-secondary"
                  style={{ padding: '2px 8px', fontSize: '11px' }}
                >
                  DOWNLOAD FILE ↗
                </a>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '2px 8px', fontSize: '11px' }}
                  onClick={() => setPreviewDoc(null)}
                >
                  ✕ CLOSE
                </button>
              </div>
            </div>
            <div style={{
              background: '#050505',
              border: '1px solid #1a1a1a',
              padding: 'var(--sp-4)',
              overflowY: 'auto',
              maxHeight: '65vh',
              fontFamily: previewDoc.type === 'json' || previewDoc.type === 'csv' ? 'var(--font-mono)' : 'inherit',
              fontSize: '12px',
              lineHeight: 1.6,
              color: 'var(--c-text)',
              whiteSpace: 'pre-wrap',
            }}>
              {previewDoc.content}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
