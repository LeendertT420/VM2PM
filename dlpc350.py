import time
import os
import struct
import hid

# Texas Instruments DLPC350 Identification
VENDOR_ID  = 0x0451
PRODUCT_ID = 0x6401  # Used for both application and flashing mode


class DLPC350Controller:
    def __init__(self):
        self.dev = None

    def connect(self):
        """
        Connects specifically to Interface 0 (MI_00) of VID 0x0451 / PID 0x6401.
        """
        self.dev = hid.device()
        target_path = None

        # Scan for TI DLPC350 USB devices and target Interface 0
        for device_info in hid.enumerate(VENDOR_ID, PRODUCT_ID):
            if device_info.get('interface_number') in (0, -1):
                target_path = device_info['path']
                break

        if target_path:
            try:
                self.dev.open_path(target_path)
                self.dev.set_nonblocking(1)
                print(f"[USB] Connected to DLPC350 (PID: 0x{PRODUCT_ID:04X}, Interface 0)")
                return True
            except IOError as e:
                print(f"[USB] Connection error: {e}")
                return False
        else:
            print(f"[USB] DLPC350 Interface 0 not found. Check physical USB connection.")
            return False

    def close(self):
        """Closes the HID device handle."""
        if self.dev:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None

    def _send_command(self, cmd2, cmd3, payload=None, rw=0, programming_mode=False):
        """
        Translates TI C++ USB protocol into raw 65-byte USB HID report packets.
        - Normal Mode: Control Flags = 0x40
        - Flash/Programming Mode: Control Flags = 0x47 (Subcode 0x7 active)
        """
        if payload is None:
            payload = []
        
        dest_subcode = 0x07 if programming_mode else 0x00
        flags = (rw << 7) | 0x40 | dest_subcode
        
        length = len(payload) + 2  # CMD2 + CMD3 + Payload length
        
        packet = [
            0x00,                 # USB Report ID
            flags,                # Control Flags
            0x00,                 # Sequence Number
            length & 0xFF,        # Length LSB
            (length >> 8) & 0xFF, # Length MSB
            cmd3,                 # TI CMD3
            cmd2                  # TI CMD2
        ] + list(payload)
        
        # Pad to standard 65-byte USB HID packet length
        packet += [0x00] * (65 - len(packet))
        
        self.dev.write(packet)
        time.sleep(0.02)  # Hardware processing window

    # -------------------------------------------------------------------------
    # PHASE 1: FIRMWARE BINARY PREPARATION
    # -------------------------------------------------------------------------
    @staticmethod
    def build_firmware(stock_bin_path, bmp_folder, output_bin_path):
        """
        Checks for existing binary or verifies stock binary paths.
        """
        print("\n--- Phase 1: Preparing Firmware Binary ---")
        
        # If custom compiled firmware already exists, use it
        if os.path.exists(output_bin_path):
            print(f"[Build] Found compiled binary: '{output_bin_path}'")
            return output_bin_path

        if not os.path.exists(stock_bin_path):
            raise FileNotFoundError(f"Stock base binary '{stock_bin_path}' not found!")

        # Otherwise copy base firmware to destination path
        with open(stock_bin_path, 'rb') as f_in:
            fw_data = f_in.read()

        with open(output_bin_path, 'wb') as f_out:
            f_out.write(fw_data)

        print(f"[Build] Prepared firmware file: '{output_bin_path}'")
        return output_bin_path

    # -------------------------------------------------------------------------
    # PHASE 2: FIRMWARE FLASHING (Bootloader Stream)
    # -------------------------------------------------------------------------
    def flash_firmware(self, bin_path):
        """
        Switches board into programming mode, erases SPI flash, and writes firmware blocks.
        """
        print("\n--- Phase 2: Uploading Firmware to Board ---")
        
        # 1. Stop active pattern display engine FIRST
        print("[Flash] Stopping active display engine...")
        self._send_command(0x1A, 0x24, [0x00])
        time.sleep(0.5)

        # 2. Request Programming Mode with EMPTY payload [] (0 data bytes)
        print("[Flash] Requesting Programming Mode transition...")
        self._send_command(0x30, 0x01, payload=[0x01])
        time.sleep(2.0)

        # Visual Verification Gate
        print("[Flash] Verifying hardware state...")
        print(">> Note: The DMD light output MUST turn off before proceeding.")

        with open(bin_path, 'rb') as f:
            firmware_bytes = f.read()

        # 3. SPI Flash Erase Command (CMD 0x30 0x02)
        print("[Flash] Erasing onboard SPI Flash...")
        self._send_command(0x30, 0x02, programming_mode=True)
        time.sleep(3.0)

        # 4. Stream binary data in 512-byte blocks (CMD 0x30 0x03)
        block_size = 512
        total_blocks = (len(firmware_bytes) + block_size - 1) // block_size

        print(f"[Flash] Writing {len(firmware_bytes)} bytes ({total_blocks} blocks)...")
        for i in range(total_blocks):
            chunk = firmware_bytes[i * block_size : (i + 1) * block_size]
            self._send_command(0x30, 0x03, list(chunk), programming_mode=True)
            
            if i % 100 == 0 or i == total_blocks - 1:
                progress = ((i + 1) / total_blocks) * 100
                print(f"Flashing Progress: {progress:.1f}%", end="\r")

        # 5. Issue Software Reset Command (CMD 0x08 0x02) to reboot
        print("\n[Flash] Upload Complete! Rebooting DLPC350...")
        self._send_command(0x08, 0x02)
        time.sleep(5.0)
        self.close()

    # -------------------------------------------------------------------------
    # PHASE 3: PATTERN SEQUENCE & LUT CONFIGURATION
    # -------------------------------------------------------------------------
    def configure_and_start_sequence(self, num_patterns=8, exposure_us=100000, period_us=100000):
        """
        Sets Pattern Display mode, populates Flash Image LUT, and starts playback.
        """
        print("\n--- Phase 3: Configuring & Starting Pattern Sequence ---")
        
        # 1. Stop active pattern display (0x1A 0x24)
        print("[LUT] Stopping current sequences...")
        self._send_command(0x1A, 0x24, [0x00])

        # 2. Set Pattern Display Mode to 'Pattern Sequence from Flash' (0x1A 0x1B)
        print("[LUT] Setting Mode: Pattern Sequence Mode...")
        self._send_command(0x1A, 0x1B, [0x00])

        # 3. Set Trigger Mode to Internal Trigger (0x1A 0x0A)
        print("[LUT] Setting Trigger: Internal...")
        self._send_command(0x1A, 0x0A, [0x00])

        # 4. Open Pattern LUT Mailbox for writing (0x1A 0x31)
        print(f"[LUT] Configuring LUT Header for {num_patterns} patterns...")
        lut_config = [
            num_patterns & 0xFF, (num_patterns >> 8) & 0xFF,
            0x01,  # Repeat continuously
            num_patterns & 0xFF, (num_patterns >> 8) & 0xFF
        ]
        self._send_command(0x1A, 0x31, lut_config)

        # 5. Populate LUT entries for each 8-bit flash image (0x1A 0x34)
        print("[LUT] Populating LUT entries (Indices 0 through 7)...")
        for idx in range(num_patterns):
            lut_entry = [
                0x01,        # Internal Trigger + Green LED
                idx & 0xFF,  # Flash Image Index
                0x08         # 8-bit depth
            ]
            self._send_command(0x1A, 0x34, lut_entry)

        # 6. Set Exposure & Frame Period timing (0x1A 0x29)
        exp_bytes = list(struct.pack('<I', exposure_us))
        prd_bytes = list(struct.pack('<I', period_us))
        self._send_command(0x1A, 0x29, exp_bytes + prd_bytes)

        # 7. Validate Sequence (0x1A 0x1A)
        print("[LUT] Validating settings with DLPC350...")
        self._send_command(0x1A, 0x1A)
        time.sleep(0.1)

        # 8. Start Pattern Sequence Playback (0x1A 0x24)
        print("[LUT] Starting Playback!")
        self._send_command(0x1A, 0x24, [0x02])
        print("\n sequence running successfully!")


# -----------------------------------------------------------------------------
# MAIN EXECUTION SCRIPT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    STOCK_FIRMWARE  = "DLPR350PROM_v3.0.0.bin"
    CUSTOM_FIRMWARE = "banana_firmware.bin"
    BMP_DIRECTORY   = "dlp_patterns"

    dlp = DLPC350Controller()

    try:
        # Step 1: Ensure firmware binary path is ready
        firmware_file = dlp.build_firmware(STOCK_FIRMWARE, BMP_DIRECTORY, CUSTOM_FIRMWARE)

        # Step 2: Connect and Upload Firmware
        if dlp.connect():
            dlp.flash_firmware(firmware_file)

        # Step 3: Reconnect (post-reboot) and Start Banana Animation
        if not dlp.dev:
            dlp.connect()

        dlp.configure_and_start_sequence(
            num_patterns=8,
            exposure_us=100000,  # 100 ms exposure
            period_us=100000     # 100 ms frame period
        )

    except Exception as err:
        print(f"\n Automation Error: {err}")
    finally:
        dlp.close()