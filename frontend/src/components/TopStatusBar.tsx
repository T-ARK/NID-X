import React from 'react';
import { useHealth } from '../hooks/useApi';
import './TopStatusBar.css';

function StatusDot({ connected, modelLoaded }: { connected: boolean; modelLoaded: boolean }) {
  return (
    <span
      className={`status-dot ${connected ? (modelLoaded ? 'status-ready' : 'status-warn') : 'status-error'}`}
      aria-label={connected ? (modelLoaded ? 'System ready' : 'No model') : 'Backend offline'}
    />
  );
}

export function TopStatusBar() {
  const { data, loading, error } = useHealth();

  const connected = !loading && !error && !!data;
  const modelLoaded = connected && (data?.model_loaded ?? false);

  return (
    <header className="top-status-bar" role="banner">
      <div className="tsb-left">
        <StatusDot connected={connected} modelLoaded={modelLoaded} />
        <span className="tsb-name font-mono uppercase letter-wide">NID-X</span>
        <span className="tsb-sep" aria-hidden />
        <span className="tsb-env font-mono text-mute">
          {data?.env ?? 'OFFLINE'}
        </span>
      </div>

      <div className="tsb-center font-mono text-mute">
        {loading && 'CONNECTING...'}
        {error && <span className="text-red">BACKEND UNREACHABLE</span>}
        {connected && !modelLoaded && <span className="text-sec">NO MODEL — RUN TRAIN_MODEL.PY</span>}
        {connected && modelLoaded && (
          <span>MODEL <span className="text-red">{data?.model_version ?? 'LOADED'}</span></span>
        )}
      </div>

      <div className="tsb-right font-mono text-mute">
        <span>v{data?.app_version ?? '—'}</span>
      </div>
    </header>
  );
}
