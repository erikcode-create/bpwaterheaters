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


@dataclass
class AtomicInMemoryRateLimitStore:
	values: dict[str, dict] | None = None
	increment_calls: int = 0

	def __post_init__(self):
		if self.values is None:
			self.values = {}

	def increment_window(self, key: str, window_seconds: int, now: int | None = None) -> int:
		self.increment_calls += 1
		current = int(now or time.time())
		value = self.values.get(key) or {}
		reset_at = int(value.get("reset_at") or 0)
		if reset_at <= current:
			value = {"count": 0, "reset_at": current + int(window_seconds)}
		value["count"] = int(value.get("count") or 0) + 1
		self.values[key] = value
		return int(value["count"])


class FrameworkRateLimitStore:
	def __init__(self, cache):
		self.cache = cache

	def increment_window(self, key: str, window_seconds: int, now: int | None = None) -> int | None:
		client, uses_raw_client = self._redis_client()
		if client is None:
			return None

		redis_key = self._redis_key(key, uses_raw_client)
		try:
			count = int(client.incr(redis_key))
		except (AttributeError, TypeError, ValueError):
			return None

		expires_in = max(1, int(window_seconds))
		if count == 1 or self._ttl(client, redis_key) < 0:
			self._expire(client, redis_key, expires_in)
		return count

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

	def _redis_client(self):
		for attr in ("redis_server", "redis_client"):
			client = getattr(self.cache, attr, None)
			if client is not None and hasattr(client, "incr") and hasattr(client, "expire"):
				return client, True
		if hasattr(self.cache, "incr") and hasattr(self.cache, "expire"):
			return self.cache, False
		return None, False

	def _redis_key(self, key: str, uses_raw_client: bool):
		if uses_raw_client:
			make_key = getattr(self.cache, "make_key", None)
			if callable(make_key):
				return make_key(key)
		return key

	def _ttl(self, client, key) -> int:
		ttl = getattr(client, "ttl", None)
		if not callable(ttl):
			return 1
		try:
			return int(ttl(key))
		except (TypeError, ValueError):
			return 1

	def _expire(self, client, key, expires_in: int) -> None:
		try:
			client.expire(key, expires_in)
		except TypeError:
			client.expire(name=key, time=expires_in)


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
	increment_window = getattr(store, "increment_window", None)
	if callable(increment_window):
		count = increment_window(key, window_seconds, now=now)
		if count is not None:
			return int(count) <= int(limit)

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


def client_ip(framework) -> str:
	local_ip = getattr(getattr(framework, "local", None), "request_ip", None)
	if local_ip:
		return str(local_ip)
	request = getattr(framework, "request", None)
	remote_addr = getattr(request, "remote_addr", None)
	if remote_addr:
		return str(remote_addr)
	forwarded = ""
	try:
		forwarded = framework.get_request_header("X-Forwarded-For") or ""
	except Exception:
		forwarded = ""
	return forwarded.split(",", 1)[0].strip() or "unknown"


def require_bpwh_rate_limit(
	framework,
	scope: str,
	identifier: str | None,
	limit: int,
	window_seconds: int,
	message: str = "Too many requests. Please try again later.",
) -> None:
	key = f"bpwh-rate:{scope}:{hashed_identifier(identifier)}"
	store = FrameworkRateLimitStore(framework.cache())
	if check_rate_limit(store, key, limit=limit, window_seconds=window_seconds):
		return
	error_type = getattr(framework, "RateLimitExceededError", getattr(framework, "ValidationError", Exception))
	framework.throw(message, error_type)
