import argparse
from pathlib import Path
from cc_waste_model.export_onnx import export_checkpoint_to_onnx

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a trained PyTorch checkpoint to ONNX."
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "artifacts/checkpoints/baseline-mobilenetv3-small.pt"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/onnx/baseline-mobilenetv3-small.onnx"
        ),
    )
    return parser.parse_args()

def main() -> None:
    arguments = parse_arguments()

    export_checkpoint_to_onnx(
        checkpoint_path=arguments.checkpoint,
        output_path=arguments.output,
    )

    print(f"exported ONNX model: {arguments.output}")

if __name__ == "__main__":
    main()