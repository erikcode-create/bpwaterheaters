from __future__ import annotations

from bp_water_heaters.portal_view import build_portal_view


def test_portal_view_groups_booking_related_job_invoice_and_chat():
	view = build_portal_view(
		email="customer@example.com",
		customer="CUST-BPWH-0001",
		bookings=[
			{
				"name": "BPWH-BKG-2026-0002",
				"service_type": "Replacement Estimate",
				"status": "Confirmed",
				"preferred_start": "2026-05-08 09:00:00",
				"property_address": "123 Long Water Heater Way",
				"city": "Reno",
				"state": "NV",
				"postal_code": "89501",
				"sales_invoice": "SINV-0002",
				"project": "PROJ-0002",
			}
		],
		invoices=[
			{
				"name": "SINV-0002",
				"status": "Overdue",
				"grand_total": 985.5,
				"outstanding_amount": 485.5,
				"posting_date": "2026-05-07",
			}
		],
		projects=[
			{
				"name": "PROJ-0002",
				"project_name": "Reno Water Heater Replacement",
				"status": "Open",
				"percent_complete": 25,
			}
		],
		conversations=[
			{
				"name": "CHAT-0002",
				"subject": "Install access notes",
				"status": "Open",
				"last_message_at": "2026-05-07 17:15:00",
				"booking": "BPWH-BKG-2026-0002",
			}
		],
	)

	assert view["bookings"][0]["name"] == "BPWH-BKG-2026-0002"
	assert view["invoices"][0]["is_payable"] is True
	assert view["summary"]["next_action"]["kind"] == "payment_due"
	assert view["summary"]["next_action"]["amount"] == 485.5
	assert view["summary"]["active_service_record"] == "BPWH-BKG-2026-0002"
	assert view["service_records"] == [
		{
			"id": "BPWH-BKG-2026-0002",
			"title": "Replacement Estimate",
			"booking": view["bookings"][0],
			"project": view["projects"][0],
			"invoices": view["invoices"],
			"conversations": view["conversations"],
			"primary_invoice": view["invoices"][0],
			"primary_conversation": view["conversations"][0],
			"next_action": view["summary"]["next_action"],
		}
	]


def test_portal_view_marks_paid_invoices_as_history_not_payment_actions():
	view = build_portal_view(
		email="customer@example.com",
		customer="CUST-BPWH-0001",
		bookings=[
			{
				"name": "BPWH-BKG-2026-0003",
				"service_type": "Repair Diagnostic",
				"status": "Confirmed",
				"preferred_start": "2026-05-09 10:00:00",
			}
		],
		invoices=[
			{
				"name": "SINV-0003",
				"status": "Paid",
				"grand_total": 85,
				"outstanding_amount": 0,
			}
		],
		projects=[],
		conversations=[],
	)

	assert view["invoices"][0]["is_payable"] is False
	assert view["summary"]["next_action"]["kind"] == "appointment"
	assert view["service_records"][0]["primary_invoice"]["is_payable"] is False
