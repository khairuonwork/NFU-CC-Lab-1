from dataclasses import dataclass
from pathlib import Path

import torch
from torch import Tensor, nn, optim
from torch.utils.data import DataLoader
from torchvision.models import (
    MobileNet_V3_Small_Weights,
    mobilenet_v3_small,
)

from cc_waste_model.labels import (
    CLASS_LABELS,
    IMAGE_NET_MEAN,
    IMAGE_NET_STANDARD_DEVIATION,
    MODEL_INPUT_HEIGHT,
    MODEL_INPUT_WIDTH,
)

@dataclass
class EpochMetrics:
    loss: float
    accuracy: float

def select_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")

    if torch.cuda.is_available():
        return torch.device("cuda")

    return torch.device("cpu")

def create_model(use_pretrained_weights: bool) -> nn.Module:
    weights = (
        MobileNet_V3_Small_Weights.DEFAULT
        if use_pretrained_weights
        else None
    )

    model = mobilenet_v3_small(weights=weights)

    classifier_layer = model.classifier[3]

    if not isinstance(classifier_layer, nn.Linear):
        raise TypeError("Expected the final MobileNet classifier layer to be Linear")

    model.classifier[3] = nn.Linear(
        in_features=classifier_layer.in_features,
        out_features=len(CLASS_LABELS),
    )

    return model

def run_epoch(
    model: nn.Module,
    data_loader: DataLoader[tuple[Tensor, Tensor]],
    loss_function: nn.Module,
    device: torch.device,
    optimizer: optim.Optimizer | None = None,
) -> EpochMetrics:
    is_training = optimizer is not None

    if is_training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_correct = 0
    total_images = 0

    for images, labels in data_loader:
        images = images.to(device)
        labels = labels.to(device)

        if is_training:
            optimizer.zero_grad()

        with torch.set_grad_enabled(is_training):
            logits = model(images)
            loss = loss_function(logits, labels)

            if is_training:
                loss.backward()
                optimizer.step()

        predictions = logits.argmax(dim=1)
        total_loss += loss.item() * images.size(0)
        total_correct += (predictions == labels).sum().item()
        total_images += images.size(0)

    return EpochMetrics(
        loss=total_loss / total_images,
        accuracy=total_correct / total_images,
    )

def save_checkpoint(
    model: nn.Module,
    output_path: Path,
    epoch: int,
    validation_metrics: EpochMetrics,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cpu_state_dict = {
        name: parameter.detach().cpu()
        for name, parameter in model.state_dict().items()
    }

    torch.save(
        {
            "architecture": "mobilenet_v3_small",
            "class_labels": list(CLASS_LABELS),
            "image_input": {
                "channels": 3,
                "height": MODEL_INPUT_HEIGHT,
                "width": MODEL_INPUT_WIDTH,
            },
            "normalization": {
                "mean": IMAGE_NET_MEAN,
                "standard_deviation": IMAGE_NET_STANDARD_DEVIATION,
            },
            "epoch": epoch,
            "validation_loss": validation_metrics.loss,
            "validation_accuracy": validation_metrics.accuracy,
            "model_state_dict": cpu_state_dict,
        },
        output_path,
    )