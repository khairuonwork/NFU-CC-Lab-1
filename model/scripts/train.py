import argparse
import random
from pathlib import Path
import torch
from torch import nn, optim

from cc_waste_model.dataset import (
    WasteImageDataset,
    create_data_loader,
    create_train_transform,
    create_validation_transform,
)
from cc_waste_model.train import (
    create_model,
    run_epoch,
    save_checkpoint,
    select_device,
)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a MobileNetV3-Small waste classifier."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/checkpoints/baseline-mobilenetv3-small.pt"),
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.0001,
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )
    parser.add_argument(
        "--no-pretrained-weights",
        action="store_true",
    )
    return parser.parse_args()

def main() -> None:
    arguments = parse_arguments()

    random.seed(arguments.seed)
    torch.manual_seed(arguments.seed)

    device = select_device()
    print(f"device: {device}")

    train_dataset = WasteImageDataset(
        arguments.data / "train",
        create_train_transform(),
    )
    validation_dataset = WasteImageDataset(
        arguments.data / "validation",
        create_validation_transform(),
    )

    train_loader = create_data_loader(
        dataset=train_dataset,
        batch_size=arguments.batch_size,
        shuffle=True,
        num_workers=arguments.num_workers,
    )
    validation_loader = create_data_loader(
        dataset=validation_dataset,
        batch_size=arguments.batch_size,
        shuffle=False,
        num_workers=arguments.num_workers,
    )

    print(f"train images: {len(train_dataset)}")
    print(f"train class counts: {train_dataset.class_counts()}")
    print(f"validation images: {len(validation_dataset)}")
    print(f"validation class counts: {validation_dataset.class_counts()}")

    model = create_model(
        use_pretrained_weights=not arguments.no_pretrained_weights
    ).to(device)

    loss_function = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(
        model.parameters(),
        lr=arguments.learning_rate,
    )

    best_validation_accuracy = 0.0

    for epoch in range(1, arguments.epochs + 1):
        train_metrics = run_epoch(
            model=model,
            data_loader=train_loader,
            loss_function=loss_function,
            device=device,
            optimizer=optimizer,
        )
        validation_metrics = run_epoch(
            model=model,
            data_loader=validation_loader,
            loss_function=loss_function,
            device=device,
        )

        print(
            f"epoch {epoch}/{arguments.epochs} | "
            f"train loss={train_metrics.loss:.4f} | "
            f"train accuracy={train_metrics.accuracy:.2%} | "
            f"validation loss={validation_metrics.loss:.4f} | "
            f"validation accuracy={validation_metrics.accuracy:.2%}"
        )

        if validation_metrics.accuracy >= best_validation_accuracy:
            best_validation_accuracy = validation_metrics.accuracy

            save_checkpoint(
                model=model,
                output_path=arguments.output,
                epoch=epoch,
                validation_metrics=validation_metrics,
            )

            print(f"saved checkpoint: {arguments.output}")

if __name__ == "__main__":
    main()