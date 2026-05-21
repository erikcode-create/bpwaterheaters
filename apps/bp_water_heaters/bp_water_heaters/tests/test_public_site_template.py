from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SITE_TEMPLATE = APP_ROOT / "www" / "bpwaterheaters.html"
GIVEAWAY_TEMPLATE = APP_ROOT / "www" / "bpwaterheaters_giveaway.html"
GIVEAWAY_RULES_TEMPLATE = APP_ROOT / "www" / "bpwaterheaters_giveaway_rules.html"
ADMIN_TEMPLATE = APP_ROOT / "www" / "bpwaterheaters_admin.html"
PUBLIC_CSS = APP_ROOT / "public" / "css" / "bpwh.css"
PUBLIC_DESIGN_CSS = APP_ROOT / "public" / "css" / "bpwh_design.css"


def _public_site_template():
	return PUBLIC_SITE_TEMPLATE.read_text()


def _giveaway_template():
	return GIVEAWAY_TEMPLATE.read_text()


def _giveaway_rules_template():
	return GIVEAWAY_RULES_TEMPLATE.read_text()


def _admin_template():
	return ADMIN_TEMPLATE.read_text()


def _public_css():
	return PUBLIC_CSS.read_text()


def _public_design_css():
	return PUBLIC_DESIGN_CSS.read_text()


def test_public_site_uses_launch_handoff_design_markers():
	template = _public_site_template()
	css = _public_design_css()

	assert "Hot water," in template
	assert "handled" in template
	assert "NV LIC #0095421" in template
	assert "BP Water Heaters, LLC" not in template
	assert "BP Water Heaters LLC" not in template
	assert "same week" not in template.lower()
	assert "same-week" not in template.lower()
	assert "usually" not in template.lower()
	assert "C-31" in template
	assert "C-1 plumbing" not in template
	assert 'class="nav' in template
	assert 'class="hero' in template
	assert 'class="trust' in template
	assert 'class="services-grid"' in template
	assert 'class="booking__panel' in template
	assert 'class="coverage' in template
	assert 'class="faq__list' in template
	assert "/assets/bp_water_heaters/js/bpwh_public.js" in template
	assert "/assets/bp_water_heaters/css/bpwh_design.css" in template
	assert ".reveal.is-visible" in css
	assert "prefers-reduced-motion" in css
	assert 'class="bpwh-public' not in template


def test_public_site_preserves_booking_and_customer_action_hooks():
	template = _public_site_template()

	required_hooks = [
		'id="bpwh-booking-form"',
		'id="bpwh-booking-status"',
		'name="preferred_start"',
		'name="customer_name"',
		'name="email"',
		'name="phone"',
		'name="property_address"',
		'name="city"',
		'name="county"',
		'name="state"',
		'name="postal_code"',
		'name="notes"',
		'id="bpwh-contact-form"',
		'id="bpwh-contact-status"',
		'id="bpwh-portal-form"',
		'id="bpwh-portal-status"',
		'id="bpwh-chat-form"',
		'id="bpwh-chat-status"',
		"/assets/bp_water_heaters/js/bpwh_booking.js",
	]
	for hook in required_hooks:
		assert hook in template

	assert 'id="booking-form"' not in template
	assert 'name="customer_phone"' not in template
	assert 'name="service_address"' not in template


def test_public_site_requests_flexible_preferred_time_without_checkout():
	template = _public_site_template()

	assert 'id="bpwh-slot-buttons"' not in template
	assert 'select id="bpwh-preferred-start"' not in template
	assert 'type="datetime-local"' in template
	assert 'id="bpwh-preferred-start" name="preferred_start"' in template
	assert "Preferred date and time" in template
	assert "Submit booking request" in template
	assert "Collected on-site or after the diagnostic" in template
	assert "Continue to checkout - $85" not in template
	assert "Stripe-secured checkout" not in template
	assert "Reserve this slot" not in template


def test_public_site_promotes_free_install_sweepstakes_without_purchase_requirement():
	template = _public_site_template()

	assert 'href="/bpwaterheaters-giveaway"' in template
	assert "Free install sweepstakes" in template
	assert "No purchase necessary" in template
	assert "Purchase does not increase odds" in template
	assert "Up to two entries per household" in template
	assert "must purchase" not in template.lower()
	assert "purchase required" not in template.lower()


def test_giveaway_landing_page_has_entry_hooks_and_official_language():
	template = _giveaway_template()

	required_hooks = [
		'id="bpwh-giveaway-entry-form"',
		'id="bpwh-giveaway-status"',
		'name="full_name"',
		'name="email"',
		'name="phone"',
		'name="property_address"',
		'name="city"',
		'name="state"',
		'name="postal_code"',
		'name="homeowner_authorized"',
		'name="marketing_opt_in"',
		"/assets/bp_water_heaters/js/bpwh_booking.js",
	]
	for hook in required_hooks:
		assert hook in template

	assert "No purchase necessary" in template
	assert "Purchase does not increase odds" in template
	assert "Up to two entries per household" in template
	assert "free bonus entry" in template.lower()
	assert "/bpwaterheaters-giveaway-rules" in template
	assert "40-50 gallon" in template
	assert "$3,000" in template
	assert "void where prohibited" in template.lower()
	assert "promo attorney" in template.lower()


def test_giveaway_rules_page_has_required_sweepstakes_terms():
	template = _giveaway_rules_template()

	required_terms = [
		"No purchase necessary",
		"Purchase does not increase odds",
		"Up to two entries per household",
		"Free online entry",
		"Free bonus entry",
		"$125 water heater flush",
		"40-50 gallon",
		"$3,000",
		"Winner selection",
		"Odds",
		"Taxes",
		"Void where prohibited",
		"promo attorney",
	]
	for term in required_terms:
		assert term in template


def test_admin_template_has_giveaway_management_hooks():
	template = _admin_template()

	assert 'id="bpwh-admin-giveaway-entries"' in template
	assert 'id="bpwh-giveaway-export"' in template
	assert "Sweepstakes entries" in template


def test_portal_host_branch_still_uses_shared_portal_template():
	template = _public_site_template()

	assert "{% if is_portal_root %}" in template
	assert 'bp_water_heaters/templates/includes/bpwh_portal_content.html' in template
