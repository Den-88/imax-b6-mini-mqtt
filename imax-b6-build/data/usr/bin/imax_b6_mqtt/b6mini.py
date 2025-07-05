import usb.core
import usb.util

IMAX_VID = 0x0000; IMAX_PID = 0x0001
CMD_GET_DEVINFO = 0x57; CMD_GET_CHG = 0x55; CMD_GET_SYS = 0x5A
CMD_STOP = 0xFE

MODE_CHARGE     = 0x00; MODE_DISCHARGE  = 0x01
MODE_STORAGE    = 0x02; MODE_FASTCHARGE = 0x03
BAT_LIPO = 0x00; BAT_LILO = 0x01; BAT_LIFE = 0x02; BAT_LIHV = 0x03
BAT_NIMH = 0x04; BAT_NICD = 0x05; BAT_PB = 0x06

class B6Mini:
    def __init__(self):
        self._device = get_usb_device(IMAX_VID, IMAX_PID)

    def stop(self):
        return self._send([0x03, CMD_STOP, 0x00])

    def charge(self, battery_type, cells, current, max_voltage):
        return self._charge_cmd(battery_type, cells, MODE_CHARGE, current, 0.0, 0.0, max_voltage)

    def discharge(self, battery_type, cells, current, min_voltage):
        return self._charge_cmd(battery_type, cells, MODE_DISCHARGE, 0.0, current, min_voltage, 0.0)

    def storage(self, battery_type, cells, current, storage_voltage):
        discharge_current = min(1.0, current)
        return self._charge_cmd(battery_type, cells, MODE_STORAGE, current, discharge_current, 0.0, storage_voltage)

    def fastcharge(self, battery_type, cells, current, max_voltage):
        return self._charge_cmd(battery_type, cells, MODE_FASTCHARGE, current, 0.0, 0.0, max_voltage)

    def get_charge_info(self):
        return ChargeInfo(self._send([0x03, CMD_GET_CHG, 0x00]))

    def get_sys_info(self):
        return SysInfo(self._send([0x03, CMD_GET_SYS, 0x00]))

    def get_dev_info(self):
        return DeviceInfo(self._send([0x03, CMD_GET_DEVINFO, 0x00]))

    def _charge_cmd(self, bat, cells, mode, chg_current, dsc_current, voltage_low, voltage_high):
        cmd = [ 0x16, 0x05, 0x00 ]
        cmd.append(bat)
        cmd.append(cells)
        cmd.append(mode)
        append2b(cmd, int(chg_current * 1000))
        append2b(cmd, int(dsc_current * 1000))
        append2b(cmd, int(voltage_low * 1000))
        append2b(cmd, int(voltage_high * 1000))
        cmd = cmd + [0x00]*8
        return self._send(cmd, debug=True)

    def _send(self, cmd, debug = False):
        tries = 5
        data = [0x0F]
        data += cmd
        data.append(calc_checksum(data))
        data += [0xFF, 0xFF]
        while(1):
            tries -= 1
            try:
                if debug:
                    print("SEND: ", hexstr(data))
                assert self._device.write(0x1, data) == len(data)
                reply = self._device.read(0x81, 64, 500)
                break
            except usb.core.USBError:
                if tries == 0:
                    raise
                print("Send Failed... retry.")
                pass
        if debug:
            print("REPLY: ", hexstr(reply))
        return reply

def read2b(p): return next(p) * 256 + next(p)
def append2b(arr, num): arr.extend([num >> 8, num & 0xFF])
def calc_checksum(cmd): return sum(cmd[2:]) & 0xFF
def hexstr(d): return ["0x%02X" % v for v in d]
def get_usb_device(vid, pid):
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None: raise ValueError(f"Device {vid:04x}:{pid:04x} not found")
    print("Device found: ", dev.product, "by", dev.manufacturer)
    try:
        if dev.is_kernel_driver_active(0):
            print("Detaching kernel driver...")
            dev.detach_kernel_driver(0)
        dev.set_configuration()
    except usb.core.USBError as e:
        raise IOError(f"Could not set configuration on device: {e}")
    return dev

class ChargeInfo:
    _STATES = {0: "0", 1: "РАБОТАЕТ", 2: "ОЖИДАНИЕ", 3: "ГОТОВО", 4: "ОШИБКА", 5: "ЗАРЯДКА НЕ ТРЕБУЕТСЯ"}
    def __init__(self, b):
        assert len(b) > 29
        p = iter(b[4:])
        self.state = next(p)
        self.mah = read2b(p)
        self.time_sec = read2b(p)
        self.voltage = read2b(p) / 1000.0
        self.current = read2b(p)
        self.tempExt = next(p)
        self.tempInt = next(p)
        self.impedanceInt = read2b(p)
        self.cells = [read2b(p)/1000.0 for _ in range(6)]
    def state_str(self): return self._STATES.get(self.state, f"<{self.state}>")

class SysInfo:
    def __init__(self, b):
        p = iter(b[4:])
        self.cycleTime, self.timeLimitOn, self.timeLimit = next(p), next(p), read2b(p)
        self.capLimitOn, self.capLimit, self.keyBuzz, self.sysBuzz = next(p), read2b(p), next(p), next(p)
        self.inDClow, _, _, self.tempLimit = read2b(p) / 1000.0, next(p), next(p), next(p)
        self.voltage = read2b(p) / 1000.0
        self.cells = [read2b(p) / 1000.0 for _ in range(6)]

class DeviceInfo:
    def __init__(self, b):
        p = iter(b[13:])
        self.sw_version = next(p) + next(p) / 100.0
        self.hw_version = next(p)
