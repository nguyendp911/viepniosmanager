# ViePN iOS Manager 1.2 — Apple ID miễn phí, ký trực tiếp trên Windows

ViePN là công cụ Windows + web dashboard để **đọc IPA, kết nối iPhone, xác thực Apple ID miễn phí (2FA), xin provisioning profile, ký IPA, cài lên iPhone và gia hạn trước khi hết 7 ngày**. Không cần cài ứng dụng SideStore/AltStore/iLoader.

**Quan trọng:** Mã nguồn và API đã được triển khai, nhưng luồng Apple ID và ký/cài IPA **chưa được xác nhận thành công trên iPhone của bạn**. Apple dùng giao thức không công khai cho Personal Team, có thể thay đổi hoặc chặn; không nên coi đây là cam kết hoạt động liên tục. Xem [tài liệu kỹ thuật, bảo mật và giới hạn](docs/APPLE_ID_NATIVE.md).

## Cài đặt Windows (Python 3.14)

1. Cài iTunes/Apple Mobile Device Service từ Apple. Mở khóa iPhone, kết nối USB và chọn Trust This Computer.
2. Mở PowerShell trong repo:

```powershell
cd C:\ViePN-iOS-Manager
git pull origin main
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
powershell -ExecutionPolicy Bypass -File .\windows\apple-login.ps1
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
```

Nếu dùng ZIP (không có thư mục `.git`), tải bản mới từ GitHub và thay phần mã nguồn, **không xóa** `%LOCALAPPDATA%\ViePN-iOS-Manager` chứa token, IPA và phiên Apple. Khi cập nhật chương trình, dừng server cũ bằng `Ctrl+C`.

3. Mở `http://127.0.0.1:8765`. Access token dashboard nằm trong `%LOCALAPPDATA%\ViePN-iOS-Manager\access_token.txt`.
4. Tab **Apple ID miễn phí**: chọn IPA, chọn iPhone → **Ký IPA** hoặc **Ký + cài iPhone**. Theo dõi trong **Nhật ký hoạt động**. Không nhập Apple ID/password/2FA vào dashboard.

## Khởi động nhanh và xóa IPA khỏi thư viện (Windows)

Sau khi cài đặt một lần bằng `windows\setup.ps1`, bạn chỉ cần **nhấp đúp** vào file **`Start-ViePN.bat`** ở thư mục gốc dự án (ví dụ `C:\ViePN-iOS-Manager\Start-ViePN.bat`).

- Nếu ViePN đang chạy tại `http://127.0.0.1:8765`, file BAT chỉ mở dashboard.
- Nếu ViePN chưa chạy, BAT mở cửa sổ PowerShell khởi động server, sau đó mở trình duyệt.
- Giữ cửa sổ PowerShell chạy để bộ lập lịch gia hạn hoạt động.

Trong tab **Thư viện IPA**, nhấn **🗑 Xóa** bên cạnh IPA cần xóa và xác nhận. Thao tác xóa bản IPA trong thư viện Windows (SQLite + file lưu trên đĩa), **không gỡ ứng dụng khỏi iPhone**. ViePN sẽ từ chối xóa file đang được một ứng dụng theo dõi/gia hạn sử dụng hoặc đang có tác vụ ký/cài chưa hoàn thành; dữ liệu cần thiết cho việc gia hạn được giữ an toàn.

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

Không lưu mật khẩu Apple trong web hoặc GitHub; phiên đăng nhập được lưu tại `%LOCALAPPDATA%\ViePN-iOS-Manager\session` theo tài khoản Windows. Không công khai cổng TCP 8765.

## Giới hạn tài khoản miễn phí

Theo Apple, Personal Team thường giới hạn 3 ứng dụng cài trên mỗi thiết bị, 10 App IDs/7 ngày, 3 thiết bị/7 ngày và provisioning profiles hết hạn 7 ngày. Phải tạo profile mới, ký lại và cài đè; không thể gia hạn chỉ bằng đổi ngày trong IPA. IPA mã hóa FairPlay không thể ký lại. Firmware IPSW đã ngừng ký không được hỗ trợ.

## Biểu tượng ViePN trên iPhone

ViePN iOS dùng AppIcon mang logo chiếc khiên neon do chủ dự án cung cấp. Bộ asset được cấu hình trong `ios/ViePNMobile/Assets.xcassets/AppIcon.appiconset` với `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon`. GitHub Actions tạo PNG 1024×1024 từ bản ảnh nguồn tối ưu dung lượng trước khi build IPA.

Để nâng lên ảnh gốc sắc nét nhất, chép file PNG 1024×1024 tên `AppIcon-1024.png` vào thư mục asset trên và commit. CI sẽ ưu tiên file PNG này, không ghi đè. Xem [hướng dẫn icon](ios/APPICON.md).

## Cấu trúc

- `backend/viepn/native_sign.py` — đăng nhập terminal, cấp profile, ký IPA.
- `backend/viepn/applekit/` — Apple auth/GSA + developer services, MIT attribution.
- `backend/viepn/service.py` — quản lý signing jobs, cài đặt và scheduler.
- `backend/viepn/api.py` — dashboard APIs (không nhận Apple ID password).
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
