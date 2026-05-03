from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from bp_water_heaters.api.chat import admin_reply
from bp_water_heaters.access import is_allowed_admin


def require_bpwh_admin():
	mobile_user = _mobile_user_from_request()
	if mobile_user:
		return mobile_user
	user = frappe.session.user
	if user == "Administrator":
		return user
	if not is_allowed_admin(user):
		frappe.throw(_("You are not allowed to administer BP Water Heaters."), frappe.PermissionError)
	return user


@frappe.whitelist(allow_guest=True)
def dashboard():
	require_bpwh_admin()
	return {
		"open_bookings": frappe.db.count("BPWH Booking", {"status": ["in", ["Pending Payment", "Payment Pending Settlement", "Confirmed"]]}),
		"new_contacts": frappe.db.count("BPWH Contact Request", {"status": "New"}),
		"open_chats": frappe.db.count("BPWH Chat Conversation", {"status": ["!=", "Closed"]}),
		"open_projects": frappe.db.count("Project", {"status": "Open"}),
	}


@frappe.whitelist(allow_guest=True)
def list_bookings(limit: int = 50):
	require_bpwh_admin()
	return frappe.get_all(
		"BPWH Booking",
		fields=[
			"name",
			"customer_name",
			"email",
			"phone",
			"preferred_start",
			"status",
			"stripe_payment_status",
			"payment_settlement_status",
			"sales_invoice",
			"project",
		],
		order_by="preferred_start desc",
		limit_page_length=min(int(limit or 50), 200),
	)


@frappe.whitelist(allow_guest=True)
def list_chats(limit: int = 50):
	require_bpwh_admin()
	return frappe.get_all(
		"BPWH Chat Conversation",
		fields=["name", "subject", "status", "customer_name", "email", "phone", "booking", "last_message_at"],
		order_by="last_message_at desc",
		limit_page_length=min(int(limit or 50), 200),
	)


@frappe.whitelist(allow_guest=True)
def get_chat_messages(conversation: str):
	require_bpwh_admin()
	if not frappe.db.exists("BPWH Chat Conversation", conversation):
		frappe.throw(_("Chat conversation not found."))

	frappe.db.sql(
		"""
		update `tabBPWH Chat Message`
		set read_by_admin = 1
		where conversation = %s
		""",
		(conversation,),
	)
	return {
		"conversation": frappe.db.get_value(
			"BPWH Chat Conversation",
			conversation,
			["name", "subject", "status", "customer_name", "email", "phone", "booking", "last_message_at"],
			as_dict=True,
		),
		"messages": frappe.get_all(
			"BPWH Chat Message",
			filters={"conversation": conversation},
			fields=["name", "sender_type", "sender_email", "message", "posted_at"],
			order_by="posted_at asc",
			limit_page_length=200,
		),
	}


@frappe.whitelist(allow_guest=True)
def update_chat_status(conversation: str, status: str):
	require_bpwh_admin()
	allowed = {"Open", "Waiting on Customer", "Closed"}
	if status not in allowed:
		frappe.throw(_("Unsupported chat status."))
	frappe.db.set_value("BPWH Chat Conversation", conversation, "status", status, update_modified=True)
	return {"conversation": conversation, "status": status}


@frappe.whitelist(allow_guest=True)
def list_projects(limit: int = 50):
	require_bpwh_admin()
	return frappe.get_all(
		"Project",
		filters={"project_type": "Water Heater Service"},
		fields=["name", "project_name", "status", "customer", "percent_complete", "expected_start_date", "expected_end_date"],
		order_by="modified desc",
		limit_page_length=min(int(limit or 50), 200),
	)


@frappe.whitelist(allow_guest=True)
def update_project(project: str, status: str | None = None, percent_complete: float | None = None):
	require_bpwh_admin()
	if not frappe.db.exists("Project", project):
		frappe.throw(_("Project not found."))

	updates = {}
	if status:
		allowed_statuses = {"Open", "Completed", "Cancelled"}
		if status not in allowed_statuses:
			frappe.throw(_("Unsupported project status."))
		updates["status"] = status
	if percent_complete is not None and str(percent_complete) != "":
		percent = max(0, min(float(percent_complete), 100))
		updates["percent_complete"] = percent

	if not updates:
		return {"project": project}

	frappe.db.set_value("Project", project, updates, update_modified=True)
	return {"project": project, **updates}


@frappe.whitelist(allow_guest=True)
def list_invoices(limit: int = 50):
	require_bpwh_admin()
	return frappe.get_all(
		"Sales Invoice",
		filters={"company": "BP Water Heaters"},
		fields=["name", "customer", "posting_date", "grand_total", "outstanding_amount", "status"],
		order_by="posting_date desc",
		limit_page_length=min(int(limit or 50), 200),
	)


@frappe.whitelist(allow_guest=True)
def list_contact_requests(limit: int = 50):
	require_bpwh_admin()
	return frappe.get_all(
		"BPWH Contact Request",
		fields=["name", "full_name", "email", "phone", "source", "status", "creation"],
		order_by="creation desc",
		limit_page_length=min(int(limit or 50), 200),
	)


@frappe.whitelist(allow_guest=True)
def customer_history(email: str):
	require_bpwh_admin()
	normalized_email = (email or "").strip().lower()
	if not normalized_email:
		frappe.throw(_("Email is required."))
	return {
		"bookings": frappe.get_all(
			"BPWH Booking",
			filters={"email": normalized_email},
			fields=["name", "preferred_start", "status", "sales_invoice", "project", "payment_entry"],
			order_by="preferred_start desc",
			limit_page_length=100,
		),
		"contact_requests": frappe.get_all(
			"BPWH Contact Request",
			filters={"email": normalized_email},
			fields=["name", "status", "source", "creation"],
			order_by="creation desc",
			limit_page_length=100,
		),
		"chats": frappe.get_all(
			"BPWH Chat Conversation",
			filters={"email": normalized_email},
			fields=["name", "subject", "status", "last_message_at"],
			order_by="last_message_at desc",
			limit_page_length=100,
		),
	}


@frappe.whitelist(allow_guest=True)
def reply_chat(conversation: str, message: str):
	user = require_bpwh_admin()
	return admin_reply(conversation, message, user)


@frappe.whitelist(allow_guest=True)
def ensure_job_for_booking(booking: str):
	require_bpwh_admin()
	if not frappe.db.exists("BPWH Booking", booking):
		frappe.throw(_("Booking not found."))
	from bp_water_heaters.erp import prepare_booking_erp_records

	doc = frappe.get_doc("BPWH Booking", booking)
	records = prepare_booking_erp_records(doc)
	return {"booking": booking, **records}


@frappe.whitelist(allow_guest=True)
def update_booking_status(booking: str, status: str):
	require_bpwh_admin()
	allowed = {"Pending Payment", "Payment Pending Settlement", "Confirmed", "Payment Failed", "Cancelled", "Completed", "Expired", "Refunded", "Disputed"}
	if status not in allowed:
		frappe.throw(_("Unsupported booking status."))
	frappe.db.set_value("BPWH Booking", booking, "status", status, update_modified=True)
	return {"booking": booking, "status": status}


@frappe.whitelist(allow_guest=True)
def register_device_token(device_token: str, platform: str = "iOS"):
	user = require_bpwh_admin()
	existing = frappe.db.exists("BPWH Device Token", {"user": user, "device_token": device_token})
	if existing:
		frappe.db.set_value("BPWH Device Token", existing, {"enabled": 1, "last_seen_at": now_datetime()}, update_modified=True)
		return {"name": existing}
	doc = frappe.get_doc(
		{
			"doctype": "BPWH Device Token",
			"user": user,
			"platform": platform,
			"device_token": device_token,
			"enabled": 1,
			"last_seen_at": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	return {"name": doc.name}


def _mobile_user_from_request():
	try:
		from bp_water_heaters.mobile_auth import user_from_bearer_token

		return user_from_bearer_token()
	except Exception:
		return None
