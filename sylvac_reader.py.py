# sylvac_reader.py
import ctypes
import ctypes.wintypes as wintypes
import win32con
import win32gui
import win32api
import time
import re
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import signal
from pathlib import Path
import mysql.connector
from datetime import datetime
from zoneinfo import ZoneInfo

# Optional: config.ini support
import configparser

# ------------------------------
# Logging setup (file + console)
# ------------------------------
def setup_logging() -> logging.Logger:
    logger = logging.getLogger("SylvacMySQLLogger")
    logger.setLevel(logging.DEBUG)

    # Log directory next to the script or CWD fallback
    try:
        base_dir = Path(__file__).resolve().parent
    except Exception:
        base_dir = Path.cwd()

    log_dir = base_dir / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_dir = Path.cwd()

    log_file = log_dir / "sylvac_mysql.log"

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    file_handler.setFormatter(file_fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_fmt)

    # Avoid duplicate handlers on rerun
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log uncaught exceptions
    def _excepthook(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook
    return logger

logger = setup_logging()

# ------------------------------
# OS guard
# ------------------------------
if sys.platform != "win32":
    logger.error("This script supports Windows only. Exiting.")
    print("This script supports Windows only. Exiting.")
    sys.exit(1)

# ------------------------------
# Config
# ------------------------------
def load_config():
    cfg = configparser.ConfigParser()
    try:
        cfg.read((Path(__file__).parent / "config.ini"))
    except Exception:
        pass
    return cfg

CFG = load_config()
TZ = ZoneInfo(CFG.get("reader", "timezone", fallback=os.getenv("TZ", "Asia/Kolkata")))
MAPPING_REFRESH_SECONDS = CFG.getint("reader", "mapping_refresh_seconds", fallback=int(os.getenv("MAPPING_REFRESH_SECONDS", "30")))

DB_HOST = CFG.get("mysql", "host", fallback=os.getenv("DB_HOST", "localhost"))
DB_USER = CFG.get("mysql", "user", fallback=os.getenv("DB_USER", "bluetooth_app"))
DB_PASSWORD = CFG.get("mysql", "password", fallback=os.getenv("DB_PASSWORD", "Strong_Password_ChangeMe!"))
DB_NAME = CFG.get("mysql", "database", fallback=os.getenv("DB_NAME", "bluetooth_sensor_db"))

# ------------------------------
# MySQL Database Functions
# ------------------------------
class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=False,
                connection_timeout=5,
            )
            logger.info("✅ Database connection successful.")
            return True
        except mysql.connector.Error as err:
            logger.error(f"❌ Database connection failed: {err}")
            self.conn = None
            return False

    def ensure_connection(self):
        """Check connection and reconnect if needed."""
        try:
            if self.conn is None or not self.conn.is_connected():
                logger.warning("Database connection lost. Attempting to reconnect...")
                return self.connect()
            return True
        except Exception as e:
            logger.error(f"Error checking database connection: {e}")
            return self.connect()

    def insert_reading(self, device_mac, equipment_name, value, timestamp):
        """Insert Sylvac reading into database."""
        if not self.ensure_connection():
            logger.error("Cannot insert reading - no database connection")
            return False

        cursor = None
        try:
            cursor = self.conn.cursor()
            # Save device_mac and mapped equipmentName with IST timestamp
            query = """INSERT INTO bluetooth_sensor_value 
                       (device_mac, equipmentName, value, CRTD) 
                       VALUES (%s, %s, %s, %s)"""
            cursor.execute(query, (device_mac, equipment_name, value, timestamp))
            self.conn.commit()
            msg = f"✅ Reading saved → MAC: {device_mac}, Equip: {equipment_name}, Value: {value}, Time: {timestamp}"
            logger.info(msg)
            print(msg)
            return True
        except mysql.connector.Error as err:
            logger.error(f"❌ Database error during insert: {err}")
            if self.conn:
                self.conn.rollback()
            return False
        except Exception as e:
            logger.exception(f"Unexpected error during database insert: {e}")
            if self.conn:
                self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def fetch_mapping(self):
        """Return dict mac->equipmentName from mac_equipment_map."""
        if not self.ensure_connection():
            return {}
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT mac, equipmentName FROM mac_equipment_map")
            data = dict(cur.fetchall())
            cur.close()
            return data
        except Exception:
            logger.exception("Failed to fetch mapping from DB")
            return {}

    def close(self):
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("🔌 Database connection closed.")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

# Global database manager instance
db_manager = None

# ------------------------------
# Windows constants & structs
# ------------------------------
RID_INPUT = 0x10000003
RIM_TYPEKEYBOARD = 1
RIDEV_INPUTSINK = 0x00000100
WM_INPUT = 0x00FF

HOGP_GUID = "{00001812-0000-1000-8000-00805f9b34fb}".lower()  # BLE HOGP

try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
except Exception:
    user32 = ctypes.windll.user32

try:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
except Exception:
    kernel32 = ctypes.windll.kernel32

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND)
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM)
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG)
    ]

class RAWINPUTUNION(ctypes.Union):
    _fields_ = [("keyboard", RAWKEYBOARD)]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWINPUTUNION)
    ]

# ------------------------------
# Helper functions
# ------------------------------
def extract_mac_from_device_path(path: str):
    """Extract MAC address from device path for BLE HOGP devices."""
    try:
        p = path.lower()
        if HOGP_GUID not in p:
            return None
        m = re.search(r'_([0-9a-f]{12})(?=#)', p)
        mac = m.group(1) if m else None
        if mac is None:
            logger.debug("HOGP device path matched but no MAC found: %s", path)
        return mac
    except Exception:
        logger.exception("Failed to extract MAC from device path: %s", path)
        return None

# Optional: Validate reading format like +003.892
READING_RE = re.compile(r'^[+-]?\d{1,3}\.\d{3}$')

def validate_reading(reading: str) -> bool:
    """Validate if reading matches expected format."""
    if READING_RE.match(reading):
        return True
    # Keep loose; just log
    logger.debug("Reading did not match expected pattern: %s", reading)
    return False

def get_raw_input_device_info(device_handle):
    """Return device path (unique ID string) or 'Unknown device' on failure."""
    try:
        RIDI_DEVICENAME = 0x20000007
        size = wintypes.UINT(0)
        res = user32.GetRawInputDeviceInfoW(
            device_handle, RIDI_DEVICENAME, None, ctypes.byref(size)
        )
        if res == 0xFFFFFFFF:
            err = ctypes.get_last_error()
            logger.warning("GetRawInputDeviceInfoW(size) failed. GetLastError=%s", err)
            return "Unknown device"

        if size.value == 0:
            logger.debug("GetRawInputDeviceInfoW returned size=0 for handle=%s", device_handle)
            return "Unknown device"

        name_buffer = ctypes.create_unicode_buffer(size.value)
        res = user32.GetRawInputDeviceInfoW(
            device_handle, RIDI_DEVICENAME, name_buffer, ctypes.byref(size)
        )
        if res == 0xFFFFFFFF:
            err = ctypes.get_last_error()
            logger.warning("GetRawInputDeviceInfoW(buffer) failed. GetLastError=%s", err)
            return "Unknown device"

        return name_buffer.value
    except Exception:
        logger.exception("Error calling GetRawInputDeviceInfoW.")
        return "Unknown device"

def register_for_raw_input(hwnd):
    """Register hidden window for raw keyboard events."""
    try:
        rid = RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, hwnd)  # UsagePage=1 (Generic Desktop), Usage=6 (Keyboard)
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            raise ctypes.WinError(ctypes.get_last_error())
        logger.info("Registered for RAWINPUT (keyboard) successfully.")
        return True
    except Exception:
        logger.exception("RegisterRawInputDevices failed.")
        return False

def flush_console_input_buffer() -> bool:
    """Clear any queued keystrokes in the console input buffer."""
    try:
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        STD_INPUT_HANDLE = -10
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        h_in = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        if not h_in or h_in == INVALID_HANDLE_VALUE:
            return False
        ok = kernel32.FlushConsoleInputBuffer(h_in)
        if not ok:
            err = ctypes.get_last_error()
            logger.debug("FlushConsoleInputBuffer failed: %s", err)
        return bool(ok)
    except Exception:
        logger.exception("flush_console_input_buffer failed")
        return False

def drain_rawinput(timeout: float = 0.2):
    """Pump messages briefly to process any last WM_INPUT after Ctrl+C."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            win32gui.PumpWaitingMessages()
        except Exception:
            logger.exception("PumpWaitingMessages during drain failed")
            break
        time.sleep(0.005)

def flush_internal_buffers(flush_partial: bool = False):
    """Optionally log or discard partial readings before exit."""
    try:
        for mac, reading in list(device_buffers.items()):
            if reading and flush_partial:
                handle_complete_reading(mac, reading)
            device_buffers[mac] = ''
        last_event_time.clear()
    except Exception:
        logger.exception("Failed to flush internal buffers")

# ------------------------------
# Mapping cache (mac -> equipmentName)
# ------------------------------
_mapping_cache = {}
_last_mapping_load = 0.0

def refresh_mapping_if_needed():
    global _mapping_cache, _last_mapping_load
    now = time.time()
    if now - _last_mapping_load < MAPPING_REFRESH_SECONDS:
        return
    try:
        mapping = db_manager.fetch_mapping() if db_manager else {}
        if mapping:
            _mapping_cache = mapping
            _last_mapping_load = now
            logger.info("🔄 Mapping refreshed: %d entries", len(_mapping_cache))
    except Exception:
        logger.exception("Failed to refresh mapping")

def get_equipment_for_mac(mac: str) -> str:
    refresh_mapping_if_needed()
    return _mapping_cache.get(mac, mac)

# ------------------------------
# Main data handling
# ------------------------------
device_buffers = {}
last_event_time = {}
READING_TIMEOUT = 0.5
ignored_devices = set()

def handle_complete_reading(mac: str, reading: str):
    """Process and save complete reading to database."""
    global db_manager
    try:
        if not reading:
            return

        # Clean reading
        reading = reading.strip()

        # Optional strict validation; keep loose by default
        # if not validate_reading(reading):
        #     return

        # Convert to float
        try:
            value_float = float(reading)
        except ValueError as e:
            logger.error(f"Cannot convert reading to float: {reading} - {e}")
            return

        # IST timestamp (DATETIME(6) format)
        ist_time = datetime.now(TZ)
        ts_str = ist_time.strftime("%Y-%m-%d %H:%M:%S.%f")

        # Resolve equipmentName via mapping (fallback to mac if unmapped)
        equipment = get_equipment_for_mac(mac)

        # Log to console + file
        console_msg = f"{ts_str} MAC: {mac} Equip: {equipment} Value: {value_float:.3f}"
        print(f"📊 Reading received: {console_msg}")
        logger.info(f"Reading received: MAC={mac}, Equip={equipment}, Value={value_float}")

        # Save to database
        if db_manager:
            ok = db_manager.insert_reading(mac, equipment, value_float, ts_str)
            if not ok:
                logger.warning("Failed to save reading to database")
        else:
            logger.warning("No database connection - reading not saved")

    except Exception:
        logger.exception("Failed to handle complete reading. mac=%s reading=%s", mac, reading)

def handle_input(lparam):
    """Process raw input from HID devices."""
    try:
        dwSize = wintypes.UINT(0)
        res = user32.GetRawInputData(
            lparam, RID_INPUT, None, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER)
        )
        if res == 0xFFFFFFFF:
            err = ctypes.get_last_error()
            logger.warning("GetRawInputData(size) failed. GetLastError=%s", err)
            return
        if dwSize.value == 0:
            logger.debug("GetRawInputData returned size=0")
            return

        buffer = ctypes.create_string_buffer(dwSize.value)
        ret = user32.GetRawInputData(
            lparam, RID_INPUT, buffer, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER)
        )
        if ret == 0xFFFFFFFF or ret == 0 or ret != dwSize.value:
            err = ctypes.get_last_error()
            logger.warning(
                "GetRawInputData(buffer) unexpected ret=%s size=%s GetLastError=%s",
                ret, dwSize.value, err
            )
            return

        raw = RAWINPUT.from_buffer_copy(buffer)
        if raw.header.dwType != RIM_TYPEKEYBOARD:
            return

        device_name = get_raw_input_device_info(raw.header.hDevice)

        # Only accept BLE HOGP dials
        mac = extract_mac_from_device_path(device_name)
        if not mac:
            if device_name not in ignored_devices:
                ignored_devices.add(device_name)
                logger.info("Ignored non-HOGP device: %s", device_name)
            return

        key_code = raw.data.keyboard.VKey
        flags = raw.data.keyboard.Flags

        # Key down only (Flags==0 for make)
        if flags != 0:
            return

        # Convert key code to character
        try:
            char_code = win32api.MapVirtualKey(int(key_code), 2)
        except Exception:
            logger.exception("MapVirtualKey failed for key_code=%s", key_code)
            char_code = 0

        key_char = chr(char_code) if char_code != 0 else ''

        if key_char == '\r':  # Enter ends a reading
            reading = device_buffers.get(mac, '')
            if reading:
                handle_complete_reading(mac, reading)
            device_buffers[mac] = ''
        elif key_char:
            now = time.time()
            last_time = last_event_time.get(mac, 0.0)
            if now - last_time > READING_TIMEOUT and device_buffers.get(mac, ''):
                handle_complete_reading(mac, device_buffers[mac])
                device_buffers[mac] = ''
            device_buffers[mac] = device_buffers.get(mac, '') + key_char
            last_event_time[mac] = now
        else:
            logger.debug("Ignored non-printable key. key_code=%s device=%s", key_code, mac)

    except Exception:
        logger.exception("Unexpected error in handle_input")

# ------------------------------
# Window procedure
# ------------------------------
def wnd_proc(hwnd, msg, wparam, lparam):
    try:
        if msg == WM_INPUT:
            handle_input(lparam)
        elif msg == win32con.WM_DESTROY:
            try:
                win32gui.PostQuitMessage(0)
            except Exception:
                logger.exception("PostQuitMessage failed.")
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    except Exception:
        logger.exception("Exception in window procedure (WndProc).")
        try:
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        except Exception:
            return 0

# ------------------------------
# Graceful shutdown helpers
# ------------------------------
_shutdown_flag = False

def _on_signal(signum, frame):
    global _shutdown_flag
    _shutdown_flag = True
    logger.info("Received signal %s. Preparing to exit...", signum)
    flush_console_input_buffer()

for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
    if sig is not None:
        try:
            signal.signal(sig, _on_signal)
        except Exception:
            pass

# ------------------------------
# Main
# ------------------------------
def main():
    global db_manager

    logger.info("Starting Sylvac to MySQL Logger...")
    print("=" * 60)
    print("🚀 Sylvac HID Reader with MySQL Database Integration")
    print("=" * 60)

    # Initialize database connection
    db_manager = DatabaseManager()
    if not db_manager.conn:
        print("⚠️  Warning: Running without database connection.")
        print("    Readings will be displayed but not saved.")
    else:
        print("✅ Database connected successfully.")

    print("\n📡 Listening for HID dials (HID keyboard mode)...")
    print("🔹 Send readings from each dial - they will be saved to database")
    print("🔹 Press Ctrl+C to exit safely.\n")
    print("-" * 60)

    hwnd = None
    try:
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "SylvacMySQLLogger"
        wc.lpfnWndProc = wnd_proc
        try:
            atom = win32gui.RegisterClass(wc)
        except Exception:
            logger.debug("RegisterClass failed; attempting to get existing class.")
            atom = wc.lpszClassName

        try:
            hwnd = win32gui.CreateWindow(atom, "SylvacMySQLLogger", 0, 0, 0, 0, 0, 0, 0, 0, None)
        except Exception:
            logger.exception("CreateWindow failed. Exiting.")
            print("Failed to create hidden window. See logs for details.")
            return

        if not register_for_raw_input(hwnd):
            print("Failed to register for RAWINPUT. See logs for details.")
            return

        # Initial mapping load
        refresh_mapping_if_needed()

        # Message pump
        while not _shutdown_flag:
            try:
                win32gui.PumpWaitingMessages()
                time.sleep(0.01)
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received in message pump.")
                break
            except Exception:
                logger.exception("PumpWaitingMessages error; continuing.")
                time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received in main loop.")
    except Exception:
        logger.exception("Fatal error in main loop.")
    finally:
        try:
            print("\n" + "-" * 60)
            print("🛑 Shutting down...")

            # Finish processing any last messages
            drain_rawinput(0.2)

            # Flush partial readings
            flush_internal_buffers(flush_partial=False)

            # Clear console keystrokes
            flush_console_input_buffer()
            time.sleep(0.05)
            flush_console_input_buffer()

            # Close database connection
            if db_manager:
                db_manager.close()

        except Exception:
            logger.exception("Shutdown cleanup failed")

        print("✅ Stopped listening. Goodbye!")
        if hwnd:
            try:
                win32gui.DestroyWindow(hwnd)
            except Exception:
                logger.exception("DestroyWindow failed during shutdown.")

if __name__ == "__main__":
    main()