import SwiftUI

struct ContentView: View {
    @Bindable var session: AdminSession

    var body: some View {
        if session.isAuthenticated {
            AdminTabs(session: session)
        } else {
            LoginView(session: session)
        }
    }
}

struct LoginView: View {
    @Bindable var session: AdminSession

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Spacer()
            Image(systemName: "wrench.and.screwdriver.fill")
                .font(.system(size: 44, weight: .bold))
                .foregroundStyle(.orange)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 8) {
                Text("BP Water Heaters")
                    .font(.largeTitle.bold())
                Text("Admin operations for bookings, jobs, invoices, payments, and chat.")
                    .font(.body)
                    .foregroundStyle(.secondary)
            }
            if let error = session.lastError {
                Text(error)
                    .font(.callout)
                    .foregroundStyle(.red)
            }
            Button {
                session.loginWithMicrosoft()
            } label: {
                Label("Sign in with Microsoft", systemImage: "person.crop.circle.badge.checkmark")
                    .frame(maxWidth: .infinity, minHeight: 52)
            }
            .buttonStyle(.borderedProminent)
            Spacer()
        }
        .padding(24)
    }
}

struct AdminTabs: View {
    let session: AdminSession

    var body: some View {
        TabView {
            DashboardView(session: session)
                .tabItem { Label("Dashboard", systemImage: "gauge.with.dots.needle.67percent") }
            BookingsView(session: session)
                .tabItem { Label("Bookings", systemImage: "calendar") }
            JobsView(session: session)
                .tabItem { Label("Jobs", systemImage: "checklist") }
            InvoicesView(session: session)
                .tabItem { Label("Invoices", systemImage: "doc.text") }
            ContactsView(session: session)
                .tabItem { Label("Contacts", systemImage: "person.2") }
            ChatsView(session: session)
                .tabItem { Label("Chat", systemImage: "message") }
            SettingsView(session: session)
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}

struct DashboardView: View {
    let session: AdminSession
    @State private var summary: DashboardSummary?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                if let summary {
                    MetricRow(title: "Open bookings", value: summary.openBookings)
                    MetricRow(title: "New contacts", value: summary.newContacts)
                    MetricRow(title: "Open chats", value: summary.openChats)
                    MetricRow(title: "Open projects", value: summary.openProjects)
                } else if let error {
                    Text(error).foregroundStyle(.red)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Dashboard")
            .task {
                do {
                    summary = try await session.get("bp_water_heaters.api.mobile.admin_dashboard")
                } catch {
                    self.error = error.localizedDescription
                }
            }
        }
    }
}

struct MetricRow: View {
    let title: String
    let value: Int

    var body: some View {
        HStack {
            Text(title)
            Spacer()
            Text(value, format: .number)
                .font(.headline)
        }
        .frame(minHeight: 44)
    }
}

struct BookingsView: View {
    let session: AdminSession
    @State private var bookings: [Booking] = []
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List(bookings) { booking in
                BookingRow(session: session, booking: booking) {
                    await load()
                }
            }
            .navigationTitle("Bookings")
            .overlay {
                if let error {
                    ContentUnavailableView("Bookings unavailable", systemImage: "calendar.badge.exclamationmark", description: Text(error))
                }
            }
            .refreshable {
                await load()
            }
            .task {
                await load()
            }
        }
    }

    private func load() async {
        do {
            bookings = try await session.get("bp_water_heaters.api.mobile.admin_list_bookings")
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct BookingRow: View {
    let session: AdminSession
    let booking: Booking
    let reload: () async -> Void

    private let statuses = [
        "Pending Payment",
        "Payment Pending Settlement",
        "Confirmed",
        "Payment Failed",
        "Cancelled",
        "Completed",
        "Expired",
        "Refunded",
        "Disputed"
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text(booking.customerName).font(.headline)
                Text("\(booking.status) · \(booking.preferredStart ?? "")")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(booking.email).font(.caption).foregroundStyle(.secondary)
            }
            HStack {
                Menu("Status") {
                    ForEach(statuses, id: \.self) { status in
                        Button(status) {
                            Task {
                                try? await session.updateBookingStatus(booking, status: status)
                                await reload()
                            }
                        }
                    }
                }
                .frame(minHeight: 44)
                Button("Create Job") {
                    Task {
                        try? await session.ensureJob(for: booking)
                        await reload()
                    }
                }
                .frame(minHeight: 44)
            }
            .buttonStyle(.bordered)
        }
        .frame(minHeight: 84)
    }
}

struct JobsView: View {
    let session: AdminSession
    @State private var projects: [ProjectRecord] = []
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List(projects) { project in
                ProjectRow(session: session, project: project) {
                    await load()
                }
            }
            .navigationTitle("Jobs")
            .overlay {
                if let error {
                    ContentUnavailableView("Jobs unavailable", systemImage: "checklist.unchecked", description: Text(error))
                }
            }
            .refreshable {
                await load()
            }
            .task {
                await load()
            }
        }
    }

    private func load() async {
        do {
            projects = try await session.get("bp_water_heaters.api.mobile.admin_list_projects")
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct ProjectRow: View {
    let session: AdminSession
    let project: ProjectRecord
    let reload: () async -> Void
    @State private var percent: Double

    init(session: AdminSession, project: ProjectRecord, reload: @escaping () async -> Void) {
        self.session = session
        self.project = project
        self.reload = reload
        _percent = State(initialValue: project.percentComplete ?? 0)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text(project.projectName).font(.headline)
                Text("\(project.status) · \(Int(percent))%")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if let customer = project.customer {
                    Text(customer).font(.caption).foregroundStyle(.secondary)
                }
            }
            Slider(value: $percent, in: 0...100, step: 5) {
                Text("Progress")
            } minimumValueLabel: {
                Text("0")
            } maximumValueLabel: {
                Text("100")
            }
            .onChange(of: percent) { _, newValue in
                Task {
                    try? await session.updateProject(project, percentComplete: newValue)
                }
            }
            HStack {
                ForEach(["Open", "Completed", "Cancelled"], id: \.self) { status in
                    Button(status) {
                        Task {
                            try? await session.updateProject(project, status: status, percentComplete: status == "Completed" ? 100 : nil)
                            await reload()
                        }
                    }
                    .frame(minHeight: 44)
                }
            }
            .buttonStyle(.bordered)
        }
        .frame(minHeight: 110)
    }
}

struct InvoicesView: View {
    let session: AdminSession
    @State private var invoices: [InvoiceRecord] = []

    var body: some View {
        NavigationStack {
            List(invoices) { invoice in
                VStack(alignment: .leading, spacing: 6) {
                    Text(invoice.name).font(.headline)
                    Text("\(invoice.status) · \(invoice.customer)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text("Total \(currency(invoice.grandTotal)) · open \(currency(invoice.outstandingAmount))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(minHeight: 56)
            }
            .navigationTitle("Invoices")
            .task {
                invoices = (try? await session.get("bp_water_heaters.api.mobile.admin_list_invoices")) ?? []
            }
        }
    }

    private func currency(_ amount: Double?) -> String {
        (amount ?? 0).formatted(.currency(code: "USD"))
    }
}

struct ContactsView: View {
    let session: AdminSession
    @State private var contacts: [ContactRequest] = []

    var body: some View {
        NavigationStack {
            List(contacts) { contact in
                VStack(alignment: .leading, spacing: 6) {
                    Text(contact.fullName).font(.headline)
                    Text("\(contact.status) · \(contact.email)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text(contact.phone ?? "No phone")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(minHeight: 56)
            }
            .navigationTitle("Contacts")
            .task {
                contacts = (try? await session.get("bp_water_heaters.api.mobile.admin_list_contact_requests")) ?? []
            }
        }
    }
}

struct ChatsView: View {
    let session: AdminSession
    @State private var chats: [ChatConversation] = []
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List(chats) { chat in
                NavigationLink {
                    ChatDetailView(session: session, conversation: chat)
                } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(chat.subject).font(.headline)
                        Text("\(chat.status) · \(chat.email ?? "")")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(minHeight: 56)
                }
            }
            .navigationTitle("Chat")
            .overlay {
                if let error {
                    ContentUnavailableView("Chat unavailable", systemImage: "message.badge", description: Text(error))
                }
            }
            .refreshable {
                await load()
            }
            .task {
                await load()
            }
        }
    }

    private func load() async {
        do {
            chats = try await session.get("bp_water_heaters.api.mobile.admin_list_chats")
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct ChatDetailView: View {
    let session: AdminSession
    let conversation: ChatConversation
    @State private var thread: ChatThread?
    @State private var reply = ""
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(thread?.messages ?? []) { message in
                        ChatBubble(message: message)
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            Divider()
            VStack(spacing: 12) {
                TextField("Reply to customer", text: $reply, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(2...5)
                HStack {
                    Button("Close") {
                        Task {
                            try? await session.updateChatStatus(conversation, status: "Closed")
                            await load()
                        }
                    }
                    .frame(minHeight: 44)
                    Spacer()
                    Button("Send") {
                        Task { await send() }
                    }
                    .buttonStyle(.borderedProminent)
                    .frame(minHeight: 44)
                    .disabled(reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .padding(16)
        }
        .navigationTitle(conversation.subject)
        .navigationBarTitleDisplayMode(.inline)
        .overlay {
            if let error {
                ContentUnavailableView("Chat unavailable", systemImage: "message.badge", description: Text(error))
            }
        }
        .task {
            await load()
        }
    }

    private func load() async {
        do {
            thread = try await session.chatMessages(for: conversation)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func send() async {
        let message = reply.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }
        do {
            try await session.reply(to: conversation, message: message)
            reply = ""
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct ChatBubble: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(message.senderType)
                .font(.caption.bold())
            Text(message.message)
                .font(.body)
            if let postedAt = message.postedAt {
                Text(postedAt)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .frame(maxWidth: 320, alignment: .leading)
        .background(message.senderType == "Admin" ? Color.accentColor.opacity(0.16) : Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .frame(maxWidth: .infinity, alignment: message.senderType == "Admin" ? .trailing : .leading)
    }
}

struct SettingsView: View {
    let session: AdminSession

    var body: some View {
        NavigationStack {
            List {
                LabeledContent("Portal", value: session.baseURL.absoluteString)
                LabeledContent("Auth", value: "Microsoft")
                LabeledContent("Secrets", value: "Server-side only")
                Button("Sign Out", role: .destructive) {
                    session.logout()
                }
            }
            .navigationTitle("Settings")
        }
    }
}

#Preview {
    ContentView(session: AdminSession())
}
