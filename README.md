# Petlibro PLWF116 with ESPHome

ESPHome for the Petlibro PLWF116 cordless water fountain (Dockstream 2 Cordless,
3 L, battery, two radar sensors). The board has a Realtek RTL8721DM (AmebaD)
with 8 MiB flash. The vendor bootloader stays on the chip.

**Status:** runs on one device since November 2026. Pump, scale, LEDs, button,
battery, power supply detection and radar work. OTA updates work in both slots.

## Disclaimer

Use this at your own risk. Flashing replaces the vendor firmware, can make the
device unusable and ends the warranty. The device then no longer works with the
Petlibro app or cloud. You are responsible for the safety of your pets: check
that the pump, the dry-run protection and the water level work before you
leave the fountain alone. Open the device only when it is unplugged, and use
3.3 V on the UART only.

This project is not affiliated with or endorsed by Petlibro. Product names are
trademarks of their owners. The software comes without warranty, see
[LICENSE](LICENSE).

## Requirements

AmebaD support is not merged upstream yet. You need:

- ESPHome from [esphome#18718](https://github.com/esphome/esphome/pull/18718)
  (`pip install git+https://github.com/esphome/esphome.git@refs/pull/18718/head`)
- LibreTiny from [libretiny#403](https://github.com/libretiny-eu/libretiny/pull/403)
  plus the patches in [`libretiny/`](libretiny/) (chip model, board). The configs
  use the branch `plwf116` of [GoliathLabs/libretiny](https://github.com/GoliathLabs/libretiny),
  which is #403 plus these patches.
- ltchiptool from [ltchiptool#98](https://github.com/libretiny-eu/ltchiptool/pull/98)
  for the first flash over UART. Also install it into
  `~/.platformio/penv/.libretiny`, else the build stops with
  "Unsupported family - realtek-ambd".

## Pinout

GPIO numbers: PA_n = n, PB_n = 32 + n. ESPHome does not know the board, so the
configs use these numbers.

| Function | Pin | Notes |
|---|---|---|
| Pump | PA_30 (30) | HIGH = on. Pull-up after reset: the pump runs until the firmware drives it LOW |
| Pump boost | PB_4 (36) | HIGH = boost, only with the pump on |
| Scale HX717 SCK / DOUT | PB_5 (37) / PB_6 (38) | works with the `hx711` component |
| Button | PA_15 (15) | active low, external pull-up |
| Power supply | PA_13 (13) | LOW = adapter plugged in |
| Charging | PA_12 (12) | LOW = charging |
| Battery voltage | PB_2 (34), ADC | divider assumed 1:2 |
| Radar detection | PA_14 (14) | LOW = detected, both sides on one line |
| Radar power | PA_16 (16) | LOW = on |
| Radar config | PA_19 (19), PB_1 (33) | one-wire, idle HIGH |
| LED WiFi white / red | PA_26 / PA_28 | all LEDs active high |
| LED water red / yellow | PA_25 / PB_3 | |
| LED filter | PB_7 | |
| LED battery white / red | PB_23 / PB_26 | |
| Board revision | PA_17, PA_18 | inputs |
| Unknown | PB_22 | output in the vendor firmware, no visible effect |
| Log UART | PA_7 (TX), PA_8 (RX) | 115200, pads TX/RX/GND/3V3 on the board |

## Flash layout

| Area | Content |
|---|---|
| `0x000000–0x006000` | vendor bootloader (KM0 + KM4). Keep it |
| `0x006000` | OTA1, LibreTiny app (max. 0xFA000) |
| `0x100000` | SDK settings |
| `0x186000` | OTA2. Vendor firmware at first |
| `0x306000` | LibreTiny KVS |
| `0x3EC000`, `0x7C0000` | vendor data (cloud identity, calibration, log). Keep it |

The bootloader starts OTA2 if its signature `81958711` is valid, else OTA1.

## First flash

1. Make a full backup of the flash first. It holds the device's cloud
   identity, so do not publish it.
2. UART download mode: unplug the power, hold the TX pad to GND, plug in the
   power, release after 2–3 s. Connect a 3.3 V USB UART adapter (adapter RX to
   TX, adapter TX to RX, GND). Do not power the board from the adapter.
3. Build `esphome/plwf116-minimal.yaml` or `esphome/plwf116.yaml`. The image is
   `.esphome/build/<name>/.pioenvs/<name>/image_ota.0x006000.bin`.
4. From a LibreTiny checkout:
   ```
   python path/to/scripts/ambd_session.py check IMAGE PORT
   python path/to/scripts/ambd_session.py write IMAGE PORT
   python path/to/scripts/ambd_session.py invalidate-ota2 PORT
   ```
   `invalidate-ota2` zeroes the 8 signature bytes of the vendor firmware in
   OTA2. Then the bootloader starts OTA1.
5. Power cycle without the bridge. After that, use OTA.

The first OTA update writes OTA2 and replaces the vendor firmware there.

To go back, write the full backup at `0x0`.

## Notes

- **OTA:** with libretiny#403 the update image has a blank slot signature. The
  firmware writes it after the last block, so an update that stops early does
  not leave a broken slot that the bootloader would start.
- **OTA authentication:** `ota` uses `encryption` with the `api_key` (no
  password). A device still running password-OTA firmware needs one transition
  install: add `password: !secret ota_password` and `allow_plaintext_upload: true`
  under `ota: encryption:`, upload once, then remove both.
- **Flash loader:** it sends stray NAK bytes. `ambd_session.py` works around
  this until ltchiptool skips them. Writes failed under WSL2 with usbipd; they
  worked with ltchiptool on native Windows.
- **Scale:** zero point and factor are per device. Measure the raw value with
  an empty tank, then add or remove a known amount of water.
- **Button:** the pin reads "pressed" for a moment at boot. The config ignores
  clicks in the first 10 s.
- **Power:** the device restarts when the adapter is plugged in or unplugged.
- **Pump mode:** "Radar auf Akku" (default) runs the pump all the time on the
  adapter and only after a detection on battery, like the vendor firmware.

## Not done

- Radar gain and threshold (one-wire on PA_19/PB_1). The sensors keep their
  own settings.
- Battery divider not measured.
- `invalidate-ota2` in this script form is not tested. The same write was
  done with ltchiptool directly.
- BLE.

## License

MIT
