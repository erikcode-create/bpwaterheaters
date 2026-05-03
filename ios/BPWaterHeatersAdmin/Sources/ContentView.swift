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
                    summary = try await session.get("bp_water_heaters.api.admin.dashboard")
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

    var body: some View {
        NavigationStack {
            List(bookings) { booking in
                VStack(alignment: .leading, spacing: 6) {
                    Text(booking.customerName).font(.headline)
                    Text("\(booking.status) · \(booking.preferredStart ?? "")")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text(booking.email).font(.caption).foregroundStyle(.secondary)
                }
                .frame(minHeight: 56)
            }
            .navigationTitle("Bookings")
            .task {
                bookings = (try? await session.get("bp_water_heaters.api.admin.list_bookings")) ?? []
            }
        }
    }
}

struct JobsView: View {
    let session: AdminSession
    @State private var projects: [ProjectRecord] = []

    var body: some View {
        NavigationStack {
            List(projects) { project in
                VStack(alignment: .leading, spacing: 6) {
                    Text(project.projectName).font(.headline)
                    Text("\(project.status) · \(Int(project.percentComplete ?? 0))%")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    if let customer = project.customer {
                        Text(customer).font(.caption).foregroundStyle(.secondary)
                    }
                }
                .frame(minHeight: 56)
            }
            .navigationTitle("Jobs")
            .task {
                projects = (try? await session.get("bp_water_heaters.api.admin.list_projects")) ?? []
            }
        }
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
                invoices = (try? await session.get("bp_water_heaters.api.admin.list_invoices")) ?? []
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
                contacts = (try? await session.get("bp_water_heaters.api.admin.list_contact_requests")) ?? []
            }
        }
    }
}

struct ChatsView: View {
    let session: AdminSession
    @State private var chats: [ChatConversation] = []

    var body: some View {
        NavigationStack {
            List(chats) { chat in
                VStack(alignment: .leading, spacing: 6) {
                    Text(chat.subject).font(.headline)
                    Text("\(chat.status) · \(chat.email ?? "")")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .frame(minHeight: 56)
            }
            .navigationTitle("Chat")
            .task {
                chats = (try? await session.get("bp_water_heaters.api.admin.list_chats")) ?? []
            }
        }
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
