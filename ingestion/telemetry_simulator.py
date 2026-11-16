import asyncio
import asyncpg
import os
import random
import uuid
from datetime import datetime, timezone, timedelta

DB_DSN = os.getenv("DATABASE_URL", "postgresql://localhost/sli_aggregator")

SERVICES = [
    {"service_id": "svc-auth-01", "endpoints": ["/v1/login", "/v1/token/refresh"], "base_latency_ms": 45.0, "error_rate": 0.0004, "spike_probability": 0.02},
    {"service_id": "svc-cat-02", "endpoints": ["/v1/items/search", "/v1/categories"], "base_latency_ms": 85.0, "error_rate": 0.001, "spike_probability": 0.04},
    {"service_id": "svc-chk-03", "endpoints": ["/v1/cart/validate", "/v1/payment/process"], "base_latency_ms": 130.0, "error_rate": 0.0025, "spike_probability": 0.05},
    {"service_id": "svc-rec-04", "endpoints": ["/v1/recommendations/feed", "/v1/trending"], "base_latency_ms": 190.0, "error_rate": 0.006, "spike_probability": 0.08}
]

def generate_event(service: dict, timestamp: datetime) -> tuple:
    request_id = uuid.uuid4()
    endpoint = random.choice(service["endpoints"])
    if random.random() < service["error_rate"]:
        http_status = random.choice([500, 502, 503, 504])
    elif random.random() < 0.005:
        http_status = random.choice([400, 401, 404, 429])
    else:
        http_status = 200
    latency = random.gauss(service["base_latency_ms"], service["base_latency_ms"] * 0.2)
    if random.random() < service["spike_probability"]:
        latency *= random.uniform(3.0, 8.0)
    return (request_id, service["service_id"], endpoint, http_status, round(max(5.0, latency), 2), timestamp)

async def batch_writer(pool: asyncpg.Pool, queue: asyncio.Queue, batch_size: int = 250):
    insert_query = "INSERT INTO raw_telemetry (request_id, service_id, endpoint, http_status, latency_ms, timestamp_utc) VALUES ($1, $2, $3, $4, $5, $6)"
    buffer = []
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=1.5)
            buffer.append(event)
            queue.task_done()
            if len(buffer) >= batch_size:
                async with pool.acquire() as conn:
                    await conn.executemany(insert_query, buffer)
                print(f"[DB FLUSH] Wrote {len(buffer)} telemetry records to PostgreSQL.")
                buffer.clear()
        except asyncio.TimeoutError:
            if buffer:
                async with pool.acquire() as conn:
                    await conn.executemany(insert_query, buffer)
                print(f"[DB IDLE FLUSH] Wrote {len(buffer)} telemetry records to PostgreSQL.")
                buffer.clear()

async def seed_historical_data(pool: asyncpg.Pool, hours_back: int = 48, events_per_hour: int = 1000):
    print(f"Seeding {hours_back} hours of historical telemetry...")
    insert_query = "INSERT INTO raw_telemetry (request_id, service_id, endpoint, http_status, latency_ms, timestamp_utc) VALUES ($1, $2, $3, $4, $5, $6)"
    now = datetime.now(timezone.utc)
    batch = []
    for hour_offset in range(hours_back, 0, -1):
        hour_start = now - timedelta(hours=hour_offset)
        is_incident_hour = (hour_offset == 14)
        for _ in range(events_per_hour):
            svc = random.choice(SERVICES)
            event_time = hour_start + timedelta(seconds=random.randint(0, 3599))
            if is_incident_hour and svc["service_id"] == "svc-chk-03":
                degraded_svc = {**svc, "error_rate": 0.04, "spike_probability": 0.35}
                batch.append(generate_event(degraded_svc, event_time))
            else:
                batch.append(generate_event(svc, event_time))
            if len(batch) >= 2000:
                async with pool.acquire() as conn:
                    await conn.executemany(insert_query, batch)
                batch.clear()
    if batch:
        async with pool.acquire() as conn:
            await conn.executemany(insert_query, batch)
    print("Historical seeding complete!")

async def live_traffic_producer(queue: asyncio.Queue, events_per_second: int = 40):
    print(f"Starting live traffic stream (~{events_per_second} req/sec). Press Ctrl+C to stop.")
    delay = 1.0 / events_per_second
    while True:
        await queue.put(generate_event(random.choice(SERVICES), datetime.now(timezone.utc)))
        await asyncio.sleep(delay)

async def main():
    pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=2, max_size=5)
    queue = asyncio.Queue(maxsize=10000)
    await seed_historical_data(pool, hours_back=48, events_per_hour=1000)
    consumer = asyncio.create_task(batch_writer(pool, queue))
    producer = asyncio.create_task(live_traffic_producer(queue))
    try:
        await asyncio.gather(producer, consumer)
    finally:
        await pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped telemetry simulator.")
