# Điều khiển ViePN iOS Manager từ iPhone qua Internet

**Kiến trúc:** Tailscale (VPN riêng) + Tailscale Serve HTTPS + gateway chỉ cho phép các API quản lý + ViePN Windows Backend. Không mở cổng router, không dùng Tailscale Funnel.

Tailscale Serve không công khai cho toàn Internet, chỉ cho các máy / thành viên được phép trong *tailnet*; vẫn cần access token ViePN như trước.

## Điều kiện

- Windows 10/11 đang bật, ViePN đã cài và chạy được với Python 3.14.
- Tailscale trên Windows: https://tailscale.com/download/windows
- Tailscale trên iPhone: https://tailscale.com/download/ios
- Cả hai thiết bị đăng nhập **cùng tailnet** và Tailscale iPhone được bật.
- Bật MagicDNS và HTTPS certificates trong Tailscale admin nếu được yêu cầu.
- App ViePN iOS mới nhất đã được ký/cài hợp lệ.

## Thiết lập Windows (một lần)

1. Tại Windows, chạy Tailscale rồi đăng nhập. Không bật Funnel và không tạo NAT/port forwarding.
2. Trong ViePN, dừng server cũ bằng Ctrl+C nếu nó đang chạy trên `0.0.0.0` hoặc nếu đã mở 8765 trên router. Chạy server trên loopback `127.0.0.1` thay vì 0.0.0.0.
3. Cập nhật mã nguồn rồi cài thêm thư viện cho gateway:

```powershell
cd C:\ViePN-iOS-Manager
git pull origin main
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
```

Nếu dự án được giải nén ZIP không có `.git`, tải ZIP của nhánh `main` và chép các thư mục mã nguồn mới vào `C:\ViePN-iOS-Manager`, giữ nguyên `%LOCALAPPDATA%\ViePN-iOS-Manager`.

4. **Nhấp đúp đúng một file `Start-ViePN.bat`** ở thư mục gốc. BAT tự kiểm tra môi trường Python, cài các thư viện còn thiếu, bật API/gateway nội bộ và Tailscale Serve HTTPS.

Script làm những việc sau:
- Kiểm tra server ViePN (127.0.0.1:8765). Nếu chưa chạy thì khởi động nó ở localhost.
- Khởi động **gateway riêng** tại 127.0.0.1:8766. Gateway KHÔNG có API quản lý Apple ID.
- Kiểm tra Tailscale Windows, rồi chạy:
  `tailscale serve --bg --https=443 http://127.0.0.1:8766`
- In URL riêng có dạng `https://ten-may.ten-tailnet.ts.net`.

**Cảnh báo:** Nếu ViePN đang mở 8765 qua `0.0.0.0` (trên mọi card mạng), script sẽ dừng và yêu cầu đóng server đó. Không tắt tường lửa Windows. Tailscale có thể yêu cầu bạn bật HTTPS tại trang quản trị trước khi Serve hoạt động.

## Thiết lập trên iPhone (một lần)

1. Cài Tailscale và đăng nhập **cùng tailnet** với Windows; bật VPN.
2. Trong Safari, mở `https://ten-may.ten-tailnet.ts.net/api/health`. Nếu thành công, bạn sẽ thấy JSON có `"ok": true`.
3. Mở ứng dụng ViePN iOS → **Kết nối** → nhập:
   - **Địa chỉ API:** `https://ten-may.ten-tailnet.ts.net` (không thêm `/api`).
   - **Access token:** lấy từ file `%LOCALAPPDATA%\ViePN-iOS-Manager\access_token.txt` trên Windows.
4. Nhấn **Lưu và kết nối**; token được lưu trong iPhone Keychain.

**Nếu mở Safari qua HTTPS:** bạn cũng có thể truy cập dashboard web từ xa. Trang login yêu cầu token giống truy cập local. Các API Apple ID login/2FA/logout bị chặn bởi gateway.

## API trên Internet

Gateway có một **allowlist** cố định và đòi Bearer token cho các API chứa dữ liệu riêng: tổng quan, thư viện IPA, trạng thái iPhone, nhập/xóa IPA, gửi lệnh ký/cài và kiểm tra gia hạn.

**Không cho phép qua gateway**:
- Đăng nhập/đăng xuất Apple ID, nhập mật khẩu, 2FA, chuyển tài khoản và quản lý phiên.
- Truy cập bất kỳ đường dẫn API nào không nằm trong allowlist.
- Truy cập file hệ thống Windows và upload các định dạng không được ViePN chấp nhận.

Muốn đăng nhập Apple ID mới hoặc xác minh lại 2FA, hãy dùng ViePN local trên Windows (`http://127.0.0.1:8765`) hoặc `windows/apple-login.ps1`. Không nhập Apple ID vào trang ViePN mở qua Tailscale.

## Gia hạn ứng dụng và giới hạn phần cứng

Kết nối từ xa cho phép **gửi lệnh** và quản lý hồ sơ/IPA. Nó **không** làm cho một iPhone nằm xa máy Windows tự xuất hiện như kết nối USB với `pymobiledevice3`.

Muốn thực sự cài/refresh IPA từ Windows, iPhone cần được kết nối USB hoặc kết nối Wi-Fi pairing mà `pymobiledevice3` nhận diện được. Nếu iPhone đang ở xa, việc cài đặt/refresh có thể thất bại dù HTTPS API vẫn hoạt động. Apple ID miễn phí còn yêu cầu cấp profile hợp lệ 7 ngày; Apple có thể yêu cầu xác minh lại.

Cần Windows bật, Tailscale Windows kết nối và gateway hoạt động. Sau khi restart máy, bạn có thể chạy lại `Start-ViePN.bat`. Cấu hình Tailscale Serve dùng `--bg` sẽ tiếp tục trên Tailscale, nhưng cả ViePN backend và gateway cũng phải chạy.

## Tự khởi động kết nối từ xa sau khi đăng nhập Windows

Sau **một lần** thiết lập Tailscale Serve thành công bằng `Start-ViePN.bat`, có thể tạo tác vụ tự chạy sau mỗi lần đăng nhập Windows:

```powershell
cd C:\ViePN-iOS-Manager
powershell -ExecutionPolicy Bypass -File .\windows\register-remote-autostart.ps1
```

Tác vụ chạy file `Start-ViePN.bat --auto` để kiểm tra/khởi chạy backend, gateway và Serve sau khi người dùng đăng nhập Windows. Đây là tác vụ theo tài khoản người dùng đã đăng nhập: nó không hoạt động nếu máy đã tắt, Windows chưa đăng nhập, máy vào Sleep hoặc tài khoản Tailscale chưa kết nối.

Để tắt tự khởi động, vào **Task Scheduler** và vô hiệu hóa `ViePN iOS Manager - Private Remote Control`; hoặc chạy:

```powershell
Unregister-ScheduledTask -TaskName "ViePN iOS Manager - Private Remote Control" -Confirm:$false
```

## Thông báo đẩy khi IPA gần hết hạn hoặc ký/gia hạn thất bại

ViePN tích hợp thông báo qua **ntfy iOS** theo cơ chế *tùy chọn và có sự đồng ý*, vì IPA ký bằng Apple ID miễn phí không mặc định có quyền APNs của Apple. Đây là ứng dụng nhận thông báo **riêng**, không phải thông báo APNs bên trong app ViePN.

- Cài ứng dụng [ntfy](https://ntfy.sh/) trên iPhone, bật thông báo.
- Trên dashboard chạy trực tiếp ở **http://127.0.0.1:8765** → **Cài đặt** → **Thông báo trên iPhone**, đồng ý sử dụng ntfy.sh và nhấn **Bật thông báo**.
- Sao chép **topic** riêng trong dashboard, trong ứng dụng ntfy nhấn **Subscribe** và nhập topic đó.
- Nhấn **Gửi thử** từ Windows. Các thông báo tự động: hết hạn trong 48 giờ, ký/cài/gia hạn thất bại, gia hạn thành công.
- Có thể nhấn **Tắt** bất kỳ lúc nào. Không cung cấp endpoint cấu hình topic qua Remote Gateway.

ViePN không gửi Apple ID, UDID, tên ứng dụng hay dữ liệu IPA lên ntfy.sh. Dịch vụ ntfy.sh nhìn thấy địa chỉ IP Windows và thông điệp trạng thái, và bất kỳ người nào biết topic cũng có thể đọc thông điệp đó. Giữ topic bí mật và không chia sẻ công khai. Máy Windows phải bật và truy cập Internet được.

## Kiểm tra và tắt kết nối từ xa

Windows PowerShell:

```powershell
tailscale status
tailscale serve status
Invoke-RestMethod http://127.0.0.1:8766/api/health
powershell -ExecutionPolicy Bypass -File .\windows\stop-remote.ps1
```

`stop-remote.ps1` tắt Serve HTTPS trên port 443, không xóa IPA hay token. Nếu bạn đang dùng Tailscale Serve HTTPS:443 cho một ứng dụng khác, hãy kiểm tra và sao lưu cấu hình trước vì lệnh này có thể ảnh hưởng dịch vụ đó.

## Chính sách bảo mật khuyến nghị

- Không dùng Tailscale Funnel, không mở port 8765/8766/443 trên router.
- Chỉ thêm những thiết bị và người dùng bạn tin tưởng vào tailnet; thắt chặt Tailscale access control rules (grants/ACLs) cho máy ViePN.
- Không đưa token, mật khẩu Apple ID, file pairing và chứng chỉ vào GitHub, email hay chat công khai.
- Thường xuyên cập nhật Tailscale và ViePN; bật khóa màn hình và bảo vệ tài khoản Windows/iPhone.
- Khi mất iPhone: thu hồi thiết bị từ trang quản lý Tailscale, đổi token ViePN và thu hồi phiên Apple nếu cần.
- Gateway chỉ phục vụ HTTPS thông qua Tailscale Serve; chạy HTTP backend/gateway trực tiếp qua LAN không an toàn.

Docs: https://tailscale.com/docs/reference/tailscale-cli/serve
