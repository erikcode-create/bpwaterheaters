from __future__ import annotations

from datetime import datetime

from bp_water_heaters.giveaway import (
	GIVEAWAY_BONUS_KIND,
	GIVEAWAY_FREE_BONUS_ENTRY,
	campaign_status,
	eligible_entries_to_csv,
	next_free_entry_award,
	normalize_household_key,
)


def test_giveaway_campaign_window_tracks_open_closed_and_config_needed():
	assert campaign_status(now=datetime(2026, 6, 1, 9), start_at=None, end_at=None)["state"] == "not_configured"
	assert (
		campaign_status(
			now=datetime(2026, 6, 1, 9),
			start_at=datetime(2026, 6, 2, 0),
			end_at=datetime(2026, 7, 2, 23, 59),
		)["state"]
		== "scheduled"
	)
	assert (
		campaign_status(
			now=datetime(2026, 6, 10, 9),
			start_at=datetime(2026, 6, 2, 0),
			end_at=datetime(2026, 7, 2, 23, 59),
		)["state"]
		== "open"
	)
	assert (
		campaign_status(
			now=datetime(2026, 7, 3, 0),
			start_at=datetime(2026, 6, 2, 0),
			end_at=datetime(2026, 7, 2, 23, 59),
		)["state"]
		== "closed"
	)


def test_household_key_normalizes_service_address_for_duplicate_limit():
	first = normalize_household_key(" 123 Main St. ", "Reno", "nv", "89501-1234")
	second = normalize_household_key("123 MAIN STREET", "reno", "NV", "89501")

	assert first == second
	assert first == "123-main-street|reno|nv|89501"


def test_free_entry_awards_standard_then_free_bonus_for_same_household():
	first = next_free_entry_award([])
	second = next_free_entry_award([first["entry_kind"]])

	assert first == {"entry_source": "Free Online Entry", "entry_kind": "Standard"}
	assert second == {"entry_source": GIVEAWAY_FREE_BONUS_ENTRY, "entry_kind": GIVEAWAY_BONUS_KIND}


def test_free_entry_rejects_household_after_standard_and_bonus_entries():
	try:
		next_free_entry_award(["Standard", "Bonus"])
	except ValueError as exc:
		assert "maximum" in str(exc).lower()
	else:
		raise AssertionError("Expected max-entry household to be rejected")


def test_eligible_entries_export_as_csv_for_manual_spreadsheet_draw():
	csv_text = eligible_entries_to_csv(
		[
			{
				"name": "BPWH-GIVE-2026-00002",
				"full_name": "Ada Lovelace",
				"email": "ada@example.com",
				"phone": "775-555-0102",
				"property_address": "123 Main St",
				"city": "Reno",
				"state": "NV",
				"postal_code": "89501",
				"entry_source": "Free Online Entry",
				"entry_kind": "Standard",
				"status": "Eligible",
			}
		]
	)

	assert csv_text.splitlines()[0] == (
		"name,full_name,email,phone,property_address,city,state,postal_code,entry_source,entry_kind,status"
	)
	assert "BPWH-GIVE-2026-00002,Ada Lovelace,ada@example.com" in csv_text
