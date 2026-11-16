# Product Requirements Document (PRD): Distributed SLI & Availability Aggregator

## 1. Objective
Simulate a multi-microservice environment modeled on Google Site Reliability Engineering (SRE) principles. Track real-time Service Level Indicators (SLIs), measure compliance against Service Level Objectives (SLOs), calculate Error Budget burn rates, and surface executive operational health reports via FastAPI and Tableau Public.

## 2. Core Constraints
* **100% Free Stack:** Python, PostgreSQL, FastAPI, Tableau Public.
* **Self-Contained:** Synthetic data generation eliminates external paid API dependencies.
* **Reproducible:** Anyone cloning the repository can initialize the database and run the simulation locally.

## 3. Architecture
1. **PostgreSQL Data Store:** Normalized schema separating high-throughput raw request logs from pre-aggregated hourly rollups.
2. **Python Asynchronous Ingestion Engine:** Simulates traffic across 4 core microservices (User Authentication, Product Catalog, Checkout Engine, Search Recommendations) with controlled latency spikes and HTTP 500 error bursts.
3. **FastAPI Reporting Layer:** Translates raw database metrics into executive statuses (`HEALTHY`, `WARNING_HIGH_BURN_RATE`, `LATENCY_SLO_BREACH`, `CRITICAL_AVAILABILITY_BREACH`).
4. **Tableau Public Dashboard:** Visualizes 48-hour availability trends, 95th/99th percentile latency spikes, and error budget consumption.