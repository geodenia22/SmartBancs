package com.smartbancs.transactionservice.messaging.event;

import com.smartbancs.transactionservice.messaging.config.RabbitMQConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

@Component
public class TransactionCompletedConsumer {

    private static final Logger LOGGER = LoggerFactory.getLogger(TransactionCompletedConsumer.class);

    @RabbitListener(queues = RabbitMQConfig.TRANSACTION_COMPLETED_QUEUE)
    public void receive(TransactionCompletedEvent event) {
        LOGGER.info(
                "Transaction completed event received: transactionId={}, sourceAccountId={}, destinationAccountId={}, amount={}",
                event.transactionId(),
                event.sourceAccountId(),
                event.destinationAccountId(),
                event.amount()
        );
    }
}
