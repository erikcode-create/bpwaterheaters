from __future__ import annotations

import json
import time as time_module
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime

from bp_water_heaters.erp import prepare_booking_erp_records, record_payment_for_booking, record_payment_for_invoice
from bp_water_heaters.payments import classify_stripe_event, sanitize_stripe_event_for_audit
from bp_water_heaters.security_limits import client_ip, require_frappe_rate_limit
from bp_water_heaters.taxes import select_tax_rule
from bp_water_heaters.urls import public_url

CALL_OUT_FEE = Decimal("85.00")
SLOT_MINUTES = 60
BUFFER_MINUTES = 30
HOLD_MINUTES = 30
WORK_START = time(9, 0)
WORK_END = time(17, 0)
ACTIVE_STATUSES = ("Pending Payment", "Payment Pending Settlement", "Confirmed")


@frappe.whitelist(allow_guest=True)
def get_available_slots(start_date: str | None = None, days: int = 14):
	"""Return bookable one-hour estimate slots with a 30 minute service buffer."""

	days = min(max(int(days or 14), 1), 45)
	first_day = getdate(start_date) if start_date else getdate()
	bookings = _get_bookings(first_day, first_day + timedelta(days=days + 1))
	slots = []
	current_day = first_day
	now = now_datetime()

	for _ in range(days):
		if current_day.weekday() < 5:
			for slot_start in _slots_for_day(current_day):
				slot_end = slot_start + timedelta(minutes=SLOT_MINUTES)
				if slot_start <= now:
					continue
				if _slot_is_available(slot_start, slot_end, bookings):
					slots.append(
						{
							"start": slot_start.isoformat(),
							"end": slot_end.isoformat(),
							"label": slot_start.strftime("%A, %b %-d at %-I:%M %p"),
						}
					)
		current_day += timedelta(days=1)

	return {"slots": slots, "callout_fee": float(CALL_OUT_FEE), "hold_minutes": HOLD_MINUTES}


@frappe.whitelist(allow_guest=True)
def create_booking_hold(
	customer_name: str,
	email: str,
	phone: str,
	property_address: str,
	city: str,
	state: str,
	postal_code: str,
	preferred_start: str,
	service_type: str = "Estimate",
	county: str | None = None,
	notes: str | None = None,
):
	require_frappe_rate_limit(frappe, "booking-hold-ip", client_ip(frappe), limit=8, window_seconds=3600)
	require_frappe_rate_limit(frappe, "booking-hold-email", email, limit=4, window_seconds=3600)
	slot_start = get_datetime(preferred_start)
	slot_end = slot_start + timedelta(minutes=SLOT_MINUTES)

	_validate_customer_input(customer_name, email, phone, property_address, city, state, postal_code)
	_validate_slot(slot_start, slot_end)

	if not _slot_is_available(slot_start, slot_end, _get_bookings(slot_start.date(), slot_end.date() + timedelta(days=1))):
		frappe.throw(_("That appointment time was just taken. Please choose another slot."))

	booking = frappe.get_doc(
		{
			"doctype": "BPWH Booking",
			"customer_name": customer_name.strip(),
			"email": email.strip().lower(),
			"phone": phone.strip(),
			"service_type": service_type or "Estimate",
			"property_address": property_address.strip(),
			"city": city.strip(),
			"county": (county or "").strip(),
			"state": state.strip().upper(),
			"postal_code": postal_code.strip(),
			"preferred_start": slot_start,
			"preferred_end": slot_end,
			"hold_expires_at": add_to_date(now_datetime(), minutes=HOLD_MINUTES),
			"status": "Pending Payment",
			"callout_fee": CALL_OUT_FEE,
			"stripe_payment_status": "Not Started",
			"payment_settlement_status": "Not Started",
			"notes": notes,
		}
	)
	booking.insert(ignore_permissions=True)
	_apply_tax_rule_to_booking(booking)

	checkout = _create_checkout_session_if_configured(booking)
	return {
		"booking": booking.name,
		"status": booking.status,
		"hold_expires_at": booking.hold_expires_at,
		"callout_fee": float(CALL_OUT_FEE),
		"checkout": checkout,
	}


@frappe.whitelist(allow_guest=True)
def submit_contact_request(full_name: str, email: str, phone: str, message: str, source: str = "Website"):
	require_frappe_rate_limit(frappe, "contact-request-ip", client_ip(frappe), limit=8, window_seconds=3600)
	require_frappe_rate_limit(frappe, "contact-request-email", email, limit=4, window_seconds=3600)
	if not full_name or not email or not phone or not message:
		frappe.throw(_("Please include your name, email, phone, and message."))

	doc = frappe.get_doc(
		{
			"doctype": "BPWH Contact Request",
			"full_name": full_name.strip(),
			"email": email.strip().lower(),
			"phone": phone.strip(),
			"message": message.strip(),
			"source": source,
			"status": "New",
		}
	)
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist(allow_guest=True)
def stripe_webhook():
	"""Handle Stripe Checkout webhooks once the endpoint is registered in Stripe."""

	stripe_secret = frappe.conf.get("bpwh_stripe_webhook_secret")
	if not stripe_secret:
		frappe.throw(_("Stripe webhook secret is not configured."))

	try:
		import stripe
	except ImportError:
		frappe.throw(_("Stripe Python package is not installed."))

	payload = frappe.request.get_data()
	signature = frappe.get_request_header("Stripe-Signature")
	event = stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=stripe_secret)

	_process_stripe_event(event)

	return {"received": True}


def _create_checkout_session_if_configured(booking):
	stripe_key = frappe.conf.get("bpwh_stripe_secret_key")
	if not stripe_key:
		return {
			"configured": False,
			"url": None,
			"message": "Stripe credentials are not connected yet.",
		}

	try:
		import stripe
	except ImportError:
		return {
			"configured": False,
			"url": None,
			"message": "Stripe Python package is not installed yet.",
		}

	stripe.api_key = stripe_key
	stripe.api_version = "2026-04-22.dahlia"
	customer_id = _ensure_stripe_customer(stripe, booking)
	session_args = {
		"mode": "payment",
		"success_url": public_url("/bpwaterheaters", {"booking": booking.name, "payment": "success"}),
		"cancel_url": public_url("/bpwaterheaters", {"booking": booking.name, "payment": "cancelled"}),
		"customer": customer_id,
		"client_reference_id": booking.name,
		"payment_method_types": ["card", "us_bank_account"],
		"line_items": [
			{
				"price_data": {
					"currency": "usd",
					"product_data": {
						"name": "BP Water Heaters estimate call-out fee",
						"description": "Credited toward approved replacement or larger service work.",
					},
					"unit_amount": int(CALL_OUT_FEE * 100),
				},
				"quantity": 1,
			}
		],
		"metadata": _stripe_metadata(booking),
		"payment_intent_data": {"metadata": _stripe_metadata(booking)},
		"expires_at": _stripe_expires_at(),
	}
	session = stripe.checkout.Session.create(
		**session_args,
		idempotency_key=_stripe_idempotency_key("booking", booking),
	)

	booking.db_set(
		{
			"stripe_checkout_session_id": session.id,
			"stripe_payment_status": "Open",
			"payment_settlement_status": "Pending",
		},
		update_modified=True,
	)

	return {"configured": True, "url": session.url, "session_id": session.id}


def _stripe_expires_at():
	return int(time_module.time()) + (HOLD_MINUTES * 60)


def _ensure_stripe_customer(stripe, booking):
	if booking.get("stripe_customer_id"):
		return booking.stripe_customer_id

	customer = stripe.Customer.create(
		email=booking.email,
		name=booking.customer_name,
		phone=booking.phone,
		metadata=_stripe_metadata(booking),
		idempotency_key=_stripe_idempotency_key("customer", booking),
	)
	booking.db_set("stripe_customer_id", customer.id, update_modified=False)
	return customer.id


def _stripe_idempotency_key(kind, booking):
	booking_name = booking.get("name") if hasattr(booking, "get") else booking.name
	creation = booking.get("creation")
	if hasattr(creation, "strftime"):
		creation_token = creation.strftime("%Y%m%d%H%M%S%f")
	else:
		creation_token = "".join(ch for ch in str(creation or "") if ch.isalnum())
	return f"bpwh-{kind}-{booking_name}-{creation_token or 'pending'}"[:255]


def _stripe_metadata(booking):
	return {
		"brand": "bp_water_heaters",
		"erp_site": frappe.local.site,
		"booking_id": booking.name,
		"service_type": "estimate_callout",
	}


def _process_stripe_event(event):
	event_id = event.get("id")
	event_type = event.get("type")
	payload = event.get("data", {}).get("object", {})

	if event_id and frappe.db.exists("BPWH Stripe Event", event_id):
		return

	state = classify_stripe_event(event_type, payload)
	sales_invoice = _stripe_sales_invoice(payload)
	if sales_invoice:
		_process_invoice_stripe_event(event, state, sales_invoice)
		return

	if not state.booking_id or not frappe.db.exists("BPWH Booking", state.booking_id):
		_record_stripe_event(event_id, event_type, state.booking_id, event, "Ignored")
		frappe.log_error(title="BPWH Stripe webhook missing booking", message=frappe.as_json(sanitize_stripe_event_for_audit(event)))
		return

	booking = frappe.get_doc("BPWH Booking", state.booking_id)
	try:
		booking.status = state.booking_status
		booking.stripe_payment_status = state.payment_status
		booking.payment_settlement_status = state.settlement_status
		booking.payment_method_type = state.payment_method_type
		booking.stripe_payment_intent = state.payment_intent
		booking.stripe_latest_event_id = event_id
		booking.save(ignore_permissions=True)

		if state.booking_status == "Payment Pending Settlement":
			prepare_booking_erp_records(booking)
		elif state.booking_status == "Confirmed" and state.payment_status == "Paid":
			record_payment_for_booking(booking, state.payment_method_type)

		_record_stripe_event(event_id, event_type, booking.name, event, "Processed")
	except Exception as exc:
		_record_stripe_event(event_id, event_type, booking.name, event, "Failed", str(exc))
		raise


def _process_invoice_stripe_event(event, state, sales_invoice):
	event_id = event.get("id")
	event_type = event.get("type")

	if not frappe.db.exists("Sales Invoice", sales_invoice):
		_record_stripe_event(event_id, event_type, None, event, "Ignored", sales_invoice=sales_invoice)
		frappe.log_error(title="BPWH Stripe webhook missing invoice", message=frappe.as_json(sanitize_stripe_event_for_audit(event)))
		return

	try:
		if state.booking_status == "Confirmed" and state.payment_status == "Paid":
			record_payment_for_invoice(sales_invoice, state.payment_method_type, state.payment_intent)
		_record_stripe_event(event_id, event_type, None, event, "Processed", sales_invoice=sales_invoice)
	except Exception as exc:
		_record_stripe_event(event_id, event_type, None, event, "Failed", str(exc), sales_invoice=sales_invoice)
		raise


def _stripe_sales_invoice(payload):
	return (payload.get("metadata") or {}).get("sales_invoice")


def _record_stripe_event(event_id, event_type, booking_id, event, status, error=None, sales_invoice=None):
	if not event_id or frappe.db.exists("BPWH Stripe Event", event_id):
		return

	frappe.get_doc(
		{
			"doctype": "BPWH Stripe Event",
			"event_id": event_id,
			"event_type": event_type,
			"booking": booking_id if booking_id and frappe.db.exists("BPWH Booking", booking_id) else None,
			"sales_invoice": sales_invoice if sales_invoice and frappe.db.exists("Sales Invoice", sales_invoice) else None,
			"status": status,
			"processed_at": now_datetime(),
			"error": error,
			"payload": frappe.as_json(sanitize_stripe_event_for_audit(event)),
		}
	).insert(ignore_permissions=True)


def redact_stored_stripe_payloads(limit: int = 500):
	for row in frappe.get_all("BPWH Stripe Event", fields=["name", "payload"], limit_page_length=limit):
		if not row.get("payload"):
			continue
		try:
			payload = json.loads(row.payload)
		except (TypeError, ValueError):
			continue
		if "data" not in payload:
			continue
		sanitized = sanitize_stripe_event_for_audit(payload)
		frappe.db.set_value(
			"BPWH Stripe Event",
			row.name,
			"payload",
			frappe.as_json(sanitized),
			update_modified=False,
		)


def _apply_tax_rule_to_booking(booking):
	rule = select_tax_rule(booking.state, booking.city, booking.get("county"))
	tax_template = _existing_sales_tax_template(rule.template_name)
	booking.db_set(
		{
			"tax_template": tax_template,
			"tax_rate": rule.rate,
			"tax_source_url": rule.source_url,
		},
		update_modified=False,
	)


def _existing_sales_tax_template(template_name):
	return frappe.db.exists("Sales Taxes and Charges Template", template_name) or frappe.db.exists(
		"Sales Taxes and Charges Template", f"{template_name} - BPWH"
	)


def _validate_customer_input(customer_name, email, phone, property_address, city, state, postal_code):
	if not all([customer_name, email, phone, property_address, city, state, postal_code]):
		frappe.throw(_("Please fill out every required field."))
	if state.strip().upper() not in {"NV", "CA"}:
		frappe.throw(_("Online booking is currently available for Nevada and California addresses."))


def _validate_slot(slot_start: datetime, slot_end: datetime):
	if slot_start.weekday() >= 5:
		frappe.throw(_("Online booking is available Monday through Friday."))
	if slot_start.time() < WORK_START or slot_end.time() > WORK_END:
		frappe.throw(_("Online booking is available from 9 AM to 5 PM."))


def _slots_for_day(day: date):
	slot_start = datetime.combine(day, WORK_START)
	end_of_day = datetime.combine(day, WORK_END)
	step = timedelta(minutes=SLOT_MINUTES + BUFFER_MINUTES)
	while slot_start + timedelta(minutes=SLOT_MINUTES) <= end_of_day:
		yield slot_start
		slot_start += step


def _get_bookings(start_day: date, end_day: date):
	return frappe.get_all(
		"BPWH Booking",
		filters={
			"preferred_start": ["<", datetime.combine(end_day, time.max)],
			"preferred_end": [">", datetime.combine(start_day, time.min)],
			"status": ["in", ACTIVE_STATUSES],
		},
		fields=["name", "preferred_start", "preferred_end", "status", "hold_expires_at"],
	)


def _slot_is_available(slot_start: datetime, slot_end: datetime, bookings) -> bool:
	blocked_start = slot_start - timedelta(minutes=BUFFER_MINUTES)
	blocked_end = slot_end + timedelta(minutes=BUFFER_MINUTES)
	now = now_datetime()

	for booking in bookings:
		if booking.status == "Pending Payment" and booking.hold_expires_at and get_datetime(booking.hold_expires_at) <= now:
			continue

		existing_start = get_datetime(booking.preferred_start)
		existing_end = get_datetime(booking.preferred_end)
		if existing_start < blocked_end and existing_end > blocked_start:
			return False

	return True
