"""
USB Barcode scanner reader using evdev.
Reads barcodes from USB HID devices on Linux (Raspberry Pi).
"""
import time
from typing import Optional, Callable
from pathlib import Path

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

from raspberry_app.barcode.validator import BarcodeValidator
from raspberry_app.utils.logger import LoggerMixin


class BarcodeReader(LoggerMixin):
    """
    USB barcode scanner reader using evdev.

    Reads scancodes from USB HID device and converts to barcode strings.
    Includes debouncing to prevent duplicate reads.

    Example:
        >>> reader = BarcodeReader()
        >>> reader.start()
        >>> # Barcode scanned -> callback invoked
        >>> reader.stop()
    """

    # Scancode to character mapping for barcode scanners
    SCANCODES = {
        # Numbers
        2: '1', 3: '2', 4: '3', 5: '4', 6: '5',
        7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
        # Letters (if needed for some barcodes)
        16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't',
        21: 'y', 22: 'u', 23: 'i', 24: 'o', 25: 'p',
        30: 'a', 31: 's', 32: 'd', 33: 'f', 34: 'g',
        35: 'h', 36: 'j', 37: 'k', 38: 'l',
        44: 'z', 45: 'x', 46: 'c', 47: 'v', 48: 'b',
        49: 'n', 50: 'm',
        # Special
        12: '-', 13: '=', 26: '[', 27: ']',
        39: ';', 40: "'", 41: '`', 43: '\\',
        51: ',', 52: '.', 53: '/',
    }

    def __init__(self, device_path: Optional[str] = None,
                 validator: Optional[BarcodeValidator] = None,
                 debounce_ms: int = 100):
        """
        Initialize barcode reader.

        Args:
            device_path: Path to evdev device (e.g., /dev/input/event0).
                        If None, auto-detects barcode scanner.
            validator: BarcodeValidator instance. If None, creates default.
            debounce_ms: Debounce time in milliseconds to prevent duplicate reads
        """
        if not EVDEV_AVAILABLE:
            raise ImportError("evdev library not available. Install with: pip install evdev")

        self.device_path = device_path
        self.device: Optional[InputDevice] = None
        self.validator = validator or BarcodeValidator()
        self.debounce_ms = debounce_ms

        self.callback: Optional[Callable[[str], None]] = None
        self.running = False

        self.last_barcode = ""
        self.last_barcode_time = 0.0
        self.buffer = []

    def find_barcode_scanner(self) -> Optional[str]:
        """
        Auto-detect barcode scanner device.

        Returns:
            str: Device path if found, None otherwise
        """
        self.logger.info("Searching for barcode scanner...")

        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

        for device in devices:
            # Look for devices that look like barcode scanners
            # Usually have "barcode", "scanner", or "HID" in the name
            name_lower = device.name.lower()

            if any(keyword in name_lower for keyword in ['barcode', 'scanner', 'hid']):
                self.logger.info(f"Found potential barcode scanner: {device.name} at {device.path}")
                return device.path

        # If no obvious scanner, look for generic USB HID devices
        for device in devices:
            if 'usb' in device.phys.lower():
                self.logger.info(f"Found USB device: {device.name} at {device.path}")
                return device.path

        self.logger.warning("No barcode scanner found")
        return None

    def connect(self) -> bool:
        """
        Connect to barcode scanner device.

        Returns:
            bool: True if connected successfully
        """
        try:
            # Auto-detect if no path provided
            if not self.device_path:
                self.device_path = self.find_barcode_scanner()

            if not self.device_path:
                self.logger.error("No barcode scanner device found")
                return False

            # Open device
            self.device = InputDevice(self.device_path)

            # Try to grab exclusive access
            try:
                self.device.grab()
                self.logger.info(f"Connected to barcode scanner: {self.device.name}")
            except:
                self.logger.warning(f"Could not grab exclusive access to {self.device.name}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to barcode scanner: {e}")
            return False

    def disconnect(self):
        """Disconnect from barcode scanner."""
        if self.device:
            try:
                self.device.ungrab()
            except:
                pass
            self.device.close()
            self.device = None
            self.logger.info("Disconnected from barcode scanner")

    def set_callback(self, callback: Callable[[str], None]):
        """
        Set callback function to be called when barcode is scanned.

        Args:
            callback: Function that receives barcode string
        """
        self.callback = callback

    def _process_barcode(self, barcode: str):
        """
        Process scanned barcode.

        Args:
            barcode: Raw barcode string
        """
        # Check debounce
        current_time = time.time()
        if (barcode == self.last_barcode and
            (current_time - self.last_barcode_time) * 1000 < self.debounce_ms):
            self.logger.debug(f"Debounced duplicate barcode: {barcode}")
            return

        # Update debounce tracking
        self.last_barcode = barcode
        self.last_barcode_time = current_time

        # Validate barcode
        if not self.validator.validate(barcode):
            self.logger.warning(f"Invalid barcode: {barcode}")
            return

        # Format barcode
        formatted = self.validator.format(barcode)
        if not formatted:
            self.logger.warning(f"Could not format barcode: {barcode}")
            return

        self.logger.info(f"Barcode scanned: {formatted}")

        # Call callback
        if self.callback:
            try:
                self.callback(formatted)
            except Exception as e:
                self.logger.error(f"Error in barcode callback: {e}")

    def read_loop(self):
        """
        Main read loop. Reads events from device and builds barcode string.

        This is a blocking call. Run in a separate thread.
        """
        if not self.device:
            self.logger.error("Not connected to device")
            return

        self.running = True
        self.logger.info("Starting barcode read loop")

        try:
            for event in self.device.read_loop():
                if not self.running:
                    break

                # Only process key press events
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)

                    # Key down event
                    if key_event.keystate == key_event.key_down:
                        scancode = key_event.scancode

                        # Enter key = end of barcode
                        if scancode == ecodes.KEY_ENTER:
                            if self.buffer:
                                barcode = ''.join(self.buffer)
                                self.buffer = []
                                self._process_barcode(barcode)
                        # Add character to buffer
                        elif scancode in self.SCANCODES:
                            char = self.SCANCODES[scancode]
                            self.buffer.append(char)

        except Exception as e:
            self.logger.error(f"Error in read loop: {e}")
        finally:
            self.running = False
            self.logger.info("Barcode read loop stopped")

    def start(self, callback: Optional[Callable[[str], None]] = None):
        """
        Start reading barcodes.

        Args:
            callback: Optional callback function for scanned barcodes
        """
        if callback:
            self.set_callback(callback)

        if not self.device:
            if not self.connect():
                raise RuntimeError("Failed to connect to barcode scanner")

        # Start read loop (blocking - should be run in thread)
        self.read_loop()

    def stop(self):
        """Stop reading barcodes."""
        self.running = False
        self.disconnect()


# Example usage
if __name__ == "__main__":
    import sys

    def on_barcode(barcode: str):
        """Callback for scanned barcodes."""
        print(f"\n🔍 Barcode scanned: {barcode}")

    try:
        print("=" * 60)
        print("BARCODE READER TEST")
        print("=" * 60)
        print("\nInitializing barcode reader...")

        reader = BarcodeReader()
        reader.set_callback(on_barcode)

        print("Connecting to scanner...")
        if reader.connect():
            print(f"✅ Connected to: {reader.device.name}")
            print(f"   Path: {reader.device.path}")
            print("\n📱 Scan a barcode (Ctrl+C to exit)...\n")

            reader.read_loop()
        else:
            print("❌ Could not connect to barcode scanner")
            print("   Make sure:")
            print("   - Scanner is plugged in")
            print("   - You have permission to access /dev/input/*")
            print("   - Try: sudo usermod -a -G input $USER")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping...")
        reader.stop()
        print("✅ Stopped")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
