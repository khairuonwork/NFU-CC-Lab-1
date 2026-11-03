# Master–Worker Protocol

This document defines the first runtime contract between the master controller and a worker.

See [Redis Worker Messages](../docs/redis-worker-messages.md) for every Redis
Stream message addressed to a Worker, including the manual heartbeat control
message.

## Scope

Version 1 covers inference only. Training will use a separate contract after the inference path works end-to-end.

## Redis keys

| Key | Redis type | Purpose |
| --- | --- | --- |
| `cc:worker:node1` | Hash with TTL | Node1 heartbeat and current state |
| `cc:worker:node2` | Hash with TTL | Node2 heartbeat and current state |
| `cc:queue:node1` | Stream | Inference jobs reserved for Node1 |
| `cc:queue:node2` | Stream | Inference jobs reserved for Node2 |
| `cc:control:node1` | Stream | Manual control messages for Node1 |
| `cc:control:node2` | Stream | Manual control messages for Node2 |
| `cc:result:<job-id>:<worker-id>` | String with TTL | Temporary inference result |
| `cc:job:<job-id>` | Hash with TTL | Temporary job metadata for UI polling |

A worker refreshes its own `cc:worker:<worker-id>` key. The master treats a missing key as offline.

## Worker availability for the UI

The UI calls `GET /inference/workers` before enabling an execution button. The Master reads both heartbeat hashes and their short reservation keys, then returns the worker state currently usable for dispatching.

```json
{
  "workers": [
    {
      "worker_id": "node1",
      "state": "idle",
      "available": true,
      "last_seen_at": "2026-10-28T10:00:00+00:00",
      "current_job_id": null
    },
    {
      "worker_id": "node2",
      "state": "training",
      "available": false,
      "last_seen_at": "2026-10-28T10:00:00+00:00",
      "current_job_id": "4dc597d5-2147-459c-a84d-b7159c188071"
    }
  ],
  "available_workers": 1,
  "execution_modes": {
    "load_balance": {
      "enabled": true,
      "required_workers": 1,
      "available_workers": 1
    },
    "ensemble": {
      "enabled": false,
      "required_workers": 2,
      "available_workers": 1
    }
  }
}
```

A worker with an active dispatch reservation is reported as `reserved`, even if its last heartbeat still says `idle`. This prevents the UI from presenting a stale available state during dispatch.

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

The master accepts `multipart/form-data` at `POST /inference/images`. The client must provide an image file and an explicit `execution_mode`. The master accepts JPG, JPEG, PNG, and WEBP files up to the configured upload limit, verifies that the file content matches its extension, then stores it under `uploads/inference/<uuid>.<suffix>`.

The uploaded object is deleted when every assigned worker has returned a result. If no worker can be reserved, the master deletes it immediately. A timed-out job retains its input temporarily because a late worker may still be reading it. The Master also removes any inference upload older than the configured retention window, including jobs whose browser session was closed.

## Inference order

The UI sends an `InferenceOrder` to `POST /inference/orders` when its image already exists in RustFS. An order states the user intent; it is not yet a worker message. The Master reads `execution_mode` and calls either `load_balance()` or `ensemble_inference()` explicitly.

```json
{
  "image_key": "uploads/inference/4dc597d5-2147-459c-a84d-b7159c188071.jpg",
  "execution_mode": "ensemble"
}
```

## Inference job

The master writes one JSON payload into the selected worker stream using `XADD cc:queue:<worker-id> payload '<json>'`. Each stream keeps only the configured maximum number of entries so acknowledged inference history does not grow without bound. The worker downloads `image_key` from RustFS and uses the model configured for that worker.

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
    "recyclable": 0.06
  },
  "model_key": "models/baseline-mobilenetv3-small.onnx",
  "elapsed_ms": 83,
  "completed_at": "2026-10-28T10:00:01Z"
}
```

A failed result has `status: "failed"` and an `error` string instead of classification output.

## Job timeout

The master derives a job timeout from `submitted_at`. If the configured timeout passes before every assigned worker returns a result, `GET /inference/jobs/<job-id>` returns `status: "failed"`, `reason: "job_timeout"`, and `missing_worker_ids`. The UI can show a clear failure instead of polling until the Redis job TTL expires.

## Pending job recovery

A worker acknowledges a Stream message only after it has written its Redis result. If the worker process stops first, that message stays pending in its Consumer Group. On restart, the worker uses `XAUTOCLAIM` to reclaim one pending message that has been idle for at least `CC_PENDING_JOB_RECLAIM_IDLE_MS`. If the result already exists, it only acknowledges the old message; otherwise it processes the job normally.

## Model contract

Every worker runs a MobileNetV3-Small ONNX model with the same versioned contract. Both workers currently use the same RustFS model object: `models/baseline-mobilenetv3-small.onnx`.
Each Worker VM downloads and caches its own local copy, while RustFS remains
the source of truth.

| Field | Value |
| --- | --- |
| Model input | RGB image tensor in NCHW order |
| Input shape | `1 × 3 × 224 × 224` |
| Value range before normalization | `0.0` to `1.0` |
| Mean | `(0.485, 0.456, 0.406)` |
| Standard deviation | `(0.229, 0.224, 0.225)` |
| Class `0` | `organic` |
| Class `1` | `recyclable` |
| Model output | Raw logits with shape `1 × 2` |

The training and ONNX export pipeline must preserve this exact class order. Ensemble averaging is valid only when both workers use compatible label indexes and preprocessing.

## Worker cache

Before inference, a worker downloads `image_key` to `CC_WORKER_CACHE_DIR`. The cache is a temporary local copy only. The worker removes the file after it produces either a successful or failed result, so RustFS remains the source of truth for the uploaded image.

A model is cached separately under `CC_MODEL_CACHE_DIR`. The default is temporary storage. Docker deployment may mount this directory as a volume when model reuse across restarts is needed; RustFS remains the source of truth and `CC_MODEL_KEY` identifies the desired artifact.
