import React, { useCallback, useEffect, useState } from 'react';
import { useApiData } from '../hooks/useApi';
import { api } from '../services/api';
import { PageHeader, MetricPanel, EmptyState, LoadingState, ErrorState } from '../components/Common';
import { ConfusionMatrix } from '../components/ConfusionMatrix';
import { ModelComparison } from '../components/ModelComparison';
import type { AnalyticalReport, HistoryResponse, MetricsResponse, ModelInfoResponse, PerClassMetrics, ReportEntry } from '../types/api';

function fmt(v: number | null | undefined, isPercent = true): string {
  if (v == null) return 'N/A';
  return isPercent ? `${(v * 100).toFixed(2)}%` : String(v);
}

function perClassFromConfusionMatrix(matrix: number[][] | null | undefined): Record<string, PerClassMetrics> | null {
  if (!matrix?.length || matrix.some(row => row.length !== matrix.length)) return null;
  return Object.fromEntries(matrix.map((row, classIndex) => {
    const truePositive = row[classIndex];
    const falsePositive = matrix.reduce((sum, otherRow) => sum + otherRow[classIndex], 0) - truePositive;
    const falseNegative = row.reduce((sum, value) => sum + value, 0) - truePositive;
    const precision = truePositive + falsePositive ? truePositive / (truePositive + falsePositive) : 0;
    const recall = truePositive + falseNegative ? truePositive / (truePositive + falseNegative) : 0;
    return [String(classIndex), {
      precision,
      recall,
      f1_score: precision + recall ? (2 * precision * recall) / (precision + recall) : 0,
      support: row.reduce((sum, value) => sum + value, 0),
    }];
  }));
}

function parseAnalyticalReport(content: string): AnalyticalReport {
  const validJson = content.replace(/(^|[:,\[\]\s])(-?Infinity|NaN)(?=[,\]\}\s])/g, '$1null');
  return JSON.parse(validJson) as AnalyticalReport;
}

export default function ModelPerformance() {
  const { data: metrics, loading: loadingMetrics, error: errMetrics, refetch: refetchMetrics } =
    useApiData<MetricsResponse>(() => api.metrics(), []);
  const { data: modelInfo, loading: loadingInfo } =
    useApiData<ModelInfoResponse>(() => api.modelInfo(), []);
  const { data: telemetry, error: telemetryError, refetch: refetchTelemetry } =
    useApiData(() => api.overviewStats(), []);
  const { data: history, error: historyError, refetch: refetchHistory } =
    useApiData<HistoryResponse>(() => api.history(8), []);

  const [figures, setFigures] = useState<ReportEntry[]>([]);
  const [trafficEvaluation, setTrafficEvaluation] = useState<AnalyticalReport | null>(null);
  const [trafficEvaluationError, setTrafficEvaluationError] = useState<string | null>(null);
  const [activeFig, setActiveFig] = useState(0);
  const [figureError, setFigureError] = useState<string | null>(null);
  const [cacheKey, setCacheKey] = useState<number>(Date.now());
  const [generating, setGenerating] = useState(false);
  const [genMessage, setGenMessage] = useState<string | null>(null);

  const loadFigures = useCallback(async () => {
    setFigureError(null);
    try {
      const response = await api.reports();
      const reports = response.reports.filter(report => report.available);
      setFigures(reports.filter(report =>
        report.available && report.type === 'png' && report.report_id.startsWith('figure_')
      ));
      setCacheKey(Date.now());
      const latestEvaluationReport = reports
        .filter(report => report.type === 'json'
          && report.report_id.startsWith('analytical_report_')
          && report.report_id.endsWith('_json'))
        .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))[0];
      if (latestEvaluationReport) {
        try {
          const reportText = await api.fetchReportText(latestEvaluationReport.report_id);
          setTrafficEvaluation(parseAnalyticalReport(reportText));
          setTrafficEvaluationError(null);
        } catch (e) {
          setTrafficEvaluation(null);
          setTrafficEvaluationError(e instanceof Error ? e.message : 'Failed to load uploaded traffic evaluation');
        }
      } else {
        setTrafficEvaluation(null);
        setTrafficEvaluationError(null);
      }
    } catch (e) {
      setFigureError(e instanceof Error ? e.message : 'Failed to load report images');
    }
  }, []);

  useEffect(() => {
    loadFigures();
  }, [loadFigures]);

  useEffect(() => {
    if (figures.length < 2) return;
    const timer = window.setInterval(() => {
      setActiveFig(current => (current + 1) % figures.length);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [figures.length]);

  useEffect(() => {
    setActiveFig(current => Math.min(current, Math.max(0, figures.length - 1)));
  }, [figures.length]);

  const handleRefresh = async () => {
    setCacheKey(Date.now());
    refetchMetrics();
    await Promise.all([loadFigures(), refetchTelemetry(), refetchHistory()]);
  };

  const handleRegenerate = async () => {
    setGenerating(true);
    setGenMessage(null);
    try {
      const res = await api.generateReport();
      setGenMessage(res.message);
      setCacheKey(Date.now());
      refetchMetrics();
      await loadFigures();
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

  const sampleMetrics = !!metrics?.is_sample_data;
  const uploadedMetrics = trafficEvaluation?.evaluation_metrics;
  const hasUploadedEvaluation = !!uploadedMetrics?.has_ground_truth;
  const hasEvaluationMetrics = hasUploadedEvaluation || (!!metrics?.available && !sampleMetrics);
  const classMetrics = hasUploadedEvaluation
    ? perClassFromConfusionMatrix(uploadedMetrics?.confusion_matrix)
    : metrics?.per_class;

  const selectedFig = figures[activeFig];
  const classNames = modelInfo?.target_mapping
    ? Object.fromEntries(Object.entries(modelInfo.target_mapping).map(([name, value]) => [String(value), name]))
    : {};
  const getHistoryFilename = (summary: string | null) => {
    if (!summary) return 'Uploaded dataset';
    try {
      const parsed = JSON.parse(summary) as { filename?: string };
      return parsed.filename ?? 'Uploaded dataset';
    } catch {
      return summary;
    }
  };
  const evaluationValues = {
    accuracy: uploadedMetrics?.accuracy ?? metrics?.accuracy,
    precision: uploadedMetrics?.precision ?? metrics?.precision,
    recall: uploadedMetrics?.recall ?? metrics?.recall,
    f1_score: uploadedMetrics?.f1_score ?? metrics?.f1_score,
    false_positive_rate: uploadedMetrics?.false_positive_rate ?? metrics?.false_positive_rate,
    false_negative_rate: uploadedMetrics?.false_negative_rate ?? metrics?.false_negative_rate,
    roc_auc: uploadedMetrics?.roc_auc ?? metrics?.roc_auc,
    pr_auc: uploadedMetrics?.pr_auc ?? metrics?.pr_auc,
    confusion_matrix: uploadedMetrics?.confusion_matrix ?? metrics?.confusion_matrix,
  };

  return (
    <div className="page" style={{ padding: 'var(--sp-8)' }}>
      <PageHeader
        title="Model Performance"
        sub="Held-out validation metrics, discrimination curves, and candidate model benchmark comparison."
      />

      {!hasEvaluationMetrics && !sampleMetrics && (
        <EmptyState
          title="NO MODEL EVALUATION FOUND"
          desc="Train the candidate models on your network dataset to generate evaluation metrics. Any available user-data report images remain accessible below."
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
      )}

      <section className="panel" style={{ marginBottom: 'var(--sp-6)' }} aria-label="Live ingested traffic telemetry">
        <div className="panel-header">
          <span className="panel-title">LIVE INGESTED TRAFFIC TELEMETRY</span>
          <span className="tag font-mono">ALL RECORDED BATCHES</span>
        </div>
        <div className="grid-4" style={{ marginBottom: 'var(--sp-5)' }}>
          <MetricPanel
            label="Flows Ingested"
            value={telemetry?.total_flows_analyzed.toLocaleString() ?? '—'}
            sub="Across recorded traffic batches"
          />
          <MetricPanel
            label="Threats Detected"
            value={telemetry?.total_attacks_detected.toLocaleString() ?? '—'}
            sub="Classified as malicious"
            red={!!telemetry?.total_attacks_detected}
          />
          <MetricPanel
            label="Benign Flows"
            value={telemetry?.total_benign_flows.toLocaleString() ?? '—'}
            sub="Classified as benign"
          />
          <MetricPanel
            label="Ingestion Batches"
            value={telemetry?.total_batches.toLocaleString() ?? '—'}
            sub="CSV analyses recorded"
          />
        </div>
        {telemetryError && (
          <p role="alert" style={{ color: 'var(--c-red)', fontSize: 'var(--fs-xs)' }}>
            Could not load traffic totals: {telemetryError}
          </p>
        )}
        {historyError ? (
          <ErrorState message={`Could not load recent traffic history: ${historyError}`} onRetry={refetchHistory} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Source</th>
                  <th>Analyzed</th>
                  <th>Threats</th>
                  <th>Benign</th>
                  <th>Batch</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {(history?.history ?? []).map(batch => (
                  <tr key={batch.id}>
                    <td title={getHistoryFilename(batch.summary)}>{getHistoryFilename(batch.summary)}</td>
                    <td>{batch.source_type.replace(/_/g, ' ')}</td>
                    <td>{batch.record_count.toLocaleString()}</td>
                    <td>{batch.attack_count.toLocaleString()}</td>
                    <td>{batch.benign_count.toLocaleString()}</td>
                    <td>{batch.batch_id?.slice(0, 8) ?? '—'}</td>
                    <td>{new Date(batch.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
                {history && history.history.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', color: 'var(--c-text-mute)' }}>
                      No traffic has been ingested yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {sampleMetrics && !hasUploadedEvaluation && (
        <div className="panel" style={{ marginBottom: 'var(--sp-6)' }}>
          <div className="panel-header">
            <span className="panel-title">USER-DATA EVALUATION REQUIRED</span>
            <span className="tag font-mono">SAMPLE BENCHMARKS HIDDEN</span>
          </div>
          <p style={{ color: 'var(--c-text-mute)', fontSize: 'var(--fs-sm)', margin: 0 }}>
            The active model was trained on bundled sample data, so its training benchmarks stay hidden.
            Labeled user-uploaded traffic evaluations appear separately below.
          </p>
        </div>
      )}

      {hasEvaluationMetrics && metrics && (
        <>
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

      <section className="panel" style={{ marginBottom: 'var(--sp-6)' }} aria-label="Evaluation metrics">
        <div className="panel-header">
          <span className="panel-title">EVALUATION METRICS</span>
          <span className="tag font-mono">
            {hasUploadedEvaluation && trafficEvaluation
              ? `USER DATA: ${trafficEvaluation.filename}`
              : metrics.evaluated_at
                ? `EVALUATED: ${new Date(metrics.evaluated_at).toLocaleDateString()}`
                : 'HELD-OUT RESULTS'}
          </span>
        </div>
        <div className="grid-4">
          <MetricPanel label="Accuracy" value={fmt(evaluationValues.accuracy)} sub="Overall correctness" />
          <MetricPanel label="Recall (Sensitivity)" value={fmt(evaluationValues.recall)} sub="True positive rate" />
          <MetricPanel label="Precision" value={fmt(evaluationValues.precision)} sub="Positive predictive value" />
          <MetricPanel label="F1-Score" value={fmt(evaluationValues.f1_score)} sub="Harmonic mean" />
          <MetricPanel label="False Positive Rate" value={fmt(evaluationValues.false_positive_rate)} sub="Benign flows flagged as attack" red />
          <MetricPanel label="False Negative Rate" value={fmt(evaluationValues.false_negative_rate)} sub="Attacks missed" />
          <MetricPanel label="ROC-AUC" value={fmt(evaluationValues.roc_auc, false)} sub="Area under ROC curve" />
          <MetricPanel label="PR-AUC (AP)" value={fmt(evaluationValues.pr_auc, false)} sub="Average precision" />
        </div>
        {trafficEvaluationError && (
          <p role="alert" style={{ color: 'var(--c-red)', fontSize: 'var(--fs-xs)', margin: 'var(--sp-3) 0 0' }}>
            Could not load uploaded-data evaluation: {trafficEvaluationError}
          </p>
        )}
      </section>
        </>
      )}
      {!hasEvaluationMetrics && (
        <section className="panel" style={{ marginBottom: 'var(--sp-6)' }} aria-label="Evaluation metrics">
          <div className="panel-header">
            <span className="panel-title">EVALUATION METRICS</span>
            <span className="tag font-mono">USER-DATA RESULTS REQUIRED</span>
          </div>
          <p style={{ color: 'var(--c-text-mute)', fontSize: 'var(--fs-sm)', margin: 0 }}>
            Evaluation metrics are unavailable. Sample-trained evaluation results remain hidden; analyze a labeled
            user dataset to display accuracy, precision, recall, F1, and AUC scores here.
          </p>
          {trafficEvaluationError && (
            <p role="alert" style={{ color: 'var(--c-red)', fontSize: 'var(--fs-xs)', margin: 'var(--sp-3) 0 0' }}>
              Could not load uploaded-data evaluation: {trafficEvaluationError}
            </p>
          )}
        </section>
      )}

      <section className="panel" style={{ marginBottom: 'var(--sp-6)' }} aria-label="Model performance benchmark">
        <div className="panel-header">
          <span className="panel-title">MODEL PERFORMANCE BENCHMARK</span>
          <span className="tag font-mono">CROSS-VALIDATION & HELD-OUT RESULTS</span>
        </div>
        {hasEvaluationMetrics && metrics?.model_comparison?.length ? (
          <ModelComparison
            data={metrics.model_comparison}
            best={metrics.model_name ?? undefined}
          />
        ) : (
          <p style={{ color: 'var(--c-text-mute)', fontSize: 'var(--fs-xs)', margin: 0 }}>
            {sampleMetrics
              ? 'Benchmark values from the bundled sample model are hidden. Train and evaluate with your own dataset to compare candidates.'
              : 'No candidate benchmark results are available. Train and evaluate a model using your own dataset to populate this table.'}
          </p>
        )}
      </section>

      {/* Two Column Section: Left = Tables, Right = Figure Viewer */}
      <div
        className="grid-2"
        style={{
          alignItems: 'start',
          marginBottom: 'var(--sp-6)',
        }}
      >
        {/* Left Column: Confusion Matrix & Class Breakdown */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
          {/* Confusion Matrix Panel */}
          {hasEvaluationMetrics && metrics && (
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Confusion Matrix</span>
                <span className="font-mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
                  N = {(trafficEvaluation?.total_records ?? metrics.n_test)?.toLocaleString() ?? '—'}
                </span>
              </div>
              {evaluationValues.confusion_matrix ? (
                <ConfusionMatrix
                  matrix={evaluationValues.confusion_matrix}
                  labels={evaluationValues.confusion_matrix.map((_, index) => classNames[String(index)] ?? `CLASS ${index}`)}
                />
              ) : (
                <p style={{ color: 'var(--c-text-mute)', fontSize: 'var(--fs-xs)' }}>Matrix unavailable.</p>
              )}
            </div>
          )}

          {/* Per-Classification Mode Table */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Per Classification Mode</span>
              <span className="tag font-mono">{modelInfo?.classification_mode ?? 'MODE N/A'}</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Mode</th>
                    <th>Class</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1-Score</th>
                    <th>Support</th>
                  </tr>
                </thead>
                <tbody>
                  {hasEvaluationMetrics && classMetrics ? (
                    Object.entries(classMetrics).map(([className, pcm]) => (
                      <tr key={className}>
                        <td>{modelInfo?.classification_mode ?? 'N/A'}</td>
                        <td style={{ fontWeight: 600, color: className === '1' || className.toLowerCase().includes('attack') ? 'var(--c-red)' : 'var(--c-text)' }}>
                          {classNames[className] ? `${classNames[className]} (${className})` : className}
                        </td>
                        <td>{fmt(pcm.precision)}</td>
                        <td>{fmt(pcm.recall)}</td>
                        <td>{fmt(pcm.f1_score)}</td>
                        <td>{pcm.support?.toLocaleString() ?? '—'}</td>
                      </tr>
                    ))
                  ) : modelInfo?.target_mapping && Object.keys(modelInfo.target_mapping).length ? (
                    Object.entries(modelInfo.target_mapping).map(([className, classId]) => (
                      <tr key={classId}>
                        <td>{modelInfo.classification_mode ?? 'N/A'}</td>
                        <td>{className} ({classId})</td>
                        <td>N/A</td>
                        <td>N/A</td>
                        <td>N/A</td>
                        <td>N/A</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', color: 'var(--c-text-mute)' }}>
                        No class mapping is available.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {!hasEvaluationMetrics && (
              <p style={{ color: 'var(--c-text-mute)', fontSize: 'var(--fs-xs)', margin: 'var(--sp-3) 0 0' }}>
                Per-class scores are hidden until evaluation on labeled user data is available.
              </p>
            )}
          </div>
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
                disabled={generating || sampleMetrics}
                title={sampleMetrics ? 'Train a model on your own dataset to generate evaluation visualizations' : undefined}
              >
                {generating ? 'REGENERATING...' : sampleMetrics ? 'TRAIN A USER MODEL FIRST' : 'REGENERATE CHARTS'}
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
            {figureError ? (
              <ErrorState message={figureError} onRetry={loadFigures} />
            ) : selectedFig ? (
              <img
                key={`${selectedFig.report_id}-${cacheKey}`}
                src={`${api.downloadReport(selectedFig.report_id)}?t=${cacheKey}`}
                alt={selectedFig.name}
                style={{ maxWidth: '100%', maxHeight: '440px', objectFit: 'contain', display: 'block' }}
              />
            ) : (
              <p style={{ color: 'var(--c-text-mute)', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', textAlign: 'center' }}>
                {sampleMetrics
                  ? 'No user-data report images available. Analyze your own dataset to generate report images.'
                  : 'No report images have been generated yet.'}
              </p>
            )}
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
            <span>
              {selectedFig ? `${selectedFig.name} (${activeFig + 1}/${figures.length})` : 'NO REPORT IMAGE'}
            </span>
            {selectedFig && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => setActiveFig(current => (current - 1 + figures.length) % figures.length)}
                  disabled={figures.length < 2}
                  aria-label="Previous report image"
                >
                  PREVIOUS
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setActiveFig(current => (current + 1) % figures.length)}
                  disabled={figures.length < 2}
                  aria-label="Next report image"
                >
                  NEXT
                </button>
                <a
                  href={api.downloadReport(selectedFig.report_id)}
                  download
                  className="text-red"
                  style={{ textDecoration: 'underline' }}
                >
                  DOWNLOAD PNG ↗
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
