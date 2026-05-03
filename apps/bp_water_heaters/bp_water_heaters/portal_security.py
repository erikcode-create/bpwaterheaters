from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


PORTAL_TOKEN_DAYS = 7


@dataclass(frozen=True)
class IssuedPortalToken:
	email: str
	token: str
	token_hash: str
	expires_at: datetime


@dataclass(frozen=True)
class IssuedCheckoutReturnToken:
	portal_token: str
	email: str
	sales_invoice: str
	token: str
	token_hash: str
	expires_at: datetime


def issue_token(email: str, now: datetime | None = None) -> IssuedPortalToken:
	now = now or datetime.now(timezone.utc)
	token = secrets.token_urlsafe(32)
	return IssuedPortalToken(
		email=email.strip().lower(),
		token=token,
		token_hash=hash_token(token),
		expires_at=now + timedelta(days=PORTAL_TOKEN_DAYS),
	)


def hash_token(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_checkout_return_token(
	portal_token: str,
	email: str,
	sales_invoice: str,
	now: datetime | None = None,
) -> IssuedCheckoutReturnToken:
	now = now or datetime.now(timezone.utc)
	token = secrets.token_urlsafe(32)
	return IssuedCheckoutReturnToken(
		portal_token=portal_token,
		email=email.strip().lower(),
		sales_invoice=sales_invoice,
		token=token,
		token_hash=hash_return_token(token),
		expires_at=now + timedelta(minutes=30),
	)


def hash_return_token(token: str) -> str:
	return hashlib.sha256((token or "").strip().encode("utf-8")).hexdigest()
