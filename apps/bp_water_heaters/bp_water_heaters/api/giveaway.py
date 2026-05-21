from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import get_datetime, now_datetime

from bp_water_heaters.giveaway import (
	GIVEAWAY_BONUS_KIND,
	GIVEAWAY_CAMPAIGN_NAME,
	GIVEAWAY_ELIGIBLE_STATUS,
	GIVEAWAY_PAID_ENTRY,
	GIVEAWAY_PRIZE_ARV,
	GIVEAWAY_STANDARD_KIND,
	GIVEAWAY_WINNER_STATUS,
	campaign_status,
	eligible_entries_to_csv,
	next_free_entry_award,
	normalize_household_key,
)
from bp_water_heaters.security_limits import client_ip, require_bpwh_rate_limit

_ = getattr(frappe, "_", lambda message: message)


@frappe.whitelist(allow_guest=True)
def get_campaign_context():
	status = _campaign_status_from_config()
	return {
		"campaign_name": GIVEAWAY_CAMPAIGN_NAME,
		"prize_arv": GIVEAWAY_PRIZE_ARV,
		"state": status["state"],
		"is_open": status["is_open"],
		"start_at": str(status["start_at"]) if status["start_at"] else None,
		"end_at": str(status["end_at"]) if status["end_at"] else None,
	}


@frappe.whitelist(allow_guest=True)
def submit_free_entry(
	full_name: str,
	email: str,
	phone: str,
	property_address: str,
	city: str,
	state: str,
	postal_code: str,
	homeowner_authorized=None,
	is_adult=None,
	marketing_opt_in=None,
):
	require_bpwh_rate_limit(frappe, "giveaway-entry-ip", client_ip(frappe), limit=10, window_seconds=3600)
	require_bpwh_rate_limit(frappe, "giveaway-entry-email", email, limit=3, window_seconds=3600)
	_require_campaign_open()
	_validate_public_entry(full_name, email, phone, property_address, city, state, postal_code, homeowner_authorized, is_adult)

	household_key = normalize_household_key(property_address, city, state, postal_code)
	try:
		award = next_free_entry_award(_existing_household_entry_kinds(household_key))
	except ValueError:
		frappe.throw(_("This household already has the maximum giveaway entries."))

	doc = _insert_entry(
		{
			"entry_source": award["entry_source"],
			"entry_kind": award["entry_kind"],
			"status": GIVEAWAY_ELIGIBLE_STATUS,
			"full_name": full_name.strip(),
			"email": email.strip().lower(),
			"phone": phone.strip(),
			"is_adult": 1,
			"homeowner_authorized": 1,
			"marketing_opt_in": 1 if _truthy(marketing_opt_in) else 0,
			"property_address": property_address.strip(),
			"city": city.strip(),
			"state": state.strip().upper(),
			"postal_code": postal_code.strip(),
			"household_key": household_key,
		}
	)
	return {"name": doc.name, "status": doc.status, "entry_source": doc.entry_source, "entry_kind": doc.entry_kind}


@frappe.whitelist()
def create_paid_flush_entry(
	full_name: str,
	email: str,
	phone: str,
	property_address: str,
	city: str,
	state: str,
	postal_code: str,
	linked_booking: str | None = None,
	linked_sales_invoice: str | None = None,
	flush_paid_completed=None,
	marketing_opt_in=None,
):
	from bp_water_heaters.api.admin import require_bpwh_admin, require_post

	require_bpwh_admin()
	require_post()
	_require_campaign_open()
	if not _truthy(flush_paid_completed):
		frappe.throw(_("The flush must be paid and completed before creating a giveaway entry."))
	_validate_required_contact(full_name, email, phone, property_address, city, state, postal_code)

	household_key = normalize_household_key(property_address, city, state, postal_code)
	duplicate_bonus = _existing_household_entry(household_key, GIVEAWAY_BONUS_KIND)
	if duplicate_bonus:
		frappe.throw(_("This household already has a bonus entry for the giveaway."))

	doc = _insert_entry(
		{
			"entry_source": GIVEAWAY_PAID_ENTRY,
			"entry_kind": GIVEAWAY_BONUS_KIND,
			"status": GIVEAWAY_ELIGIBLE_STATUS,
			"full_name": full_name.strip(),
			"email": email.strip().lower(),
			"phone": phone.strip(),
			"is_adult": 1,
			"homeowner_authorized": 1,
			"marketing_opt_in": 1 if _truthy(marketing_opt_in) else 0,
			"property_address": property_address.strip(),
			"city": city.strip(),
			"state": state.strip().upper(),
			"postal_code": postal_code.strip(),
			"household_key": household_key,
			"linked_booking": linked_booking if linked_booking and frappe.db.exists("BPWH Booking", linked_booking) else None,
			"linked_sales_invoice": linked_sales_invoice if linked_sales_invoice and frappe.db.exists("Sales Invoice", linked_sales_invoice) else None,
			"flush_paid_completed": 1,
		}
	)
	return {"name": doc.name, "status": doc.status, "entry_source": doc.entry_source, "entry_kind": doc.entry_kind}


@frappe.whitelist()
def admin_list_entries(limit: int = 100):
	from bp_water_heaters.api.admin import require_bpwh_admin

	require_bpwh_admin()
	return frappe.get_all(
		"BPWH Giveaway Entry",
		fields=[
			"name",
			"full_name",
			"email",
			"phone",
			"property_address",
			"city",
			"state",
			"postal_code",
			"entry_source",
			"entry_kind",
			"status",
			"marketing_opt_in",
			"linked_booking",
			"linked_sales_invoice",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=min(int(limit or 100), 500),
	)


@frappe.whitelist()
def admin_export_eligible_entries():
	from bp_water_heaters.api.admin import require_bpwh_admin

	require_bpwh_admin()
	rows = frappe.get_all(
		"BPWH Giveaway Entry",
		filters={"campaign_name": GIVEAWAY_CAMPAIGN_NAME, "status": GIVEAWAY_ELIGIBLE_STATUS},
		fields=[
			"name",
			"full_name",
			"email",
			"phone",
			"property_address",
			"city",
			"state",
			"postal_code",
			"entry_source",
			"entry_kind",
			"status",
		],
		order_by="creation asc",
		limit_page_length=5000,
	)
	return {
		"filename": "bpwh-giveaway-eligible-entries.csv",
		"csv": eligible_entries_to_csv(rows),
		"count": len(rows),
	}


@frappe.whitelist()
def admin_mark_winner(entry: str):
	from bp_water_heaters.api.admin import require_bpwh_admin, require_post

	user = require_bpwh_admin()
	require_post()
	if not frappe.db.exists("BPWH Giveaway Entry", entry):
		frappe.throw(_("Giveaway entry not found."))
	frappe.db.set_value(
		"BPWH Giveaway Entry",
		entry,
		{
			"status": GIVEAWAY_WINNER_STATUS,
			"winner_selected_at": now_datetime(),
			"winner_selected_by": user,
		},
		update_modified=True,
	)
	return {"entry": entry, "status": GIVEAWAY_WINNER_STATUS}


def _insert_entry(values):
	doc = frappe.get_doc({"doctype": "BPWH Giveaway Entry", "campaign_name": GIVEAWAY_CAMPAIGN_NAME, **values})
	doc.insert(ignore_permissions=True)
	return doc


def _validate_public_entry(full_name, email, phone, property_address, city, state, postal_code, homeowner_authorized, is_adult):
	_validate_required_contact(full_name, email, phone, property_address, city, state, postal_code)
	if not _truthy(is_adult):
		frappe.throw(_("Please confirm you are at least 18 years old."))
	if not _truthy(homeowner_authorized):
		frappe.throw(_("Please confirm you own the home or are authorized to approve the install."))


def _validate_required_contact(full_name, email, phone, property_address, city, state, postal_code):
	if not all([full_name, email, phone, property_address, city, state, postal_code]):
		frappe.throw(_("Please fill out every required field."))
	if state.strip().upper() not in {"NV", "CA"}:
		frappe.throw(_("The giveaway is currently limited to BP Water Heaters service areas in Nevada and California."))


def _existing_household_entry(household_key: str, entry_kind: str | None = None):
	filters = {
		"campaign_name": GIVEAWAY_CAMPAIGN_NAME,
		"household_key": household_key,
		"status": ["not in", ["Duplicate", "Cancelled"]],
	}
	if entry_kind:
		filters["entry_kind"] = entry_kind
	rows = frappe.get_all(
		"BPWH Giveaway Entry",
		filters=filters,
		fields=["name"],
		limit_page_length=1,
	)
	return rows[0].name if rows else None


def _existing_household_entry_kinds(household_key: str):
	rows = frappe.get_all(
		"BPWH Giveaway Entry",
		filters={
			"campaign_name": GIVEAWAY_CAMPAIGN_NAME,
			"household_key": household_key,
			"status": ["not in", ["Duplicate", "Cancelled"]],
		},
		fields=["entry_kind"],
		limit_page_length=2,
	)
	return [row.get("entry_kind") or GIVEAWAY_STANDARD_KIND for row in rows]


def _campaign_status_from_config(now: datetime | None = None):
	start_at = _config_datetime("bpwh_giveaway_start_at")
	end_at = _config_datetime("bpwh_giveaway_end_at")
	return campaign_status(now or now_datetime(), start_at, end_at)


def _require_campaign_open():
	status = _campaign_status_from_config()
	if not status["is_open"]:
		frappe.throw(_("The giveaway entry window is not open."))


def _config_datetime(key: str):
	conf = getattr(frappe, "conf", {}) or {}
	value = conf.get(key)
	if not value:
		return None
	return get_datetime(value)


def _truthy(value):
	return str(value).lower() in {"1", "true", "yes", "on"}
