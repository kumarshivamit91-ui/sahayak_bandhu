from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sklearn.ensemble import RandomForestClassifier
import joblib
import numpy as np

from PIL import Image
from io import BytesIO
from datetime import datetime
import os
import uuid

from model_utils import extract_image_features


# =========================================================
# RESQAI API
# =========================================================

app = FastAPI(
    title="ResQAI - Landslide Risk Monitoring API",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# PROJECT PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
IMAGE_MODEL_PATH = os.path.join(BASE_DIR, "image_model.joblib")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads"
)


# =========================================================
# DEMO ML MODEL
# =========================================================
#
# Features:
# rainfall
# soil moisture
# slope
#
# This is a DEMO model trained on generated data.
# Real SIH deployment should use verified historical data.
# =========================================================

def calculate_risk_score(rainfall, moisture, slope):

    rainfall_score = min(
        rainfall / 200 * 40,
        40
    )

    moisture_score = moisture / 100 * 30

    slope_score = min(
        slope / 45 * 30,
        30
    )

    return round(
        max(
            0,
            min(
                rainfall_score
                + moisture_score
                + slope_score,
                100
            )
        )
    )


def score_to_label(score):

    if score >= 70:
        return 2       # HIGH

    if score >= 40:
        return 1       # MODERATE

    return 0           # LOW


np.random.seed(42)

X_train = []
y_train = []


for _ in range(1500):

    rainfall = np.random.uniform(10, 300)
    moisture = np.random.uniform(10, 100)
    slope = np.random.uniform(1, 60)

    label = score_to_label(
        calculate_risk_score(
            rainfall,
            moisture,
            slope
        )
    )

    X_train.append([
        rainfall,
        moisture,
        slope
    ])

    y_train.append(label)


model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X_train, y_train)

image_model_bundle = None

if os.path.exists(IMAGE_MODEL_PATH):
    image_model_bundle = joblib.load(IMAGE_MODEL_PATH)


RISK_NAMES = {
    0: "LOW",
    1: "MODERATE",
    2: "HIGH"
}


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return FileResponse(INDEX_FILE)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "online",
        "environmental_model": "Rule-based environmental risk score",
        "image_model": (
            image_model_bundle.get("source")
            if image_model_bundle
            else "not loaded"
        ),
        "image_model_license": (
            image_model_bundle.get("source_license")
            if image_model_bundle
            else None
        ),
        "timestamp": datetime.now().isoformat()
    }


# =========================================================
# IMAGE ANALYSIS
# =========================================================

def analyze_image(image_bytes):

    try:

        image = Image.open(
            BytesIO(image_bytes)
        ).convert("RGB")

        image = image.resize((128, 128))

        pixels = np.asarray(image) / 255.0

        brightness = float(
            pixels.mean()
        )

        green_ratio = float(
            pixels[:, :, 1].mean()
        )

        blue_ratio = float(
            pixels[:, :, 2].mean()
        )

        return {
            "image_valid": True,
            "width": 128,
            "height": 128,
            "brightness": round(brightness, 3),
            "green_ratio": round(green_ratio, 3),
            "blue_ratio": round(blue_ratio, 3)
        }

    except Exception:

        return {
            "image_valid": False,
            "brightness": 0,
            "green_ratio": 0,
            "blue_ratio": 0
        }


def predict_image(image_bytes):

    if image_model_bundle is None:
        return {
            "available": False,
            "message": (
                "No trained image model found. "
                "Run train_model.py with labelled images."
            )
        }

    try:
        trained_model = image_model_bundle["model"]
        classes = image_model_bundle["classes"]

        if image_model_bundle.get("mode") == "annotated_crop_detector":
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            window_size = max(32, min(image.width, image.height) // 4)
            candidates = []

            for top in range(0, max(1, image.height - window_size + 1), window_size // 2):
                for left in range(0, max(1, image.width - window_size + 1), window_size // 2):
                    crop = image.crop((
                        left,
                        top,
                        min(image.width, left + window_size),
                        min(image.height, top + window_size)
                    ))
                    crop_buffer = BytesIO()
                    crop.save(crop_buffer, format="PNG")
                    features = extract_image_features(crop_buffer.getvalue()).reshape(1, -1)
                    probabilities = trained_model.predict_proba(features)[0]
                    candidates.append((float(probabilities[1]), left, top))

            landslide_probability, left, top = max(candidates)
            prediction = int(landslide_probability >= 0.5)
            confidence = max(landslide_probability, 1 - landslide_probability) * 100

            return {
                "available": True,
                "class": classes[prediction],
                "confidence": round(confidence, 2),
                "landslide_probability": round(landslide_probability * 100, 2),
                "source": image_model_bundle.get("source"),
                "source_license": image_model_bundle.get("source_license"),
                "best_region": {
                    "left": left,
                    "top": top,
                    "size": window_size
                }
            }

        features = extract_image_features(image_bytes).reshape(1, -1)
        probabilities = trained_model.predict_proba(features)[0]
        prediction = int(trained_model.predict(features)[0])

        return {
            "available": True,
            "class": classes[prediction],
            "confidence": round(float(max(probabilities)) * 100, 2),
            "training_counts": image_model_bundle.get("training_counts", {})
        }

    except Exception as error:
        return {
            "available": False,
            "message": f"Image model could not analyze this file: {error}"
        }

# =========================================================
# RISK PREDICTION
# =========================================================

@app.post("/predict")
async def predict_risk(

    file: UploadFile = File(...),

    rainfall: float = Form(...),

    moisture: float = Form(...),

    slope: float = Form(...)

):

    # -----------------------------------------------------
    # Validate environmental values
    # -----------------------------------------------------

    rainfall = max(0, min(rainfall, 500))
    moisture = max(0, min(moisture, 100))
    slope = max(0, min(slope, 90))


    # -----------------------------------------------------
    # Read image
    # -----------------------------------------------------

    image_bytes = await file.read()

    image_analysis = analyze_image(
        image_bytes
    )

    image_prediction = predict_image(
        image_bytes
    )


    # -----------------------------------------------------
    # Save uploaded image
    # -----------------------------------------------------

    extension = os.path.splitext(
        file.filename or ""
    )[1]

    if not extension:
        extension = ".jpg"

    saved_name = (
        str(uuid.uuid4())
        + extension
    )

    saved_path = os.path.join(
        UPLOAD_DIR,
        saved_name
    )

    with open(
        saved_path,
        "wb"
    ) as output_file:

        output_file.write(
            image_bytes
        )


    # -----------------------------------------------------
    # ML Prediction
    # -----------------------------------------------------

    features = np.array([[
        rainfall,
        moisture,
        slope
    ]])

    prediction = int(
        model.predict(features)[0]
    )

    probability = model.predict_proba(
        features
    )[0]

    risk = RISK_NAMES[prediction]

    confidence = float(
        max(probability) * 100
    )


    # -----------------------------------------------------
    # Risk score uses the same rule used to create model labels.
    # -----------------------------------------------------

    score = calculate_risk_score(
        rainfall,
        moisture,
        slope
    )


    # -----------------------------------------------------
    # Risk factors
    # -----------------------------------------------------

    reasons = []

    if rainfall >= 120:

        reasons.append(
            "Heavy rainfall"
        )

    elif rainfall >= 80:

        reasons.append(
            "Elevated rainfall"
        )


    if moisture >= 80:

        reasons.append(
            "High soil moisture"
        )

    elif moisture >= 60:

        reasons.append(
            "Elevated soil moisture"
        )


    if slope >= 35:

        reasons.append(
            "Steep terrain"
        )

    elif slope >= 20:

        reasons.append(
            "Moderate slope"
        )


    if not reasons:

        reasons.append(
            "No major environmental risk factor detected"
        )


    # -----------------------------------------------------
    # Recommendation
    # -----------------------------------------------------

    if risk == "HIGH":

        recommendation = (
            "Immediate field verification and "
            "authority attention recommended."
        )

    elif risk == "MODERATE":

        recommendation = (
            "Monitor the area closely and "
            "consider field inspection."
        )

    else:

        recommendation = (
            "Current environmental conditions "
            "appear relatively stable."
        )


    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return {

        "filename": file.filename,

        "risk": risk,

        "score": score,

        "confidence": round(
            confidence,
            2
        ),

        "rainfall": rainfall,

        "soil_moisture": moisture,

        "slope": slope,

        "reasons": reasons,

        "recommendation": recommendation,

        "image_analysis": image_analysis,

        "image_prediction": image_prediction,

        "image_url":
            f"/uploads/{saved_name}",

        "timestamp":
            datetime.now().isoformat()

    }


# =========================================================
# RISK ZONES
# =========================================================

@app.get("/risk-zones")
def risk_zones():

    return {

        "zones": [

            {
                "id": 1,
                "state": "Meghalaya",
                "lat": 25.4670,
                "lng": 91.3662,
                "risk": "HIGH",
                "rainfall": 145,
                "moisture": 82,
                "road_status": "PARTIALLY BLOCKED"
            },

            {
                "id": 2,
                "state": "Assam",
                "lat": 26.2006,
                "lng": 92.9376,
                "risk": "MODERATE",
                "rainfall": 95,
                "moisture": 65,
                "road_status": "OPEN"
            },

            {
                "id": 3,
                "state": "Sikkim",
                "lat": 27.5330,
                "lng": 88.5122,
                "risk": "LOW",
                "rainfall": 35,
                "moisture": 40,
                "road_status": "OPEN"
            },

            {
                "id": 4,
                "state": "Arunachal Pradesh",
                "lat": 27.0844,
                "lng": 93.6053,
                "risk": "HIGH",
                "rainfall": 165,
                "moisture": 87,
                "road_status": "BLOCKED"
            },

            {
                "id": 5,
                "state": "Nagaland",
                "lat": 25.6751,
                "lng": 94.1086,
                "risk": "MODERATE",
                "rainfall": 110,
                "moisture": 72,
                "road_status": "OPEN"
            }

        ]

    }


# =========================================================
# ALERTS
# =========================================================

@app.get("/alerts")
def alerts():

    return {

        "alerts": [

            {
                "id": "AL-001",
                "location": "Meghalaya",
                "risk": "HIGH",
                "message":
                    "Heavy rainfall and high soil moisture detected.",
                "priority": "CRITICAL"
            },

            {
                "id": "AL-002",
                "location": "Arunachal Pradesh",
                "risk": "HIGH",
                "message":
                    "Possible slope instability detected.",
                "priority": "HIGH"
            },

            {
                "id": "AL-003",
                "location": "Assam",
                "risk": "MODERATE",
                "message":
                    "Elevated rainfall conditions.",
                "priority": "MEDIUM"
            }

        ]

    }


# =========================================================
# FIELD REPORT
# =========================================================

@app.post("/field-report")
async def field_report(

    file: UploadFile = File(None),

    latitude: float = Form(...),

    longitude: float = Form(...),

    issue_type: str = Form(...),

    description: str = Form("")

):

    report_id = (
        "REP-"
        + str(uuid.uuid4())[:8].upper()
    )


    saved_file = None


    if file:

        extension = os.path.splitext(
            file.filename or ""
        )[1]

        if not extension:
            extension = ".jpg"

        filename = (
            report_id
            + extension
        )

        path = os.path.join(
            UPLOAD_DIR,
            filename
        )

        content = await file.read()

        with open(
            path,
            "wb"
        ) as f:

            f.write(content)

        saved_file = (
            f"/uploads/{filename}"
        )


    return {

        "success": True,

        "report_id": report_id,

        "status": "RECEIVED",

        "priority": "HIGH",

        "issue_type": issue_type,

        "latitude": latitude,

        "longitude": longitude,

        "description": description,

        "file": saved_file,

        "message":
            "Field report submitted successfully."

    }


# =========================================================
# DASHBOARD SUMMARY
# =========================================================

@app.get("/dashboard")
def dashboard():

    return {

        "overall_risk": "HIGH",

        "high_risk_zones": 12,

        "moderate_risk_zones": 8,

        "active_alerts": 4,

        "blocked_roads": 3,

        "available_resources": {

            "ambulances": 12,

            "rescue_teams": 8,

            "boats": 5,

            "volunteers": 34

        },

        "weather": {

            "status": "HEAVY RAIN",

            "rainfall": 145,

            "forecast":
                "High rainfall expected"

        }

    }


@app.get("/app", include_in_schema=False)
def frontend():
    return FileResponse("index.html")


@app.get("/style.css", include_in_schema=False)
def stylesheet():
    return FileResponse("style.css", media_type="text/css")


@app.get("/script.js", include_in_schema=False)
def javascript():
    return FileResponse("script.js", media_type="application/javascript")