# Kiến trúc và mức bảo đảm

1. **API** FastAPI có bearer token, chạy `127.0.0.1` mặc định; giao diện web cùng origin.
2. **Kho dữ liệu** SQLite lưu IPA, profile, trạng thái cài, jobs và events trên Windows. P12 và password chỉ cấu hình qua đường dẫn/biến môi trường.
3. **Adapter thiết bị** gọi `pymobiledevice3` không qua shell, trích lỗi stdout/stderr có giới hạn.
4. **Signing adapter** gọi `zsign` tạo IPA mới. Metadata profile được kiểm tra trước, iOS kiểm chứng chữ ký thực tế.
5. **Renewal scheduler** quét 30 phút/lần; nếu còn dưới 48 giờ sẽ xếp job ký/cài. Nó chỉ thành công khi tồn tại profile mới hợp lệ, khả năng kết nối iPhone và chứng chỉ còn hiệu lực. Nếu không, ghi `needs_attention`.
6. **SwiftUI** chỉ truy cập API Windows, không có quyền cài IPA trực tiếp trong sandbox. Token lưu Keychain.
7. **CI** chạy pytest và build IPA chưa ký; không chứa/chạy với bất kỳ private key nào.

## Bảo mật

- Mặc định không mở dịch vụ ra Internet. Khi dùng LAN, cấu hình firewall giới hạn dải IP và HTTPS reverse proxy.
- Token cấp toàn quyền cho API; đổi token nếu thất lạc. Không gửi token qua HTTP trên Wi-Fi không tin cậy.
- Không upload IPA từ nguồn không rõ. Chỉ cài ứng dụng mà bạn có quyền sử dụng.
- iOS không cung cấp bảo đảm refresh chính xác theo phút; việc gia hạn phụ thuộc truy cập thiết bị và profile mới.

## Các phần cần phát triển tiếp để sản xuất

Chạy thực tế trên thiết bị, hỗ trợ profile CMS nhị phân và xác minh cryptographic signature, secret vault cho P12, API TLS/role-based access, credential-safe signing, build có chữ ký, và chiến lược cấp profile tự động **được Apple hỗ trợ**. Không coi những phần này đã hoàn thiện.
