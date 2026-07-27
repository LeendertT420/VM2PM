import time
from dlpc350 import DLPC350Controller

def force_pattern(dmd, pattern_id):
    """
    Sequence required by DLPC350 to stop flash playback and force internal pattern:
    1. Stop Pattern Sequence (CMD2: 0x1A, CMD3: 0x24)
    2. Unpark DMD (CMD2: 0x06, CMD3: 0x09)
    3. Set Display Mode to Pattern Mode (CMD2: 0x1A, CMD3: 0x1B)
    4. Set Internal Test Pattern (CMD2: 0x1A, CMD3: 0x11)
    """
    # 1. Stop current playback
    dmd.send_command(0x02, 0x1A, 0x24, [0x00])
    time.sleep(0.05)

    # 2. Unpark DMD
    dmd.send_command(0x02, 0x06, 0x09, [0x00])
    time.sleep(0.05)

    # 3. Set Pattern Display Mode (0x01)
    dmd.send_command(0x02, 0x1A, 0x1B, [0x01])
    time.sleep(0.05)

    # 4. Set Test Pattern (0x01 = Solid White/ON, 0x00 = Solid Black/OFF)
    dmd.send_command(0x02, 0x1A, 0x11, [pattern_id])

def main():
    dmd = DLPC350Controller()
    dmd.connect()

    try:
        print("1. Forcing ALL mirrors to ON (+12 degrees)...")
        force_pattern(dmd, 0x01) # White pattern
        print("Check DMD surface. Logo should disappear into uniform mirror reflection.")
        time.sleep(5)

        print("2. Forcing ALL mirrors to OFF (-12 degrees)...")
        force_pattern(dmd, 0x00) # Black pattern
        print("Check DMD surface. Surface should go dark/dull.")
        time.sleep(5)

    finally:
        dmd.disconnect()

if __name__ == "__main__":
    main()