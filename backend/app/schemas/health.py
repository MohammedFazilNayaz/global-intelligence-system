from datetime import datetime
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database: str
    environment: str
