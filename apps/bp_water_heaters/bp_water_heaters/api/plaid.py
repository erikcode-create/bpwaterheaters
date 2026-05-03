from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

from bp_water_heaters.api.admin import require_bpwh_admin, require_post
from bp_water_heaters.plaid_webhook_security import decide_transactions_webhook, validate_plaid_webhook_claims
from bp_water_heaters.plaid_sync import plaid_removed_transaction_id, plaid_transaction_to_bank_transaction
from bp_water_heaters.security_limits import client_ip, require_bpwh_rate_limit
from bp_water_heaters.urls import webhook_url

COMPANY = "BP Water Heaters"
PLAID_ENVIRONMENTS = {
	"sandbox": "https://sandbox.plaid.com",
	"development": "https://development.plaid.com",
	"production": "https://production.plaid.com",
}
TRANSACTIONS_WEBHOOK_METHOD = "bp_water_heaters.api.plaid.transactions_webhook"


@frappe.whitelist()
def status():
	require_bpwh_admin()
	return {
		"configured": _plaid_is_configured(),
		"environment": (frappe.conf.get("bpwh_plaid_environment") or "production").strip().lower(),
		"items": _plaid_items(),
		"bank_accounts": _bank_accounts(),
	}


@frappe.whitelist()
def create_link_token():
	require_bpwh_admin()
	payload = {
		"user": {"client_user_id": _client_user_id()},
		"client_name": "BP Water Heaters ERP",
		"products": ["transactions"],
		"country_codes": ["US"],
		"language": "en",
		"webhook": webhook_url(TRANSACTIONS_WEBHOOK_METHOD),
		"transactions": {"days_requested": 730},
	}
	response = _plaid_request("/link/token/create", payload)
	return {
		"link_token": response.get("link_token"),
		"expiration": response.get("expiration"),
		"request_id": response.get("request_id"),
	}


@frappe.whitelist()
def exchange_public_token(public_token: str, institution_name: str | None = None):
	require_bpwh_admin()
	require_post()
	if not public_token:
		frappe.throw(_("Plaid public token is required."))

	response = _plaid_request("/item/public_token/exchange", {"public_token": public_token})
	item_id = response.get("item_id")
	access_token = response.get("access_token")
	if not item_id or not access_token:
		frappe.throw(_("Plaid did not return an Item ID and access token."))

	doc = _get_or_create_plaid_item(item_id)
	doc.institution_name = institution_name or doc.institution_name or item_id
	doc.access_token = access_token
	doc.status = "Needs Account Mapping"
	doc.last_error = None
	doc.save(ignore_permissions=True)
	return {"item": doc.name, "item_id": item_id, "status": doc.status}


@frappe.whitelist()
def list_plaid_accounts(item: str):
	require_bpwh_admin()
	doc = frappe.get_doc("BPWH Plaid Item", item)
	response = _plaid_request("/accounts/get", {"access_token": _access_token(doc)})
	return {
		"item": doc.name,
		"accounts": [_public_account(account) for account in response.get("accounts", [])],
		"request_id": response.get("request_id"),
	}


@frappe.whitelist()
def map_plaid_account(item: str, plaid_account_id: str, bank_account: str):
	require_bpwh_admin()
	require_post()
	doc = frappe.get_doc("BPWH Plaid Item", item)
	accounts = list_plaid_accounts(doc.name)["accounts"]
	selected = next((account for account in accounts if account["account_id"] == plaid_account_id), None)
	if not selected:
		frappe.throw(_("That Plaid account is not available for this Item."))

	if not bank_account or bank_account == "__create__":
		bank_account = _ensure_erp_bank_account(doc, selected)
	elif not frappe.db.exists("Bank Account", bank_account):
		frappe.throw(_("ERPNext Bank Account {0} does not exist.").format(bank_account))
	else:
		_update_bank_account_metadata(bank_account, doc, selected)

	doc.selected_plaid_account_id = selected["account_id"]
	doc.selected_account_name = selected.get("name")
	doc.selected_account_mask = selected.get("mask")
	doc.bank_account = bank_account
	doc.status = "Linked"
	doc.last_error = None
	doc.save(ignore_permissions=True)
	return {"item": doc.name, "status": doc.status, "bank_account": doc.bank_account, "plaid_account": selected}


@frappe.whitelist()
def sync_bank_transactions(item: str | None = None):
	_maybe_require_admin()
	items = _items_for_sync(item)
	if not items:
		_log_sync("Not Configured", "No mapped Plaid Items are ready to sync.")
		return {"configured": False, "message": "No mapped Plaid Items are ready to sync.", "items": []}

	results = []
	for plaid_item in items:
		doc = frappe.get_doc("BPWH Plaid Item", plaid_item)
		try:
			results.append(_sync_item_transactions(doc))
		except Exception as exc:
			doc.db_set({"status": "Failed", "last_error": str(exc)}, update_modified=True)
			_log_sync("Failed", str(exc), doc)
			raise

	return {"configured": True, "items": results}


@frappe.whitelist(allow_guest=True)
def transactions_webhook():
	require_bpwh_rate_limit(frappe, "plaid-webhook-ip", client_ip(frappe), limit=120, window_seconds=60)
	raw_body = frappe.request.get_data() or b""
	_verify_plaid_webhook(raw_body)
	try:
		payload = json.loads(raw_body.decode("utf-8"))
	except (UnicodeDecodeError, ValueError):
		frappe.throw(_("Plaid webhook body is invalid."), frappe.PermissionError)
	decision = decide_transactions_webhook(payload, _known_plaid_item_ids(), _configured_plaid_environment())
	if decision.should_sync:
		require_bpwh_rate_limit(
			frappe,
			"plaid-webhook-item",
			decision.item_id,
			limit=12,
			window_seconds=300,
		)
		frappe.enqueue(
			"bp_water_heaters.api.plaid.sync_bank_transactions",
			queue="short",
			item=decision.item_id,
		)
	return {"ok": True, "action": decision.reason}


def _sync_item_transactions(doc):
	if not doc.bank_account or not doc.selected_plaid_account_id:
		frappe.throw(_("Plaid Item {0} is not mapped to an ERP bank account.").format(doc.name))

	added: list[dict[str, Any]] = []
	modified: list[dict[str, Any]] = []
	removed: list[dict[str, Any]] = []
	cursor = doc.cursor or None
	next_cursor = cursor

	while True:
		payload = {"access_token": _access_token(doc)}
		if next_cursor:
			payload["cursor"] = next_cursor
		response = _plaid_request("/transactions/sync", payload)
		added.extend(_for_selected_account(response.get("added", []), doc.selected_plaid_account_id))
		modified.extend(_for_selected_account(response.get("modified", []), doc.selected_plaid_account_id))
		removed.extend(response.get("removed", []))
		next_cursor = response.get("next_cursor")
		if not response.get("has_more"):
			break

	created = updated = deleted = 0
	for transaction in added:
		action = _upsert_bank_transaction(transaction, doc.bank_account)
		created += 1 if action == "created" else 0
		updated += 1 if action == "updated" else 0
	for transaction in modified:
		action = _upsert_bank_transaction(transaction, doc.bank_account)
		created += 1 if action == "created" else 0
		updated += 1 if action == "updated" else 0
	for removed_transaction in removed:
		deleted += 1 if _remove_bank_transaction(removed_transaction, doc.bank_account) else 0

	doc.db_set(
		{
			"cursor": next_cursor,
			"status": "Synced",
			"last_synced_at": now_datetime(),
			"last_error": None,
		},
		update_modified=True,
	)
	_log_sync("Synced", None, doc)
	return {
		"item": doc.name,
		"created": created,
		"updated": updated,
		"removed": deleted,
		"cursor": next_cursor,
	}


def _upsert_bank_transaction(transaction, bank_account):
	transaction_id = transaction.get("transaction_id")
	if not transaction_id:
		return "ignored"

	values = plaid_transaction_to_bank_transaction(transaction, bank_account, COMPANY)
	name = frappe.db.get_value("Bank Transaction", {"transaction_id": transaction_id, "bank_account": bank_account}, "name")
	if name:
		doc = frappe.get_doc("Bank Transaction", name)
		for field, value in values.items():
			if field != "doctype":
				doc.db_set(field, value, update_modified=True)
		return "updated"

	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return "created"


def _remove_bank_transaction(removed, bank_account):
	transaction_id = plaid_removed_transaction_id(removed)
	if not transaction_id:
		return False

	name = frappe.db.get_value("Bank Transaction", {"transaction_id": transaction_id, "bank_account": bank_account}, "name")
	if not name:
		return False

	doc = frappe.get_doc("Bank Transaction", name)
	if doc.docstatus == 0:
		doc.delete(ignore_permissions=True)
		return True
	if doc.docstatus == 1:
		doc.cancel()
		return True
	return False


def _items_for_sync(item=None):
	if item:
		return [item]
	return frappe.get_all(
		"BPWH Plaid Item",
		filters={
			"bank_account": ["is", "set"],
			"selected_plaid_account_id": ["is", "set"],
			"status": ["in", ["Linked", "Synced", "Failed"]],
		},
		pluck="name",
	)


def _get_or_create_plaid_item(item_id: str):
	if frappe.db.exists("BPWH Plaid Item", item_id):
		return frappe.get_doc("BPWH Plaid Item", item_id)
	return frappe.get_doc({"doctype": "BPWH Plaid Item", "item_id": item_id, "status": "Needs Account Mapping"})


def _plaid_request(endpoint: str, payload: dict[str, Any]):
	client_id = frappe.conf.get("bpwh_plaid_client_id")
	secret = frappe.conf.get("bpwh_plaid_secret")
	if not client_id or not secret:
		frappe.throw(_("Plaid production client ID and secret are not configured."))

	url = f"{_plaid_base_url()}{endpoint}"
	body = {"client_id": client_id, "secret": secret, **payload}
	response = requests.post(url, json=body, timeout=45)
	try:
		data = response.json()
	except ValueError:
		data = {"error": response.text}
	if response.status_code >= 400:
		message = data.get("error_message") or data.get("error") or response.text
		frappe.throw(_("Plaid request failed: {0}").format(message))
	return data


def _plaid_is_configured():
	return bool(frappe.conf.get("bpwh_plaid_client_id") and frappe.conf.get("bpwh_plaid_secret"))


def _plaid_items():
	return frappe.get_all(
		"BPWH Plaid Item",
		fields=[
			"name",
			"item_id",
			"institution_name",
			"status",
			"selected_account_name",
			"selected_account_mask",
			"bank_account",
			"last_synced_at",
			"last_error",
		],
		order_by="modified desc",
		limit_page_length=50,
	)


def _bank_accounts():
	meta = frappe.get_meta("Bank Account")
	fields = ["name"]
	for field in ["account_name", "bank", "account", "is_company_account"]:
		if meta.has_field(field):
			fields.append(field)
	return frappe.get_all("Bank Account", fields=fields, order_by="modified desc", limit_page_length=100)


def _client_user_id():
	source = f"{frappe.local.site}:{frappe.session.user}"
	digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
	return f"bpwh-{digest[:24]}"


def _ensure_erp_bank_account(item_doc, selected):
	integration_id = selected["account_id"]
	existing = frappe.db.exists("Bank Account", {"integration_id": integration_id})
	if existing:
		_update_bank_account_metadata(existing, item_doc, selected)
		return existing

	institution_name = (item_doc.institution_name or "Plaid Bank").strip()
	if not frappe.db.exists("Bank", institution_name):
		frappe.get_doc({"doctype": "Bank", "bank_name": institution_name}).insert(ignore_permissions=True)

	parent_account = frappe.db.exists("Account", "Bank Accounts - BPWH")
	if not parent_account:
		frappe.throw(_("BPWH bank parent account is not configured."))

	account_name = _bank_gl_account_name(item_doc, selected)
	gl_account = frappe.db.exists("Account", f"{account_name} - BPWH")
	if not gl_account:
		gl_account = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"parent_account": parent_account,
				"account_type": "Bank",
				"company": COMPANY,
			}
		).insert(ignore_permissions=True).name

	bank_account = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": selected.get("name") or account_name,
			"bank": institution_name,
			"account": gl_account,
			"mask": selected.get("mask"),
			"integration_id": integration_id,
			"is_company_account": 1,
			"company": COMPANY,
		}
	)
	bank_account.insert(ignore_permissions=True)
	return bank_account.name


def _update_bank_account_metadata(bank_account, item_doc, selected):
	updates = {
		"account_name": selected.get("name"),
		"mask": selected.get("mask"),
		"integration_id": selected.get("account_id"),
		"is_company_account": 1,
		"company": COMPANY,
	}
	if item_doc.institution_name:
		if not frappe.db.exists("Bank", item_doc.institution_name):
			frappe.get_doc({"doctype": "Bank", "bank_name": item_doc.institution_name}).insert(ignore_permissions=True)
		updates["bank"] = item_doc.institution_name
	frappe.db.set_value("Bank Account", bank_account, updates, update_modified=True)


def _bank_gl_account_name(item_doc, selected):
	parts = [selected.get("name") or "Operating Bank", item_doc.institution_name, selected.get("mask")]
	name = " ".join(part for part in parts if part)
	return name[:120]


def _plaid_base_url():
	environment = _configured_plaid_environment()
	return PLAID_ENVIRONMENTS.get(environment, PLAID_ENVIRONMENTS["production"])


def _configured_plaid_environment():
	return (frappe.conf.get("bpwh_plaid_environment") or "production").strip().lower()


def _access_token(doc):
	if hasattr(doc, "get_password"):
		return doc.get_password("access_token")
	return doc.access_token


def _for_selected_account(transactions, plaid_account_id):
	return [transaction for transaction in transactions if transaction.get("account_id") == plaid_account_id]


def _public_account(account):
	return {
		"account_id": account.get("account_id"),
		"name": account.get("name"),
		"official_name": account.get("official_name"),
		"mask": account.get("mask"),
		"type": account.get("type"),
		"subtype": account.get("subtype"),
		"iso_currency_code": (account.get("balances") or {}).get("iso_currency_code"),
	}


def _maybe_require_admin():
	if getattr(frappe, "session", None) and getattr(frappe.session, "user", "Guest") != "Guest":
		require_bpwh_admin()


def _verify_plaid_webhook(raw_body: bytes):
	signed_jwt = frappe.get_request_header("Plaid-Verification")
	if not signed_jwt:
		frappe.throw(_("Plaid webhook signature is missing."), frappe.PermissionError)
	try:
		import jwt
		from jwt import algorithms
	except ImportError:
		frappe.throw(_("PyJWT with crypto support is not installed."), frappe.PermissionError)
	try:
		header = jwt.get_unverified_header(signed_jwt)
	except Exception:
		frappe.throw(_("Plaid webhook signature is invalid."), frappe.PermissionError)
	if header.get("alg") != "ES256" or not header.get("kid"):
		frappe.throw(_("Plaid webhook signature algorithm is unsupported."), frappe.PermissionError)
	key = _plaid_webhook_key(header["kid"])
	try:
		public_key = algorithms.ECAlgorithm.from_jwk(json.dumps(key))
		claims = jwt.decode(
			signed_jwt,
			key=public_key,
			algorithms=["ES256"],
			options={"verify_aud": False, "verify_iat": False},
		)
	except Exception:
		frappe.throw(_("Plaid webhook signature is invalid."), frappe.PermissionError)
	if not validate_plaid_webhook_claims(claims, raw_body):
		frappe.throw(_("Plaid webhook signature body check failed."), frappe.PermissionError)
	return claims


def _plaid_webhook_key(key_id: str):
	cache_key = f"bpwh:plaid-webhook-key:{key_id}"
	cached = frappe.cache().get_value(cache_key)
	if cached:
		if isinstance(cached, bytes):
			cached = cached.decode("utf-8")
		try:
			key = json.loads(cached) if isinstance(cached, str) else cached
		except ValueError:
			key = None
		if key and _plaid_webhook_key_is_current(key):
			return key

	response = _plaid_request("/webhook_verification_key/get", {"key_id": key_id})
	key = response.get("key")
	if not key:
		frappe.throw(_("Plaid webhook verification key was not returned."), frappe.PermissionError)
	expired_at = key.get("expired_at")
	ttl = 3600
	if expired_at:
		ttl = max(60, int(int(expired_at) - time.time()))
	frappe.cache().set_value(cache_key, json.dumps(key), expires_in_sec=ttl)
	return key


def _plaid_webhook_key_is_current(key: dict[str, Any]):
	expired_at = key.get("expired_at")
	return not expired_at or int(expired_at) > int(time.time())


def _known_plaid_item_ids():
	return frappe.get_all("BPWH Plaid Item", pluck="name", limit_page_length=500)


def _log_sync(status, error=None, item=None):
	doc = frappe.get_doc(
		{
			"doctype": "BPWH Plaid Sync Log",
			"plaid_item_id": item.item_id if item else None,
			"cursor": item.cursor if item else None,
			"status": status,
			"last_synced_at": now_datetime(),
			"error": error,
		}
	)
	doc.insert(ignore_permissions=True)
