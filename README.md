# ViePN iOS Manager

Công cụ quản lý **IPA và iPhone/iPad của chính bạn** trên Windows, kèm dashboard web và ứng dụng điều khiển iOS bằng SwiftUI. Hỗ trợ quy trình Apple ID miễn phí thông qua SideStore.

**Trạng thái:** mã nguồn triển khai được và có kiểm thử backend; **chưa được thử trực tiếp trên iPhone thật trong môi trường này**. GitHub Actions xây dựng bản **IPA chưa ký** để ký bằng chứng chỉ/provisioning profile hợp lệ của bạn.

## Apple ID miễn phí (ký và gia hạn 7 ngày)

**Đã có chế độ riêng trong dashboard: `Apple ID miễn phí`.** Không cần P12 hoặc zsign cho chế độ này.

1. Cài iLoader và SideStore theo [hướng dẫn SideStore chính thức](https://docs.sidestore.io/docs/installation/install). Đăng nhập Apple Account **trực tiếp trong iLoader/SideStore**, không nhập Apple ID hay mật khẩu vào ViePN.
2. Mở trang `http://127.0.0.1:8765`, đăng nhập bằng access token ViePN, chọn **Apple ID miễn phí**.
3. Chọn IPA, bấm **Tải IPA về Windows** để chuyển bằng iCloud Drive/Files, hoặc chọn **Tạo liên kết Wi-Fi** để chuyển qua mạng nội bộ.
4. Trên iPhone, nhập IPA vào SideStore để ký/cài; vào **My Apps → Refresh All** trước khi hết 7 ngày.

**Phân biệt trách nhiệm:** ViePN giúp chuẩn bị/chuyển IPA và quản lý thư viện, **không tự đăng nhập Apple hay tự ký/gia hạn bằng Apple ID**. SideStore là thành phần thực hiện ký và refresh. Gia hạn nền có thể không luôn thành công. Với Apple Account miễn phí thường giới hạn tối đa 3 app đang cài, tính cả SideStore. Xem [hướng dẫn đầy đủ và bảo mật liên kết Wi-Fi](docs/FREE_APPLE_ID.md).

### Chuyển IPA qua Wi-Fi

Chỉ bật API trên mạng LAN riêng đáng tin và giới hạn Windows Firewall **Private**:

```powershell
cd C:\ViePN-iOS-Manager
$env:VIEPN_HOST = '0.0.0.0'
.\windows\start.ps1
```

Dùng `ipconfig` để xem IPv4 Windows, nhập địa chỉ đó trong tab **Apple ID miễn phí**. Link IPA có hiệu lực 10 phút, tải một lần, không chứa token quản trị; ai có link vẫn tải được IPA trước khi hết hạn. **Không mở cổng 8765 ra Internet.**

## Chức năng

- Thư viện IPA: tải lên, kiểm tra `Info.plist`, bundle ID, phiên bản và ngày hết hạn profile nhúng.
- Quản lý thiết bị: liệt kê các iPhone được ghép đôi qua Apple Mobile Device Service / `pymobiledevice3`.
- Ký IPA dùng **P12 + `.mobileprovision` hợp lệ** với `zsign` và cài đặt qua USB/Wi-Fi bằng `pymobiledevice3`.
- Theo dõi ứng dụng đã cài, lịch sử tác vụ và lỗi; kiểm tra gia hạn tự động trước hạn mặc định 48 giờ.
- Khi có **profile mới hơn và đúng thiết bị/bundle**, tự xếp tác vụ ký lại và cài đè. Nếu không có profile mới, báo cần can thiệp — **không tự cấp profile Apple từ tài khoản miễn phí**.
- Ứng dụng SwiftUI gửi lệnh quản lý đến Windows qua API có bearer token, lưu token bằng iOS Keychain.

## Bắt đầu từ Windows

1. Cài **Python 3.10 trở lên** (có thể dùng Python 3.14) và [iTunes bản cho Windows từ Apple](https://www.apple.com/itunes/) để có dịch vụ Apple Mobile Device Service. Mở khóa iPhone, kết nối USB và chọn **Trust This Computer**.
2. Mở PowerShell tại thư mục repo, chạy:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
   powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
   ```

3. Mở `http://127.0.0.1:8765` trên Windows. Token đăng nhập nằm trong `%LOCALAPPDATA%\ViePN-iOS-Manager\access_token.txt` (không gửi cho người khác).
4. Kết nối iPhone qua USB và kiểm tra mục **Thiết bị**. Nếu không thấy iPhone, kiểm tra iTunes/Apple Mobile Device Service, nút Trust và cáp USB.
5. Nhập IPA, P12 và profile hợp lệ theo [hướng dẫn ký](docs/SIGNING.md), cài từ dashboard hoặc ứng dụng iPhone.

Để chạy thủ công (không dùng PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe backend\run.py
```

## Python 3.14 / Windows PowerShell 5.1

Hai script trong `windows/` chỉ dùng ký tự ASCII để tránh lỗi mã hóa khi chạy bằng Windows PowerShell 5.1. `setup.ps1` tự phát hiện bản Python 3 mới nhất thông qua `py -3` (hoặc dùng `python` nếu không có launcher), không ép dùng 3.12.

Để dùng Python 3.14 thủ công:

```powershell
cd C:\ViePN-iOS-Manager
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe backend\run.py
```

Nếu `py -3.14` không hoạt động, dùng `py --list-paths` để kiểm tra các phiên bản Python. Cài đặt thư viện có thể phát sinh lỗi riêng tùy cấu hình Windows và phiên bản dependency; khi đó hãy gửi toàn bộ lỗi `pip install` để chẩn đoán.

## Cấu hình ký (PowerShell)

```powershell
$env:VIEPN_SIGN_P12 = 'C:\\Certificates\\my-dev.p12'
$env:VIEPN_SIGN_PROFILE = 'C:\\Certificates\\my-app.mobileprovision'
$env:VIEPN_SIGN_PASSWORD = 'your-local-p12-password'
$env:VIEPN_ZSIGN = 'C:\\Tools\\zsign.exe'
.\windows\start.ps1
```

Đừng commit bất kỳ `.p12`, `.mobileprovision`, access token, UDID cá nhân hay mật khẩu nào vào GitHub. Có thể nhập `.mobileprovision` thông qua dashboard/API. Trường hợp tải IPA **chưa ký**, hãy bật tùy chọn **Ký lại** khi cài.

## iPhone client / CI

- `ios/project.yml` là cấu hình XcodeGen. Trên macOS: `brew install xcodegen`, rồi `cd ios && xcodegen generate`.
- GitHub Actions (macOS runner) build bản `ViePNMobile-UNSIGNED.ipa`, có thể tải ở phần **Actions → workflow run → Artifacts**. Đây **không phải IPA cài được ngay**.
- Khi muốn kết nối iPhone tới Windows, chạy backend với `VIEPN_HOST=0.0.0.0` **chỉ trên mạng nội bộ tin cậy**, cho phép cổng TCP 8765 trong Windows Firewall. Tốt nhất đặt phía sau HTTPS reverse proxy với xác thực/truy cập giới hạn. Không mở trực tiếp 8765 ra Internet.
- Ứng dụng iOS đóng vai trò **điều khiển Windows**; nó không tự cài IPA từ quyền sandbox ứng dụng thông thường, cũng không thay thế SideStore.

## Các giới hạn quan trọng

- Apple Personal Team miễn phí cấp profile có hạn **7 ngày**, giới hạn số App ID, thiết bị và app. Ký lại muốn gia hạn thực sự cần **profile mới được cấp hợp lệ**, không thể chỉ sửa thời gian trong IPA. Xem [Apple Developer](https://developer.apple.com/help/account/basics/about-your-developer-account).
- Để gia hạn **không cần Windows sau lần đầu**, nên sử dụng **SideStore** như một luồng riêng (không được tích hợp giả vào ứng dụng này).
- IPA chưa ký có thể ký nếu hợp lệ, nhưng firmware iOS IPSW đã ngừng được Apple ký không thể cài bằng công cụ này.
- Cài đè thường giữ dữ liệu khi bundle ID và quyền ký tương thích; luôn sao lưu thiết bị trước khi thử với IPA quan trọng.
- Kiểm tra profile nhúng chỉ là kiểm tra metadata, không chứng minh chữ ký đúng: iOS quyết định tính hợp lệ khi cài.

## Kiểm thử

```powershell
py -3 -m pip install -r backend/requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `backend/viepn` | FastAPI, SQLite, IPA parser, signing/install worker, scheduler |
| `backend/tests` | Unit/integration tests không yêu cầu iPhone |
| `web` | Dashboard HTML/JS chạy offline cùng API |
| `ios` | Mã SwiftUI và XcodeGen |
| `windows` | PowerShell thiết lập/chạy trên Windows |
| `docs` | Hướng dẫn ký và kiến trúc |

Phát triển độc lập, không liên kết với Apple, AltStore hoặc SideStore.
