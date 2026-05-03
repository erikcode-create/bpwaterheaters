from __future__ import annotations

from typing import Any


def build_portal_view(
	*,
	email: str,
	customer: str | None,
	bookings: list[dict[str, Any]],
	invoices: list[dict[str, Any]],
	projects: list[dict[str, Any]],
	conversations: list[dict[str, Any]],
) -> dict[str, Any]:
	booking_rows = [_copy_row(row) for row in bookings]
	invoice_rows = [_annotate_invoice(row) for row in invoices]
	project_rows = [_copy_row(row) for row in projects]
	conversation_rows = [_copy_row(row) for row in conversations]

	service_records = _build_service_records(
		bookings=booking_rows,
		invoices=invoice_rows,
		projects=project_rows,
		conversations=conversation_rows,
	)
	next_action = _select_next_action(booking_rows, invoice_rows, conversation_rows)
	active_service_record = _select_active_service_record(service_records, next_action)
	for record in service_records:
		record["next_action"] = next_action if record["id"] == active_service_record else _select_record_action(record)

	return {
		"email": email,
		"customer": customer,
		"bookings": booking_rows,
		"invoices": invoice_rows,
		"projects": project_rows,
		"conversations": conversation_rows,
		"summary": {
			"email": email,
			"customer": customer,
			"active_service_record": active_service_record,
			"next_action": next_action,
			"counts": {
				"bookings": len(booking_rows),
				"invoices": len(invoice_rows),
				"projects": len(project_rows),
				"conversations": len(conversation_rows),
				"payable_invoices": sum(1 for invoice in invoice_rows if invoice["is_payable"]),
			},
		},
		"service_records": service_records,
	}


def _build_service_records(
	*,
	bookings: list[dict[str, Any]],
	invoices: list[dict[str, Any]],
	projects: list[dict[str, Any]],
	conversations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	projects_by_name = {project.get("name"): project for project in projects if project.get("name")}
	invoices_by_name = {invoice.get("name"): invoice for invoice in invoices if invoice.get("name")}
	conversations_by_booking: dict[str, list[dict[str, Any]]] = {}
	for conversation in conversations:
		booking_name = conversation.get("booking")
		if booking_name:
			conversations_by_booking.setdefault(booking_name, []).append(conversation)

	records = []
	used_invoice_names = set()
	used_conversation_names = set()
	for booking in bookings:
		booking_name = booking.get("name")
		project = projects_by_name.get(booking.get("project"))
		record_invoices = []
		if booking.get("sales_invoice") in invoices_by_name:
			record_invoices.append(invoices_by_name[booking["sales_invoice"]])
			used_invoice_names.add(booking["sales_invoice"])
		elif len(bookings) == 1 and len(invoices) == 1:
			record_invoices.append(invoices[0])
			used_invoice_names.add(invoices[0].get("name"))
		record_conversations = conversations_by_booking.get(booking_name, [])
		used_conversation_names.update(
			conversation.get("name") for conversation in record_conversations if conversation.get("name")
		)
		records.append(
			{
				"id": booking_name,
				"title": booking.get("service_type") or booking.get("name") or "Service",
				"booking": booking,
				"project": project,
				"invoices": record_invoices,
				"conversations": record_conversations,
				"primary_invoice": _first(record_invoices),
				"primary_conversation": _first(record_conversations),
			}
		)

	for invoice in invoices:
		if invoice.get("name") not in used_invoice_names:
			records.append(
				{
					"id": invoice.get("name"),
					"title": f"Invoice {invoice.get('name')}",
					"booking": None,
					"project": None,
					"invoices": [invoice],
					"conversations": [],
					"primary_invoice": invoice,
					"primary_conversation": None,
				}
			)

	for conversation in conversations:
		if conversation.get("name") not in used_conversation_names:
			records.append(
				{
					"id": conversation.get("name"),
					"title": conversation.get("subject") or "Message Thread",
					"booking": None,
					"project": None,
					"invoices": [],
					"conversations": [conversation],
					"primary_invoice": None,
					"primary_conversation": conversation,
				}
			)
	return records


def _select_next_action(
	bookings: list[dict[str, Any]],
	invoices: list[dict[str, Any]],
	conversations: list[dict[str, Any]],
) -> dict[str, Any]:
	payable_invoice = _first(invoice for invoice in invoices if invoice["is_payable"])
	if payable_invoice:
		return {
			"kind": "payment_due",
			"label": "Payment Due",
			"invoice": payable_invoice.get("name"),
			"amount": payable_invoice.get("outstanding_amount"),
		}

	upcoming_booking = _first(booking for booking in bookings if booking.get("preferred_start"))
	if upcoming_booking:
		return {
			"kind": "appointment",
			"label": "Appointment Scheduled",
			"booking": upcoming_booking.get("name"),
			"starts_at": upcoming_booking.get("preferred_start"),
		}

	open_conversation = _first(
		conversation for conversation in conversations if conversation.get("status") != "Closed"
	)
	if open_conversation:
		return {
			"kind": "message",
			"label": "Open Message",
			"conversation": open_conversation.get("name"),
			"last_message_at": open_conversation.get("last_message_at"),
		}

	return {"kind": "all_set", "label": "All Set"}


def _select_record_action(record: dict[str, Any]) -> dict[str, Any]:
	payable_invoice = _first(invoice for invoice in record["invoices"] if invoice["is_payable"])
	if payable_invoice:
		return {
			"kind": "payment_due",
			"label": "Payment Due",
			"invoice": payable_invoice.get("name"),
			"amount": payable_invoice.get("outstanding_amount"),
		}
	if record.get("booking") and record["booking"].get("preferred_start"):
		return {
			"kind": "appointment",
			"label": "Appointment Scheduled",
			"booking": record["booking"].get("name"),
			"starts_at": record["booking"].get("preferred_start"),
		}
	if record.get("primary_conversation"):
		return {
			"kind": "message",
			"label": "Open Message",
			"conversation": record["primary_conversation"].get("name"),
			"last_message_at": record["primary_conversation"].get("last_message_at"),
		}
	return {"kind": "all_set", "label": "All Set"}


def _select_active_service_record(service_records: list[dict[str, Any]], next_action: dict[str, Any]) -> str | None:
	for record in service_records:
		if next_action.get("booking") and (record.get("booking") or {}).get("name") == next_action["booking"]:
			return record["id"]
		if next_action.get("invoice") and any(invoice.get("name") == next_action["invoice"] for invoice in record["invoices"]):
			return record["id"]
		if next_action.get("conversation") and any(
			conversation.get("name") == next_action["conversation"] for conversation in record["conversations"]
		):
			return record["id"]
	return service_records[0]["id"] if service_records else None


def _annotate_invoice(row: dict[str, Any]) -> dict[str, Any]:
	invoice = _copy_row(row)
	outstanding_amount = float(invoice.get("outstanding_amount") or 0)
	invoice["is_payable"] = outstanding_amount > 0
	return invoice


def _copy_row(row: dict[str, Any]) -> dict[str, Any]:
	return dict(row or {})


def _first(values):
	for value in values:
		if value:
			return value
	return None
