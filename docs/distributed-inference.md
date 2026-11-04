# Distributed Inference

## Runtime

```text
Browser -> SvelteKit -> Master API -> Redis -> Node1 / Node2
                               |                 |
                               +---- RustFS <-----+
```

The browser calls only the Master API. Redis coordinates Workers. RustFS stores
uploaded images and the ONNX artifact.

| Component | Responsibility | Main file |
| --- | --- | --- |
| Master | Select Workers, reserve them, publish jobs, combine results | `service/master/app/services/job_dispatcher.py` |
| Worker | Read its Redis Stream, run ONNX, write one result | `service/worker/app/services/job_consumer.py` |
| Heartbeat | Publish Worker state to Redis | `service/worker/app/services/heartbeat.py` |
| Client | Read Worker state, submit images, poll job state | `client/src/routes/+page.svelte` |

## Heartbeat

Each Worker writes `cc:worker:<worker-id>` to Redis every 5 seconds. The Hash
expires after 15 seconds. The Master treats a missing Hash as `offline`.

```text
Worker -> HSET cc:worker:node1 -> Redis
Master -> HGETALL cc:worker:node1 -> Worker status API
```

The Client refreshes Worker status every 8 seconds. Its manual retry button
sends a control Stream request and waits up to 3 seconds for a fresh Worker ACK.

## Execution modes

| Mode | Worker requirement | Redis writes | Result |
| --- | --- | --- | --- |
| Load balancing | One idle Worker | One `cc:queue:<worker-id>` entry | One Worker result |
| Ensemble | Two idle Workers | Same job ID in both Worker streams | Mean probability per label |

`JobDispatcher.accept_order()` calls `load_balance()` or
`ensemble_inference()` in `service/master/app/services/job_dispatcher.py`.

For ensemble, `service/master/app/services/job_status.py` sums each label score
and divides it by `len(worker_results)`. The largest averaged probability is the
final label.

## Job flow

1. Client uploads an image to `POST /inference/images`.
2. Master stores it in RustFS and reserves Worker(s) with Redis `SET NX EX`.
3. Master writes one inference message per selected Worker Stream.
4. Worker downloads the image, runs ONNX Runtime, writes a temporary result, then ACKs.
5. Client polls `GET /inference/jobs/<job-id>`.
6. Master deletes the uploaded image after all assigned Workers finish.

## Failure rules

- No heartbeat Hash after its TTL: Worker is `offline`.
- Active reservation: Worker is `reserved`, even if its latest heartbeat says `idle`.
- No idle Worker: load balancing is disabled.
- Fewer than two idle Workers: ensemble is disabled.
- Failed Worker result or job timeout: job status is `failed`.
- Pending inference messages are reclaimed after restart with `XAUTOCLAIM`.

See [Redis Worker Traffic](redis-worker-messages.md) for Redis keys and payloads.
