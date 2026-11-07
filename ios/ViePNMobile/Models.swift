import Foundation
import Security

struct IPAInfo: Codable, Identifiable {
    let id: String
    let name: String
    let bundleId: String
    let version: String?
    let profileExpires: String?
    let signedCandidate: Int
    let alias: String?
    let createdAt: String?
    let sizeBytes: Int?
    let profileTeam: String?

    var buildDisplayName: String {
        let base = (alias?.isEmpty == false) ? alias! : name
        return "\(base) · v\(version ?? "–") · \(id.prefix(8))"
    }
}

struct InstallationInfo: Codable, Identifiable {
    let id: String
    let deviceUdid: String
    let bundleId: String
    let expiresAt: String?
    let autoRenew: Int
    let state: String
    let lastError: String?
}

struct ProfileInfo: Codable, Identifiable {
    let id: String
    let filename: String
    let expiresAt: String?
    let bundlePattern: String?
}

struct JobInfo: Codable, Identifiable {
    let id: String
    let kind: String
    let state: String
    let createdAt: String
    let outputJson: String?
}

struct ServerTools: Codable {
    let pymobiledevice3: Bool
    let zsign: Bool
    let signingP12: Bool
}

struct Overview: Codable {
    let ipas: [IPAInfo]
    let installations: [InstallationInfo]
    let profiles: [ProfileInfo]
    let jobs: [JobInfo]
    let tools: ServerTools
    let renewalHours: Int
}

struct JobResponse: Codable { let jobId: String }
struct CheckResponse: Codable { let queuedJobIds: [String] }
struct DeviceInfo: Identifiable {
    let id: String
    let name: String
}

extension String {
    var expiryDate: Date? {
        // Python datetime.isoformat can send fractional seconds and UTC offset.
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: self) ?? { () -> Date? in
            f.formatOptions = [.withInternetDateTime]
            return f.date(from: self)
        }()
    }
}

enum SecureStore {
    static let service = "com.viepn.iosmanager"
    static func setToken(_ token: String) {
        let key: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: "api-token"]
        SecItemDelete(key as CFDictionary)
        guard let data = token.data(using: .utf8), !token.isEmpty else { return }
        var attrs = key
        attrs[kSecValueData as String] = data
        attrs[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(attrs as CFDictionary, nil)
    }
    static func token() -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: "api-token",
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var data: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &data) == errSecSuccess,
              let bytes = data as? Data else { return "" }
        return String(data: bytes, encoding: .utf8) ?? ""
    }
}
