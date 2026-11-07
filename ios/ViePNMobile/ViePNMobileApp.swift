import SwiftUI

@main
struct ViePNMobileApp: App {
    @StateObject private var manager = ManagerModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(manager)
                .preferredColorScheme(.dark)
        }
    }
}
