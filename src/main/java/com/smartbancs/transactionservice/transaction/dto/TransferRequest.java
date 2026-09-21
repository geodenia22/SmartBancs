package com.smartbancs.transactionservice.transaction.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.util.UUID;

public record TransferRequest(

        @NotNull(message = "Source account id is required")
        UUID sourceAccountId,

        @NotNull(message = "Destination account id is required")
        UUID destinationAccountId,

        @NotNull(message = "Amount is required")
        @DecimalMin(value = "0.01", message = "Amount must be greater than zero")
        BigDecimal amount
) {
}
