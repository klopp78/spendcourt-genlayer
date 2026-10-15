# SpendCourt for GenLayer

SpendCourt is a GenLayer-native, noncustodial payment-authorization protocol for delegated AI-agent work. A payer freezes a service mandate, budget, deadline, and acceptance policy before execution. Validators authenticate delivery evidence, issue a bounded authorization receipt, and independently verify the downstream payment record before the order is marked settled.

## Why GenLayer

A conventional smart contract can enforce a numeric cap but cannot decide whether an agent actually completed the requested work. SpendCourt uses GenLayer consensus to assess ambiguous delivery evidence and turns that decision into an enforceable payment boundary.

## Contract lifecycle

1. `register_order` fetches and commits the mandate, acceptance policy, and repository baseline.
2. `assess_delivery` independently renders four evidence sources and compares every consequential verdict field across validators.
3. `finalize_receipt` lets only the payer reserve budget for a positive assessment.
4. `execute_settlement` cross-checks a commit-pinned payment manifest plus an exact 64-hex Studio transaction hash against payer, payee, amount, currency, and authorization receipt before recording settlement.

Completion is quantized to `0`, `25%`, `50%`, `75%`, or `100%`. The authorized amount is deterministically capped by the requested amount and remaining order budget.

## Integrity properties

- SHA-256 commitments over canonical JSON, URLs, frozen terms, and rendered snapshots
- validator recomputation of every decision-critical field and source hash
- immutable baseline terms used during every later assessment
- invoice and evidence-bundle replay protection
- reservation and cumulative settlement accounting across every order and invoice
- enforced on-chain deadlines for assessment, finalization, and payment verification
- strict JSON boolean parsing and consistency rules for every positive verdict
- complete commit-pinned evidence snapshots with no silent source truncation
- exact GenVM `FINISHED_WITH_RETURN` checks and `LATEST_FINAL` readback in the application
- explicit 40-hex Git commit references and 64-hex Studio transaction references, with their types bound into validator evidence commitments

SpendCourt never claims that an internal accounting entry moved money. Funds move through an external payment rail; the contract records settlement only after validators authenticate the resulting execution proof.

## Evidence

- Contract source: `contracts/spend_court.py`
- Interactive application: https://klopp78.github.io/spendcourt-genlayer/
- Contract explorer: https://explorer-studio.genlayer.com/address/0x7CC6f181F0046E11C80fA21e1862AbD40B20b33c
- Payment relay: https://explorer-studio.genlayer.com/address/0x699FeD986a887842c164c5B69C2dE75255970C7A
- Verified 1 GEN relay payment: https://explorer-studio.genlayer.com/tx/0xa959d786d78909b98be88b5ebbb010920f8d60f185da2ff863f22ee4ca20607b
- Live receipt readback: `get_payment` returns the payer, payee, and `1000000000000000000` wei amount for receipt `6fbc4ae0071bcc2c7c0e99d1c2bb4b8698ec989cb291fc7bdc7fd6dba1898251`; `is_receipt_used` returns `true`; `get_payment_count` returns `1`.
- Zero-value rejection check: https://explorer-studio.genlayer.com/tx/0x146c8e7ba83739c8cb13a10a0094af36fb47ec2675d25f4bf5823062540664fd
- Rejection-state readback: receipt `ad8e4217f392a1e8b5b4bd96e0448b6d78691cef848d543487ac07886f9e65ac` remains unused and `get_payment_count` remains `1`.
- Finalized settlement: https://explorer-studio.genlayer.com/tx/0xce5be449bf2753df7bed204e2466fa96525b007cdc82a5a726b37243247136de
- Example materials: `examples/`

## Verification

```bash
npm ci
npm test
```

The test suite checks contract integrity markers, partial settlement math, unauthorized callers, blocked receipts, payer-only finalization, replay protection, and the submitted payment relay's payable transfer and receipt-state interfaces. Live Studio readbacks verify the accepted 1 GEN relay record and that a zero-value rejected invocation does not consume a receipt or increment the payment count.
