package com.smartbancs.transactionservice.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Component;

@Component
public class TransactionMetrics {

    private final Counter completed;
    private final Counter failed;
    private final Counter idempotent;
    private final Timer duration;

    public TransactionMetrics(MeterRegistry registry) {
        this.completed = Counter.builder("smartbancs.transactions.completed")
                .description("Successfully completed financial transactions")
                .register(registry);

        this.failed = Counter.builder("smartbancs.transactions.failed")
                .description("Failed financial transactions")
                .register(registry);

        this.idempotent = Counter.builder("smartbancs.transactions.idempotent")
                .description("Requests resolved through idempotency")
                .register(registry);

        this.duration = Timer.builder("smartbancs.transactions.duration")
                .description("Financial transaction processing time")
                .register(registry);
    }

    public void completed() {
        completed.increment();
    }

    public void failed() {
        failed.increment();
    }

    public void idempotent() {
        idempotent.increment();
    }

    public Timer.Sample start(MeterRegistry registry) {
        return Timer.start(registry);
    }

    public void stop(Timer.Sample sample) {
        sample.stop(duration);
    }
}