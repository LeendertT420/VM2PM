

import argparse
import time

# The SDK modules are provided by the Optotune wheels. Install them first as shown above.
try:
    # optoICC exposes the board API; optoKummenberg contains UnitType/definitions in some SDK versions
    import optoICC
    # Try to import UnitType from either module (examples use optoKummenberg.UnitType or optoICC.UnitType)
    try:
        from optoKummenberg import UnitType
    except Exception:
        UnitType = getattr(optoICC, 'UnitType', None)
except Exception as e:
    raise RuntimeError(
        "Could not import optoICC SDK modules. Make sure you installed the provided .whl files "
        "from your SDK download. See top of this script for pip commands.") from e


def find_lens_channel(board):
    """Return (channel_index, channel_obj) for the first connected lens device, or raise RuntimeError."""
    # DeviceModel enum is available in docs: optoICC.tools.definitions.DeviceModel
    try:
        from optoICC.tools.definitions import DeviceModel
    except Exception:
        # fallback: check names on connected_devices
        DeviceModel = None

    connected = []
    # Query device types for up to 4 channels (ICC-4C supports 4)
    for ch in range(4):
        try:
            dev_type = board.MiscFeatures.GetDeviceType(ch)
        except Exception:
            dev_type = None
        connected.append(dev_type)

    # If DeviceModel available, match known lens enums (EL_1640_TC corresponds to EL_1640_TC)
    if DeviceModel is not None:
        for idx, d in enumerate(connected):
            if d is None:
                continue
            try:
                dm = DeviceModel(d)
            except Exception:
                continue
            if dm.name.startswith('EL_'):
                return idx, board.channel[idx]
    # fallback: pick first non-zero / non-None device
    for idx, d in enumerate(connected):
        if d is not None:
            return idx, board.channel[idx]
    raise RuntimeError('No lens device found on any channel')


def continuous_sweep(port='COM4', min_dpt=-50.0, max_dpt=50.0, steps=500, half_cycle_time=5.0):
    """Perform a continuous sweep from min_dpt to max_dpt and back.

    half_cycle_time = seconds to go from min->max (so full cycle is 2*half_cycle_time)
    steps = number of discrete steps per half cycle
    """
    print(f"Connecting to controller on port {port}...")
    # connect() auto-detects board type. Use port explicit to avoid searching.
    board = optoICC.connect(port=port)

    ch_idx, ch = find_lens_channel(board)
    print(f"Found lens on channel {ch_idx}")

    # Use static focal-power input
    ch.StaticInput.SetAsInput()

    # Optionally, you can use the signal generator in FP unit as an alternative.
    # Prepare sweep sequence
    step_dt = float(half_cycle_time) / max(1, steps)
    up_values = [min_dpt + (max_dpt - min_dpt) * i / steps for i in range(steps + 1)]
    down_values = list(reversed(up_values))

    print(f"Starting continuous sweep: {min_dpt} dpt -> {max_dpt} dpt -> {min_dpt} dpt (step_dt={step_dt:.4f}s, steps={steps})")
    try:
        while True:
            for v in up_values:
                # Set focal power in diopters
                ch.StaticInput.SetFocalPower(float(v))
                time.sleep(step_dt)
            for v in down_values:
                ch.StaticInput.SetFocalPower(float(v))
                time.sleep(step_dt)
    except KeyboardInterrupt:
        print('\nKeyboard interrupt received — stopping sweep and setting focal power to 0 dpt')
        try:
            ch.StaticInput.SetFocalPower(0.0)
        except Exception:
            pass
        print('Done')
    except Exception as e:
        print(f'Error during sweep: {e}')
        raise


def main():
    parser = argparse.ArgumentParser(description='Continuous focal-power sweep for Optotune lens')
    parser.add_argument('--port', default='COM4', help='Serial port where controller is attached (default COM4)')
    parser.add_argument('--min', type=float, default=-2., help='Minimum focal power (dpt)')
    parser.add_argument('--max', type=float, default=3., help='Maximum focal power (dpt)')
    parser.add_argument('--steps', type=int, default=500, help='Steps per half-cycle')
    parser.add_argument('--half-time', type=float, default=5.0, dest='half_cycle_time',
                        help='Time (s) to sweep from min to max (half cycle)')
    args = parser.parse_args()

    continuous_sweep(port=args.port, min_dpt=args.min, max_dpt=args.max, steps=args.steps,
                     half_cycle_time=args.half_cycle_time)


if __name__ == '__main__':
    main()
