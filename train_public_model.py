from io import BytesIO
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from model_utils import extract_image_features


DATASET_PATH = Path(
    "data/public/mit_landslides/data/train-00000-of-00001.parquet"
)
MODEL_PATH = Path("image_model.joblib")
RANDOM_STATE = 42
CLASS_NAMES = ["background", "landslide"]


def image_bytes(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def crop_for_box(image, box):
    x, y, width, height = box
    padding = max(width, height) * 0.15
    left = max(0, int(x - padding))
    top = max(0, int(y - padding))
    right = min(image.width, int(x + width + padding))
    bottom = min(image.height, int(y + height + padding))
    return image.crop((left, top, right, bottom))


def overlaps_box(left, top, size, box):
    x, y, width, height = box
    right = left + size
    bottom = top + size
    box_right = x + width
    box_bottom = y + height
    intersection_width = max(0, min(right, box_right) - max(left, x))
    intersection_height = max(0, min(bottom, box_bottom) - max(top, y))
    return intersection_width * intersection_height > 0


def background_crops(image, boxes, rng):
    crops = []
    size = max(32, min(image.width, image.height) // 4)

    for _ in range(3):
        for _attempt in range(30):
            left = int(rng.integers(0, max(1, image.width - size + 1)))
            top = int(rng.integers(0, max(1, image.height - size + 1)))
            if not any(overlaps_box(left, top, size, box) for box in boxes):
                crops.append(image.crop((left, top, left + size, top + size)))
                break

    return crops


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATASET_PATH}. Download the documented MIT dataset first."
        )

    table = pq.read_table(DATASET_PATH, columns=["image", "objects"])
    rows = table.to_pylist()
    train_rows, test_rows = train_test_split(
        rows,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )
    rng = np.random.default_rng(RANDOM_STATE)

    train_features = []
    train_labels = []
    test_features = []
    test_labels = []

    for split_rows, features, labels in [
        (train_rows, train_features, train_labels),
        (test_rows, test_features, test_labels),
    ]:
        for row in split_rows:
            image = Image.open(BytesIO(row["image"]["bytes"])).convert("RGB")
            boxes = row["objects"]["bbox"]

            for box in boxes:
                features.append(extract_image_features(image_bytes(crop_for_box(image, box))))
                labels.append(1)

            for crop in background_crops(image, boxes, rng):
                features.append(extract_image_features(image_bytes(crop)))
                labels.append(0)

    train_features = np.asarray(train_features)
    test_features = np.asarray(test_features)
    train_labels = np.asarray(train_labels)
    test_labels = np.asarray(test_labels)

    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(train_features, train_labels)
    predictions = model.predict(test_features)

    print(f"Training images: {len(train_rows)}")
    print(f"Validation images: {len(test_rows)}")
    print(classification_report(
        test_labels,
        predictions,
        labels=[0, 1],
        target_names=CLASS_NAMES,
        zero_division=0,
    ))

    joblib.dump({
        "model": model,
        "classes": CLASS_NAMES,
        "feature_version": 1,
        "mode": "annotated_crop_detector",
        "source": "bbrenes/objectRecognition_Landslides",
        "source_license": "MIT",
        "training_images": len(train_rows),
        "validation_images": len(test_rows),
    }, MODEL_PATH)
    print(f"Saved trained model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
