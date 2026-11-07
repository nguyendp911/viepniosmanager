import SwiftUI
import Foundation

@MainActor
final class ManagerModel: ObservableObject {
    @AppStorage("serverURL") var serverURL: String = ""
    @Published var token: String = SecureStore.token()
    @Published var overview: Overview?
    @Published var devices: [DeviceInfo] = []
    @Published var busy = false
    @Published var notice: String?
    @Published var error: String?

    var isConfigured: Bool { !serverURL.isEmpty && !token.isEmpty }
    var client: APIClient { APIClient(server: serverURL, token: token) }

    func saveConnection(url: String, token: String) throws {
        let address = url.trimmingCharacters(in: .whitespacesAndNewlines)
        let secret = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard APIClient.allowedServerURL(address) else {
            throw APIError(message: "Từ xa phải dùng HTTPS. Hãy nhập URL Tailscale Serve https://...ts.net")
        }
        guard secret.count >= 20 else {
            throw APIError(message: "Access token không hợp lệ. Hãy sao chép token từ Windows.")
        }
        serverURL = address
        self.token = secret
        SecureStore.setToken(secret)
        error = nil
    }

    func load() async {
        guard isConfigured else { return }
        busy = true
        defer { busy = false }
        do {
            async let loaded: Overview = client.get("/overview", as: Overview.self)
            async let connected: [DeviceInfo] = client.devices()
            overview = try await loaded
            // A missing iPhone must not prevent local IPA management.
            devices = (try? await connected) ?? []
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func execute(_ operation: @escaping (APIClient) async throws -> String) async {
        busy = true
        defer { busy = false }
        do {
            notice = try await operation(client)
            error = nil
            // Tasks continue on Windows; reload shows their current state.
            if let overview = try? await client.get("/overview", as: Overview.self) {
                self.overview = overview
            }
        } catch { self.error = error.localizedDescription }
    }

    func renameIPA(id: String, alias: String) async {
        await execute { c in
            let _: IPAActionReply = try await c.patch(
                "/ipas/\(id)/label", body: RenameBuildBody(alias: alias),
                as: IPAActionReply.self
            )
            return "Đã đặt tên riêng cho bản build"
        }
    }

    func deleteIPAs(_ ids: [String], all: Bool, force: Bool) async {
        await execute { c in
            let result: DeleteIPAReply = try await c.post(
                "/ipas/bulk-delete",
                body: DeleteBuildsBody(
                    all: all, ipa_ids: all ? [] : ids, force: force,
                    confirm: all ? "DELETE ALL IPAS" : "DELETE SELECTED IPAS"
                ), as: DeleteIPAReply.self
            )
            return "Đã xóa \(result.deletedIds.count) IPA · hủy theo dõi \(result.trackingRemoved) bản cài"
        }
    }

    func uploadIPA(_ url: URL) async {
        await execute { c in
            try await c.upload("/ipas", fileURL: url, as: url.lastPathComponent)
            return "Đã nhập IPA vào thư viện Windows"
        }
    }

    func uploadProfile(_ url: URL) async {
        await execute { c in
            try await c.upload("/profiles", fileURL: url, as: url.lastPathComponent)
            return "Đã nhập provisioning profile"
        }
    }

    func install(ipaID: String, deviceID: String, resign: Bool, autoRenew: Bool) async {
        await execute { c in
            let r: JobResponse = try await c.post("/install", body: InstallBody(
                ipa_id: ipaID, udid: deviceID, auto_renew: autoRenew,
                resign: resign, profile_id: nil), as: JobResponse.self)
            return "Đã tạo tác vụ cài: \(r.jobId.prefix(8))"
        }
    }

    func renew(id: String) async {
        await execute { c in
            let r: JobResponse = try await c.post("/renew", body: RenewBody(installation_id: id), as: JobResponse.self)
            return "Đã tạo tác vụ gia hạn: \(r.jobId.prefix(8))"
        }
    }

    func scanRenewals() async {
        await execute { c in
            let r: CheckResponse = try await c.post("/renew/check", body: EmptyBody(), as: CheckResponse.self)
            return "Đã gửi \(r.queuedJobIds.count) tác vụ"
        }
    }
}

private struct RenameBuildBody: Encodable {
    let alias: String
}
private struct IPAActionReply: Decodable {
    let id: String
    let alias: String?
}
private struct DeleteBuildsBody: Encodable {
    let all: Bool
    let ipa_ids: [String]
    let force: Bool
    let confirm: String
}
private struct DeleteIPAReply: Decodable {
    let deletedIds: [String]
    let filesRemoved: Int
    let trackingRemoved: Int
}
