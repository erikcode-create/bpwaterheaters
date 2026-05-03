from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import getdate, nowdate

from bp_water_heaters.install import (
	CALLOUT_ITEM_CODE,
	COMPANY,
	STRIPE_ACH_ACCOUNT,
	STRIPE_ACH_MODE,
	STRIPE_CARD_ACCOUNT,
	STRIPE_CARD_MODE,
)
from bp_water_heaters.taxes import select_tax_rule


def prepare_booking_erp_records(booking):
	customer = ensure_customer(booking)
	ensure_contact(booking, customer)
	ensure_address(booking, customer)
	apply_booking_tax_rule(booking)
	invoice = ensure_sales_invoice(booking, customer)
	project = ensure_project(booking, customer)

	booking.db_set(
		{
			"erp_customer": customer,
			"sales_invoice": invoice,
			"project": project,
		},
		update_modified=True,
	)
	return {"customer": customer, "sales_invoice": invoice, "project": project}


def record_payment_for_booking(booking, payment_method_type: str | None):
	if booking.payment_entry and frappe.db.exists("Payment Entry", booking.payment_entry):
		return booking.payment_entry

	records = prepare_booking_erp_records(booking)
	invoice = records["sales_invoice"]
	account, mode = _payment_account_and_mode(payment_method_type)

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	payment_entry = get_payment_entry("Sales Invoice", invoice)
	payment_entry.mode_of_payment = mode
	payment_entry.paid_to = account
	payment_entry.reference_no = booking.stripe_payment_intent or booking.stripe_checkout_session_id or booking.name
	payment_entry.reference_date = nowdate()
	payment_entry.save(ignore_permissions=True)
	payment_entry.submit()

	booking.db_set("payment_entry", payment_entry.name, update_modified=True)
	return payment_entry.name


def record_payment_for_invoice(sales_invoice: str, payment_method_type: str | None, reference_no: str | None):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	if not frappe.db.exists("Sales Invoice", sales_invoice):
		frappe.throw(f"Sales Invoice {sales_invoice} does not exist.")

	existing = frappe.db.get_value(
		"Payment Entry Reference",
		{"reference_doctype": "Sales Invoice", "reference_name": sales_invoice, "docstatus": 1},
		"parent",
	)
	if existing:
		return existing

	account, mode = _payment_account_and_mode(payment_method_type)
	payment_entry = get_payment_entry("Sales Invoice", sales_invoice)
	payment_entry.mode_of_payment = mode
	payment_entry.paid_to = account
	payment_entry.reference_no = reference_no or sales_invoice
	payment_entry.reference_date = nowdate()
	payment_entry.save(ignore_permissions=True)
	payment_entry.submit()
	return payment_entry.name


def ensure_customer(booking):
	if booking.erp_customer and frappe.db.exists("Customer", booking.erp_customer):
		return booking.erp_customer

	existing = frappe.db.get_value("Contact Email", {"email_id": booking.email}, "parent")
	if existing:
		customer = _customer_for_contact(existing)
		if customer:
			return customer

	customer_group = frappe.db.exists("Customer Group", "Individual") or frappe.db.exists(
		"Customer Group", "All Customer Groups"
	)
	territory = frappe.db.exists("Territory", "All Territories") or frappe.db.get_value("Territory", {}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": booking.customer_name,
			"customer_type": "Individual",
			"customer_group": customer_group,
			"territory": territory,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_contact(booking, customer):
	contact_name = frappe.db.get_value("Contact Email", {"email_id": booking.email}, "parent")
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
	else:
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": booking.customer_name,
				"email_ids": [{"email_id": booking.email, "is_primary": 1}],
				"phone_nos": [{"phone": booking.phone, "is_primary_phone": 1}],
			}
		)

	if not any(link.link_doctype == "Customer" and link.link_name == customer for link in contact.get("links", [])):
		contact.append("links", {"link_doctype": "Customer", "link_name": customer})
	contact.save(ignore_permissions=True)
	return contact.name


def ensure_address(booking, customer):
	existing = frappe.db.get_value(
		"Dynamic Link",
		{"parenttype": "Address", "link_doctype": "Customer", "link_name": customer},
		"parent",
	)
	if existing:
		return existing

	address = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": booking.customer_name,
			"address_type": "Billing",
			"address_line1": booking.property_address,
			"city": booking.city,
			"state": booking.state,
			"pincode": booking.postal_code,
			"country": "United States",
			"links": [{"link_doctype": "Customer", "link_name": customer}],
		}
	)
	address.insert(ignore_permissions=True)
	return address.name


def apply_booking_tax_rule(booking):
	rule = select_tax_rule(booking.state, booking.city, booking.get("county"))
	booking.db_set(
		{
			"tax_template": rule.template_name if frappe.db.exists("Sales Taxes and Charges Template", rule.template_name) else None,
			"tax_rate": rule.rate,
			"tax_source_url": rule.source_url,
		},
		update_modified=False,
	)
	return rule


def ensure_sales_invoice(booking, customer):
	if booking.sales_invoice and frappe.db.exists("Sales Invoice", booking.sales_invoice):
		return booking.sales_invoice

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": COMPANY,
			"customer": customer,
			"due_date": nowdate(),
			"set_posting_time": 1,
			"posting_date": getdate(booking.preferred_start),
			"taxes_and_charges": booking.tax_template,
			"items": [
				{
					"item_code": CALLOUT_ITEM_CODE,
					"qty": 1,
					"rate": Decimal(booking.callout_fee or 85),
				}
			],
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	return invoice.name


def ensure_project(booking, customer):
	if booking.project and frappe.db.exists("Project", booking.project):
		return booking.project

	project_name = f"{booking.name} - {booking.customer_name}"
	existing = frappe.db.exists("Project", {"project_name": project_name})
	if existing:
		return existing

	project_type = _ensure_project_type()
	project = frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": project_name,
			"status": "Open",
			"is_active": "Yes",
			"company": COMPANY,
			"customer": customer,
			"project_type": project_type,
			"expected_start_date": getdate(booking.preferred_start),
			"notes": f"{booking.property_address}, {booking.city}, {booking.state} {booking.postal_code}\n\n{booking.notes or ''}",
		}
	)
	project.insert(ignore_permissions=True)
	return project.name


def _ensure_project_type():
	if not frappe.db.exists("Project Type", "Water Heater Service"):
		frappe.get_doc({"doctype": "Project Type", "project_type": "Water Heater Service"}).insert(ignore_permissions=True)
	return "Water Heater Service"


def _payment_account_and_mode(payment_method_type):
	if payment_method_type == "us_bank_account":
		return STRIPE_ACH_ACCOUNT, STRIPE_ACH_MODE
	return STRIPE_CARD_ACCOUNT, STRIPE_CARD_MODE


def _customer_for_contact(contact_name):
	for link in frappe.get_doc("Contact", contact_name).get("links", []):
		if link.link_doctype == "Customer":
			return link.link_name
	return None
