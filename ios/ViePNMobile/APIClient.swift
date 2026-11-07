import Foundation

struct APIError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

struct APIClient {
    var server: String
    var token: String
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    // HTTPS is mandatory for Internet/Tailscale connections. Keep HTTP only
    // for explicit RFC1918 LAN addresses and localhost during setup.
    static func allowedServerURL(_ value: String) -> Bool {
        guard let url = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              let scheme = url.scheme?.lowercased(),
              let host = url.host?.lowercased(),
              !host.isEmpty,
              url.user == nil, url.password == nil, url.query == nil,
              url.fragment == nil else { return false }

        if scheme == "https" { return true }
        guard scheme == "http" else { return false }
        if host == "localhost" || host == "127.0.0.1" || host.hasSuffix(".local") {
            return true
        }
        let parts = host.split(separator: ".").compactMap { UInt8($0) }
        guard parts.count == 4 else { return false }
        return parts[0] == 10 ||
               (parts[0] == 172 && (16...31).contains(parts[1])) ||
               (parts[0] == 192 && parts[1] == 168)
    }

    private func request(_ path: String, method: String = "GET", contentType: String? = nil) throws -> URLRequest {
        guard let base = URL(string: server.trimmingCharacters(in: .whitespacesAndNewlines)),
              ["http", "https"].contains(base.scheme?.lowercased() ?? ""),
              base.host != nil else { throw APIError(message: "Địa chỉ máy chủ không hợp lệ") }
        guard Self.allowedServerURL(server) else {
            throw APIError(message: "Điều khiển từ xa bắt buộc sử dụng HTTPS. HTTP chỉ cho phép mạng LAN riêng.")
        }
        // Never include the access token in a URL's query or URL credentials.
        guard let url = URL(string: "/api" + path, relativeTo: base)?.absoluteURL else {
            throw APIError(message: "Không thể tạo URL")
        }
        var r = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 90)
        r.httpMethod = method
        r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let contentType { r.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        return r
    }

    private func decode<T: Decodable>(_ data: Data, _ response: URLResponse, as: T.Type) throws -> T {
        guard let http = response as? HTTPURLResponse else { throw APIError(message: "Không nhận được phản hồi HTTP") }
        if !(200...299).contains(http.statusCode) {
            let text = String(data: data, encoding: .utf8) ?? ""
            let description = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw APIError(message: description ?? "HTTP \(http.statusCode): \(text.prefix(180))")
        }
        return try decoder.decode(T.self, from: data)
    }

    func get<T: Decodable>(_ path: String, as: T.Type) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request(path))
        return try decode(data, response, as: T.self)
    }

    func post<T: Decodable, P: Encodable>(_ path: String, body: P, as: T.Type) async throws -> T {
        var r = try request(path, method: "POST", contentType: "application/json")
        r.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await URLSession.shared.data(for: r)
        return try decode(data, response, as: T.self)
    }

    func patch<T: Decodable, P: Encodable>(_ path: String, body: P, as: T.Type) async throws -> T {
        var r = try request(path, method: "PATCH", contentType: "application/json")
        r.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await URLSession.shared.data(for: r)
        return try decode(data, response, as: T.self)
    }

    func upload(_ path: String, fileURL: URL, as filename: String) async throws {
        guard fileURL.startAccessingSecurityScopedResource() else {
            throw APIError(message: "Không có quyền đọc file trong Files")
        }
        defer { fileURL.stopAccessingSecurityScopedResource() }
        let boundary = "ViePN-\(UUID().uuidString)"
        var data = Data()
        data.append(Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\nContent-Type: application/octet-stream\r\n\r\n".utf8))
        data.append(try Data(contentsOf: fileURL))
        data.append(Data("\r\n--\(boundary)--\r\n".utf8))
        let r = try request(path, method: "POST", contentType: "multipart/form-data; boundary=\(boundary)")
        let (result, response) = try await URLSession.shared.upload(for: r, from: data)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let reason = String(data: result, encoding: .utf8) ?? "Upload thất bại"
            throw APIError(message: String(reason.prefix(220)))
        }
    }

    func devices() async throws -> [DeviceInfo] {
        // pymobiledevice3 usbmux list uses Identifier / UniqueDeviceID /
        // DeviceName. Older tooling sometimes uses udid/name or nested
        // Properties. Decode all grounded variants without silently dropping.
        let (data, response) = try await URLSession.shared.data(for: request("/devices"))
        guard let http = response as? HTTPURLResponse else {
            throw APIError(message: "Máy Windows không phản hồi khi quét thiết bị.")
        }
        guard (200...299).contains(http.statusCode) else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw APIError(message: "Không tải được thiết bị (HTTP \(http.statusCode)): \(detail ?? "Kiểm tra Apple Mobile Device Service trên Windows.")")
        }
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let entries = root["devices"] as? [Any] else {
            throw APIError(message: "Danh sách thiết bị từ Windows không đúng định dạng.")
        }

        func value(_ dictionary: [String: Any], keys: [String]) -> String? {
            for key in keys {
                if let result = dictionary[key] as? String {
                    let trimmed = result.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty { return trimmed }
                }
            }
            return nil
        }
        var devices: [DeviceInfo] = []
        var seen = Set<String>()
        for entry in entries {
            let item = (entry as? [String: Any]) ?? [:]
            let properties = (item["Properties"] as? [String: Any]) ?? [:]
            let keys = ["UniqueDeviceID", "Identifier", "udid", "identifier", "serial_number", "SerialNumber", "serial"]
            let id = value(item, keys: keys)
                ?? value(properties, keys: keys)
                ?? (entry as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
            guard let udid = id, !udid.isEmpty, seen.insert(udid).inserted else { continue }
            let name = value(item, keys: ["DeviceName", "device_name", "name"])
                ?? value(properties, keys: ["DeviceName", "device_name", "name"])
                ?? "iPhone / iPad"
            devices.append(DeviceInfo(id: udid, name: name))
        }
        // Do not misrepresent a nonempty but incompatible response as no device.
        if !entries.isEmpty && devices.isEmpty {
            throw APIError(message: "Windows nhận thiết bị nhưng thiếu mã UDID phù hợp. Hãy cập nhật pymobiledevice3.")
        }
        return devices
    }
}

struct InstallBody: Encodable {
    let ipa_id: String
    let udid: String
    let auto_renew: Bool
    let resign: Bool
    let profile_id: String?
}
struct SignBody: Encodable { let ipa_id: String; let udid: String; let profile_id: String? }
struct RenewBody: Encodable { let installation_id: String }
struct EmptyBody: Encodable {}
