import pycrafter4500

import usb.core

devices = list(usb.core.find(find_all=True))
print(f"Found {len(devices)} devices total.")
for dev in devices:
    print(f"VID: {hex(dev.idVendor)}, PID: {hex(dev.idProduct)}")



pycrafter4500.power_up()

pycrafter4500.pattern_mode(num_pats=3,
                           fps=222,
                           bit_depth=7,
                           led_color=0b111,  # BGR flags                 
                           )

pycrafter4500.power_down()