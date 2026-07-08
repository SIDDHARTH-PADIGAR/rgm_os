"""
FastAPI entrypoint for Revenue Growth Management OS V1.

Endpoints:
- GET  /health
- POST /train/baseline
- POST /forecast/baseline
"""

import subprocess
from fastapi import FastAPI, HTTPException
from app.schemas import TrainResponse, ForecastRequest, ForecastResponse
from app.services.baseline_service import predict_baseline

app = FastAPI(title="Revenue Growth Management OS")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/train/baseline", response_model=TrainResponse)
def train_baseline():
    """
    Triggers the baseline model training script.
    In production this would become a job queue / workflow trigger,
    but subprocess is fine for V1.
    """
    try:
        result = subprocess.run(
            ["python", "-m", "models.train_baseline"],
            capture_output=True,
            text=True,
            check=True
        )
        return TrainResponse(
            status="success",
            message=result.stdout[-1000:] if result.stdout else "Baseline model trained."
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr)


@app.post("/forecast/baseline", response_model=ForecastResponse)
def forecast_baseline(request: ForecastRequest):
    """
    Score one product-week feature vector using the saved baseline model.
    """
    try:
        pred = predict_baseline(request.model_dump())
        return ForecastResponse(predicted_units=pred)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))