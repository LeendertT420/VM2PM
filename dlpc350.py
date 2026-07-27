import hid
import time
import struct

class DLPC350Controller:
    VENDOR_ID = 0x0451
    PRODUCT_ID = 0x6401

    def __init__(self):
        self.device = None
        self.sequence_num = 0x00

    def connect(self):
        try:
            self.device = hid.device()
            self.device.open(self.VENDOR_ID, self.PRODUCT_ID)
            self.device.set_nonblocking(1)
            print("[DLPC350] Connected successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to DLPC350 USB Device: {e}")

    def disconnect(self):
        if self.device:
            self.device.close()
            print("[DLPC350] Disconnected.")

    def _send_packet(self, mode: str, cmd2: int, cmd3: int, data: list = None):
        if data is None:
            data = []
        payload_len = len(data) + 2
        
        # 0xC0 for Read (Bit 7=1, Bit 6=1), 0x40 for Write (Bit 6=1 for reply/ack)
        rw_flag = 0xC0 if mode == 'r' else 0x40
        
        header = [
            0x00, # Report ID
            rw_flag,
            self.sequence_num,
            payload_len & 0xFF,
            (payload_len >> 8) & 0xFF,
            cmd2,
            cmd3
        ]
        packet = header + data
        packet += [0x00] * (65 - len(packet))

        self.device.write(packet)
        self.sequence_num = (self.sequence_num + 1) % 256
        time.sleep(0.01)

        # If it's a read command, read the response back from the USB endpoint
        if mode == 'r':
            response = self.device.read(64)
            return response


    def set_display_mode(self, pattern_mode: bool = True):
        """0x01 = Pattern Display Mode, 0x00 = Video Mode"""
        mode = 0x01 if pattern_mode else 0x00
        self._send_packet('w', 0x1A, 0x1B, [mode])

    def stop_pattern_sequence(self):
        """Stop pattern display sequence (0x00 = Stop)"""
        self._send_packet('w', 0x1A, 0x24, [0x00])

    def start_pattern_sequence(self):
        """Start pattern display sequence (0x02 = Start)"""
        self._send_packet('w', 0x1A, 0x24, [0x02])

    def set_pattern_input_source(self, source: int = 0):
        """0 = Internal Flash, 1 = Video Port"""
        self._send_packet('w', 0x1A, 0x22, [source])

    def set_pattern_trigger_mode(self, mode: int = 1):
        """
        0 = VSYNC (Requires active video cable)
        1 = Internal Timer / External Trig
        """
        self._send_packet('w', 0x1A, 0x23, [mode])

    def configure_pattern_timing(self, exposure_us: int, period_us: int):
        """Exposure & Period in microseconds."""
        data = list(struct.pack('<II', exposure_us, period_us))
        self._send_packet('w', 0x1A, 0x29, data)

    def validate_pattern_sequence(self):
        """
        MANDATORY STEP: Requests DLPC350 controller to validate LUT configuration.
        """
        self._send_packet('w', 0x1A, 0x1A, [0x00])
        time.sleep(0.05)

    def program_sequence(self, num_patterns: int, bit_depth: int = 1, enable_leds: bool = True):
        """
        Full sequence setup: Stops current pattern, programs LUT mailboxes,
        validates the payload, and readies execution.
        """
        # 1. Halt active execution & set mode
        self.stop_pattern_sequence()
        self.set_display_mode(pattern_mode=True)
        self.set_pattern_input_source(source=0)  # Internal Flash
        self.set_pattern_trigger_mode(mode=1)     # Mode 1: Internal Trigger

        # 2. Open LUT Mailbox for Pattern Definition (CMD3: 0x33, Value: 0x02)
        self._send_packet('w', 0x1A, 0x33, [0x02])
        
        # 3. Reset LUT Pointer (CMD3: 0x32)
        self._send_packet('w', 0x1A, 0x32, [0x00])

        # 4. Fill LUT Mailbox (CMD3: 0x34)
        # LED Select: 0b111 (RGB ON for visual testing) or 0b000 (Laser Pass-through)
        led_flags = 0b111 if enable_leds else 0b000
        
        for pat_idx in range(num_patterns):
            b0 = pat_idx & 0xFF
            b1 = (bit_depth & 0x07) | (led_flags << 3)
            
            # Buffer swap on first pattern
            b2 = 0x01 if pat_idx == 0 else 0x00
            
            self._send_packet('w', 0x1A, 0x34, [b0, b1, b2])

        # 5. Close LUT Mailbox (CMD3: 0x33, Value: 0x00)
        self._send_packet('w', 0x1A, 0x33, [0x00])

        # 6. Configure Pattern LUT Execution Parameters (CMD3: 0x31)
        # [num_lut_entries_lsb, msb, do_repeat (0=repeat, 1=once), num_pats, num_flash_images]
        lut_config = [
            num_patterns & 0xFF, (num_patterns >> 8) & 0xFF,
            0x00,  # 0x00 = Continuous Repeat
            num_patterns & 0xFF, (num_patterns >> 8) & 0xFF,
            0x01, 0x00  # Number of flash images used
        ]
        self._send_packet('w', 0x1A, 0x31, lut_config)

        # 7. Validate sequence setup
        self.validate_pattern_sequence()


    def get_hardware_status(self):
        """CMD2: 0x1A, CMD3: 0x0A"""
        response = self._send_packet('r', 0x1A, 0x0A)
        if response:
            # The data payload starts after the header (usually at index 6 or 7 depending on your HID library's return format)
            print(f"[DLPC350] Hardware Status Response: {response}")
            return response
        else:
            print("[DLPC350] No response received.")
            return None


    def set_input_source_test_pattern(self):
        """
        Input Source Selection (CMD2: 0x1A, CMD3: 0x00)
        Data: 0x01 = Internal test pattern
        """
        # Ensure we are in Video Mode first
        self.set_display_mode(pattern_mode=False) 
        
        # Set source to Internal test pattern (0x01)
        # We also need to send the parallel interface bit depth for the second byte. 
        # Using 0x01 (Internal Pattern) and 0x00 (30-bits) as safe defaults.
        self._send_packet('w', 0x1A, 0x00, [0x01, 0x00])

    def set_test_pattern_checkerboard(self):
        """
        Internal Test Patterns Select (CMD2: 0x12, CMD3: 0x03)
        Data: 0x07 = Checkerboard
        """
        self._send_packet('w', 0x12, 0x03, [0x07])


# Execution Example
if __name__ == "__main__":
    dmd = DLPC350Controller()
    try:
        dmd.connect()

        print(dmd.get_hardware_status())
        dmd.set_input_source_test_pattern()
        dmd.set_test_pattern_checkerboard()
        time.sleep(3)
        
        # Set timing: 50 ms exposure time (visible to human eye)
        dmd.configure_pattern_timing(exposure_us=50000, period_us=50000)

        # Program 8 stored flash patterns with RGB LEDs ON for testing
        dmd.program_sequence(num_patterns=8, bit_depth=1, enable_leds=True)

        print("[DLPC350] Validation sent. Starting sequence...")
        dmd.start_pattern_sequence()

        time.sleep(5) # Let it play for 5 seconds

    finally:
        dmd.stop_pattern_sequence()
        dmd.disconnect()