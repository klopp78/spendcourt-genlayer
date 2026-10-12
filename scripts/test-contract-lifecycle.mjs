import assert from "node:assert/strict";
import { createHash } from "node:crypto";
const PAYER = "0x1111111111111111111111111111111111111111";
const AGENT = "0x2222222222222222222222222222222222222222";
const PAYEE = "0x3333333333333333333333333333333333333333";
const sha = (value) => createHash("sha256").update(value).digest("hex");
class SpendCourtModel {
  constructor() { this.orders = new Map(); this.assessments = new Map(); this.settlements = new Map(); }
  register() { const id = `ord_${sha("immutable baseline").slice(0, 20)}`; this.orders.set(id, { payer: PAYER, agent: AGENT, payee: PAYEE, maximum_budget: 1000, remaining_budget: 1000, settled_amount: 0, state: "open", baseline: { baseline_hash: sha("terms and policy") } }); return id; }
  assess(orderId, requested, completionBps, caller = AGENT) { const order = this.orders.get(orderId); if (![order.payer, order.agent, order.payee].includes(caller)) throw new Error("only_order_party_can_request_assessment"); if (requested > order.remaining_budget) throw new Error("requested_amount_exceeds_remaining_budget"); const authorized = Math.min(requested, order.remaining_budget, Math.floor(requested * completionBps / 10000)); const id = `sct_${sha(`${orderId}|${requested}|${completionBps}`).slice(0, 20)}`; this.assessments.set(id, { order_id: orderId, requested_amount: requested, authorized_amount: authorized, completion_bps: completionBps, state: authorized ? "assessed" : "blocked", settlement_ready: false, evidence_bundle_hash: sha("four snapshots") }); return id; }
  finalize(orderId, assessmentId, caller = PAYER) { const order = this.orders.get(orderId); const receipt = this.assessments.get(assessmentId); if (caller !== order.payer) throw new Error("only_payer_can_finalize"); if (receipt.state !== "assessed") throw new Error("assessment_not_authorizable"); receipt.state = "finalized"; receipt.settlement_ready = true; receipt.authorization_receipt_hash = sha(JSON.stringify(receipt)); }
  execute(orderId, assessmentId) { const order = this.orders.get(orderId); const receipt = this.assessments.get(assessmentId); if (receipt.state !== "finalized" || !receipt.settlement_ready) throw new Error("settlement_requires_finalized_receipt"); if (this.settlements.has(assessmentId)) throw new Error("settlement_already_executed"); if (receipt.authorized_amount > order.remaining_budget) throw new Error("settlement_exceeds_spending_boundary"); order.remaining_budget -= receipt.authorized_amount; order.settled_amount += receipt.authorized_amount; receipt.state = "executed"; receipt.settlement_ready = false; this.settlements.set(assessmentId, { status: "executed", executed_amount: receipt.authorized_amount, remaining_budget: order.remaining_budget, transfer_mechanism: "contract_state_credit_to_payee" }); }
}
const model = new SpendCourtModel();
const order = model.register();
assert.throws(() => model.assess(order, 100, 10000, "0x4444444444444444444444444444444444444444"), /only_order_party/);
assert.throws(() => model.assess(order, 1001, 10000), /exceeds_remaining/);
const blocked = model.assess(order, 500, 0);
assert.throws(() => model.finalize(order, blocked), /not_authorizable/);
const partial = model.assess(order, 800, 7500);
assert.equal(model.assessments.get(partial).authorized_amount, 600);
assert.throws(() => model.finalize(order, partial, AGENT), /only_payer/);
model.finalize(order, partial); model.execute(order, partial);
assert.equal(model.orders.get(order).remaining_budget, 400);
assert.equal(model.settlements.get(partial).executed_amount, 600);
assert.throws(() => model.execute(order, partial), /requires_finalized/);
console.log("SpendCourt lifecycle tests passed");
