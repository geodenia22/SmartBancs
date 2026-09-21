package com.smartbancs.transactionservice.account.service;

import com.smartbancs.transactionservice.account.dto.CreateAccountRequest;
import com.smartbancs.transactionservice.account.entity.Account;
import com.smartbancs.transactionservice.account.repository.AccountRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class AccountService {

    private final AccountRepository accountRepository;

    public AccountService(AccountRepository accountRepository) {
        this.accountRepository = accountRepository;
    }

    public Account create(CreateAccountRequest request) {

        Account account = new Account(
                request.ownerName(),
                request.initialBalance()
        );

        return accountRepository.save(account);
    }

    public List<Account> findAll() {
        return accountRepository.findAll();
    }
}