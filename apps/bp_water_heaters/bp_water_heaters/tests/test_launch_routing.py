from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace


def _fake_frappe(host: str):
	return SimpleNamespace(local=SimpleNamespace(request=SimpleNamespace(host=host), response={}))


def _load_page(module_name: str, fake_frappe):
	sys.modules["frappe"] = fake_frappe
	module = importlib.import_module(module_name)
	module.frappe = fake_frappe
	return module


def test_portal_subdomain_root_uses_portal_context_without_login_redirect():
	fake_frappe = _fake_frappe("portal.bpwaterheaters.com")
	page = _load_page("bp_water_heaters.www.bpwaterheaters", fake_frappe)
	context = SimpleNamespace()

	page.get_context(context)

	assert fake_frappe.local.response == {}
	assert context.is_portal_root is True
	assert context.title == "BP Water Heaters Portal"


def test_public_root_still_uses_public_site_context():
	fake_frappe = _fake_frappe("bpwaterheaters.com")
	page = _load_page("bp_water_heaters.www.bpwaterheaters", fake_frappe)
	context = SimpleNamespace()

	page.get_context(context)

	assert context.is_portal_root is False
	assert context.title == "BP Water Heaters | Northern Nevada Water Heater Service"
	assert context.no_breadcrumbs
	assert context.show_sidebar is False


def test_junk_probe_routes_are_app_level_404_routes():
	from bp_water_heaters import hooks
	from bp_water_heaters.launch import JUNK_PROBE_ROUTES

	routes = {(rule["from_route"], rule["to_route"]) for rule in hooks.website_route_rules}

	for path in JUNK_PROBE_ROUTES:
		assert (path, "bpwh_not_found") in routes


def test_junk_probe_page_sets_clean_404_response():
	fake_frappe = _fake_frappe("bpwaterheaters.com")
	page = _load_page("bp_water_heaters.www.bpwh_not_found", fake_frappe)
	context = SimpleNamespace()

	page.get_context(context)

	assert fake_frappe.local.response["http_status_code"] == 404
	assert context.title == "Not Found"
