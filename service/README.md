# Python Services

- `master/` runs once on NodeMaster as the controller API.
- `worker/` is one generic worker application. The same Docker image will later run on Node1 and Node2 with different `WORKER_ID` values.

Docker and application logic will be added after the runtime contracts are agreed.
