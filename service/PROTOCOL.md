# Master-Worker Protocol

Scope: inference for one Master and two Workers. Training has no runtime
contract yet.

Detailed Redis payloads: [Redis Worker Traffic](../docs/redis-worker-messages.md).

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /inference/workers` | Worker state and execution-mode availability |
| `POST /inference/workers/refresh` | Request an immediate heartbeat from each Worker |
| `POST /inference/images` | Upload image, create order, queue job |
| `POST /inference/orders` | Queue an existing RustFS image |
| `GET /inference/jobs/<job-id>` | Temporary job state and result |

## Redis keys

| Key | Type | Writer | Purpose |
| --- | --- | --- | --- |
| `cc:worker:<worker-id>` | Hash with TTL | Worker | Heartbeat and state |
| `cc:reservation:<worker-id>` | String with TTL | Master | Dispatch lock |
| `cc:queue:<worker-id>` | Stream | Master | Inference job for one Worker |
| `cc:control:<worker-id>` | Stream | Master | Manual Worker control |
| `cc:job:<job-id>` | Hash with TTL | Master, Worker | Temporary job metadata |
| `cc:result:<job-id>:<worker-id>` | String with TTL | Worker | One inference result |

## Worker state

Worker writes its own heartbeat every 5 seconds. The Hash TTL is 15 seconds.
Master reports a missing Hash as `offline`.

Allowed states: `idle`, `busy`, `training`. A Worker with an active reservation
is returned as `reserved` so another request cannot select it.

## Inference

1. Master stores the image in RustFS.
2. Master reserves idle Worker(s) with `SET NX EX`.
3. Master writes one job JSON payload to each selected Worker Stream.
4. Worker downloads the image, runs ONNX, writes one result, then `XACK`s.
5. Master returns one result for load balancing or averages label probabilities for ensemble.

`load_balance` requires one idle Worker. `ensemble` requires two and writes the
same `job_id` to both Worker Streams.

## Result and failure rules

- A result has `status: succeeded` or `status: failed`.
- Master marks a job failed after `CC_JOB_TIMEOUT_SECONDS` if required results are missing.
- Worker restarts reclaim pending inference messages with `XAUTOCLAIM`.
- Uploaded inference images are deleted after every assigned Worker finishes.

## Model contract

Both Workers use `models/baseline-mobilenetv3-small.onnx` from RustFS.

| Field | Value |
| --- | --- |
| Input | RGB, NCHW, `1 × 3 × 224 × 224` |
| Input range | `0.0` to `1.0` before normalization |
| Mean | `(0.485, 0.456, 0.406)` |
| Standard deviation | `(0.229, 0.224, 0.225)` |
| Labels | `organic`, `recyclable` |
| Output | Logits `1 × 2` |

All ensemble models must use this preprocessing and label order.
