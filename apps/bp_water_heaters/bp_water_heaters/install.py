import frappe

from bp_water_heaters.taxes import CALIFORNIA_SOURCE_URL, NEVADA_COUNTY_RATES, NEVADA_SOURCE_URL

CALLOUT_ITEM_CODE = "BPWH-CALLOUT-ESTIMATE"
COMPANY = "BP Water Heaters"
COMPANY_ABBR = "BPWH"
STRIPE_CARD_MODE = "Stripe Card"
STRIPE_ACH_MODE = "Stripe ACH"
STRIPE_CARD_ACCOUNT = f"Stripe Card Clearing - {COMPANY_ABBR}"
STRIPE_ACH_ACCOUNT = f"Stripe ACH Clearing - {COMPANY_ABBR}"
SALES_TAX_ACCOUNT = f"Sales Tax Payable - {COMPANY_ABBR}"
ADMIN_EMAILS = ("chase@bluebergconstruction.com", "curtis@bpwaterheaters.com")
BRAND_NAME = "BP Water Heaters"
BRAND_MARK = "/assets/bp_water_heaters/images/bpwh-logo.svg"
BRAND_BADGE = "/assets/bp_water_heaters/images/bpwh-badge.svg"
BLANK_FOOTER_TEMPLATE = "BPWH Empty Footer"
FRAPPE_HELP_ITEMS = {
	"Documentation",
	"User Forum",
	"Frappe School",
	"Report an Issue",
	"About",
	"Frappe Support",
}


def after_install():
	ensure_setup()


def after_migrate():
	ensure_setup()


def ensure_setup():
	ensure_branding()
	ensure_role()
	ensure_payment_accounts()
	ensure_payment_modes()
	ensure_callout_item()
	ensure_tax_templates()
	ensure_admin_users()
	ensure_microsoft_login_if_configured()
	ensure_signup_policy()
	redact_stripe_event_payloads()


def redact_stripe_event_payloads():
	if not frappe.db.exists("DocType", "BPWH Stripe Event"):
		return
	from bp_water_heaters.api.booking import redact_stored_stripe_payloads

	redact_stored_stripe_payloads()


def ensure_branding():
	ensure_empty_footer_template()
	_set_single_values(
		"Website Settings",
		{
			"app_name": BRAND_NAME,
			"app_logo": BRAND_MARK,
			"splash_image": BRAND_BADGE,
			"favicon": BRAND_MARK,
			"footer_template": BLANK_FOOTER_TEMPLATE,
			"footer_powered": 0,
			"show_footer_on_login": 0,
			"disable_signup": 1,
		},
	)
	_set_single_values("Navbar Settings", {"app_logo": BRAND_MARK})
	_set_single_values("System Settings", {"app_name": BRAND_NAME})
	ensure_bpwh_brand_record()
	remove_vendor_help_links()


def _set_single_values(doctype: str, values: dict):
	if not frappe.db.exists("DocType", doctype):
		return
	meta = frappe.get_meta(doctype)
	for field, value in values.items():
		if meta.has_field(field):
			frappe.db.set_single_value(doctype, field, value)


def ensure_bpwh_brand_record():
	existing = frappe.db.exists("Brand", {"brand": BRAND_NAME})
	if existing:
		doc = frappe.get_doc("Brand", existing)
	else:
		doc = frappe.get_doc({"doctype": "Brand", "brand": BRAND_NAME})

	doc.image = BRAND_BADGE
	doc.description = "Residential and commercial water heater service for Northern Nevada and California."
	doc.save(ignore_permissions=True)


def ensure_empty_footer_template():
	if not frappe.db.exists("DocType", "Web Template"):
		return

	if frappe.db.exists("Web Template", BLANK_FOOTER_TEMPLATE):
		doc = frappe.get_doc("Web Template", BLANK_FOOTER_TEMPLATE)
		is_new = False
	else:
		doc = frappe.get_doc({"doctype": "Web Template", "name": BLANK_FOOTER_TEMPLATE})
		is_new = True

	doc.type = "Footer"
	doc.standard = 0
	doc.template = ""
	if is_new:
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def remove_vendor_help_links():
	if not frappe.db.exists("DocType", "Navbar Settings"):
		return

	navbar_settings = frappe.get_single("Navbar Settings")
	items_to_remove = [
		item for item in navbar_settings.get("help_dropdown", []) if item.item_label in FRAPPE_HELP_ITEMS
	]
	if not items_to_remove:
		return

	for item in items_to_remove:
		navbar_settings.remove(item)

	previous_in_patch = getattr(frappe.flags, "in_patch", False)
	try:
		frappe.flags.in_patch = True
		navbar_settings.save(ignore_permissions=True)
	finally:
		frappe.flags.in_patch = previous_in_patch


def ensure_role():
	if not frappe.db.exists("Role", "BPWH Admin"):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": "BPWH Admin",
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)


def ensure_callout_item():
	if frappe.db.exists("Item", CALLOUT_ITEM_CODE):
		return

	item_group = frappe.db.exists("Item Group", "Services") or frappe.db.exists("Item Group", "All Item Groups")
	stock_uom = frappe.db.exists("UOM", "Nos") or frappe.db.get_value("UOM", {}, "name")

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": CALLOUT_ITEM_CODE,
			"item_name": "BP Water Heaters Estimate Call-Out Fee",
			"description": (
				"One-hour water heater estimate visit. Creditable toward approved replacement "
				"or larger service work."
			),
			"item_group": item_group,
			"stock_uom": stock_uom,
			"is_stock_item": 0,
			"is_sales_item": 1,
		}
	).insert(ignore_permissions=True)


def ensure_payment_accounts():
	ensure_account("Stripe Card Clearing", STRIPE_CARD_ACCOUNT, "Bank", _bank_parent_account())
	ensure_account("Stripe ACH Clearing", STRIPE_ACH_ACCOUNT, "Bank", _bank_parent_account())
	ensure_account("Sales Tax Payable", SALES_TAX_ACCOUNT, "Tax", _tax_parent_account())


def ensure_account(account_name, full_account_name, account_type, parent_account):
	if frappe.db.exists("Account", full_account_name):
		return full_account_name

	frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"company": COMPANY,
			"parent_account": parent_account,
			"account_type": account_type,
			"is_group": 0,
		}
	).insert(ignore_permissions=True)
	return full_account_name


def ensure_payment_modes():
	ensure_mode_of_payment(STRIPE_CARD_MODE, STRIPE_CARD_ACCOUNT)
	ensure_mode_of_payment(STRIPE_ACH_MODE, STRIPE_ACH_ACCOUNT)


def ensure_mode_of_payment(mode, account):
	if frappe.db.exists("Mode of Payment", mode):
		doc = frappe.get_doc("Mode of Payment", mode)
	else:
		doc = frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mode, "type": "Bank", "enabled": 1})

	if not any(row.company == COMPANY for row in doc.get("accounts", [])):
		doc.append("accounts", {"company": COMPANY, "default_account": account})
	doc.save(ignore_permissions=True)


def ensure_tax_templates():
	for county_key, (template_name, rate) in NEVADA_COUNTY_RATES.items():
		ensure_tax_rule_and_template("NV", county_key.title(), template_name, rate, NEVADA_SOURCE_URL)
	ensure_tax_rule_and_template("NV", "Nevada base", "NV State Base Sales Tax - BPWH", 6.85, NEVADA_SOURCE_URL)
	ensure_tax_rule_and_template("CA", "California statewide", "CA Statewide Sales Tax - BPWH", 7.25, CALIFORNIA_SOURCE_URL)
	ensure_tax_rule_and_template("OOA", "Out of area", "Out of Area Sales Tax - BPWH", 0.0, "")


def ensure_tax_rule_and_template(state, jurisdiction, template_name, rate, source_url):
	if not frappe.db.exists("BPWH Tax Rule", template_name):
		frappe.get_doc(
			{
				"doctype": "BPWH Tax Rule",
				"template_name": template_name,
				"state": state,
				"jurisdiction": jurisdiction,
				"rate": rate,
				"source_url": source_url,
				"effective_date": "2026-04-01",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	if _existing_sales_tax_template(template_name):
		return

	template = frappe.get_doc(
		{
			"doctype": "Sales Taxes and Charges Template",
			"title": template_name,
			"company": COMPANY,
			"disabled": 0,
		}
	)
	if rate:
		template.append(
			"taxes",
			{
				"charge_type": "On Net Total",
				"account_head": SALES_TAX_ACCOUNT,
				"description": f"{jurisdiction} sales tax",
				"rate": rate,
			},
		)
	template.insert(ignore_permissions=True)


def _existing_sales_tax_template(template_name):
	return frappe.db.exists("Sales Taxes and Charges Template", template_name) or frappe.db.exists(
		"Sales Taxes and Charges Template", f"{template_name} - {COMPANY_ABBR}"
	)


def _bank_parent_account():
	return frappe.db.exists("Account", f"Bank Accounts - {COMPANY_ABBR}") or frappe.db.exists(
		"Account", f"Current Assets - {COMPANY_ABBR}"
	)


def _tax_parent_account():
	return (
		frappe.db.exists("Account", f"Duties and Taxes - {COMPANY_ABBR}")
		or frappe.db.exists("Account", f"Current Liabilities - {COMPANY_ABBR}")
		or frappe.db.exists("Account", f"Liabilities - {COMPANY_ABBR}")
	)


def ensure_admin_users():
	for email in ADMIN_EMAILS:
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
		else:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@", 1)[0].title(),
					"user_type": "System User",
					"enabled": 1,
					"send_welcome_email": 0,
				}
			)
		if not any(role.role == "BPWH Admin" for role in user.get("roles", [])):
			user.append("roles", {"role": "BPWH Admin"})
		user.save(ignore_permissions=True)


def ensure_microsoft_login_if_configured():
	tenant_id = frappe.conf.get("bpwh_microsoft_tenant_id")
	client_id = frappe.conf.get("bpwh_microsoft_client_id")
	client_secret = frappe.conf.get("bpwh_microsoft_client_secret")
	if not all([tenant_id, client_id, client_secret]):
		return

	if frappe.db.exists("Social Login Key", "office_365"):
		doc = frappe.get_doc("Social Login Key", "office_365")
	else:
		doc = frappe.new_doc("Social Login Key")
		doc.social_login_provider = "Office 365"
		doc.provider_name = "Office 365"

	doc.enable_social_login = 1
	doc.client_id = client_id
	doc.client_secret = client_secret
	doc.base_url = "https://login.microsoftonline.com"
	doc.custom_base_url = 0
	doc.authorize_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/authorize"
	doc.access_token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	doc.redirect_url = "/api/method/frappe.integrations.oauth2_logins.login_via_office365"
	doc.auth_url_data = '{"response_type": "code", "scope": "openid email profile"}'
	doc.sign_ups = "Deny"
	doc.save(ignore_permissions=True)

	if frappe.conf.get("bpwh_disable_password_login_after_microsoft"):
		frappe.db.set_single_value("System Settings", "disable_user_pass_login", 1)


def ensure_signup_policy():
	try:
		frappe.db.set_single_value("Website Settings", "disable_signup", 1)
	except Exception:
		pass
