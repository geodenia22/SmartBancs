# SmartBancs AI Risk Engine

SmartBancs AI Risk Engine is an independent Python microservice that evaluates whether a transaction pattern is anomalous relative to a reproducible demo baseline.

> This MVP detects anomalous transaction patterns. It does not determine or prove that a transaction is fraudulent.

## Architecture

- `app/main.py`: FastAPI endpoints and application lifecycle.
- `app/schemas.py`: Pydantic request and response contracts.
- `app/feature_engineering.py`: observable transaction features and human-readable reasons.
- `app/risk_engine.py`: demo-data training, Isolation Forest scoring, model versioning, and `joblib` persistence.
- `app/messaging/rabbitmq_consumer.py`: RabbitMQ event consumer, isolated from HTTP and ML logic.
- `model/`: generated demo model artifact. `data/` is reserved for future approved datasets.

The service has no database, authentication, or frontend. It receives completed transaction events published by `transaction-service`, but it does not modify that service.

## Run locally

Requires Python 3.13.

```powershell
cd transaction-service/transaction-service/ai-service
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The RabbitMQ consumer starts with FastAPI in one daemon thread. Avoid `--reload` when consuming events outside local development: reload restarts the application process and therefore its consumer.

On first startup, the service trains a deterministic **DEMO MODEL / SYNTHETIC DATA** baseline with `random_state=42` and writes `model/isolation-forest-v1.joblib`. Later starts load that artifact rather than retraining it for every request.

## Endpoints

### `GET /health`

```json
{
  "status": "UP",
  "service": "smartbancs-ai-risk-engine",
  "modelVersion": "isolation-forest-v1"
}
```

### `POST /api/v1/risk/analyze`

```json
{
  "transactionId": "550e8400-e29b-41d4-a716-446655440000",
  "sourceAccountId": "11111111-1111-4111-8111-111111111111",
  "destinationAccountId": "22222222-2222-4222-8222-222222222222",
  "amount": 2500.00,
  "createdAt": "2026-09-20T23:15:00Z"
}
```

Example response:

```json
{
  "transactionId": "550e8400-e29b-41d4-a716-446655440000",
  "riskScore": 82.4,
  "riskLevel": "HIGH",
  "anomaly": true,
  "reasons": [
    "Transaction amount is unusually high relative to the demo baseline",
    "Transaction occurred during an unusual hour"
  ],
  "modelVersion": "isolation-forest-v1",
  "evaluatedAt": "2026-09-20T23:15:02Z"
}
```

## Features and scoring

The MVP uses only features observable in the request: `amount`, `hourOfDay`, and `isNightTransaction`. Future historical features such as transaction frequency, historical average amount, deviation from average, and recent transaction count are intentionally not simulated.

Isolation Forest isolates uncommon feature combinations by repeatedly partitioning the synthetic baseline. Its raw output is an anomaly measure, not a probability. The service maps that measure to a 0-100 **anomaly risk score** using the 5th and 95th percentiles of the demo training baseline, clipping values outside that range. Thresholds are transparent constants: `LOW` is 0-34, `MEDIUM` is 35-64, and `HIGH` is 65-100.

Reasons are not claimed to be causal explanations from Isolation Forest. They are generated separately from observable inputs: an amount above the demo baseline's 95th percentile and a nighttime hour. Requests without those indicators receive an expected-demo-behavior reason; an anomalous combination can receive an explicit combination reason.

## Model version and limitations

Every response carries `modelVersion: "isolation-forest-v1"` for basic traceability. The model is trained only with reproducible synthetic data to demonstrate the HTTP → features → model → score pipeline. It has not been validated with real financial history and must not be used to conclude that a transaction is fraudulent.

## RabbitMQ consumer

The consumer declares its own durable queue so it receives a copy of each event and does not compete with the demonstration consumer in `transaction-service`.

- Exchange: `smartbancs.transactions.exchange`
- Queue: `smartbancs.ai.transactions.completed`
- Routing key: `transaction.completed`

It accepts the completed-transaction JSON, validates it with the same `TransactionRiskRequest` schema used by `POST /api/v1/risk/analyze`, and calls the same in-memory `RiskEngine` instance. A successfully analyzed message receives `basic_ack`. A malformed or failed message receives `basic_nack(requeue=False)` so it cannot create an infinite retry loop. Credentials are read from `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, and `RABBITMQ_PASSWORD`; the development defaults match the local SmartBancs Docker setup.

## Docker

```powershell
docker build -t smartbancs-ai-risk-engine .
docker run --rm -p 8000:8000 smartbancs-ai-risk-engine
```
