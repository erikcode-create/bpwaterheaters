from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SITE_TEMPLATE = APP_ROOT / "www" / "bpwaterheaters.html"
PUBLIC_CSS = APP_ROOT / "public" / "css" / "bpwh.css"
PUBLIC_DESIGN_CSS = APP_ROOT / "public" / "css" / "bpwh_design.css"


def _public_site_template():
	return PUBLIC_SITE_TEMPLATE.read_text()


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
		'id="bpwh-slot-buttons"',
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


def test_portal_host_branch_still_uses_shared_portal_template():
	template = _public_site_template()

	assert "{% if is_portal_root %}" in template
	assert 'bp_water_heaters/templates/includes/bpwh_portal_content.html' in template
