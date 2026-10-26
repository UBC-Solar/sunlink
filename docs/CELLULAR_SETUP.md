# How to Set Up Cellular for Telemetry

This document provides a simple guide to preparing the physical setup for cellular. Currently, TEL uses a Raspberry Pi + Nighthawk Hotspot configuration in order to send data over to InfluxDB. Alternatively, a method utilizing a dedicated cellular module to do this instead is being worked on.

## RPI + Hotspot

1. First, we must switch TEL from radio to cellular within its software (if it is not already). Open the `main` branch in the `firmware_v4` repo and navigate to `\firmware\common\car_configs\car_configs.h`. Change the value of `CAR_CONFIG_CELLULAR` from 0 to 1.
2. Check the `RADIO/CEL` pins on TEL has a jumper on it so that TEL is in cellular mode in its hardware.
3. Ensure that the RPI has an SD card slotted in. The hotspot should also have an SD card (You can take off the back cover to check.)
4. Plug the hotspot and RPI into a power source and link them together with an ethernet cable. You will know that the ethernet cable is properly connected if there are lights in the port of the RPI.
5. On the hotspot under `Internet`, ensure that the `Ethernet and Cellular` are enabled. Reboot if it asks you to.
6. Under `Network Map`, check that `sunlite` is under `Devices Connected`. This is the step where the most issues occur. You may need to adjust the ethernet settings or keep unplugging and plugging the ethernet cable back in until you see `sunlite`.
7. Connect the RPI to TEL using a USB-to-UART cable -- three of its male header wires should have the labels `GND`, `TX`, AND `RX`. Find the same labelled sockets on TEL and plug them in.
8. Now, you should be able to run the cellular scripts in `README.md` and see data on **Grafana**.