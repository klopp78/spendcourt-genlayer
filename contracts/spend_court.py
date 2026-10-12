# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Consensus settlement receipts for delegated AI-agent work."""

from genlayer import *
import hashlib
import json
import typing


class DeliveryVerdict(typing.NamedTuple):
    decision: str
    completion_bps: u16
    confidence: u8
    scope_match: bool
    invoice_authentic: bool
    execution_verified: bool
    delivery_verified: bool
    evidence_bundle_hash: str
    assessment_context_hash: str
    snapshot_commitments_json: str
    summary: str


class SpendCourt(gl.Contract):
    """Evidence-bound AI service orders with consensus-limited settlement."""

    order_count: u64
    assessment_count: u64
    latest_order_id: str
    latest_assessment_id: str
    order_ids: DynArray[str]
    assessment_ids: DynArray[str]
    orders: TreeMap[str, str]
    assessments: TreeMap[str, str]
    settlements: TreeMap[str, str]
    payee_claims: TreeMap[str, str]

    def __init__(self):
        self.order_count = u64(0)
        self.assessment_count = u64(0)
        self.latest_order_id = ""
        self.latest_assessment_id = ""

    @gl.public.view
    def get_order(self, order_id: str) -> str:
        return self.orders.get(order_id, "")

    @gl.public.view
    def get_assessment(self, assessment_id: str) -> str:
        return self.assessments.get(assessment_id, "")

    @gl.public.view
    def get_settlement(self, assessment_id: str) -> str:
        return self.settlements.get(assessment_id, "")

    @gl.public.view
    def get_payee_claim(self, payee_wallet: str, currency: str) -> str:
        return self.payee_claims.get(_claim_key(_wallet(payee_wallet), _text(currency, 20, "currency_required").upper()), "")

    @gl.public.view
    def get_latest_order_id(self) -> str:
        return self.latest_order_id

    @gl.public.view
    def get_latest_assessment_id(self) -> str:
        return self.latest_assessment_id

    @gl.public.view
    def list_order_ids(self) -> str:
        return _canonical_json([item for item in self.order_ids])

    @gl.public.view
    def list_assessment_ids(self) -> str:
        return _canonical_json([item for item in self.assessment_ids])

    @gl.public.write
    def register_order(
        self,
        service_title: str,
        agent_wallet: str,
        payee_wallet: str,
        currency: str,
        maximum_budget: str,
        deadline_utc: str,
        mandate_url: str,
        acceptance_policy_url: str,
        work_repository_url: str,
    ) -> str:
        payer = str(gl.message.sender_address).lower()
        title = _text(service_title, 140, "service_title_required")
        agent = _wallet(agent_wallet)
        payee = _wallet(payee_wallet)
        normalized_currency = _text(currency, 20, "currency_required").upper()
        budget = _positive_amount(maximum_budget, "maximum_budget_invalid")
        deadline = _text(deadline_utc, 40, "deadline_required")
        sources = _baseline_sources(mandate_url, acceptance_policy_url, work_repository_url)

        def leader_fn():
            return _capture_baseline(title, payer, agent, payee, normalized_currency, budget, deadline, sources)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                proposed = json.loads(leader_result.calldata)
                independent = json.loads(_capture_baseline(
                    title, payer, agent, payee, normalized_currency, budget, deadline, sources
                ))
            except Exception:
                return False
            return (
                proposed.get("baseline_hash") == independent.get("baseline_hash")
                and proposed.get("snapshot_commitments") == independent.get("snapshot_commitments")
                and proposed.get("source_bundle_hash") == independent.get("source_bundle_hash")
                and proposed.get("review_materials") == independent.get("review_materials")
            )

        baseline = json.loads(gl.vm.run_nondet_unsafe(leader_fn, validator_fn))
        order_id = "ord_" + _sha256_parts([payer, agent, payee, title.lower(), baseline["baseline_hash"]])[:20]
        if len(self.orders.get(order_id, "")) > 0:
            raise Exception("order_already_registered")

        self.order_count = u64(int(self.order_count) + 1)
        record = {
            "schema_version": "spendcourt.order.v1",
            "order_id": order_id,
            "sequence": int(self.order_count),
            "service_title": title,
            "payer": payer,
            "agent": agent,
            "payee": payee,
            "currency": normalized_currency,
            "maximum_budget": budget,
            "remaining_budget": budget,
            "settled_amount": 0,
            "deadline_utc": deadline,
            "baseline": baseline,
            "assessment_ids": [],
            "state": "open",
        }
        self.orders[order_id] = _canonical_json(record)
        self.order_ids.append(order_id)
        self.latest_order_id = order_id
        return order_id

    @gl.public.write
    def assess_delivery(
        self,
        order_id: str,
        invoice_number: str,
        requested_amount: str,
        invoice_url: str,
        execution_log_url: str,
        deliverable_url: str,
        payment_transaction_url: str,
    ) -> str:
        order = _load(self.orders.get(order_id, ""), "order_not_found")
        requester = str(gl.message.sender_address).lower()
        if requester not in (order["payer"], order["agent"], order["payee"]):
            raise Exception("only_order_party_can_request_assessment")
        if order["state"] != "open":
            raise Exception("order_not_open")
        invoice = _text(invoice_number, 100, "invoice_number_required")
        amount = _positive_amount(requested_amount, "requested_amount_invalid")
        if amount > int(order["remaining_budget"]):
            raise Exception("requested_amount_exceeds_remaining_budget")
        sources = _delivery_sources(invoice_url, execution_log_url, deliverable_url, payment_transaction_url)

        def leader_fn():
            return _adjudicate_delivery(order, invoice, amount, sources)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                proposed = _parse_verdict(leader_result.calldata)
                independent = _parse_verdict(_adjudicate_delivery(order, invoice, amount, sources))
            except Exception:
                return False
            return (
                proposed.decision == independent.decision
                and proposed.completion_bps == independent.completion_bps
                and proposed.scope_match == independent.scope_match
                and proposed.invoice_authentic == independent.invoice_authentic
                and proposed.execution_verified == independent.execution_verified
                and proposed.delivery_verified == independent.delivery_verified
                and proposed.evidence_bundle_hash == independent.evidence_bundle_hash
                and proposed.assessment_context_hash == independent.assessment_context_hash
                and proposed.snapshot_commitments_json == independent.snapshot_commitments_json
                and abs(int(proposed.confidence) - int(independent.confidence)) <= 10
            )

        verdict = json.loads(gl.vm.run_nondet_unsafe(leader_fn, validator_fn))
        authorized_amount = min(
            amount,
            int(order["remaining_budget"]),
            amount * int(verdict["completion_bps"]) // 10000,
        )
        if verdict["decision"] in ("rejected", "unverifiable"):
            authorized_amount = 0
        self.assessment_count = u64(int(self.assessment_count) + 1)
        assessment_id = "sct_" + _sha256_parts([
            order_id, invoice.lower(), str(amount), verdict["evidence_bundle_hash"], str(int(self.assessment_count))
        ])[:20]
        record = {
            "schema_version": "spendcourt.assessment.v1",
            "assessment_id": assessment_id,
            "order_id": order_id,
            "requester": requester,
            "invoice_number": invoice,
            "requested_amount": amount,
            "authorized_amount": authorized_amount,
            "currency": order["currency"],
            "baseline_hash": order["baseline"]["baseline_hash"],
            "source_manifest": sources,
            "snapshot_commitments": verdict["snapshot_commitments"],
            "evidence_bundle_hash": verdict["evidence_bundle_hash"],
            "assessment_context_hash": verdict["assessment_context_hash"],
            "consensus_result": verdict,
            "state": "assessed" if authorized_amount > 0 else "blocked",
            "settlement_ready": False,
        }
        order["assessment_ids"].append(assessment_id)
        self.orders[order_id] = _canonical_json(order)
        self.assessments[assessment_id] = _canonical_json(record)
        self.assessment_ids.append(assessment_id)
        self.latest_assessment_id = assessment_id
        return assessment_id

    @gl.public.write
    def finalize_receipt(self, order_id: str, assessment_id: str) -> str:
        order = _load(self.orders.get(order_id, ""), "order_not_found")
        assessment = _load(self.assessments.get(assessment_id, ""), "assessment_not_found")
        caller = str(gl.message.sender_address).lower()
        if caller != order["payer"]:
            raise Exception("only_payer_can_finalize")
        if assessment["order_id"] != order_id:
            raise Exception("assessment_order_mismatch")
        if assessment["state"] != "assessed" or int(assessment["authorized_amount"]) <= 0:
            raise Exception("assessment_not_authorizable")
        if int(assessment["authorized_amount"]) > int(order["remaining_budget"]):
            raise Exception("finalization_exceeds_spending_boundary")
        assessment["state"] = "finalized"
        assessment["settlement_ready"] = True
        assessment["finalized_by"] = caller
        assessment["authorization_receipt_hash"] = _sha256(_canonical_json(assessment))
        self.assessments[assessment_id] = _canonical_json(assessment)
        return assessment["authorization_receipt_hash"]

    @gl.public.write
    def execute_settlement(self, order_id: str, assessment_id: str) -> str:
        order = _load(self.orders.get(order_id, ""), "order_not_found")
        assessment = _load(self.assessments.get(assessment_id, ""), "assessment_not_found")
        if assessment["order_id"] != order_id:
            raise Exception("assessment_order_mismatch")
        if assessment["state"] != "finalized" or assessment["settlement_ready"] is not True:
            raise Exception("settlement_requires_finalized_receipt")
        if len(self.settlements.get(assessment_id, "")) > 0:
            raise Exception("settlement_already_executed")
        amount = int(assessment["authorized_amount"])
        if amount <= 0 or amount > int(order["remaining_budget"]):
            raise Exception("settlement_exceeds_spending_boundary")

        order["remaining_budget"] = int(order["remaining_budget"]) - amount
        order["settled_amount"] = int(order["settled_amount"]) + amount
        if int(order["remaining_budget"]) == 0:
            order["state"] = "settled"
        assessment["state"] = "executed"
        assessment["settlement_ready"] = False
        claim_key = _claim_key(order["payee"], order["currency"])
        existing = self.payee_claims.get(claim_key, "")
        claim = json.loads(existing) if len(existing) > 0 else {
            "schema_version": "spendcourt.claim.v1",
            "payee": order["payee"],
            "currency": order["currency"],
            "claimable_amount": 0,
            "assessment_ids": [],
        }
        claim["claimable_amount"] = int(claim["claimable_amount"]) + amount
        claim["assessment_ids"].append(assessment_id)
        settlement = {
            "schema_version": "spendcourt.settlement.v1",
            "order_id": order_id,
            "assessment_id": assessment_id,
            "executed_by": str(gl.message.sender_address).lower(),
            "payer": order["payer"],
            "payee": order["payee"],
            "currency": order["currency"],
            "executed_amount": amount,
            "remaining_budget": order["remaining_budget"],
            "authorization_receipt_hash": assessment["authorization_receipt_hash"],
            "transfer_mechanism": "contract_state_credit_to_payee",
            "status": "executed",
        }
        settlement["settlement_hash"] = _sha256(_canonical_json(settlement))
        self.orders[order_id] = _canonical_json(order)
        self.assessments[assessment_id] = _canonical_json(assessment)
        self.settlements[assessment_id] = _canonical_json(settlement)
        self.payee_claims[claim_key] = _canonical_json(claim)
        return settlement["settlement_hash"]


def _capture_baseline(title, payer, agent, payee, currency, budget, deadline, sources) -> str:
    snapshots = _render_sources(sources)
    commitments = _snapshot_commitments(sources, snapshots)
    materials = {}
    for snapshot in snapshots:
        if snapshot["source_type"] in ("service_mandate", "acceptance_policy"):
            materials[snapshot["source_type"]] = {
                "canonical_url": snapshot["canonical_url"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "snapshot_excerpt": snapshot["text"][:2000],
            }
    baseline = {
        "service_title": title, "payer": payer, "agent": agent, "payee": payee,
        "currency": currency, "maximum_budget": budget, "deadline_utc": deadline,
        "snapshot_commitments": commitments, "review_materials": materials,
    }
    baseline["source_bundle_hash"] = _sha256(_canonical_json(sources))
    baseline["baseline_hash"] = _sha256(_canonical_json(baseline))
    return _canonical_json(baseline)


def _adjudicate_delivery(order: dict, invoice: str, amount: int, sources) -> str:
    snapshots = _render_sources(sources)
    commitments = _snapshot_commitments(sources, snapshots)
    evidence_bundle_hash = _sha256(_canonical_json(commitments))
    context = {
        "order_id": order["order_id"],
        "baseline_hash": order["baseline"]["baseline_hash"],
        "service_mandate": order["baseline"]["review_materials"]["service_mandate"],
        "acceptance_policy": order["baseline"]["review_materials"]["acceptance_policy"],
        "invoice_number": invoice,
        "requested_amount": amount,
        "remaining_budget": order["remaining_budget"],
        "delivery_commitments": commitments,
    }
    context_hash = _sha256(_canonical_json(context))
    prompt = f"""
You are the GenLayer Internet Court reconciling one AI-agent service invoice.
Compare the fetched invoice, execution log, deliverable, and payment transaction with the
immutable service mandate and acceptance policy. Return only minified JSON with keys:
decision (fulfilled|partial|rejected|unverifiable), completion_bps (one of 0,2500,5000,7500,10000),
confidence (0-100), scope_match, invoice_authentic, execution_verified, delivery_verified,
evidence_bundle_hash, summary. Full payment requires authentic invoice, matching execution,
verified delivery, and direct compliance with the frozen mandate. Partial payment must reflect
demonstrably delivered scope. Reject contradictions or unauthorized work. Use unverifiable for
inaccessible or insufficient evidence. evidence_bundle_hash must equal {evidence_bundle_hash}.

Immutable context: {_canonical_json(context)}
Rendered delivery evidence: {_canonical_json(snapshots)}
"""
    data = json.loads(gl.nondet.exec_prompt(prompt))
    result = {
        "decision": str(data["decision"]).lower(),
        "completion_bps": int(data["completion_bps"]),
        "confidence": max(0, min(100, int(data["confidence"]))),
        "scope_match": bool(data["scope_match"]),
        "invoice_authentic": bool(data["invoice_authentic"]),
        "execution_verified": bool(data["execution_verified"]),
        "delivery_verified": bool(data["delivery_verified"]),
        "evidence_bundle_hash": str(data["evidence_bundle_hash"]),
        "assessment_context_hash": context_hash,
        "snapshot_commitments": commitments,
        "summary": str(data["summary"])[:500],
    }
    return _canonical_json(result)


def _parse_verdict(raw: str) -> DeliveryVerdict:
    data = json.loads(raw)
    decision = str(data["decision"]).lower()
    completion = int(data["completion_bps"])
    confidence = int(data["confidence"])
    if decision not in ("fulfilled", "partial", "rejected", "unverifiable"):
        raise Exception("invalid_decision")
    if completion not in (0, 2500, 5000, 7500, 10000):
        raise Exception("invalid_completion_bps")
    if confidence < 0 or confidence > 100:
        raise Exception("invalid_confidence")
    if len(str(data["evidence_bundle_hash"])) != 64 or len(str(data["assessment_context_hash"])) != 64:
        raise Exception("invalid_commitment")
    if len(data["snapshot_commitments"]) != 4:
        raise Exception("invalid_snapshot_commitments")
    return DeliveryVerdict(
        decision, u16(completion), u8(confidence), bool(data["scope_match"]),
        bool(data["invoice_authentic"]), bool(data["execution_verified"]),
        bool(data["delivery_verified"]), str(data["evidence_bundle_hash"]),
        str(data["assessment_context_hash"]), _canonical_json(data["snapshot_commitments"]),
        str(data["summary"]),
    )


def _render_sources(sources):
    snapshots = []
    for source in sources:
        rendered = gl.nondet.web.render(source["canonical_url"], mode="text")[:7000]
        snapshots.append({
            "source_index": source["source_index"], "source_type": source["source_type"],
            "canonical_url": source["canonical_url"], "url_hash": source["url_hash"],
            "snapshot_hash": _sha256(rendered), "snapshot_chars": len(rendered), "text": rendered,
        })
    return snapshots


def _snapshot_commitments(sources, snapshots):
    return [{
        "source_index": source["source_index"], "source_type": source["source_type"],
        "host": source["host"], "canonical_url": source["canonical_url"],
        "url_hash": source["url_hash"], "snapshot_hash": snapshot["snapshot_hash"],
        "snapshot_chars": snapshot["snapshot_chars"],
    } for source, snapshot in zip(sources, snapshots)]


def _baseline_sources(mandate, policy, repository):
    return [_source(1, "service_mandate", mandate), _source(2, "acceptance_policy", policy), _source(3, "work_repository", repository)]


def _delivery_sources(invoice, execution_log, deliverable, payment_transaction):
    return [_source(1, "invoice", invoice), _source(2, "execution_log", execution_log), _source(3, "deliverable", deliverable), _source(4, "payment_transaction", payment_transaction)]


def _source(index: int, source_type: str, raw_url: str) -> dict:
    url = str(raw_url).strip()
    if not url.startswith("https://") or "?" in url or "#" in url or len(url) > 700:
        raise Exception("sources_require_canonical_https_without_query")
    remainder = url[8:]
    if "/" not in remainder:
        raise Exception("source_path_required")
    host, path = remainder.split("/", 1)
    path = "/".join([part for part in path.split("/") if part])
    if not host or not path:
        raise Exception("source_path_required")
    canonical = "https://" + host.lower() + "/" + path
    return {"source_index": index, "source_type": source_type, "host": host.lower(), "canonical_url": canonical, "url_hash": _sha256(canonical)}


def _load(raw: str, error: str) -> dict:
    if not raw:
        raise Exception(error)
    return json.loads(raw)


def _text(value: str, maximum: int, error: str) -> str:
    clean = " ".join(str(value).strip().split())
    if not clean or len(clean) > maximum:
        raise Exception(error)
    return clean


def _wallet(value: str) -> str:
    wallet = str(value).strip().lower()
    if not wallet.startswith("0x") or len(wallet) != 42:
        raise Exception("invalid_wallet")
    return wallet


def _positive_amount(value: str, error: str) -> int:
    amount = int(str(value).strip())
    if amount <= 0:
        raise Exception(error)
    return amount


def _claim_key(payee: str, currency: str) -> str:
    return _sha256_parts([payee, currency.upper()])


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_parts(parts) -> str:
    return _sha256(_canonical_json([str(part) for part in parts]))
