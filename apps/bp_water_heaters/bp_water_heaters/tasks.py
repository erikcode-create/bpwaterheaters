from __future__ import annotations

import frappe
from frappe.utils import now_datetime


def expire_stale_booking_holds():
	stale = frappe.get_all(
		"BPWH Booking",
		filters={
			"status": "Pending Payment",
			"hold_expires_at": ["<=", now_datetime()],
		},
		fields=["name"],
	)
	for row in stale:
		frappe.db.set_value(
			"BPWH Booking",
			row.name,
			{"status": "Expired", "stripe_payment_status": "Expired", "payment_settlement_status": "Expired"},
			update_modified=True,
		)
