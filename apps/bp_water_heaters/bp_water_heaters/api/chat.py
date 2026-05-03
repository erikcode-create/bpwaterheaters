from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from bp_water_heaters.api.portal import _validate_token


@frappe.whitelist(allow_guest=True)
def start_public_chat(full_name: str, email: str, phone: str, message: str, booking: str | None = None):
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
def get_portal_messages(token: str, conversation: str):
	token_doc = _validate_token(token)
	if not _conversation_belongs_to_email(conversation, token_doc.email):
		frappe.throw(_("That chat is not available for this portal link."))
	messages = frappe.get_all(
		"BPWH Chat Message",
		filters={"conversation": conversation},
		fields=["name", "sender_type", "sender_email", "message", "posted_at"],
		order_by="posted_at asc",
	)
	frappe.db.set_value("BPWH Chat Message", {"conversation": conversation}, "read_by_customer", 1)
	return {"conversation": conversation, "messages": messages}


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
