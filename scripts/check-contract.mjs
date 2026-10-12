import { readFileSync } from "node:fs";
const source = readFileSync("contracts/spend_court.py", "utf8");
const expect = (condition, message) => { if (!condition) throw new Error(message); };
expect(source.startsWith("# { \"Depends\": \"py-genlayer:"), "missing pinned runtime");
expect(/class\s+SpendCourt\s*\(gl\.Contract\)/.test(source), "missing SpendCourt contract");
for (const method of ["register_order", "assess_delivery", "finalize_receipt", "execute_settlement", "get_order", "get_assessment", "get_settlement", "get_payee_claim"]) expect(new RegExp(`def\\s+${method}\\s*\\(`).test(source), `missing ${method}`);
for (const marker of ["gl.vm.run_nondet_unsafe", "gl.nondet.web.render", "gl.nondet.exec_prompt", "hashlib.sha256", "snapshot_commitments", "baseline_hash", "assessment_context_hash", "settlement_requires_finalized_receipt", "settlement_exceeds_spending_boundary", "contract_state_credit_to_payee", "completion_bps"]) expect(source.includes(marker), `missing integrity marker: ${marker}`);
expect(!/\bhash\s*\(/.test(source), "non-deterministic Python hash is forbidden");
console.log("SpendCourt contract integrity checks passed");
