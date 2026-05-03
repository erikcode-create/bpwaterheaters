from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from bp_water_heaters.access import is_allowed_admin, normalize_email
from bp_water_heaters.mobile_auth import (
	email_from_microsoft_claims,
	issue_mobile_token,
	user_from_bearer_token,
	validate_microsoft_id_token,
)

DEFAULT_REDIRECT_URI = "bpwhadmin://auth"


@frappe.whitelist(allow_guest=True)
def mobile_oauth_config():
	tenant_id, client_id = _mobile_microsoft_config()
	redirect_uri = frappe.conf.get("bpwh_mobile_redirect_uri") or DEFAULT_REDIRECT_URI
	if not tenant_id or not client_id:
		return {"configured": False, "message": "Microsoft mobile auth is not configured."}
	return {
		"configured": True,
		"tenant_id": tenant_id,
		"client_id": client_id,
		"authorization_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
		"token_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
		"redirect_uri": redirect_uri,
		"scopes": ["openid", "email", "profile"],
	}


@frappe.whitelist(allow_guest=True)
def login_with_microsoft_id_token(id_token: str, device_name: str | None = None):
	tenant_id, client_id = _mobile_microsoft_config()
	claims = validate_microsoft_id_token(id_token, tenant_id, client_id)
	email = email_from_microsoft_claims(claims)
	if not is_allowed_admin(email):
		frappe.throw(_("You are not allowed to administer BP Water Heaters."), frappe.PermissionError)

	user = _ensure_admin_user(email)
	issued = issue_mobile_token(user)
	frappe.get_doc(
		{
			"doctype": "BPWH Mobile Session",
			"user": user,
			"status": "Active",
			"token_hash": issued.token_hash,
			"expires_at": issued.expires_at.replace(tzinfo=None),
			"last_accessed_at": now_datetime(),
			"device_name": device_name,
			"microsoft_subject": claims.get("sub"),
		}
	).insert(ignore_permissions=True)
	return {"token": issued.token, "expires_at": issued.expires_at.isoformat(), "user": user}


@frappe.whitelist(allow_guest=True)
def me():
	user = user_from_bearer_token()
	if not user:
		frappe.throw(_("Mobile session is invalid or expired."), frappe.PermissionError)
	return {"user": user}


@frappe.whitelist(allow_guest=True)
def logout():
	user = user_from_bearer_token()
	if not user:
		return {"ok": True}
	header = frappe.get_request_header("Authorization") or ""
	token = header.split(" ", 1)[1].strip()
	from bp_water_heaters.mobile_auth import hash_mobile_token

	name = frappe.db.get_value("BPWH Mobile Session", {"token_hash": hash_mobile_token(token), "status": "Active"}, "name")
	if name:
		frappe.db.set_value("BPWH Mobile Session", name, "status", "Revoked", update_modified=True)
	return {"ok": True}


def _mobile_microsoft_config():
	tenant_id = frappe.conf.get("bpwh_mobile_microsoft_tenant_id") or frappe.conf.get("bpwh_microsoft_tenant_id")
	client_id = frappe.conf.get("bpwh_mobile_microsoft_client_id") or frappe.conf.get("bpwh_microsoft_client_id")
	return (tenant_id or "").strip(), (client_id or "").strip()


def _ensure_admin_user(email: str):
	normalized = normalize_email(email)
	if frappe.db.exists("User", normalized):
		return normalized

	parts = normalized.split("@", 1)[0].replace(".", " ").replace("_", " ").split()
	first_name = parts[0].title() if parts else "BPWH"
	last_name = " ".join(part.title() for part in parts[1:]) if len(parts) > 1 else "Admin"
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": normalized,
			"first_name": first_name,
			"last_name": last_name,
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": "BPWH Admin"}],
		}
	)
	user.insert(ignore_permissions=True)
	return normalized
