(function () {
	const state = { plaid: null };
	const status = document.getElementById("bpwh-admin-status");
	const metrics = document.getElementById("bpwh-admin-metrics");
	const plaidMessage = document.getElementById("bpwh-plaid-message");
	const plaidItems = document.getElementById("bpwh-plaid-items");
	const plaidConnect = document.getElementById("bpwh-plaid-connect");

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
		return String(value ?? "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function money(value) {
		return Number(value || 0).toLocaleString("en-US", { style: "currency", currency: "USD" });
	}

	function setMessage(element, text, kind) {
		element.textContent = text || "";
		element.className = `bpwh-admin-message ${text ? "is-visible" : ""} ${kind || ""}`;
	}

	function renderMetrics(summary) {
		metrics.innerHTML = [
			["Open bookings", summary.open_bookings],
			["New contacts", summary.new_contacts],
			["Giveaway entries", summary.giveaway_entries],
			["Open chats", summary.open_chats],
			["Open jobs", summary.open_projects],
		]
			.map(([label, value]) => `<article><strong>${value}</strong><span>${label}</span></article>`)
			.join("");
	}

	function renderRows(elementId, rows, formatter) {
		const element = document.getElementById(elementId);
		element.innerHTML = rows.length ? rows.map(formatter).join("") : "<p class='bpwh-empty'>Nothing here yet.</p>";
	}

	function statusOptions(current, options) {
		return options
			.map((option) => `<option value="${escapeHtml(option)}" ${option === current ? "selected" : ""}>${escapeHtml(option)}</option>`)
			.join("");
	}

	function renderBookings(bookings) {
		const options = [
			"Requested",
			"Pending Payment",
			"Payment Pending Settlement",
			"Confirmed",
			"Payment Failed",
			"Cancelled",
			"Completed",
			"Expired",
			"Refunded",
			"Disputed",
		];
		renderRows("bpwh-admin-bookings", bookings, (booking) => `
			<article class="bpwh-admin-row" data-booking="${escapeHtml(booking.name)}">
				<div>
					<strong>${escapeHtml(booking.customer_name)}</strong>
					<span>${escapeHtml(booking.service_type || "")} · ${escapeHtml(booking.preferred_start || "")} · ${escapeHtml(booking.email)}</span>
					<span>${escapeHtml(booking.stripe_payment_status || "No payment")} · ${escapeHtml(booking.payment_settlement_status || "")}</span>
				</div>
				<div class="bpwh-admin-actions">
					<select data-action="booking-status">${statusOptions(booking.status, options)}</select>
					<button type="button" data-action="ensure-job">Create/update job</button>
					${
						booking.service_type === "Flush" && booking.status === "Completed"
							? "<button type='button' data-action='create-flush-entry'>Create flush entry</button>"
							: ""
					}
				</div>
				<script type="application/json" data-booking-payload>${JSON.stringify(booking).replace(/</g, "\\u003c")}</script>
			</article>
		`);
	}

	function renderGiveawayEntries(entries) {
		renderRows("bpwh-admin-giveaway-entries", entries, (entry) => `
			<article class="bpwh-admin-row" data-giveaway-entry="${escapeHtml(entry.name)}">
				<div>
					<strong>${escapeHtml(entry.full_name)}</strong>
					<span>${escapeHtml(entry.entry_kind || "")} · ${escapeHtml(entry.entry_source)} · ${escapeHtml(entry.status)} · ${escapeHtml(entry.email)}</span>
					<span>${escapeHtml(entry.property_address)}, ${escapeHtml(entry.city)} ${escapeHtml(entry.state)} ${escapeHtml(entry.postal_code)}</span>
				</div>
				<div class="bpwh-admin-actions">
					${entry.status === "Winner" ? "<span>Winner</span>" : "<button type='button' data-action='mark-giveaway-winner'>Mark winner</button>"}
				</div>
			</article>
		`);
	}

	function downloadText(filename, text, type) {
		const blob = new Blob([text], { type: type || "text/plain" });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = filename;
		document.body.append(anchor);
		anchor.click();
		anchor.remove();
		URL.revokeObjectURL(url);
	}

	function renderProjects(projects) {
		renderRows("bpwh-admin-projects", projects, (project) => `
			<article class="bpwh-admin-row" data-project="${escapeHtml(project.name)}">
				<div>
					<strong>${escapeHtml(project.project_name)}</strong>
					<span>${escapeHtml(project.customer || "No customer")} · ${escapeHtml(project.expected_start_date || "")}</span>
				</div>
				<div class="bpwh-admin-actions">
					<select data-action="project-status">${statusOptions(project.status, ["Open", "Completed", "Cancelled"])}</select>
					<label class="bpwh-admin-range">
						<span>${Number(project.percent_complete || 0).toFixed(0)}%</span>
						<input type="range" min="0" max="100" step="5" value="${Number(project.percent_complete || 0)}" data-action="project-percent">
					</label>
				</div>
			</article>
		`);
	}

	function renderInvoices(invoices) {
		renderRows("bpwh-admin-invoices", invoices, (invoice) => `
			<article class="bpwh-admin-row">
				<div>
					<strong>${escapeHtml(invoice.name)}</strong>
					<span>${escapeHtml(invoice.customer)} · ${escapeHtml(invoice.status)}</span>
					<span>${money(invoice.grand_total)} total · ${money(invoice.outstanding_amount)} outstanding</span>
				</div>
			</article>
		`);
	}

	function renderChats(chats) {
		renderRows("bpwh-admin-chats", chats, (chat) => `
			<article class="bpwh-admin-row" data-conversation="${escapeHtml(chat.name)}">
				<div>
					<strong>${escapeHtml(chat.subject)}</strong>
					<span>${escapeHtml(chat.status)} · ${escapeHtml(chat.email || "")}</span>
					<span>${escapeHtml(chat.last_message_at || "")}</span>
				</div>
				<div class="bpwh-admin-actions">
					<button type="button" data-action="open-chat">Open</button>
					<button type="button" data-action="close-chat">Close</button>
				</div>
			</article>
		`);
	}

	function renderPlaid(plaid) {
		state.plaid = plaid;
		if (!plaid.configured) {
			plaidConnect.disabled = true;
			setMessage(plaidMessage, "Plaid production credentials are not configured yet. Add the production client ID and secret to site config, then refresh this page.", "is-warning");
		} else {
			plaidConnect.disabled = false;
			setMessage(plaidMessage, `Plaid is configured for ${plaid.environment}. Connect the real bank, map one Plaid account to one ERP bank account, then sync.`, "");
		}
		plaidItems.innerHTML = plaid.items.length
			? plaid.items.map((item) => renderPlaidItem(item)).join("")
			: "<p class='bpwh-empty'>No bank connection yet.</p>";
	}

	function renderPlaidItem(item) {
		const mapped = item.bank_account && item.selected_account_name;
		return `
			<article class="bpwh-admin-row bpwh-plaid-item" data-plaid-item="${escapeHtml(item.name)}">
				<div>
					<strong>${escapeHtml(item.institution_name || item.item_id)}</strong>
					<span>${escapeHtml(item.status)}${mapped ? ` · ${escapeHtml(item.selected_account_name)} ${escapeHtml(item.selected_account_mask || "")}` : ""}</span>
					<span>${item.bank_account ? `ERP bank: ${escapeHtml(item.bank_account)}` : "Needs ERP bank mapping"}</span>
					${item.last_error ? `<span class="bpwh-admin-error">${escapeHtml(item.last_error)}</span>` : ""}
				</div>
				<div class="bpwh-admin-actions">
					<button type="button" data-action="load-plaid-accounts">Map account</button>
					<button type="button" data-action="sync-plaid" ${mapped ? "" : "disabled"}>Sync</button>
				</div>
				<div class="bpwh-plaid-mapping" id="bpwh-plaid-map-${escapeHtml(item.name)}"></div>
			</article>`;
	}

	function bankOptions() {
		const accounts = (state.plaid?.bank_accounts || [])
			.map((account) => {
				const label = [account.account_name, account.bank, account.account].filter(Boolean).join(" · ") || account.name;
				return `<option value="${escapeHtml(account.name)}">${escapeHtml(label)}</option>`;
			})
			.join("");
		return `<option value="__create__">Create ERP bank account from selected Plaid account</option>${accounts}`;
	}

	async function loadPlaidAccounts(item) {
		const container = document.getElementById(`bpwh-plaid-map-${CSS.escape(item)}`);
		container.innerHTML = "<p class='bpwh-empty'>Loading Plaid accounts.</p>";
		const result = await call("bp_water_heaters.api.plaid.list_plaid_accounts", { item });
		container.innerHTML = `
			<label>
				<span>Plaid account</span>
				<select data-plaid-account>
					${result.accounts.map((account) => `
						<option value="${escapeHtml(account.account_id)}">${escapeHtml(account.name)} ${escapeHtml(account.mask || "")} · ${escapeHtml(account.subtype || account.type || "")}</option>
					`).join("")}
				</select>
			</label>
			<label>
				<span>ERP bank account</span>
				<select data-bank-account>${bankOptions()}</select>
			</label>
			<button type="button" data-action="save-plaid-map">Save mapping</button>`;
	}

	async function connectPlaid() {
		if (!state.plaid?.configured) return;
		if (!window.Plaid) {
			setMessage(plaidMessage, "Plaid Link has not loaded yet. Try again in a moment.", "is-warning");
			return;
		}
		setMessage(plaidMessage, "Creating secure Plaid Link token.", "");
		const result = await call("bp_water_heaters.api.plaid.create_link_token");
		const handler = Plaid.create({
			token: result.link_token,
			onSuccess: async (publicToken, metadata) => {
				try {
					setMessage(plaidMessage, "Exchanging Plaid public token and saving the server-side Item.", "");
					await call("bp_water_heaters.api.plaid.exchange_public_token", {
						public_token: publicToken,
						institution_name: metadata?.institution?.name || "",
					});
					await loadPlaid();
				} catch (error) {
					setMessage(plaidMessage, error.message || "Plaid Link succeeded, but ERP could not save the connection.", "is-error");
				}
			},
			onExit: (error) => {
				if (error) setMessage(plaidMessage, error.display_message || error.error_message || "Plaid Link exited with an error.", "is-error");
			},
		});
		handler.open();
	}

	async function openChat(conversation) {
		const row = document.querySelector(`[data-conversation="${CSS.escape(conversation)}"]`);
		const existing = row.querySelector(".bpwh-chat-thread");
		if (existing) {
			existing.remove();
			return;
		}
		const result = await call("bp_water_heaters.api.admin.get_chat_messages", { conversation });
		const messages = result.messages.map((message) => `
			<div class="bpwh-chat-message bpwh-chat-message--${message.sender_type === "Admin" ? "admin" : "customer"}">
				<strong>${escapeHtml(message.sender_type)}</strong>
				<p>${escapeHtml(message.message)}</p>
				<span>${escapeHtml(message.posted_at || "")}</span>
			</div>
		`).join("");
		row.insertAdjacentHTML("beforeend", `
			<form class="bpwh-chat-thread" data-chat-reply="${escapeHtml(conversation)}">
				${messages || "<p class='bpwh-empty'>No messages yet.</p>"}
				<textarea name="message" rows="3" placeholder="Reply to customer" required></textarea>
				<button type="submit">Send reply</button>
			</form>`);
	}

	async function loadPlaid() {
		renderPlaid(await call("bp_water_heaters.api.plaid.status"));
	}

	async function load() {
		status.textContent = "Loading live BP Water Heaters operations.";
		const [summary, bookings, giveawayEntries, projects, invoices, chats, plaid] = await Promise.all([
			call("bp_water_heaters.api.admin.dashboard"),
			call("bp_water_heaters.api.admin.list_bookings"),
			call("bp_water_heaters.api.giveaway.admin_list_entries"),
			call("bp_water_heaters.api.admin.list_projects"),
			call("bp_water_heaters.api.admin.list_invoices"),
			call("bp_water_heaters.api.admin.list_chats"),
			call("bp_water_heaters.api.plaid.status"),
		]);
		renderMetrics(summary);
		renderBookings(bookings);
		renderGiveawayEntries(giveawayEntries);
		renderProjects(projects);
		renderInvoices(invoices);
		renderChats(chats);
		renderPlaid(plaid);
		status.textContent = "Live operations are ready.";
	}

	document.addEventListener("change", async (event) => {
		const target = event.target;
		const booking = target.closest("[data-booking]")?.dataset.booking;
		const project = target.closest("[data-project]")?.dataset.project;
		if (target.dataset.action === "booking-status" && booking) {
			await call("bp_water_heaters.api.admin.update_booking_status", { booking, status: target.value });
		}
		if (target.dataset.action === "project-status" && project) {
			await call("bp_water_heaters.api.admin.update_project", { project, status: target.value });
		}
		if (target.dataset.action === "project-percent" && project) {
			target.previousElementSibling.textContent = `${target.value}%`;
			await call("bp_water_heaters.api.admin.update_project", { project, percent_complete: target.value });
		}
	});

	document.addEventListener("click", async (event) => {
		const target = event.target;
		if (!target.dataset.action) return;
		const booking = target.closest("[data-booking]")?.dataset.booking;
		const project = target.closest("[data-project]")?.dataset.project;
		const conversation = target.closest("[data-conversation]")?.dataset.conversation;
		const plaidItem = target.closest("[data-plaid-item]")?.dataset.plaidItem;
		const giveawayEntry = target.closest("[data-giveaway-entry]")?.dataset.giveawayEntry;
		if (target.dataset.action === "ensure-job" && booking) {
			await call("bp_water_heaters.api.admin.ensure_job_for_booking", { booking });
			await load();
		}
		if (target.dataset.action === "create-flush-entry" && booking) {
			const row = target.closest("[data-booking]");
			const bookingPayload = JSON.parse(row.querySelector("[data-booking-payload]").textContent);
			await call("bp_water_heaters.api.giveaway.create_paid_flush_entry", {
				full_name: bookingPayload.customer_name,
				email: bookingPayload.email,
				phone: bookingPayload.phone,
				property_address: bookingPayload.property_address,
				city: bookingPayload.city,
				state: bookingPayload.state,
				postal_code: bookingPayload.postal_code,
				linked_booking: bookingPayload.name,
				linked_sales_invoice: bookingPayload.sales_invoice,
				flush_paid_completed: "1",
			});
			await load();
		}
		if (target.dataset.action === "open-chat" && conversation) {
			await openChat(conversation);
		}
		if (target.dataset.action === "close-chat" && conversation) {
			await call("bp_water_heaters.api.admin.update_chat_status", { conversation, status: "Closed" });
			await load();
		}
		if (target.dataset.action === "load-plaid-accounts" && plaidItem) {
			await loadPlaidAccounts(plaidItem);
		}
		if (target.dataset.action === "save-plaid-map" && plaidItem) {
			const row = target.closest("[data-plaid-item]");
			await call("bp_water_heaters.api.plaid.map_plaid_account", {
				item: plaidItem,
				plaid_account_id: row.querySelector("[data-plaid-account]").value,
				bank_account: row.querySelector("[data-bank-account]").value,
			});
			await loadPlaid();
		}
		if (target.dataset.action === "sync-plaid" && plaidItem) {
			await call("bp_water_heaters.api.plaid.sync_bank_transactions", { item: plaidItem });
			await loadPlaid();
		}
		if (target.dataset.action === "project-complete" && project) {
			await call("bp_water_heaters.api.admin.update_project", { project, status: "Completed", percent_complete: 100 });
			await load();
		}
		if (target.dataset.action === "export-giveaway") {
			const result = await call("bp_water_heaters.api.giveaway.admin_export_eligible_entries");
			downloadText(result.filename, result.csv, "text/csv");
			status.textContent = `Exported ${result.count} eligible giveaway entries.`;
		}
		if (target.dataset.action === "mark-giveaway-winner" && giveawayEntry) {
			await call("bp_water_heaters.api.giveaway.admin_mark_winner", { entry: giveawayEntry });
			await load();
		}
	});

	document.addEventListener("submit", async (event) => {
		const form = event.target;
		const conversation = form.dataset.chatReply;
		if (!conversation) return;
		event.preventDefault();
		const message = form.elements.message.value.trim();
		if (!message) return;
		await call("bp_water_heaters.api.admin.reply_chat", { conversation, message });
		await openChat(conversation);
		await openChat(conversation);
	});

	plaidConnect.addEventListener("click", connectPlaid);
	load().catch((error) => {
		status.textContent = "Could not load operations.";
		setMessage(plaidMessage, error.message, "is-error");
	});
})();
