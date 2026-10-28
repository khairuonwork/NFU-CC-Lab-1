import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy
import onnxruntime
from PIL import Image

from app.core.config import Settings
from app.core.model_contract import (
    CLASS_LABELS,
    IMAGE_NET_MEAN,
    IMAGE_NET_STANDARD_DEVIATION,
    MODEL_INPUT_HEIGHT,
    MODEL_INPUT_WIDTH,
)
from app.services.object_storage import download_model

# Run one compatible MobileNetV3-Small ONNX model on this worker.
@dataclass
class OnnxImageClassifier:
    session: onnxruntime.InferenceSession
    input_name: str
    output_name: str

    # Keep the blocking Pillow and ONNX work outside the async event loop.
    async def classify(self, image_path: Path) -> tuple[str, dict[str, float]]:
        return await asyncio.to_thread(self._classify_sync, image_path)

    def _classify_sync(self, image_path: Path) -> tuple[str, dict[str, float]]:
        tensor = _prepare_input(image_path)
        output = self.session.run([self.output_name], {self.input_name: tensor})[0]
        probabilities = _softmax(numpy.asarray(output).reshape(-1))

        if probabilities.size != len(CLASS_LABELS):
            raise ValueError(
                "Model output count does not match the configured class contract"
            )

        scores = {
            label: float(probability)
            for label, probability in zip(CLASS_LABELS, probabilities, strict=True)
        }
        label = max(scores, key=scores.get)
        return label, scores

# Download the model once, then create one reusable CPU inference session.
async def create_model_runtime(
    rustfs: Any,
    settings: Settings,
) -> OnnxImageClassifier:
    model_path = await download_model(rustfs, settings)
    session = await asyncio.to_thread(
        onnxruntime.InferenceSession,
        str(model_path),
        providers=["CPUExecutionProvider"],
    )

    if len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1:
        raise ValueError("The worker model must have exactly one input and one output")

    return OnnxImageClassifier(
        session=session,
        input_name=session.get_inputs()[0].name,
        output_name=session.get_outputs()[0].name,
    )

# Convert an uploaded image into the model tensor defined by model_contract.py.
def _prepare_input(image_path: Path) -> numpy.ndarray:
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        resized_image = rgb_image.resize(
            (MODEL_INPUT_WIDTH, MODEL_INPUT_HEIGHT),
            Image.Resampling.BILINEAR,
        )
        pixels = numpy.asarray(resized_image, dtype=numpy.float32) / 255.0

    normalized = (
        pixels - numpy.asarray(IMAGE_NET_MEAN, dtype=numpy.float32)
    ) / numpy.asarray(IMAGE_NET_STANDARD_DEVIATION, dtype=numpy.float32)
    return numpy.transpose(normalized, (2, 0, 1))[numpy.newaxis, ...]

# Convert the three raw ONNX logits into a probability distribution.
def _softmax(logits: numpy.ndarray) -> numpy.ndarray:
    shifted_logits = logits - numpy.max(logits)
    exponentials = numpy.exp(shifted_logits)
    return exponentials / numpy.sum(exponentials)
