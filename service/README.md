# Services

| Directory | Runtime | Role |
| --- | --- | --- |
| `master/` | NodeMaster | FastAPI controller, Redis dispatch, RustFS access |
| `worker/` | Node1 and Node2 | Redis Stream consumer, ONNX Runtime inference |

Both Workers use the same image with different `CC_WORKER_ID` values.

See [Master-Worker Protocol](PROTOCOL.md) for API, Redis, model, and failure
rules.
