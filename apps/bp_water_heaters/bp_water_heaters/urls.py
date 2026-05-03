from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode


def build_site_url(base_url: str, path: str = "", query: Mapping[str, object] | None = None) -> str:
	base = (base_url or "").strip().rstrip("/")
	clean_path = (path or "").strip()
	if clean_path and not clean_path.startswith("/"):
		clean_path = f"/{clean_path}"
	url = f"{base}{clean_path}"
	if query:
		params = {key: value for key, value in query.items() if value is not None}
		if params:
			url = f"{url}?{urlencode(params)}"
	return url


def public_url(path: str = "", query: Mapping[str, object] | None = None, config: Mapping[str, object] | None = None) -> str:
	return build_site_url(_configured_base("bpwh_public_base_url", config), path, query)


def portal_url(path: str = "", query: Mapping[str, object] | None = None, config: Mapping[str, object] | None = None) -> str:
	return build_site_url(_configured_base("bpwh_portal_base_url", config), path, query)


def webhook_url(method: str, config: Mapping[str, object] | None = None) -> str:
	return portal_url(f"/api/method/{method}", config=config)


def _configured_base(key: str, config: Mapping[str, object] | None = None) -> str:
	if config is not None:
		value = config.get(key)
		if value:
			return str(value)
	try:
		import frappe

		value = frappe.conf.get(key)
		if value:
			return str(value)
		return frappe.utils.get_url()
	except Exception:
		if key == "bpwh_portal_base_url":
			return "https://portal.bpwaterheaters.com"
		return "https://bpwaterheaters.com"
