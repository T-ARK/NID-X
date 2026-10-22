// NID-X API Types

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model_version: string | null;
  app_version: string;
  env: string;
}

export interface ModelInfoResponse {
  model_name: string | null;
  model_version: string | null;
  training_timestamp: string | null;
  dataset_id: string | null;
  classification_mode: string | null;
  feature_count: number | null;
  feature_names: string[] | null;
  target_mapping: Record<string, number> | null;
  evaluation_split: string | null;
  available: boolean;
}

export interface PerClassMetrics {
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  support: number | null;
}

export interface MetricsResponse {
  available: boolean;
  /** True when the metrics came from the bundled demo model trained on sample data */
  is_sample_data?: boolean;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  false_positive_rate: number | null;
  false_negative_rate: number | null;
  roc_auc: number | null;
  pr_auc: number | null;
  confusion_matrix: number[][] | null;
  per_class: Record<string, PerClassMetrics> | null;
  training_duration_s: number | null;
  inference_duration_ms: number | null;
  n_train: number | null;
  n_test: number | null;
  model_name: string | null;
  evaluated_at: string | null;
  model_comparison?: {
    model: string;
    cv_f1: number;
    val_accuracy?: number;
    val_precision: number;
    val_recall: number;
    val_f1: number;
    val_fpr?: number;
    train_duration_s?: number;
  }[] | null;
}

export interface PredictionResult {
  row_index: number;
  predicted_label: string;
  predicted_class: number;
  probability: number | null;
  model_version: string | null;
  timestamp: string;
  warning: string | null;
}

export interface PredictResponse {
  predictions: PredictionResult[];
  attack_count: number;
  benign_count: number;
  total: number;
  model_version: string | null;
  batch_id: string;
}

export interface TrafficChartItem {
  id: string;
  title: string;
  url: string;
  filename: string;
}

export interface TrafficEvaluation {
  has_ground_truth: boolean;
  label_column: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc?: number | null;
  pr_auc?: number | null;
  false_positive_rate: number;
  false_negative_rate: number;
  confusion_matrix: number[][];
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
}

export interface AnalyticalReport {
  batch_id: string;
  batch_short: string;
  filename: string;
  timestamp: string;
  model_version: string;
  overall_threat_level: string;
  total_records: number;
  attack_count: number;
  benign_count: number;
  attack_rate: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  traffic_stats?: Record<string, any>;
  tcp_flags?: Record<string, number>;
  evaluation_metrics?: TrafficEvaluation | null;
  top_suspicious_flows?: any[];
  recommendations: string[];
  markdown_report_path?: string;
  json_report_path?: string;
}

export interface CSVPredictResponse {
  batch_id: string;
  total_records: number;
  attack_count: number;
  benign_count: number;
  attack_rate: number;
  predictions: PredictionResult[];
  warnings: string[];
  model_version: string | null;
  overall_threat_level?: string;
  inference_ms?: number;
  evaluation?: TrafficEvaluation | null;
  charts?: TrafficChartItem[];
  chart_data?: {
    threat_distribution?: { benign: number; attack: number; attack_rate: number };
    severity_breakdown?: { critical: number; high: number; medium: number; low: number };
    risk_histogram?: { bins: number[]; counts: number[] };
    tcp_flags?: Record<string, number>;
  };
  analytical_report?: AnalyticalReport;
  report_id?: string;
}

export interface AlertRecord {
  id: string;
  timestamp: string;
  predicted_class: string;
  score: number | null;
  model_ver: string | null;
  source_type: string | null;
  batch_id: string | null;
  flow_meta: string | null;
  severity: string;
  acknowledged: number;
  resolved: number;
}

export interface AlertsResponse {
  alerts: AlertRecord[];
  total: number;
  page: number;
  page_size: number;
  summary?: {
    total_alerts: number;
    unack_alerts: number;
    resolved_alerts: number;
    attack_alerts: number;
  };
}

export interface HistoryRecord {
  id: string;
  timestamp: string;
  source_type: string;
  batch_id: string | null;
  model_ver: string | null;
  record_count: number;
  attack_count: number;
  benign_count: number;
  summary: string | null;
}

export interface HistoryResponse {
  history: HistoryRecord[];
  total: number;
}

export interface ReportEntry {
  report_id: string;
  name: string;
  type: string;
  size_bytes: number;
  created_at: string | null;
  available: boolean;
}

export interface ReportsListResponse {
  reports: ReportEntry[];
}

export interface SettingsResponse {
  classification_mode: string;
  prediction_threshold: number;
  max_upload_mb: number;
  max_upload_rows: number;
  batch_size: number;
  random_seed: number;
  label_column: string;
  dataset_filename: string;
  model_available: boolean;
}
