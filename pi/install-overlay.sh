#!/bin/sh
# Run ON THE RASPBERRY PI from this folder. Compiles the overlay, installs it and enables it in config.txt.
set -eu
command -v dtc >/dev/null || { echo "Install the device-tree compiler first: sudo apt install device-tree-compiler"; exit 1; }
BOOT=/boot/firmware; [ -d "$BOOT/overlays" ] || BOOT=/boot
dtc -@ -I dts -O dtb -o vinyl-adc.dtbo vinyl-adc-overlay.dts
sudo cp vinyl-adc.dtbo "$BOOT/overlays/"
CFG="$BOOT/config.txt"
grep -q '^dtoverlay=vinyl-adc' "$CFG" || echo 'dtoverlay=vinyl-adc' | sudo tee -a "$CFG" >/dev/null
sudo install -D -m 644 pcm_pins.py /usr/local/lib/vinyl-adc/pcm_pins.py
sudo install -m 644 vinyl-adc-consumer.service /etc/systemd/system/vinyl-adc-consumer.service
sudo systemctl daemon-reload && sudo systemctl enable vinyl-adc-consumer.service >/dev/null 2>&1
echo "Installed $BOOT/overlays/vinyl-adc.dtbo, enabled it in $CFG, and enabled the boot-time consumer-mode service."
echo "Check that no other I2S sound overlay (hifiberry-*, iqaudio-*, googlevoicehat-*, i2s-*) is enabled there:"
grep -n -E '^dtoverlay=(hifiberry|iqaudio|googlevoicehat|i2s-|adau|audioinjector)' "$CFG" || echo "  none found"
echo "Reboot, then: arecord -l   (expect a card named vinyl-adc)"
