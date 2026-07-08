"""
Request / response schemas for the FastAPI app.
"""

from pydantic import BaseModel


class TrainResponse(BaseModel):
    status: str
    message: str


class ForecastRequest(BaseModel):
    product_id: int
    department_id: int
    aisle_id: int
    order_count: float
    reorder_units: float
    avg_add_to_cart_order: float
    avg_days_since_prior_order: float
    lag_1_units: float
    lag_2_units: float
    lag_4_units: float
    rolling_4w_mean: float
    rolling_4w_std: float


class ForecastResponse(BaseModel):
    predicted_units: float