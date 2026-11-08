import Foundation
import CoreBluetooth
import SwiftUI

/// Optional foreground Bluetooth LE peripheral. No Apple UDID, password,
/// session cookie or ViePN API token is broadcast over the air.
/// Windows recognizes the ephemeral UUID only after Tailscale registration.
@MainActor
final class ViePNBLEPeripheral: NSObject, ObservableObject, CBPeripheralManagerDelegate {
    static let serviceID = CBUUID(string: "2A4E9A9D-5F50-42B9-86BA-92D2670979C3")
    static let tokenID = CBUUID(string: "2A4E9A9D-5F50-42B9-86BA-92D2670979C4")

    @Published private(set) var status = "Bluetooth đang tắt trong ViePN"
    @Published private(set) var active = false
    @Published private(set) var enabled = false
    let token = UUID().uuidString.lowercased()
    private var peripheral: CBPeripheralManager?
    private var serviceReady = false

    func enable() {
        guard !enabled else { return }
        enabled = true
        status = "Đang kiểm tra quyền Bluetooth..."
        if peripheral == nil {
            peripheral = CBPeripheralManager(delegate: self, queue: nil)
        } else {
            configureIfPoweredOn()
        }
    }

    func disable() {
        enabled = false
        active = false
        peripheral?.stopAdvertising()
        peripheral?.removeAllServices()
        serviceReady = false
        status = "Bluetooth đang tắt trong ViePN"
    }

    func peripheralManagerDidUpdateState(_ manager: CBPeripheralManager) {
        switch manager.state {
        case .poweredOn:
            configureIfPoweredOn()
        case .poweredOff:
            active = false
            status = "Hãy bật Bluetooth trong Cài đặt iPhone"
        case .unauthorized:
            active = false
            status = "ViePN chưa được cấp quyền Bluetooth trong Cài đặt iPhone"
        case .unsupported:
            active = false
            status = "Thiết bị iOS không hỗ trợ Bluetooth LE Peripheral"
        default:
            active = false
            status = "Đang khởi tạo Bluetooth..."
        }
    }

    private func configureIfPoweredOn() {
        guard enabled, let manager = peripheral, manager.state == .poweredOn else { return }
        guard !serviceReady else { return }
        serviceReady = true
        let characteristic = CBMutableCharacteristic(
            type: Self.tokenID, properties: [.read], value: nil,
            permissions: [.readable]
        )
        let service = CBMutableService(type: Self.serviceID, primary: true)
        service.characteristics = [characteristic]
        manager.add(service)
    }

    func peripheralManager(_ peripheral: CBPeripheralManager, didAdd service: CBService, error: Error?) {
        guard enabled else { return }
        if error != nil {
            serviceReady = false
            status = "Không thể khởi tạo dịch vụ BLE"
            return
        }
        peripheral.startAdvertising([
            CBAdvertisementDataServiceUUIDsKey: [Self.serviceID],
            CBAdvertisementDataLocalNameKey: "ViePN"
        ])
        status = "Đang phát Bluetooth ViePN trong phạm vi gần"
    }

    func peripheralManagerDidStartAdvertising(_ peripheral: CBPeripheralManager, error: Error?) {
        active = enabled && error == nil
        if error != nil { status = "Không phát được tín hiệu BLE; kiểm tra quyền Bluetooth" }
    }

    func peripheralManager(_ peripheral: CBPeripheralManager, didReceiveRead request: CBATTRequest) {
        guard enabled && request.characteristic.uuid == Self.tokenID else {
            peripheral.respond(to: request, withResult: .readNotPermitted)
            return
        }
        let bytes = Data(token.utf8)
        guard request.offset <= bytes.count else {
            peripheral.respond(to: request, withResult: .invalidOffset)
            return
        }
        request.value = bytes.subdata(in: request.offset..<bytes.count)
        peripheral.respond(to: request, withResult: .success)
    }
}
