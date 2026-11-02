import argparse
import shutil
from pathlib import Path
from cc_waste_model.labels import CLASS_LABELS

IMAGE_EXTENSIONS = {
    ".bmp", 
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}

SOURCE_SPLITS = {
    "train": "train",
    "test": "validation",
}

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the waste classification dataset for training."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/raw/waste-classification-organic-recyclable"),
        help="Original dataset directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed"),
        help="Prepared dataset directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing prepared data before copying files.",
    )
    return parser.parse_args()

def normalize_label(directory_name: str) -> str:
    normalized_name = directory_name.strip().casefold()

    if normalized_name == "organic":
        return "organic"

    if normalized_name == "recyclable":
        return "recyclable"

    raise ValueError(
        f"Unsupported class directory: {directory_name}. "
        f"Expected one of: {', '.join(CLASS_LABELS)}"
    )

def find_images(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
    )


def prepare_split(source_split: Path, output_split: Path) -> int:
    copied_images = 0

    for class_directory in sorted(source_split.iterdir()):
        if not class_directory.is_dir():
            continue

        label = normalize_label(class_directory.name)
        destination_directory = output_split / label
        destination_directory.mkdir(parents=True, exist_ok=True)

        for image_path in find_images(class_directory):
            destination_path = destination_directory / image_path.name
            shutil.copy2(image_path, destination_path)
            copied_images += 1

    return copied_images

def main() -> None:
    arguments = parse_arguments()
    source_directory = arguments.source.resolve()
    output_directory = arguments.output.resolve()

    if not source_directory.is_dir():
        raise FileNotFoundError(
            f"Dataset source directory does not exist: {source_directory}"
        )

    if output_directory.exists() and any(output_directory.iterdir()):
        if not arguments.overwrite:
            raise FileExistsError(
                f"Prepared dataset already exists: {output_directory}. "
                "Run again with --overwrite to rebuild it."
            )

        shutil.rmtree(output_directory)

    total_images = 0

    for source_name, output_name in SOURCE_SPLITS.items():
        source_split = source_directory / source_name

        if not source_split.is_dir():
            raise FileNotFoundError(
                f"Expected dataset split does not exist: {source_split}"
            )

        output_split = output_directory / output_name
        copied_images = prepare_split(source_split, output_split)
        total_images += copied_images

        print(f"{output_name}: copied {copied_images} images")

    print(f"Prepared {total_images} images in: {output_directory}")


if __name__ == "__main__":
    main()