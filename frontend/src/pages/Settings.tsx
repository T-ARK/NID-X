import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { PageHeader, LoadingState, ErrorState } from '../components/Common';
import type { SettingsResponse, ModelInfoResponse } from '../types/api';

export default function Settings() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [threshold, setThreshold] = useState<number>(0.5);
  const [maxUploadMb, setMaxUploadMb] = useState<number>(50);
  const [batchSize, setBatchSize] = useState<number>(1000);
  const [classMode, setClassMode] = useState<string>('binary');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Training trigger state
  const [trainDataset, setTrainDataset] = useState<'sample' | 'raw'>('sample');
  const [trainingStatus, setTrainingStatus] = useState<{ running: boolean; last_result: string | null; error: string | null }>({
    running: false,
    last_result: null,
    error: null,
  });
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m, t] = await Promise.all([
        api.settings(),
        api.modelInfo(),
        api.trainStatus(),
      ]);
      setSettings(s);
      setModelInfo(m);
      setThreshold(s.prediction_threshold);
      setMaxUploadMb(s.max_upload_mb);
      setBatchSize(s.batch_size);
      setClassMode(s.classification_mode);
      setTrainingStatus(t);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Poll training status if running
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    if (trainingStatus.running) {
      timer = setInterval(async () => {
        try {
          const st = await api.trainStatus();
          setTrainingStatus(st);
          if (!st.running) {
            loadData();
          }
        } catch {}
      }, 3000);
    }
    return () => clearInterval(timer);
  }, [trainingStatus.running]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveStatus(null);
    try {
      const updated = await api.updateSettings({
        prediction_threshold: Number(threshold),
        max_upload_mb: Number(maxUploadMb),
        batch_size: Number(batchSize),
        classification_mode: classMode,
      });
      setSettings(updated);
      setSaveStatus('CONFIGURATION PERSISTED SUCCESSFULLY');
    } catch (e) {
      setSaveStatus(e instanceof Error ? e.message : 'Failed to persist settings');
    } finally {
      setSaving(false);
    }
  };

  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [uploadingDataset, setUploadingDataset] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const handleUploadDataset = async () => {
    if (!datasetFile) return;
    setUploadingDataset(true);
    setUploadMsg(null);
    try {
      const res = await api.uploadDataset(datasetFile);
      setUploadMsg(res.message);
    } catch (e) {
      setUploadMsg(e instanceof Error ? e.message : 'Dataset upload failed');
    } finally {
      setUploadingDataset(false);
    }
  };

  const handleTriggerTrain = async () => {
    setTriggerMsg(null);
    try {
      const path = 'data/raw/network_flows.csv';
      const res = await api.trainModel(path);
      setTriggerMsg(res.message);
      setTrainingStatus(prev => ({ ...prev, running: true }));
    } catch (e) {
      setTriggerMsg(e instanceof Error ? e.message : 'Training launch failed');
    }
  };

  if (loading) {
    return (
      <div className="page" style={{ padding: 'var(--sp-8)' }}>
        <PageHeader title="System Configuration" sub="Loading runtime parameters..." />
        <LoadingState label="Loading parameters..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page" style={{ padding: 'var(--sp-8)' }}>
        <PageHeader title="System Configuration" sub="Runtime parameters" />
        <ErrorState message={error} onRetry={loadData} />
      </div>
    );
  }

  return (
    <div className="page" style={{ padding: 'var(--sp-8)' }}>
      <PageHeader
        title="System Configuration"
        sub="Runtime inference parameters, upload safety thresholds, and model training execution engine."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
        {/* Editable Parameters Form */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Inference & Upload Thresholds</span>
            <span className="tag font-mono">DYNAMIC RUNTIME CONFIG</span>
          </div>

          <form onSubmit={handleSave}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--sp-5)' }}>
              {/* Threshold Slider */}
              <div>
                <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 6 }}>
                  PREDICTION DECISION THRESHOLD: <span style={{ color: 'var(--c-red)', fontWeight: 600 }}>{threshold}</span>
                </label>
                <input
                  type="range"
                  min="0.10"
                  max="0.90"
                  step="0.05"
                  value={threshold}
                  onChange={e => setThreshold(parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--c-red)' }}
                  aria-label="Prediction decision threshold"
                />
                <p style={{ fontSize: '11px', color: 'var(--c-text-mute)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                  Probability cutoff above which flows are labeled ATTACK (1). Default: 0.50.
                </p>
              </div>

              {/* Classification Mode */}
              <div>
                <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 6 }}>
                  CLASSIFICATION MODE
                </label>
                <select
                  className="input"
                  value={classMode}
                  onChange={e => setClassMode(e.target.value)}
                  aria-label="Classification mode"
                >
                  <option value="binary">BINARY (BENIGN vs ATTACK)</option>
                  <option value="multiclass">MULTICLASS (FAMILY-SPECIFIC)</option>
                </select>
                <p style={{ fontSize: '11px', color: 'var(--c-text-mute)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                  Multiclass requires multi-category labels in dataset.
                </p>
              </div>

              {/* Max Upload Size */}
              <div>
                <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 6 }}>
                  MAXIMUM UPLOAD FILE SIZE (MB)
                </label>
                <input
                  type="number"
                  className="input"
                  min="1"
                  max="200"
                  value={maxUploadMb}
                  onChange={e => setMaxUploadMb(parseInt(e.target.value) || 1)}
                  aria-label="Maximum upload file size"
                />
                <p style={{ fontSize: '11px', color: 'var(--c-text-mute)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                  Enforced at HTTP endpoint to prevent memory exhaustion.
                </p>
              </div>

              {/* Batch Size */}
              <div>
                <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)', marginBottom: 6 }}>
                  INFERENCE BATCH SIZE (RECORDS)
                </label>
                <input
                  type="number"
                  className="input"
                  min="50"
                  max="5000"
                  step="50"
                  value={batchSize}
                  onChange={e => setBatchSize(parseInt(e.target.value) || 50)}
                  aria-label="Inference batch size"
                />
                <p style={{ fontSize: '11px', color: 'var(--c-text-mute)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                  Batch iteration size during large CSV prediction streaming.
                </p>
              </div>
            </div>

            {saveStatus && (
              <div style={{
                marginTop: 'var(--sp-4)',
                padding: 'var(--sp-2) var(--sp-3)',
                background: saveStatus.includes('SUCCESS') ? 'rgba(255,255,255,0.06)' : 'rgba(255,48,56,0.1)',
                border: '1px solid',
                borderColor: saveStatus.includes('SUCCESS') ? 'var(--c-border-str)' : 'var(--c-red)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-xs)',
                color: saveStatus.includes('SUCCESS') ? 'var(--c-text)' : 'var(--c-red)',
              }}>
                {saveStatus}
              </div>
            )}

            <div style={{ marginTop: 'var(--sp-5)' }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'PERSISTING...' : 'SAVE CONFIGURATION'}
              </button>
            </div>
          </form>
        </div>

        {/* Model Training Trigger Panel */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Model Retraining Engine</span>
            <span className="tag font-mono">
              {trainingStatus.running ? 'EXECUTION IN PROGRESS' : 'READY'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
            <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--c-text-sec)', maxWidth: 640, lineHeight: 1.7 }}>
              Re-executes the candidate training pipeline across Logistic Regression, Decision Tree, Random Forest, and HistGradientBoosting with cross-validation and automatic F1 model selection.
            </p>

            <div style={{
              background: 'rgba(255, 48, 56, 0.05)',
              border: '1px solid var(--c-border)',
              padding: 'var(--sp-3)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-xs)',
              color: 'var(--c-text-sec)',
            }}>
              <strong style={{ color: 'var(--c-red)' }}>COMPLIANCE POLICY:</strong> The system solely trains and analyzes user-uploaded datasets. Synthetic or artificial data generation is disabled.
            </div>

            {/* User Dataset Ingestion for Training */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
              <label style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text-mute)' }}>
                UPLOAD USER TRAINING DATASET (CSV):
              </label>
              <div style={{ display: 'flex', gap: 'var(--sp-3)', alignItems: 'center' }}>
                <input
                  type="file"
                  accept=".csv"
                  className="input"
                  style={{ maxWidth: 350, padding: '6px' }}
                  onChange={e => setDatasetFile(e.target.files?.[0] ?? null)}
                />
                <button
                  className="btn btn-secondary"
                  onClick={handleUploadDataset}
                  disabled={!datasetFile || uploadingDataset}
                >
                  {uploadingDataset ? 'UPLOADING...' : 'SAVE DATASET'}
                </button>
              </div>
              {uploadMsg && (
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)', color: 'var(--c-text)' }}>
                  {uploadMsg}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 'var(--sp-3)', alignItems: 'center', marginTop: 'var(--sp-2)' }}>
              <button
                className="btn btn-primary"
                onClick={handleTriggerTrain}
                disabled={trainingStatus.running}
              >
                {trainingStatus.running ? 'TRAINING IN PROGRESS...' : 'START TRAINING PIPELINE'}
              </button>
            </div>

            {triggerMsg && (
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-xs)',
                color: 'var(--c-text)',
                padding: 'var(--sp-2) var(--sp-3)',
                background: 'rgba(255,48,56,0.08)',
                border: '1px solid var(--c-border)',
              }}>
                {triggerMsg}
              </div>
            )}

            {trainingStatus.running && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--sp-3)',
                padding: 'var(--sp-3)',
                background: 'var(--c-bg)',
                border: '1px solid var(--c-red)',
              }}>
                <span style={{ animation: 'spin 1.5s linear infinite', color: 'var(--c-red)' }}>◌</span>
                <span className="font-mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--c-text)' }}>
                  Training candidate models (Logistic Regression, Decision Tree, Random Forest, HistGradientBoosting)...
                </span>
              </div>
            )}

            {trainingStatus.last_result && !trainingStatus.running && (
              <div className="font-mono text-mute" style={{ fontSize: 'var(--fs-xs)' }}>
                LAST TRAINING RESULT: <span style={{ color: 'var(--c-text)' }}>{trainingStatus.last_result}</span>
              </div>
            )}

            {trainingStatus.error && (
              <div className="font-mono text-red" style={{ fontSize: 'var(--fs-xs)' }}>
                ERROR: {trainingStatus.error}
              </div>
            )}
          </div>
        </div>

        {/* Read-Only System Telemetry */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">System & Environment Telemetry</span>
            <span className="tag font-mono">HOST STATUS</span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 'var(--sp-4)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-xs)',
          }}>
            <div>
              <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>TARGET LABEL COLUMN</div>
              <div style={{ color: 'var(--c-text)' }}>{settings?.label_column}</div>
            </div>
            <div>
              <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>DATASET FILENAME</div>
              <div style={{ color: 'var(--c-text)' }}>{settings?.dataset_filename}</div>
            </div>
            <div>
              <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>RANDOM SEED (DETERMINISM)</div>
              <div style={{ color: 'var(--c-text)' }}>{settings?.random_seed}</div>
            </div>
            <div>
              <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>MODEL PERSISTENCE PATH</div>
              <div style={{ color: 'var(--c-text-sec)' }}>models/intrusion_model.joblib</div>
            </div>
            <div>
              <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>FEATURE COUNT</div>
              <div style={{ color: 'var(--c-text)' }}>{modelInfo?.feature_count ?? 'N/A'}</div>
            </div>
            <div>
              <div style={{ color: 'var(--c-text-mute)', marginBottom: 4 }}>AUDIT DATABASE</div>
              <div style={{ color: 'var(--c-text)' }}>SQLite (WAL mode)</div>
            </div>
          </div>
        </div>

        {/* CLI Reference Panel */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">CLI Execution Cheatsheet</span>
            <span className="tag font-mono">BASH / LINUX</span>
          </div>
          <div style={{
            background: 'var(--c-bg)',
            border: '1px solid var(--c-border)',
            padding: 'var(--sp-4)',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-xs)',
            lineHeight: 2,
            color: 'var(--c-text-sec)',
          }}>
            <div><span style={{ color: 'var(--c-text-mute)' }}># Inspect user dataset schema:</span></div>
            <div><code style={{ color: 'var(--c-text)' }}>python scripts/inspect_dataset.py data/raw/network_flows.csv</code></div>
            <div style={{ marginTop: 8 }}><span style={{ color: 'var(--c-text-mute)' }}># Train candidate models on user dataset & select best by F1 score:</span></div>
            <div><code style={{ color: 'var(--c-text)' }}>python scripts/train_model.py --dataset data/raw/network_flows.csv --rows 50000</code></div>
            <div style={{ marginTop: 8 }}><span style={{ color: 'var(--c-text-mute)' }}># Evaluate model on held-out split of user dataset and render charts:</span></div>
            <div><code style={{ color: 'var(--c-text)' }}>python scripts/evaluate_model.py --dataset data/raw/network_flows.csv</code></div>
            <div style={{ marginTop: 8 }}><span style={{ color: 'var(--c-text-mute)' }}># Run full pytest test suite:</span></div>
            <div><code style={{ color: 'var(--c-text)' }}>pytest backend/tests/test_nidx.py -v</code></div>
          </div>
        </div>
      </div>
    </div>
  );
}
