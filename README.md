# SpendCourt for GenLayer

SpendCourt is a GenLayer-native settlement console for delegated AI-agent work. A payer freezes a service mandate, budget, deadline, and acceptance policy before execution. Validators later authenticate the invoice, execution log, deliverable, and payment intent, then issue a durable receipt that authorizes no more than the independently assessed completion amount.

## Why GenLayer

A conventional smart contract can enforce a numeric cap but cannot decide whether an agent actually completed the requested work. SpendCourt uses GenLayer consensus to assess ambiguous delivery evidence and turns that decision into an enforceable payment boundary.

## Contract lifecycle

1. `register_order` fetches and commits the mandate, acceptance policy, and repository baseline.
2. `assess_delivery` independently renders four evidence sources and compares every consequential verdict field across validators.
3. `finalize_receipt` lets only the payer convert a positive assessment into an executable authorization receipt.
4. `execute_settlement` refuses missing, blocked, repeated, or over-budget receipts and credits the payee ledger.

Completion is quantized to `0`, `25%`, `50%`, `75%`, or `100%`. The authorized amount is deterministically capped by the requested amount and remaining order budget.

## Integrity properties

- SHA-256 commitments over canonical JSON, URLs, frozen terms, and rendered snapshots
- validator recomputation of every decision-critical field and source hash
- immutable baseline terms used during every later assessment
- explicit payer finalization before settlement
- persistent order, assessment, settlement, and payee-claim records
- finalized transaction wait and `LATEST_FINAL` readback in the application

## Evidence

- Contract source: `contracts/spend_court.py`
- Interactive application: https://klopp78.github.io/spendcourt-genlayer/
- Contract explorer: added after Studio deployment
- Example materials: `examples/`

## Verification

```bash
npm ci
npm test
```

The test suite checks contract integrity markers, partial settlement math, unauthorized callers, blocked receipts, payer-only finalization, replay protection, frontend/contract method parity, the application build, and the GitHub Pages bundle.
