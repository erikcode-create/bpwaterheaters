app_name = "bp_water_heaters"
app_title = "BP Water Heaters"
app_publisher = "Blueberg Construction"
app_description = "ERPNext app for BP Water Heaters public site and booking"
app_email = "admin@bpwaterheaters.com"
app_license = "mit"
app_logo_url = "/assets/bp_water_heaters/images/bpwh-mark.svg"
app_include_css = "/assets/bp_water_heaters/css/bpwh_brand.css"
web_include_css = "/assets/bp_water_heaters/css/bpwh_brand.css"

after_install = "bp_water_heaters.install.after_install"
after_migrate = "bp_water_heaters.install.after_migrate"

website_route_rules = [
	{"from_route": "/", "to_route": "bpwaterheaters"},
	{"from_route": "/bpwaterheaters-portal", "to_route": "bpwaterheaters_portal"},
]

scheduler_events = {
	"hourly": [
		"bp_water_heaters.tasks.expire_stale_booking_holds",
	],
	"daily": [
		"bp_water_heaters.api.plaid.sync_bank_transactions",
	],
}

website_context = {
	"favicon": "/assets/bp_water_heaters/images/bpwh-mark.svg",
	"splash_image": "/assets/bp_water_heaters/images/bpwh-badge.svg",
}

fixtures = [
	{
		"doctype": "Role",
		"filters": [["name", "in", ["BPWH Admin"]]],
	}
]
