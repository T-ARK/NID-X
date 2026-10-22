import React from 'react';

export function EmptyState({ title, desc, action }: {
  title: string; desc?: string; action?: React.ReactNode;
}) {
  return (
    <div className="state-box" role="status">
      <div className="state-icon">◫</div>
      <div className="state-title">{title}</div>
      {desc && <p className="state-desc">{desc}</p>}
      {action}
    </div>
  );
}

export function LoadingState({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="state-box" role="status" aria-live="polite">
      <div className="state-icon" aria-hidden style={{ animation: 'spin 1.5s linear infinite' }}>◌</div>
      <div className="state-title font-mono">{label}</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-box" role="alert">
      <div className="state-icon text-red">⚠</div>
      <div className="state-title text-red">Error</div>
      <p className="state-desc">{message}</p>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry}>Retry</button>
      )}
    </div>
  );
}

export function MetricPanel({
  label, value, sub, red = false
}: {
  label: string; value: string | number | null | undefined; sub?: string; red?: boolean;
}) {
  const display = value === null || value === undefined ? 'N/A' : String(value);
  const isNA = display === 'N/A';
  return (
    <div className="metric-panel">
      <div className="metric-label">{label}</div>
      <div className={`metric-value${isNA ? ' na' : ''}${red && !isNA ? ' red' : ''}`}>
        {display}
      </div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export function PageHeader({ title, sub }: { title: React.ReactNode; sub?: string }) {
  return (
    <div style={{ marginBottom: 'var(--sp-6)' }}>
      <h1 className="page-title">{title}</h1>
      {sub && <p className="page-sub">{sub}</p>}
    </div>
  );
}
