#!/usr/bin/env python3
"""Watch KVM USB hub; switch QSN-CBB input via DDC (m1ddc) and notify."""
import ctypes, time, datetime, subprocess, sys, os, logging
from logging.handlers import RotatingFileHandler

LOG_PATH = os.path.expanduser('~/Library/Logs/kvm-usb-watch.log')
_h = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
_h.setFormatter(logging.Formatter('%(message)s'))
_logger = logging.getLogger('kvm'); _logger.setLevel(logging.INFO); _logger.addHandler(_h)

HUB_VID, HUB_PID = 0x1A40, 0x0801
HUB_LOC = 0x03132200  # exact location of KVM USB 2.0 Hub on this Mac
DEBOUNCE_S = 0.40
M1DDC = '/opt/homebrew/bin/m1ddc'
INPUT_WIN = 15   # DP1, reads back as 16
INPUT_MAC = 18   # HDMI2
OK_READ = {INPUT_WIN: (15, 16), INPUT_MAC: (18,)}
RECHECK_S = 10.0  # after switching to Windows, verify monitor stayed there

def ddc(*args):
    try:
        r = subprocess.run([M1DDC, 'display', '1', *map(str, args)], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception as e:
        return f'ERR {e}'

def switch_input(target):
    for attempt in range(1, 4):
        ddc('set', 'input', target)
        time.sleep(0.8)
        got = ddc('get', 'input')
        try: gv = int(got)
        except ValueError: gv = None
        log(f'DDC set input {target} attempt {attempt} -> read {got}')
        if gv in OK_READ[target]:
            return True
    return False

iokit = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/IOKit.framework/IOKit')
cf = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
vp, u32, u64 = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64
iokit.IOServiceMatching.restype = vp
iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
iokit.IOServiceGetMatchingServices.argtypes = [u32, vp, ctypes.POINTER(u32)]
iokit.IOIteratorNext.restype = u32
iokit.IOIteratorNext.argtypes = [u32]
iokit.IOObjectRelease.argtypes = [u32]
iokit.IORegistryEntryCreateCFProperty.restype = vp
iokit.IORegistryEntryCreateCFProperty.argtypes = [u32, vp, vp, u32]
cf.CFStringCreateWithCString.restype = vp
cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, u32]
cf.CFNumberGetValue.argtypes = [vp, ctypes.c_int, vp]
cf.CFGetTypeID.argtypes = [vp]
cf.CFGetTypeID.restype = u64
cf.CFNumberGetTypeID.restype = u64

def cfs(s):
    return cf.CFStringCreateWithCString(None, s.encode(), 0x08000100)

def pnum(svc, key):
    p = iokit.IORegistryEntryCreateCFProperty(svc, cfs(key), None, 0)
    if not p or cf.CFGetTypeID(p) != cf.CFNumberGetTypeID():
        return None
    v = ctypes.c_int64()
    if cf.CFNumberGetValue(p, 4, ctypes.byref(v)):
        return int(v.value)
    return None

def hub_present():
    it = u32()
    iokit.IOServiceGetMatchingServices(0, iokit.IOServiceMatching(b'IOUSBHostDevice'), ctypes.byref(it))
    found = False
    while True:
        s = iokit.IOIteratorNext(it.value)
        if not s:
            break
        vid, pid, loc = pnum(s, 'idVendor'), pnum(s, 'idProduct'), pnum(s, 'locationID')
        iokit.IOObjectRelease(s)
        if vid == HUB_VID and pid == HUB_PID and loc == HUB_LOC:
            found = True
            # keep draining iterator
    iokit.IOObjectRelease(it.value)
    return found

def notify(title, body):
    # macOS notification via osascript
    script = f'display notification "{body}" with title "{title}"'
    try:
        subprocess.run(['osascript', '-e', script], check=False, timeout=5)
    except Exception as e:
        log(f'notify_err {e}')

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
    _logger.info(f'{ts} {msg}')

def main():
    present = hub_present()
    log(f'READY hub_present={present} (watching {HUB_LOC:08x} {HUB_VID:04x}:{HUB_PID:04x})')
    notify('KVM Watch', f'监听已启动，当前键鼠在本机={present}')
    last_stable = present
    pending = None  # None or bool candidate after debounce start
    pending_since = 0.0
    recheck_at = None
    while True:
        now = time.time()
        cur = hub_present()
        if cur != last_stable:
            if pending is None or pending != cur:
                pending = cur
                pending_since = now
            elif now - pending_since >= DEBOUNCE_S:
                last_stable = pending
                pending = None
                if last_stable:
                    log('ACTION: 键鼠回到 Mac -> HDMI2')
                    recheck_at = None
                    ok = switch_input(INPUT_MAC)
                    notify('KVM', '已切到 Mac (HDMI2)' if ok else '切 HDMI2 失败')
                else:
                    log('ACTION: 键鼠离开 Mac -> Windows DP1')
                    ok = switch_input(INPUT_WIN)
                    notify('KVM', '已切到 Windows (DP1)' if ok else '切 DP1 失败')
                    recheck_at = time.time() + RECHECK_S
        else:
            pending = None
        if recheck_at and time.time() >= recheck_at:
            recheck_at = None
            if not last_stable:
                got = ddc('get', 'input')
                log(f'RECHECK {RECHECK_S:.0f}s after DP1: input={got}')
                if got.strip() == str(INPUT_MAC):
                    log('WARN: 显示器已回 HDMI2 但键鼠仍在 Windows（Windows 可能关机/无信号）')
                    notify('KVM', 'Windows 无信号，显示器回到了 Mac，请按 KVM 切回')
        time.sleep(0.1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
