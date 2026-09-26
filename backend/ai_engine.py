import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "yatasetu_temple1_calendar_model_final.pkl"
)

model = joblib.load(MODEL_PATH)


def calculate_risk(predicted_crowd, temple_capacity):
    if temple_capacity <= 0:
        return "UNKNOWN", 0.0

    occupancy = (predicted_crowd / temple_capacity) * 100

    if occupancy < 50:
        level = "LOW"
    elif occupancy < 70:
        level = "MEDIUM"
    elif occupancy < 90:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return level, round(occupancy, 2)


def predict_for_date(
    date_str,
    temperature=27.0,
    rainfall=0.0,
    festival_type="None",
    temple_capacity=15000
):
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format.")

    if temple_capacity <= 0:
        raise ValueError("Temple capacity must be greater than 0.")

    rows = []

    for hour in range(24):
        rows.append({
            "temple_id": 1,
            "day_of_week": date.weekday(),
            "hour": hour,
            "month": date.month,
            "is_weekend": int(date.weekday() >= 5),
            "is_festival": int(festival_type != "None"),
            "festival_type": festival_type,
            "temperature": float(temperature),
            "rainfall": float(rainfall),
            "temple_capacity": int(temple_capacity)
        })

    inputs = pd.DataFrame(rows)

    predictions = np.maximum(
        0,
        np.round(model.predict(inputs)).astype(int)
    )

    results = []

    for hour, crowd in enumerate(predictions):
        risk, occupancy = calculate_risk(
            int(crowd),
            int(temple_capacity)
        )

        results.append({
            "temple_id": 1,
            "date": date_str,
            "hour": hour,
            "predicted_crowd": int(crowd),
            "temple_capacity": int(temple_capacity),
            "occupancy_percentage": occupancy,
            "risk_level": risk
        })

    return pd.DataFrame(results)
