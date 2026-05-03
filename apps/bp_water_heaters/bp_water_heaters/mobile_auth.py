from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bp_water_heaters.access import is_allowed_admin, normalize_email

MOBILE_TOKEN_HOURS = 12


@dataclass(frozen=True)
class IssuedMobileToken:
	user: str
	token: str
	token_hash: str
	expires_at: datetime


def hash_mobile_token(token: str) -> str:
	return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def issue_mobile_token(user: str, now: datetime | None = None) -> IssuedMobileToken:
	normalized = normalize_email(user)
	if not is_allowed_admin(normalized):
		raise ValueError("User is not allowed to administer BP Water Heaters.")

	issued_at = now or datetime.now(timezone.utc)
	token = secrets.token_urlsafe(48)
	return IssuedMobileToken(
		user=normalized,
		token=token,
		token_hash=hash_mobile_token(token),
		expires_at=issued_at + timedelta(hours=MOBILE_TOKEN_HOURS),
	)


def validate_microsoft_id_token(id_token: str, tenant_id: str, client_id: str) -> dict:
	try:
		import jwt
		from jwt import PyJWKClient
	except ImportError as exc:
		raise RuntimeError("PyJWT with crypto support is not installed.") from exc

	if not id_token or not tenant_id or not client_id:
		raise ValueError("Microsoft tenant ID, client ID, and ID token are required.")

	jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
	issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
	signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(id_token).key
	claims = jwt.decode(id_token, signing_key, algorithms=["RS256"], audience=client_id, issuer=issuer)
	if normalize_email(claims.get("tid")) != normalize_email(tenant_id):
		raise ValueError("Microsoft token came from the wrong tenant.")
	return claims


def email_from_microsoft_claims(claims: dict) -> str:
	return normalize_email(claims.get("preferred_username") or claims.get("email") or claims.get("upn"))


def user_from_bearer_token(token: str | None = None) -> str | None:
	try:
		import frappe
		from frappe.utils import get_datetime, now_datetime
	except Exception:
		return None

	bearer = token or _authorization_bearer()
	if not bearer:
		return None

	token_hash = hash_mobile_token(bearer)
	name = frappe.db.get_value("BPWH Mobile Session", {"token_hash": token_hash, "status": "Active"}, "name")
	if not name:
		return None

	doc = frappe.get_doc("BPWH Mobile Session", name)
	if get_datetime(doc.expires_at) <= now_datetime():
		doc.db_set("status", "Expired", update_modified=True)
		return None
	if not is_allowed_admin(doc.user):
		return None

	doc.db_set("last_accessed_at", now_datetime(), update_modified=False)
	return doc.user


def _authorization_bearer() -> str | None:
	import frappe

	header = frappe.get_request_header("Authorization") or ""
	if not header.lower().startswith("bearer "):
		return None
	return header.split(" ", 1)[1].strip() or None
