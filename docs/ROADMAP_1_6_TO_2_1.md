# ViePN iOS Manager — Lộ trình kỹ thuật 1.6 → 2.1

Trạng thái: mã nguồn đã được triển khai theo các nhóm tính năng dưới đây. GitHub Actions chứng minh khả năng build/test, **không** chứng minh Apple ID, USB pairing, ký hay cài IPA thành công trên thiết bị thực tế.

## 1.6 — Bảo vệ dữ liệu / Connection Doctor

- `GET /api/doctor` (bearer token): các phép kiểm tra chỉ đọc, không gửi ra ngoài mật khẩu, token, Apple session hay định danh thiết bị.
- `GET /api/backups`, `POST /api/backups`, `GET /api/backups/{name}` (bearer + localhost): sao lưu SQLite (online backup), IPA và profile độc lập thành ZIP kèm SHA-256. **Không** sao lưu mật khẩu, token, phiên Apple; metadata SQLite có thể chứa tên ứng dụng và email tài khoản liên quan, cần bảo vệ file ZIP.
- Trước khi xóa IPA hàng loạt: bắt buộc tạo snapshot trên Windows; sao lưu lỗi thì từ chối xóa.
- Khôi phục chỉ bằng lệnh offline sau khi dừng backend và gateway. Archive được kiểm SHA-256, dữ liệu hiện tại được lưu bản sao trước khi ghi đè, và khôi phục trạng thái cũ nếu lỗi khi ghi.
- Ví dụ phục hồi sau khi đã dừng ViePN:
  ```powershell
  cd C:\ViePN-iOS-Manager
  .\.venv\Scripts\python.exe .\backend\restore_backup.py "C:\Users\<user>\AppData\Local\ViePN-iOS-Manager\backups\ViePN-YYYYMMDD-HHMMSS-xxxxxxxx.zip" --confirm "RESTORE VIEPN"
  ```
  Hãy dùng đường dẫn thật; không thay `<user>` theo ví dụ nếu khác. Sau khi khôi phục, mở ViePN và kiểm tra các bản cài/theo dõi, vì trạng thái trên iPhone có thể đã thay đổi.

## 1.7 — Build Manager

- Tên tùy chỉnh, phiên bản, ngày nhập, SHA, hạn profile và trạng thái đã ký.
- Nhãn `unassigned`, `dev`, `test`, `stable`, `archive`, lọc và tìm kiếm trên web/iOS.
- API phân loại và đổi tên có bearer token; cả hai không sửa bundle ID hoặc nội dung IPA.

## 1.8 — Tin cậy tác vụ / Smart Auto-Renew cơ bản

- Chống tạo trùng tác vụ gia hạn đang queued/running.
- Gia hạn tự quét có backoff tăng từ 6 đến tối đa 24 giờ theo số lần thất bại; đặt lại bộ đếm khi gia hạn thành công.
- Retry thủ công cho tác vụ `sign`, `apple_sign`, `renew` thất bại, tối đa 3 lần/24 giờ/cùng đầu vào; cần xác nhận. **Không tự động retry cài IPA**, tránh cài đặt lặp.
- Windows vẫn phải nhận diện iPhone bằng USB hoặc Wi-Fi pairing; một HTTPS/VPN tunnel không tự tạo kết nối thiết bị. Apple Personal Team có thể yêu cầu đăng nhập và 2FA lại.

## 2.0 — Giao diện & xử lý lỗi

- Web: layout thích ứng màn hình nhỏ, kiểm tra khả năng truy cập bàn phím, trang Build Manager tìm/lọc.
- iOS: pull-to-refresh, tìm/lọc/phân loại build, Connection Doctor, hàng đợi gần đây và xác nhận retry.
- Kết quả diagnostics là kiểm tra môi trường, không được trình bày như kiểm chứng ký thành công trên iPhone.

## 2.1 — Portable Windows Installer & Integrity CI

- `Start-ViePN.bat` vẫn là **file duy nhất** để bật API Windows, gateway, Tailscale Serve và lịch quét.
- GitHub Actions đóng gói `ViePN-Windows-Portable.zip` cùng file `.sha256`; kiểm tra danh sách file cho phép, manifest và SHA-256.
- Giải nén Portable ZIP và chạy `Install-ViePN.bat`: script xác minh checksum của các tệp trong manifest, kiểm tra 8765/8766 đã dừng, sao lưu mã nguồn cũ và cài vào `C:\ViePN-iOS-Manager`.
- Data trong `%LOCALAPPDATA%\ViePN-iOS-Manager` được giữ nguyên. Khi nâng cấp, nên sao lưu riêng folder dữ liệu và kiểm tra chữ ký/GitHub checksum từ nguồn bạn tin cậy.
- Đây là bản phân phối **ZIP/PowerShell**, chưa phải MSI/EXE có chữ ký Authenticode; không đưa ra cam kết SmartScreen không cảnh báo.

## Kiểm thử & tiêu chí chấp nhận

- CI: unit/backend tests, dashboard JavaScript syntax, PowerShell parse, Windows BAT self-test, iOS unsigned compile, đóng gói ZIP và SHA-256 kiểm định.
- Các kiểm thử bắt buộc: archive bị sửa phải bị từ chối; API backup không dùng từ gateway; xóa IPA được sao lưu trước; retry không vượt giới hạn; OTA/HTTPS không nhận API Apple ID/2FA; gói phát hành không chứa token hoặc session.
- Chưa kiểm chứng tự động: signing Apple ID/2FA thực, iPhone Wi-Fi pairing, iOS background notifications ntfy, máy Windows của người dùng, Windows MSI/EXE code signing, mọi phiên bản Windows 10/11.
- Tính năng mới được cập nhật mã nguồn và qua CI, **không** tự cài vào máy Windows/iPhone của bạn. Cần `git pull` hoặc cài Portable ZIP rồi khởi động lại ViePN; ứng dụng iOS cần ký IPA unsigned và cài bản mới.

## Rollback

- Nếu bản code mới có lỗi, đóng tất cả cửa sổ ViePN, dùng source backup trong `C:\ViePN-iOS-Manager\code-backups\` hoặc checkout commit GitHub trước đó.
- Nếu dữ liệu đã bị xóa/sai, dùng archive ZIP lưu trong `%LOCALAPPDATA%\ViePN-iOS-Manager\backups` và lệnh restore offline; kiểm tra kết quả trước khi bật lại lịch gia hạn.
- Không xóa token/Apple session thủ công, không mở API 8765/8766 ra Internet, không dùng Tailscale Funnel.
