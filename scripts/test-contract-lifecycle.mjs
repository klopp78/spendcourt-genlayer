import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const PAYER = "0x1111111111111111111111111111111111111111";
const AGENT = "0x2222222222222222222222222222222222222222";
const PAYEE = "0x3333333333333333333333333333333333333333";
const OUTSIDER = "0x4444444444444444444444444444444444444444";
const sha = (value) => createHash("sha256").update(value).digest("hex");

class SpendCourtModel {
  constructor(now = 1_800_000_000) {
    this.now = now;
    this.orders = new Map();
    this.assessments = new Map();
    this.settlements = new Map();
    this.invoices = new Map();
    this.evidence = new Set();
  }
  register(deadline = this.now + 3600) {
    if (deadline <= this.now) throw new Error("deadline_must_be_in_future");
    const id = `ord_${sha(String(deadline)).slice(0, 20)}`;
    this.orders.set(id, { payer: PAYER, agent: AGENT, payee: PAYEE, remaining: 1000, reserved: 0, settled: 0, deadline, state: "open" });
    return id;
  }
  active(order) {
    if (this.now > order.deadline) throw new Error("order_deadline_expired");
  }
  assess(orderId, invoice, evidenceKey, requested, completionBps, caller = AGENT) {
    const order = this.orders.get(orderId);
    this.active(order);
    if (![order.payer, order.agent, order.payee].includes(caller)) throw new Error("only_order_party");
    const invoiceKey = sha(`${orderId}|${invoice.toLowerCase()}`);
    if (this.invoices.has(invoiceKey)) throw new Error("invoice_already_assessed");
    if (this.evidence.has(evidenceKey)) throw new Error("evidence_bundle_already_assessed");
    if (requested > order.remaining - order.reserved) throw new Error("exceeds_available_budget");
    const authorized = Math.floor(requested * completionBps / 10000);
    const id = `sct_${sha(invoiceKey + evidenceKey).slice(0, 20)}`;
    this.assessments.set(id, { orderId, invoiceKey, authorized, state: authorized ? "assessed" : "blocked" });
    this.invoices.set(invoiceKey, { assessmentId: id, authorized, settled: 0 });
    this.evidence.add(evidenceKey);
    return id;
  }
  finalize(orderId, assessmentId, caller = PAYER) {
    const order = this.orders.get(orderId);
    const receipt = this.assessments.get(assessmentId);
    this.active(order);
    if (caller !== order.payer) throw new Error("only_payer_can_finalize");
    if (receipt.state !== "assessed") throw new Error("assessment_not_authorizable");
    if (receipt.authorized > order.remaining - order.reserved) throw new Error("exceeds_available_budget");
    order.reserved += receipt.authorized;
    receipt.state = "finalized";
  }
  execute(orderId, assessmentId, paymentVerified, caller = PAYER) {
    const order = this.orders.get(orderId);
    const receipt = this.assessments.get(assessmentId);
    this.active(order);
    if (caller !== order.payer) throw new Error("only_payer_can_confirm_payment");
    if (receipt.state !== "finalized") throw new Error("settlement_requires_finalized_receipt");
    if (!paymentVerified) throw new Error("downstream_payment_not_verified");
    order.remaining -= receipt.authorized;
    order.reserved -= receipt.authorized;
    order.settled += receipt.authorized;
    receipt.state = "settled";
    this.invoices.get(receipt.invoiceKey).settled += receipt.authorized;
    this.settlements.set(assessmentId, { status: "verified", amount: receipt.authorized });
  }
}

const model = new SpendCourtModel();
assert.throws(() => model.register(model.now), /deadline_must_be_in_future/);
const order = model.register();
assert.throws(() => model.assess(order, "INV-X", "proof-x", 100, 10000, OUTSIDER), /only_order_party/);
const blocked = model.assess(order, "INV-0", "proof-0", 100, 0);
assert.throws(() => model.finalize(order, blocked), /not_authorizable/);
const first = model.assess(order, "INV-1", "proof-1", 600, 10000);
assert.throws(() => model.assess(order, "INV-1", "proof-2", 600, 10000), /invoice_already_assessed/);
assert.throws(() => model.assess(order, "INV-2", "proof-1", 600, 10000), /evidence_bundle_already_assessed/);
assert.throws(() => model.finalize(order, first, AGENT), /only_payer/);
model.finalize(order, first);
assert.equal(model.orders.get(order).reserved, 600);
assert.throws(() => model.assess(order, "INV-3", "proof-3", 500, 10000), /exceeds_available_budget/);
assert.throws(() => model.execute(order, first, false), /payment_not_verified/);
assert.throws(() => model.execute(order, first, true, AGENT), /only_payer/);
model.execute(order, first, true);
assert.equal(model.orders.get(order).remaining, 400);
assert.equal(model.orders.get(order).reserved, 0);
assert.equal(model.orders.get(order).settled, 600);
assert.equal(model.invoices.get(model.assessments.get(first).invoiceKey).settled, 600);
assert.throws(() => model.execute(order, first, true), /requires_finalized/);
const expired = model.register(model.now + 1);
model.now += 2;
assert.throws(() => model.assess(expired, "INV-LATE", "proof-late", 10, 10000), /deadline_expired/);
console.log("SpendCourt v2 lifecycle and negative-path tests passed");
