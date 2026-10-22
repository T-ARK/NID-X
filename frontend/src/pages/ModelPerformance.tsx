import React, { useState } from 'react';
import { useApiData } from '../hooks/useApi';
import { api } from '../services/api';
import { PageHeader, MetricPanel, EmptyState, LoadingState, ErrorState } from '../components/Common';
import { ConfusionMatrix } from '../components/ConfusionMatrix';
import { ModelComparison } from '../components/ModelComparison';
import type { MetricsResponse, ModelInfoResponse } from '../types/api';

function fmt(v: number | null | undefined, isPercent = true): string {
  if (v == null) return 'N/A';
  return isPercent ? `${(v * 100).toFixed(2)}%` : String(v);
}

const FIGURES = [
  { id: 'class_distribution', label: 'THREAT BREAKDOWN', filename: 'class_distribution.png' },
  { id: 'error_analysis', label: 'ANOMALY DENSITY', filename: 'error_analysis.png' },
  { id: 'confusion_matrix', label: 'CONFUSION MATRIX', filename: 'confusion_matrix.png' },
  { id: 'roc_curve', label: 'ROC CURVE', filename: 'roc_curve.png' },
  { id: 'pr_curve', label: 'PR CURVE', filename: 'pr_curve.png' },
  { id: 'feature_importance', label: 'FEATURE IMPORTANCE', filename: 'feature_importance.png' },
  { id: 'model_comparison', label: 'MODEL BENCHMARKS', filename: 'model_comparison.png' },
  { id: 'numeric_distributions', label: 'FEATURE DISTRIBUTIONS', filename: 'numeric_distributions.png' },
  { id: 'correlation_heatmap', label: 'CORRELATION HEATMAP', filename: 'correlation_heatmap.png' },
];

export default function ModelPerformance() {
  const { data: metrics, loading: loadingMetrics, error: errMetrics, refetch: refetchMetrics } =
    useApiData<MetricsResponse>(() => api.metrics(), []);
  const { data: modelInfo, loading: loadingInfo } =
    useApiData<ModelInfoResponse>(() => api.modelInfo(), []);

  const [activeFig, setActiveFig] = useState<string>('class_distribution');
  const [cacheKey, setCacheKey] = useState<number>(Date.now());
  const [generating, setGenerating] = useState(false);
  const [genMessage, setGenMessage] = useState<string | null>(null);

  const handleRefresh = () => {
    setCacheKey(Date.now());
    refetchMetrics();
  };

  const handleRegenerate = async () => {
    setGenerating(true);
    setGenMessage(null);
    try {
      const res = await api.generateReport();
      setGenMessage(res.message);
      setCacheKey(Date.now());
      refetchMetrics();
    } catch (e) {
      setGenMessage(e instanceof Error ? e.message : 'Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  if (loadingMetrics || loadingInfo) {
    return (
      <div className="page" style={{ padding: 'var(--sp-8)' }}>
        <PageHeader title="Model Performance" sub="Loading persisted evaluation reports and model telemetry..." />
        <LoadingState label="Loading evaluation data..." />
      </div>
    );
  }

  if (errMetrics) {
    return (
      <div className="page" style={{ padding: 'var(--sp-8)' }}>
        <PageHeader title="Model Performance" sub="Evaluation telemetry" />
        <ErrorState message={errMetrics} onRetry={refetchMetrics} />
      </div>
    );
  }

  if (!metrics || !metrics.available) {
    return (
      <div className="page" style={{ padding: 'var(--sp-8)' }}>
        <PageHeader title="Model Performance" sub="Evaluation telemetry and discrimination benchmarks" />
        <EmptyState
          title="NO MODEL EVALUATION FOUND"
          desc="The model has not been trained or evaluated yet. Train the candidate models on your network dataset using the command below."
          action={
            <div style={{ marginTop: 'var(--sp-4)', textAlign: 'center' }}>
              <code style={{
                display: 'inline-block',
                background: 'var(--c-bg-sec)',
                border: '1px solid var(--c-border)',
                padding: '10px 16px',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-sm)',
                color: 'var(--c-text)',
              }}>
                python scripts/train_model.py --dataset data/raw/network_flows.csv
              </code>
            </div>
          }
        />
      </div>
    );
  }

  const selectedFig = FIGURES.find(f => f.id === activeFig) ?? FIGURES[0];

  return (
    <div className="page" style={{ padding: 'var(--sp-8)' }}>
      <PageHeader
        title="Model Performance"
        sub="Held-out validation metrics, discrimination curves, and candidate model benchmark comparison."
      />

      {/* Model Metadata Panel */}
      <div className="panel" style={{ marginBottom: 'var(--sp-6)' }}>
        <div className="panel-header">
          <span className="panel-title">Model Specifications & Telemetry</span>
          <span className="tag font-mono">SELECTED CANDIDATE</span>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 'var(--sp-4)',
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--fs-xs)',
        }}>
          <div>
            <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>ALGORITHM</div>
            <div style={{ color: 'var(--c-text)', fontWeight: 600 }}>{metrics.model_name ?? 'N/A'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>VERSION</div>
            <div style={{ color: 'var(--c-red)', fontWeight: 600 }}>{modelInfo?.model_version ?? 'N/A'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>DATASET SOURCE</div>
            <div style={{ color: 'var(--c-text-sec)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={modelInfo?.dataset_id ?? ''}>
              {modelInfo?.dataset_id ? modelInfo.dataset_id.split('/').slice(-2).join('/') : 'N/A'}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>EVALUATION SPLIT</div>
            <div style={{ color: 'var(--c-text-sec)' }}>{modelInfo?.evaluation_split ?? 'Stratified (70/10/20)'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>TRAINING TIME</div>
            <div style={{ color: 'var(--c-text-sec)' }}>{metrics.training_duration_s ? `${metrics.training_duration_s.toFixed(2)}s` : 'N/A'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>INFERENCE LATENCY</div>
            <div style={{ color: 'var(--c-text-sec)' }}>{metrics.inference_duration_ms ? `${metrics.inference_duration_ms.toFixed(2)}ms` : 'N/A'}</div>
          </div>
        </div>
      </div>

      {/* Held-Out Metrics Grid */}
      <div className="grid-4" style={{ marginBottom: 'var(--sp-6)' }}>
        <MetricPanel
          label="Accuracy"
          value={fmt(metrics.accuracy)}
          sub="Overall correctness"
        />
        <MetricPanel
          label="Recall (Sensitivity)"
          value={fmt(metrics.recall)}
          sub="True positive rate"
        />
        <MetricPanel
          label="Precision"
          value={fmt(metrics.precision)}
          sub="Positive predictive value"
        />
        <MetricPanel
          label="F1-Score"
          value={fmt(metrics.f1_score)}
          sub="Harmonic mean (Selection criteria)"
        />
        <MetricPanel
          label="False Positive Rate"
          value={fmt(metrics.false_positive_rate)}
          sub="Benign flows flagged as attack"
          red
        />
        <MetricPanel
          label="False Negative Rate"
          value={fmt(metrics.false_negative_rate)}
          sub="Attacks missed"
        />
        <MetricPanel
          label="ROC-AUC"
          value={fmt(metrics.roc_auc, false)}
          sub="Area under ROC curve"
        />
        <MetricPanel
          label="PR-AUC (AP)"
          value={fmt(metrics.pr_auc, false)}
          sub="Average Precision"
        />
      </div>

      {/* Two Column Section: Left = Tables, Right = Figure Viewer */}
      <div className="grid-2" style={{ alignItems: 'start', marginBottom: 'var(--sp-6)' }}>
        {/* Left Column: Confusion Matrix & Class Breakdown */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
          {/* Confusion Matrix Panel */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Confusion Matrix</span>
              <span className="font-mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
                N = {metrics.n_test?.toLocaleString() ?? '—'}
              </span>
            </div>
            {metrics.confusion_matrix ? (
              <ConfusionMatrix matrix={metrics.confusion_matrix} labels={['BENIGN', 'ATTACK']} />
            ) : (
              <p style={{ color: 'var(--c-text-mute)', fontSize: 'var(--fs-xs)' }}>Matrix unavailable.</p>
            )}
          </div>

          {/* Per-Class Breakdown Table */}
          {metrics.per_class && (
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Per-Class Discrimination Metrics</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Class</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>F1-Score</th>
                      <th>Support</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metrics.per_class).map(([className, pcm]) => (
                      <tr key={className}>
                        <td style={{ fontWeight: 600, color: className === '1' || className.toLowerCase().includes('attack') ? 'var(--c-red)' : 'var(--c-text)' }}>
                          {className === '0' ? 'BENIGN (0)' : className === '1' ? 'ATTACK (1)' : className}
                        </td>
                        <td>{fmt(pcm.precision)}</td>
                        <td>{fmt(pcm.recall)}</td>
                        <td>{fmt(pcm.f1_score)}</td>
                        <td>{pcm.support?.toLocaleString() ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Model Comparison Table */}
          {metrics.model_comparison && metrics.model_comparison.length > 0 && (
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Candidate Models Benchmark</span>
                <span className="font-mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
                  CV = 3 FOLDS
                </span>
              </div>
              <ModelComparison
                data={metrics.model_comparison}
                best={metrics.model_name ?? undefined}
              />
            </div>
          )}
        </div>

        {/* Right Column: Figure Gallery */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Generated Evaluation Visualizations</span>
            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)' }}
                onClick={handleRefresh}
              >
                RELOAD METRICS
              </button>
              <button
                className="btn btn-primary"
                style={{ padding: '4px 10px', fontSize: 'var(--fs-xs)' }}
                onClick={handleRegenerate}
                disabled={generating}
              >
                {generating ? 'REGENERATING...' : 'REGENERATE CHARTS'}
              </button>
            </div>
          </div>

          {genMessage && (
            <div style={{
              background: 'rgba(255,48,56,0.08)',
              border: '1px solid var(--c-border)',
              padding: 'var(--sp-2) var(--sp-3)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-xs)',
              color: 'var(--c-text-sec)',
              marginBottom: 'var(--sp-3)',
            }}>
              {genMessage}
            </div>
          )}

          {/* Figure Selectors */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 'var(--sp-1)',
            marginBottom: 'var(--sp-4)',
            borderBottom: '1px solid var(--c-border)',
            paddingBottom: 'var(--sp-2)',
          }}>
            {FIGURES.map(f => (
              <button
                key={f.id}
                onClick={() => setActiveFig(f.id)}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--fs-xs)',
                  padding: '4px 8px',
                  background: activeFig === f.id ? 'var(--c-red)' : 'transparent',
                  color: activeFig === f.id ? 'var(--c-white)' : 'var(--c-text-mute)',
                  border: '1px solid',
                  borderColor: activeFig === f.id ? 'var(--c-red)' : 'var(--c-border)',
                  cursor: 'pointer',
                  letterSpacing: '0.04em',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Active Figure Display */}
          <div style={{
            background: 'var(--c-bg)',
            border: '1px solid var(--c-border)',
            padding: 'var(--sp-3)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            minHeight: '340px',
            justifyContent: 'center',
          }}>
            <img
              key={`${selectedFig.id}-${cacheKey}`}
              src={`/static/figures/${selectedFig.filename}?t=${cacheKey}`}
              alt={`NID-X Evaluation: ${selectedFig.label}`}
              style={{
                maxWidth: '100%',
                maxHeight: '440px',
                objectFit: 'contain',
                display: 'block',
              }}
              onError={(e) => {
                const target = e.currentTarget;
                target.style.display = 'none';
                const parent = target.parentElement;
                if (parent && !parent.querySelector('.fig-missing')) {
                  const div = document.createElement('div');
                  div.className = 'fig-missing font-mono text-mute';
                  div.style.padding = '30px';
                  div.style.fontSize = '12px';
                  div.style.textAlign = 'center';
                  div.innerHTML = `FIGURE NOT YET GENERATED<br/><span style="font-size:10px; color:#555;">Analyze traffic or click "REFRESH CHARTS"</span>`;
                  parent.appendChild(div);
                }
              }}
            />
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: 'var(--sp-3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-xs)',
            color: 'var(--c-text-mute)',
          }}>
            <span>FIGURE: {selectedFig.filename}</span>
            <a
              href={`/api/reports/figure_${selectedFig.id}/download`}
              download={selectedFig.filename}
              className="text-red"
              style={{ textDecoration: 'underline' }}
            >
              DOWNLOAD PNG ↗
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
