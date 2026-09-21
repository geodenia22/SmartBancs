package com.smartbancs.transactionservice.messaging.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.amqp.support.converter.JacksonJsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String TRANSACTIONS_EXCHANGE = "smartbancs.transactions.exchange";
    public static final String TRANSACTION_COMPLETED_QUEUE = "smartbancs.transactions.completed";
    public static final String TRANSACTION_COMPLETED_ROUTING_KEY = "transaction.completed";

    @Bean
    public TopicExchange transactionsExchange() {
        return new TopicExchange(TRANSACTIONS_EXCHANGE);
    }

    @Bean
    public Queue transactionCompletedQueue() {
        return new Queue(TRANSACTION_COMPLETED_QUEUE, true);
    }

    @Bean
    public Binding transactionCompletedBinding(Queue transactionCompletedQueue, TopicExchange transactionsExchange) {
        return BindingBuilder.bind(transactionCompletedQueue)
                .to(transactionsExchange)
                .with(TRANSACTION_COMPLETED_ROUTING_KEY);
    }

    @Bean
    public MessageConverter rabbitMessageConverter() {
        return new JacksonJsonMessageConverter();
    }
}
