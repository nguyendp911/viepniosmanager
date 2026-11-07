# ViePN iOS Manager 2.1.1 — Hotfix xóa IPA trên Windows & iPhone

Bản chính thức **2.1.1 Stable** sửa thông báo `Could not remove IPA files` ở bản 2.1.0.

## Sửa lỗi

- Trước đây, xóa IPA hàng loạt từ web hoặc iOS có thể trả lỗi chung do Windows đang giữ file, hoặc quá trình sao lưu trước khi xóa thất bại.
- ViePN nay **phân biệt lỗi sao lưu với lỗi xóa**, hiển thị lý do bằng tiếng Việt và không âm thầm bỏ qua an toàn dữ liệu.
- Khi file IPA đã được sao lưu và Windows giữ khóa, ViePN có thể xóa thông tin khỏi thư viện/ngừng theo dõi gia hạn, đồng thời giữ file vật lý trong danh sách **chờ dọn** cho đến khi Windows nhả khóa. Dọn lại khi ViePN khởi động, hoặc khi backend kiểm tra lại.
- Web và app iPhone hiển thị rõ số file vẫn đang chờ dọn. Cùng một backend trên Windows phục vụ cả hai thiết bị; **chỉ cài lại IPA iPhone mà không nâng cấp Windows sẽ không sửa được lỗi này**.
- Không dùng cơ chế này để gỡ ứng dụng đang cài trên thiết bị iOS. Xóa trong ViePN chỉ ảnh hưởng thư viện IPA và lịch theo dõi ở Windows.

## Bảo mật

- Tự sao lưu IPA, profile và SQLite trước khi xóa hàng loạt; nếu sao lưu thất bại, **không có bản nào bị xóa**.
- Không tự ý tắt Windows Defender hoặc thay đổi quyền toàn hệ thống để xóa file.
- Không mở API quản lý Apple ID, chứng chỉ hoặc bản sao lưu qua Internet.
- Các file bị khóa được dọn sau, không tự ý xóa một IPA cùng SHA đã được nhập lại thư viện.

## Cài đặt

1. Tải `ViePN-Windows-Portable-2.1.1.zip` và `.sha256` từ bản phát hành này. Dùng PowerShell `Get-FileHash` để xác nhận checksum trước khi giải nén.
2. Đóng tất cả cửa sổ ViePN trên máy Windows; giải nén gói ZIP vào một thư mục mới.
3. Chạy `Install-ViePN.bat`, sau đó chạy `C:\ViePN-iOS-Manager\Start-ViePN.bat`.
4. Mở `http://127.0.0.1:8765/api/health` và xác nhận phiên bản `2.1.1`. Từ iPhone, cần bật Tailscale và sử dụng URL HTTPS của Windows như trước.
5. Nếu vẫn muốn giao diện thông báo mới trên iPhone, ký lại `ViePNMobile-2.1.1-UNSIGNED.ipa` bằng profile hợp lệ rồi cài lại. Cập nhật Windows là bắt buộc; cập nhật iOS là tùy chọn cho phần chữ thông báo.

**Lưu ý:** IPA trong release là bản unsigned, không thể cài trực tiếp nếu chưa ký. Gói Windows là ZIP/BAT/PowerShell không có Authenticode; không có chứng chỉ ký phát hành do người dùng cung cấp. CI xác minh build và unit tests; chưa thử thực tế trên Windows/iPhone của bạn.
