import SwiftUI
import UniformTypeIdentifiers

private enum Palette {
    static let bg = Color(red: 0.045, green: 0.073, blue: 0.13)
    static let panel = Color(red: 0.075, green: 0.13, blue: 0.21)
    static let blue = Color(red: 0.32, green: 0.6, blue: 1)
    static let mint = Color(red: 0.28, green: 0.83, blue: 0.69)
    static let secondary = Color(red: 0.58, green: 0.67, blue: 0.79)
}

private struct Panel<Content: View>: View {
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 14) { content }
            .padding(17).frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.panel, in: RoundedRectangle(cornerRadius: 18))
    }
}

struct ContentView: View {
    @EnvironmentObject var model: ManagerModel
    @State private var showSettings = false

    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Tổng quan", systemImage: "square.grid.2x2.fill") }
            LibraryView()
                .tabItem { Label("Thư viện", systemImage: "square.stack.3d.up.fill") }
            RenewView()
                .tabItem { Label("Gia hạn", systemImage: "arrow.clockwise.circle.fill") }
            ConnectionView()
                .tabItem { Label("Kết nối", systemImage: "gearshape.fill") }
        }
        .tint(Palette.blue)
        .background(Palette.bg)
        .task { await model.load() }
        .overlay(alignment: .top) {
            if let notice = model.notice {
                Text(notice).font(.footnote).padding(13)
                    .background(Palette.mint.opacity(0.95), in: Capsule())
                    .foregroundStyle(.black).padding(.top, 12)
                    .onTapGesture { model.notice = nil }
            }
        }
    }
}

private struct Page<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 15) {
                    content
                }
                .padding(16)
            }
            .background(Palette.bg)
            .navigationTitle(title)
            .toolbarBackground(Palette.bg, for: .navigationBar)
        }
    }
}

private struct StatusView: View {
    @EnvironmentObject var model: ManagerModel
    var body: some View {
        Group {
            if let message = model.error {
                Text(message).font(.footnote).foregroundStyle(.red)
                    .padding(11).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
            }
            if !model.isConfigured {
                Text("Hãy thiết lập địa chỉ Windows và access token trong tab Kết nối.")
                    .font(.footnote).foregroundStyle(.orange)
            }
        }
    }
}

private struct KPI: View {
    let value: Int
    let title: String
    let symbol: String
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: symbol).foregroundStyle(Palette.blue)
            Text("\(value)").font(.system(size: 29, weight: .bold, design: .rounded))
            Text(title).font(.caption).foregroundStyle(Palette.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(15).background(Palette.panel, in: RoundedRectangle(cornerRadius: 17))
    }
}

private struct DashboardView: View {
    @EnvironmentObject var model: ManagerModel
    var body: some View {
        Page(title: "ViePN iOS Manager") {
            HStack(spacing: 12) {
                Image(systemName: "iphone.gen3").font(.largeTitle).foregroundStyle(Palette.mint)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Trung tâm quản lý iOS").font(.headline)
                    Text("Windows Companion").font(.caption).foregroundStyle(Palette.secondary)
                }
                Spacer()
                if model.busy { ProgressView().tint(Palette.blue) }
            }.padding(.bottom, 5)
            StatusView()
            HStack {
                KPI(value: model.overview?.ipas.count ?? 0, title: "Ứng dụng IPA", symbol: "square.stack.3d.up")
                KPI(value: model.devices.count, title: "Thiết bị", symbol: "iphone")
            }
            HStack {
                KPI(value: model.overview?.installations.count ?? 0, title: "Đang theo dõi", symbol: "checkmark.shield")
                KPI(value: model.overview?.installations.filter {
                    guard let x = $0.expiresAt?.expiryDate else { return false }
                    return x.timeIntervalSinceNow < 172800
                }.count ?? 0, title: "Sắp hết hạn", symbol: "clock.arrow.circlepath")
            }
            Panel {
                Text("Chữ ký ứng dụng").font(.headline)
                if let installs = model.overview?.installations, !installs.isEmpty {
                    ForEach(installs.prefix(6)) { install in
                        InstallRow(info: install)
                        Divider().overlay(.white.opacity(0.08))
                    }
                } else {
                    Text("Chưa có ứng dụng nào được theo dõi.")
                        .font(.subheadline).foregroundStyle(Palette.secondary)
                }
            }
            Panel {
                Text("Tình trạng công cụ").font(.headline)
                Label("Kết nối Windows", systemImage: model.overview == nil ? "wifi.slash" : "wifi")
                    .foregroundStyle(model.overview == nil ? .orange : Palette.mint)
                Label("Trình ký: \((model.overview?.tools.zsign ?? false) ? "Sẵn sàng" : "Chưa cấu hình")", systemImage: "signature")
                Label("Cầu nối thiết bị: \((model.overview?.tools.pymobiledevice3 ?? false) ? "Sẵn sàng" : "Chưa cài")", systemImage: "cable.connector")
            }
            Button { Task { await model.load() } } label: {
                Label("Làm mới dữ liệu", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity)
            }.buttonStyle(.borderedProminent).disabled(!model.isConfigured || model.busy)
        }
    }
}

private struct LibraryView: View {
    @EnvironmentObject var model: ManagerModel
    @State private var selectingIPA = false
    @State private var selectedIPA = ""
    @State private var selectedDevice = ""
    @State private var resign = false
    @State private var autoRenew = true
    @State private var buildQuery = ""
    @State private var buildChannel = "all"
    @State private var editingBuildID = ""
    @State private var editingBuildName = ""
    @State private var showRenamePrompt = false
    @State private var pendingDeleteIDs: [String] = []
    @State private var pendingDeleteAll = false
    @State private var showDeletePrompt = false
    private let ipaType = UTType(filenameExtension: "ipa") ?? .data

    var body: some View {
        Page(title: "Thư viện IPA") {
            StatusView()
            Button { selectingIPA = true } label: {
                Label("Nhập file IPA từ Files", systemImage: "square.and.arrow.up")
                    .frame(maxWidth: .infinity)
            }.buttonStyle(.borderedProminent)
            Panel {
                HStack {
                    Text("Các bản build IPA").font(.headline)
                    Spacer()
                    Text("\(model.overview?.ipas.count ?? 0) bản").font(.caption).foregroundStyle(Palette.secondary)
                }
                Text("Các bản build trùng tên được phân biệt bằng mã SHA, ngày nhập và hạn profile. Bạn có thể đổi tên riêng cho từng bản.")
                    .font(.caption).foregroundStyle(Palette.secondary)
                TextField("Tìm theo tên, bundle ID, phiên bản, SHA...", text: $buildQuery)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .textFieldStyle(.roundedBorder)
                Picker("Nhóm bản build", selection: $buildChannel) {
                    Text("Tất cả").tag("all")
                    Text("Stable").tag("stable")
                    Text("Test").tag("test")
                    Text("Dev").tag("dev")
                    Text("Archive").tag("archive")
                    Text("Chưa phân loại").tag("unassigned")
                }.tint(.white)
                if let ipas = model.overview?.ipas, !ipas.isEmpty {
                    Button(role: .destructive) {
                        pendingDeleteAll = true
                        pendingDeleteIDs = ipas.map(\.id)
                        showDeletePrompt = true
                    } label: {
                        Label("Xóa toàn bộ IPA (kể cả có profile)", systemImage: "trash")
                            .frame(maxWidth: .infinity)
                    }.buttonStyle(.bordered).disabled(model.busy)
                    ForEach(ipas.filter { ipa in
                        let matchChannel = buildChannel == "all" || (ipa.channel ?? "unassigned") == buildChannel
                        let query = buildQuery.trimmingCharacters(in: .whitespacesAndNewlines)
                        let matchText = query.isEmpty ||
                            [ipa.name, ipa.alias ?? "", ipa.bundleId, ipa.version ?? "", ipa.id]
                                .contains(where: { $0.localizedCaseInsensitiveContains(query) })
                        return matchChannel && matchText
                    }) { ipa in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(ipa.alias ?? ipa.name)
                                .font(.subheadline.bold())
                            Text("\(ipa.name) · v\(ipa.version ?? "–")")
                                .font(.caption).foregroundStyle(Palette.secondary)
                            Text("\(ipa.bundleId) · SHA \(ipa.id.prefix(12))")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(Palette.secondary)
                            Text("Ngày nhập: \(String((ipa.createdAt ?? "–").prefix(16)).replacingOccurrences(of: "T", with: " "))")
                                .font(.caption2).foregroundStyle(Palette.secondary)
                            if ipa.signedCandidate == 1 {
                                Text("Có profile · Hết hạn: \(String((ipa.profileExpires ?? "Không rõ").prefix(16)).replacingOccurrences(of: "T", with: " "))")
                                    .font(.caption2).foregroundStyle(Palette.mint)
                            } else {
                                Text("Chưa xác định chữ ký").font(.caption2).foregroundStyle(.orange)
                            }
                            if let count = model.overview?.installations.filter({
                                $0.sourceIpaId == ipa.id || $0.currentIpaId == ipa.id
                            }).count, count > 0 {
                                Text("Đang theo dõi gia hạn: \(count) bản cài")
                                    .font(.caption2).foregroundStyle(.orange)
                            }
                            HStack {
                                Menu {
                                    ForEach(["unassigned", "dev", "test", "stable", "archive"], id: \.self) { channel in
                                        Button(channel.uppercased()) {
                                            Task { await model.classifyIPA(id: ipa.id, channel: channel) }
                                        }
                                    }
                                } label: {
                                    Label((ipa.channel ?? "unassigned").uppercased(), systemImage: "tag")
                                }.buttonStyle(.bordered)
                                Button("Đổi tên") {
                                    editingBuildID = ipa.id
                                    editingBuildName = ipa.alias ?? ""
                                    showRenamePrompt = true
                                }.buttonStyle(.bordered)
                                Button("Xóa", role: .destructive) {
                                    pendingDeleteAll = false
                                    pendingDeleteIDs = [ipa.id]
                                    showDeletePrompt = true
                                }.buttonStyle(.bordered)
                            }.disabled(model.busy)
                        }
                        Divider().overlay(.white.opacity(0.08))
                    }
                } else {
                    Text("Chưa nhập IPA").foregroundStyle(Palette.secondary)
                }
            }
            Panel {
                Text("Ký và cài ứng dụng").font(.headline)
                Picker("Ứng dụng", selection: $selectedIPA) {
                    Text("Chọn IPA").tag("")
                    ForEach(model.overview?.ipas ?? []) { ipa in
                        Text(ipa.buildDisplayName).tag(ipa.id)
                    }
                }.tint(.white)
                Picker("iPhone", selection: $selectedDevice) {
                    Text("Chọn thiết bị").tag("")
                    ForEach(model.devices) { device in
                        Text("\(device.name) · \(device.id.prefix(7))").tag(device.id)
                    }
                }.tint(.white)
                Toggle("Ký lại bằng P12/profile", isOn: $resign).tint(Palette.mint)
                Toggle("Tự động thử gia hạn", isOn: $autoRenew).tint(Palette.mint)
                Button {
                    Task { await model.install(ipaID: selectedIPA, deviceID: selectedDevice,
                        resign: resign, autoRenew: autoRenew) }
                } label: {
                    Label("Gửi lệnh cài lên iPhone", systemImage: "arrow.down.to.line")
                        .frame(maxWidth: .infinity)
                }.buttonStyle(.borderedProminent)
                .disabled(selectedIPA.isEmpty || selectedDevice.isEmpty || model.busy)
            }
        }
        .alert("Tên phân biệt bản build", isPresented: $showRenamePrompt) {
            TextField("Tên mới (để trống để đặt lại)", text: $editingBuildName)
            Button("Lưu") {
                Task { await model.renameIPA(id: editingBuildID, alias: editingBuildName) }
            }
            Button("Hủy", role: .cancel) {}
        } message: {
            Text("Chỉ thay đổi tên hiển thị trong ViePN, không sửa IPA hoặc bundle ID.")
        }
        .confirmationDialog("Xóa IPA trên Windows?", isPresented: $showDeletePrompt,
                            titleVisibility: .visible) {
            Button("Xóa \(pendingDeleteIDs.count) IPA và hủy theo dõi gia hạn liên quan",
                   role: .destructive) {
                Task {
                    await model.deleteIPAs(pendingDeleteIDs, all: pendingDeleteAll, force: true)
                    if pendingDeleteIDs.contains(selectedIPA) { selectedIPA = "" }
                }
            }
            Button("Hủy", role: .cancel) {}
        } message: {
            Text("Nếu một bản IPA đang được theo dõi gia hạn, lịch theo dõi sẽ bị xóa. Không gỡ ứng dụng khỏi iPhone, không thu hồi profile Apple. Không thể hoàn tác.")
        }
        .fileImporter(isPresented: $selectingIPA, allowedContentTypes: [ipaType], allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let first = urls.first { Task { await model.uploadIPA(first) } }
            if case .failure(let error) = result { model.error = error.localizedDescription }
        }
    }
}

private struct InstallRow: View {
    let info: InstallationInfo
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "app.fill").font(.title2).foregroundStyle(Palette.blue)
            VStack(alignment: .leading, spacing: 4) {
                Text(info.bundleId).font(.subheadline.bold()).lineLimit(2)
                Text(info.state).font(.caption2).foregroundStyle(Palette.secondary)
                if let error = info.lastError { Text(error).font(.caption2).foregroundStyle(.red) }
            }
            Spacer()
            if let date = info.expiresAt?.expiryDate {
                let days = Int(ceil(date.timeIntervalSinceNow / 86400))
                Text(days <= 0 ? "Hết hạn" : "\(days) ngày")
                    .font(.caption.bold()).foregroundStyle(days <= 2 ? .orange : Palette.mint)
            }
        }
    }
}

private struct RenewView: View {
    @EnvironmentObject var model: ManagerModel
    @State private var selectingProfile = false
    private let profileType = UTType(filenameExtension: "mobileprovision") ?? .data

    var body: some View {
        Page(title: "Gia hạn chữ ký") {
            StatusView()
            Panel {
                Label("Tự động kiểm tra khi còn \(model.overview?.renewalHours ?? 48) giờ", systemImage: "clock.arrow.circlepath")
                    .font(.subheadline.bold()).foregroundStyle(Palette.mint)
                Text("Windows sẽ thử ký/cài khi có provisioning profile mới hợp lệ. Nếu Apple chưa cấp profile mới, cần làm mới qua quy trình xác thực hoặc SideStore.")
                    .font(.caption).foregroundStyle(Palette.secondary)
                Button { Task { await model.scanRenewals() } } label: {
                    Label("Quét và gửi tác vụ", systemImage: "arrow.clockwise")
                        .frame(maxWidth: .infinity)
                }.buttonStyle(.borderedProminent).disabled(model.busy)
            }
            Panel {
                Text("Ứng dụng cần quản lý").font(.headline)
                if let installs = model.overview?.installations, !installs.isEmpty {
                    ForEach(installs) { install in
                        InstallRow(info: install)
                        Button("Thử gia hạn ứng dụng này") { Task { await model.renew(id: install.id) } }
                            .buttonStyle(.bordered).disabled(model.busy)
                        Divider().overlay(.white.opacity(0.08))
                    }
                } else { Text("Chưa có ứng dụng đã cài").foregroundStyle(Palette.secondary) }
            }
            Panel {
                Text("Provisioning profiles").font(.headline)
                ForEach(model.overview?.profiles ?? []) { profile in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(profile.filename).font(.subheadline)
                        Text(profile.bundlePattern ?? "").font(.caption).foregroundStyle(Palette.secondary)
                    }
                }
                Button { selectingProfile = true } label: {
                    Label("Nhập profile mới", systemImage: "doc.badge.plus")
                }.buttonStyle(.borderedProminent)
            }
            if let url = URL(string: "https://docs.sidestore.io/docs/faq") {
                Link("Cách SideStore làm mới ứng dụng trên iPhone", destination: url)
                    .font(.footnote).foregroundStyle(Palette.blue)
            }
        }
        .fileImporter(isPresented: $selectingProfile, allowedContentTypes: [profileType], allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let first = urls.first { Task { await model.uploadProfile(first) } }
            if case .failure(let error) = result { model.error = error.localizedDescription }
        }
    }
}

private struct ConnectionView: View {
    @EnvironmentObject var model: ManagerModel
    @State private var server = ""
    @State private var secret = ""

    var body: some View {
        Page(title: "Kết nối Windows") {
            Panel {
                Text("ViePN Windows Companion").font(.headline)
                Text("Điều khiển ViePN trên Windows từ xa qua HTTPS và Tailscale VPN. Tailscale trên iPhone và Windows phải đăng nhập cùng mạng riêng.")
                    .font(.footnote).foregroundStyle(Palette.secondary)
                VStack(alignment: .leading, spacing: 7) {
                    Text("Địa chỉ API").font(.caption).foregroundStyle(Palette.secondary)
                    TextField("https://quan-ly-noi-bo.example", text: $server)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .keyboardType(.URL).textContentType(.URL)
                        .padding(13).background(Palette.bg, in: RoundedRectangle(cornerRadius: 10))
                    Text("Access token").font(.caption).foregroundStyle(Palette.secondary)
                    SecureField("Token từ Windows", text: $secret)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .padding(13).background(Palette.bg, in: RoundedRectangle(cornerRadius: 10))
                }
                Button {
                    do {
                        try model.saveConnection(url: server, token: secret)
                        Task { await model.load() }
                    } catch {
                        model.error = error.localizedDescription
                    }
                } label: {
                    Label("Lưu và kết nối", systemImage: "link")
                        .frame(maxWidth: .infinity)
                }.buttonStyle(.borderedProminent)
                Text("Điều khiển từ xa: cài và bật Tailscale trên iPhone. Nhập địa chỉ HTTPS của máy Windows do Tailscale Serve cung cấp, ví dụ https://viepn-pc.tailnet-name.ts.net.")
                    .font(.caption).foregroundStyle(Palette.secondary)
                Text("Access token được lưu trong Keychain. Ứng dụng từ chối HTTP qua Internet; HTTP LAN chỉ dùng để thử nghiệm.")
                    .font(.caption).foregroundStyle(.orange)
            }
            StatusView()
            Panel {
                Label("Thông báo IPA trên iPhone", systemImage: "bell.badge.fill")
                    .font(.headline).foregroundStyle(Palette.mint)
                Text("ViePN có thể gửi cảnh báo sắp hết hạn, ký thất bại và gia hạn thành công qua ứng dụng ntfy (cài riêng). Không yêu cầu quyền APNs cho app ViePN ký bằng Apple ID miễn phí.")
                    .font(.footnote).foregroundStyle(Palette.secondary)
                Text("Trên máy Windows mở dashboard localhost → Cài đặt → Thông báo trên iPhone → Bật, gửi thử và sao chép topic. Trên iPhone, mở ntfy và Subscribe chính topic đó.")
                    .font(.footnote).foregroundStyle(Palette.secondary)
                if let link = URL(string: "https://ntfy.sh/") {
                    Link(destination: link) {
                        Label("Tìm hiểu và cài ứng dụng ntfy", systemImage: "arrow.up.right.square")
                    }.buttonStyle(.bordered)
                }
                Text("Chỉ có cảnh báo khi Windows bật, ViePN đang chạy và người dùng đã bật gửi qua ntfy.sh. Dịch vụ ntfy là bên thứ ba.")
                    .font(.caption).foregroundStyle(.orange)
            }
            Panel {
                Text("Thiết bị nhận diện trên Windows").font(.headline)
                ForEach(model.devices) { device in
                    Label(device.name, systemImage: "iphone")
                        .font(.subheadline)
                    Text(device.id).font(.caption2).foregroundStyle(Palette.secondary)
                }
                Button { Task { await model.load() } } label: {
                    Label("Quét lại", systemImage: "arrow.clockwise")
                }.buttonStyle(.bordered)
            }
        }
        .onAppear { server = model.serverURL; secret = model.token }
    }
}
