## ViePN 2.3.0 — Certificate Manager và Ad Hoc OTA không dây

**Đã thêm quy trình chứng chỉ Distribution/Ad Hoc**: import P12 và .mobileprovision ngay trên Windows bằng `Import-ViePN-Certificate.bat`, xác minh cặp khóa–chứng chỉ–profile, lưu mật khẩu dưới Windows DPAPI. P12 và mật khẩu **không tải lên GitHub hay Tailscale**.

Trong app iPhone và dashboard Windows, chọn IPA → **Ký Ad Hoc không cần USB** → sau khi ký xong chọn IPA đã ký → tạo liên kết **HTTPS OTA** có hạn 10 phút. Liên kết chỉ tạo được khi IPA và thiết bị nằm trong phạm vi profile của Apple. iOS có thể từ chối nếu code signature, trust, entitlements hoặc cài đặt HTTPS chưa hợp lệ. Phần này không biến Bluetooth thành giao thức cài IPA.

Với IPA có Keyboard Extension, cần profile Ad Hoc riêng cho từng extension; không dùng profile app chính để ký chồng. Đọc [hướng dẫn ViePN 2.3.0](docs/RELEASE_2_3_0.md).

## ViePN 2.2 — Kết nối không dây Tailscale + Bluetooth

**Không cần cáp để iPhone xuất hiện trong danh sách ViePN.** Khi ứng dụng iOS kết nối Tailscale HTTPS, thiết bị tự đăng ký với Windows và hiển thị trong tab **Thiết bị từ xa**. Trên iPhone: **Kết nối → Kết nối không dây ViePN → Đăng ký iPhone**.

Nếu muốn phát hiện thiết bị ở gần qua **Bluetooth BLE**, cài thư viện quét tùy chọn bằng `windows\Enable-ViePN-Bluetooth.bat` (Windows cần adapter BLE), rồi bật **Phát Bluetooth ViePN** trên iPhone khi app đang mở. Windows có nút **Quét Bluetooth gần Windows**.

Trong phần **Thư viện IPA**, danh sách thiết bị phân biệt rõ **Tailscale** và **Apple USB/Wi-Fi pairing**. Tailscale/BLE giúp đăng ký, phát hiện và điều khiển ViePN từ xa, **không cấp quyền cài IPA qua giao thức Apple**. Đối với thiết bị chỉ đăng ký từ xa, nút cài trực tiếp được khóa để tránh hiểu nhầm; bản 2.3 đã bổ sung cài OTA cho các IPA có profile Ad Hoc hợp lệ, nhưng vẫn không thay thế Apple pairing cho lệnh usbmux.

Xem hướng dẫn và giới hạn tại [ViePN 2.2.0 — Remote + Bluetooth BLE](docs/RELEASE_2_2_0.md).

# ViePN iOS Manager 2.3.0 — Apple ID và Ad Hoc trên Windows

ViePN là công cụ Windows + web dashboard để **đọc IPA, kết nối iPhone, xác thực Apple ID miễn phí (2FA), xin provisioning profile, ký IPA, cài lên iPhone và gia hạn trước khi hết 7 ngày**. Không cần cài ứng dụng SideStore/AltStore/iLoader.

**Quan trọng:** Mã nguồn và API đã được triển khai, nhưng luồng Apple ID và ký/cài IPA **chưa được xác nhận thành công trên iPhone của bạn**. Apple dùng giao thức không công khai cho Personal Team, có thể thay đổi hoặc chặn; không nên coi đây là cam kết hoạt động liên tục. Xem [tài liệu kỹ thuật, bảo mật và giới hạn](docs/APPLE_ID_NATIVE.md).

## Tự cập nhật bằng một file BAT (Windows + iOS IPA)

Từ **ViePN 2.1.2**, nhấp đúp **`C:\ViePN-iOS-Manager\Update-ViePN.bat`**:

1. Truy vấn **GitHub Releases → latest stable** của `nguyendp911/viepniosmanager`, không tải nhánh main chưa kiểm thử.
2. Tự tải `ViePN-Windows-Portable-VERSION.zip` và `.sha256`, kèm `ViePNMobile-VERSION-UNSIGNED.ipa` và `.sha256`.
3. Kiểm tra **cả hai SHA-256**, giải nén ZIP vào thư mục tạm và kiểm tra manifest/version. Nếu lỗi, **không sửa nguồn ViePN đang dùng**.
4. Nếu backend/gateway đang chạy, chỉ dừng các tiến trình Python nhận diện là ViePN trong thư mục cài đặt sau khi kiểm tra **không có tác vụ ký/cài/gia hạn hoạt động**. Nếu tiến trình không xác định được hoặc không đọc được danh sách tác vụ, hủy cập nhật thay vì dừng nhầm.
5. Gọi bộ cài có kiểm tra checksum từng file và sao lưu mã nguồn cũ vào `C:\ViePN-iOS-Manager\code-backups` trước khi ghi đè mã nguồn.
6. Lưu IPA unsigned có tên phiên bản trong **`C:\ViePN-iOS-Manager\IPA\ViePNMobile-VERSION-UNSIGNED.ipa`**. Không xóa IPA cũ hay dữ liệu trong `%LOCALAPPDATA%\ViePN-iOS-Manager`.
7. Chạy lại `Start-ViePN.bat` sau khi cập nhật. IPA unsigned **cần ký trước khi cài trên iPhone**.

**Lần đầu:** nếu bản ViePN hiện tại chưa có `Update-ViePN.bat`, hãy tải và giải nén bộ Windows Portable 2.1.2, chạy `Install-ViePN.bat` **một lần** để nhận nút cập nhật tự động. Từ những lần sau chỉ cần một file BAT.

Không cần mở cổng mạng hoặc bật Tailscale Funnel; updater chỉ tải bản phát hành từ trang GitHub chính thức. Không tắt Defender hoặc bypass kiểm tra checksum.

## Cài đặt Windows (Python 3.14)

1. Cài iTunes/Apple Mobile Device Service từ Apple. Mở khóa iPhone, kết nối USB và chọn Trust This Computer.
2. Mở PowerShell trong repo:

```powershell
cd C:\ViePN-iOS-Manager
git pull origin main
Start-ViePN.bat
```

Nếu dùng ZIP (không có thư mục `.git`), tải bản mới từ GitHub và thay phần mã nguồn, **không xóa** `%LOCALAPPDATA%\ViePN-iOS-Manager` chứa token, IPA và phiên Apple. Khi cập nhật chương trình, dừng server cũ bằng `Ctrl+C`.

3. Mở `http://127.0.0.1:8765`. Access token dashboard nằm trong `%LOCALAPPDATA%\ViePN-iOS-Manager\access_token.txt`.
4. Vào tab **Apple ID miễn phí** tại **http://127.0.0.1:8765**: chọn máy chủ anisette riêng hoặc đồng ý dùng dịch vụ cộng đồng, nhập Apple ID, mật khẩu và mã 2FA nếu Apple yêu cầu; sau đó chọn IPA, iPhone → **Ký IPA** hoặc **Ký + cài iPhone**. Theo dõi trong **Nhật ký hoạt động**. Chỉ nhập Apple ID khi dashboard chạy trên localhost; không đăng nhập qua mạng LAN.
5. **Đăng xuất và đăng nhập lại:** Trong cùng tab, chọn tài khoản rồi nhấn **Đăng xuất tài khoản chọn** (hoặc **Đăng xuất tất cả**). Khi cần dùng lại, nhập Apple ID và 2FA nếu được yêu cầu. Dữ liệu IPA và bản cài vẫn được giữ nguyên. Có thể dùng nút **Chuyển tài khoản** để chọn Apple ID đã lưu phiên; không cần đăng nhập lại nếu phiên còn hiệu lực.

Nếu không muốn nhập tài khoản trong trình duyệt, cách nhập 2FA bằng PowerShell vẫn được hỗ trợ: `powershell -ExecutionPolicy Bypass -File .\windows\apple-login.ps1`.

## Nâng cấp 1.6 đến 2.1 — Sao lưu, Build Manager, Retry, iOS 2.0, Windows Portable

Đã bổ sung **Connection Doctor**, sao lưu ZIP kèm SHA-256 trước khi xóa hàng loạt, phục hồi offline, nhóm Dev/Test/Stable/Archive, lọc và tìm bản build, giới hạn retry ký/gia hạn và giao diện iPhone mới.

**Bản Windows Portable 2.1:** Mở [GitHub Actions](https://github.com/nguyendp911/viepniosmanager/actions), chọn build mới nhất đạt kiểm thử và tải artifact `ViePN-Windows-Portable-2.1`. Giải nén ZIP, xác minh SHA256, nhấp đúp `Install-ViePN.bat` để kiểm tra gói trước khi cập nhật mã nguồn tại `C:\ViePN-iOS-Manager`. Dừng các cửa sổ ViePN trước khi cập nhật. Dữ liệu IPA/token/Apple session trong `%LOCALAPPDATA%\ViePN-iOS-Manager` không bị ghi đè. Sau đó nhấp đúp `Start-ViePN.bat`.

**Lưu ý:** Đây là bộ cài ZIP/PowerShell, **không phải EXE/MSI đã ký số**. IPA GitHub Actions là bản **unsigned**: cần ký trước khi cài lên iPhone. Xem [toàn bộ lộ trình, hạn chế thực tế và hướng dẫn rollback](docs/ROADMAP_1_6_TO_2_1.md).

## Khởi động nhanh và xóa IPA khỏi thư viện (Windows)

Bạn chỉ cần **nhấp đúp một file duy nhất: `Start-ViePN.bat`** ở thư mục gốc dự án (ví dụ `C:\ViePN-iOS-Manager\Start-ViePN.bat`). BAT tự tạo môi trường Python nếu chưa có, cài gói thiếu, mở API Windows (127.0.0.1:8765), khởi động gateway (127.0.0.1:8766), bật Tailscale Serve HTTPS khi Tailscale đã đăng nhập, và mở dashboard.

- Nếu ViePN đang chạy phiên bản cũ trên 8765, **dừng phiên bản cũ** và nhấp đúp BAT lại. Không chạy song song hai phiên bản.
- Nếu chưa cài Tailscale hoặc chưa đăng nhập, BAT vẫn mở dashboard cục bộ và thông báo cách bật Remote.
- Nếu phát hiện cổng 8765/8766 công khai trên LAN, BAT từ chối để tránh lộ API.
- Giữ các cửa sổ API và gateway chạy để gia hạn, nhận thông báo và điều khiển từ xa.

Trong tab **Thư viện IPA**, mỗi bản build được phân biệt bằng **tên tùy chỉnh, phiên bản, ngày nhập, mã SHA và hạn provisioning profile**. Nhấn **Đổi tên** để đặt biệt danh phân biệt các bản build cùng tên; tên này chỉ tồn tại trong ViePN, không sửa Info.plist bên trong IPA.

Bạn có thể **Xóa** một IPA, **Chọn tất cả / Xóa đã chọn** hoặc **Xóa toàn bộ IPA** (kể cả IPA đã ký/có embedded profile). ViePN hiển thị cảnh báo, rồi yêu cầu nhập cụm xác nhận `DELETE SELECTED IPAS` hoặc `DELETE ALL IPAS`.

Nếu file đang được một bản cài theo dõi gia hạn sử dụng, phải đồng ý **hủy bản ghi theo dõi gia hạn** liên quan thì mới xóa được. ViePN không cho xóa khi có tác vụ ký/cài/gia hạn đang chạy hoặc đang đợi liên quan. Thao tác chỉ xóa IPA và lịch theo dõi trên máy Windows: **không gỡ ứng dụng khỏi iPhone, không xóa provisioning profile Apple khỏi hệ thống Developer, và không xóa các tệp .mobileprovision độc lập đã tải lên**. Khi cần gia hạn lại, hãy nhập lại IPA, thiết lập tài khoản và theo dõi mới.

## Điều khiển ViePN từ iPhone qua Internet (Private Remote)

ViePN có gateway riêng tại `127.0.0.1:8766` chỉ cho phép các API điều khiển đã được kiểm tra. Tailscale Serve tạo URL HTTPS nội bộ tailnet, **không mở cổng 8765/8766 công khai** và không cần mở port trên router.

1. Cài [Tailscale cho Windows](https://tailscale.com/download/windows) và [Tailscale cho iPhone](https://tailscale.com/download/ios), đăng nhập cùng tailnet.
2. Cập nhật ViePN từ GitHub. File BAT sẽ kiểm tra các gói Python và cài những phần còn thiếu.
3. Nhấp đúp **`Start-ViePN.bat`**. Đây là file BAT duy nhất để bật backend, dashboard, gateway và Tailscale Serve HTTPS. Có thể cần bật MagicDNS và HTTPS certificates trong Tailscale admin.
4. Sao chép URL dạng `https://may-tinh.tailnet.ts.net`. Trong ứng dụng iOS → **Kết nối** → nhập URL này và access token ViePN từ Windows.
5. Điều khiển trạng thái, quản lý IPA, tạo tác vụ ký/cài và gia hạn khi iPhone có Internet và Tailscale VPN đang bật.

**Giới hạn:** Các thao tác đăng nhập/đăng xuất Apple ID, mật khẩu và 2FA **không được cung cấp qua gateway từ xa**; chỉ thao tác trên máy Windows local. Lệnh ký/cài từ xa cần iPhone được Windows nhận diện bằng USB hoặc pairing Wi-Fi; VPN không thay thế kết nối thiết bị để cài IPA. Máy Windows, gateway và Tailscale phải chạy thì điều khiển từ xa mới hoạt động.

Tắt kết nối từ xa: `powershell -ExecutionPolicy Bypass -File .\windows\stop-remote.ps1`.

Xem **[hướng dẫn chi tiết và xử lý lỗi](docs/REMOTE_ACCESS.md)**. Không dùng Tailscale Funnel (chế độ công khai Internet).

## 🔔 Thông báo đẩy iPhone (tùy chọn)

ViePN hỗ trợ cảnh báo chữ ký sắp hết hạn trong vòng **48 giờ**, tác vụ ký/cài/gia hạn **thất bại** và **gia hạn thành công**. Vì ứng dụng được ký bằng Apple ID miễn phí không được đảm bảo quyền APNs, thông báo đẩy **không xuất hiện trực tiếp trong ứng dụng ViePN**. Thay vào đó, người dùng cài ứng dụng miễn phí [ntfy](https://ntfy.sh/) trên iPhone.

1. Trên **Windows localhost** (http://127.0.0.1:8765) → **Cài đặt** → **Thông báo trên iPhone**.
2. Đọc lưu ý về dịch vụ bên thứ ba rồi chọn đồng ý và nhấn **Bật thông báo**.
3. Sao chép **topic bí mật** ViePN tạo, gửi an toàn sang iPhone.
4. Trong ứng dụng ntfy trên iPhone chọn **Subscribe** và nhập đúng topic. Bật quyền thông báo.
5. Trên Windows nhấn **Gửi thử** để kiểm tra. Muốn dừng, nhấn **Tắt**.

Chỉ gửi trạng thái chung, không gửi Apple ID, tên IPA, UDID, mã 2FA, token hay nội dung log. Tuy nhiên **ntfy.sh là dịch vụ bên thứ ba** và người biết topic có thể xem thông báo; topic phải được giữ bí mật. Tính năng **mặc định tắt** và chỉ được bật khi bạn đồng ý. Máy Windows phải còn chạy ViePN và có Internet. Mỗi hạn hết hiệu lực chỉ cảnh báo một lần nếu gửi thành công; khi ntfy.sh không phản hồi, ViePN sẽ thử lại vào lần quét tiếp theo.

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
- `backend/viepn/service.py` — quản lý signing jobs, cài đặt, quét gia hạn và cảnh báo.
- `backend/viepn/notifications.py` — cảnh báo ntfy có sự đồng ý, topic riêng và tránh gửi lặp.
- `backend/viepn/api.py` — dashboard APIs; các endpoint tài khoản nhạy cảm chỉ cho localhost có access token và cùng Origin.
- `backend/viepn/remote_gateway.py` — gateway chỉ cho phép API đã xác định, có token, chặn truy cập Apple ID/2FA từ xa.
- `backend/remote_run.py` — chạy gateway trên 127.0.0.1:8766.
- `Start-ViePN.bat` — chạy toàn bộ ViePN, tự cài gói Python thiếu, backend, gateway và Tailscale Serve.
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

GitHub Actions gồm backend tests, JavaScript syntax check, Windows BAT/PowerShell checks, iOS unsigned build. Kết quả unit tests không thay thế kiểm chứng ký/cài trên một thiết bị thật.

Project độc lập với Apple Inc. và không được Apple chứng nhận.
