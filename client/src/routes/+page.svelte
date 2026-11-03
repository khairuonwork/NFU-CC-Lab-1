<script lang="ts">
  import { onMount } from 'svelte';

  import DistributedFlow from '../lib/components/distributed-flow.svelte';

  import type {
    ApiError,
    ExecutionMode,
    InferenceJob,
    QueuedInference,
    WorkerRefresh,
    WorkerRefreshResponse,
    WorkerSnapshot,
  } from '#lib/types';

  type SubmissionState = 'idle' | 'uploading' | 'queued' | 'processing' | 'succeeded' | 'failed';

  const pollIntervalMs = 1_000;
  const workerRefreshIntervalMs = 8_000;

  let workerSnapshot = $state<WorkerSnapshot | null>(null);
  let workerError = $state('');
  let workerLoading = $state(true);
  let selectedMode = $state<ExecutionMode>('load_balance');
  let selectedFile = $state<File | null>(null);
  let selectedPreviewUrl = $state<string | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);
  let queuedInference = $state<QueuedInference | null>(null);
  let currentJob = $state<InferenceJob | null>(null);
  let submissionState = $state<SubmissionState>('idle');
  let submissionError = $state('');
  let pollRevision = 0;
  let heartbeatRevision = $state(0);
  let connectionRetrying = $state(false);
  let workerRefreshResult = $state<WorkerRefresh | null>(null);

  let selectedModeAvailability = $derived(workerSnapshot?.execution_modes[selectedMode] ?? null);
  let canSubmit = $derived(
    Boolean(selectedFile && selectedModeAvailability?.enabled && submissionState === 'idle'),
  );

  class ApiRequestError extends Error {
    readonly body: ApiError;

    constructor(message: string, body: ApiError) {
      super(message);
      this.body = body;
    }
  }

  onMount(() => {
    void refreshWorkers();
    const timer = window.setInterval(() => void refreshWorkers(), workerRefreshIntervalMs);

    return () => {
      window.clearInterval(timer);
      pollRevision += 1;
      clearSelectedPreview();
    };
  });

  async function refreshWorkers(): Promise<void> {
    try {
      const response = await fetch('/api/inference/workers', {
        headers: { accept: 'application/json' },
        cache: 'no-store',
      });
      const snapshot = await readJson<WorkerSnapshot>(response);

      workerSnapshot = snapshot;
      workerError = '';
      heartbeatRevision += 1;
      ensureSelectedModeIsAvailable(snapshot);
    } catch (error) {
      workerError = errorMessage(error);
    } finally {
      workerLoading = false;
    }
  }

  function ensureSelectedModeIsAvailable(snapshot: WorkerSnapshot): void {
    if (snapshot.execution_modes[selectedMode].enabled) {
      return;
    }

    if (snapshot.execution_modes.load_balance.enabled) {
      selectedMode = 'load_balance';
    }
  }

  function handleFileChange(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    clearSelectedPreview();
    selectedFile = input.files?.[0] ?? null;
    selectedPreviewUrl = selectedFile ? URL.createObjectURL(selectedFile) : null;
    submissionError = '';
  }

  function clearSelectedPreview(): void {
    if (selectedPreviewUrl) {
      URL.revokeObjectURL(selectedPreviewUrl);
      selectedPreviewUrl = null;
    }
  }

  async function retryWorkerConnection(): Promise<void> {
    connectionRetrying = true;
    workerLoading = true;
    workerError = '';

    try {
      const response = await fetch('/api/inference/workers/refresh', {
        method: 'POST',
        headers: { accept: 'application/json' },
      });
      const refreshed = await readJson<WorkerRefreshResponse>(response);

      workerSnapshot = refreshed;
      workerRefreshResult = refreshed.refresh;
      heartbeatRevision += 1;
      ensureSelectedModeIsAvailable(refreshed);
    } catch (error) {
      workerError = errorMessage(error);
    } finally {
      connectionRetrying = false;
      workerLoading = false;
    }
  }

  function clearJobResult(): void {
    pollRevision += 1;
    clearSelectedPreview();
    selectedFile = null;
    queuedInference = null;
    currentJob = null;
    submissionState = 'idle';
    submissionError = '';

    if (fileInput) {
      fileInput.value = '';
    }

    void refreshWorkers();
  }

  async function submitInference(): Promise<void> {
    if (!selectedFile || !selectedModeAvailability?.enabled || !canSubmit) {
      return;
    }

    pollRevision += 1;
    queuedInference = null;
    currentJob = null;
    submissionError = '';
    submissionState = 'uploading';

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('execution_mode', selectedMode);

    try {
      const response = await fetch('/api/inference/images', {
        method: 'POST',
        body: formData,
        headers: { accept: 'application/json' },
      });
      const queued = await readJson<QueuedInference>(response);

      queuedInference = queued;
      submissionState = 'queued';
      void refreshWorkers();
      void watchInferenceJob(queued.job_id);
    } catch (error) {
      submissionState = 'failed';
      submissionError = errorMessage(error);
      void refreshWorkers();
    }
  }

  async function watchInferenceJob(jobId: string): Promise<void> {
    const revision = ++pollRevision;

    while (revision === pollRevision) {
      try {
        const response = await fetch(`/api/inference/jobs/${encodeURIComponent(jobId)}`, {
          headers: { accept: 'application/json' },
          cache: 'no-store',
        });
        const job = await readJson<InferenceJob>(response);

        currentJob = job;
        submissionState = job.status;

        if (job.status === 'succeeded' || job.status === 'failed') {
          void refreshWorkers();
          return;
        }
      } catch (error) {
        submissionState = 'failed';
        submissionError = errorMessage(error);
        void refreshWorkers();
        return;
      }

      await delay(pollIntervalMs);
    }
  }

  async function readJson<T>(response: Response): Promise<T> {
    let body: T | ApiError = {};

    try {
      body = (await response.json()) as T | ApiError;
    } catch {
      // The Master normally returns JSON. Keep a useful UI error if a proxy fails before that.
    }

    if (!response.ok) {
      const apiError = body as ApiError;
      throw new ApiRequestError(
        apiError.message ?? `The request failed with HTTP ${response.status}.`,
        apiError,
      );
    }

    return body as T;
  }

  function errorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      return error.message;
    }

    return 'The request could not be completed. Check the Master API connection and try again.';
  }

  function delay(milliseconds: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function labelForMode(mode: ExecutionMode): string {
    return mode === 'load_balance' ? 'Load balancing' : 'Ensemble inference';
  }

  function modeDescription(mode: ExecutionMode): string {
    return mode === 'load_balance'
      ? 'Send the image to one idle worker.'
      : 'Send the same image to both workers and average the probabilities.';
  }

  function modeUnavailableMessage(mode: ExecutionMode): string {
    const availability = workerSnapshot?.execution_modes[mode];

    if (!availability) {
      return 'Worker availability has not loaded yet.';
    }

    return `${availability.available_workers} of ${availability.required_workers} required worker(s) are idle.`;
  }

  function formatWorkerState(state: string): string {
    return state.replace('_', ' ');
  }

  function formatDate(value: string | null): string {
    if (!value) {
      return 'No heartbeat';
    }

    return new Intl.DateTimeFormat(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(new Date(value));
  }

  function formatPercent(value: number): string {
    return new Intl.NumberFormat(undefined, {
      style: 'percent',
      maximumFractionDigits: 2,
    }).format(value);
  }

  function failedJobMessage(job: InferenceJob): string {
    if (job.reason === 'job_timeout') {
      const missingWorkers = job.missing_worker_ids?.join(', ') ?? 'a worker';
      return `The job timed out while waiting for ${missingWorkers}.`;
    }

    if (job.reason === 'worker_failed') {
      return 'A worker returned an error while processing this image.';
    }

    return 'The job failed before all workers returned a successful result.';
  }

  function orderedProbabilities(
    probabilities: Record<string, number> | null | undefined,
  ): [string, number][] {
    return Object.entries(probabilities ?? {}).sort(([, left], [, right]) => right - left);
  }
</script>

<svelte:head>
  <title>CC Lab Inference</title>
  <meta
    name="description"
    content="Submit a waste image for distributed classification through the CC Lab workers."
  />
</svelte:head>

<main>
  <header class="page-header">
    <div>
      <p class="eyebrow">CC Lab</p>
      <h1>Waste classification</h1>
      <p class="summary">Submit one image and run it through the available inference workers.</p>
    </div>
    <button
      class="secondary-button"
      type="button"
      onclick={() => void retryWorkerConnection()}
      disabled={workerLoading || connectionRetrying}
      title="Recheck the Client-to-Master connection and the latest worker heartbeats."
    >
      {connectionRetrying ? 'Requesting heartbeat…' : 'Retry worker connection'}
    </button>
  </header>

  {#if workerError}
    <section class="notice error-notice" role="alert">
      <strong>Worker status is unavailable.</strong>
      <span>{workerError}</span>
    </section>
  {/if}

  {#if workerRefreshResult}
    <p class="refresh-result" role="status">
      {#if workerRefreshResult.acknowledged_worker_ids.length > 0}
        Fresh heartbeat: {workerRefreshResult.acknowledged_worker_ids.join(', ')}.
      {:else}
        No Worker acknowledged this heartbeat request.
      {/if}
      {#if workerRefreshResult.unresponsive_worker_ids.length > 0}
        No reply within 3 seconds: {workerRefreshResult.unresponsive_worker_ids.join(', ')}.
      {/if}
    </p>
  {/if}

  <div class="layout">
    <section class="panel workers-panel" aria-labelledby="workers-heading">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Capacity</p>
          <h2 id="workers-heading">Workers</h2>
        </div>
        {#if workerSnapshot}
          <span class="availability-summary">{workerSnapshot.available_workers} idle</span>
        {/if}
      </div>

      {#if workerLoading && !workerSnapshot}
        <p class="muted">Reading worker heartbeat data…</p>
      {:else if workerSnapshot}
        <ul class="worker-list" aria-label="Worker status">
          {#each workerSnapshot.workers as worker (worker.worker_id)}
            <li class="worker-row">
              <div>
                <strong>{worker.worker_id}</strong>
                <span class="muted">Last heartbeat: {formatDate(worker.last_seen_at)}</span>
              </div>
              <span class:idle={worker.state === 'idle'} class="state-pill {worker.state}">
                {formatWorkerState(worker.state)}
              </span>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted">No worker state is available yet.</p>
      {/if}
    </section>

    <section class="panel submit-panel" aria-labelledby="submit-heading">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Inference request</p>
          <h2 id="submit-heading">Choose a mode and image</h2>
        </div>
      </div>

      <fieldset class="mode-options">
        <legend>Execution mode</legend>
        {#each ['load_balance', 'ensemble'] as mode}
          {@const executionMode = mode as ExecutionMode}
          {@const availability = workerSnapshot?.execution_modes[executionMode]}
          <label class:disabled={!availability?.enabled} class="mode-option">
            <input
              type="radio"
              name="execution-mode"
              value={executionMode}
              bind:group={selectedMode}
              disabled={!availability?.enabled}
            />
            <span>
              <strong>{labelForMode(executionMode)}</strong>
              <small>{modeDescription(executionMode)}</small>
              {#if availability && !availability.enabled}
                <small class="mode-unavailable">{modeUnavailableMessage(executionMode)}</small>
              {/if}
            </span>
          </label>
        {/each}
      </fieldset>

      <label class="file-label" for="image-file">Image file</label>
      <input
        id="image-file"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        bind:this={fileInput}
        onchange={handleFileChange}
        disabled={submissionState !== 'idle'}
      />
      <p class="muted file-name" aria-live="polite">
        {selectedFile
          ? `${selectedFile.name} (${Math.ceil(selectedFile.size / 1024)} KB)`
          : 'Choose a JPG, PNG, or WebP image.'}
      </p>

      {#if selectedPreviewUrl}
        <figure class="image-preview">
          <img
            src={selectedPreviewUrl}
            alt={`Preview of ${selectedFile?.name ?? 'selected image'}`}
          />
          <figcaption>The image is removed after all assigned Workers finish the job.</figcaption>
        </figure>
      {/if}

      <button
        class="primary-button"
        type="button"
        onclick={() => void submitInference()}
        disabled={!canSubmit}
      >
        {submissionState === 'uploading'
          ? 'Uploading image…'
          : submissionState === 'queued' || submissionState === 'processing'
            ? 'Inference in progress…'
            : `Run ${labelForMode(selectedMode)}`}
      </button>

      {#if !selectedModeAvailability?.enabled && workerSnapshot}
        <p class="muted" role="status">{modeUnavailableMessage(selectedMode)}</p>
      {/if}
    </section>
  </div>

  <DistributedFlow
    snapshot={workerSnapshot}
    {queuedInference}
    {currentJob}
    {submissionState}
    {heartbeatRevision}
  />

  <section class="panel result-panel" aria-labelledby="result-heading">
    <div class="section-heading">
      <div>
        <p class="eyebrow">Job result</p>
        <h2 id="result-heading">Inference status</h2>
      </div>
      <div class="result-actions">
        {#if queuedInference || submissionError}
          <button class="secondary-button clear-button" type="button" onclick={clearJobResult}>
            Clear result
          </button>
        {/if}
        {#if submissionState !== 'idle'}
          <span class="state-pill {submissionState}">{formatWorkerState(submissionState)}</span>
        {/if}
      </div>
    </div>

    {#if submissionError}
      <div class="notice error-notice" role="alert">{submissionError}</div>
    {:else if queuedInference}
      <div class="job-meta">
        <span><strong>Job:</strong> {queuedInference.job_id}</span>
        <span><strong>Workers:</strong> {queuedInference.worker_ids.join(', ')}</span>
        <span><strong>Mode:</strong> {labelForMode(queuedInference.execution_mode)}</span>
      </div>

      {#if currentJob?.status === 'succeeded' && currentJob.result}
        <div class="result-summary">
          <p class="prediction-label">Prediction</p>
          <p class="prediction-value">{currentJob.result.label ?? 'No label returned'}</p>
        </div>

        {#if orderedProbabilities(currentJob.result.probabilities).length > 0}
          <ul class="probability-list" aria-label="Classification probabilities">
            {#each orderedProbabilities(currentJob.result.probabilities) as [label, probability]}
              <li>
                <div class="probability-heading">
                  <span>{label}</span>
                  <strong>{formatPercent(probability)}</strong>
                </div>
                <div class="probability-track" aria-hidden="true">
                  <div
                    class="probability-fill"
                    style={`width: ${Math.max(0, Math.min(probability * 100, 100))}%`}
                  ></div>
                </div>
              </li>
            {/each}
          </ul>
        {/if}

        <div class="worker-result-grid">
          {#each currentJob.worker_results as workerResult (workerResult.worker_id)}
            <article class="worker-result">
              <strong>{workerResult.worker_id}</strong>
              <span>{workerResult.status}</span>
              {#if workerResult.status === 'succeeded'}
                <span>{workerResult.label}</span>
                <span>{workerResult.elapsed_ms ?? '—'} ms</span>
              {:else}
                <span>{workerResult.error ?? 'Worker did not return a result.'}</span>
              {/if}
            </article>
          {/each}
        </div>
      {:else if currentJob?.status === 'failed'}
        <div class="notice error-notice" role="alert">
          {failedJobMessage(currentJob)}
        </div>
        <div class="worker-result-grid">
          {#each currentJob.worker_results as workerResult (workerResult.worker_id)}
            <article class="worker-result">
              <strong>{workerResult.worker_id}</strong>
              <span>{workerResult.status}</span>
              <span
                >{workerResult.error ?? workerResult.label ?? 'No result details returned.'}</span
              >
            </article>
          {/each}
        </div>
      {:else}
        <p class="muted" aria-live="polite">
          {submissionState === 'queued'
            ? 'The job is queued for the selected worker.'
            : 'The worker is processing the image.'}
        </p>
      {/if}
    {:else}
      <p class="muted">A completed inference result will appear here.</p>
    {/if}
  </section>
</main>

<style>
  main {
    width: min(100% - 2rem, 70rem);
    margin: 0 auto;
    padding: 2rem 0 3rem;
  }

  .page-header,
  .section-heading,
  .worker-row,
  .probability-heading,
  .result-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .refresh-result {
    margin: -0.75rem 0 1rem;
    color: #aeb8c7;
    font-size: 0.9rem;
  }

  h1,
  h2,
  p {
    margin: 0;
  }

  h1 {
    font-size: clamp(1.8rem, 4vw, 2.6rem);
    letter-spacing: -0.04em;
  }

  h2 {
    font-size: 1.15rem;
  }

  .eyebrow {
    margin-bottom: 0.35rem;
    color: #9fb3c8;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .summary,
  .muted {
    color: #aeb8c7;
  }

  .summary {
    max-width: 44rem;
    margin-top: 0.65rem;
    line-height: 1.55;
  }

  .layout {
    display: grid;
    grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .panel,
  .notice {
    border: 1px solid #303948;
    border-radius: 0.75rem;
    background: #181e29;
  }

  .panel {
    padding: 1.25rem;
  }

  .notice {
    display: grid;
    gap: 0.25rem;
    margin-bottom: 1rem;
    padding: 0.9rem 1rem;
  }

  .error-notice {
    border-color: #85484e;
    color: #ffd9dc;
    background: #351d24;
  }

  .availability-summary,
  .state-pill {
    border-radius: 999px;
    padding: 0.3rem 0.6rem;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: capitalize;
  }

  .availability-summary,
  .state-pill.idle,
  .state-pill.succeeded {
    color: #b4f2cb;
    background: #133d2c;
  }

  .state-pill.busy,
  .state-pill.reserved,
  .state-pill.queued,
  .state-pill.processing {
    color: #ffe5aa;
    background: #4b3918;
  }

  .state-pill.offline,
  .state-pill.failed {
    color: #ffd9dc;
    background: #54252d;
  }

  .worker-list,
  .probability-list {
    display: grid;
    gap: 0.75rem;
    margin: 1rem 0 0;
    padding: 0;
    list-style: none;
  }

  .worker-row {
    align-items: start;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #303948;
  }

  .worker-row:last-child {
    padding-bottom: 0;
    border-bottom: 0;
  }

  .worker-row > div,
  .worker-result {
    display: grid;
    gap: 0.28rem;
  }

  .worker-row .muted,
  .mode-option small,
  .worker-result {
    font-size: 0.85rem;
  }

  .mode-options {
    display: grid;
    gap: 0.65rem;
    margin: 1.1rem 0;
    padding: 0;
    border: 0;
  }

  .mode-options legend,
  .file-label {
    font-weight: 700;
  }

  .mode-option {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    padding: 0.8rem;
    border: 1px solid #3a4657;
    border-radius: 0.55rem;
    cursor: pointer;
  }

  .mode-option:has(input:checked) {
    border-color: #7ea9f9;
    background: #182940;
  }

  .mode-option.disabled {
    cursor: not-allowed;
    opacity: 0.58;
  }

  .mode-option span {
    display: grid;
    gap: 0.2rem;
  }

  .mode-unavailable {
    color: #ffd78d;
  }

  .file-label {
    display: block;
    margin-bottom: 0.5rem;
  }

  input[type='file'] {
    width: 100%;
    color: #cbd5e1;
  }

  .file-name {
    min-height: 1.35rem;
    margin: 0.45rem 0 1rem;
    font-size: 0.85rem;
  }

  .image-preview {
    display: grid;
    gap: 0.45rem;
    margin: 0 0 1rem;
  }

  .image-preview img {
    width: 100%;
    max-height: 18rem;
    aspect-ratio: 4 / 3;
    border: 1px solid #3a4657;
    border-radius: 0.45rem;
    object-fit: contain;
    background: #0f141d;
  }

  .image-preview figcaption {
    color: #aeb8c7;
    font-size: 0.8rem;
    line-height: 1.45;
  }

  button {
    min-height: 2.65rem;
    border: 0;
    border-radius: 0.5rem;
    padding: 0.65rem 1rem;
    cursor: pointer;
    font-weight: 750;
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .primary-button {
    width: 100%;
    color: #07121f;
    background: #9fc3ff;
  }

  .primary-button:not(:disabled):hover {
    background: #c2d9ff;
  }

  .secondary-button {
    color: #dce6f3;
    border: 1px solid #465365;
    background: transparent;
  }

  .secondary-button:not(:disabled):hover {
    background: #242d3a;
  }

  .result-panel {
    min-height: 15rem;
  }

  .result-actions {
    justify-content: end;
  }

  .clear-button {
    min-height: auto;
    padding: 0.42rem 0.65rem;
    font-size: 0.82rem;
  }

  .job-meta {
    display: grid;
    gap: 0.4rem;
    margin: 1rem 0;
    color: #b7c3d3;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.8rem;
    overflow-wrap: anywhere;
  }

  .result-summary {
    margin: 1.25rem 0 1rem;
  }

  .prediction-label {
    color: #aeb8c7;
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
  }

  .prediction-value {
    margin-top: 0.2rem;
    color: #d7e6ff;
    font-size: clamp(1.6rem, 4vw, 2.3rem);
    font-weight: 800;
    text-transform: capitalize;
  }

  .probability-heading {
    margin-bottom: 0.35rem;
    text-transform: capitalize;
  }

  .probability-track {
    height: 0.55rem;
    overflow: hidden;
    border-radius: 99px;
    background: #303948;
  }

  .probability-fill {
    height: 100%;
    border-radius: inherit;
    background: #84b6ff;
  }

  .worker-result-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.75rem;
    margin-top: 1.2rem;
  }

  .worker-result {
    padding: 0.8rem;
    border: 1px solid #303948;
    border-radius: 0.5rem;
    color: #b7c3d3;
  }

  .worker-result strong {
    color: #eef4ff;
  }

  @media (max-width: 46rem) {
    main {
      width: min(100% - 1.25rem, 70rem);
      padding-top: 1.25rem;
    }

    .page-header,
    .section-heading,
    .result-actions {
      align-items: flex-start;
      flex-direction: column;
    }

    .secondary-button {
      width: 100%;
    }

    .layout {
      grid-template-columns: 1fr;
    }
  }
</style>
