# Shared inference contract for every worker model.
MODEL_SCHEMA_VERSION = 1
MODEL_INPUT_WIDTH = 224
MODEL_INPUT_HEIGHT = 224
MODEL_INPUT_CHANNELS = 3

# Class index order must stay identical across every ensemble model.
CLASS_LABELS = (
    "organic",
    "recyclable"
)

# MobileNetV3-Small uses RGB input normalized with ImageNet statistics.
IMAGE_NET_MEAN = (0.485, 0.456, 0.406)
IMAGE_NET_STANDARD_DEVIATION = (0.229, 0.224, 0.225)
