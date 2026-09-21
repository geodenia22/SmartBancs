from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pika
from pydantic import ValidationError

from app.schemas import TransactionRiskRequest

if TYPE_CHECKING:
    from app.risk_engine import RiskEngine

LOGGER = logging.getLogger(__name__)

TRANSACTIONS_EXCHANGE = "smartbancs.transactions.exchange"
AI_TRANSACTION_COMPLETED_QUEUE = "smartbancs.ai.transactions.completed"
TRANSACTION_COMPLETED_ROUTING_KEY = "transaction.completed"
RECONNECT_DELAY_SECONDS = 5


@dataclass(frozen=True)
class RabbitMQSettings:
    host: str
    port: int
    username: str
    password: str

    @classmethod
    def from_environment(cls) -> "RabbitMQSettings":
        return cls(
            host=os.getenv("RABBITMQ_HOST", "localhost"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            username=os.getenv("RABBITMQ_USER", "smartbancs"),
            password=os.getenv("RABBITMQ_PASSWORD", "smartbancs123"),
        )


class RabbitMQConsumer:
    """Consumes transaction events on a daemon thread without blocking FastAPI."""

    def __init__(self, risk_engine: "RiskEngine", settings: RabbitMQSettings | None = None) -> None:
        self._risk_engine = risk_engine
        self._settings = settings or RabbitMQSettings.from_environment()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            LOGGER.warning("RabbitMQ consumer is already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._consume_forever,
            name="rabbitmq-risk-consumer",
            daemon=True,
        )
        self._thread.start()
        LOGGER.info("RabbitMQ consumer thread started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        LOGGER.info("RabbitMQ consumer thread stopped")

    def _connection_parameters(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(self._settings.username, self._settings.password)
        return pika.ConnectionParameters(
            host=self._settings.host,
            port=self._settings.port,
            credentials=credentials,
            heartbeat=30,
            blocked_connection_timeout=30,
        )

    def _consume_forever(self) -> None:
        while not self._stop_event.is_set():
            connection: pika.BlockingConnection | None = None
            try:
                connection = pika.BlockingConnection(self._connection_parameters())
                channel = connection.channel()
                channel.exchange_declare(
                    exchange=TRANSACTIONS_EXCHANGE,
                    exchange_type="topic",
                    durable=True,
                )
                channel.queue_declare(queue=AI_TRANSACTION_COMPLETED_QUEUE, durable=True)
                channel.queue_bind(
                    queue=AI_TRANSACTION_COMPLETED_QUEUE,
                    exchange=TRANSACTIONS_EXCHANGE,
                    routing_key=TRANSACTION_COMPLETED_ROUTING_KEY,
                )
                channel.basic_consume(
                    queue=AI_TRANSACTION_COMPLETED_QUEUE,
                    on_message_callback=self._handle_message,
                    auto_ack=False,
                )
                LOGGER.info(
                    "RabbitMQ consumer connected: exchange=%s queue=%s routingKey=%s",
                    TRANSACTIONS_EXCHANGE,
                    AI_TRANSACTION_COMPLETED_QUEUE,
                    TRANSACTION_COMPLETED_ROUTING_KEY,
                )

                while connection.is_open and not self._stop_event.is_set():
                    connection.process_data_events(time_limit=1)
            except pika.exceptions.AMQPConnectionError:
                LOGGER.warning("RabbitMQ is unavailable; retrying in %s seconds", RECONNECT_DELAY_SECONDS)
                self._stop_event.wait(RECONNECT_DELAY_SECONDS)
            except Exception:
                LOGGER.exception("RabbitMQ consumer stopped unexpectedly; retrying")
                self._stop_event.wait(RECONNECT_DELAY_SECONDS)
            finally:
                if connection is not None and connection.is_open:
                    connection.close()

    def _handle_message(self, channel, method, properties, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
            transaction = TransactionRiskRequest.model_validate(payload)
            assessment = self._risk_engine.assess(transaction)
            LOGGER.info(
                "AI risk assessment completed: transactionId=%s riskScore=%s riskLevel=%s anomaly=%s modelVersion=%s",
                assessment.transactionId,
                assessment.riskScore,
                assessment.riskLevel.value,
                assessment.anomaly,
                assessment.modelVersion,
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
            LOGGER.exception("Invalid transaction event rejected")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            LOGGER.exception("Transaction event processing failed and was rejected")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
