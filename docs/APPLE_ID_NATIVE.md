# ViePN iOS Manager - ký trực tiếp bằng Apple ID miễn phí (Windows)

**Trạng thái hiện tại:** có mã nguồn cho Apple ID GrandSlam + 2FA, Apple Developer Services provisioning, ký IPA bằng Python, cài ứng dụng bằng pymobiledevice3, và bộ quét tự gia hạn trước 48 giờ. Chưa thử đăng nhập thực tế trên Apple ID của bạn hoặc cài thành công lên iPhone thật. Apple có thể đổi giao thức không công khai bất cứ lúc nào.

## Không cần SideStore / AltStore

ViePN tự điều phối:
1. Đăng nhập Apple ID và 2FA trong PowerShell local.
2. Lấy team Personal Team; tạo/gắn development certificate, App ID và đăng ký UDID thiết bị với Apple.
3. Xin provisioning profile mới (thường có hạn 7 ngày).
4. Ký IPA bằng Python `ipasign` sau khi sửa bundle ID phù hợp với team.
5. Cài qua `pymobiledevice3` trên Windows.
6. Ghi lại IPA gốc và thời hạn; khi còn 48 giờ xin profile mới rồi cài đè; khi server hoạt động sẽ quét mặc định mỗi 30 phút.

**Đây là tính năng của chính ViePN**, không yêu cầu cài ứng dụng quản lý chữ ký thứ ba lên PC/iPhone. Mã nguồn GSA và provisioning được tích hợp trực tiếp (nguồn MIT có ghi công trong `backend/viepn/applekit/LICENSE` và `NOTICE.md`). Phần mềm vẫn dùng các thư viện mã nguồn mở như ứng dụng Python thông thường.

## Cài đặt

Yêu cầu: Python 3.14 đang có, iTunes/Apple Mobile Device Service, iPhone kết nối USB và Trust This Computer; có thể cần Developer Mode trên iPhone.

```powershell
cd C:\ViePN-iOS-Manager
git pull origin main
powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
powershell -ExecutionPolicy Bypass -File .\windows\apple-login.ps1
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
```

**Nếu thư mục bạn tải chỉ là ZIP không có .git**, hãy tải ZIP mới từ GitHub và sao lưu thư mục `%LOCALAPPDATA%\ViePN-iOS-Manager` trước khi thay mã nguồn. Đừng xóa thư mục dữ liệu nếu muốn giữ IPA, token và các tác vụ.

Mở `http://127.0.0.1:8765`, đăng nhập bằng access token ViePN, chọn tab **Apple ID miễn phí**. Chọn IPA + iPhone, rồi bấm **Ký IPA** hoặc **Ký + cài iPhone**. Sử dụng mục Gia hạn hoặc nút Gia hạn tất cả để chạy ký mới theo yêu cầu.

## Đăng nhập, đăng xuất và chuyển Apple ID ngay trên dashboard

Tại **http://127.0.0.1:8765** → tab **Apple ID miễn phí**, sau khi nhập access token quản trị:

1. Chọn cấu hình anisette đã lưu, máy chủ HTTPS của bạn hoặc **chủ động đồng ý** sử dụng nhà cung cấp cộng đồng.
2. Nhập Apple ID và mật khẩu → nhấn **Đăng nhập Apple ID**. Nếu Apple yêu cầu xác minh, nhập mã **2FA 6 số** vào biểu mẫu vừa xuất hiện → **Xác minh**.
3. Khi đăng nhập thành công, tài khoản sẽ nằm trong danh sách **Tài khoản đã đăng nhập**. Chọn tài khoản khác và nhấn **Chuyển tài khoản** để dùng phiên đã lưu, không cần nhập lại mật khẩu nếu phiên còn hiệu lực.
4. Nhấn **Đăng xuất tài khoản chọn** hoặc **Đăng xuất tất cả** để xóa phiên Apple đã lưu trên Windows. **Không xóa file IPA, dữ liệu cài đặt hoặc ứng dụng trên iPhone**. Khi cần dùng lại chỉ cần đăng nhập lại (Apple có thể yêu cầu 2FA).

**Bảo mật:** Các endpoint quản lý tài khoản có xác thực bearer token, kiểm tra Origin và chỉ hoạt động khi server lắng nghe trên **loopback** (127.0.0.1/localhost). Nếu ViePN đang bật LAN (ví dụ `VIEPN_HOST=0.0.0.0`), biểu mẫu sẽ từ chối thao tác; chuyển server về localhost hoặc dùng `windows/apple-login.ps1` trên máy Windows. Mật khẩu không được ghi vào database; khi 2FA được yêu cầu, mật khẩu tồn tại tạm trong bộ nhớ tiến trình tối đa 5 phút hoặc đến khi xác minh, hủy, hay đăng xuất. Phiên xác thực Apple vẫn được lưu tại dữ liệu người dùng Windows như trước.

Khi nhiều Apple ID đã đăng nhập, mỗi ứng dụng được gắn với tài khoản đã dùng để ký để tránh ký nhầm khi gia hạn. Những bản cài từ trước khi có trường thông tin này có thể cần đăng nhập đúng tài khoản ban đầu.

## Mac-generated anisette: giới hạn kỹ thuật quan trọng

Apple không công bố API cho Personal Team đăng nhập/cấp profile ngoài Xcode, và thay đổi xác thực từ tháng 10/2026. Quy trình GrandSlam cần dữ liệu anisette kiểu Mac. Windows không thể đảm bảo tự tạo dữ liệu được Apple chấp nhận chỉ từ Apple ID.

**ViePN không tự động kết nối dịch vụ cộng đồng nếu chưa có sự đồng ý của bạn.** Khi chạy `apple-login.ps1`, chọn:
- Nhập HTTPS URL máy chủ anisette **do bạn vận hành**, nếu có.
- Hoặc xác nhận dùng dịch vụ anisette cộng đồng. Dịch vụ đó là phụ thuộc ngoài; dịch vụ có thể thấy IP và định danh thiết bị ngẫu nhiên, nhưng không được nhận mật khẩu Apple ID / mã 2FA / token Apple trong luồng này.
- Nếu không đồng ý bất kỳ dịch vụ nào, ViePN sẽ dừng trước khi đăng nhập; không có cách nào đáng tin cậy để hứa một ứng dụng Windows độc lập tuyệt đối sử dụng Personal Team trong mọi phiên bản iOS.

**Bảo mật:** không nhập mật khẩu Apple vào dashboard, không đưa P12, profile, token, session hay file pairing lên GitHub. Phiên Apple nằm dưới `%LOCALAPPDATA%\ViePN-iOS-Manager\session`, quyền truy cập phụ thuộc quyền tài khoản Windows. Không mở port 8765 ra Internet. Chỉ nên chạy những IPA bạn sở hữu/quyền sử dụng.

## Tự gia hạn trên Windows

Trên PowerShell cùng tài khoản đã đăng nhập Apple:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\register-auto-renew.ps1
```

Tác vụ Windows tự mở ViePN khi bạn đăng nhập Windows. Server quét mỗi 30 phút; mặc định chỉ gia hạn khi còn 48 giờ. Điều kiện: PC đang bật, tài khoản Apple vẫn xác thực, iPhone kết nối qua USB hoặc Wi-Fi đã ghép đôi, Apple cấp profile hợp lệ. Nếu bất kỳ điều kiện nào thiếu, ViePN đánh dấu cần can thiệp; không thể bảo đảm tuyệt đối 24/7 trên iOS gốc.

Không thể tự cài firmware IPSW bị Apple ngừng ký hoặc cài IPA mà không được Apple ký hợp lệ.

## Thiết kế nội bộ

- `backend/viepn/native_sign.py` — local login, nguồn profile, engine IPA signing.
- `backend/viepn/applekit/` — mã xác thực GSA / Developer Services được vendoring có giấy phép MIT.
- `backend/viepn/service.py` — job `apple_sign`, `apple_install`, re-provision/renew.
- `backend/viepn/api.py` — endpoints có bearer token; **không có API nhận password Apple**.
- `windows/apple-login.ps1` — nhập Apple ID và 2FA qua console tại máy tính.
- `windows/register-auto-renew.ps1` — chạy scheduler theo user Windows logon.

## Trạng thái thử nghiệm

Kiểm thử unit/API giúp phát hiện lỗi lập trình nhưng không chứng minh Apple đang chấp nhận GSA hoặc IPA sẽ chạy trên iPhone. Cần thử nghiệm thực tế mới xác nhận end-to-end. Các dịch vụ không công khai có thể bị Apple chặn; mọi lỗi được đưa vào nhật ký thay vì báo giả thành công.
