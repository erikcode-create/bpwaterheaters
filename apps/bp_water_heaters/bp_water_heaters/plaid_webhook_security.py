from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


ALLOWED_TRANSACTIONS_SYNC_WEBHOOKS = {"SYNC_UPDATES_AVAILABLE"}
PLAID_WEBHOOK_MAX_AGE_SECONDS = 5 * 60


@dataclass(frozen=True)
class PlaidWebhookDecision:
	should_sync: bool
	item_id: str | None
	reason: str


def validate_plaid_webhook_claims(claims: dict[str, Any], raw_body: bytes, now: datetime | None = None) -> bool:
	now = now or datetime.now(timezone.utc)
	try:
		issued_at = int(claims.get("iat"))
	except (TypeError, ValueError):
		return False
	if abs(int(now.timestamp()) - issued_at) > PLAID_WEBHOOK_MAX_AGE_SECONDS:
		return False

	claimed_hash = str(claims.get("request_body_sha256") or "")
	body_hash = hashlib.sha256(raw_body).hexdigest()
	return bool(claimed_hash) and hmac.compare_digest(body_hash, claimed_hash)


def decide_transactions_webhook(
	payload: dict[str, Any],
	known_item_ids: Iterable[str],
	expected_environment: str | None,
) -> PlaidWebhookDecision:
	webhook_type = payload.get("webhook_type")
	webhook_code = payload.get("webhook_code")
	item_id = payload.get("item_id")
	environment = (payload.get("environment") or "").strip().lower()
	expected = (expected_environment or "").strip().lower()
	if webhook_type != "TRANSACTIONS":
		return PlaidWebhookDecision(False, item_id, "unsupported_type")
	if webhook_code not in ALLOWED_TRANSACTIONS_SYNC_WEBHOOKS:
		return PlaidWebhookDecision(False, item_id, "unsupported_code")
	if not item_id or item_id not in set(known_item_ids):
		return PlaidWebhookDecision(False, item_id, "unknown_item")
	if expected and environment and environment != expected:
		return PlaidWebhookDecision(False, item_id, "environment_mismatch")
	return PlaidWebhookDecision(True, item_id, "sync")
