import Foundation

struct DashboardSummary: Decodable {
    let openBookings: Int
    let newContacts: Int
    let openChats: Int
    let openProjects: Int

    enum CodingKeys: String, CodingKey {
        case openBookings = "open_bookings"
        case newContacts = "new_contacts"
        case openChats = "open_chats"
        case openProjects = "open_projects"
    }
}

struct Booking: Decodable, Identifiable {
    let name: String
    let customerName: String
    let email: String
    let phone: String?
    let preferredStart: String?
    let status: String
    let stripePaymentStatus: String?
    let paymentSettlementStatus: String?
    let salesInvoice: String?
    let project: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case customerName = "customer_name"
        case email
        case phone
        case preferredStart = "preferred_start"
        case status
        case stripePaymentStatus = "stripe_payment_status"
        case paymentSettlementStatus = "payment_settlement_status"
        case salesInvoice = "sales_invoice"
        case project
    }
}

struct ChatConversation: Decodable, Identifiable {
    let name: String
    let subject: String
    let status: String
    let customerName: String?
    let email: String?
    let phone: String?
    let booking: String?
    let lastMessageAt: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case subject
        case status
        case customerName = "customer_name"
        case email
        case phone
        case booking
        case lastMessageAt = "last_message_at"
    }
}

struct ChatThread: Decodable {
    let conversation: ChatConversation
    let messages: [ChatMessage]
}

struct ChatMessage: Decodable, Identifiable {
    let name: String
    let senderType: String
    let senderEmail: String?
    let message: String
    let postedAt: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case senderType = "sender_type"
        case senderEmail = "sender_email"
        case message
        case postedAt = "posted_at"
    }
}

struct ProjectRecord: Decodable, Identifiable {
    let name: String
    let projectName: String
    let status: String
    let customer: String?
    let percentComplete: Double?
    let expectedStartDate: String?
    let expectedEndDate: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case projectName = "project_name"
        case status
        case customer
        case percentComplete = "percent_complete"
        case expectedStartDate = "expected_start_date"
        case expectedEndDate = "expected_end_date"
    }
}

struct InvoiceRecord: Decodable, Identifiable {
    let name: String
    let customer: String
    let postingDate: String?
    let grandTotal: Double?
    let outstandingAmount: Double?
    let status: String

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case customer
        case postingDate = "posting_date"
        case grandTotal = "grand_total"
        case outstandingAmount = "outstanding_amount"
        case status
    }
}

struct ContactRequest: Decodable, Identifiable {
    let name: String
    let fullName: String
    let email: String
    let phone: String?
    let source: String?
    let status: String
    let creation: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case fullName = "full_name"
        case email
        case phone
        case source
        case status
        case creation
    }
}

struct BPWHAPIEnvelope<Value: Decodable>: Decodable {
    let message: Value
}

struct BPWHAPIErrorEnvelope: Decodable {
    let message: String?
    let exception: String?
    let excType: String?

    enum CodingKeys: String, CodingKey {
        case message
        case exception
        case excType = "exc_type"
    }
}

struct EmptyResponse: Decodable {}

struct GenericActionResponse: Decodable {
    let booking: String?
    let project: String?
    let conversation: String?
    let status: String?
}

struct MobileOAuthConfig: Decodable {
    let configured: Bool
    let message: String?
    let tenantID: String?
    let clientID: String?
    let authorizationEndpoint: URL?
    let tokenEndpoint: URL?
    let redirectURI: String?
    let scopes: [String]?

    enum CodingKeys: String, CodingKey {
        case configured
        case message
        case tenantID = "tenant_id"
        case clientID = "client_id"
        case authorizationEndpoint = "authorization_endpoint"
        case tokenEndpoint = "token_endpoint"
        case redirectURI = "redirect_uri"
        case scopes
    }
}

struct MicrosoftTokenResponse: Decodable {
    let idToken: String
    let accessToken: String?
    let expiresIn: Int?

    enum CodingKeys: String, CodingKey {
        case idToken = "id_token"
        case accessToken = "access_token"
        case expiresIn = "expires_in"
    }
}

struct MicrosoftErrorResponse: Decodable {
    let error: String
    let errorDescription: String?

    enum CodingKeys: String, CodingKey {
        case error
        case errorDescription = "error_description"
    }
}

struct MobileLoginResponse: Decodable {
    let token: String
    let expiresAt: String
    let user: String

    enum CodingKeys: String, CodingKey {
        case token
        case expiresAt = "expires_at"
        case user
    }
}
