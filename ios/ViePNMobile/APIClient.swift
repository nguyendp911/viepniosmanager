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

    private func request(_ path: String, method: String = "GET", contentType: String? = nil) throws -> URLRequest {
        guard let base = URL(string: server.trimmingCharacters(in: .whitespacesAndNewlines)),
              ["http", "https"].contains(base.scheme?.lowercased() ?? ""),
              base.host != nil else { throw APIError(message: "Địa chỉ máy chủ không hợp lệ") }
        // Avoid leaking token to an untrusted internet endpoint by accident.
        // Users should configure HTTPS on remotely accessible servers.
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
        let r = try request("/devices")
        let (data, response) = try await URLSession.shared.data(for: r)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError(message: "Không tải được danh sách thiết bị")
        }
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let devices = root["devices"] as? [[String: Any]] else { return [] }
        return devices.compactMap { d in
            guard let udid = (d["udid"] ?? d["serial"] ?? d["serial_number"] ?? d["UniqueDeviceID"] ?? d["identifier"]) as? String else { return nil }
            let name = (d["device_name"] ?? d["name"] ?? d["DeviceName"]) as? String ?? "iPhone / iPad"
            return DeviceInfo(id: udid, name: name)
        }
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
