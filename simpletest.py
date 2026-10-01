import hid
import struct
import time

VENDOR_ID = 0x0451
PRODUCT_ID = 0x6401

def build_read_packet(cmd2, cmd3, seq=0x01):
    """
    Builds a 65-byte HID packet formatted for DLPC350.
    In TI's C++ struct, cmd is a 16-bit Little-Endian integer ((CMD2 << 8) | CMD3),
    which places CMD3 at offset 5 and CMD2 at offset 6.
    """
    packet = bytearray(65)
    packet[0] = 0x00  # HID Report ID
    packet[1] = 0x03  # Flags: Read (bit 0 = 1) + Reply Requested (bit 1 = 1)
    packet[2] = seq   # Sequence Number
    packet[3] = 0x02  # Payload Length LSB (2 bytes for command)
    packet[4] = 0x00  # Payload Length MSB
    packet[5] = cmd3  # CMD3 (Low byte in Little Endian)
    packet[6] = cmd2  # CMD2 (High byte in Little Endian)
    return packet

def test_dlpc350():
    try:
        dev = hid.device()
        print("Connecting to DLPC350...")
        dev.open(VENDOR_ID, PRODUCT_ID)
        dev.set_nonblocking(False)
        print("[SUCCESS] USB device handle opened.")

        # List of commands to try: (Name, CMD2, CMD3)
        commands_to_test = [
            ("GET_VERSION", 0x02, 0x05),
            ("STATUS_SYS",  0x1A, 0x0B),
            ("STATUS_HW",   0x1A, 0x0A),
        ]

        for name, cmd2, cmd3 in commands_to_test:
            print(f"\nSending {name} (CMD2: {hex(cmd2)}, CMD3: {hex(cmd3)})...")
            packet = build_read_packet(cmd2, cmd3)
            
            bytes_written = dev.write(packet)
            
            # Read 65 bytes back with a 1.5 second timeout
            response = dev.read(65, timeout_ms=1500)

            if response:
                print(f"[SUCCESS] Received {len(response)} bytes response for {name}!")
                print(f"Raw Header Bytes [0..5]: {[hex(x) for x in response[:6]]}")
                print(f"Raw Data Payload [6..15]: {[hex(x) for x in response[6:16]]}")
                
                # Check for NACK flag in response (Bit 7 of Byte 0)
                nack = (response[0] >> 7) & 0x01
                if nack:
                    print("--> Board returned NACK (Command rejected by board).")
                else:
                    print("--> Board returned ACK (Command accepted!).")
                
                dev.close()
                return
            else:
                print(f"--> [TIMEOUT] No response for {name}.")

        print("\n[FAIL] Device opened and wrote packets, but all commands timed out.")
        dev.close()

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    test_dlpc350()