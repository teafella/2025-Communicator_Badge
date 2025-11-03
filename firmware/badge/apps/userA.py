"""Bluetooth HID Keyboard app for the Communicator Badge."""

import time
from apps.base_app import BaseApp
from ui.page import Page
import ui.styles as styles
import lvgl

# Check if Bluetooth is available
BLUETOOTH_AVAILABLE = False
try:
    import bluetooth
    from micropython import const
    BLUETOOTH_AVAILABLE = True
    print("BT Keyboard: Bluetooth module found!")
except ImportError:
    print("BT Keyboard: Bluetooth module not available in this build")


# Keyboard scan codes (simplified set)
KEY_CODES = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
    'y': 0x1C, 'z': 0x1D,
    '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22,
    '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    '\n': 0x28, '\x1b': 0x29, '\b': 0x2A, '\t': 0x2B, ' ': 0x2C,
    '-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30, '\\': 0x31,
    ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36, '.': 0x37, '/': 0x38,
    '`l': 0x4F, '`h': 0x50, '`k': 0x51, '`j': 0x52, '\x7f': 0x4C,
}

# Modifier keys
MOD_LCTRL = 0x01
MOD_LSHIFT = 0x02
MOD_LALT = 0x04


class SimpleBLEKeyboard:
    """BLE HID Keyboard with proper service registration."""
    
    def __init__(self, debug_callback=None):
        self.debug_callback = debug_callback

        self._debug("Initializing BLE with HID...")
        
        self._debug("Creating BLE object...")
        self.ble = bluetooth.BLE()
        self._debug("Activating BLE...")
        self.ble.active(True)
        self._debug("Setting up variables...")
        self.connected = False
        self.advertising = False
        self.conn_handle = None
        
        # Set up callback for BLE events
        self._debug("Setting up IRQ callback...")
        self.ble.irq(self._ble_irq)
        
        # Register HID services
        self._debug("About to register services...")
        self._register_services()
        self._debug("HID keyboard ready")
        
    def _debug(self, message):
        """Send debug message to callback if available."""
        print(f"BLE: {message}")
        if self.debug_callback:
            self.debug_callback(f"BLE: {message}")
        
    def _ble_irq(self, event, data):
        """Handle BLE events."""
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, _, _ = data
            self.conn_handle = conn_handle
            self.connected = True
            print(f"BLE: Device connected! Handle: {conn_handle}")
        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            self.connected = False
            self.conn_handle = None
            print("BLE: Device disconnected")
            
    def _register_services(self):
        """Diagnostic test of gatts_register_services with different approaches."""
        self._debug("Testing service registration...")
        
        # First, let's see what bluetooth constants are available
        try:
            self._debug(f"FLAG_READ = {bluetooth.FLAG_READ}")
            self._debug(f"FLAG_WRITE = {bluetooth.FLAG_WRITE}")
            self._debug(f"FLAG_NOTIFY = {bluetooth.FLAG_NOTIFY}")
        except Exception as e:
            self._debug(f"Flag inspection failed: {e}")
        
        # Test 1: Try without any services (empty)
        try:
            self._debug("Test 1 - Empty services")
            self.handles = self.ble.gatts_register_services(())
            self._debug("Empty services worked!")
            return
        except Exception as e:
            self._debug(f"Empty services failed: {e}")
        
        # Test 2: Try with bytes UUID instead of bluetooth.UUID
        try:
            self._debug("Test 2 - Bytes UUID")
            service_uuid = b'\x12\x34'  # 16-bit UUID as bytes
            char_uuid = b'\x56\x78'
            
            char = (char_uuid, bluetooth.FLAG_READ)
            service = (service_uuid, (char,))
            
            self.handles = self.ble.gatts_register_services((service,))
            self.report_handle = self.handles[0][0]
            self._debug("Bytes UUID worked!")
            return
        except Exception as e:
            self._debug(f"Bytes UUID failed: {e}")
        
        # Test 3: Try with integer flags instead of constants
        try:
            self._debug("Test 3 - Integer flags")
            SERVICE_UUID = bluetooth.UUID(0x1234)
            CHAR_UUID = bluetooth.UUID(0x5678)
            
            char = (CHAR_UUID, 0x02)  # Use raw integer instead of FLAG_READ
            service = (SERVICE_UUID, (char,))
            
            self.handles = self.ble.gatts_register_services((service,))
            self.report_handle = self.handles[0][0]
            self._debug("Integer flags worked!")
            return
        except Exception as e:
            self._debug(f"Integer flags failed: {e}")
        
        self._debug("All tests failed!")
            
    def start_advertising(self):
        """Start advertising as a keyboard."""
        if self.advertising:
            return
            
        print("BLE: Starting advertising as HID keyboard...")
        
        # Advertising data
        name = "Badge Keyboard"
        adv_data = bytearray()
        
        # Flags: LE General Discoverable, BR/EDR not supported
        adv_data.extend(b'\x02\x01\x06')
        
        # Appearance: Keyboard (0x03C1)
        adv_data.extend(b'\x03\x19\xC1\x03')
        
        # Complete local name
        name_bytes = name.encode('utf-8')
        adv_data.extend(bytes([len(name_bytes) + 1, 0x09]) + name_bytes)
        
        # Scan response data with HID service UUID
        scan_resp = bytearray()
        # Complete list of 16-bit service UUIDs: HID Service (0x1812)
        scan_resp.extend(b'\x03\x03\x12\x18')
        
        self.ble.gap_advertise(100000, adv_data=adv_data, resp_data=scan_resp)
        self.advertising = True
        print("BLE: Now advertising as HID keyboard 'Badge Keyboard'")
        
    def stop_advertising(self):
        """Stop advertising."""
        if not self.advertising:
            return
            
        print("BLE: Stopping advertising...")
        self.ble.gap_advertise(None)
        self.advertising = False
        
    def send_key(self, key, shift=False, ctrl=False, alt=False):
        """Send a key press via HID."""
        if not self.connected or not self.conn_handle:
            return False
            
        # Build modifier byte
        modifiers = 0
        if shift:
            modifiers |= MOD_LSHIFT
        if ctrl:
            modifiers |= MOD_LCTRL
        if alt:
            modifiers |= MOD_LALT
            
        # Get key code
        key_code = KEY_CODES.get(key.lower(), 0)
        if key_code == 0 and key.upper() in KEY_CODES:
            key_code = KEY_CODES[key.upper()]
            modifiers |= MOD_LSHIFT
            
        # Create HID report: [Report ID, modifiers, reserved, key1, key2, key3, key4, key5, key6]
        report = bytes([0x01, modifiers, 0x00, key_code, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        try:
            # Send key press
            self.ble.gatts_notify(self.conn_handle, self.report_handle, report)
            print(f"BLE: Sent key '{key}' (code: 0x{key_code:02x})")
            
            # Small delay then send key release
            import time
            time.sleep_ms(50)
            
            # Send key release (all zeros except report ID)
            release_report = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.ble.gatts_notify(self.conn_handle, self.report_handle, release_report)
            
            return True
        except Exception as e:
            print(f"BLE: Error sending key: {e}")
            return False


class App(BaseApp):
    """Bluetooth HID Keyboard app."""

    def __init__(self, name: str, badge):
        super().__init__(name, badge)
        self.foreground_sleep_ms = 100
        self.background_sleep_ms = 1000
        
        # UI elements
        self.p = None
        self.status_label = None
        self.key_label = None
        self.info_label = None
        
        # State
        self.status_text = "Ready"
        self.info_text = "Press F1 to start"
        self.debug_text = "Debug: Starting..."
        self.debug_lines = ["Debug: Starting..."]  # Multiple debug lines
        self.last_key = None
        self.last_key_time = 0

        # BLE
        self.ble_keyboard = None
        self.advertising = False
        self.connected = False
        self.conn_handle = None
        self.bonded = False  # Track if properly bonded
        self.notifications_enabled = False  # Track if Mac subscribed to notifications
        self.bonded_time = 0  # Track when bonding completed
        self.prepared_writes = {}  # Store prepared write data manually
        
    def start(self):
        """Start the app."""
        super().start()
        print("BT Keyboard: App started")

        # Auto-start BLE advertising immediately, even in background
        if BLUETOOTH_AVAILABLE and not self.ble_keyboard:
            try:
                print("BT Keyboard: Auto-starting BLE in background...")
                self._init_bluetooth()
            except Exception as e:
                print(f"BT Keyboard: Auto-start failed: {e}")
        
    def run_foreground(self):
        """Run foreground tasks."""
        # Handle F1 - toggle advertising
        if self.badge.keyboard.f1():
            self.debug_text = "F1 PRESSED!"
            self._toggle_bluetooth()

        # Handle F5 - exit
        elif self.badge.keyboard.f5():
            self.debug_text = "F5 PRESSED!"
            self._cleanup()
            self.badge.display.clear()
            self.switch_to_background()
            return
            
        # Handle regular keys
        key = self.badge.keyboard.read_key()
        if key:
            self.debug_text = f"Key: {key}"
            self.last_key = key
            self.last_key_time = time.ticks_ms()
            
            # Send via BLE if connected
            if self.ble_keyboard and self.connected:
                self._send_key(key)
                self._add_debug(f"Sent key: {key}")
            
        # Check if we've been bonded for a while but Mac still hasn't subscribed
        if (self.bonded and not self.notifications_enabled and self.bonded_time > 0 and 
            time.ticks_diff(time.ticks_ms(), self.bonded_time) > 5000):  # 5 seconds after bonding
            self._add_debug("Mac bonded but no subscription yet - trying nudge...")
            try:
                # Try changing battery level again to trigger Mac to re-examine services
                import urandom
                battery_level = bytes([urandom.randint(80, 100)])
                self.ble_keyboard.gatts_write(self.battery_level_handle, battery_level)
                self._add_debug(f"Sent battery nudge: {battery_level[0]}%")
                self.bonded_time = time.ticks_ms()  # Reset timer to avoid spam
            except Exception as e:
                self._add_debug(f"Battery nudge failed: {e}")
        
        # Update status
        self._update_status()
        
        # Update display
        self._update_display()
        
    def switch_to_foreground(self):
        """Switch to foreground."""
        super().switch_to_foreground()
        print("BT Keyboard: Switching to foreground")

        try:
            # Create UI without title bar
            self.p = Page()
            self.p.create_content()
            self.p.create_menubar(["Toggle", "", "", "", "Exit"])

            # Create multiple debug labels from top to bottom
            self.debug_labels = []
            for i in range(7):  # Create 7 debug lines (8th would overlap menu bar)
                label = lvgl.label(self.p.content)
                label.set_style_text_font(lvgl.font_montserrat_12, 0)
                label.align(lvgl.ALIGN.TOP_LEFT, 5, 5 + i * 15)  # Stack them vertically
                label.set_text("")
                self.debug_labels.append(label)

            self.p.replace_screen()
            self._add_debug("UI created successfully")

            # Auto-start BLE advertising
            if not self.ble_keyboard:
                self._add_debug("Auto-starting BLE...")
                self._toggle_bluetooth()
            else:
                self._add_debug("BLE already running")

            self._update_status()
            print("BT Keyboard: UI created & auto-started")

        except Exception as e:
            print(f"BT Keyboard: UI error: {e}")
        
    def switch_to_background(self):
        """Switch to background."""
        print("BT Keyboard: Switching to background")
        self._cleanup()
        self.p = None
        self.debug_labels = None
        super().switch_to_background()
        
    def _init_bluetooth(self):
        """Initialize BLE keyboard and start advertising."""
        if not BLUETOOTH_AVAILABLE:
            print("BT Keyboard: Bluetooth not available")
            return

        if self.ble_keyboard:
            print("BT Keyboard: Already initialized")
            return

        # Create working BLE keyboard
        if not self.ble_keyboard:
            try:
                self._add_debug("Creating keyboard...")
                
                # Create BLE object
                ble = bluetooth.BLE()
                ble.active(True)
                
                # Set the device name first
                ble.config(gap_name="Badge Keyboard")
                
                # Proper security configuration for macOS compatibility
                try:
                    # Configure security settings that macOS requires for HID devices
                    ble.config(bond=True)           # Enable bonding (required for HID)
                    ble.config(mitm=True)           # MITM protection (required by macOS for keyboards)
                    ble.config(le_secure=True)      # Enable LE Secure Connections
                    ble.config(io=3)                # DisplayYesNo capability (easier pairing)
                    self._add_debug("Security configured for macOS")
                except Exception as e:
                    self._add_debug(f"Security config failed: {e}")
                
                # Set up IRQ handler for connections
                ble.irq(self._ble_irq)
                
                # HID keyboard service with all required characteristics
                HIDS_UUID = bluetooth.UUID(0x1812)        # HID Service
                HID_INFO_UUID = bluetooth.UUID(0x2A4A)    # HID Information
                HID_REPORT_MAP_UUID = bluetooth.UUID(0x2A4B)  # Report Map
                HID_REPORT_UUID = bluetooth.UUID(0x2A4D)  # HID Report
                HID_CONTROL_UUID = bluetooth.UUID(0x2A4C) # HID Control Point
                HID_PROTOCOL_UUID = bluetooth.UUID(0x2A4E) # Protocol Mode
                HID_BOOT_KBD_INPUT_UUID = bluetooth.UUID(0x2A22) # Boot Keyboard Input
                HID_BOOT_KBD_OUTPUT_UUID = bluetooth.UUID(0x2A32) # Boot Keyboard Output
                
                # Descriptors
                CCCD_UUID = bluetooth.UUID(0x2902)
                REPORT_REF_UUID = bluetooth.UUID(0x2908)  # Report Reference
                
                # Define characteristics
                hid_info_char = (HID_INFO_UUID, bluetooth.FLAG_READ)
                report_map_char = (HID_REPORT_MAP_UUID, bluetooth.FLAG_READ)
                control_char = (HID_CONTROL_UUID, bluetooth.FLAG_WRITE_NO_RESPONSE)
                protocol_char = (HID_PROTOCOL_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE_NO_RESPONSE)
                
                # Input report with descriptors - add INDICATE flag for macOS compatibility
                report_char = (HID_REPORT_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY | bluetooth.FLAG_INDICATE, (
                    (CCCD_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE),
                    (REPORT_REF_UUID, bluetooth.FLAG_READ),
                ))
                
                # Skip boot keyboard characteristics for now to simplify
                # boot_kbd_input_char = (HID_BOOT_KBD_INPUT_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY, (
                #     (CCCD_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE),
                # ))
                # boot_kbd_output_char = (HID_BOOT_KBD_OUTPUT_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE)
                
                # Battery Service (MANDATORY for HID devices per spec)
                BATTERY_SERVICE_UUID = bluetooth.UUID(0x180F)  # Battery Service
                BATTERY_LEVEL_UUID = bluetooth.UUID(0x2A19)    # Battery Level
                
                # Device Information Service (required for proper HID recognition)
                DIS_UUID = bluetooth.UUID(0x180A)          # Device Information Service
                PNP_ID_UUID = bluetooth.UUID(0x2A50)       # PnP ID
                MANUFACTURER_UUID = bluetooth.UUID(0x2A29) # Manufacturer Name
                
                # Battery Service (mandatory for HID devices on macOS)
                BATTERY_SERVICE_UUID = bluetooth.UUID(0x180F)    # Battery Service
                BATTERY_LEVEL_UUID = bluetooth.UUID(0x2A19)      # Battery Level
                
                # Device Information characteristics
                manufacturer_char = (MANUFACTURER_UUID, bluetooth.FLAG_READ)
                pnp_id_char = (PNP_ID_UUID, bluetooth.FLAG_READ)
                
                # Battery Service characteristics
                battery_level_char = (BATTERY_LEVEL_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY, (
                    (CCCD_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE),
                ))
                
                # Device Information Service
                dis_service = (DIS_UUID, (manufacturer_char, pnp_id_char))
                
                # Battery Service
                battery_service = (BATTERY_SERVICE_UUID, (battery_level_char,))
                
                # Define simplified HID service without boot protocol
                hid_service = (HIDS_UUID, (hid_info_char, report_map_char, control_char, protocol_char, report_char))
                
                # Register all three mandatory services (DIS, Battery, HID)
                handles = ble.gatts_register_services((dis_service, battery_service, hid_service))
                
                # Store handles for all characteristics
                # Service 0: Device Information Service
                self.manufacturer_handle = handles[0][0]
                self.pnp_id_handle = handles[0][1]
                
                # Service 1: Battery Service
                self.battery_level_handle = handles[1][0]
                self.battery_cccd_handle = handles[1][1]  # CCCD descriptor for battery notifications
                
                # Service 2: HID Service (simplified)
                self.ble_keyboard = ble
                self.hid_info_handle = handles[2][0]
                self.report_map_handle = handles[2][1] 
                self.control_handle = handles[2][2]
                self.protocol_handle = handles[2][3]
                self.report_handle = handles[2][4]
                self.cccd_handle = handles[2][5]  # CCCD descriptor for HID reports
                self.report_ref_handle = handles[2][6]  # Report Reference descriptor
                # Boot keyboard handles removed for simplification
                self.advertising = False
                self.connected = False
                
                # Set up Device Information Service
                manufacturer_name = b"Hackaday"
                ble.gatts_write(self.manufacturer_handle, manufacturer_name)
                
                # PnP ID: Vendor ID Source=1 (Bluetooth), Vendor ID=0x1234, Product ID=0x5678, Version=0x0100
                pnp_id = bytes([0x01, 0x34, 0x12, 0x78, 0x56, 0x00, 0x01])
                ble.gatts_write(self.pnp_id_handle, pnp_id)
                
                # Set up Battery Service (set to 100% battery level)
                battery_level = bytes([100])  # 100% battery level
                ble.gatts_write(self.battery_level_handle, battery_level)
                
                # Set up HID information (version, country, flags)
                hid_info = bytes([0x11, 0x01, 0x00, 0x02])  # Version 1.11, country 0, flags 2
                ble.gatts_write(self.hid_info_handle, hid_info)
                
                # Set protocol mode (Report Protocol = 1, standard mode)
                # Some devices start in Boot (0) but macOS might prefer Report (1)
                ble.gatts_write(self.protocol_handle, bytes([0x01]))
                
                # Set report reference (Report ID=0, Report Type=Input=1)
                ble.gatts_write(self.report_ref_handle, bytes([0x00, 0x01]))
                
                # Try to pre-enable notifications by writing to CCCD
                # This might help macOS recognize that notifications are available
                try:
                    ble.gatts_write(self.cccd_handle, b'\x00\x00')  # Initialize CCCD to disabled
                    self._add_debug("Initialized HID CCCD")
                except Exception as e:
                    self._add_debug(f"CCCD init failed: {e}")
                
                # Simplified HID report map that macOS definitely likes
                # This is a standard USB HID keyboard descriptor without Report ID
                report_map = bytes([
                    0x05, 0x01,  # Usage Page (Generic Desktop)
                    0x09, 0x06,  # Usage (Keyboard)
                    0xA1, 0x01,  # Collection (Application)
                    0x05, 0x07,  # Usage Page (Keyboard/Keypad)
                    0x19, 0xE0,  # Usage Minimum (Left Control)
                    0x29, 0xE7,  # Usage Maximum (Right GUI)
                    0x15, 0x00,  # Logical Minimum (0)
                    0x25, 0x01,  # Logical Maximum (1)
                    0x75, 0x01,  # Report Size (1)
                    0x95, 0x08,  # Report Count (8)
                    0x81, 0x02,  # Input (Data,Var,Abs) - Modifier keys
                    0x95, 0x01,  # Report Count (1)
                    0x75, 0x08,  # Report Size (8)
                    0x81, 0x01,  # Input (Const,Array,Abs) - Reserved byte
                    0x95, 0x06,  # Report Count (6)
                    0x75, 0x08,  # Report Size (8)
                    0x15, 0x00,  # Logical Minimum (0)
                    0x25, 0x65,  # Logical Maximum (101)
                    0x05, 0x07,  # Usage Page (Keyboard/Keypad)
                    0x19, 0x00,  # Usage Minimum (0)
                    0x29, 0x65,  # Usage Maximum (101)
                    0x81, 0x00,  # Input (Data,Array,Abs) - Key codes
                    0xC0         # End Collection
                ])
                ble.gatts_write(self.report_map_handle, report_map)
                
                # Show all handle values for debugging
                self._add_debug(f"CCCD handle: {self.cccd_handle}")
                self._add_debug(f"Report handle: {self.report_handle}")
                self._add_debug(f"Battery CCCD: {self.battery_cccd_handle}")
                
                self._add_debug("Keyboard ready! v15 (CCCD-only prepared writes)")

            except Exception as e:
                self._add_debug(f"Create failed: {e}")
                print(f"BT Keyboard: Init failed: {e}")
                return

        # Auto-start advertising
        try:
            self._add_debug("Starting ads...")
            # Proper advertising with device name and HID service
            name = "Badge Keyboard"
            adv_data = bytearray()

            # Flags: LE General Discoverable, BR/EDR not supported
            adv_data.extend(b'\x02\x01\x06')

            # Appearance: Keyboard (0x03C1) - this is critical for macOS recognition
            adv_data.extend(b'\x03\x19\xC1\x03')

            # Complete local name
            name_bytes = name.encode('utf-8')
            adv_data.extend(bytes([len(name_bytes) + 1, 0x09]) + name_bytes)

            # Scan response with multiple service UUIDs
            scan_resp = bytearray()
            # Complete list of 16-bit service UUIDs: HID (0x1812), Battery (0x180F), DIS (0x180A)
            scan_resp.extend(b'\x07\x03\x12\x18\x0F\x18\x0A\x18')
            # TX Power Level (0dBm) - sometimes helps with macOS
            scan_resp.extend(b'\x02\x0A\x00')

            self.ble_keyboard.gap_advertise(100000, adv_data=adv_data, resp_data=scan_resp)
            self.advertising = True
            self._add_debug("Badge Keyboard advertised!")
            print("BT Keyboard: Now advertising!")

        except Exception as e:
            self._add_debug(f"Advertising failed: {e}")
            print(f"BT Keyboard: Advertising failed: {e}")

        self._update_status()

    def _toggle_bluetooth(self):
        """Toggle Bluetooth advertising on/off."""
        if not BLUETOOTH_AVAILABLE:
            print("BT Keyboard: BT Not Available")
            if hasattr(self, 'debug_labels') and self.debug_labels:
                self._add_debug("BT Not Available")
            return

        # Initialize if needed
        if not self.ble_keyboard:
            self._init_bluetooth()
            return

        # Toggle advertising
        try:
            if self.advertising:
                self._add_debug("Stopping ads...")
                self.ble_keyboard.gap_advertise(None)
                self.advertising = False
            else:
                self._add_debug("Starting ads...")
                # Proper advertising with device name and HID service
                name = "Badge Keyboard"
                adv_data = bytearray()

                # Flags: LE General Discoverable, BR/EDR not supported
                adv_data.extend(b'\x02\x01\x06')

                # Appearance: Keyboard (0x03C1) - this is critical for macOS recognition
                adv_data.extend(b'\x03\x19\xC1\x03')

                # Complete local name
                name_bytes = name.encode('utf-8')
                adv_data.extend(bytes([len(name_bytes) + 1, 0x09]) + name_bytes)

                # Scan response with multiple service UUIDs
                scan_resp = bytearray()
                # Complete list of 16-bit service UUIDs: HID (0x1812), Battery (0x180F), DIS (0x180A)
                scan_resp.extend(b'\x07\x03\x12\x18\x0F\x18\x0A\x18')
                # TX Power Level (0dBm) - sometimes helps with macOS
                scan_resp.extend(b'\x02\x0A\x00')

                self.ble_keyboard.gap_advertise(100000, adv_data=adv_data, resp_data=scan_resp)
                self.advertising = True
                self._add_debug("Badge Keyboard advertised!")

        except Exception as e:
            self._add_debug(f"Advertising failed: {e}")

        self._update_status()
        
    def _send_key(self, key):
        """Send a key via HID report."""
        if not self.ble_keyboard or not self.connected:
            return
            
        if not self.notifications_enabled:
            self._add_debug("Mac hasn't subscribed to notifications yet!")
            return
            
        # Get key code from our existing KEY_CODES dictionary
        key_code = KEY_CODES.get(key.lower(), 0)
        if key_code == 0:
            return  # Unknown key
            
        try:
            # Create HID report: [modifiers, reserved, key1, key2, key3, key4, key5, key6]
            # Modifiers: Ctrl=1, Shift=2, Alt=4, GUI=8 (left), Ctrl=16, Shift=32, Alt=64, GUI=128 (right)
            modifiers = 0
            
            # Handle uppercase letters (add shift)
            if key.isupper() and key.isalpha():
                modifiers |= 0x02  # Left Shift
                key_code = KEY_CODES.get(key.lower(), 0)  # Use lowercase key code
            
            # Send key press without Report ID (new simplified format)
            report = bytes([modifiers, 0x00, key_code, 0x00, 0x00, 0x00, 0x00, 0x00])
            self._add_debug(f"Sending: mod={modifiers:02x} key={key_code:02x}")
            # Try notification first, fall back to indication
            try:
                self.ble_keyboard.gatts_notify(self.conn_handle, self.report_handle, report)
            except Exception as notify_e:
                self._add_debug(f"Notify failed, trying indicate: {notify_e}")
                try:
                    self.ble_keyboard.gatts_indicate(self.conn_handle, self.report_handle, report)
                except Exception as indicate_e:
                    self._add_debug(f"Indicate also failed: {indicate_e}")
                    raise
            
            # Small delay then send key release
            import time
            time.sleep_ms(50)
            
            # Send key release (all zeros) without Report ID
            release_report = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.ble_keyboard.gatts_notify(self.conn_handle, self.report_handle, release_report)
            
        except Exception as e:
            self._add_debug(f"Send failed: {e}")
        
    def _ble_irq(self, event, data):
        """Handle BLE events."""
        try:
            # Debug all events
            self._add_debug(f"BLE Event: {event}")
            
            if event == 1:  # _IRQ_CENTRAL_CONNECT
                conn_handle, _, _ = data
                self.conn_handle = conn_handle
                self.connected = True
                self._add_debug("Device connected!")
                # Immediately try to initiate pairing for better macOS compatibility
                try:
                    self.ble_keyboard.gap_pair(conn_handle)
                    self._add_debug("Initiated pairing process")
                except Exception as e:
                    self._add_debug(f"Pairing initiation failed: {e}")
            elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
                self.connected = False
                self.conn_handle = None
                self.bonded = False
                self.notifications_enabled = False
                self.bonded_time = 0
                self.prepared_writes.clear()
                self._add_debug("Device disconnected")
            elif event == 3:  # _IRQ_GATTS_WRITE
                conn_handle, value_handle = data
                self._add_debug(f"Mac wrote to handle {value_handle}")
                if value_handle == self.cccd_handle:
                    # Client subscribed to notifications - this is critical!
                    value = self.ble_keyboard.gatts_read(value_handle)
                    self._add_debug(f"HID CCCD written: {value.hex()}")
                    if value == b'\x01\x00':
                        self._add_debug("Mac SUBSCRIBED to HID notifications!")
                        self.notifications_enabled = True
                    elif value == b'\x02\x00':
                        self._add_debug("Mac SUBSCRIBED to HID indications!")
                        self.notifications_enabled = True
                    elif value == b'\x00\x00':
                        self._add_debug("Mac UNSUBSCRIBED from HID notifications")
                        self.notifications_enabled = False
                    else:
                        self._add_debug(f"Mac wrote unknown CCCD value: {value.hex()}")
                # Boot keyboard handling removed for simplification
                elif value_handle == self.battery_cccd_handle:
                    # Battery notifications
                    value = self.ble_keyboard.gatts_read(value_handle)
                    self._add_debug(f"Battery CCCD: {value.hex()}")
                elif value_handle == self.protocol_handle:
                    # Protocol mode change
                    value = self.ble_keyboard.gatts_read(value_handle)
                    self._add_debug(f"Protocol mode changed to: {value[0]}")
                elif value_handle == self.control_handle:
                    # Control point command
                    value = self.ble_keyboard.gatts_read(value_handle)
                    self._add_debug(f"Control point command: {value.hex()}")
            elif event == 5:  # _IRQ_PASSKEY_ACTION
                # Handle pairing requests - this is critical for macOS
                conn_handle, action, passkey = data
                self._add_debug(f"Pairing action: {action}, passkey: {passkey}")
                
                try:
                    if action == 2:  # _PASSKEY_ACTION_INPUT
                        # Mac wants us to enter a passkey - respond with a fixed value
                        self.ble_keyboard.gap_passkey(conn_handle, action, 123456)
                        self._add_debug("Passkey: Input 123456")
                    elif action == 3:  # _PASSKEY_ACTION_DISPLAY  
                        # We should display a passkey - generate a random one
                        import urandom
                        display_passkey = urandom.randint(100000, 999999)
                        self.ble_keyboard.gap_passkey(conn_handle, action, display_passkey)
                        self._add_debug(f"Passkey: Display {display_passkey}")
                    elif action == 4:  # _PASSKEY_ACTION_NUMERIC_COMPARISON
                        # Numeric comparison - always accept for now
                        self.ble_keyboard.gap_passkey(conn_handle, action, 1)
                        self._add_debug(f"Passkey: Confirmed {passkey}")
                    elif action == 0:  # _PASSKEY_ACTION_NONE
                        # No action required
                        self._add_debug("Passkey: No action required")
                    elif action == 1:  # _PASSKEY_ACTION_PASSKEY
                        # Generic passkey - use fixed value
                        self.ble_keyboard.gap_passkey(conn_handle, action, 123456)
                        self._add_debug("Passkey: Generic 123456")
                except Exception as e:
                    self._add_debug(f"Passkey error: {e}")
                    
            elif event == 6:  # _IRQ_ENCRYPTION_UPDATE
                conn_handle, encrypted, authenticated, bonded, key_size = data
                self._add_debug(f"Encryption: E:{encrypted} A:{authenticated} B:{bonded} K:{key_size}")
                if bonded:
                    self.bonded = True
                    self.bonded_time = time.ticks_ms()
                    self._add_debug("BONDED SUCCESSFULLY! Device should stay in My Devices")
                    # Try to trigger Mac to read characteristics and subscribe
                    try:
                        # Send a dummy battery notification to wake up macOS GATT client
                        battery_level = bytes([95])  # Slight change in battery level
                        self.ble_keyboard.gatts_write(self.battery_level_handle, battery_level)
                        self._add_debug("Sent battery update to wake up Mac GATT")
                        
                        # Also try manually enabling notifications on the HID CCCD
                        # Some devices need this to work properly with macOS
                        try:
                            # Write notification enable value to CCCD 
                            self.ble_keyboard.gatts_write(self.cccd_handle, b'\x01\x00')
                            self._add_debug("Manually enabled HID notifications")
                            self.notifications_enabled = True
                        except Exception as cccd_e:
                            self._add_debug(f"Manual CCCD enable failed: {cccd_e}")
                            
                    except Exception as e:
                        self._add_debug(f"Battery update failed: {e}")
                elif encrypted:
                    self._add_debug("Connection encrypted but not bonded")
                else:
                    self._add_debug("Connection not encrypted")
                
            elif event == 7:  # _IRQ_GET_SECRET
                # Return None to indicate no stored secret
                self._add_debug("Secret requested - returning None")
                return None

            elif event == 8:  # _IRQ_SET_SECRET
                # Store the secret (but we don't actually store it)
                self._add_debug("Secret provided for storage")
            elif event == 21:  # _IRQ_MTU_EXCHANGED
                # MTU exchange completed
                conn_handle, mtu = data
                self._add_debug(f"MTU exchanged: {mtu} bytes")
            elif event == 28:  # _IRQ_GATTC_READ_DONE (might be GATTS_READ_DONE)
                # Read multiple completed
                self._add_debug("GATT Read Multiple completed")
            elif event == 29:  # _IRQ_GATTS_WRITE (prepared)
                # Capture prepared write data manually (don't return values - causes crash)
                try:
                    # Debug: print entire data tuple to understand format
                    self._add_debug(f"Event 29 data: {data}, len={len(data)}")
                    if len(data) >= 2:
                        # Try different interpretations of the data
                        self._add_debug(f"  data[0]={data[0]}, data[1]={data[1]}")
                        if len(data) >= 3:
                            self._add_debug(f"  data[2]={data[2]}")
                        if len(data) >= 4:
                            self._add_debug(f"  data[3]={data[3]}")

                        # Assume format is (conn_handle, value_handle, ...)
                        conn_handle, value_handle = data[0], data[1]
                        self._add_debug(f"Event 29: Prepared write to handle {value_handle}")
                        # Store which handle is being written to
                        self.prepared_writes[value_handle] = True
                    else:
                        self._add_debug(f"Event 29: Too few data elements")
                except Exception as e:
                    self._add_debug(f"Event 29 error: {e}")
                # Don't return anything - causes crashes
            elif event == 30:  # _IRQ_GATTS_WRITE_DONE (execute)
                # Execute handler - apply prepared writes
                # MicroPython BLE limitation: handle info not available in events 29/30
                # Workaround: Assume CCCD notifications are being enabled when status=1
                try:
                    status = data[0]
                    self._add_debug(f"Event 30: status={status}")

                    if status == 1:
                        # Status 1 = execute prepared writes
                        # Check if CCCD was actually updated
                        cccd_value = self.ble_keyboard.gatts_read(self.cccd_handle)
                        self._add_debug(f"HID CCCD after execute: {cccd_value.hex() if cccd_value else 'None'}")

                        if cccd_value == b'\x01\x00' or cccd_value == b'\x02\x00':
                            # CCCD was properly updated!
                            self._add_debug("NOTIFICATIONS ENABLED via CCCD!")
                            self.notifications_enabled = True
                        elif cccd_value == b'\x00\x00':
                            # CCCD still disabled - prepared write failed due to MicroPython bug
                            # Manually write to CCCD to enable notifications
                            self._add_debug("WORKAROUND: Manually writing CCCD to enable notifications")
                            try:
                                # Write notification enable value (0x0001 in little-endian)
                                self.ble_keyboard.gatts_write(self.cccd_handle, b'\x01\x00')
                                # Verify it was written
                                new_value = self.ble_keyboard.gatts_read(self.cccd_handle)
                                self._add_debug(f"CCCD after manual write: {new_value.hex()}")
                                self.notifications_enabled = True
                                self._add_debug("NOTIFICATIONS ENABLED via manual CCCD write!")
                            except Exception as e:
                                self._add_debug(f"Manual CCCD write failed: {e}")
                        else:
                            self._add_debug(f"Unexpected CCCD value: {cccd_value.hex()}")
                    elif status == 2:
                        # Status 2 = cancel prepared writes
                        self._add_debug("Event 30: Prepared writes cancelled")

                except Exception as e:
                    self._add_debug(f"Event 30 error: {e}")
            elif event == 4:  # _IRQ_GATTS_READ_REQUEST
                # Mac is reading a characteristic - this is good!
                conn_handle, value_handle = data
                if value_handle == self.report_map_handle:
                    self._add_debug("Mac reading HID Report Map!")
                elif value_handle == self.hid_info_handle:
                    self._add_debug("Mac reading HID Info!")
                elif value_handle == self.battery_level_handle:
                    self._add_debug("Mac reading Battery Level!")
                elif value_handle == self.report_handle:
                    self._add_debug("Mac reading HID Report characteristic!")
                elif value_handle == self.cccd_handle:
                    self._add_debug("Mac reading HID CCCD descriptor!")
                elif value_handle == self.report_ref_handle:
                    self._add_debug("Mac reading Report Reference!")
                elif value_handle == self.protocol_handle:
                    self._add_debug("Mac reading Protocol Mode!")
                    # When Mac reads protocol mode, it's often getting ready to subscribe
                    # Try sending another battery update to encourage subscription
                    try:
                        import urandom
                        battery_level = bytes([urandom.randint(85, 95)])
                        self.ble_keyboard.gatts_write(self.battery_level_handle, battery_level)
                        self._add_debug(f"Protocol read -> battery nudge: {battery_level[0]}%")
                    except Exception as e:
                        self._add_debug(f"Protocol nudge failed: {e}")
                elif value_handle == self.control_handle:
                    self._add_debug("Mac reading Control Point!")
                elif value_handle == self.manufacturer_handle:
                    self._add_debug("Mac reading Manufacturer Name!")
                elif value_handle == self.pnp_id_handle:
                    self._add_debug("Mac reading PnP ID!")
                else:
                    self._add_debug(f"Mac reading unknown handle {value_handle}")
        except Exception as e:
            self._add_debug(f"BLE IRQ exception: {e}")
            # Don't return anything - returning values for event 29 causes crashes

    def _add_debug(self, message):
        """Add a debug message to the display."""
        print(f"DEBUG: {message}")  # Also print to console
        self.debug_lines.append(message)
        # Keep only last 7 lines (to avoid overlapping menu bar)
        if len(self.debug_lines) > 7:
            self.debug_lines = self.debug_lines[-7:]
        # Update display immediately
        try:
            if hasattr(self, 'debug_labels') and self.debug_labels:
                for i, label in enumerate(self.debug_labels):
                    if i < len(self.debug_lines):
                        label.set_text(self.debug_lines[i])
                    else:
                        label.set_text("")
        except Exception as e:
            print(f"DEBUG DISPLAY ERROR: {e}")
        
    def _update_status(self):
        """Update status text."""
        if not BLUETOOTH_AVAILABLE:
            self.status_text = "BT Not Available"
            self.info_text = "Module missing"
        elif not self.ble_keyboard:
            self.status_text = "BT Ready"
            self.info_text = "Press F1 to start"
        elif self.connected and self.bonded and self.notifications_enabled:
            self.status_text = "Ready to Type!"
            self.info_text = "Mac subscribed, ready!"
        elif self.connected and self.bonded:
            self.status_text = "Bonded (waiting...)"
            self.info_text = "Mac needs to subscribe"
        elif self.connected:
            self.status_text = "Connected (pairing...)"
            self.info_text = "Waiting for bond"
        elif self.advertising:
            self.status_text = "Advertising..."
            self.info_text = "Pair on your device"
        else:
            self.status_text = "BT Ready"
            self.info_text = "Press F1 to advertise"
            
    def _update_display(self):
        """Update display elements."""
        try:
            # Update debug lines on screen
            if hasattr(self, 'debug_labels') and self.debug_labels:
                for i, label in enumerate(self.debug_labels):
                    if i < len(self.debug_lines):
                        label.set_text(self.debug_lines[i])
                    else:
                        label.set_text("")
                    
        except Exception as e:
            self._add_debug(f"Display error: {e}")
            
    def _cleanup(self):
        """Clean up resources."""
        if self.ble_keyboard:
            try:
                self.ble_keyboard.stop_advertising()
            except:
                pass