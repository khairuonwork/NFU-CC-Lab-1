# Distributed Inference Code Map

This document maps the implemented inference path. The system has one Master
API, Redis on NodeMaster, RustFS, and two Worker processes. The browser never
calls a Worker directly.

## Runtime topology

```text
SvelteKit browser
  -> SvelteKit server routes
  -> FastAPI Master
  -> Redis
     -> node1 Worker
     -> node2 Worker

Workers <-> RustFS
Master <-> RustFS
```

Redis carries short-lived coordination state. RustFS stores images and the ONNX
artifact. The Master decides which Workers receive each job.

## Worker heartbeat

| Responsibility | File | Implementation |
| --- | --- | --- |
| Start the Worker runtime | `service/worker/app/main.py` | `run_worker()` creates one `WorkerRuntime`, starts `run_heartbeat_loop()`, then starts the Redis Stream consumer. |
| Publish one heartbeat | `service/worker/app/services/heartbeat.py` | `publish_heartbeat()` writes a Redis Hash and refreshes its expiry in one pipeline. |
| Repeat heartbeat | `service/worker/app/services/heartbeat.py` | `run_heartbeat_loop()` publishes, waits for `heartbeat_interval_seconds`, then repeats. |
| Read worker state | `service/master/app/services/job_dispatcher.py` | `_read_worker_status_details()` reads heartbeat Hashes and reservation keys. |
| Expose state to the UI | `service/master/app/api/routes/inference.py` | `GET /inference/workers` calls `read_worker_statuses()`. |
| Poll state in the browser | `client/src/routes/+page.svelte` | `refreshWorkers()` calls the SvelteKit proxy every four seconds. |

Each Worker writes this Redis Hash:

```text
cc:worker:node1
cc:worker:node2
```

The Hash fields are:

```text
worker_id
state
last_seen_at
current_job_id
```

The Worker also applies a TTL. With the current configuration, it publishes
every five seconds and its Hash expires after fifteen seconds. If the Worker
process stops, the Hash expires and the Master reads that Worker as `offline`.

Heartbeat is status reporting only. It does not dispatch a job.

## Load balancing

Load balancing sends one image to one idle Worker.

| Step | File | Implementation |
| --- | --- | --- |
| Receive execution mode | `service/master/app/schemas/inference_contract.py` | `ExecutionMode.LOAD_BALANCE` is the explicit request value. |
| Choose the operation | `service/master/app/services/job_dispatcher.py` | `accept_order()` calls `load_balance()` for that mode. |
| Require one Worker | `service/master/app/services/job_dispatcher.py` | `load_balance()` calls `_queue_order(..., required_workers=1)`. |
| Reserve a Worker | `service/master/app/services/job_dispatcher.py` | `_reserve_workers()` selects an idle Worker and creates `cc:reservation:<worker_id>` using Redis `SET NX EX`. |
| Publish one stream message | `service/master/app/services/job_dispatcher.py` | `_publish_job()` writes the job to `cc:queue:<worker_id>` with Redis `XADD`. |
| Consume and run inference | `service/worker/app/services/job_consumer.py` | `consume_inference_jobs()` reads only the local Worker stream with `XREADGROUP`. |

The selection is shuffled before reservation. Across repeated requests, idle
Workers receive work without a fixed first Worker.

## Ensemble inference

Ensemble inference runs the same image on both Workers, then averages their
probabilities.

| Step | File | Implementation |
| --- | --- | --- |
| Receive execution mode | `service/master/app/schemas/inference_contract.py` | `ExecutionMode.ENSEMBLE` is the explicit request value. |
| Choose the operation | `service/master/app/services/job_dispatcher.py` | `accept_order()` calls `ensemble_inference()` for that mode. |
| Require two Workers | `service/master/app/services/job_dispatcher.py` | `ensemble_inference()` calls `_queue_order(..., required_workers=2)`. |
| Publish two stream messages | `service/master/app/services/job_dispatcher.py` | `_publish_job()` puts the same job payload into each selected Worker stream. |
| Store one result per Worker | `service/worker/app/services/job_consumer.py` | `_process_message()` writes `cc:result:<job_id>:<worker_id>`. |
| Average probabilities | `service/master/app/services/job_status.py` | `_build_result()` sums each label score and divides by the number of Worker results. |

Ensemble is enabled only when two Workers are currently idle. The Master
returns this availability through `GET /inference/workers`, and the UI disables
the ensemble option before uploading an image.

## Job lifecycle and Redis keys

```text
1. Browser uploads an image to POST /inference/images.
2. Master stores the image in RustFS.
3. Master reserves Worker(s) in Redis.
4. Master writes a Redis Stream message for each selected Worker.
5. Worker downloads the image from RustFS and runs ONNX Runtime.
6. Worker stores a temporary result in Redis and acknowledges the Stream entry.
7. Browser polls GET /inference/jobs/<job_id> through SvelteKit.
```

| Redis key | Writer | Reader | Purpose |
| --- | --- | --- | --- |
| `cc:worker:<worker_id>` | Worker heartbeat loop | Master | Current Worker state with expiry. |
| `cc:reservation:<worker_id>` | Master | Master and Worker | Prevents concurrent dispatch to an apparently idle Worker. |
| `cc:queue:<worker_id>` | Master | Matching Worker | Redis Stream containing that Worker's jobs. |
| `cc:job:<job_id>` | Master, then Worker | Master/UI polling | Temporary job metadata and state. |
| `cc:result:<job_id>:<worker_id>` | Worker | Master/UI polling | One Worker result. |

## UI flow section

`client/src/lib/components/distributed-flow.svelte` renders only state that the
browser has already received from the Master API:

- Heartbeat nodes use `GET /inference/workers` data.
- The request route uses the Worker IDs returned after `POST /inference/images`.
- Worker labels change as `GET /inference/jobs/<job_id>` changes from queued to
  processing, succeeded, or failed.
- Heartbeat and active-job dots run once when a fresh state arrives. A completed
  job keeps a slower return-path animation until **Clear result** is pressed:
  green for a successful result and red for a failed result. This represents the
  retained result visible in the UI, not a persistent telemetry connection.
- **Clear result** cancels the local polling revision, clears the selected image,
  removes the retained job state from the browser, and refreshes Worker status.

The component respects `prefers-reduced-motion`.

## Failure behavior

- If a Worker no longer refreshes its heartbeat Hash, it becomes `offline` after
  the TTL expires.
- A Worker reservation prevents two requests from selecting the same idle
  Worker during the interval before its next heartbeat writes `busy`.
- If fewer than one idle Worker exists, load balancing is disabled.
- If fewer than two idle Workers exist, ensemble inference is disabled.
- A Worker exception is stored as a failed result. The job becomes failed if
  any required Worker result fails.
