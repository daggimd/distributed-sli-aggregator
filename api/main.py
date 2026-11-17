import os
from contextlib import asynccontextmanager
from typing import List, Optional
import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://daggimdesta@localhost:5432/sli_aggregator"
)

db_pool: Optional[asyncpg.Pool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    yield
    if db_pool:
        await db_pool.close()


app = FastAPI(
    title="Distributed SLI/SLO Aggregator API",
    description="Real-time reliability metrics, availability percentages, and error budget burn rates.",
    version="1.0.0",
    lifespan=lifespan,
)


class ServiceSLOStatus(BaseModel):
    service_name: str
    target_slo_percent: float
    actual_availability_percent: float
    error_budget_burn_rate: float


class HourlyRollup(BaseModel):
    timestamp_hour: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    availability_percent: float
    slo_met: bool


@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected" if db_pool else "disconnected"}


@app.get("/api/v1/slos", response_model=List[ServiceSLOStatus])
async def get_all_slo_statuses():
    query = """
        SELECT 
            service_name,
            target_slo_percent::FLOAT,
            actual_availability_percent::FLOAT,
            error_budget_burn_rate::FLOAT
        FROM vw_slo_error_budget
        ORDER BY error_budget_burn_rate DESC;
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]


@app.get("/api/v1/services/{service_id}/rollups", response_model=List[HourlyRollup])
async def get_service_rollups(service_id: int, limit: int = 24):
    query = """
        SELECT 
            timestamp_hour::TEXT,
            total_requests,
            successful_requests,
            failed_requests,
            avg_latency_ms::FLOAT,
            p95_latency_ms::FLOAT,
            p99_latency_ms::FLOAT,
            availability_percent::FLOAT,
            slo_met
        FROM service_hourly_rollups
        WHERE service_id = $1
        ORDER BY timestamp_hour DESC
        LIMIT $2;
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, service_id, limit)
        if not rows:
            raise HTTPException(status_code=404, detail="Service ID not found or no rollups available")
        return [dict(row) for row in rows]
