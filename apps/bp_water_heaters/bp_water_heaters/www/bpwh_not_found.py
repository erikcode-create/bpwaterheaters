import frappe

no_cache = 1


def get_context(context):
	frappe.local.response["http_status_code"] = 404
	context.no_cache = 1
	context.title = "Not Found"
