from datetime import timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime


class BPWHBooking(Document):
	def validate(self):
		if self.preferred_start and not self.preferred_end:
			self.preferred_end = get_datetime(self.preferred_start) + timedelta(hours=1)
		if not self.callout_fee:
			self.callout_fee = 85
		if self.status == "Pending Payment" and not self.hold_expires_at:
			self.hold_expires_at = add_to_date(now_datetime(), minutes=15)
		if self.email:
			self.email = self.email.strip().lower()
		if self.state:
			self.state = self.state.strip().upper()

	def before_save(self):
		if self.status == "Pending Payment" and self.hold_expires_at:
			if get_datetime(self.hold_expires_at) <= now_datetime():
				self.status = "Expired"
