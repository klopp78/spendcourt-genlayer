# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Payable relay for executing a SpendCourt authorization receipt."""

from genlayer import *


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


class SpendCourtPaymentRelay(gl.Contract):
    payment_count: u64
    latest_payment: str
    used_receipts: TreeMap[str, bool]

    def __init__(self):
        self.payment_count = u64(0)
        self.latest_payment = ""

    @gl.public.write.payable
    def execute_authorized_payment(
        self,
        order_id: str,
        assessment_id: str,
        authorization_receipt_hash: str,
        payee: str,
    ) -> None:
        receipt = authorization_receipt_hash.strip().lower()
        if len(receipt) != 64:
            raise Exception("invalid_authorization_receipt")
        if self.used_receipts.get(receipt, False):
            raise Exception("authorization_receipt_already_used")
        if gl.message.value == u256(0):
            raise Exception("payment_value_required")

        recipient = str(Address(payee))
        record = (
            "spendcourt.payment.v1|"
            + order_id.strip()
            + "|"
            + assessment_id.strip()
            + "|"
            + receipt
            + "|"
            + str(gl.message.sender_address).lower()
            + "|"
            + recipient.lower()
            + "|"
            + str(gl.message.value)
        )
        self.used_receipts[receipt] = True
        self.payment_count = u64(int(self.payment_count) + 1)
        self.latest_payment = record
        _Recipient(Address(payee)).emit_transfer(value=gl.message.value)

    @gl.public.view
    def get_latest_payment(self) -> str:
        return self.latest_payment

