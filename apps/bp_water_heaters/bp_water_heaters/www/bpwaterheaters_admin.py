import frappe

from bp_water_heaters.access import is_allowed_admin

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?redirect-to=/bpwaterheaters-admin"
		return

	if frappe.session.user != "Administrator" and not is_allowed_admin(frappe.session.user):
		frappe.throw("You are not allowed to administer BP Water Heaters.", frappe.PermissionError)

	context.no_cache = 1
	context.title = "BP Water Heaters Admin"
	context.no_breadcrumbs = 1
	context.show_sidebar = False
