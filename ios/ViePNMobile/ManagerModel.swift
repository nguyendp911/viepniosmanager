import SwiftUI
import Foundation

@MainActor
final class ManagerModel: ObservableObject {
    @AppStorage("serverURL") var serverURL: String = ""
    @Published var token: String = SecureStore.token()
    @Published var overview: Overview?
    @Published var devices: [DeviceInfo] = []
    @Published var devicesLoading = false
    @Published var devicesError: String?
    @Published var diagnostic: DoctorReport?
    @Published var remoteDevices: [RemoteDeviceInfo] = []
    @Published var nearbyBLE: BLEScanReply?
    @Published var bleScanBusy = false
    @Published var remoteError: String?
    let bluetooth = ViePNBLEPeripheral()
    @AppStorage("viepnRemoteDeviceID") private var remoteDeviceID = ""

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

    func registerSelf() async {
        guard isConfigured else { return }
        if remoteDeviceID.isEmpty { remoteDeviceID = UUID().uuidString.lowercased() }
        do {
            let body = RemoteRegisterBody(
                device_id: remoteDeviceID, name: "ViePN iPhone",
                ble_token: bluetooth.token
            )
            let _: RemoteRegisterReply = try await client.post(
                "/remote/devices/register", body: body, as: RemoteRegisterReply.self
            )
            remoteError = nil
            await refreshRemoteDevices()
        } catch {
            remoteError = "Đăng ký thiết bị từ xa: " + error.localizedDescription
        }
    }

    func refreshRemoteDevices() async {
        guard isConfigured else { return }
        do {
            let response: RemoteDeviceReply = try await client.get(
                "/remote/devices", as: RemoteDeviceReply.self
            )
            remoteDevices = response.devices
            remoteError = nil
        } catch {
            remoteError = error.localizedDescription
        }
    }

    func scanBluetoothNearby() async {
        guard isConfigured else { return }
        bleScanBusy = true
        defer { bleScanBusy = false }
        do {
            nearbyBLE = try await client.post(
                "/ble/scan", body: EmptyBody(), as: BLEScanReply.self
            )
        } catch {
            nearbyBLE = BLEScanReply(available: false, nearby: [],
                                     detail: error.localizedDescription)
        }
    }

    func load() async {
        guard isConfigured else {
            devices = []
            devicesError = "Chưa cấu hình kết nối đến Windows."
            return
        }
        busy = true
        defer { busy = false }
        // Independent requests: a device-discovery error should not make
        // the IPA library unavailable, or be silently rendered as zero devices.
        async let loaded: Overview = client.get("/overview", as: Overview.self)
        async let connected: [DeviceInfo] = client.devices()
        do {
            overview = try await loaded
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        devicesLoading = true
        do {
            devices = try await connected
            devicesError = nil
        } catch {
            devices = []
            devicesError = error.localizedDescription
        }
        devicesLoading = false
        await registerSelf()
    }

    func refreshDevices() async {
        guard isConfigured else {
            devicesError = "Chưa cấu hình kết nối Windows."
            return
        }
        devicesLoading = true
        defer { devicesLoading = false }
        do {
            devices = try await client.devices()
            devicesError = nil
        } catch {
            devices = []
            devicesError = error.localizedDescription
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

    func classifyIPA(id: String, channel: String) async {
        await execute { c in
            let _: ChannelIPAReply = try await c.patch(
                "/ipas/\(id)/channel", body: ChannelIPABody(channel: channel),
                as: ChannelIPAReply.self
            )
            return "Đã phân loại bản build"
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
            return "Đã xóa \(result.deletedIds.count) IPA · hủy theo dõi \(result.trackingRemoved) bản cài" +
                ((result.pendingFileDeletes ?? 0) > 0 ?
                  " · \(result.pendingFileDeletes ?? 0) file bị Windows khóa, sẽ dọn sau." : "")
        }
    }

    func checkConnection() async {
        guard isConfigured else { error = "Vui lòng cấu hình máy chủ"; return }
        do {
            diagnostic = try await client.get("/doctor", as: DoctorReport.self)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func retryJob(_ id: String) async {
        await execute { c in
            let reply: JobResponse = try await c.post(
                "/jobs/\(id)/retry", body: RetryJobBody(confirm: "RETRY JOB"),
                as: JobResponse.self
            )
            return "Đã gửi lại tác vụ: \(reply.jobId.prefix(8))"
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
    let pendingFileDeletes: Int?
}

private struct ChannelIPABody: Encodable { let channel: String }
private struct ChannelIPAReply: Decodable { let id: String; let channel: String }

private struct RetryJobBody: Encodable { let confirm: String }
