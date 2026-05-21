from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from types import ModuleType, SimpleNamespace


def _install_fake_frappe():
	if "frappe" in sys.modules:
		return
	frappe = ModuleType("frappe")
	utils = ModuleType("frappe.utils")

	frappe._ = lambda message, *args, **kwargs: message
	frappe.conf = {}
	frappe.flags = SimpleNamespace()
	frappe.local = SimpleNamespace(request=SimpleNamespace(host="bpwaterheaters.com"), response={})
	frappe.request = SimpleNamespace(method="POST")
	frappe.session = SimpleNamespace(user="test@example.com")
	frappe.PermissionError = PermissionError
	frappe.get_doc = lambda *args, **kwargs: None
	frappe.throw = lambda message, exc=None: (_ for _ in ()).throw((exc or Exception)(message))
	frappe.whitelist = lambda *args, **kwargs: (args[0] if args and callable(args[0]) else lambda fn: fn)

	utils.get_datetime = lambda value=None: value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
	utils.get_url = lambda: "http://test.local"
	utils.getdate = lambda value=None: date.today() if not value else date.fromisoformat(str(value))
	utils.now_datetime = datetime.now
	utils.nowdate = lambda: date.today().isoformat()
	frappe.utils = utils

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


_install_fake_frappe()

from bp_water_heaters.mobile_auth import hash_mobile_token, issue_mobile_token, is_allowed_admin
from bp_water_heaters.api import booking
from bp_water_heaters.payments import classify_stripe_event
from bp_water_heaters.plaid_sync import plaid_transaction_to_bank_transaction
from bp_water_heaters.portal_security import hash_token, issue_token
from bp_water_heaters.taxes import select_tax_rule
from bp_water_heaters.urls import build_site_url, public_url


def test_classifies_card_checkout_as_paid():
	state = classify_stripe_event(
		"checkout.session.completed",
		{
			"payment_status": "paid",
			"payment_intent": "pi_card",
			"metadata": {"booking_id": "BPWH-BKG-2026-00001"},
			"payment_method_types": ["card"],
		},
	)

	assert state.booking_id == "BPWH-BKG-2026-00001"
	assert state.booking_status == "Confirmed"
	assert state.payment_status == "Paid"
	assert state.settlement_status == "Settled"
	assert state.payment_method_type == "card"


def test_classifies_ach_checkout_as_pending_settlement_until_async_success():
	state = classify_stripe_event(
		"checkout.session.completed",
		{
			"payment_status": "unpaid",
			"payment_intent": "pi_ach",
			"metadata": {"booking_id": "BPWH-BKG-2026-00002"},
			"payment_method_types": ["card", "us_bank_account"],
		},
	)

	assert state.booking_status == "Payment Pending Settlement"
	assert state.payment_status == "Pending Settlement"
	assert state.settlement_status == "Pending"
	assert state.payment_method_type == "us_bank_account"

	success = classify_stripe_event(
		"checkout.session.async_payment_succeeded",
		{
			"payment_status": "paid",
			"payment_intent": "pi_ach",
			"metadata": {"booking_id": "BPWH-BKG-2026-00002"},
			"payment_method_types": ["card", "us_bank_account"],
		},
	)

	assert success.booking_status == "Confirmed"
	assert success.payment_status == "Paid"
	assert success.settlement_status == "Settled"


def test_magic_link_tokens_are_one_way_hashed():
	issued = issue_token("customer@example.com", now=datetime(2026, 5, 3, tzinfo=timezone.utc))

	assert issued.email == "customer@example.com"
	assert len(issued.token) >= 32
	assert issued.token_hash == hash_token(issued.token)
	assert issued.token not in issued.token_hash
	assert issued.expires_at.isoformat() == "2026-05-10T00:00:00+00:00"


def test_selects_official_source_tax_rules_for_nv_and_ca():
	washoe = select_tax_rule(state="NV", city="Reno", county=None)
	california = select_tax_rule(state="CA", city="Sacramento", county=None)

	assert washoe.template_name == "NV Washoe Sales Tax - BPWH"
	assert washoe.rate == 8.265
	assert "tax.nv.gov" in washoe.source_url
	assert california.template_name == "CA Statewide Sales Tax - BPWH"
	assert california.rate == 7.25
	assert "cdtfa.ca.gov" in california.source_url


def test_builds_production_public_urls_from_site_config():
	url = public_url(
		"/bpwaterheaters",
		query={"booking": "BPWH-BKG-2026-00001", "payment": "success"},
		config={"bpwh_public_base_url": "https://bpwaterheaters.com/"},
	)

	assert url == "https://bpwaterheaters.com/bpwaterheaters?booking=BPWH-BKG-2026-00001&payment=success"
	assert build_site_url("https://portal.bpwaterheaters.com/", "bpwaterheaters-portal") == "https://portal.bpwaterheaters.com/bpwaterheaters-portal"


def test_stripe_expiry_uses_epoch_seconds(monkeypatch):
	monkeypatch.setattr(booking.time_module, "time", lambda: 1_777_780_000.4)

	assert booking._stripe_expires_at() == 1_777_780_000 + (booking.HOLD_MINUTES * 60)


def test_stripe_idempotency_key_includes_booking_creation_time():
	booking_doc = {"name": "BPWH-BKG-2026-00003", "creation": datetime(2026, 5, 2, 21, 45, 12, 123456)}

	assert (
		booking._stripe_idempotency_key("customer", booking_doc)
		== "bpwh-customer-BPWH-BKG-2026-00003-20260502214512123456"
	)


def test_booking_request_does_not_open_checkout_or_payment_hold(monkeypatch):
	created = {}

	class FakeBooking(SimpleNamespace):
		name = "BPWH-BKG-2026-00004"

		def insert(self, ignore_permissions=False):
			created["doc"] = self

		def get(self, key, default=None):
			return getattr(self, key, default)

	def fake_get_doc(payload):
		return FakeBooking(**payload)

	def fail_checkout(_booking_doc):
		raise AssertionError("Booking requests should not start Stripe checkout")

	monkeypatch.setattr(booking, "require_bpwh_rate_limit", lambda *args, **kwargs: None)
	monkeypatch.setattr(booking, "client_ip", lambda _frappe: "127.0.0.1")
	monkeypatch.setattr(booking.frappe, "get_doc", fake_get_doc)
	monkeypatch.setattr(booking, "_apply_tax_rule_to_booking", lambda _booking_doc: None)
	monkeypatch.setattr(booking, "_create_checkout_session_if_configured", fail_checkout)
	monkeypatch.setattr(booking, "now_datetime", lambda: datetime(2026, 5, 20, 9, 0))

	result = booking.create_booking_request(
		customer_name="Ada Plumber",
		email="ADA@example.com",
		phone="775-555-0199",
		property_address="42 Tank Way",
		city="Reno",
		state="NV",
		postal_code="89501",
		preferred_start="2026-05-21 14:15",
		service_type="Estimate",
	)

	doc = created["doc"]
	assert result["booking"] == "BPWH-BKG-2026-00004"
	assert result["status"] == "Requested"
	assert result["checkout"] is None
	assert doc.status == "Requested"
	assert doc.hold_expires_at is None
	assert doc.stripe_payment_status == "Not Started"
	assert doc.payment_settlement_status == "Not Started"
	assert doc.email == "ada@example.com"


def test_plaid_transactions_map_to_bank_transaction_fields():
	outgoing = plaid_transaction_to_bank_transaction(
		{
			"transaction_id": "plaid-tx-out",
			"date": "2026-05-01",
			"amount": 85.25,
			"name": "Stripe payout fee",
			"merchant_name": "Stripe",
			"payment_channel": "online",
			"iso_currency_code": "USD",
		},
		bank_account="Operating Bank - BPWH",
		company="BP Water Heaters",
	)
	incoming = plaid_transaction_to_bank_transaction(
		{
			"transaction_id": "plaid-tx-in",
			"date": "2026-05-02",
			"amount": -340.00,
			"name": "Stripe payout",
			"merchant_name": "Stripe",
			"payment_channel": "other",
			"iso_currency_code": "USD",
		},
		bank_account="Operating Bank - BPWH",
		company="BP Water Heaters",
	)

	assert outgoing["transaction_id"] == "plaid-tx-out"
	assert outgoing["withdrawal"] == 85.25
	assert outgoing["deposit"] == 0
	assert outgoing["reference_number"] == "plaid-tx-out"
	assert outgoing["transaction_type"] == "online"
	assert incoming["deposit"] == 340.00
	assert incoming["withdrawal"] == 0


def test_mobile_tokens_are_allowlisted_hashed_and_expiring():
	issued = issue_mobile_token("CHASE@BLUEBERGCONSTRUCTION.COM", now=datetime(2026, 5, 3, tzinfo=timezone.utc))

	assert is_allowed_admin("curtis@bpwaterheaters.com")
	assert not is_allowed_admin("someone@example.com")
	assert issued.user == "chase@bluebergconstruction.com"
	assert issued.token_hash == hash_mobile_token(issued.token)
	assert issued.token not in issued.token_hash
	assert issued.expires_at.isoformat() == "2026-05-03T12:00:00+00:00"
