import frappe
from frappe import _
from frappe.model.document import Document

from bp_water_heaters.giveaway import (
	GIVEAWAY_BONUS_KIND,
	GIVEAWAY_CAMPAIGN_NAME,
	GIVEAWAY_DUPLICATE_STATUS,
	GIVEAWAY_FREE_BONUS_ENTRY,
	GIVEAWAY_PAID_ENTRY,
	GIVEAWAY_STANDARD_KIND,
	normalize_household_key,
)


class BPWHGiveawayEntry(Document):
	def validate(self):
		if not self.campaign_name:
			self.campaign_name = GIVEAWAY_CAMPAIGN_NAME
		if not self.entry_kind:
			self.entry_kind = (
				GIVEAWAY_BONUS_KIND if self.entry_source in {GIVEAWAY_FREE_BONUS_ENTRY, GIVEAWAY_PAID_ENTRY} else GIVEAWAY_STANDARD_KIND
			)
		if self.email:
			self.email = self.email.strip().lower()
		if self.state:
			self.state = self.state.strip().upper()
		if self.property_address and self.city and self.state and self.postal_code:
			self.household_key = normalize_household_key(
				self.property_address,
				self.city,
				self.state,
				self.postal_code,
			)
		if self.household_key and self.status not in {GIVEAWAY_DUPLICATE_STATUS, "Cancelled"}:
			duplicate = frappe.get_all(
				"BPWH Giveaway Entry",
				filters={
					"campaign_name": self.campaign_name,
					"household_key": self.household_key,
					"entry_kind": self.entry_kind,
					"status": ["not in", [GIVEAWAY_DUPLICATE_STATUS, "Cancelled"]],
					"name": ["!=", self.name],
				},
				fields=["name"],
				limit_page_length=1,
			)
			if duplicate:
				frappe.throw(_("This household already has a {0} entry for the giveaway.").format(self.entry_kind.lower()))
