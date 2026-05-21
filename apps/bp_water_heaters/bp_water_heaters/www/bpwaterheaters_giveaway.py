import frappe

from bp_water_heaters.api.giveaway import get_campaign_context

no_cache = 1


def get_context(context):
	context.title = "Free Install Sweepstakes | BP Water Heaters"
	context.no_breadcrumbs = 1
	context.show_sidebar = False
	context.giveaway = frappe._dict(get_campaign_context())
