# ViePN iOS Manager 2.3.0 — Ad Hoc Certificate Manager + HTTPS OTA

## Những gì đã triển khai

- Import P12 + mobileprovision **trực tiếp trên Windows** qua `Import-ViePN-Certificate.bat`. Password được nhập ẩn, chỉ lưu dưới dạng Windows DPAPI cho tài khoản đang đăng nhập. P12 gốc vẫn giữ mã hóa PKCS#12.
- Kiểm tra khóa riêng P12 khớp chứng chỉ, chứng chỉ đó có trong profile, ngày hết hạn, Team ID, App ID, loại Ad Hoc và danh sách thiết bị. **Không xác thực chữ ký CMS của profile chỉ bằng bộ phân tích metadata**; iOS vẫn là nơi quyết định chữ ký IPA có được tin cậy.
- `POST /api/adhoc/sign` cho phép ký bằng chứng chỉ đã nhập **qua Tailscale**, không cần cáp: thiết bị được lấy từ profile của Apple theo số thứ tự, không nhận UDID tùy ý từ Internet.
- `GET /api/certificates/status` chỉ trả về thông tin an toàn, không trả P12, mật khẩu, khóa riêng hoặc toàn bộ UDID.
- `POST /api/ota/prepare` chỉ tạo liên kết cho IPA có profile Ad Hoc phù hợp đúng chứng chỉ và thiết bị; yêu cầu hostname HTTPS `.ts.net`. Link `itms-services` kèm manifest và IPA có token ngẫu nhiên, giới hạn 10 phút và lượt tải.
- Web: **Cài đặt → Ad Hoc Certificate Manager / Cài Ad Hoc OTA**; app iPhone: **Thư viện IPA → Ad Hoc OTA**.
- Bản Windows Portable không đóng gói P12, profile hoặc mật khẩu của người dùng. Không có endpoint từ xa nào cho upload P12.

## Hướng dẫn áp dụng cho hai file cert.p12 + cert.mobileprovision của bạn

1. Cập nhật bộ cài Windows `2.3.0`. Dừng ViePN trước khi cập nhật rồi mở lại `Start-ViePN.bat`.
2. Đặt hai file gốc trong `C:\ViePN-iOS-Manager\` (hoặc nhập đường dẫn qua BAT), rồi nhấp đúp:
   `C:\ViePN-iOS-Manager\Import-ViePN-Certificate.bat`
3. Nhập mật khẩu **trực tiếp tại cửa sổ Windows**, không nhắn mật khẩu trong ChatGPT, không tải file P12 lên GitHub hoặc iPhone.
4. ViePN sẽ kiểm tra chúng có khớp nhau và còn hạn hay không. Nếu thất bại, dừng ký và kiểm tra lại mật khẩu/loại chứng chỉ. Đừng xóa bản gốc trước khi có một bản sao lưu offline an toàn.
5. Bật Tailscale trên iPhone và Windows. Trong **Thư viện**, chọn IPA có Bundle ID phù hợp với profile, nhấn **Ký IPA Ad Hoc không cần USB**. Chờ tác vụ thành công và làm mới Thư viện.
6. Chọn **bản IPA mới đã ký**, chọn thiết bị trong Ad Hoc profile rồi nhấn **Tạo liên kết cài OTA**. Mở liên kết `itms-services://` trên chính iPhone có UDID được cấp phép, đồng ý cài.
7. Nếu trình cài trên iPhone báo không hợp lệ, kiểm tra profile, bundle, entitlements và chữ ký thực tế. **CI build thành công không có nghĩa iPhone sẽ chấp nhận IPA.**

## Giới hạn quan trọng

- Profile Ad Hoc **không phải giấy phép ký mọi bundle ID**. Profile người dùng cung cấp có một App ID cụ thể và một thiết bị; chỉ IPA/thiết bị khớp mới dùng được.
- IPA có Keyboard Extension / .appex cần **profile Ad Hoc riêng cho từng extension**. ViePN 2.3 chặn ký lại extension chỉ bằng main-app profile, không xóa extension để lách lỗi. OTA chỉ hỗ trợ IPA đã ký với profile riêng hợp lệ cho từng extension.
- Chứng chỉ có thể còn hạn dài nhưng **profile mới và quyền thiết bị** vẫn phải được cập nhật thông qua Apple khi cần.
- iOS có thể chặn phương thức OTA trong một số hoàn cảnh (trust, VPN, device management, entitlement hoặc chính sách). Tailscale, BLE và chứng chỉ P12 không cho phép bỏ qua xác minh Apple.
- Các liên kết OTA là **bearer capabilities** có hạn ngắn, không công khai chia sẻ.
- Dịch vụ phân phối HTTPS và các quy tắc bảo mật phải hoạt động trong tailnet riêng; không bật Funnel.
- Không có lời hứa rằng chứng chỉ P12 và profile khớp nhau trước khi người dùng nhập mật khẩu P12 trên Windows.
- Windows gọi zsign bằng CLI hiện tại; mật khẩu có thể xuất hiện trong danh sách đối số tiến trình trong thời gian ký. Chỉ chạy dưới tài khoản Windows tin cậy, không chạy trên máy Windows dùng chung.

## Kiểm thử

- Mẫu chứng chỉ và profile **tổng hợp**, không phải khóa thực của người dùng.
- Unit test: P12/password, certificate mismatch, Ad Hoc scope, HTTPS ts.net validation, OTA token expiry, API authentication.
- GitHub Actions: backend tests, web syntax, Windows installer smoke, build IPA unsigned và checksum. Không upload khóa riêng, P12 hay Apple session lên CI.
