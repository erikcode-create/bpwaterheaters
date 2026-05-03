(function () {
	const bookingForm = document.getElementById("bpwh-booking-form");
	const contactForm = document.getElementById("bpwh-contact-form");
	const portalForm = document.getElementById("bpwh-portal-form");
	const chatForm = document.getElementById("bpwh-chat-form");
	const slotSelect = bookingForm && bookingForm.querySelector("select[name='preferred_start']");
	const bookingStatus = document.getElementById("bpwh-booking-status");
	const contactStatus = document.getElementById("bpwh-contact-status");
	const portalStatus = document.getElementById("bpwh-portal-status");
	const chatStatus = document.getElementById("bpwh-chat-status");

	function showStatus(element, message) {
		if (!element) return;
		element.textContent = message;
		element.classList.add("is-visible");
	}

	async function call(method, payload) {
		const response = await fetch(`/api/method/${method}`, {
			method: payload ? "POST" : "GET",
			headers: payload ? { "Content-Type": "application/json" } : undefined,
			body: payload ? JSON.stringify(payload) : undefined,
		});
		const data = await response.json();
		if (!response.ok || data.exc) {
			throw new Error(data._server_messages || data.message || "Request failed");
		}
		return data.message;
	}

	async function loadSlots() {
		if (!slotSelect) return;
		try {
			const data = await call("bp_water_heaters.api.booking.get_available_slots");
			slotSelect.innerHTML = "";
			if (!data.slots.length) {
				slotSelect.innerHTML = "<option value=''>No online slots are open right now</option>";
				return;
			}
			slotSelect.append(new Option("Choose an appointment time", ""));
			for (const slot of data.slots) {
				slotSelect.append(new Option(slot.label, slot.start));
			}
		} catch (error) {
			slotSelect.innerHTML = "<option value=''>Unable to load slots</option>";
			showStatus(bookingStatus, "We could not load online appointment times. Please call 775-815-9875.");
		}
	}

	async function submitBooking(event) {
		event.preventDefault();
		const formData = new FormData(bookingForm);
		const payload = Object.fromEntries(formData.entries());
		const button = bookingForm.querySelector("button[type='submit']");
		button.disabled = true;
		button.textContent = "Holding slot...";
		try {
			const result = await call("bp_water_heaters.api.booking.create_booking_hold", payload);
			if (result.checkout && result.checkout.url) {
				window.location.href = result.checkout.url;
				return;
			}
			showStatus(
				bookingStatus,
				`Your slot is held as ${result.booking}. Stripe checkout is being connected; call 775-815-9875 to finish payment.`
			);
			await loadSlots();
		} catch (error) {
			showStatus(bookingStatus, "That booking could not be created. Please check the form or call 775-815-9875.");
		} finally {
			button.disabled = false;
			button.textContent = "Hold slot and pay $85";
		}
	}

	async function submitContact(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(contactForm).entries());
		const button = contactForm.querySelector("button[type='submit']");
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
			button.textContent = "Send message";
		}
	}

	async function submitPortalRequest(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(portalForm).entries());
		const button = portalForm.querySelector("button[type='submit']");
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
			button.textContent = "Send secure link";
		}
	}

	async function submitChat(event) {
		event.preventDefault();
		const payload = Object.fromEntries(new FormData(chatForm).entries());
		const button = chatForm.querySelector("button[type='submit']");
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
			button.textContent = "Send chat";
		}
	}

	if (bookingForm) {
		bookingForm.addEventListener("submit", submitBooking);
		loadSlots();
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
})();
