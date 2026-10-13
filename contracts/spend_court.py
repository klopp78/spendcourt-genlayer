# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Consensus authorization and payment-attestation receipts for AI-agent work."""

from genlayer import *
import hashlib
import json
import typing

MAX_SOURCE_CHARS = 24000
MIN_SOURCE_CHARS = 40


class DeliveryVerdict(typing.NamedTuple):
    decision: str
    completion_bps: u16
    confidence: u8
    scope_match: bool
    invoice_authentic: bool
    execution_verified: bool
    delivery_verified: bool
    evidence_complete: bool
    evidence_bundle_hash: str
    assessment_context_hash: str
    snapshot_commitments_json: str
    summary: str


class PaymentVerdict(typing.NamedTuple):
    payment_verified: bool
    payer_match: bool
    payee_match: bool
    amount_match: bool
    currency_match: bool
    receipt_match: bool
    payment_reference: str
    payment_snapshot_hash: str
    summary: str


class SpendCourt(gl.Contract):
    """Noncustodial payment authorization with validator-verified execution proofs."""

    order_count: u64
    assessment_count: u64
    latest_order_id: str
    latest_assessment_id: str
    order_ids: DynArray[str]
    assessment_ids: DynArray[str]
    orders: TreeMap[str, str]
    assessments: TreeMap[str, str]
    settlements: TreeMap[str, str]
    invoice_keys: TreeMap[str, str]
    evidence_keys: TreeMap[str, str]

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
    def get_invoice_record(self, order_id: str, invoice_number: str) -> str:
        return self.invoice_keys.get(_invoice_key(order_id, invoice_number), "")

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
        self, service_title: str, agent_wallet: str, payee_wallet: str,
        currency: str, maximum_budget: str, deadline_timestamp: str,
        mandate_url: str, acceptance_policy_url: str, work_repository_url: str,
    ) -> str:
        payer = str(gl.message.sender_address).lower()
        title = _text(service_title, 140, "service_title_required")
        agent = _wallet(agent_wallet)
        payee = _wallet(payee_wallet)
        normalized_currency = _text(currency, 20, "currency_required").upper()
        budget = _positive_amount(maximum_budget, "maximum_budget_invalid")
        deadline = _future_timestamp(deadline_timestamp)
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
            return proposed == independent

        baseline = json.loads(gl.vm.run_nondet_unsafe(leader_fn, validator_fn))
        order_id = "ord_" + _sha256_parts([payer, agent, payee, title.lower(), baseline["baseline_hash"]])[:20]
        if self.orders.get(order_id, ""):
            raise Exception("order_already_registered")
        self.order_count = u64(int(self.order_count) + 1)
        record = {
            "schema_version": "spendcourt.order.v2",
            "protocol_model": "noncustodial_authorization_and_payment_attestation",
            "order_id": order_id, "sequence": int(self.order_count), "service_title": title,
            "payer": payer, "agent": agent, "payee": payee, "currency": normalized_currency,
            "maximum_budget": budget, "remaining_budget": budget, "reserved_amount": 0,
            "settled_amount": 0, "deadline_timestamp": deadline, "baseline": baseline,
            "assessment_ids": [], "state": "open",
        }
        self.orders[order_id] = _canonical_json(record)
        self.order_ids.append(order_id)
        self.latest_order_id = order_id
        return order_id

    @gl.public.write
    def assess_delivery(
        self, order_id: str, invoice_number: str, requested_amount: str,
        invoice_url: str, execution_log_url: str, deliverable_url: str,
        acceptance_report_url: str,
    ) -> str:
        order = _load(self.orders.get(order_id, ""), "order_not_found")
        requester = str(gl.message.sender_address).lower()
        if requester not in (order["payer"], order["agent"], order["payee"]):
            raise Exception("only_order_party_can_request_assessment")
        _require_active(order)
        invoice = _text(invoice_number, 100, "invoice_number_required")
        invoice_key = _invoice_key(order_id, invoice)
        if self.invoice_keys.get(invoice_key, ""):
            raise Exception("invoice_already_assessed")
        amount = _positive_amount(requested_amount, "requested_amount_invalid")
        available = int(order["remaining_budget"]) - int(order["reserved_amount"])
        if amount > available:
            raise Exception("requested_amount_exceeds_available_budget")
        sources = _delivery_sources(invoice_url, execution_log_url, deliverable_url, acceptance_report_url)
        evidence_key = _sha256(_canonical_json([source["canonical_url"] for source in sources]))
        if self.evidence_keys.get(evidence_key, ""):
            raise Exception("evidence_bundle_already_assessed")

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
                and proposed.evidence_complete == independent.evidence_complete
                and proposed.evidence_bundle_hash == independent.evidence_bundle_hash
                and proposed.assessment_context_hash == independent.assessment_context_hash
                and proposed.snapshot_commitments_json == independent.snapshot_commitments_json
                and abs(int(proposed.confidence) - int(independent.confidence)) <= 10
            )

        verdict = json.loads(gl.vm.run_nondet_unsafe(leader_fn, validator_fn))
        authorized_amount = min(amount, available, amount * int(verdict["completion_bps"]) // 10000)
        if verdict["decision"] in ("rejected", "unverifiable"):
            authorized_amount = 0
        self.assessment_count = u64(int(self.assessment_count) + 1)
        assessment_id = "sct_" + _sha256_parts([
            order_id, invoice_key, evidence_key, verdict["assessment_context_hash"]
        ])[:20]
        record = {
            "schema_version": "spendcourt.assessment.v2", "assessment_id": assessment_id,
            "order_id": order_id, "requester": requester, "invoice_number": invoice,
            "invoice_key": invoice_key, "evidence_key": evidence_key, "requested_amount": amount,
            "authorized_amount": authorized_amount, "settled_amount": 0, "currency": order["currency"],
            "baseline_hash": order["baseline"]["baseline_hash"], "source_manifest": sources,
            "snapshot_commitments": verdict["snapshot_commitments"],
            "evidence_bundle_hash": verdict["evidence_bundle_hash"],
            "assessment_context_hash": verdict["assessment_context_hash"],
            "consensus_result": verdict, "assessed_at": _now(),
            "state": "assessed" if authorized_amount > 0 else "blocked", "settlement_ready": False,
        }
        order["assessment_ids"].append(assessment_id)
        invoice_record = {
            "order_id": order_id, "invoice_number": invoice, "invoice_key": invoice_key,
            "assessment_id": assessment_id, "requested_amount": amount,
            "authorized_amount": authorized_amount, "settled_amount": 0,
        }
        self.orders[order_id] = _canonical_json(order)
        self.assessments[assessment_id] = _canonical_json(record)
        self.invoice_keys[invoice_key] = _canonical_json(invoice_record)
        self.evidence_keys[evidence_key] = assessment_id
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
        _require_active(order)
        if assessment["order_id"] != order_id:
            raise Exception("assessment_order_mismatch")
        if assessment["state"] != "assessed" or int(assessment["authorized_amount"]) <= 0:
            raise Exception("assessment_not_authorizable")
        amount = int(assessment["authorized_amount"])
        available = int(order["remaining_budget"]) - int(order["reserved_amount"])
        if amount > available:
            raise Exception("finalization_exceeds_available_budget")
        order["reserved_amount"] = int(order["reserved_amount"]) + amount
        assessment["state"] = "finalized"
        assessment["settlement_ready"] = True
        assessment["finalized_by"] = caller
        assessment["finalized_at"] = _now()
        assessment["authorization_receipt_hash"] = _sha256(_canonical_json(assessment))
        self.orders[order_id] = _canonical_json(order)
        self.assessments[assessment_id] = _canonical_json(assessment)
        return assessment["authorization_receipt_hash"]

    @gl.public.write
    def execute_settlement(self, order_id: str, assessment_id: str, payment_execution_url: str) -> str:
        order = _load(self.orders.get(order_id, ""), "order_not_found")
        assessment = _load(self.assessments.get(assessment_id, ""), "assessment_not_found")
        caller = str(gl.message.sender_address).lower()
        if caller != order["payer"]:
            raise Exception("only_payer_can_confirm_payment")
        _require_active(order)
        if assessment["order_id"] != order_id:
            raise Exception("assessment_order_mismatch")
        if assessment["state"] != "finalized" or assessment["settlement_ready"] is not True:
            raise Exception("settlement_requires_finalized_receipt")
        if self.settlements.get(assessment_id, ""):
            raise Exception("settlement_already_recorded")
        amount = int(assessment["authorized_amount"])
        if amount <= 0 or amount > int(order["reserved_amount"]):
            raise Exception("settlement_exceeds_reserved_boundary")
        payment_source = _source(1, "payment_execution", payment_execution_url)

        def leader_fn():
            return _verify_payment_execution(order, assessment, payment_source)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                proposed = _parse_payment_verdict(leader_result.calldata)
                independent = _parse_payment_verdict(_verify_payment_execution(order, assessment, payment_source))
            except Exception:
                return False
            return proposed == independent

        payment = json.loads(gl.vm.run_nondet_unsafe(leader_fn, validator_fn))
        if payment["payment_verified"] is not True:
            raise Exception("downstream_payment_not_verified")
        order["remaining_budget"] = int(order["remaining_budget"]) - amount
        order["reserved_amount"] = int(order["reserved_amount"]) - amount
        order["settled_amount"] = int(order["settled_amount"]) + amount
        if int(order["remaining_budget"]) == 0:
            order["state"] = "settled"
        assessment["state"] = "settled"
        assessment["settlement_ready"] = False
        assessment["settled_amount"] = amount
        invoice_record = _load(self.invoice_keys.get(assessment["invoice_key"], ""), "invoice_record_not_found")
        invoice_record["settled_amount"] = int(invoice_record["settled_amount"]) + amount
        settlement = {
            "schema_version": "spendcourt.settlement.v2",
            "protocol_model": "noncustodial_verified_downstream_payment",
            "order_id": order_id, "assessment_id": assessment_id,
            "invoice_key": assessment["invoice_key"], "confirmed_by": caller,
            "payer": order["payer"], "payee": order["payee"], "currency": order["currency"],
            "settled_amount": amount, "cumulative_order_settled_amount": order["settled_amount"],
            "remaining_budget": order["remaining_budget"],
            "authorization_receipt_hash": assessment["authorization_receipt_hash"],
            "payment_execution": payment, "status": "verified", "verified_at": _now(),
        }
        settlement["settlement_hash"] = _sha256(_canonical_json(settlement))
        self.orders[order_id] = _canonical_json(order)
        self.assessments[assessment_id] = _canonical_json(assessment)
        self.invoice_keys[assessment["invoice_key"]] = _canonical_json(invoice_record)
        self.settlements[assessment_id] = _canonical_json(settlement)
        return settlement["settlement_hash"]


def _capture_baseline(title, payer, agent, payee, currency, budget, deadline, sources) -> str:
    snapshots = _render_sources(sources)
    commitments = _snapshot_commitments(sources, snapshots)
    materials = {}
    for snapshot in snapshots:
        if snapshot["source_type"] in ("service_mandate", "acceptance_policy"):
            materials[snapshot["source_type"]] = {
                "canonical_url": snapshot["canonical_url"], "snapshot_hash": snapshot["snapshot_hash"],
                "snapshot_chars": snapshot["snapshot_chars"], "complete_text": snapshot["text"],
            }
    if len(materials) != 2:
        raise Exception("complete_acceptance_requirements_required")
    baseline = {
        "service_title": title, "payer": payer, "agent": agent, "payee": payee,
        "currency": currency, "maximum_budget": budget, "deadline_timestamp": deadline,
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
        "order_id": order["order_id"], "payer": order["payer"], "agent": order["agent"],
        "payee": order["payee"], "currency": order["currency"],
        "deadline_timestamp": order["deadline_timestamp"],
        "baseline_hash": order["baseline"]["baseline_hash"],
        "service_mandate": order["baseline"]["review_materials"]["service_mandate"],
        "acceptance_policy": order["baseline"]["review_materials"]["acceptance_policy"],
        "invoice_number": invoice, "requested_amount": amount,
        "available_budget": int(order["remaining_budget"]) - int(order["reserved_amount"]),
        "delivery_commitments": commitments, "evidence_complete": True,
    }
    context_hash = _sha256(_canonical_json(context))
    prompt = f"""
You are the GenLayer Internet Court reconciling one AI-agent service invoice.
Use every complete authenticated snapshot. Compare the invoice, execution log, deliverable,
and acceptance report with the immutable service mandate and acceptance policy. Return only
minified JSON with keys: decision (fulfilled|partial|rejected|unverifiable), completion_bps
(one of 0,2500,5000,7500,10000), confidence (0-100), scope_match, invoice_authentic,
execution_verified, delivery_verified, evidence_complete, evidence_bundle_hash, summary.
All booleans must be JSON booleans. Any positive decision requires all five booleans true,
an invoice naming the exact invoice number, authenticated execution by the registered agent,
delivery to the stated acceptance requirements, and an acceptance report tied to this work.
Use unverifiable with completion_bps 0 for incomplete or contradictory evidence.
evidence_bundle_hash must equal {evidence_bundle_hash}.

Immutable context: {_canonical_json(context)}
Complete delivery evidence: {_canonical_json(snapshots)}
"""
    data = json.loads(gl.nondet.exec_prompt(prompt))
    result = {
        "decision": str(data["decision"]).lower(), "completion_bps": int(data["completion_bps"]),
        "confidence": int(data["confidence"]), "scope_match": _strict_bool(data, "scope_match"),
        "invoice_authentic": _strict_bool(data, "invoice_authentic"),
        "execution_verified": _strict_bool(data, "execution_verified"),
        "delivery_verified": _strict_bool(data, "delivery_verified"),
        "evidence_complete": _strict_bool(data, "evidence_complete"),
        "evidence_bundle_hash": str(data["evidence_bundle_hash"]),
        "assessment_context_hash": context_hash, "snapshot_commitments": commitments,
        "summary": _text(str(data["summary"]), 500, "summary_required"),
    }
    _validate_delivery_result(result)
    return _canonical_json(result)


def _verify_payment_execution(order: dict, assessment: dict, source: dict) -> str:
    snapshot = _render_sources([source])[0]
    prompt = f"""
Verify a downstream payment execution record for a noncustodial authorization protocol.
Return only minified JSON with keys: payment_verified, payer_match, payee_match, amount_match,
currency_match, receipt_match, payment_reference, payment_snapshot_hash, summary. Every match
field must be a JSON boolean. payment_verified may be true only if all match fields are true
and the complete immutable record proves a successful, non-reverted payment from payer
{order['payer']} to payee {order['payee']} for exactly {assessment['authorized_amount']}
{order['currency']}, tied to authorization receipt {assessment['authorization_receipt_hash']}.
payment_snapshot_hash must equal {snapshot['snapshot_hash']}.

Complete payment execution record: {_canonical_json(snapshot)}
"""
    data = json.loads(gl.nondet.exec_prompt(prompt))
    result = {
        "payment_verified": _strict_bool(data, "payment_verified"),
        "payer_match": _strict_bool(data, "payer_match"), "payee_match": _strict_bool(data, "payee_match"),
        "amount_match": _strict_bool(data, "amount_match"), "currency_match": _strict_bool(data, "currency_match"),
        "receipt_match": _strict_bool(data, "receipt_match"),
        "payment_reference": _text(str(data["payment_reference"]), 180, "payment_reference_required"),
        "payment_snapshot_hash": str(data["payment_snapshot_hash"]),
        "summary": _text(str(data["summary"]), 500, "summary_required"),
    }
    if result["payment_snapshot_hash"] != snapshot["snapshot_hash"]:
        raise Exception("payment_snapshot_hash_mismatch")
    matches = [result[key] for key in ("payer_match", "payee_match", "amount_match", "currency_match", "receipt_match")]
    if result["payment_verified"] is not all(matches):
        raise Exception("inconsistent_payment_verdict")
    return _canonical_json(result)


def _parse_verdict(raw: str) -> DeliveryVerdict:
    data = json.loads(raw)
    _validate_delivery_result(data)
    return DeliveryVerdict(
        data["decision"], u16(int(data["completion_bps"])), u8(int(data["confidence"])),
        _strict_bool(data, "scope_match"), _strict_bool(data, "invoice_authentic"),
        _strict_bool(data, "execution_verified"), _strict_bool(data, "delivery_verified"),
        _strict_bool(data, "evidence_complete"), str(data["evidence_bundle_hash"]),
        str(data["assessment_context_hash"]), _canonical_json(data["snapshot_commitments"]),
        str(data["summary"]),
    )


def _parse_payment_verdict(raw: str) -> PaymentVerdict:
    data = json.loads(raw)
    if len(str(data["payment_snapshot_hash"])) != 64:
        raise Exception("invalid_payment_snapshot_hash")
    matches = [_strict_bool(data, key) for key in (
        "payer_match", "payee_match", "amount_match", "currency_match", "receipt_match"
    )]
    verified = _strict_bool(data, "payment_verified")
    if verified is not all(matches):
        raise Exception("inconsistent_payment_verdict")
    return PaymentVerdict(
        verified, matches[0], matches[1], matches[2], matches[3], matches[4],
        str(data["payment_reference"]), str(data["payment_snapshot_hash"]), str(data["summary"]),
    )


def _validate_delivery_result(data: dict):
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
    flags = [_strict_bool(data, key) for key in (
        "scope_match", "invoice_authentic", "execution_verified", "delivery_verified", "evidence_complete"
    )]
    if decision == "fulfilled" and (completion != 10000 or not all(flags)):
        raise Exception("inconsistent_fulfilled_verdict")
    if decision == "partial" and (completion not in (2500, 5000, 7500) or not all(flags)):
        raise Exception("inconsistent_partial_verdict")
    if decision in ("rejected", "unverifiable") and completion != 0:
        raise Exception("inconsistent_blocked_verdict")


def _render_sources(sources):
    snapshots = []
    for source in sources:
        rendered = gl.nondet.web.render(source["canonical_url"], mode="text")
        if len(rendered) < MIN_SOURCE_CHARS:
            raise Exception("evidence_source_incomplete")
        if len(rendered) > MAX_SOURCE_CHARS:
            raise Exception("evidence_source_too_large_use_bounded_immutable_snapshot")
        snapshots.append({
            "source_index": source["source_index"], "source_type": source["source_type"],
            "canonical_url": source["canonical_url"], "source_revision": source["source_revision"],
            "url_hash": source["url_hash"], "snapshot_hash": _sha256(rendered),
            "snapshot_chars": len(rendered), "complete": True, "text": rendered,
        })
    return snapshots


def _snapshot_commitments(sources, snapshots):
    return [{
        "source_index": source["source_index"], "source_type": source["source_type"],
        "host": source["host"], "source_revision": source["source_revision"],
        "canonical_url": source["canonical_url"], "url_hash": source["url_hash"],
        "snapshot_hash": snapshot["snapshot_hash"], "snapshot_chars": snapshot["snapshot_chars"],
        "complete": snapshot["complete"],
    } for source, snapshot in zip(sources, snapshots)]


def _baseline_sources(mandate, policy, repository):
    return [
        _source(1, "service_mandate", mandate), _source(2, "acceptance_policy", policy),
        _source(3, "work_repository", repository),
    ]


def _delivery_sources(invoice, execution_log, deliverable, acceptance_report):
    return [
        _source(1, "invoice", invoice), _source(2, "execution_log", execution_log),
        _source(3, "deliverable", deliverable), _source(4, "acceptance_report", acceptance_report),
    ]


def _source(index: int, source_type: str, raw_url: str) -> dict:
    url = str(raw_url).strip()
    if not url.startswith("https://") or "?" in url or "#" in url or len(url) > 700:
        raise Exception("sources_require_canonical_https_without_query")
    remainder = url[8:]
    if "/" not in remainder:
        raise Exception("source_path_required")
    host, path = remainder.split("/", 1)
    host = host.lower()
    parts = [part for part in path.split("/") if part]
    revision = ""
    if host == "github.com" and len(parts) >= 5 and parts[2] in ("blob", "tree"):
        revision = parts[3].lower()
    elif host == "raw.githubusercontent.com" and len(parts) >= 4:
        revision = parts[2].lower()
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise Exception("source_requires_immutable_git_commit_url")
    canonical = "https://" + host + "/" + "/".join(parts)
    return {
        "source_index": index, "source_type": source_type, "host": host,
        "source_revision": revision, "canonical_url": canonical, "url_hash": _sha256(canonical),
    }


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


def _future_timestamp(value: str) -> int:
    timestamp = _positive_amount(value, "deadline_timestamp_invalid")
    if timestamp <= _now():
        raise Exception("deadline_must_be_in_future")
    return timestamp


def _require_active(order: dict):
    if order["state"] != "open":
        raise Exception("order_not_open")
    if _now() > int(order["deadline_timestamp"]):
        raise Exception("order_deadline_expired")


def _strict_bool(data: dict, key: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise Exception("invalid_boolean_" + key)
    return value


def _invoice_key(order_id: str, invoice_number: str) -> str:
    return _sha256_parts([order_id, " ".join(str(invoice_number).strip().lower().split())])


def _now() -> int:
    return int(gl.block.timestamp)


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_parts(parts) -> str:
    return _sha256(_canonical_json([str(part) for part in parts]))
