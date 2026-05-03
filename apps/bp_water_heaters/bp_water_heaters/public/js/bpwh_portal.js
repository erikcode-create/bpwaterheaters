(function () {
	const app = document.getElementById("bpwh-portal-app");
	const intro = document.getElementById("bpwh-portal-intro");
	const status = document.getElementById("bpwh-portal-status");
	const params = new URLSearchParams(window.location.search);
	const token = params.get("token");
	const paymentReturn = params.get("payment");
	let portalData = null;
	let activeConversation = null;
	let activeMessages = [];

	const moneyFormatter = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });
	const percentFormatter = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 0 });
	const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
		month: "short",
		day: "numeric",
		year: "numeric",
		hour: "numeric",
		minute: "2-digit",
	});
	const dateFormatter = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });

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

	function formatMoney(value) {
		return moneyFormatter.format(Number(value || 0));
	}

	function formatPercent(value) {
		return percentFormatter.format(Number(value || 0) / 100);
	}

	function parseDate(value) {
		if (!value) return null;
		const normalized = String(value).replace(" ", "T");
		const parsed = new Date(normalized);
		return Number.isNaN(parsed.getTime()) ? null : parsed;
	}

	function formatDateTime(value) {
		const parsed = parseDate(value);
		return parsed ? dateTimeFormatter.format(parsed) : value || "";
	}

	function formatDate(value) {
		const parsed = parseDate(value);
		return parsed ? dateFormatter.format(parsed) : value || "";
	}

	function renderTime(value, mode) {
		if (!value) return "";
		const label = mode === "date" ? formatDate(value) : formatDateTime(value);
		return `<time datetime="${escapeHtml(value)}">${escapeHtml(label)}</time>`;
	}

	function setBusy(isBusy) {
		app.setAttribute("aria-busy", isBusy ? "true" : "false");
	}

	function setStatus(message, tone) {
		status.textContent = message || "";
		status.className = `bpwh-portal-status${message ? " is-visible" : ""}${tone ? ` is-${tone}` : ""}`;
	}

	function focusFirstHeading() {
		const heading = activeConversation
			? document.getElementById("chat-panel-title")
			: app.querySelector("[data-focus-heading]");
		if (heading) {
			heading.setAttribute("tabindex", "-1");
			heading.focus({ preventScroll: true });
		}
	}

	function statusClass(value) {
		return String(value || "Open").toLowerCase().replace(/[^a-z0-9]+/g, "-");
	}

	function renderChip(value, label) {
		if (!value) return "";
		return `<span class="bpwh-status-chip bpwh-status-chip--${statusClass(value)}">${escapeHtml(label || value)}</span>`;
	}

	function actionCopy(action) {
		if (!action) return "Your service details are ready.";
		if (action.kind === "payment_due") return `Payment due: ${formatMoney(action.amount)}.`;
		if (action.kind === "appointment") return `Appointment scheduled for ${formatDateTime(action.starts_at)}.`;
		if (action.kind === "message") return "You have an open message thread with BP Water Heaters.";
		return "You are all set right now.";
	}

	function renderReturnBanner() {
		if (paymentReturn === "success") {
			return `
				<section class="bpwh-next-action bpwh-next-action--success" aria-labelledby="payment-return-title">
					<p class="bpwh-kicker">Payment update</p>
					<h2 id="payment-return-title">Payment return received.</h2>
					<p>Invoice status can take a moment to refresh after Stripe confirms the payment.</p>
				</section>`;
		}
		if (paymentReturn === "cancelled") {
			return `
				<section class="bpwh-next-action bpwh-next-action--warning" aria-labelledby="payment-return-title">
					<p class="bpwh-kicker">Payment paused</p>
					<h2 id="payment-return-title">Checkout was not completed.</h2>
					<p>You can restart payment from the invoice action below or call BP Water Heaters.</p>
				</section>`;
		}
		return "";
	}

	function renderNextAction(summary) {
		const action = summary?.next_action || { kind: "all_set" };
		return `
			<section class="bpwh-next-action bpwh-next-action--${statusClass(action.kind)}" aria-labelledby="next-action-title">
				<div>
					<p class="bpwh-kicker">Next action</p>
					<h2 id="next-action-title">${escapeHtml(action.label || "Service Status")}</h2>
					<p>${escapeHtml(actionCopy(action))}</p>
				</div>
				<div class="bpwh-next-action__meta">
					${renderChip(action.label || "All Set")}
					<a class="bpwh-text-link" href="tel:+17758159875">Call 775-815-9875</a>
				</div>
			</section>`;
	}

	function renderActiveService(record) {
		if (!record) {
			return `
				<section class="bpwh-portal-panel bpwh-portal-panel--wide" aria-labelledby="active-service-title">
					<h2 id="active-service-title" data-focus-heading>Your Service Portal</h2>
					<p class="bpwh-empty">No bookings, invoices, jobs, or messages are tied to this secure link yet.</p>
				</section>`;
		}
		const booking = record.booking || {};
		const project = record.project || {};
		const invoice = record.primary_invoice || null;
		const conversation = record.primary_conversation || null;
		return `
			<section class="bpwh-portal-panel bpwh-service-card" aria-labelledby="active-service-title">
				<div class="bpwh-panel-heading">
					<div>
						<p class="bpwh-kicker">Active service</p>
						<h2 id="active-service-title" data-focus-heading>${escapeHtml(record.title || "Service Details")}</h2>
					</div>
					${renderChip(booking.status || project.status || record.next_action?.label)}
				</div>
				<div class="bpwh-service-card__body">
					${renderServiceDetail("Appointment", renderTime(booking.preferred_start))}
					${renderServiceDetail("Address", formatAddress(booking))}
					${renderServiceDetail("Job", project.project_name ? `${escapeHtml(project.project_name)} ${renderChip(project.status)}` : "")}
					${renderServiceDetail("Progress", project.percent_complete != null ? formatPercent(project.percent_complete) : "")}
					${renderInvoiceSummary(invoice)}
					${renderServiceDetail("Messages", conversation ? `${escapeHtml(conversation.subject || conversation.name)} ${renderChip(conversation.status)}` : "No messages yet.")}
				</div>
			</section>
			${renderActionRail(record)}`;
	}

	function renderServiceDetail(label, value) {
		if (!value) return "";
		return `
			<div class="bpwh-service-detail">
				<span>${escapeHtml(label)}</span>
				<strong>${value}</strong>
			</div>`;
	}

	function formatAddress(booking) {
		const parts = [booking.property_address, booking.city, booking.state, booking.postal_code].filter(Boolean);
		return parts.length ? escapeHtml(parts.join(", ")) : "";
	}

	function renderInvoiceSummary(invoice) {
		if (!invoice) return "";
		const outstanding = Number(invoice.outstanding_amount || 0);
		const text = outstanding > 0
			? `${escapeHtml(invoice.name)} has ${formatMoney(outstanding)} outstanding.`
			: `${escapeHtml(invoice.name)} is ${escapeHtml(invoice.status || "current")}.`;
		return renderServiceDetail("Invoice", `${text} ${renderChip(invoice.status)}`);
	}

	function renderActionRail(record) {
		const payableInvoice = (record.invoices || []).find((invoice) => invoice.is_payable);
		const conversation = record.primary_conversation;
		return `
			<aside class="bpwh-portal-panel bpwh-action-rail" aria-labelledby="action-rail-title">
				<h2 id="action-rail-title">Actions</h2>
				${payableInvoice ? renderPayButton(payableInvoice, "bpwh-action-button") : "<p class='bpwh-empty'>No open invoice balance.</p>"}
				${conversation ? `<button class="bpwh-action-button bpwh-action-button--secondary" type="button" data-conversation="${escapeHtml(conversation.name)}">Open Messages</button>` : ""}
				<button class="bpwh-action-button bpwh-action-button--secondary" type="button" data-new-message>Message BP Water Heaters</button>
				<a class="bpwh-action-button bpwh-action-button--ghost" href="tel:+17758159875">Call 775-815-9875</a>
			</aside>`;
	}

	function renderPayButton(invoice, className) {
		return `<button class="${className || "bpwh-inline-pay"}" type="button" data-invoice="${escapeHtml(invoice.name)}">Pay ${formatMoney(invoice.outstanding_amount)}</button>`;
	}

	function renderHistory(data) {
		return `
			<section class="bpwh-portal-panel" aria-labelledby="booking-history-title">
				<h2 id="booking-history-title">Bookings</h2>
				${renderRows(data.bookings, renderBookingRow, "No scheduled bookings yet.")}
			</section>
			<section class="bpwh-portal-panel" aria-labelledby="invoice-history-title">
				<h2 id="invoice-history-title">Invoices</h2>
				${renderRows(data.invoices, renderInvoiceRow, "No invoices yet.")}
			</section>
			<section class="bpwh-portal-panel bpwh-portal-panel--wide" aria-labelledby="message-history-title">
				<h2 id="message-history-title">Messages</h2>
				${renderRows(data.conversations, renderConversationRow, "No messages yet.")}
				${renderNewMessageForm()}
			</section>`;
	}

	function renderRows(rows, formatter, emptyText) {
		return rows && rows.length ? rows.map(formatter).join("") : `<p class="bpwh-empty">${escapeHtml(emptyText)}</p>`;
	}

	function renderBookingRow(booking) {
		return `
			<article class="bpwh-history-row">
				<div>
					<strong>${escapeHtml(booking.service_type || booking.name)}</strong>
					<span>${renderChip(booking.status)} ${renderTime(booking.preferred_start)}</span>
					<p>${formatAddress(booking)}</p>
				</div>
			</article>`;
	}

	function renderInvoiceRow(invoice) {
		return `
			<article class="bpwh-history-row">
				<div>
					<strong>${escapeHtml(invoice.name)}</strong>
					<span>${renderChip(invoice.status)} Total ${formatMoney(invoice.grand_total)} · Outstanding ${formatMoney(invoice.outstanding_amount)}</span>
					${invoice.posting_date ? `<p>Posted ${renderTime(invoice.posting_date, "date")}</p>` : ""}
				</div>
				${invoice.is_payable ? renderPayButton(invoice) : ""}
			</article>`;
	}

	function renderConversationRow(conversation) {
		return `
			<article class="bpwh-history-row">
				<div>
					<strong>${escapeHtml(conversation.subject || conversation.name)}</strong>
					<span>${renderChip(conversation.status)} ${renderTime(conversation.last_message_at)}</span>
				</div>
				<button class="bpwh-inline-pay" type="button" data-conversation="${escapeHtml(conversation.name)}">Open Messages</button>
			</article>`;
	}

	function renderNewMessageForm() {
		return `
			<form class="bpwh-portal-chat-form" id="bpwh-new-chat-form">
				<label for="bpwh-new-message">Send a message</label>
				<textarea id="bpwh-new-message" name="message" rows="4" placeholder="Write a message to BP Water Heaters&hellip;" required></textarea>
				<button class="bpwh-inline-pay" type="submit">Send Message</button>
			</form>`;
	}

	function renderChatPanel() {
		if (!activeConversation) return "";
		const messages = activeMessages.length
			? activeMessages.map(renderMessage).join("")
			: "<p class='bpwh-empty'>No messages yet.</p>";
		return `
			<section class="bpwh-portal-panel bpwh-chat-panel" aria-labelledby="chat-panel-title">
				<div class="bpwh-panel-heading">
					<div>
						<p class="bpwh-kicker">Messages</p>
						<h2 id="chat-panel-title" data-focus-heading>${escapeHtml(activeConversation)}</h2>
					</div>
					<button class="bpwh-inline-pay bpwh-inline-pay--secondary" type="button" id="bpwh-chat-close">Close</button>
				</div>
				<div class="bpwh-chat-thread">${messages}</div>
				<form class="bpwh-portal-chat-form bpwh-portal-chat-form--sticky" id="bpwh-chat-reply-form" data-conversation="${escapeHtml(activeConversation)}">
					<label for="bpwh-chat-reply">Reply to BP Water Heaters</label>
					<textarea id="bpwh-chat-reply" name="message" rows="4" placeholder="Reply to BP Water Heaters&hellip;" required></textarea>
					<button class="bpwh-inline-pay" type="submit">Send Reply</button>
				</form>
			</section>`;
	}

	function renderMessage(message) {
		const isAdmin = message.sender_type === "Admin";
		const sender = isAdmin ? "BP Water Heaters" : "You";
		return `
			<article class="bpwh-chat-message bpwh-chat-message--${isAdmin ? "admin" : "customer"}">
				<strong>${sender}</strong>
				<p>${escapeHtml(message.message)}</p>
				<span>${renderTime(message.posted_at)}</span>
			</article>`;
	}

	function render(data, shouldFocus) {
		portalData = data;
		intro.textContent = `Signed in by secure link for ${data.email}.`;
		const activeRecord = (data.service_records || []).find((record) => record.id === data.summary?.active_service_record)
			|| (data.service_records || [])[0];
		app.innerHTML = `
			${renderReturnBanner()}
			${renderNextAction(data.summary)}
			<div class="bpwh-portal-shell${activeConversation ? " has-chat" : ""}">
				<div class="bpwh-portal-main">
					${renderActiveService(activeRecord)}
					${renderHistory(data)}
				</div>
				${renderChatPanel()}
			</div>`;
		bindPortalActions();
		setBusy(false);
		if (shouldFocus) focusFirstHeading();
	}

	function bindPortalActions() {
		for (const button of app.querySelectorAll("[data-invoice]")) {
			button.addEventListener("click", () => payInvoice(button.dataset.invoice, button));
		}
		for (const button of app.querySelectorAll("[data-conversation]")) {
			button.addEventListener("click", () => openConversation(button.dataset.conversation));
		}
		app.querySelector("[data-new-message]")?.addEventListener("click", () => {
			document.getElementById("bpwh-new-message")?.focus();
		});
		document.getElementById("bpwh-new-chat-form")?.addEventListener("submit", sendNewPortalMessage);
		document.getElementById("bpwh-chat-reply-form")?.addEventListener("submit", sendPortalReply);
		document.getElementById("bpwh-chat-close")?.addEventListener("click", () => {
			activeConversation = null;
			activeMessages = [];
			render(portalData, true);
		});
	}

	async function payInvoice(invoice, button) {
		const previousText = button.textContent;
		button.disabled = true;
		button.textContent = "Opening Checkout…";
		setStatus(`Opening checkout for ${invoice}.`);
		try {
			const result = await call("bp_water_heaters.api.portal.create_invoice_checkout", {
				token,
				sales_invoice: invoice,
			});
			if (result.url) {
				window.location.href = result.url;
				return;
			}
			setStatus(result.message || "Online payment is not connected yet. Please call 775-815-9875.", "warning");
		} catch (error) {
			setStatus("That payment could not be started. Please call 775-815-9875.", "error");
		} finally {
			button.disabled = false;
			button.textContent = previousText;
		}
	}

	async function openConversation(conversation) {
		setBusy(true);
		setStatus("Loading messages…");
		try {
			const result = await call("bp_water_heaters.api.chat.get_portal_messages", { token, conversation });
			activeConversation = result.conversation;
			activeMessages = result.messages || [];
			setStatus("");
			render(portalData, true);
		} catch (error) {
			setStatus("That message thread could not be opened.", "error");
			setBusy(false);
		}
	}

	async function sendNewPortalMessage(event) {
		event.preventDefault();
		const form = event.currentTarget;
		const message = form.elements.message.value.trim();
		if (!message) return;
		const button = form.querySelector("button");
		button.disabled = true;
		button.textContent = "Sending…";
		setStatus("Sending message…");
		try {
			const result = await call("bp_water_heaters.api.chat.start_portal_chat", { token, message });
			form.reset();
			await openConversation(result.conversation);
			setStatus("Message sent.");
		} catch (error) {
			setStatus("Could not send that message yet. Please call 775-815-9875.", "error");
			form.elements.message.focus();
		} finally {
			button.disabled = false;
			button.textContent = "Send Message";
		}
	}

	async function sendPortalReply(event) {
		event.preventDefault();
		const form = event.currentTarget;
		const conversation = form.dataset.conversation;
		const message = form.elements.message.value.trim();
		if (!message) return;
		const button = form.querySelector("button");
		button.disabled = true;
		button.textContent = "Sending…";
		setStatus("Sending reply…");
		try {
			await call("bp_water_heaters.api.chat.send_portal_message", { token, conversation, message });
			form.reset();
			await openConversation(conversation);
			setStatus("Reply sent.");
		} catch (error) {
			setStatus("Could not send that reply yet. Please call 775-815-9875.", "error");
			form.elements.message.focus();
		} finally {
			button.disabled = false;
			button.textContent = "Send Reply";
		}
	}

	function renderRecovery(title, message) {
		intro.textContent = message;
		app.innerHTML = `
			<section class="bpwh-portal-panel bpwh-portal-panel--wide bpwh-recovery" aria-labelledby="portal-recovery-title">
				<h2 id="portal-recovery-title" data-focus-heading>${escapeHtml(title)}</h2>
				<p>${escapeHtml(message)}</p>
				<form class="bpwh-portal-chat-form" id="bpwh-recovery-form">
					<label for="bpwh-recovery-email">Email address</label>
					<input id="bpwh-recovery-email" name="email" type="email" autocomplete="email" spellcheck="false" required>
					<button class="bpwh-inline-pay" type="submit">Send Secure Link</button>
				</form>
				<a class="bpwh-text-link" href="tel:+17758159875">Call 775-815-9875</a>
			</section>`;
		document.getElementById("bpwh-recovery-form").addEventListener("submit", requestPortalLink);
		setBusy(false);
		focusFirstHeading();
	}

	async function requestPortalLink(event) {
		event.preventDefault();
		const form = event.currentTarget;
		const button = form.querySelector("button");
		button.disabled = true;
		button.textContent = "Sending…";
		setStatus("Sending secure link…");
		try {
			await call("bp_water_heaters.api.portal.request_magic_link", {
				email: form.elements.email.value.trim(),
			});
			form.reset();
			setStatus("If that email has BP Water Heaters activity, a secure portal link is on the way.");
		} catch (error) {
			setStatus("Portal link could not be sent. Please call 775-815-9875.", "error");
			form.elements.email.focus();
		} finally {
			button.disabled = false;
			button.textContent = "Send Secure Link";
		}
	}

	async function load() {
		if (!token) {
			renderRecovery("Open Your Service Portal", "This portal link is missing a secure token.");
			return;
		}
		setBusy(true);
		setStatus("Loading service details…");
		try {
			render(await call("bp_water_heaters.api.portal.get_portal_data", { token }), false);
			setStatus("");
		} catch (error) {
			renderRecovery("Portal Link Expired", "This secure link is invalid or expired. Request a fresh portal link to continue.");
			setStatus("Request a fresh secure link to continue.", "warning");
		}
	}

	load();
})();
