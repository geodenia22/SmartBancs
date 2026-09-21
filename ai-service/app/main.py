import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app.messaging.rabbitmq_consumer import RabbitMQConsumer
from app.risk_engine import MODEL_VERSION, RiskEngine
from app.schemas import HealthResponse, RiskAssessmentResponse, TransactionRiskRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)
MODEL_ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "model" / f"{MODEL_VERSION}.joblib"


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGGER.info("Starting SmartBancs AI Risk Engine")
    app.state.risk_engine = RiskEngine.load_or_train_demo_model(MODEL_ARTIFACT_PATH)
    app.state.rabbitmq_consumer = RabbitMQConsumer(app.state.risk_engine)
    app.state.rabbitmq_consumer.start()
    yield
    app.state.rabbitmq_consumer.stop()
    LOGGER.info("Stopping SmartBancs AI Risk Engine")


app = FastAPI(
    title="SmartBancs AI Risk Engine",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="UP",
        service="smartbancs-ai-risk-engine",
        modelVersion=MODEL_VERSION,
    )


@app.post("/api/v1/risk/analyze", response_model=RiskAssessmentResponse)
async def analyze_transaction(
    transaction: TransactionRiskRequest,
    request: Request,
) -> RiskAssessmentResponse:
    assessment = request.app.state.risk_engine.assess(transaction)
    LOGGER.info(
        "Transaction analyzed: transactionId=%s riskLevel=%s riskScore=%s",
        transaction.transactionId,
        assessment.riskLevel.value,
        assessment.riskScore,
    )
    return assessment
