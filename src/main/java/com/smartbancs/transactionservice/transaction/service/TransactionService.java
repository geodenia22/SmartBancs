package com.smartbancs.transactionservice.transaction.service;

import com.smartbancs.transactionservice.account.entity.Account;
import com.smartbancs.transactionservice.account.repository.AccountRepository;
import com.smartbancs.transactionservice.exception.AccountNotFoundException;
import com.smartbancs.transactionservice.exception.DuplicateTransactionException;
import com.smartbancs.transactionservice.exception.InsufficientBalanceException;
import com.smartbancs.transactionservice.exception.InvalidTransferException;
import com.smartbancs.transactionservice.messaging.event.TransactionCompletedEvent;
import com.smartbancs.transactionservice.observability.TransactionMetrics;
import com.smartbancs.transactionservice.transaction.dto.TransferRequest;
import com.smartbancs.transactionservice.transaction.dto.TransactionResponse;
import com.smartbancs.transactionservice.transaction.entity.Transaction;
import com.smartbancs.transactionservice.transaction.entity.TransactionStatus;

import com.smartbancs.transactionservice.transaction.repository.TransactionRepository;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class TransactionService {

    private static final Logger log =
            LoggerFactory.getLogger(TransactionService.class);

    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;
    private final ApplicationEventPublisher applicationEventPublisher;
    private final TransactionMetrics transactionMetrics;
    private final MeterRegistry meterRegistry;

    public TransactionService(
            AccountRepository accountRepository,
            TransactionRepository transactionRepository,
            ApplicationEventPublisher applicationEventPublisher,
            TransactionMetrics transactionMetrics,
            MeterRegistry meterRegistry) {

        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.applicationEventPublisher = applicationEventPublisher;
        this.transactionMetrics = transactionMetrics;
        this.meterRegistry = meterRegistry;
    }

    @Transactional
    public TransactionResponse transfer(
            TransferRequest request,
            String idempotencyKey) {

        Timer.Sample sample =
                transactionMetrics.start(meterRegistry);

        try {

            validateTransfer(request, idempotencyKey);

            String normalizedIdempotencyKey =
                    idempotencyKey.trim();

            /*
             * LOG 1:
             * Inicio de la operación.
             */
            log.info(
                    "Transaction started: idempotencyKey={}, sourceAccountId={}, destinationAccountId={}, amount={}",
                    normalizedIdempotencyKey,
                    request.sourceAccountId(),
                    request.destinationAccountId(),
                    request.amount()
            );

            /*
             * Primera validación de idempotencia.
             */
            TransactionResponse existingTransaction =
                    findCompletedTransaction(
                            normalizedIdempotencyKey
                    );

            if (existingTransaction != null) {

                transactionMetrics.idempotent();

                log.info(
                        "Idempotent transaction detected: transactionId={}, idempotencyKey={}",
                        existingTransaction.id(),
                        normalizedIdempotencyKey
                );

                return existingTransaction;
            }

            /*
             * Se determina un orden consistente para bloquear
             * las cuentas y reducir riesgo de deadlocks.
             */
            UUID firstAccountId =
                    request.sourceAccountId()
                            .compareTo(
                                    request.destinationAccountId()
                            ) < 0
                            ? request.sourceAccountId()
                            : request.destinationAccountId();

            UUID secondAccountId =
                    firstAccountId.equals(
                            request.sourceAccountId()
                    )
                            ? request.destinationAccountId()
                            : request.sourceAccountId();

            /*
             * Bloqueo pesimista de ambas cuentas.
             */
            Account firstAccount =
                    getAccountForUpdate(firstAccountId);

            Account secondAccount =
                    getAccountForUpdate(secondAccountId);

            /*
             * Segunda comprobación de idempotencia
             * después de adquirir los locks.
             *
             * Esto protege mejor frente a solicitudes
             * concurrentes con la misma clave.
             */
            existingTransaction =
                    findCompletedTransaction(
                            normalizedIdempotencyKey
                    );

            if (existingTransaction != null) {

                transactionMetrics.idempotent();

                log.info(
                        "Idempotent transaction detected after account lock: transactionId={}, idempotencyKey={}",
                        existingTransaction.id(),
                        normalizedIdempotencyKey
                );

                return existingTransaction;
            }

            /*
             * Identificación de cuenta origen y destino
             * independientemente del orden de bloqueo.
             */
            Account sourceAccount =
                    request.sourceAccountId()
                            .equals(firstAccountId)
                            ? firstAccount
                            : secondAccount;

            Account destinationAccount =
                    request.destinationAccountId()
                            .equals(firstAccountId)
                            ? firstAccount
                            : secondAccount;

            /*
             * Validación de saldo.
             */
            if (sourceAccount
                    .getBalance()
                    .compareTo(request.amount()) < 0) {

                throw new InsufficientBalanceException(
                        "Source account has insufficient balance"
                );
            }

            /*
             * Movimiento de fondos.
             */
            sourceAccount.debit(request.amount());
            destinationAccount.credit(request.amount());

            accountRepository.save(sourceAccount);
            accountRepository.save(destinationAccount);

            /*
             * Registro de la transacción.
             */
            Transaction transaction =
                    new Transaction(
                            request.sourceAccountId(),
                            request.destinationAccountId(),
                            request.amount(),
                            normalizedIdempotencyKey,
                            TransactionStatus.COMPLETED
                    );

            Transaction savedTransaction =
                    transactionRepository.saveAndFlush(
                            transaction
                    );

            /*
             * Publicación de evento interno.
             *
             * El listener AFTER_COMMIT se encarga posteriormente
             * de enviar el evento a RabbitMQ.
             */
            applicationEventPublisher.publishEvent(
                    new TransactionCompletedEvent(
                            savedTransaction.getId(),
                            savedTransaction.getSourceAccountId(),
                            savedTransaction.getDestinationAccountId(),
                            savedTransaction.getAmount(),
                            savedTransaction.getCreatedAt()
                    )
            );

            /*
             * Métrica de operación exitosa.
             */
            transactionMetrics.completed();

            /*
             * LOG 2:
             * Transacción completada.
             *
             * El transactionId permitirá correlacionar:
             *
             * Transaction Service
             *      -> RabbitMQ
             *      -> AI Service
             */
            log.info(
                    "Transaction completed: transactionId={}, sourceAccountId={}, destinationAccountId={}, amount={}, status={}",
                    savedTransaction.getId(),
                    savedTransaction.getSourceAccountId(),
                    savedTransaction.getDestinationAccountId(),
                    savedTransaction.getAmount(),
                    savedTransaction.getStatus()
            );

            return TransactionResponse.from(
                    savedTransaction
            );

        } catch (RuntimeException exception) {

            /*
             * Métrica de error.
             */
            transactionMetrics.failed();

            /*
             * LOG 3:
             * Error de procesamiento.
             *
             * Se registra también el stack trace.
             */
            log.error(
                    "Transaction failed: idempotencyKey={}, error={}",
                    idempotencyKey,
                    exception.getMessage(),
                    exception
            );

            throw exception;

        } finally {

            /*
             * Siempre registra la duración,
             * tanto para éxito como para error.
             */
            transactionMetrics.stop(sample);
        }
    }

    /**
     * Validaciones básicas de una transferencia.
     */
    private void validateTransfer(
            TransferRequest request,
            String idempotencyKey) {

        if (request == null
                || request.sourceAccountId() == null
                || request.destinationAccountId() == null) {

            throw new InvalidTransferException(
                    "Source and destination accounts are required"
            );
        }

        if (request.amount() == null
                || request.amount().signum() <= 0) {

            throw new InvalidTransferException(
                    "Amount must be greater than zero"
            );
        }

        if (request.sourceAccountId()
                .equals(request.destinationAccountId())) {

            throw new InvalidTransferException(
                    "Source and destination accounts must be different"
            );
        }

        if (idempotencyKey == null
                || idempotencyKey.isBlank()) {

            throw new InvalidTransferException(
                    "Idempotency key is required"
            );
        }
    }

    /**
     * Obtiene una cuenta aplicando el bloqueo
     * definido en AccountRepository.
     */
    private Account getAccountForUpdate(
            UUID accountId) {

        return accountRepository
                .findByIdForUpdate(accountId)
                .orElseThrow(
                        () -> new AccountNotFoundException(
                                accountId
                        )
                );
    }

    /**
     * Busca una operación existente utilizando
     * la clave de idempotencia.
     */
    private TransactionResponse findCompletedTransaction(
            String idempotencyKey) {

        return transactionRepository
                .findByIdempotencyKey(idempotencyKey)
                .map(transaction -> {

                    if (transaction.getStatus()
                            == TransactionStatus.COMPLETED) {

                        return TransactionResponse.from(
                                transaction
                        );
                    }

                    throw new DuplicateTransactionException(
                            "Idempotency key has already been used"
                    );
                })
                .orElse(null);
    }
}