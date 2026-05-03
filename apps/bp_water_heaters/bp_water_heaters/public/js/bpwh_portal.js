(function () {
	const app = document.getElementById("bpwh-portal-app");
	const intro = document.getElementById("bpwh-portal-intro");
	const params = new URLSearchParams(window.location.search);
	const token = params.get("token");

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

	function escapeHtml(value) {
		return String(value || "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function renderList(title, rows, formatter) {
		const items = rows.length
			? rows.map(formatter).join("")
			: "<p class='bpwh-empty'>Nothing here yet.</p>";
		return `<section class="bpwh-portal-panel"><h2>${title}</h2>${items}</section>`;
	}

	function render(data) {
		intro.textContent = `Signed in by secure link for ${data.email}.`;
		app.innerHTML = [
			renderList("Bookings", data.bookings, (booking) => `
				<article>
					<strong>${escapeHtml(booking.service_type)} ${escapeHtml(booking.name)}</strong>
					<span>${escapeHtml(booking.status)} · ${escapeHtml(booking.preferred_start || "")}</span>
					<p>${escapeHtml(booking.property_address)}, ${escapeHtml(booking.city)}, ${escapeHtml(booking.state)} ${escapeHtml(booking.postal_code)}</p>
				</article>
			`),
			renderList("Jobs", data.projects, (project) => `
				<article>
					<strong>${escapeHtml(project.project_name)}</strong>
					<span>${escapeHtml(project.status)} · ${escapeHtml(project.percent_complete || 0)}%</span>
				</article>
			`),
			renderList("Invoices", data.invoices, (invoice) => `
				<article>
					<strong>${escapeHtml(invoice.name)}</strong>
					<span>${escapeHtml(invoice.status)} · $${Number(invoice.grand_total || 0).toFixed(2)} · outstanding $${Number(invoice.outstanding_amount || 0).toFixed(2)}</span>
					<button class="bpwh-inline-pay" data-invoice="${escapeHtml(invoice.name)}">Pay invoice</button>
				</article>
			`),
			renderList("Chat", data.conversations, (conversation) => `
				<article>
					<strong>${escapeHtml(conversation.subject)}</strong>
					<span>${escapeHtml(conversation.status)} · ${escapeHtml(conversation.last_message_at || "")}</span>
					<button class="bpwh-inline-pay" data-conversation="${escapeHtml(conversation.name)}">Open chat</button>
				</article>
			`),
			`<section class="bpwh-portal-panel bpwh-portal-panel--wide">
				<h2>Send a message</h2>
				<form class="bpwh-portal-chat-form" id="bpwh-new-chat-form">
					<textarea name="message" rows="4" placeholder="Write a message to BP Water Heaters" required></textarea>
					<button class="bpwh-inline-pay" type="submit">Send chat message</button>
				</form>
			</section>`,
		].join("");
		for (const button of app.querySelectorAll(".bpwh-inline-pay")) {
			if (button.dataset.invoice) {
				button.addEventListener("click", () => payInvoice(button.dataset.invoice));
			}
			if (button.dataset.conversation) {
				button.addEventListener("click", () => openConversation(button.dataset.conversation));
			}
		}
		document.getElementById("bpwh-new-chat-form")?.addEventListener("submit", sendNewPortalMessage);
	}

	async function payInvoice(invoice) {
		const result = await call("bp_water_heaters.api.portal.create_invoice_checkout", {
			token,
			sales_invoice: invoice,
		});
		if (result.url) {
			window.location.href = result.url;
		}
	}

	async function openConversation(conversation) {
		app.innerHTML = "<p class='bpwh-empty'>Loading chat.</p>";
		try {
			const result = await call("bp_water_heaters.api.chat.get_portal_messages", { token, conversation });
			renderConversation(result);
		} catch (error) {
			app.innerHTML = "<p class='bpwh-empty'>That chat could not be opened.</p>";
		}
	}

	function renderConversation(result) {
		const messages = result.messages.length
			? result.messages.map((message) => `
				<article class="bpwh-chat-message bpwh-chat-message--${message.sender_type === "Admin" ? "admin" : "customer"}">
					<strong>${escapeHtml(message.sender_type)}</strong>
					<p>${escapeHtml(message.message)}</p>
					<span>${escapeHtml(message.posted_at || "")}</span>
				</article>
			`).join("")
			: "<p class='bpwh-empty'>No messages yet.</p>";
		app.innerHTML = `
			<section class="bpwh-portal-panel bpwh-portal-panel--wide">
				<button class="bpwh-inline-pay" id="bpwh-chat-back" type="button">Back to portal</button>
				<h2>Chat ${escapeHtml(result.conversation)}</h2>
				<div class="bpwh-chat-thread">${messages}</div>
				<form class="bpwh-portal-chat-form" id="bpwh-chat-reply-form" data-conversation="${escapeHtml(result.conversation)}">
					<textarea name="message" rows="4" placeholder="Reply to BP Water Heaters" required></textarea>
					<button class="bpwh-inline-pay" type="submit">Send reply</button>
				</form>
			</section>`;
		document.getElementById("bpwh-chat-back").addEventListener("click", load);
		document.getElementById("bpwh-chat-reply-form").addEventListener("submit", sendPortalReply);
	}

	async function sendNewPortalMessage(event) {
		event.preventDefault();
		const form = event.currentTarget;
		const message = form.elements.message.value.trim();
		if (!message) return;
		form.querySelector("button").disabled = true;
		try {
			const result = await call("bp_water_heaters.api.chat.start_portal_chat", {
				token,
				message,
			});
			openConversation(result.conversation);
		} catch (error) {
			form.querySelector("button").disabled = false;
			alert("Could not send that message yet.");
		}
	}

	async function sendPortalReply(event) {
		event.preventDefault();
		const form = event.currentTarget;
		const conversation = form.dataset.conversation;
		const message = form.elements.message.value.trim();
		if (!message) return;
		form.querySelector("button").disabled = true;
		try {
			await call("bp_water_heaters.api.chat.send_portal_message", { token, conversation, message });
			openConversation(conversation);
		} catch (error) {
			form.querySelector("button").disabled = false;
			alert("Could not send that reply yet.");
		}
	}

	async function load() {
		if (!token) {
			app.innerHTML = "<p class='bpwh-empty'>This portal link is missing a secure token.</p>";
			return;
		}
		try {
			render(await call("bp_water_heaters.api.portal.get_portal_data", { token }));
		} catch (error) {
			app.innerHTML = "<p class='bpwh-empty'>This portal link is invalid or expired.</p>";
		}
	}

	load();
})();
