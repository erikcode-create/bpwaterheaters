from __future__ import annotations

ALLOWED_ADMIN_EMAILS = frozenset({"chase@bluebergconstruction.com", "curtis@bpwaterheaters.com"})


def normalize_email(email: str | None) -> str:
	return (email or "").strip().lower()


def is_allowed_admin(email: str | None) -> bool:
	return normalize_email(email) in ALLOWED_ADMIN_EMAILS
