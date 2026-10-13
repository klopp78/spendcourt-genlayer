# SpendCourt for GenLayer

SpendCourt is a GenLayer-native, noncustodial payment-authorization protocol for delegated AI-agent work. A payer freezes a service mandate, budget, deadline, and acceptance policy before execution. Validators authenticate delivery evidence, issue a bounded authorization receipt, and independently verify the downstream payment record before the order is marked settled.

## Why GenLayer

A conventional smart contract can enforce a numeric cap but cannot decide whether an agent actually completed the requested work. SpendCourt uses GenLayer consensus to assess ambiguous delivery evidence and turns that decision into an enforceable payment boundary.

## Contract lifecycle

1. `register_order` fetches and commits the mandate, acceptance policy, and repository baseline.
2. `assess_delivery` independently renders four evidence sources and compares every consequential verdict field across validators.
3. `finalize_receipt` lets only the payer reserve budget for a positive assessment.
4. `execute_settlement` verifies a commit-pinned downstream payment record against payer, payee, amount, currency, and authorization receipt before recording settlement.

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

SpendCourt never claims that an internal accounting entry moved money. Funds move through an external payment rail; the contract records settlement only after validators authenticate the resulting execution proof.

## Evidence

- Contract source: `contracts/spend_court.py`
- Interactive application: https://klopp78.github.io/spendcourt-genlayer/
- Contract explorer: https://explorer-studio.genlayer.com/address/0x68d89833AEa1263d7D2BFD6cAe9120C501B71318
- Deployment transaction: https://explorer-studio.genlayer.com/tx/0x90c7b65b5d386d179f96c527f6b2e20e7b3d260c5d03bba08914317d861d4739
- Example materials: `examples/`

## Verification

```bash
npm ci
npm test
```

The test suite checks contract integrity markers, partial settlement math, unauthorized callers, blocked receipts, payer-only finalization, replay protection, frontend/contract method parity, the application build, and the GitHub Pages bundle.
