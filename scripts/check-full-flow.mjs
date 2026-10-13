import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const frontend = readFileSync("lib/genlayer.ts", "utf8") + readFileSync("site-static/main.ts", "utf8");
const contract = readFileSync("contracts/spend_court.py", "utf8");
for (const method of ["register_order", "assess_delivery", "finalize_receipt", "execute_settlement"]) { assert.ok(frontend.includes(`"${method}"`), `frontend missing ${method}`); assert.ok(contract.includes(`def ${method}(`), `contract missing ${method}`); }
assert.ok(frontend.includes("TransactionStatus.FINALIZED"), "writes must await FINALIZED");
assert.ok(frontend.includes("ExecutionResult.FINISHED_WITH_RETURN"), "writes must verify GenVM SUCCESS");
assert.ok(frontend.includes("TransactionHashVariant.LATEST_FINAL"), "reads must use LATEST_FINAL");
console.log("SpendCourt frontend-contract flow checks passed");
