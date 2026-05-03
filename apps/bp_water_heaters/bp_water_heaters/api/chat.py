from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from bp_water_heaters.api.portal import _validate_token
from bp_water_heaters.security_limits import clamp_limit, client_ip, require_bpwh_rate_limit


@frappe.whitelist(allow_guest=True)
def start_public_chat(full_name: str, email: str, phone: str, message: str, booking: str | None = None):
	require_bpwh_rate_limit(frappe, "public-chat-ip", client_ip(frappe), limit=8, window_seconds=3600)
	require_bpwh_rate_limit(frappe, "public-chat-email", email, limit=4, window_seconds=3600)
	if not all([full_name, email, message]):
		frappe.throw(_("Please include your name, email, and message."))

	conversation = frappe.get_doc(
		{
			"doctype": "BPWH Chat Conversation",
			"subject": "Website chat",
			"status": "Open",
			"customer_name": full_name.strip(),
			"email": email.strip().lower(),
			"phone": (phone or "").strip(),
			"booking": booking if booking and frappe.db.exists("BPWH Booking", booking) else None,
			"last_message_at": now_datetime(),
		}
	)
	conversation.insert(ignore_permissions=True)
	_add_message(conversation.name, "Customer", email.strip().lower(), message, read_by_customer=1)
	return {"conversation": conversation.name, "status": conversation.status}


@frappe.whitelist(allow_guest=True)
def send_portal_message(token: str, conversation: str, message: str):
	token_doc = _validate_token(token)
	require_bpwh_rate_limit(
		frappe,
		"portal-chat-reply",
		f"{token_doc.name}:{conversation}",
		limit=30,
		window_seconds=600,
	)
	if not _conversation_belongs_to_email(conversation, token_doc.email):
		frappe.throw(_("That chat is not available for this portal link."))
	_add_message(conversation, "Customer", token_doc.email, message, read_by_customer=1)
	frappe.db.set_value(
		"BPWH Chat Conversation",
		conversation,
		{"status": "Open", "last_message_at": now_datetime()},
		update_modified=True,
	)
	return {"conversation": conversation, "status": "Open"}


@frappe.whitelist(allow_guest=True)
def start_portal_chat(token: str, message: str, subject: str | None = None):
	token_doc = _validate_token(token)
	require_bpwh_rate_limit(frappe, "portal-chat-start", token_doc.name, limit=10, window_seconds=3600)
	conversation = frappe.get_doc(
		{
			"doctype": "BPWH Chat Conversation",
			"subject": (subject or "Customer portal chat").strip()[:140],
			"status": "Open",
			"customer_name": token_doc.email,
			"email": token_doc.email,
			"customer": token_doc.customer,
			"portal_token": token_doc.name,
			"last_message_at": now_datetime(),
		}
	)
	conversation.insert(ignore_permissions=True)
	_add_message(conversation.name, "Customer", token_doc.email, message, read_by_customer=1)
	return {"conversation": conversation.name, "status": conversation.status}


@frappe.whitelist(allow_guest=True)
def get_portal_messages(token: str, conversation: str, before: str | None = None, limit: int = 50):
	token_doc = _validate_token(token)
	if not _conversation_belongs_to_email(conversation, token_doc.email):
		frappe.throw(_("That chat is not available for this portal link."))
	page_limit = clamp_limit(limit, 50, 100)
	filters = {"conversation": conversation}
	if before:
		filters["posted_at"] = ["<", get_datetime(before)]
	messages = frappe.get_all(
		"BPWH Chat Message",
		filters=filters,
		fields=["name", "sender_type", "sender_email", "message", "posted_at"],
		order_by="posted_at desc",
		limit_page_length=page_limit + 1,
	)
	has_more = len(messages) > page_limit
	messages = list(reversed(messages[:page_limit]))
	frappe.db.set_value("BPWH Chat Message", {"conversation": conversation}, "read_by_customer", 1)
	return {
		"conversation": conversation,
		"messages": messages,
		"pagination": {
			"has_more": has_more,
			"next_before": str(messages[0].get("posted_at")) if has_more and messages else None,
			"limit": page_limit,
		},
	}


def admin_reply(conversation: str, message: str, sender_email: str):
	if not frappe.db.exists("BPWH Chat Conversation", conversation):
		frappe.throw(_("Chat conversation not found."))
	_add_message(conversation, "Admin", sender_email, message, read_by_admin=1)
	frappe.db.set_value(
		"BPWH Chat Conversation",
		conversation,
		{"status": "Waiting on Customer", "last_message_at": now_datetime()},
		update_modified=True,
	)
	return {"conversation": conversation, "status": "Waiting on Customer"}


def _add_message(
	conversation: str,
	sender_type: str,
	sender_email: str | None,
	message: str,
	read_by_admin: int = 0,
	read_by_customer: int = 0,
):
	if not message or not message.strip():
		frappe.throw(_("Please enter a message."))
	doc = frappe.get_doc(
		{
			"doctype": "BPWH Chat Message",
			"conversation": conversation,
			"sender_type": sender_type,
			"sender_email": sender_email,
			"message": message.strip(),
			"posted_at": now_datetime(),
			"read_by_admin": read_by_admin,
			"read_by_customer": read_by_customer,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _conversation_belongs_to_email(conversation, email):
	return bool(frappe.db.exists("BPWH Chat Conversation", {"name": conversation, "email": email}))
