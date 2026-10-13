# Downstream payment execution

This file is a template. A real execution record must be committed after authorization and must state:

- successful and non-reverted payment status
- payer and payee wallet addresses
- exact amount and currency
- downstream transaction reference
- matching SpendCourt authorization receipt hash

SpendCourt validators reject incomplete, mismatched, or mutable payment evidence.
