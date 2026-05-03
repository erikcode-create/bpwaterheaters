from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

SAFE_STRIPE_METADATA_KEYS = {"brand", "erp_site", "booking_id", "sales_invoice", "service_type"}


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


def sanitize_stripe_event_for_audit(event: dict[str, Any]) -> dict[str, Any]:
	obj = (event.get("data") or {}).get("object") or {}
	metadata = obj.get("metadata") or {}
	return {
		"event_id": event.get("id"),
		"event_type": event.get("type"),
		"object": {
			"id": obj.get("id"),
			"object": obj.get("object"),
			"client_reference_id": obj.get("client_reference_id"),
			"payment_status": obj.get("payment_status"),
			"status": obj.get("status"),
			"payment_intent": obj.get("payment_intent"),
			"payment_method_types": obj.get("payment_method_types"),
			"metadata": {key: metadata.get(key) for key in SAFE_STRIPE_METADATA_KEYS if metadata.get(key)},
		},
	}


def stripe_payload_needs_redaction(payload: Any) -> bool:
	return isinstance(payload, dict) and isinstance(payload.get("data"), dict) and isinstance(
		payload.get("data", {}).get("object"),
		dict,
	)


def redact_stripe_payload_rows(
	fetch_rows: Callable[[str | None, int], Sequence[Mapping[str, Any]]],
	store_payload: Callable[[str, dict[str, Any]], None],
	batch_size: int = 500,
) -> dict[str, int]:
	batch_size = max(1, int(batch_size or 500))
	last_name: str | None = None
	stats = {"scanned": 0, "redacted": 0, "skipped": 0}

	while True:
		rows = list(fetch_rows(last_name, batch_size) or [])
		if not rows:
			break

		advanced = False
		for row in rows:
			row_name = _row_value(row, "name")
			if not row_name:
				stats["skipped"] += 1
				continue

			row_name = str(row_name)
			if last_name is not None and row_name <= last_name:
				stats["skipped"] += 1
				continue

			last_name = row_name
			advanced = True
			stats["scanned"] += 1

			raw_payload = _row_value(row, "payload")
			if not raw_payload:
				stats["skipped"] += 1
				continue

			try:
				payload = json.loads(raw_payload) if isinstance(raw_payload, (str, bytes, bytearray)) else raw_payload
			except (TypeError, ValueError):
				stats["skipped"] += 1
				continue

			if not stripe_payload_needs_redaction(payload):
				stats["skipped"] += 1
				continue

			store_payload(row_name, sanitize_stripe_event_for_audit(payload))
			stats["redacted"] += 1

		if not advanced or len(rows) < batch_size:
			break

	return stats


def _row_value(row: Mapping[str, Any], key: str):
	if isinstance(row, dict):
		return row.get(key)
	return getattr(row, key, None)
