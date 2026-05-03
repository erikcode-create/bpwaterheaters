from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from bp_water_heaters.payments import sanitize_stripe_event_for_audit
from bp_water_heaters.plaid_webhook_security import (
	decide_transactions_webhook,
	validate_plaid_webhook_claims,
)
from bp_water_heaters.portal_security import (
	hash_return_token,
	issue_checkout_return_token,
)
from bp_water_heaters.security_limits import InMemoryRateLimitStore, check_rate_limit, clamp_limit


def test_plaid_webhook_claim_validation_rejects_replays_and_body_mismatches():
	raw_body = b'{"webhook_type":"TRANSACTIONS","webhook_code":"SYNC_UPDATES_AVAILABLE"}'
	body_hash = hashlib.sha256(raw_body).hexdigest()
	now = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)

	assert validate_plaid_webhook_claims({"iat": int(now.timestamp()), "request_body_sha256": body_hash}, raw_body, now=now)
	assert not validate_plaid_webhook_claims(
		{"iat": int((now - timedelta(minutes=6)).timestamp()), "request_body_sha256": body_hash},
		raw_body,
		now=now,
	)
	assert not validate_plaid_webhook_claims(
		{"iat": int(now.timestamp()), "request_body_sha256": hashlib.sha256(b"{}").hexdigest()},
		raw_body,
		now=now,
	)


def test_plaid_transactions_webhook_decision_only_syncs_allowed_matching_items():
	payload = {
		"webhook_type": "TRANSACTIONS",
		"webhook_code": "SYNC_UPDATES_AVAILABLE",
		"item_id": "item-prod",
		"environment": "production",
	}

	assert decide_transactions_webhook(payload, known_item_ids={"item-prod"}, expected_environment="production").should_sync
	assert not decide_transactions_webhook({**payload, "webhook_code": "DEFAULT_UPDATE"}, {"item-prod"}, "production").should_sync
	assert not decide_transactions_webhook({**payload, "item_id": "unknown"}, {"item-prod"}, "production").should_sync
	assert not decide_transactions_webhook({**payload, "environment": "sandbox"}, {"item-prod"}, "production").should_sync


def test_checkout_return_tokens_are_short_lived_and_one_way_hashed():
	issued = issue_checkout_return_token(
		portal_token="BPWH-PORTAL-2026-00001",
		email="Customer@Example.com",
		sales_invoice="SINV-0001",
		now=datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc),
	)

	assert issued.email == "customer@example.com"
	assert issued.token_hash == hash_return_token(issued.token)
	assert issued.token not in issued.token_hash
	assert issued.expires_at.isoformat() == "2026-05-03T12:30:00+00:00"


def test_stripe_event_audit_payload_keeps_reconciliation_fields_without_pii():
	event = {
		"id": "evt_123",
		"type": "checkout.session.completed",
		"data": {
			"object": {
				"id": "cs_123",
				"object": "checkout.session",
				"client_reference_id": "SINV-0001",
				"payment_status": "paid",
				"payment_intent": "pi_123",
				"customer_email": "customer@example.com",
				"customer_details": {"email": "customer@example.com", "name": "Customer Name"},
				"metadata": {
					"brand": "bp_water_heaters",
					"booking_id": "BPWH-BKG-0001",
					"sales_invoice": "SINV-0001",
					"customer_email": "customer@example.com",
				},
			}
		},
	}

	sanitized = sanitize_stripe_event_for_audit(event)

	assert sanitized["event_id"] == "evt_123"
	assert sanitized["object"]["id"] == "cs_123"
	assert sanitized["object"]["metadata"] == {
		"brand": "bp_water_heaters",
		"booking_id": "BPWH-BKG-0001",
		"sales_invoice": "SINV-0001",
	}
	assert "customer_email" not in str(sanitized)
	assert "Customer Name" not in str(sanitized)


def test_rate_limit_store_blocks_after_window_capacity_and_clamps_limits():
	store = InMemoryRateLimitStore()

	assert check_rate_limit(store, "magic-link:ip:127.0.0.1", limit=2, window_seconds=60, now=1000)
	assert check_rate_limit(store, "magic-link:ip:127.0.0.1", limit=2, window_seconds=60, now=1001)
	assert not check_rate_limit(store, "magic-link:ip:127.0.0.1", limit=2, window_seconds=60, now=1002)
	assert check_rate_limit(store, "magic-link:ip:127.0.0.1", limit=2, window_seconds=60, now=1061)
	assert clamp_limit("999", default=25, maximum=50) == 50
	assert clamp_limit("bad", default=25, maximum=50) == 25
