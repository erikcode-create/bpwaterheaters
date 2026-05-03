import SwiftUI

@main
struct BPWaterHeatersAdminApp: App {
    @State private var session = AdminSession()

    var body: some Scene {
        WindowGroup {
            ContentView(session: session)
        }
    }
}
