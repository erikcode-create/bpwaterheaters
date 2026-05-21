(function () {
	const bookingForm = document.getElementById("bpwh-booking-form");
	const contactForm = document.getElementById("bpwh-contact-form");
	const portalForm = document.getElementById("bpwh-portal-form");
	const chatForm = document.getElementById("bpwh-chat-form");
	const giveawayForm = document.getElementById("bpwh-giveaway-entry-form");
	const preferredStartInput = bookingForm && bookingForm.querySelector("input[name='preferred_start']");
	const bookingStatus = document.getElementById("bpwh-booking-status");
	const contactStatus = document.getElementById("bpwh-contact-status");
	const portalStatus = document.getElementById("bpwh-portal-status");
	const chatStatus = document.getElementById("bpwh-chat-status");
	const giveawayStatus = document.getElementById("bpwh-giveaway-status");

	function showStatus(element, message) {
		if (!element) return;
		element.textContent = message;
		element.classList.add("is-visible");
	}

	async function call(method, payload) {
		const headers = {};
		if (payload) headers["Content-Type"] = "application/json";
		if (window.frappe?.csrf_token) headers["X-Frappe-CSRF-Token"] = window.frappe.csrf_token;
		const response = await fetch(`/api/method/${method}`, {
			method: payload ? "POST" : "GET",
			headers: Object.keys(headers).length ? headers : undefined,
			body: payload ? JSON.stringify(payload) : undefined,
		});
		const data = await response.json();
		if (!response.ok || data.exc) {
			throw new Error(data._server_messages || data.message || "Request failed");
		}
		return data.message;
	}

	function localDateTimeValue(date) {
		const pad = (value) => String(value).padStart(2, "0");
		return [
			date.getFullYear(),
			pad(date.getMonth() + 1),
			pad(date.getDate()),
		].join("-") + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
	}

	function setPreferredStartMinimum() {
		if (!preferredStartInput) return;
		preferredStartInput.min = localDateTimeValue(new Date());
	}

	async function submitBooking(event) {
		event.preventDefault();
		const formData = new FormData(bookingForm);
		const payload = Object.fromEntries(formData.entries());
		const button = bookingForm.querySelector("button[type='submit']");
		const defaultText = button.dataset.defaultText || button.textContent;
		button.disabled = true;
		button.textContent = "Sending request...";
		try {
			const result = await call("bp_water_heaters.api.booking.create_booking_request", payload);
			showStatus(
				bookingStatus,
				`Request received as ${result.booking}. BP Water Heaters will text to confirm the final arrival window. The $85 diagnostic fee is collected on-site or after diagnosis.`
			);
			bookingForm.reset();
			setPreferredStartMinimum();
		} catch (error) {
			showStatus(bookingStatus, "That booking could not be created. Please check the form or call 775-815-9875.");
		} finally {
			button.disabled = false;
			button.textContent = defaultText;
		}
	}

	async function submitContact(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(contactForm).entries());
		const button = contactForm.querySelector("button[type='submit']");
		const defaultText = button.dataset.defaultText || button.textContent;
		button.disabled = true;
		button.textContent = "Sending...";
		try {
			const result = await call("bp_water_heaters.api.booking.submit_contact_request", payload);
			showStatus(contactStatus, `Message received as ${result.name}. BP Water Heaters will follow up.`);
			contactForm.reset();
		} catch (error) {
			showStatus(contactStatus, "Message could not be sent. Please call 775-815-9875.");
		} finally {
			button.disabled = false;
			button.textContent = defaultText;
		}
	}

	async function submitPortalRequest(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(portalForm).entries());
		const button = portalForm.querySelector("button[type='submit']");
		const defaultText = button.dataset.defaultText || button.textContent;
		button.disabled = true;
		button.textContent = "Sending...";
		try {
			await call("bp_water_heaters.api.portal.request_magic_link", payload);
			showStatus(portalStatus, "If that email has BP Water Heaters activity, a secure portal link is on the way.");
			portalForm.reset();
		} catch (error) {
			showStatus(portalStatus, "Portal link could not be sent. Please call 775-815-9875.");
		} finally {
			button.disabled = false;
			button.textContent = defaultText;
		}
	}

	async function submitChat(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(chatForm).entries());
		const button = chatForm.querySelector("button[type='submit']");
		const defaultText = button.dataset.defaultText || button.textContent;
		button.disabled = true;
		button.textContent = "Sending...";
		try {
			const result = await call("bp_water_heaters.api.chat.start_public_chat", payload);
			showStatus(chatStatus, `Chat started as ${result.conversation}. BP Water Heaters will reply here and by email.`);
			chatForm.reset();
		} catch (error) {
			showStatus(chatStatus, "Chat could not be started. Please call 775-815-9875.");
		} finally {
			button.disabled = false;
			button.textContent = defaultText;
		}
	}

	async function submitGiveawayEntry(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(giveawayForm).entries());
		payload.is_adult = giveawayForm.elements.is_adult.checked ? "1" : "";
		payload.homeowner_authorized = giveawayForm.elements.homeowner_authorized.checked ? "1" : "";
		payload.marketing_opt_in = giveawayForm.elements.marketing_opt_in.checked ? "1" : "";
		const button = giveawayForm.querySelector("button[type='submit']");
		const defaultText = button.dataset.defaultText || button.textContent;
		button.disabled = true;
		button.textContent = "Submitting...";
		try {
			const result = await call("bp_water_heaters.api.giveaway.submit_free_entry", payload);
			const entryKind = result.entry_kind ? `${result.entry_kind.toLowerCase()} ` : "";
			showStatus(giveawayStatus, `Your ${entryKind}entry was received as ${result.name}. No purchase was required and purchase does not increase odds.`);
			giveawayForm.reset();
		} catch (error) {
			showStatus(giveawayStatus, "That entry could not be submitted. Please check the form or call 775-815-9875.");
		} finally {
			button.disabled = false;
			button.textContent = defaultText;
		}
	}

	if (bookingForm) {
		bookingForm.addEventListener("submit", submitBooking);
		setPreferredStartMinimum();
	}
	if (contactForm) {
		contactForm.addEventListener("submit", submitContact);
	}
	if (portalForm) {
		portalForm.addEventListener("submit", submitPortalRequest);
	}
	if (chatForm) {
		chatForm.addEventListener("submit", submitChat);
	}
	if (giveawayForm) {
		giveawayForm.addEventListener("submit", submitGiveawayEntry);
	}
})();
