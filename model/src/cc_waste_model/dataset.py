from collections import Counter
from pathlib import Path

import torch
from PIL import Image
from torch import Tensor
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from cc_waste_model.labels import (
    CLASS_LABELS,
    CLASS_TO_INDEX,
    IMAGE_NET_MEAN,
    IMAGE_NET_STANDARD_DEVIATION,
    MODEL_INPUT_HEIGHT,
    MODEL_INPUT_WIDTH,
)

IMAGE_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}


class WasteImageDataset(Dataset[tuple[Tensor, int]]):
    # Read one prepared dataset split and return image tensors with class indices.
    def __init__(self, directory: Path, transform: transforms.Compose) -> None:
        self.directory = directory
        self.transform = transform
        self.samples = self._collect_samples()

    def _collect_samples(self) -> list[tuple[Path, int]]:
        if not self.directory.is_dir():
            raise FileNotFoundError(
                f"Dataset split directory does not exist: {self.directory}"
            )

        samples: list[tuple[Path, int]] = []

        for label in CLASS_LABELS:
            class_directory = self.directory / label

            if not class_directory.is_dir():
                raise FileNotFoundError(
                    f"Expected class directory does not exist: {class_directory}"
                )

            for image_path in sorted(class_directory.rglob("*")):
                if (
                    image_path.is_file()
                    and image_path.suffix.casefold() in IMAGE_EXTENSIONS
                ):
                    samples.append((image_path, CLASS_TO_INDEX[label]))

        if not samples:
            raise ValueError(f"No supported image files found in: {self.directory}")

        return samples

    def class_counts(self) -> dict[str, int]:
        counts = Counter(label_index for _, label_index in self.samples)

        return {
            label: counts[CLASS_TO_INDEX[label]]
            for label in CLASS_LABELS
        }

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Tensor, int]:
        image_path, label_index = self.samples[index]

        with Image.open(image_path) as image:
            image_tensor = self.transform(image.convert("RGB"))

        return image_tensor, label_index


def create_train_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(
                (MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH),
                scale=(0.8, 1.0),
            ),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=IMAGE_NET_MEAN,
                std=IMAGE_NET_STANDARD_DEVIATION,
            ),
        ]
    )


def create_validation_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(
                (MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH)
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=IMAGE_NET_MEAN,
                std=IMAGE_NET_STANDARD_DEVIATION,
            ),
        ]
    )


def create_data_loader(
    dataset: WasteImageDataset,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
) -> DataLoader[tuple[Tensor, Tensor]]:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.backends.mps.is_available(),
    )