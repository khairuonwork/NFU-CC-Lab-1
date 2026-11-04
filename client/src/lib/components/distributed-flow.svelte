<script lang="ts">
  import type { InferenceJob, QueuedInference, WorkerSnapshot, WorkerStatus } from '#lib/types';

  type SubmissionState = 'idle' | 'uploading' | 'queued' | 'processing' | 'succeeded' | 'failed';
  type PlaybackPhase = 'idle' | 'upload' | 'dispatch' | 'processing' | 'succeeded' | 'failed';

  const playbackDuration = {
    upload: 5_000,
    dispatch: 8_000,
    processing: 16_000,
    result: 8_000,
  } as const;

  let {
    snapshot,
    queuedInference,
    currentJob,
    submissionState,
    heartbeatRevision,
  }: {
    snapshot: WorkerSnapshot | null;
    queuedInference: QueuedInference | null;
    currentJob: InferenceJob | null;
    submissionState: SubmissionState;
    heartbeatRevision: number;
  } = $props();

  let playbackPhase = $state<PlaybackPhase>('idle');
  let playbackJobId = '';
  let playbackRun = 0;
  let playbackPaused = $state(false);
  let playbackFinished = $state(false);

  let assignedWorkerIds = $derived(queuedInference?.worker_ids ?? currentJob?.worker_ids ?? []);
  let executionMode = $derived(
    queuedInference?.execution_mode ?? currentJob?.execution_mode ?? null,
  );
  let jobFlowKey = $derived(
    `${queuedInference?.job_id ?? 'no-job'}:${assignedWorkerIds.join(',')}`,
  );
  let playbackActive = $derived(playbackPhase !== 'idle' && !playbackFinished);

  $effect(() => {
    const jobId = queuedInference?.job_id ?? '';

    if (jobId === playbackJobId) {
      return;
    }

    playbackJobId = jobId;
    playbackRun += 1;
    playbackPaused = false;
    playbackFinished = false;

    if (!jobId) {
      playbackPhase = 'idle';
      return;
    }

    void playInferenceRoute(jobId, playbackRun);
  });

  function workerSummary(worker: WorkerStatus): string {
    if (worker.state === 'offline') {
      return 'No current heartbeat';
    }

    if (worker.current_job_id) {
      return `Job ${worker.current_job_id.slice(0, 8)}`;
    }

    return worker.state === 'idle' ? 'Ready' : worker.state;
  }

  function workerStateClass(worker: WorkerStatus): string {
    return `is-${worker.state}`;
  }

  function phaseTitle(): string {
    if (playbackPhase === 'upload') return 'Uploading image';
    if (playbackPhase === 'dispatch') return 'Dispatching through Redis';
    if (playbackPhase === 'processing') return 'Worker inference';
    if (playbackPhase === 'succeeded') return 'Returning result';
    if (playbackPhase === 'failed') return 'Returning failure state';
    return 'Waiting for an inference request';
  }

  function phaseDescription(): string {
    if (playbackPhase === 'upload') {
      return 'Browser sends the selected image to the Master API.';
    }

    if (playbackPhase === 'dispatch') {
      return executionMode === 'ensemble'
        ? 'The Master reserves both workers and publishes two jobs.'
        : 'The Master reserves one idle worker and publishes one job.';
    }

    if (playbackPhase === 'processing') {
      if (submissionState === 'succeeded' || submissionState === 'failed') {
        return 'The job has finished. The visual route is completing its processing step.';
      }

      return 'The selected worker processes the cached image with ONNX Runtime.';
    }

    if (playbackPhase === 'succeeded') {
      return 'The Master has the required result and sends it back to the browser.';
    }

    if (playbackPhase === 'failed') {
      return 'The Master returns the failure state to the browser.';
    }

    return 'Choose an image and execution mode to show the route.';
  }

  function modeLabel(): string {
    return executionMode === 'ensemble' ? 'Ensemble' : 'Load balancing';
  }

  async function playInferenceRoute(jobId: string, run: number): Promise<void> {
    playbackPhase = 'upload';
    await waitForStage(playbackDuration.upload, jobId, run);

    if (!isCurrentPlayback(jobId, run)) return;

    playbackPhase = 'dispatch';
    await waitForStage(playbackDuration.dispatch, jobId, run);

    if (!isCurrentPlayback(jobId, run)) return;

    playbackPhase = 'processing';
    await waitForStage(playbackDuration.processing, jobId, run);

    while (isCurrentPlayback(jobId, run)) {
      const terminalStatus = currentTerminalStatus(jobId);

      if (terminalStatus) {
        playbackPhase = terminalStatus;
        await waitForStage(playbackDuration.result, jobId, run);
        playbackFinished = isCurrentPlayback(jobId, run);
        return;
      }

      await delay(250);
    }
  }

  async function waitForStage(durationMs: number, jobId: string, run: number): Promise<void> {
    let elapsedMs = 0;

    while (elapsedMs < durationMs && isCurrentPlayback(jobId, run)) {
      await delay(100);

      if (!playbackPaused) {
        elapsedMs += 100;
      }
    }
  }

  function currentTerminalStatus(jobId: string): 'succeeded' | 'failed' | null {
    if (currentJob?.job_id !== jobId) return null;
    if (currentJob.status === 'succeeded' || currentJob.status === 'failed') {
      return currentJob.status;
    }

    return null;
  }

  function isCurrentPlayback(jobId: string, run: number): boolean {
    return playbackJobId === jobId && playbackRun === run;
  }

  function togglePlaybackPause(): void {
    playbackPaused = !playbackPaused;
  }

  function delay(milliseconds: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }
</script>

<section class="distributed-flow" aria-labelledby="distributed-flow-heading">
  <div class="section-heading">
    <div>
      <h2 id="distributed-flow-heading">System path</h2>
      <p>Current worker connection and the selected inference route.</p>
    </div>
  </div>

  <div class="connection-block">
    <h3>Worker connection</h3>
    {#if snapshot}
      {#key heartbeatRevision}
        <div
          class="connection-map"
          aria-label="Workers publish heartbeats to Redis, which the Master API reads"
        >
          <div class="connection-workers">
            {#each snapshot.workers as worker (worker.worker_id)}
              <article class={`node worker-node ${workerStateClass(worker)}`}>
                <strong>{worker.worker_id}</strong>
                <span>{workerSummary(worker)}</span>
              </article>
            {/each}
          </div>
          <span class="route-line" aria-hidden="true"></span>
          <article class="node">
            <strong>Redis</strong>
            <span>Heartbeat records</span>
          </article>
          <span class="route-line" aria-hidden="true"></span>
          <article class="node">
            <strong>Master API</strong>
            <span>Reads worker status</span>
          </article>
        </div>
      {/key}
    {:else}
      <p class="muted">Waiting for worker status from the Master API.</p>
    {/if}
  </div>

  <div class="request-block">
    <div class="route-heading">
      <div>
        <h3>Inference route</h3>
        <p>{executionMode ? `${modeLabel()} mode` : 'No request queued'}</p>
      </div>
      {#if playbackActive}
        <button class="pause-button" type="button" onclick={togglePlaybackPause}>
          {playbackPaused ? 'Resume visual path' : 'Pause visual path'}
        </button>
      {/if}
    </div>

    {#key jobFlowKey}
      <div
        class:phase-upload={playbackPhase === 'upload'}
        class:phase-dispatch={playbackPhase === 'dispatch'}
        class:phase-processing={playbackPhase === 'processing'}
        class:result-succeeded={playbackPhase === 'succeeded'}
        class:result-failed={playbackPhase === 'failed'}
        class:playback-paused={playbackPaused}
        class="request-map"
        aria-live="polite"
      >
        <article class="node browser-node">
          <strong>Browser</strong>
          <span>Selected image</span>
        </article>
        <div class="route-rail upload-rail" aria-hidden="true"><i class="packet"></i></div>
        <article class="node master-node">
          <strong>Master API</strong>
          <span>Stores and dispatches</span>
        </article>
        <div class="route-rail dispatch-rail" aria-hidden="true">
          <i class="packet first-packet"></i>
          {#if executionMode === 'ensemble'}
            <i class="packet second-packet"></i>
          {/if}
        </div>
        <div class="route-workers">
          {#if assignedWorkerIds.length > 0}
            {#each assignedWorkerIds as workerId (workerId)}
              <article class="node assigned-worker">
                <strong>{workerId}</strong>
                <span>{playbackPhase === 'processing' ? 'ONNX Runtime' : 'Selected worker'}</span>
              </article>
            {/each}
          {:else}
            <article class="node waiting-worker">
              <strong>Worker</strong>
              <span>Waiting for a request</span>
            </article>
          {/if}
        </div>
      </div>
    {/key}

    <div class="route-status" role="status">
      <strong>{phaseTitle()}</strong>
      <span>{phaseDescription()}</span>
    </div>
  </div>
</section>

<style>
  .distributed-flow {
    display: grid;
    gap: 1.5rem;
    margin: 1rem 0;
    padding: 1.25rem;
    border: 1px solid #d4d9df;
    border-radius: 0.5rem;
    background: #ffffff;
  }

  .section-heading,
  .route-heading {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: 1rem;
  }

  h2,
  h3,
  p {
    margin: 0;
  }

  h2 {
    font-size: 1.15rem;
  }

  h3 {
    font-size: 0.95rem;
  }

  .section-heading p,
  .route-heading p,
  .node span,
  .muted,
  .route-status span {
    color: #596575;
    font-size: 0.85rem;
    line-height: 1.45;
  }

  .section-heading p {
    margin-top: 0.25rem;
  }

  .connection-block,
  .request-block {
    display: grid;
    gap: 0.75rem;
  }

  .connection-block {
    padding-top: 1.25rem;
    border-top: 1px solid #e1e4e8;
  }

  .connection-map,
  .request-map {
    display: flex;
    align-items: stretch;
    gap: 0.5rem;
    min-width: 0;
  }

  .connection-workers,
  .route-workers {
    display: grid;
    flex: 1 1 0;
    gap: 0.5rem;
    min-width: 0;
  }

  .node {
    display: grid;
    flex: 1 1 0;
    min-width: 0;
    min-height: 4.5rem;
    align-content: center;
    gap: 0.2rem;
    padding: 0.75rem;
    border: 1px solid #c9d0d8;
    border-radius: 0.35rem;
    background: #fafbfc;
  }

  .node strong {
    overflow-wrap: anywhere;
  }

  .worker-node.is-idle,
  .result-succeeded .assigned-worker {
    border-color: #4c8865;
    background: #f2f8f3;
  }

  .worker-node.is-busy,
  .worker-node.is-reserved,
  .worker-node.is-training,
  .phase-processing .assigned-worker {
    border-color: #ae7b20;
    background: #fff8e8;
  }

  .worker-node.is-offline,
  .result-failed .assigned-worker {
    border-color: #b45459;
    background: #fff4f4;
  }

  .route-line,
  .route-rail {
    position: relative;
    display: grid;
    flex: 0 0 3rem;
    place-items: center;
    overflow: hidden;
  }

  .route-line::before,
  .route-rail::before {
    width: 100%;
    height: 1px;
    background: #99a3af;
    content: '';
  }

  .route-line::after,
  .route-rail::after {
    position: absolute;
    right: 0.15rem;
    width: 0;
    height: 0;
    border-top: 0.28rem solid transparent;
    border-bottom: 0.28rem solid transparent;
    border-left: 0.38rem solid #687484;
    content: '';
  }

  .packet {
    position: absolute;
    z-index: 1;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: #1769cc;
    opacity: 0;
  }

  .phase-upload .upload-rail .packet {
    animation: travel-horizontal 5s linear both;
  }

  .phase-dispatch .dispatch-rail .first-packet {
    animation: travel-horizontal 8s linear both;
  }

  .phase-dispatch .dispatch-rail .second-packet {
    animation: travel-horizontal 8s linear 1.2s both;
  }

  .result-succeeded .upload-rail .packet,
  .result-succeeded .dispatch-rail .packet {
    background: #317d4d;
    animation: travel-back 8s linear both;
  }

  .result-failed .upload-rail .packet,
  .result-failed .dispatch-rail .packet {
    background: #ad424a;
    animation: travel-back 8s linear both;
  }

  .playback-paused .packet {
    animation-play-state: paused;
  }

  .phase-upload .browser-node,
  .phase-dispatch .master-node {
    border-color: #1769cc;
    background: #f2f7ff;
  }

  .waiting-worker {
    border-style: dashed;
  }

  .route-status {
    display: grid;
    gap: 0.2rem;
    padding: 0.8rem;
    border: 1px solid #dfe3e8;
    background: #fafbfc;
  }

  .pause-button {
    min-height: 2.75rem;
    border: 1px solid #aeb7c2;
    border-radius: 0.35rem;
    padding: 0.5rem 0.75rem;
    color: #283443;
    background: #ffffff;
    font-weight: 700;
  }

  .pause-button:hover {
    background: #eef3f8;
  }

  @keyframes travel-horizontal {
    from {
      opacity: 0;
      transform: translateX(-1.4rem);
    }

    12% {
      opacity: 1;
    }

    88% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateX(1.4rem);
    }
  }

  @keyframes travel-back {
    from {
      opacity: 0;
      transform: translateX(1.4rem);
    }

    12% {
      opacity: 1;
    }

    88% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateX(-1.4rem);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .packet {
      animation: none !important;
    }
  }

  @media (max-width: 46rem) {
    .section-heading,
    .route-heading {
      flex-direction: column;
    }

    .connection-map,
    .request-map {
      display: grid;
      grid-template-columns: 1fr;
    }

    .route-line,
    .route-rail {
      width: 100%;
      height: 1.5rem;
      min-height: 1.5rem;
    }

    .route-line::before,
    .route-rail::before {
      width: 1px;
      height: 100%;
    }

    .route-line::after,
    .route-rail::after {
      right: auto;
      bottom: 0.1rem;
      border-top: 0.38rem solid #687484;
      border-right: 0.28rem solid transparent;
      border-bottom: 0;
      border-left: 0.28rem solid transparent;
    }

    .phase-upload .upload-rail .packet,
    .phase-dispatch .dispatch-rail .first-packet,
    .phase-dispatch .dispatch-rail .second-packet,
    .result-succeeded .upload-rail .packet,
    .result-succeeded .dispatch-rail .packet,
    .result-failed .upload-rail .packet,
    .result-failed .dispatch-rail .packet {
      animation-name: travel-vertical;
    }

    .result-succeeded .upload-rail .packet,
    .result-succeeded .dispatch-rail .packet,
    .result-failed .upload-rail .packet,
    .result-failed .dispatch-rail .packet {
      animation-name: travel-vertical-back;
    }
  }

  @keyframes travel-vertical {
    from {
      opacity: 0;
      transform: translateY(-0.6rem);
    }

    12% {
      opacity: 1;
    }

    88% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateY(0.6rem);
    }
  }

  @keyframes travel-vertical-back {
    from {
      opacity: 0;
      transform: translateY(0.6rem);
    }

    12% {
      opacity: 1;
    }

    88% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateY(-0.6rem);
    }
  }
</style>
