import frappe

no_cache = 1


def get_context(context):
	host = (frappe.local.request.host or "").split(":")[0]
	if host == "portal.bpwaterheaters.com":
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login"
		return
	context.title = "BP Water Heaters | Northern Nevada Water Heater Service"
	context.no_breadcrumbs = 1
	context.show_sidebar = False
