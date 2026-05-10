import frappe

from bp_water_heaters.launch import is_portal_host

no_cache = 1


def get_context(context):
	host = getattr(getattr(frappe.local, "request", None), "host", "")
	context.is_portal_root = is_portal_host(host)
	if context.is_portal_root:
		context.no_cache = 1
		context.title = "BP Water Heaters Portal"
		return
	context.title = "BP Water Heaters | Northern Nevada Water Heater Service"
	context.no_breadcrumbs = 1
	context.show_sidebar = False
