from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Protocol


class RateLimitStore(Protocol):
	def get(self, key: str) -> dict | None:
		...

	def set(self, key: str, value: dict, expires_in: int) -> None:
		...


@dataclass
class InMemoryRateLimitStore:
	values: dict[str, dict] | None = None

	def __post_init__(self):
		if self.values is None:
			self.values = {}

	def get(self, key: str) -> dict | None:
		return self.values.get(key)

	def set(self, key: str, value: dict, expires_in: int) -> None:
		self.values[key] = value


class FrappeRateLimitStore:
	def __init__(self, cache):
		self.cache = cache

	def get(self, key: str) -> dict | None:
		raw = self.cache.get_value(key)
		if not raw:
			return None
		if isinstance(raw, bytes):
			raw = raw.decode("utf-8")
		if isinstance(raw, dict):
			return raw
		try:
			return json.loads(raw)
		except (TypeError, ValueError):
			return None

	def set(self, key: str, value: dict, expires_in: int) -> None:
		self.cache.set_value(key, json.dumps(value), expires_in_sec=expires_in)


def clamp_limit(value, default: int = 25, maximum: int = 50, minimum: int = 1) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		parsed = default
	return max(minimum, min(parsed, maximum))


def check_rate_limit(
	store: RateLimitStore,
	key: str,
	limit: int,
	window_seconds: int,
	now: int | None = None,
) -> bool:
	now = int(now or time.time())
	value = store.get(key) or {}
	reset_at = int(value.get("reset_at") or 0)
	count = int(value.get("count") or 0)
	if reset_at <= now:
		reset_at = now + int(window_seconds)
		count = 0
	if count >= int(limit):
		return False
	store.set(key, {"count": count + 1, "reset_at": reset_at}, max(1, reset_at - now))
	return True


def hashed_identifier(value: str | None) -> str:
	normalized = (value or "unknown").strip().lower()
	return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def client_ip(frappe_module) -> str:
	local_ip = getattr(getattr(frappe_module, "local", None), "request_ip", None)
	if local_ip:
		return str(local_ip)
	request = getattr(frappe_module, "request", None)
	remote_addr = getattr(request, "remote_addr", None)
	if remote_addr:
		return str(remote_addr)
	forwarded = ""
	try:
		forwarded = frappe_module.get_request_header("X-Forwarded-For") or ""
	except Exception:
		forwarded = ""
	return forwarded.split(",", 1)[0].strip() or "unknown"


def require_frappe_rate_limit(
	frappe_module,
	scope: str,
	identifier: str | None,
	limit: int,
	window_seconds: int,
	message: str = "Too many requests. Please try again later.",
) -> None:
	key = f"bpwh-rate:{scope}:{hashed_identifier(identifier)}"
	store = FrappeRateLimitStore(frappe_module.cache())
	if check_rate_limit(store, key, limit=limit, window_seconds=window_seconds):
		return
	error_type = getattr(frappe_module, "RateLimitExceededError", getattr(frappe_module, "ValidationError", Exception))
	frappe_module.throw(message, error_type)
