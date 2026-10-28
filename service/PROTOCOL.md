# Master–Worker Protocol

This document defines the first runtime contract between the master controller and a worker.

## Scope

Version 1 covers inference only. Training will use a separate contract after the inference path works end-to-end.

## Redis keys

| Key | Redis type | Purpose |
| --- | --- | --- |
| `cc:worker:node1` | Hash with TTL | Node1 heartbeat and current state |
| `cc:worker:node2` | Hash with TTL | Node2 heartbeat and current state |
| `cc:queue:node1` | Stream | Inference jobs reserved for Node1 |
| `cc:queue:node2` | Stream | Inference jobs reserved for Node2 |
| `cc:result:<job-id>:<worker-id>` | String with TTL | Temporary inference result |
| `cc:job:<job-id>` | Hash with TTL | Temporary job metadata for UI polling |

A worker refreshes its own `cc:worker:<worker-id>` key. The master treats a missing key as offline.

## Worker heartbeat fields

```json
{
  "worker_id": "node1",
  "state": "idle",
  "last_seen_at": "2026-10-28T10:00:00Z",
  "current_job_id": null
}
```

Allowed `state` values are `idle`, `busy`, and `training`.

## Image upload

The master accepts `multipart/form-data` at `POST /inference/images`. The client must provide an image file and an explicit `execution_mode`. The master stores the file under `uploads/inference/<uuid>.<suffix>` before it writes the inference job to Redis. If no worker can be reserved, the master deletes that newly uploaded object.

## Inference job

The master writes one JSON payload into the selected worker stream using `XADD cc:queue:<worker-id> payload '<json>'`. The worker downloads `image_key` from RustFS and uses the model configured for that worker.

```json
{
  "schema_version": 1,
  "job_id": "4dc597d5-2147-459c-a84d-b7159c188071",
  "job_type": "inference",
  "execution_mode": "load_balance",
  "image_key": "uploads/inference/4dc597d5-2147-459c-a84d-b7159c188071.jpg",
  "submitted_at": "2026-10-28T10:00:00Z"
}
```

`execution_mode` can be:

- `load_balance`: the master writes one job to one idle worker.
- `ensemble`: the master writes the same `job_id` to both worker streams. Each worker uses its own configured model. The master averages their returned class probabilities.

The stream destination identifies the worker. The job does not contain a shell command, local path, or arbitrary model path.

## Inference result

The worker writes a short-lived result under `cc:result:<job-id>:<worker-id>`.

```json
{
  "schema_version": 1,
  "job_id": "4dc597d5-2147-459c-a84d-b7159c188071",
  "worker_id": "node1",
  "status": "succeeded",
  "label": "organic",
  "probabilities": {
    "organic": 0.94,
    "anorganic": 0.05,
    "electronic": 0.01
  },
  "model_key": "models/model-a/current.onnx",
  "elapsed_ms": 83,
  "completed_at": "2026-10-28T10:00:01Z"
}
```

A failed result has `status: "failed"` and an `error` string instead of classification output.

## Worker cache

Before inference, a worker downloads `image_key` to `CC_WORKER_CACHE_DIR`. The cache is a temporary local copy only. The worker removes the file after it produces either a successful or failed result, so RustFS remains the source of truth for the uploaded image.
