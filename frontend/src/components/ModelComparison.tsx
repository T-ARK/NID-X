import React from 'react';

interface Props {
  data: { model: string; val_f1: number; val_precision: number; val_recall: number; cv_f1: number }[];
  best?: string;
}

export function ModelComparison({ data, best }: Props) {
  if (!data || data.length === 0) return null;
  return (
    <div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>CV F1</th>
              <th>Val F1</th>
              <th>Val Precision</th>
              <th>Val Recall</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.model}>
                <td style={{ color: row.model === best ? 'var(--c-red)' : 'var(--c-text)' }}>
                  {row.model === best && <span style={{ color: 'var(--c-red)', marginRight: 6 }}>★</span>}
                  {row.model}
                </td>
                <td>{(row.cv_f1 * 100).toFixed(2)}%</td>
                <td>{(row.val_f1 * 100).toFixed(2)}%</td>
                <td>{(row.val_precision * 100).toFixed(2)}%</td>
                <td>{(row.val_recall * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
