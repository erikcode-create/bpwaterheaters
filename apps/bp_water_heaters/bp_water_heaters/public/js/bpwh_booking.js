(function () {
	const bookingForm = document.getElementById("bpwh-booking-form");
	const contactForm = document.getElementById("bpwh-contact-form");
	const portalForm = document.getElementById("bpwh-portal-form");
	const chatForm = document.getElementById("bpwh-chat-form");
	const slotSelect = bookingForm && bookingForm.querySelector("select[name='preferred_start']");
	const slotButtons = document.getElementById("bpwh-slot-buttons");
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

	function renderSlotButtons(slots) {
		if (!slotButtons || !slotSelect) return;
		slotButtons.innerHTML = "";
		for (const slot of slots) {
			const button = document.createElement("button");
			button.type = "button";
			button.className = "slot";
			button.dataset.value = slot.start;
			button.append(document.createTextNode(slot.label));
			const meta = document.createElement("small");
			meta.textContent = "available";
			button.append(meta);
			button.addEventListener("click", () => {
				slotSelect.value = slot.start;
				slotButtons.querySelectorAll(".slot").forEach((item) => item.setAttribute("aria-pressed", "false"));
				button.setAttribute("aria-pressed", "true");
			});
			button.setAttribute("aria-pressed", "false");
			slotButtons.append(button);
		}
	}

	async function loadSlots() {
		if (!slotSelect) return;
		try {
			const data = await call("bp_water_heaters.api.booking.get_available_slots");
			const slots = Array.isArray(data.slots) ? data.slots : [];
			slotSelect.innerHTML = "";
			if (slotButtons) slotButtons.innerHTML = "";
			if (!slots.length) {
				slotSelect.innerHTML = "<option value=''>No online slots are open right now</option>";
				return;
			}
			slotSelect.append(new Option("Choose an appointment time", ""));
			for (const slot of slots) {
				slotSelect.append(new Option(slot.label, slot.start));
			}
			renderSlotButtons(slots);
		} catch (error) {
			slotSelect.innerHTML = "<option value=''>Unable to load slots</option>";
			if (slotButtons) slotButtons.innerHTML = "";
			showStatus(bookingStatus, "We could not load online appointment times. Please call 775-815-9875.");
		}
	}

	async function submitBooking(event) {
		event.preventDefault();
		const formData = new FormData(bookingForm);
		const payload = Object.fromEntries(formData.entries());
		const button = bookingForm.querySelector("button[type='submit']");
		const defaultText = button.dataset.defaultText || button.textContent;
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
