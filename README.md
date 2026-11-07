# ViePN iOS Manager 1.3 — Apple ID miễn phí, ký trực tiếp trên Windows

ViePN là công cụ Windows + web dashboard để **đọc IPA, kết nối iPhone, xác thực Apple ID miễn phí (2FA), xin provisioning profile, ký IPA, cài lên iPhone và gia hạn trước khi hết 7 ngày**. Không cần cài ứng dụng SideStore/AltStore/iLoader.

**Quan trọng:** Mã nguồn và API đã được triển khai, nhưng luồng Apple ID và ký/cài IPA **chưa được xác nhận thành công trên iPhone của bạn**. Apple dùng giao thức không công khai cho Personal Team, có thể thay đổi hoặc chặn; không nên coi đây là cam kết hoạt động liên tục. Xem [tài liệu kỹ thuật, bảo mật và giới hạn](docs/APPLE_ID_NATIVE.md).

## Cài đặt Windows (Python 3.14)

1. Cài iTunes/Apple Mobile Device Service từ Apple. Mở khóa iPhone, kết nối USB và chọn Trust This Computer.
2. Mở PowerShell trong repo:

```powershell
cd C:\ViePN-iOS-Manager
git pull origin main
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
```

Nếu dùng ZIP (không có thư mục `.git`), tải bản mới từ GitHub và thay phần mã nguồn, **không xóa** `%LOCALAPPDATA%\ViePN-iOS-Manager` chứa token, IPA và phiên Apple. Khi cập nhật chương trình, dừng server cũ bằng `Ctrl+C`.

3. Mở `http://127.0.0.1:8765`. Access token dashboard nằm trong `%LOCALAPPDATA%\ViePN-iOS-Manager\access_token.txt`.
4. Vào tab **Apple ID miễn phí** tại **http://127.0.0.1:8765**: chọn máy chủ anisette riêng hoặc đồng ý dùng dịch vụ cộng đồng, nhập Apple ID, mật khẩu và mã 2FA nếu Apple yêu cầu; sau đó chọn IPA, iPhone → **Ký IPA** hoặc **Ký + cài iPhone**. Theo dõi trong **Nhật ký hoạt động**. Chỉ nhập Apple ID khi dashboard chạy trên localhost; không đăng nhập qua mạng LAN.
5. **Đăng xuất và đăng nhập lại:** Trong cùng tab, chọn tài khoản rồi nhấn **Đăng xuất tài khoản chọn** (hoặc **Đăng xuất tất cả**). Khi cần dùng lại, nhập Apple ID và 2FA nếu được yêu cầu. Dữ liệu IPA và bản cài vẫn được giữ nguyên. Có thể dùng nút **Chuyển tài khoản** để chọn Apple ID đã lưu phiên; không cần đăng nhập lại nếu phiên còn hiệu lực.

Nếu không muốn nhập tài khoản trong trình duyệt, cách nhập 2FA bằng PowerShell vẫn được hỗ trợ: `powershell -ExecutionPolicy Bypass -File .\windows\apple-login.ps1`.

## Khởi động nhanh và xóa IPA khỏi thư viện (Windows)

Sau khi cài đặt một lần bằng `windows\setup.ps1`, bạn chỉ cần **nhấp đúp** vào file **`Start-ViePN.bat`** ở thư mục gốc dự án (ví dụ `C:\ViePN-iOS-Manager\Start-ViePN.bat`).

- Nếu ViePN đang chạy tại `http://127.0.0.1:8765`, file BAT chỉ mở dashboard.
- Nếu ViePN chưa chạy, BAT mở cửa sổ PowerShell khởi động server, sau đó mở trình duyệt.
- Giữ cửa sổ PowerShell chạy để bộ lập lịch gia hạn hoạt động.

Trong tab **Thư viện IPA**, nhấn **🗑 Xóa** bên cạnh IPA cần xóa và xác nhận. Thao tác xóa bản IPA trong thư viện Windows (SQLite + file lưu trên đĩa), **không gỡ ứng dụng khỏi iPhone**. ViePN sẽ từ chối xóa file đang được một ứng dụng theo dõi/gia hạn sử dụng hoặc đang có tác vụ ký/cài chưa hoàn thành; dữ liệu cần thiết cho việc gia hạn được giữ an toàn.

## Điều khiển ViePN từ iPhone qua Internet (Private Remote)

ViePN có gateway riêng tại `127.0.0.1:8766` chỉ cho phép các API điều khiển đã được kiểm tra. Tailscale Serve tạo URL HTTPS nội bộ tailnet, **không mở cổng 8765/8766 công khai** và không cần mở port trên router.

1. Cài [Tailscale cho Windows](https://tailscale.com/download/windows) và [Tailscale cho iPhone](https://tailscale.com/download/ios), đăng nhập cùng tailnet.
2. Cập nhật ViePN, chạy `windows\setup.ps1` để cài `httpx` và thư viện mới.
3. Nhấp đúp **`Start-ViePN-Remote.bat`**. Script bảo đảm API Windows chỉ nghe localhost, khởi động gateway rồi bật Tailscale Serve HTTPS. Có thể cần bật MagicDNS và HTTPS certificates trong Tailscale admin.
4. Sao chép URL dạng `https://may-tinh.tailnet.ts.net`. Trong ứng dụng iOS → **Kết nối** → nhập URL này và access token ViePN từ Windows.
5. Điều khiển trạng thái, quản lý IPA, tạo tác vụ ký/cài và gia hạn khi iPhone có Internet và Tailscale VPN đang bật.

**Giới hạn:** Các thao tác đăng nhập/đăng xuất Apple ID, mật khẩu và 2FA **không được cung cấp qua gateway từ xa**; chỉ thao tác trên máy Windows local. Lệnh ký/cài từ xa cần iPhone được Windows nhận diện bằng USB hoặc pairing Wi-Fi; VPN không thay thế kết nối thiết bị để cài IPA. Máy Windows, gateway và Tailscale phải chạy thì điều khiển từ xa mới hoạt động.

Tắt kết nối từ xa: `powershell -ExecutionPolicy Bypass -File .\windows\stop-remote.ps1`.

Xem **[hướng dẫn chi tiết và xử lý lỗi](docs/REMOTE_ACCESS.md)**. Không dùng Tailscale Funnel (chế độ công khai Internet).

## Tự gia hạn

- ViePN quét ứng dụng đang bật Auto Renew mỗi 30 phút, ký lại và cài đè khi còn 48 giờ.
- Để server tự chạy khi đăng nhập Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\register-auto-renew.ps1
```

- **PC phải đang bật**, iPhone kết nối USB hoặc Wi-Fi đã ghép đôi, phiên Apple còn hiệu lực. Nếu máy tắt, iPhone không truy cập được hoặc Apple đòi 2FA lại thì không thể bảo đảm gia hạn. Không có cách hợp lệ để đặt hạn chữ ký vĩnh viễn bằng Apple ID miễn phí.

## Truy cập Apple/anisette và sự độc lập

Việc giao tiếp Apple Developer Services sử dụng mã nguồn tích hợp ngay trong ViePN, không yêu cầu một ứng dụng ký riêng. Một phần mã xác thực GSA và cấp profile được phái sinh từ nguồn MIT [iPASide](https://github.com/pwnapplehat/iPASide), kèm [license và ghi công](backend/viepn/applekit/NOTICE.md). Ký IPA được thực hiện bằng thư viện Python `ipasign` hoặc zsign nếu cấu hình fallback.

**Anisette kiểu Mac** vẫn cần để xác thực tài khoản. Theo những thay đổi Apple gần đây, không thể đảm bảo Windows tự tạo anisette được Apple chấp nhận mà không có Mac. ViePN yêu cầu bạn chọn **máy chủ riêng của bạn** hoặc **đồng ý rõ ràng** cho phép dùng nhà cung cấp anisette cộng đồng; không âm thầm gửi kết nối. Dịch vụ cộng đồng không nhận mật khẩu, mã 2FA hoặc token Apple, nhưng thấy IP/định danh thiết bị được cấp. Không có chọn lựa nào thì đăng nhập sẽ dừng an toàn. Vậy nên **đây chưa phải giải pháp 100% tự chủ toàn bộ dịch vụ từ Windows**.

Mật khẩu Apple chỉ được giữ tạm trong bộ nhớ backend để hoàn tất 2FA (tối đa 5 phút) và không được lưu trong SQLite; không lưu mật khẩu vào GitHub. Trang đăng nhập chỉ hoạt động khi server bind localhost và URL browser cũng là localhost; phiên xác thực Apple được lưu tại `%LOCALAPPDATA%\ViePN-iOS-Manager\session` theo tài khoản Windows. Không công khai cổng TCP 8765.

## Giới hạn tài khoản miễn phí

Theo Apple, Personal Team thường giới hạn 3 ứng dụng cài trên mỗi thiết bị, 10 App IDs/7 ngày, 3 thiết bị/7 ngày và provisioning profiles hết hạn 7 ngày. Phải tạo profile mới, ký lại và cài đè; không thể gia hạn chỉ bằng đổi ngày trong IPA. IPA mã hóa FairPlay không thể ký lại. Firmware IPSW đã ngừng ký không được hỗ trợ.

## Biểu tượng ViePN trên iPhone

ViePN iOS dùng AppIcon mang logo chiếc khiên neon do chủ dự án cung cấp. Bộ asset được cấu hình trong `ios/ViePNMobile/Assets.xcassets/AppIcon.appiconset` với `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon`. GitHub Actions tạo PNG 1024×1024 từ bản ảnh nguồn tối ưu dung lượng trước khi build IPA.

Để nâng lên ảnh gốc sắc nét nhất, chép file PNG 1024×1024 tên `AppIcon-1024.png` vào thư mục asset trên và commit. CI sẽ ưu tiên file PNG này, không ghi đè. Xem [hướng dẫn icon](ios/APPICON.md).

## Cấu trúc

- `backend/viepn/native_sign.py` — đăng nhập terminal, cấu hình anisette, cấp profile, ký IPA.
- `backend/viepn/apple_auth.py` — quản lý đăng nhập lại, 2FA, chuyển tài khoản và đăng xuất cục bộ qua API localhost.
- `backend/viepn/applekit/` — Apple auth/GSA + developer services, MIT attribution.
- `backend/viepn/service.py` — quản lý signing jobs, cài đặt và scheduler.
- `backend/viepn/api.py` — dashboard APIs; các endpoint tài khoản nhạy cảm chỉ cho localhost có access token và cùng Origin.
- `backend/viepn/remote_gateway.py` — gateway chỉ cho phép API đã xác định, có token, chặn truy cập Apple ID/2FA từ xa.
- `backend/remote_run.py` — chạy gateway trên 127.0.0.1:8766.
- `Start-ViePN-Remote.bat` — thiết lập kết nối HTTPS riêng qua Tailscale Serve.
- `web/index.html` — dashboard và tab Apple ID miễn phí.
- `windows/apple-login.ps1` — đăng nhập Apple ID/2FA tại máy tính.
- `windows/register-auto-renew.ps1` — tạo Windows Scheduled Task.
- `ios/` — SwiftUI companion quản lý Windows, không thể tự ký/cài IPA trong sandbox.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

GitHub Actions gồm backend tests, JavaScript syntax check, iOS unsigned build. Kết quả unit tests không thay thế kiểm chứng ký/cài trên một thiết bị thật.

Project độc lập với Apple Inc. và không được Apple chứng nhận.
