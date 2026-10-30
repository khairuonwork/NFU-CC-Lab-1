CLASS_LABELS = (
    "organic",
    "recyclable",
)

CLASS_TO_INDEX = {
    label: index
    for index, label in enumerate(CLASS_LABELS)
}

INDEX_TO_CLASS = dict(enumerate(CLASS_LABELS))

MODEL_INPUT_WIDTH = 224
MODEL_INPUT_HEIGHT = 224
MODEL_INPUT_CHANNELS = 3

IMAGE_NET_MEAN = (0.485, 0.456, 0.406)
IMAGE_NET_STANDARD_DEVIATION = (0.229, 0.224, 0.225)