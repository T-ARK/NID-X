// NID-X API Service

import type {
  AlertsResponse,
  CSVPredictResponse,
  HealthResponse,
  HistoryResponse,
  MetricsResponse,
  ModelInfoResponse,
  PredictResponse,
  ReportsListResponse,
  SettingsResponse,
} from '../types/api';

const BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try { detail = JSON.parse(body)?.detail ?? body; } catch {}
    throw new Error(`[${res.status}] ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  modelInfo: () => request<ModelInfoResponse>('/model/info'),
  metrics: () => request<MetricsResponse>('/metrics'),
  settings: () => request<SettingsResponse>('/settings'),

  predict: (records: Record<string, unknown>[]) =>
    request<PredictResponse>('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records }),
    }),

  predictCsv: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<CSVPredictResponse>('/predict/csv', { method: 'POST', body: fd });
  },

  uploadDataset: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ status: string; message: string; path: string; size_bytes: number }>('/dataset/upload', {
      method: 'POST',
      body: fd,
    });
  },

  alerts: (page = 1, pageSize = 50, unackOnly = false, batchId?: string) => {
    let url = `/alerts?page=${page}&page_size=${pageSize}&unack_only=${unackOnly}`;
    if (batchId) url += `&batch_id=${encodeURIComponent(batchId)}`;
    return request<AlertsResponse>(url);
  },

  clearAuditLog: () =>
    request<{ message: string; status: string }>('/alerts/clear', { method: 'POST' }),

  acknowledgeAlert: (id: string) =>
    fetch(`${BASE}/alerts/${id}/acknowledge`, { method: 'POST' }),

  resolveAlert: (id: string) =>
    fetch(`${BASE}/alerts/${id}/resolve`, { method: 'POST' }),

  history: (limit = 50, offset = 0) =>
    request<HistoryResponse>(`/history?limit=${limit}&offset=${offset}`),

  reports: () => request<ReportsListResponse>('/reports'),

  downloadReport: (reportId: string) =>
    `${BASE}/reports/${encodeURIComponent(reportId)}/download`,

  fetchReportText: async (reportId: string): Promise<string> => {
    const res = await fetch(`${BASE}/reports/${encodeURIComponent(reportId)}/download`);
    if (!res.ok) throw new Error('Failed to fetch report text content');
    return res.text();
  },

  generateReport: () =>
    request<{ message: string; figures?: string[]; status: string }>('/reports/generate', { method: 'POST' }),

  updateSettings: (data: Partial<SettingsResponse>) =>
    request<SettingsResponse>('/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  trainModel: (dataset?: string) =>
    request<{ message: string; status: string }>(
      dataset ? `/train?dataset=${encodeURIComponent(dataset)}` : '/train',
      { method: 'POST' }
    ),

  trainStatus: () =>
    request<{ running: boolean; last_result: string | null; error: string | null }>('/train/status'),

  overviewStats: () =>
    request<{
      total_flows_analyzed: number;
      total_attacks_detected: number;
      total_benign_flows: number;
      total_batches: number;
      overall_attack_rate: number;
      total_alerts: number;
      unack_alerts: number;
      resolved_alerts: number;
      latest_batch: any;
      metrics: MetricsResponse | null;
    }>('/overview/stats'),

  getSampleDataset: async () => {
    const res = await fetch(`${BASE}/dataset/sample`);
    if (!res.ok) throw new Error('Sample demonstration dataset not found on server.');
    const blob = await res.blob();
    return new File([blob], 'sample_flows.csv', { type: 'text/csv' });
  },
};

