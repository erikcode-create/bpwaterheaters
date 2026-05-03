from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StripeEventState:
	booking_id: str | None
	booking_status: str
	payment_status: str
	settlement_status: str
	payment_method_type: str | None
	payment_intent: str | None


def classify_stripe_event(event_type: str, session: dict[str, Any]) -> StripeEventState:
	booking_id = (session.get("metadata") or {}).get("booking_id") or session.get("client_reference_id")
	payment_method_type = _payment_method_type(event_type, session)
	payment_status = session.get("payment_status")
	payment_intent = session.get("payment_intent")

	if event_type == "checkout.session.expired":
		return StripeEventState(booking_id, "Expired", "Expired", "Expired", payment_method_type, payment_intent)

	if event_type in {"checkout.session.async_payment_failed", "payment_intent.payment_failed"}:
		return StripeEventState(booking_id, "Payment Failed", "Failed", "Failed", payment_method_type, payment_intent)

	if event_type in {"charge.refunded", "refund.created"}:
		return StripeEventState(booking_id, "Refunded", "Refunded", "Refunded", payment_method_type, payment_intent)

	if event_type == "charge.dispute.created":
		return StripeEventState(booking_id, "Disputed", "Disputed", "Disputed", payment_method_type, payment_intent)

	if event_type == "checkout.session.async_payment_succeeded":
		return StripeEventState(booking_id, "Confirmed", "Paid", "Settled", payment_method_type, payment_intent)

	if event_type == "checkout.session.completed":
		if payment_method_type == "us_bank_account" and payment_status != "paid":
			return StripeEventState(
				booking_id,
				"Payment Pending Settlement",
				"Pending Settlement",
				"Pending",
				payment_method_type,
				payment_intent,
			)
		return StripeEventState(booking_id, "Confirmed", "Paid", "Settled", payment_method_type, payment_intent)

	return StripeEventState(booking_id, "Pending Payment", "Open", "Unknown", payment_method_type, payment_intent)


def _payment_method_type(event_type: str, session: dict[str, Any]) -> str | None:
	payment_method_types = session.get("payment_method_types") or []
	if event_type.startswith("checkout.session.async_") and "us_bank_account" in payment_method_types:
		return "us_bank_account"
	if session.get("payment_status") != "paid" and "us_bank_account" in payment_method_types:
		return "us_bank_account"
	if len(payment_method_types) == 1:
		return payment_method_types[0]

	payment_method_details = session.get("payment_method_details") or {}
	if payment_method_details.get("type"):
		return payment_method_details["type"]

	return None
