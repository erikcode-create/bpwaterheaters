from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from bp_water_heaters.portal_security import hash_token, issue_token
from bp_water_heaters.urls import portal_url


@frappe.whitelist(allow_guest=True)
def request_magic_link(email: str):
	normalized_email = (email or "").strip().lower()
	if not normalized_email:
		frappe.throw(_("Please enter your email address."))

	issued = issue_token(normalized_email)
	customer = _customer_for_email(normalized_email)
	booking = frappe.db.get_value("BPWH Booking", {"email": normalized_email}, "name")
	token_doc = frappe.get_doc(
		{
			"doctype": "BPWH Portal Token",
			"email": normalized_email,
			"token_hash": issued.token_hash,
			"expires_at": issued.expires_at.replace(tzinfo=None),
			"status": "Active",
			"customer": customer,
			"booking": booking,
		}
	)
	token_doc.insert(ignore_permissions=True)

	if customer or booking:
		_send_magic_link(normalized_email, issued.token)

	return {"ok": True, "message": "If that email has BP Water Heaters activity, a portal link has been sent."}


@frappe.whitelist(allow_guest=True)
def get_portal_data(token: str):
	token_doc = _validate_token(token)
	customer = token_doc.customer or _customer_for_email(token_doc.email)

	bookings = frappe.get_all(
		"BPWH Booking",
		filters={"email": token_doc.email},
		fields=[
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
		order_by="preferred_start desc",
	)
	invoices = []
	projects = []
	if customer:
		invoices = frappe.get_all(
			"Sales Invoice",
			filters={"customer": customer},
			fields=["name", "posting_date", "grand_total", "outstanding_amount", "status"],
			order_by="posting_date desc",
		)
		projects = frappe.get_all(
			"Project",
			filters={"customer": customer},
			fields=["name", "project_name", "status", "percent_complete", "expected_start_date", "expected_end_date"],
			order_by="modified desc",
		)

	conversations = frappe.get_all(
		"BPWH Chat Conversation",
		filters={"email": token_doc.email},
		fields=["name", "subject", "status", "last_message_at", "booking"],
		order_by="last_message_at desc",
	)
	token_doc.db_set("last_accessed_at", now_datetime(), update_modified=False)
	return {
		"email": token_doc.email,
		"customer": customer,
		"bookings": bookings,
		"invoices": invoices,
		"projects": projects,
		"conversations": conversations,
	}


@frappe.whitelist(allow_guest=True)
def create_invoice_checkout(token: str, sales_invoice: str):
	token_doc = _validate_token(token)
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
	amount = float(invoice.outstanding_amount or invoice.grand_total)
	if amount <= 0:
		frappe.throw(_("That invoice does not have an outstanding balance."))

	metadata = {
		"brand": "bp_water_heaters",
		"erp_site": frappe.local.site,
		"sales_invoice": invoice.name,
		"customer_email": token_doc.email,
		"service_type": "invoice_payment",
	}
	stripe.api_key = stripe_key
	stripe.api_version = "2026-04-22.dahlia"
	session = stripe.checkout.Session.create(
		mode="payment",
		customer_email=token_doc.email,
		customer_creation="always",
		client_reference_id=invoice.name,
		payment_method_types=["card", "us_bank_account"],
		success_url=portal_url("/bpwaterheaters-portal", {"token": token, "payment": "success"}),
		cancel_url=portal_url("/bpwaterheaters-portal", {"token": token, "payment": "cancelled"}),
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
		idempotency_key=f"bpwh-invoice-{invoice.name}",
	)
	return {"configured": True, "url": session.url, "session_id": session.id}


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
