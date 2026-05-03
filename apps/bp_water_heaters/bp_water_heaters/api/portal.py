from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from bp_water_heaters.portal_view import _annotate_invoice, build_portal_view
from bp_water_heaters.portal_security import (
	checkout_return_is_reusable,
	hash_return_token,
	hash_token,
	issue_checkout_return_token,
	issue_token,
)
from bp_water_heaters.security_limits import clamp_limit, client_ip, require_frappe_rate_limit
from bp_water_heaters.urls import portal_url

PORTAL_INITIAL_LIMIT = 25
PORTAL_MAX_LIMIT = 50


@frappe.whitelist(allow_guest=True)
def request_magic_link(email: str):
	require_frappe_rate_limit(frappe, "portal-magic-ip", client_ip(frappe), limit=10, window_seconds=3600)
	normalized_email = (email or "").strip().lower()
	if not normalized_email:
		frappe.throw(_("Please enter your email address."))
	require_frappe_rate_limit(frappe, "portal-magic-email", normalized_email, limit=3, window_seconds=3600)

	issued = issue_token(normalized_email)
	customer = _customer_for_email(normalized_email)
	booking = frappe.db.get_value("BPWH Booking", {"email": normalized_email}, "name")
	_insert_portal_token(issued, customer=customer, booking=booking)

	if customer or booking:
		_send_magic_link(normalized_email, issued.token)

	return {"ok": True, "message": "If that email has BP Water Heaters activity, a portal link has been sent."}


@frappe.whitelist(allow_guest=True)
def get_portal_data(token: str):
	token_doc = _validate_token(token)
	customer = token_doc.customer or _customer_for_email(token_doc.email)
	require_frappe_rate_limit(frappe, "portal-data-token", token_doc.name, limit=120, window_seconds=3600)
	rows = _portal_rows(token_doc.email, customer, limit=PORTAL_INITIAL_LIMIT)

	token_doc.db_set("last_accessed_at", now_datetime(), update_modified=False)
	view = build_portal_view(
		email=token_doc.email,
		customer=customer,
		bookings=rows["bookings"]["rows"],
		invoices=rows["invoices"]["rows"],
		projects=rows["projects"]["rows"],
		conversations=rows["conversations"]["rows"],
	)
	view["pagination"] = {section: data["pagination"] for section, data in rows.items()}
	return view


@frappe.whitelist(allow_guest=True)
def get_portal_history(token: str, section: str, cursor: str | None = None, limit: int = 25):
	token_doc = _validate_token(token)
	customer = token_doc.customer or _customer_for_email(token_doc.email)
	require_frappe_rate_limit(frappe, "portal-history-token", token_doc.name, limit=180, window_seconds=3600)
	if section not in {"bookings", "invoices", "projects", "conversations"}:
		frappe.throw(_("Unsupported portal history section."))
	data = _portal_section_rows(token_doc.email, customer, section, limit=clamp_limit(limit, 25, PORTAL_MAX_LIMIT), cursor=cursor)
	if section == "invoices":
		data["rows"] = [_annotate_invoice(row) for row in data["rows"]]
	return {"section": section, **data}


@frappe.whitelist(allow_guest=True)
def create_invoice_checkout(token: str, sales_invoice: str):
	token_doc = _validate_token(token)
	require_frappe_rate_limit(
		frappe,
		"portal-checkout",
		f"{token_doc.name}:{sales_invoice}",
		limit=5,
		window_seconds=600,
	)
	if not _invoice_belongs_to_email(sales_invoice, token_doc.email):
		frappe.throw(_("That invoice is not available for this portal link."))

	stripe_key = frappe.conf.get("bpwh_stripe_secret_key")
	if not stripe_key:
		return {"configured": False, "message": "Stripe credentials are not connected yet."}

	try:
		import stripe
	except ImportError:
		return {"configured": False, "message": "Stripe Python package is not installed yet."}

	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	amount = float(invoice.outstanding_amount or 0)
	if amount <= 0:
		frappe.throw(_("That invoice does not have an outstanding balance."))

	active_checkout = _active_checkout_return(token_doc.email, invoice.name)
	if active_checkout:
		return {
			"configured": True,
			"url": active_checkout.checkout_url,
			"session_id": active_checkout.stripe_checkout_session_id,
			"reused": True,
		}

	metadata = {
		"brand": "bp_water_heaters",
		"erp_site": frappe.local.site,
		"sales_invoice": invoice.name,
		"service_type": "invoice_payment",
	}
	return_token, return_token_name = _create_checkout_return_token(token_doc, invoice.name)
	stripe.api_key = stripe_key
	stripe.api_version = "2026-04-22.dahlia"
	try:
		session = stripe.checkout.Session.create(
			mode="payment",
			customer_email=token_doc.email,
			customer_creation="always",
			client_reference_id=invoice.name,
			payment_method_types=["card", "us_bank_account"],
			success_url=portal_url("/bpwaterheaters-portal", {"checkout_return": return_token, "payment": "success"}),
			cancel_url=portal_url("/bpwaterheaters-portal", {"checkout_return": return_token, "payment": "cancelled"}),
			line_items=[
				{
					"price_data": {
						"currency": "usd",
						"product_data": {"name": f"BP Water Heaters invoice {invoice.name}"},
						"unit_amount": int(amount * 100),
					},
					"quantity": 1,
				}
			],
			metadata=metadata,
			payment_intent_data={"metadata": metadata},
			idempotency_key=f"bpwh-invoice-{invoice.name}-{return_token_name}",
		)
	except Exception:
		frappe.db.set_value("BPWH Portal Return Token", return_token_name, "status", "Expired", update_modified=True)
		raise

	frappe.db.set_value(
		"BPWH Portal Return Token",
		return_token_name,
		{
			"stripe_checkout_session_id": session.id,
			"checkout_url": session.url,
		},
		update_modified=True,
	)
	return {"configured": True, "url": session.url, "session_id": session.id, "reused": False}


@frappe.whitelist(allow_guest=True)
def consume_checkout_return(checkout_return: str, payment: str | None = None):
	return_doc = _validate_checkout_return(checkout_return)
	issued = issue_token(return_doc.email)
	customer = _customer_for_email(return_doc.email)
	booking = frappe.db.get_value("BPWH Booking", {"email": return_doc.email}, "name")
	_insert_portal_token(issued, customer=customer, booking=booking)
	return_doc.db_set(
		{
			"status": "Consumed",
			"payment_return": (payment or "")[:32],
			"consumed_at": now_datetime(),
		},
		update_modified=True,
	)
	if return_doc.portal_token:
		frappe.db.set_value("BPWH Portal Token", return_doc.portal_token, "status", "Revoked", update_modified=True)
	return {
		"ok": True,
		"token": issued.token,
		"payment": payment,
		"message": "Payment return accepted.",
	}


def _validate_token(token: str):
	token_hash = hash_token((token or "").strip())
	name = frappe.db.get_value("BPWH Portal Token", {"token_hash": token_hash, "status": "Active"}, "name")
	if not name:
		frappe.throw(_("This portal link is invalid or expired."))

	doc = frappe.get_doc("BPWH Portal Token", name)
	if get_datetime(doc.expires_at) <= now_datetime():
		doc.db_set("status", "Expired", update_modified=True)
		frappe.throw(_("This portal link has expired."))
	return doc


def _validate_checkout_return(checkout_return: str):
	token_hash = hash_return_token((checkout_return or "").strip())
	name = frappe.db.get_value("BPWH Portal Return Token", {"token_hash": token_hash, "status": "Active"}, "name")
	if not name:
		frappe.throw(_("This checkout return link is invalid or expired."))
	doc = frappe.get_doc("BPWH Portal Return Token", name)
	if get_datetime(doc.expires_at) <= now_datetime():
		doc.db_set("status", "Expired", update_modified=True)
		frappe.throw(_("This checkout return link has expired."))
	return doc


def _insert_portal_token(issued, customer=None, booking=None):
	token_doc = frappe.get_doc(
		{
			"doctype": "BPWH Portal Token",
			"email": issued.email,
			"token_hash": issued.token_hash,
			"expires_at": issued.expires_at.replace(tzinfo=None),
			"status": "Active",
			"customer": customer,
			"booking": booking,
		}
	)
	token_doc.insert(ignore_permissions=True)
	return token_doc


def _create_checkout_return_token(token_doc, sales_invoice: str):
	issued = issue_checkout_return_token(token_doc.name, token_doc.email, sales_invoice)
	doc = frappe.get_doc(
		{
			"doctype": "BPWH Portal Return Token",
			"email": issued.email,
			"token_hash": issued.token_hash,
			"status": "Active",
			"expires_at": issued.expires_at.replace(tzinfo=None),
			"portal_token": token_doc.name,
			"sales_invoice": sales_invoice,
		}
	)
	doc.insert(ignore_permissions=True)
	return issued.token, doc.name


def _active_checkout_return(email: str, sales_invoice: str):
	now = now_datetime()
	rows = frappe.get_all(
		"BPWH Portal Return Token",
		filters={
			"email": email,
			"sales_invoice": sales_invoice,
			"status": "Active",
			"expires_at": [">", now],
		},
		fields=["name", "status", "expires_at", "stripe_checkout_session_id", "checkout_url"],
		order_by="creation desc",
		limit_page_length=5,
	)
	for row in rows:
		if checkout_return_is_reusable(row, now=now):
			return row
	return None


def _portal_rows(email: str, customer: str | None, limit: int):
	return {
		"bookings": _portal_section_rows(email, customer, "bookings", limit),
		"invoices": _portal_section_rows(email, customer, "invoices", limit),
		"projects": _portal_section_rows(email, customer, "projects", limit),
		"conversations": _portal_section_rows(email, customer, "conversations", limit),
	}


def _portal_section_rows(email: str, customer: str | None, section: str, limit: int, cursor: str | None = None):
	page_limit = clamp_limit(limit, PORTAL_INITIAL_LIMIT, PORTAL_MAX_LIMIT)
	limit_start = clamp_limit(cursor, 0, 100000, minimum=0)
	query = _portal_section_query(email, customer, section)
	rows = frappe.get_all(
		query["doctype"],
		filters=query["filters"],
		fields=query["fields"],
		order_by=query["order_by"],
		limit_start=limit_start,
		limit_page_length=page_limit + 1,
	)
	has_more = len(rows) > page_limit
	rows = rows[:page_limit]
	return {
		"rows": rows,
		"pagination": {
			"cursor": str(limit_start),
			"next_cursor": str(limit_start + page_limit) if has_more else None,
			"has_more": has_more,
			"limit": page_limit,
		},
	}


def _portal_section_query(email: str, customer: str | None, section: str):
	if section == "bookings":
		return {
			"doctype": "BPWH Booking",
			"filters": {"email": email},
			"fields": [
				"name",
				"customer_name",
				"service_type",
				"property_address",
				"city",
				"state",
				"postal_code",
				"preferred_start",
				"preferred_end",
				"status",
				"stripe_payment_status",
				"payment_settlement_status",
				"sales_invoice",
				"payment_entry",
				"project",
				"tax_rate",
			],
			"order_by": "preferred_start desc",
		}
	if section == "invoices":
		return {
			"doctype": "Sales Invoice",
			"filters": {"customer": customer or "__no_customer__"},
			"fields": ["name", "posting_date", "grand_total", "outstanding_amount", "status"],
			"order_by": "posting_date desc",
		}
	if section == "projects":
		return {
			"doctype": "Project",
			"filters": {"customer": customer or "__no_customer__"},
			"fields": ["name", "project_name", "status", "percent_complete", "expected_start_date", "expected_end_date"],
			"order_by": "modified desc",
		}
	return {
		"doctype": "BPWH Chat Conversation",
		"filters": {"email": email},
		"fields": ["name", "subject", "status", "last_message_at", "booking"],
		"order_by": "last_message_at desc",
	}


def _send_magic_link(email, token):
	link = portal_url("/bpwaterheaters-portal", {"token": token})
	frappe.sendmail(
		recipients=[email],
		subject="Your BP Water Heaters portal link",
		message=f"Use this secure link to view your BP Water Heaters bookings, jobs, invoices, and chat: {link}",
		now=False,
	)


def _customer_for_email(email):
	contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	if not contact_name:
		return None
	for link in frappe.get_doc("Contact", contact_name).get("links", []):
		if link.link_doctype == "Customer":
			return link.link_name
	return None


def _invoice_belongs_to_email(sales_invoice, email):
	if not frappe.db.exists("Sales Invoice", sales_invoice):
		return False
	customer = frappe.db.get_value("Sales Invoice", sales_invoice, "customer")
	return customer and customer == _customer_for_email(email)
