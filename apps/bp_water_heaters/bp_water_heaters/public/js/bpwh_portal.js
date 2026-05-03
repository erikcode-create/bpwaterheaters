(function () {
	const app = document.getElementById("bpwh-portal-app");
	const intro = document.getElementById("bpwh-portal-intro");
	const params = new URLSearchParams(window.location.search);
	const token = params.get("token");

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
				</article>
			`),
		].join("");
		for (const button of app.querySelectorAll(".bpwh-inline-pay")) {
			button.addEventListener("click", () => payInvoice(button.dataset.invoice));
		}
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
