<script lang="ts">
  import { animate } from 'motion';

  import type { InferenceJob, QueuedInference, WorkerSnapshot, WorkerStatus } from '#lib/types';

  type SubmissionState = 'idle' | 'uploading' | 'queued' | 'processing' | 'succeeded' | 'failed';
  type PlaybackPhase = 'idle' | 'upload' | 'dispatch' | 'processing' | 'succeeded' | 'failed';
  type PlaybackControls = { stop: () => void };

  const playbackDuration = {
    upload: 2_500,
    dispatch: 4_000,
    processing: 8_000,
    result: 5_000,
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

  let requestMap = $state<HTMLDivElement | null>(null);
  let playbackPhase = $state<PlaybackPhase>('idle');
  let playbackJobId = '';
  let playbackRun = 0;
  let motionControls: PlaybackControls[] = [];

  let assignedWorkerIds = $derived(queuedInference?.worker_ids ?? currentJob?.worker_ids ?? []);
  let executionMode = $derived(
    queuedInference?.execution_mode ?? currentJob?.execution_mode ?? null,
  );
  let jobFlowKey = $derived(
    `${queuedInference?.job_id ?? 'no-job'}:${assignedWorkerIds.join(',')}`,
  );

  $effect(() => {
    const jobId = queuedInference?.job_id ?? '';

    if (jobId === playbackJobId) {
      return;
    }

    playbackJobId = jobId;
    playbackRun += 1;
    stopMotion();

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

    return worker.state === 'idle' ? 'Ready for a job' : worker.state;
  }

  function workerStateClass(worker: WorkerStatus): string {
    return `is-${worker.state}`;
  }

  function workerRouteStatus(): string {
    if (playbackPhase === 'upload') return 'Waiting for upload';
    if (playbackPhase === 'dispatch') return 'Redis Stream queue';
    if (playbackPhase === 'processing') return 'Running ONNX';
    if (playbackPhase === 'succeeded') return 'Result returned';
    if (playbackPhase === 'failed') return 'Job failed';
    return 'Awaiting a queued job';
  }

  function jobPathText(): string {
    if (submissionState === 'uploading') {
      return 'The image is being uploaded to the Master API.';
    }

    if (!queuedInference) {
      return 'No inference job has been queued in this browser session.';
    }

    if (playbackPhase === 'upload') {
      return 'Visual playback: Browser sends the image to the Master API.';
    }

    if (playbackPhase === 'dispatch') {
      return `Visual playback: Master dispatches to ${assignedWorkerIds.join(' and ')}.`;
    }

    if (playbackPhase === 'processing') {
      if (submissionState === 'succeeded' || submissionState === 'failed') {
        return 'The job has finished. The visual route is completing before it is marked complete.';
      }

      return `${assignedWorkerIds.join(' and ')} ${assignedWorkerIds.length === 1 ? 'is' : 'are'} processing the image.`;
    }

    if (playbackPhase === 'succeeded') {
      return 'Visual playback complete. The Master received all required worker results.';
    }

    if (playbackPhase === 'failed') {
      return 'Visual playback complete. The inference job finished with an error.';
    }

    return 'The Master accepted the job. Visual playback is preparing the route.';
  }

  function modeLabel(): string {
    return executionMode === 'ensemble' ? 'Ensemble' : 'Load balancing';
  }

  async function playInferenceRoute(jobId: string, run: number): Promise<void> {
    await delay(100);

    if (!isCurrentPlayback(jobId, run)) return;

    playbackPhase = 'upload';
    animateRequestDots('upload', 'forward', playbackDuration.upload);
    await delay(playbackDuration.upload);

    if (!isCurrentPlayback(jobId, run)) return;

    playbackPhase = 'dispatch';
    animateRequestDots('dispatch', 'forward', playbackDuration.dispatch);
    await delay(playbackDuration.dispatch);

    if (!isCurrentPlayback(jobId, run)) return;

    playbackPhase = 'processing';
    await delay(playbackDuration.processing);

    while (isCurrentPlayback(jobId, run)) {
      const terminalStatus = currentTerminalStatus(jobId);

      if (terminalStatus) {
        playbackPhase = terminalStatus;
        animateRequestDots('result', 'reverse', playbackDuration.result);
        return;
      }

      await delay(1_000);
    }
  }

  function currentTerminalStatus(jobId: string): 'succeeded' | 'failed' | null {
    if (queuedInference?.job_id !== jobId) return null;
    if (submissionState === 'succeeded' || submissionState === 'failed') return submissionState;
    return null;
  }

  function isCurrentPlayback(jobId: string, run: number): boolean {
    return playbackJobId === jobId && playbackRun === run;
  }

  function animateRequestDots(
    stage: 'upload' | 'dispatch' | 'result',
    direction: 'forward' | 'reverse',
    durationMs: number,
  ): void {
    stopMotion();

    if (!requestMap || prefersReducedMotion()) return;

    const dots = [...requestMap.querySelectorAll<HTMLElement>(`[data-stage="${stage}"]`)];
    const isVertical = window.matchMedia('(max-width: 46rem)').matches;

    dots.forEach((dot, index) => {
      const travel = direction === 'forward' ? 22 : -22;
      const keyframes = isVertical
        ? { opacity: [0, 1, 1, 0], y: [-travel, 0, 0, travel] }
        : { opacity: [0, 1, 1, 0], x: [-travel, 0, 0, travel] };
      const controls = animate(dot, keyframes, {
        duration: durationMs / 1_000,
        delay: index * 0.35,
        ease: 'easeInOut',
      });

      motionControls.push(controls);
    });
  }

  function stopMotion(): void {
    for (const controls of motionControls) controls.stop();
    motionControls = [];
  }

  function prefersReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function delay(milliseconds: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }
</script>

<section class="distributed-flow" aria-labelledby="distributed-flow-heading">
  <div class="flow-heading">
    <div>
      <p class="eyebrow">Distributed state</p>
      <h2 id="distributed-flow-heading">Live worker path</h2>
    </div>
    {#if snapshot}
      <p class="flow-summary">{snapshot.available_workers} Worker(s) available</p>
    {/if}
  </div>

  <div class="flow-block" aria-labelledby="heartbeat-heading">
    <div class="flow-block-heading">
      <h3 id="heartbeat-heading">Heartbeat route</h3>
      <p>Worker status is read from Redis through the Master API.</p>
    </div>

    {#if snapshot}
      {#key heartbeatRevision}
        <div
          class="heartbeat-map"
          aria-label="Worker heartbeats flow to Redis, then to the Master API"
        >
          <div class="worker-stack">
            {#each snapshot.workers as worker (worker.worker_id)}
              <article class={`flow-node worker-node ${workerStateClass(worker)}`}>
                <strong>{worker.worker_id}</strong>
                <span>{workerSummary(worker)}</span>
              </article>
            {/each}
          </div>

          <div class="flow-connection heartbeat-connection" aria-hidden="true"><span></span></div>

          <article class="flow-node redis-node">
            <strong>Redis</strong>
            <span>Worker hashes and reservations</span>
          </article>

          <div class="flow-connection heartbeat-connection" aria-hidden="true"><span></span></div>

          <article class="flow-node master-node">
            <strong>Master API</strong>
            <span>/inference/workers</span>
          </article>
        </div>
      {/key}
    {:else}
      <p class="flow-empty">Waiting for the Master API to return worker heartbeat data.</p>
    {/if}
  </div>

  <div class="flow-block" aria-labelledby="request-heading">
    <div class="flow-block-heading">
      <h3 id="request-heading">Inference route</h3>
      <p>
        {executionMode
          ? `${modeLabel()} uses the Workers selected by the Master.`
          : 'A route appears after an image has been submitted.'}
      </p>
    </div>

    {#key jobFlowKey}
      <div
        bind:this={requestMap}
        class:phase-upload={playbackPhase === 'upload'}
        class:phase-dispatch={playbackPhase === 'dispatch'}
        class:phase-processing={playbackPhase === 'processing'}
        class:result-succeeded={playbackPhase === 'succeeded'}
        class:result-failed={playbackPhase === 'failed'}
        class="request-map"
        aria-live="polite"
      >
        <article class="flow-node browser-node">
          <strong>Browser</strong>
          <span>Image upload</span>
        </article>

        <div class="flow-connection request-connection" aria-hidden="true">
          <span data-stage="upload"></span>
          <span class="result-dot" data-stage="result"></span>
        </div>

        <article class="flow-node master-node">
          <strong>Master API</strong>
          <span>Upload, reserve, dispatch</span>
        </article>

        <div class="flow-connection request-connection dispatch-connection" aria-hidden="true">
          {#if executionMode === 'ensemble'}
            <span class="ensemble-first" data-stage="dispatch"></span>
            <span class="ensemble-second" data-stage="dispatch"></span>
          {:else}
            <span data-stage="dispatch"></span>
          {/if}
          <span class="result-dot" data-stage="result"></span>
        </div>

        <div class="assigned-workers" aria-label="Workers selected for the current job">
          {#if assignedWorkerIds.length > 0}
            {#each assignedWorkerIds as workerId (workerId)}
              <article class="flow-node assigned-worker">
                <strong>{workerId}</strong>
                <span>{workerRouteStatus()}</span>
              </article>
            {/each}
          {:else}
            <article class="flow-node waiting-worker">
              <strong>Workers</strong>
              <span>Awaiting a queued job</span>
            </article>
          {/if}
        </div>
      </div>
    {/key}

    <p class="flow-status" role="status">{jobPathText()}</p>
  </div>
</section>

<style>
  .distributed-flow {
    display: grid;
    gap: 1.25rem;
    margin-bottom: 1rem;
    padding: 1.25rem;
    border: 1px solid #303948;
    border-radius: 0.75rem;
    background: #181e29;
  }

  .flow-heading,
  .flow-block-heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .flow-heading h2,
  .flow-block-heading h3,
  .flow-heading p,
  .flow-block-heading p,
  .flow-status,
  .flow-empty {
    margin: 0;
  }

  .eyebrow {
    margin-bottom: 0.35rem;
    color: #9fb3c8;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .flow-heading h2 {
    font-size: 1.15rem;
  }

  .flow-summary,
  .flow-block-heading p,
  .flow-node span,
  .flow-status,
  .flow-empty {
    color: #aeb8c7;
    font-size: 0.85rem;
  }

  .flow-summary {
    margin-left: auto;
  }

  .flow-block {
    display: grid;
    gap: 0.8rem;
    padding-top: 1.25rem;
    border-top: 1px solid #303948;
  }

  .flow-block-heading {
    align-items: start;
  }

  .flow-block-heading h3 {
    color: #edf3fd;
    font-size: 0.95rem;
  }

  .flow-block-heading p {
    max-width: 32rem;
    text-align: right;
  }

  .heartbeat-map,
  .request-map {
    display: flex;
    align-items: stretch;
    gap: 0.6rem;
    min-width: 0;
  }

  .worker-stack,
  .assigned-workers {
    display: grid;
    flex: 1 1 0;
    gap: 0.5rem;
    min-width: 0;
  }

  .flow-node {
    display: grid;
    min-width: 0;
    min-height: 4.6rem;
    gap: 0.25rem;
    align-content: center;
    padding: 0.7rem 0.8rem;
    border: 1px solid #3a4657;
    border-radius: 0.45rem;
    background: #141a24;
  }

  .flow-node strong {
    color: #edf3fd;
    overflow-wrap: anywhere;
  }

  .worker-node.is-idle {
    border-color: #276346;
  }

  .worker-node.is-busy,
  .worker-node.is-reserved,
  .worker-node.is-training {
    border-color: #80612a;
  }

  .worker-node.is-offline {
    border-color: #7c3e48;
  }

  .redis-node {
    flex: 1.15 1 0;
    border-color: #536a92;
  }

  .master-node {
    flex: 1.15 1 0;
    border-color: #7894c0;
  }

  .browser-node,
  .assigned-workers {
    flex: 1 1 0;
  }

  .waiting-worker {
    height: 100%;
    border-style: dashed;
  }

  .flow-connection {
    position: relative;
    display: grid;
    flex: 0 0 2.8rem;
    place-items: center;
    overflow: hidden;
  }

  .flow-connection::before {
    width: 100%;
    height: 1px;
    background: #526174;
    content: '';
  }

  .flow-connection::after {
    position: absolute;
    right: 0.1rem;
    width: 0;
    height: 0;
    border-top: 0.28rem solid transparent;
    border-bottom: 0.28rem solid transparent;
    border-left: 0.4rem solid #748397;
    content: '';
  }

  .flow-connection span {
    position: absolute;
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: #a9c8ff;
    opacity: 0;
    will-change: opacity, transform;
  }

  .heartbeat-connection span {
    animation: heartbeat-travel 10s ease-in-out both;
  }

  .request-map.result-succeeded .result-dot {
    background: #9fddba;
  }

  .request-map.result-failed .result-dot {
    background: #ffadb5;
  }

  .dispatch-connection .ensemble-first {
    top: 30%;
  }

  .dispatch-connection .ensemble-second {
    top: 70%;
  }

  .phase-upload .browser-node,
  .phase-dispatch .master-node,
  .phase-processing .assigned-worker {
    border-color: #a9c8ff;
  }

  .result-succeeded .assigned-worker,
  .result-succeeded .master-node {
    border-color: #63a97f;
  }

  .result-failed .assigned-worker,
  .result-failed .master-node {
    border-color: #c76d77;
  }

  .flow-status,
  .flow-empty {
    line-height: 1.5;
  }

  @keyframes heartbeat-travel {
    from {
      opacity: 0;
      transform: translateX(-1.25rem);
    }

    40% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateX(1.25rem);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .heartbeat-connection span {
      animation: none;
    }
  }

  @media (max-width: 46rem) {
    .flow-heading,
    .flow-block-heading {
      align-items: start;
      flex-direction: column;
    }

    .flow-heading p,
    .flow-block-heading p {
      margin-left: 0;
      text-align: left;
    }

    .heartbeat-map,
    .request-map {
      display: grid;
      grid-template-columns: 1fr;
    }

    .flow-connection {
      width: 100%;
      height: 1.75rem;
      min-height: 1.75rem;
    }

    .flow-connection::before {
      width: 1px;
      height: 100%;
    }

    .flow-connection::after {
      right: auto;
      bottom: 0.08rem;
      border-top: 0.4rem solid #748397;
      border-right: 0.28rem solid transparent;
      border-bottom: 0;
      border-left: 0.28rem solid transparent;
    }

    .dispatch-connection .ensemble-first {
      top: auto;
      left: 30%;
    }

    .dispatch-connection .ensemble-second {
      top: auto;
      left: 70%;
    }

    .heartbeat-connection span {
      animation-name: vertical-heartbeat-travel;
    }
  }

  @keyframes vertical-heartbeat-travel {
    from {
      opacity: 0;
      transform: translateY(-0.5rem);
    }

    40% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateY(0.5rem);
    }
  }
</style>
