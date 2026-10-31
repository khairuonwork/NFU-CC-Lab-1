<script lang="ts">
  import type { InferenceJob, QueuedInference, WorkerSnapshot, WorkerStatus } from '#lib/types';

  type SubmissionState = 'idle' | 'uploading' | 'queued' | 'processing' | 'succeeded' | 'failed';

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

  let assignedWorkerIds = $derived(queuedInference?.worker_ids ?? currentJob?.worker_ids ?? []);
  let executionMode = $derived(
    queuedInference?.execution_mode ?? currentJob?.execution_mode ?? null,
  );
  let isActiveJob = $derived(
    submissionState === 'uploading' ||
      submissionState === 'queued' ||
      submissionState === 'processing',
  );
  let hasSucceededResult = $derived(Boolean(queuedInference && submissionState === 'succeeded'));
  let hasFailedResult = $derived(Boolean(queuedInference && submissionState === 'failed'));
  let jobFlowKey = $derived(
    `${queuedInference?.job_id ?? 'no-job'}:${submissionState}:${assignedWorkerIds.join(',')}`,
  );

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

  function jobPathText(): string {
    if (submissionState === 'uploading') {
      return 'The image is being uploaded to the Master API.';
    }

    if (!queuedInference) {
      return 'No inference job has been queued in this browser session.';
    }

    if (submissionState === 'queued') {
      return `The Master queued the job for ${assignedWorkerIds.join(' and ')}.`;
    }

    if (submissionState === 'processing') {
      return `${assignedWorkerIds.join(' and ')} ${assignedWorkerIds.length === 1 ? 'is' : 'are'} processing the image.`;
    }

    if (submissionState === 'succeeded') {
      return 'The Master received all required worker results.';
    }

    return 'The inference job finished with an error.';
  }

  function modeLabel(): string {
    return executionMode === 'ensemble' ? 'Ensemble' : 'Load balancing';
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

          <div class="flow-connection heartbeat-connection" aria-hidden="true">
            <span></span>
          </div>

          <article class="flow-node redis-node">
            <strong>Redis</strong>
            <span>Worker hashes and reservations</span>
          </article>

          <div class="flow-connection heartbeat-connection" aria-hidden="true">
            <span></span>
          </div>

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
        class:job-active={isActiveJob}
        class:result-succeeded={hasSucceededResult}
        class:result-failed={hasFailedResult}
        class="request-map"
        aria-live="polite"
      >
        <article class="flow-node browser-node">
          <strong>Browser</strong>
          <span>Image upload</span>
        </article>

        <div class="flow-connection request-connection" aria-hidden="true">
          <span></span>
        </div>

        <article class="flow-node master-node">
          <strong>Master API</strong>
          <span>Upload, reserve, dispatch</span>
        </article>

        <div class="flow-connection request-connection" aria-hidden="true">
          <span></span>
        </div>

        <div class="assigned-workers" aria-label="Workers selected for the current job">
          {#if assignedWorkerIds.length > 0}
            {#each assignedWorkerIds as workerId (workerId)}
              <article class="flow-node assigned-worker">
                <strong>{workerId}</strong>
                <span>
                  {submissionState === 'succeeded'
                    ? 'Result returned'
                    : submissionState === 'failed'
                      ? 'Job failed'
                      : submissionState === 'processing'
                        ? 'Running ONNX'
                        : 'Redis Stream queue'}
                </span>
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
  .flow-block-heading p {
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
  }

  .heartbeat-connection span {
    animation: heartbeat-travel 1.6s ease-out both;
  }

  .job-active .request-connection span {
    animation: request-travel 2.2s ease-in-out both;
  }

  .result-succeeded .request-connection span,
  .result-failed .request-connection span {
    animation: result-travel 3.2s linear infinite;
  }

  .result-succeeded .request-connection span {
    background: #9fddba;
  }

  .result-failed .request-connection span {
    background: #ffadb5;
  }

  .flow-status,
  .flow-empty {
    margin: 0;
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

  @keyframes request-travel {
    from {
      opacity: 0;
      transform: translateX(-1.25rem);
    }

    25% {
      opacity: 1;
    }

    75% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateX(1.25rem);
    }
  }

  @keyframes result-travel {
    from {
      opacity: 0;
      transform: translateX(1.25rem);
    }

    25% {
      opacity: 1;
    }

    75% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateX(-1.25rem);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .heartbeat-connection span,
    .job-active .request-connection span,
    .result-succeeded .request-connection span,
    .result-failed .request-connection span {
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
      border-left: 0.28rem solid transparent;
      border-bottom: 0;
    }

    .heartbeat-connection span,
    .job-active .request-connection span {
      animation-name: vertical-travel;
    }

    .result-succeeded .request-connection span,
    .result-failed .request-connection span {
      animation-name: vertical-result-travel;
    }
  }

  @keyframes vertical-travel {
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

  @keyframes vertical-result-travel {
    from {
      opacity: 0;
      transform: translateY(0.5rem);
    }

    25% {
      opacity: 1;
    }

    75% {
      opacity: 1;
    }

    to {
      opacity: 0;
      transform: translateY(-0.5rem);
    }
  }
</style>
