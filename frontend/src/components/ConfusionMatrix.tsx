import React from 'react';

interface Props {
  matrix: number[][];
  labels?: string[];
}

export function ConfusionMatrix({ matrix, labels = ['BENIGN', 'ATTACK'] }: Props) {
  if (!matrix || matrix.length === 0) return null;

  const total = matrix.flat().reduce((a, b) => a + b, 0);

  return (
    <div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-xs)' }}>
          <thead>
            <tr>
              <th style={{ padding: '8px 12px', color: 'var(--c-text-mute)', borderBottom: '1px solid var(--c-border)', textAlign: 'left' }}>
                Actual ↓ / Pred →
              </th>
              {labels.map((l, i) => (
                <th key={i} style={{ padding: '8px 12px', color: 'var(--c-text-sec)', borderBottom: '1px solid var(--c-border)', textAlign: 'center', textTransform: 'uppercase' }}>
                  {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, ri) => (
              <tr key={ri}>
                <td style={{ padding: '8px 12px', color: 'var(--c-text-sec)', borderBottom: '1px solid var(--c-border)', textTransform: 'uppercase', fontWeight: 600 }}>
                  {labels[ri] ?? `Class ${ri}`}
                </td>
                {row.map((val, ci) => {
                  const isDiag = ri === ci;
                  const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                  return (
                    <td key={ci} style={{
                      padding: '8px 12px',
                      textAlign: 'center',
                      borderBottom: '1px solid var(--c-border)',
                      background: isDiag ? 'rgba(255,48,56,0.10)' : 'transparent',
                      color: isDiag ? 'var(--c-text)' : 'var(--c-text-sec)',
                      fontWeight: isDiag ? 700 : 400,
                    }}>
                      {val.toLocaleString()}
                      <span style={{ color: 'var(--c-text-mute)', fontSize: '10px', display: 'block' }}>
                        {pct}%
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
