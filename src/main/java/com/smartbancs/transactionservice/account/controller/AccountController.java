package com.smartbancs.transactionservice.account.controller;

import com.smartbancs.transactionservice.account.dto.CreateAccountRequest;
import com.smartbancs.transactionservice.account.entity.Account;
import com.smartbancs.transactionservice.account.service.AccountService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/accounts")
public class AccountController {

    private final AccountService accountService;

    public AccountController(AccountService accountService) {
        this.accountService = accountService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Account create(
            @Valid @RequestBody CreateAccountRequest request
    ) {
        return accountService.create(request);
    }

    @GetMapping
    public List<Account> findAll() {
        return accountService.findAll();
    }
}