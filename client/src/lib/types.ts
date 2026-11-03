export type ExecutionMode = 'load_balance' | 'ensemble';

export type WorkerState = 'idle' | 'busy' | 'offline' | 'reserved' | 'training';

export interface WorkerStatus {
  worker_id: string;
  state: WorkerState;
  available: boolean;
  last_seen_at: string | null;
  current_job_id: string | null;
}

export interface ExecutionModeAvailability {
  enabled: boolean;
  required_workers: number;
  available_workers: number;
}

export interface WorkerSnapshot {
  workers: WorkerStatus[];
  available_workers: number;
  execution_modes: Record<ExecutionMode, ExecutionModeAvailability>;
}

export interface WorkerRefresh {
  request_id: string;
  acknowledged_worker_ids: string[];
  unresponsive_worker_ids: string[];
}

export interface WorkerRefreshResponse extends WorkerSnapshot {
  refresh: WorkerRefresh;
}

export interface QueuedInference {
  status: 'queued';
  job_id: string;
  image_key: string;
  execution_mode: ExecutionMode;
  worker_ids: string[];
}

export interface WorkerInferenceResult {
  job_id: string;
  worker_id: string;
  status: 'succeeded' | 'failed';
  label: string | null;
  probabilities: Record<string, number> | null;
  model_key: string | null;
  elapsed_ms: number | null;
  completed_at: string;
  error: string | null;
}

export interface InferenceSummary {
  label: string | null;
  probabilities: Record<string, number>;
  worker_ids: string[];
  elapsed_ms?: number | null;
  model_key?: string | null;
}

export interface InferenceJob {
  job_id: string;
  status: 'queued' | 'processing' | 'succeeded' | 'failed';
  reason?: 'job_timeout' | 'worker_failed';
  missing_worker_ids?: string[];
  image_key: string;
  execution_mode: ExecutionMode;
  worker_ids: string[];
  worker_results: WorkerInferenceResult[];
  result?: InferenceSummary;
}

export interface ApiError {
  status?: string;
  reason?: string;
  message?: string;
}
