# Waste Model

MobileNetV3-Small classifies `organic` and `recyclable` waste images.

| Path | Purpose |
| --- | --- |
| `data/raw/` | Source dataset, ignored by Git |
| `data/processed/` | Prepared train and validation splits |
| `artifacts/checkpoints/` | PyTorch checkpoints, ignored by Git |
| `artifacts/onnx/` | Exported ONNX artifact, ignored by Git |
| `scripts/` | Dataset preparation, training, ONNX export |

The deployed object key is `models/baseline-mobilenetv3-small.onnx` in RustFS.
