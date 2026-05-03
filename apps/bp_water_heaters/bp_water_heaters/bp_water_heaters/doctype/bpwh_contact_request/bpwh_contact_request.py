from frappe.model.document import Document


class BPWHContactRequest(Document):
	def validate(self):
		if self.email:
			self.email = self.email.strip().lower()
