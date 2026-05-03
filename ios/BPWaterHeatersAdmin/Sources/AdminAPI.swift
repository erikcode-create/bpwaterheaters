import AuthenticationServices
import CryptoKit
import Foundation
import Observation
import Security
import UIKit

@Observable
final class AdminSession {
    var baseURL = URL(string: "https://portal.bpwaterheaters.com")!
    var isAuthenticated = KeychainTokenStore.load() != nil
    var lastError: String?

    private let callbackScheme = "bpwhadmin"
    private var bearerToken = KeychainTokenStore.load()
    private var webAuthSession: ASWebAuthenticationSession?

    func loginWithMicrosoft() {
        Task { await beginMicrosoftLogin() }
    }

    func logout() {
        Task {
            _ = try? await post("bp_water_heaters.api.mobile.logout", form: [:], as: EmptyResponse.self)
            KeychainTokenStore.clear()
            await MainActor.run {
                bearerToken = nil
                isAuthenticated = false
            }
        }
    }

    func get<Value: Decodable>(_ method: String, as type: Value.Type = Value.self) async throws -> Value {
        let url = baseURL.appending(path: "/api/method/\(method)")
        var request = URLRequest(url: url)
        authorize(&request)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(FrappeEnvelope<Value>.self, from: data).message
    }

    func updateBookingStatus(_ booking: Booking, status: String) async throws {
        let _: GenericActionResponse = try await post(
            "bp_water_heaters.api.mobile.admin_update_booking_status",
            form: ["booking": booking.name, "status": status]
        )
    }

    func ensureJob(for booking: Booking) async throws {
        let _: GenericActionResponse = try await post(
            "bp_water_heaters.api.mobile.admin_ensure_job_for_booking",
            form: ["booking": booking.name]
        )
    }

    func updateProject(_ project: ProjectRecord, status: String? = nil, percentComplete: Double? = nil) async throws {
        var form = ["project": project.name]
        if let status {
            form["status"] = status
        }
        if let percentComplete {
            form["percent_complete"] = String(percentComplete)
        }
        let _: GenericActionResponse = try await post("bp_water_heaters.api.mobile.admin_update_project", form: form)
    }

    func chatMessages(for conversation: ChatConversation) async throws -> ChatThread {
        try await post("bp_water_heaters.api.mobile.admin_get_chat_messages", form: ["conversation": conversation.name])
    }

    func reply(to conversation: ChatConversation, message: String) async throws {
        let _: GenericActionResponse = try await post(
            "bp_water_heaters.api.mobile.admin_reply_chat",
            form: ["conversation": conversation.name, "message": message]
        )
    }

    func updateChatStatus(_ conversation: ChatConversation, status: String) async throws {
        let _: GenericActionResponse = try await post(
            "bp_water_heaters.api.mobile.admin_update_chat_status",
            form: ["conversation": conversation.name, "status": status]
        )
    }

    @MainActor
    private func beginMicrosoftLogin() async {
        do {
            let config: MobileOAuthConfig = try await getPublic("bp_water_heaters.api.mobile.mobile_oauth_config")
            guard config.configured,
                  let clientID = config.clientID,
                  let authorizationEndpoint = config.authorizationEndpoint,
                  let tokenEndpoint = config.tokenEndpoint,
                  let redirectURI = config.redirectURI
            else {
                throw AdminAPIError.message(config.message ?? "Microsoft mobile auth is not configured.")
            }
            let scopes = config.scopes ?? ["openid", "email", "profile"]

            let verifier = PKCE.randomString()
            let state = PKCE.randomString()
            let nonce = PKCE.randomString()
            let authorizationURL = try authorizationURL(
                authorizationEndpoint: authorizationEndpoint,
                clientID: clientID,
                redirectURI: redirectURI,
                scopes: scopes,
                verifier: verifier,
                state: state,
                nonce: nonce
            )
            let callbackURL = try await authenticate(url: authorizationURL)
            let code = try authorizationCode(from: callbackURL, expectedState: state)
            let microsoftToken = try await exchangeAuthorizationCode(
                code,
                verifier: verifier,
                tokenEndpoint: tokenEndpoint,
                redirectURI: redirectURI,
                scopes: scopes,
                clientID: clientID
            )
            let login: MobileLoginResponse = try await post(
                "bp_water_heaters.api.mobile.login_with_microsoft_id_token",
                form: [
                    "id_token": microsoftToken.idToken,
                    "device_name": UIDevice.current.name
                ],
                authorized: false
            )

            KeychainTokenStore.save(login.token)
            await MainActor.run {
                bearerToken = login.token
                isAuthenticated = true
                lastError = nil
            }
        } catch {
            await MainActor.run {
                lastError = error.localizedDescription
            }
        }
    }

    private func getPublic<Value: Decodable>(_ method: String, as type: Value.Type = Value.self) async throws -> Value {
        let url = baseURL.appending(path: "/api/method/\(method)")
        let (data, response) = try await URLSession.shared.data(from: url)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(FrappeEnvelope<Value>.self, from: data).message
    }

    func post<Value: Decodable>(
        _ method: String,
        form: [String: String],
        as type: Value.Type = Value.self,
        authorized: Bool = true
    ) async throws -> Value {
        let url = baseURL.appending(path: "/api/method/\(method)")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded; charset=utf-8", forHTTPHeaderField: "Content-Type")
        request.httpBody = formBody(form)
        if authorized {
            authorize(&request)
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(FrappeEnvelope<Value>.self, from: data).message
    }

    private func authorize(_ request: inout URLRequest) {
        guard let bearerToken else { return }
        request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")
    }

    private func authorizationURL(
        authorizationEndpoint: URL,
        clientID: String,
        redirectURI: String,
        scopes: [String],
        verifier: String,
        state: String,
        nonce: String
    ) throws -> URL {
        var components = URLComponents(url: authorizationEndpoint, resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "client_id", value: clientID),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "redirect_uri", value: redirectURI),
            URLQueryItem(name: "response_mode", value: "query"),
            URLQueryItem(name: "scope", value: scopes.joined(separator: " ")),
            URLQueryItem(name: "state", value: state),
            URLQueryItem(name: "nonce", value: nonce),
            URLQueryItem(name: "code_challenge", value: PKCE.challenge(for: verifier)),
            URLQueryItem(name: "code_challenge_method", value: "S256")
        ]
        guard let url = components?.url else {
            throw AdminAPIError.message("Could not build Microsoft sign-in URL.")
        }
        return url
    }

    @MainActor
    private func authenticate(url: URL) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            webAuthSession = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { callbackURL, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                guard let callbackURL else {
                    continuation.resume(throwing: AdminAPIError.message("Microsoft sign-in did not return a callback."))
                    return
                }
                continuation.resume(returning: callbackURL)
            }
            webAuthSession?.prefersEphemeralWebBrowserSession = false
            webAuthSession?.presentationContextProvider = PresentationAnchorProvider.shared
            webAuthSession?.start()
        }
    }

    private func authorizationCode(from callbackURL: URL, expectedState: String) throws -> String {
        guard let components = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false) else {
            throw AdminAPIError.message("Microsoft callback was not readable.")
        }
        let items = components.queryItems ?? []
        if let error = items.first(where: { $0.name == "error_description" })?.value {
            throw AdminAPIError.message(error)
        }
        guard items.first(where: { $0.name == "state" })?.value == expectedState else {
            throw AdminAPIError.message("Microsoft sign-in state did not match.")
        }
        guard let code = items.first(where: { $0.name == "code" })?.value else {
            throw AdminAPIError.message("Microsoft sign-in did not return an authorization code.")
        }
        return code
    }

    private func exchangeAuthorizationCode(
        _ code: String,
        verifier: String,
        tokenEndpoint: URL,
        redirectURI: String,
        scopes: [String],
        clientID: String
    ) async throws -> MicrosoftTokenResponse {
        var request = URLRequest(url: tokenEndpoint)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded; charset=utf-8", forHTTPHeaderField: "Content-Type")
        request.httpBody = formBody([
            "client_id": clientID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirectURI,
            "code_verifier": verifier,
            "scope": scopes.joined(separator: " ")
        ])
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(MicrosoftTokenResponse.self, from: data)
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            if let frappeError = try? JSONDecoder().decode(FrappeErrorEnvelope.self, from: data), let message = frappeError.message {
                throw AdminAPIError.message(message)
            }
            if let microsoftError = try? JSONDecoder().decode(MicrosoftErrorResponse.self, from: data) {
                throw AdminAPIError.message(microsoftError.errorDescription ?? microsoftError.error)
            }
            throw URLError(.badServerResponse)
        }
    }
}

final class PresentationAnchorProvider: NSObject, ASWebAuthenticationPresentationContextProviding {
    static let shared = PresentationAnchorProvider()

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }
}

private enum AdminAPIError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): message
        }
    }
}

private enum PKCE {
    static func randomString() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        let byteCount = bytes.count
        bytes.withUnsafeMutableBytes { buffer in
            _ = SecRandomCopyBytes(kSecRandomDefault, byteCount, buffer.baseAddress!)
        }
        return Data(bytes).base64URLEncodedString()
    }

    static func challenge(for verifier: String) -> String {
        let digest = SHA256.hash(data: Data(verifier.utf8))
        return Data(digest).base64URLEncodedString()
    }
}

private enum KeychainTokenStore {
    private static let service = "com.blueberg.bpwaterheaters.admin"
    private static let account = "bpwh-mobile-token"

    static func load() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let token = String(data: data, encoding: .utf8)
        else {
            return nil
        }
        return token
    }

    static func save(_ token: String) {
        clear()
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: Data(token.utf8),
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
    }
}

private func formBody(_ parameters: [String: String]) -> Data {
    parameters
        .map { "\($0.key.formPercentEncoded)=\($0.value.formPercentEncoded)" }
        .joined(separator: "&")
        .data(using: .utf8) ?? Data()
}

private extension String {
    var formPercentEncoded: String {
        addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed.subtracting(charactersIn: "+&=")) ?? self
    }
}

private extension CharacterSet {
    func subtracting(charactersIn string: String) -> CharacterSet {
        var copy = self
        copy.remove(charactersIn: string)
        return copy
    }
}

private extension Data {
    func base64URLEncodedString() -> String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
