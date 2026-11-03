# Redis Worker Traffic

This document lists every Redis record used between the Master and a Worker.
Redis is the meeting point; the Master and Workers do not call each other over
HTTP during inference.

## Traffic overview

| Direction | Redis operation | Key or stream | Data written | Read by |
| --- | --- | --- | --- | --- |
| Master → Worker | `XADD` | `cc:queue:<worker-id>` | Inference job JSON in `payload` | Target Worker only |
| Master → Worker | `XADD` | `cc:control:<worker-id>` | Manual heartbeat request JSON in `payload` | Target Worker only |
| Worker → Master | `HSET` + TTL | `cc:worker:<worker-id>` | Current Worker state and `last_seen_at` | Master and UI status endpoint |
| Worker → Master | `SET` + TTL | `cc:result:<job-id>:<worker-id>` | Inference result JSON | Master job-status endpoint |
| Worker → Master | `SET` + TTL | `cc:heartbeat-refresh:<request-id>:<worker-id>` | `acknowledged` | Master manual-refresh endpoint |
| Worker → Redis | `XACK` | Original Stream entry | No payload; confirms one message was consumed | Redis Consumer Group |

The Master reads Worker-originated records. It does not receive a direct TCP
callback from a Worker.

## Stream names

| Stream | Target | Consumer group | Purpose |
| --- | --- | --- | --- |
| `cc:queue:<worker-id>` | One Worker | `cc-workers` | Run one inference job. |
| `cc:control:<worker-id>` | One Worker | `cc-worker-controls` | Run a small control action without executing inference. |

For example, Node1 reads `cc:queue:node1` and `cc:control:node1`. Node2 never
consumes either Node1 stream.

## Inference job

The Master uses `XADD cc:queue:<worker-id>` after it reserves a Worker. The
Stream entry has one field named `payload`, containing this JSON document:

```json
{
  "schema_version": 1,
  "job_id": "4dc597d5-2147-459c-a84d-b7159c188071",
  "job_type": "inference",
  "execution_mode": "load_balance",
  "image_key": "uploads/inference/4dc597d5-2147-459c-a84d-b7159c188071.jpg",
  "submitted_at": "2026-11-03T10:00:00+00:00"
}
```

`execution_mode` explains the request intent:

- `load_balance`: the Master writes the job to one selected idle Worker.
- `ensemble`: the Master writes the same `job_id` to both selected Worker
  streams. Each Worker produces one independent probability distribution.

The Worker downloads `image_key` from RustFS, runs ONNX inference, writes its
temporary result to `cc:result:<job-id>:<worker-id>`, then ACKs the Stream entry.

## Manual heartbeat request

The UI's **Retry worker connection** button calls
`POST /inference/workers/refresh`. The Master writes one control message to
each `cc:control:<worker-id>` stream.

```json
{
  "schema_version": 1,
  "message_type": "worker_control",
  "command": "publish_heartbeat",
  "request_id": "c098a7a9-f767-4742-bb20-5b4301f27f8e",
  "requested_at": "2026-11-03T10:00:00+00:00"
}
```

When a Worker consumes `publish_heartbeat`, it immediately refreshes its own
`cc:worker:<worker-id>` hash and creates this short-lived acknowledgement key:

```text
cc:heartbeat-refresh:<request-id>:<worker-id>
```

The Master waits up to `CC_WORKER_REFRESH_TIMEOUT_SECONDS` for those keys, then
returns both acknowledged and unresponsive Worker IDs to the UI. A missing
acknowledgement does not prove a VM is permanently down; it means that Worker
did not consume the control message within the requested window.

## Why Stream control instead of Redis Pub/Sub

The manual heartbeat is a command with an acknowledgement, not a broadcast
notification. Redis Streams retain the message until the Worker consumer group
ACKs it. Pub/Sub would drop the request if a Worker were briefly disconnected,
which would make the UI unable to distinguish a missed notification from a
non-responsive Worker.

## Worker heartbeat record

Each Worker writes this hash automatically every
`CC_HEARTBEAT_INTERVAL_SECONDS` seconds. The manual control request writes the
same record immediately instead of waiting for the next scheduled interval.

```json
{
  "worker_id": "node1",
  "state": "idle",
  "last_seen_at": "2026-11-03T10:00:00+00:00",
  "current_job_id": ""
}
```

The key is `cc:worker:node1` for Node1 and `cc:worker:node2` for Node2. Redis
removes the key after `CC_HEARTBEAT_TTL_SECONDS` unless the Worker refreshes it.
The Master reports a missing key as `offline`.

## Worker inference result

After a Worker finishes an inference job, it writes one temporary JSON record:

```json
{
  "schema_version": 1,
  "job_id": "4dc597d5-2147-459c-a84d-b7159c188071",
  "worker_id": "node1",
  "status": "succeeded",
  "label": "recyclable",
  "probabilities": {
    "organic": 0.18,
    "recyclable": 0.82
  },
  "model_key": "models/baseline-mobilenetv3-small.onnx",
  "elapsed_ms": 83,
  "completed_at": "2026-11-03T10:00:01+00:00",
  "error": null
}
```

The result key is:

```text
cc:result:<job-id>:<worker-id>
```

For load balancing, the Master returns the single assigned Worker's result. For
ensemble inference, the Master reads both result keys and averages each label's
probability before choosing the highest averaged label.

## Stream acknowledgement

After writing either a successful or failed inference result, a Worker runs
`XACK` for the original `cc:queue:<worker-id>` entry. After a manual heartbeat,
it runs `XACK` for the original `cc:control:<worker-id>` entry.

`XACK` has no JSON body. It changes Consumer Group state so Redis no longer
marks the entry as pending. If a Worker stops before acknowledging an inference
message, the Worker reclaims that pending message after restart with
`XAUTOCLAIM`.
