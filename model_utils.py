from io import BytesIO

import numpy as np
from PIL import Image


IMAGE_SIZE = (32, 32)


def extract_image_features(image_bytes):
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image = image.resize(IMAGE_SIZE)
    pixels = np.asarray(image, dtype=np.float32) / 255.0

    color_features = pixels.reshape(-1)
    histogram_features = np.concatenate([
        np.histogram(pixels[:, :, channel], bins=16, range=(0, 1), density=True)[0]
        for channel in range(3)
    ])

    grayscale = pixels.mean(axis=2)
    horizontal_edges = np.abs(np.diff(grayscale, axis=1)).mean()
    vertical_edges = np.abs(np.diff(grayscale, axis=0)).mean()
    texture_features = np.array([
        grayscale.mean(),
        grayscale.std(),
        horizontal_edges,
        vertical_edges,
    ], dtype=np.float32)

    return np.concatenate([color_features, histogram_features, texture_features])
