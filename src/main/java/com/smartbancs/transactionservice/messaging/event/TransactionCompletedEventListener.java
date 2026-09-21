package com.smartbancs.transactionservice.messaging.event;

import com.smartbancs.transactionservice.messaging.config.RabbitMQConfig;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class TransactionCompletedEventListener {

    private final RabbitTemplate rabbitTemplate;

    public TransactionCompletedEventListener(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onTransactionCompleted(TransactionCompletedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.TRANSACTIONS_EXCHANGE,
                RabbitMQConfig.TRANSACTION_COMPLETED_ROUTING_KEY,
                event
        );
    }
}
