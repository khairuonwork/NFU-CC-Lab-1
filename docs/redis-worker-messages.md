# Redis Worker Traffic

Master and Workers coordinate through Redis. Workers do not receive inference
requests over HTTP.

| Direction | Operation | Key or stream | Content |
| --- | --- | --- | --- |
| Master -> Worker | `XADD` | `cc:queue:<worker-id>` | Inference job JSON |
| Master -> Worker | `XADD` | `cc:control:<worker-id>` | Manual heartbeat request JSON |
| Worker -> Redis | `HSET` + TTL | `cc:worker:<worker-id>` | State, time, current job |
| Worker -> Redis | `SET` + TTL | `cc:result:<job-id>:<worker-id>` | Inference result JSON |
| Worker -> Redis | `SET` + TTL | `cc:heartbeat-refresh:<request-id>:<worker-id>` | `acknowledged` |
| Worker -> Redis | `XACK` | Original Stream entry | Consumer Group acknowledgement |

## Streams read by one Worker

| Stream | Consumer group | Purpose |
| --- | --- | --- |
| `cc:queue:node1` | `cc-workers` | Inference jobs for Node1 |
| `cc:control:node1` | `cc-worker-controls` | Control actions for Node1 |

Node2 uses the equivalent `node2` streams. A Worker reads only its own streams.

## Inference message

Master writes this value as the Stream `payload` field:

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

`load_balance` goes to one selected idle Worker. `ensemble` writes the same job
ID to both selected Worker streams.

## Manual heartbeat message

The Client calls `POST /inference/workers/refresh`. Master writes this payload
to each control stream:

```json
{
  "schema_version": 1,
  "message_type": "worker_control",
  "command": "publish_heartbeat",
  "request_id": "c098a7a9-f767-4742-bb20-5b4301f27f8e",
  "requested_at": "2026-11-03T10:00:00+00:00"
}
```

The Worker publishes its heartbeat immediately, writes the ACK key, then ACKs
the control Stream entry. Master waits up to
`CC_WORKER_REFRESH_TIMEOUT_SECONDS`, currently 3 seconds.

## Worker-written records

Heartbeat Hash, written every `CC_HEARTBEAT_INTERVAL_SECONDS`, currently 5
seconds:

```json
{
  "worker_id": "node1",
  "state": "idle",
  "last_seen_at": "2026-11-03T10:00:00+00:00",
  "current_job_id": ""
}
```

Result String, written after inference:

```json
{
  "schema_version": 1,
  "job_id": "4dc597d5-2147-459c-a84d-b7159c188071",
  "worker_id": "node1",
  "status": "succeeded",
  "label": "recyclable",
  "probabilities": {"organic": 0.18, "recyclable": 0.82},
  "model_key": "models/baseline-mobilenetv3-small.onnx",
  "elapsed_ms": 83,
  "completed_at": "2026-11-03T10:00:01+00:00",
  "error": null
}
```

`XACK` carries no JSON. It clears the Stream message from pending state. A
restarted Worker reclaims pending inference messages with `XAUTOCLAIM`.
