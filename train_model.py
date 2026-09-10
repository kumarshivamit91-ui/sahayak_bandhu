from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from model_utils import extract_image_features


DATA_DIR = Path("data")
MODEL_PATH = Path("image_model.joblib")
CLASS_NAMES = ["no_landslide", "landslide"]
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_dataset():
    features = []
    labels = []
    counts = {}

    for label, class_name in enumerate(CLASS_NAMES):
        class_dir = DATA_DIR / class_name
        images = [
            path for path in class_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        counts[class_name] = len(images)

        for image_path in images:
            try:
                features.append(extract_image_features(image_path.read_bytes()))
                labels.append(label)
            except Exception as error:
                print(f"Skipping {image_path}: {error}")

    if len(set(labels)) < 2:
        raise ValueError(
            "Both data/no_landslide and data/landslide need labelled images."
        )

    if min(counts.values()) < 2:
        raise ValueError("Each class needs at least two valid images.")

    return np.asarray(features), np.asarray(labels), counts


def main():
    features, labels, counts = load_dataset()
    test_size = max(2, round(len(labels) * 0.2))

    train_features, test_features, train_labels, test_labels = train_test_split(
        features,
        labels,
        test_size=test_size,
        random_state=42,
        stratify=labels,
    )

    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train_features, train_labels)

    predictions = model.predict(test_features)
    print("Images:", counts)
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
        "training_counts": counts,
    }, MODEL_PATH)
    print(f"Saved trained model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
