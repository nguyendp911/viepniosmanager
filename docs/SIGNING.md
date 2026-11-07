# Ký ứng dụng hợp lệ

**Không có cách hợp lệ để bỏ qua cơ chế kiểm tra chữ ký ứng dụng iOS trên máy nguyên bản.** Công cụ dùng `zsign` cùng chứng chỉ P12 và provisioning profile do Apple cấp tương ứng với app/thiết bị.

## Cần chuẩn bị

1. Một app/IPA được phép ký và sử dụng.
2. Chứng chỉ phát triển/phân phối và khóa riêng xuất ra `.p12` của chính bạn. Lưu an toàn, không upload lên GitHub hoặc server không tin cậy.
3. Một `.mobileprovision` còn hiệu lực, có App ID/bundle ID phù hợp, thiết bị UDID nằm trong danh sách được phép (với profile phát triển/ad hoc).
4. `zsign` phiên bản phù hợp với Windows và `pymobiledevice3`, cũng như iTunes/Apple Mobile Device Service.

Mở PowerShell tại repo, thiết lập biến môi trường P12, password, zsign và profile theo README. Sau đó tải IPA qua dashboard, chọn thiết bị và **Ký lại bằng P12/profile**.

Để tự gia hạn, công cụ kiểm tra profile mới đã nhập vào thư viện. Nếu profile hết hạn sau 7 ngày, bản profile mới phải được cấp qua cơ chế Apple/Xcode hoặc công cụ hợp lệ bên ngoài rồi nhập lại. Scheduler sẽ không giả mạo profile hoặc tạo chữ ký không hợp lệ.

### Xử lý lỗi thường gặp

- **No newer, valid ... profile**: tải lên profile mới, kiểm tra ngày hết hạn, bundle ID và UDID.
- **P12 or .mobileprovision file missing**: kiểm tra đường dẫn các biến môi trường.
- **Exit ... install**: mở khóa iPhone, bật Developer Mode khi cần, chọn Trust, kiểm tra chứng chỉ và entitlements. Xem lỗi nguyên bản của công cụ thiết bị trong job.
- **Unable to determine signature expiration**: IPA không có profile nhúng dạng có thể phân tích. Hãy ký lại.

Tài liệu: https://developer.apple.com/help/account/provisioning-profiles/create-a-development-provisioning-profile
