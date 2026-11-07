# Apple ID mien phi — ky 7 ngay / Free Apple Account

**Chi mot tai khoan Apple mien phi; khong can P12, zsign hay Apple Developer tra phi.**

## Thanh phan va gioi han

- ViePN Windows quan ly file IPA, phat hien iPhone, va cho phep tai file IPA ve PC hoac chuyen mot lan qua Wi-Fi.
- **iLoader** thiet lap SideStore lan dau, su dung Apple Account cua ban tren may Windows. ViePN khong thu thap Apple ID, mat khau, 2FA hay session.
- **SideStore** ky IPA, cai IPA, va lam moi chu ky 7 ngay tren iPhone. Qua trinh lam moi nen cua iOS khong duoc dam bao 100%.
- Tai khoan Apple mien phi thuong gioi han 3 ung dung (bao gom SideStore) dang cai va 10 App ID moi 7 ngay.
- ViePN *khong* tu dong ky hoac gia han bang Apple ID; thao tac do do SideStore thuc hien. Khong co ket noi API/chia se khoang chua chung thuc chinh thuc giua hai app.

## Cai SideStore lan dau tren Windows

1. Doc huong dan chinh thuc [SideStore prerequisites](https://docs.sidestore.io/docs/installation/prerequisites).
2. Cai iTunes, iLoader; tren iPhone cai LocalDevVPN tu App Store.
3. Noi cap USB, mo khoa iPhone, chon Trust Computer.
4. Mo iLoader, dang nhap **truc tiep trong iLoader**, chon iPhone va **Install SideStore (Stable)**.
5. Tren iPhone, tin cay app tai Settings > General > VPN & Device Management; bat Developer Mode neu can.
6. Ket noi Wi-Fi, bat LocalDevVPN; mo SideStore, dang nhap Apple Account cua ban, lam moi SideStore trong My Apps (nut 7 DAYS) mot lan.
7. Khi can gia han, SideStore > My Apps > Refresh All. Lam moi truoc han 1–2 ngay; khong phu thuoc hoan toan vao background.

Huong dan: https://docs.sidestore.io/docs/installation/install

## Chuyen IPA tu ViePN qua iPhone

### Cach 1 — Khuyen dung: qua iCloud Drive/Files

1. Trong dashboard ViePN, chon **Apple ID mien phi** va chon IPA.
2. Nhan **Tai IPA ve Windows**, chuyen file vao iCloud Drive hoac cach chuyen file cua ban.
3. Tren iPhone, mo file trong Files va nhap vao SideStore de ky/cai.

### Cach 2 — Link Wi-Fi mot lan

1. Tren PowerShell, dung ViePN backend bang Ctrl+C.
2. Chay chi trong **mang LAN rieng dang tin**:

   ```powershell
   cd C:\ViePN-iOS-Manager
   $env:VIEPN_HOST = '0.0.0.0'
   .\windows\start.ps1
   ```

3. Cho phep ket noi TCP 8765 trong Windows Firewall **Private** chi cho subnet LAN dang tin, khong mo ra Internet hay mang Public.
4. Su dung `ipconfig` tren Windows de tim IPv4 noi bo (vi du `192.168.1.10`).
5. Tren dashboard > Apple ID mien phi: chon IPA, nhap IPv4, bam **Tao lien ket Wi-Fi (10 phut)**, sao chep link.
6. Mo Safari tren iPhone **cung Wi-Fi** va dan link. File .ipa se duoc tai xuong. Mo Files > Downloads, nhap vao SideStore.

### Bao mat share link

- Link cua moi IPA dung token ngau nhien (256 bit), co han 10 phut va **chi tai mot lan**; no khong chua access token quan tri.
- Ai co link truoc khi no het han cung co the tai file IPA. Khong chia se link cong khai.
- Share token chi luu trong RAM ViePN Windows, se mat khi khoi dong lai.
- Endpoint tai IPA khong doi dang nhap, theo mo hinh **capability URL**. Dung mang LAN rieng. API quan tri su dung bearer token va HTTP thuong, **khong an toan khi mo ra mang cong cong**.
- Không upload Apple ID, mat khau, ma 2FA, pairing file, certificates, provisioning profile hay access token len GitHub.

## Khi van de

- **'Thiếu zsign'**: Khong phai loi trong che do Apple ID mien phi. Gia han/ky tren SideStore.
- **SideStore không nhận pairing**: [Hướng dẫn cập nhật pairing file](https://docs.sidestore.io/docs/advanced/pairing-file).
- **Link tải không mở trên iPhone**: kiểm tra cùng Wi-Fi, IP máy tính, server bind 0.0.0.0, Private Firewall. Thử URL `http://<ip-windows>:8765/` trước (sẽ hiển thị dashboard nhưng yêu cầu token quản trị).
- **Không đủ slot cài**: tài khoản miễn phí tối đa 3 app bao gồm SideStore.
- **App đã hết hạn**: mở SideStore và thử gia hạn; nếu SideStore cũng hết hạn, có thể phải cài lại qua iLoader.
- **ViePN quản lý không thấy ứng dụng SideStore**: ViePN và SideStore hiện chưa đồng bộ thời hạn ứng dụng, ViePN không giả mạo trạng thái.
