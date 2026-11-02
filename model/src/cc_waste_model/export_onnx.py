from pathlib import Path
import onnx
import onnxruntime
import torch
from torch import nn

from cc_waste_model.labels import (
    CLASS_LABELS,
    MODEL_INPUT_CHANNELS,
    MODEL_INPUT_HEIGHT,
    MODEL_INPUT_WIDTH,
)
from cc_waste_model.train import create_model

def load_model_from_checkpoint(checkpoint_path: Path) -> nn.Module:
    checkpoint = torch.load(
        checkpoint_path,
        map_location=torch.device("cpu"),
        weights_only=True,
    )

    if checkpoint["architecture"] != "mobilenet_v3_small":
        raise ValueError(
            f"Unsupported model architecture: {checkpoint['architecture']}"
        )

    if checkpoint["class_labels"] != list(CLASS_LABELS):
        raise ValueError(
            "Checkpoint labels do not match the current model contract."
        )

    model = create_model(use_pretrained_weights=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    return model


def export_checkpoint_to_onnx(
    checkpoint_path: Path,
    output_path: Path,
) -> None:
    if not checkpoint_path.is_file():
        raise FileNotFoundError(
            f"Checkpoint does not exist: {checkpoint_path}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = load_model_from_checkpoint(checkpoint_path)

    example_input = torch.randn(
        1,
        MODEL_INPUT_CHANNELS,
        MODEL_INPUT_HEIGHT,
        MODEL_INPUT_WIDTH,
    )

    torch.onnx.export(
    model,
    example_input,
    str(output_path),
    input_names=["image"],
    output_names=["logits"],
    opset_version=18,
    external_data=False,
)

    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)

    session = onnxruntime.InferenceSession(
        str(output_path),
        providers=["CPUExecutionProvider"],
    )

    input_name = session.get_inputs()[0].name
    outputs = session.run(
        None,
        {
            input_name: example_input.numpy(),
        },
    )

    output_shape = tuple(outputs[0].shape)
    expected_shape = (1, len(CLASS_LABELS))

    if output_shape != expected_shape:
        raise ValueError(
            f"Unexpected ONNX output shape: {output_shape}. "
            f"Expected: {expected_shape}"
        )