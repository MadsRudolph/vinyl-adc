# Raspberry Pi capture

The ADC is the I²S clock master; the Pi only listens. Status: the wiring and clocking follow the schematic and the 17 September bench screen (PI_BCLK 3.0727 MHz, PI_LRCLK 48.011 kHz, PI_DIN toggling, all 3.3 V logic). The overlay compiles and `decimate.py` passes its synthetic test, and on 17 September the overlay was installed on a Pi 4 (Pi OS Trixie, kernel 6.18): the `vinyladc` capture card registers and the I²S block programs 64-bit frames in consumer mode. **No capture from the real ADC has been decoded yet**; treat the first one as bring-up.

## 1. Wiring: digital board J2 → Pi 40-pin header

J2 is the single row of 8 on the digital board; pin 1 is the square pad.

| J2 pin | Signal | Pi pin | Notes |
|---|---|---|---|
| 1 | +5 V | 2 (5 V) | **Leave open for the first power-up**, see below |
| 2 | GND | 6 | |
| 3 | +3.3 V | 1 (3V3) | Powers only the 74HC4049 level shifter. Remove the AD3 V+ wire first |
| 4 | PI_BCLK | 12 (GPIO18, PCM_CLK) | 3.072 MHz, from the ADC |
| 5 | PI_LRCLK | 35 (GPIO19, PCM_FS) | 48 kHz, from the ADC |
| 6 | PI_DIN | 38 (GPIO20, PCM_DIN) | interleaved modulator bits |
| 7 | GPCLK0 | leave open | only for clocking the ADC from the Pi (J1 on 2–3); J1 stays on 1–2, the crystal |
| 8 | GND | 39 | |

Keep these wires short (10 cm jumpers are fine) and run the two grounds.

## 2. Power

**First power-up (recommended): keep the Korad.** J2.1 stays on the Korad at 5.00 V with the 0.30 A limit, exactly as in the bench tests, and is *not* connected to the Pi. The Pi shares ground, supplies the 3.3 V and receives the three signals. A wiring mistake then trips the Korad instead of loading the Pi's 5 V rail. The stack draws about 74 mA.

**Final build:** Pi pin 2 → J2.1 and no Korad. Never connect both 5 V sources at once.

**Power-up order: boot the Pi first, then switch the ADC's +5 V on.** Measured on a Pi 4 (Pi OS Trixie, kernel 6.18): the I²S block comes out of reset as clock *master*, so from the moment the driver claims GPIO18/19 until a capture device is first opened, both clock pins are **outputs** (`MODE_A = 0`). `vinyl-adc-consumer.service` (installed by `install-overlay.sh`) opens the device once at boot and logs the pin state before and after; it finishes about 22 s after kernel start, and from then on both pins are inputs (`CLKM = FSM = 1`). With the ADC unpowered during that window its level shifter outputs sit low, the same level the Pi drives, so nothing fights. `sudo python3 pcm_pins.py` shows the current direction at any time.

For the final build, where the Pi's own 5 V powers the stack and the ADC therefore clocks during the Pi's boot, fit about 470 Ω in series with PI_BCLK and PI_LRCLK so the ten-second overlap is current-limited to a few milliamps.

The 74HC4049 itself is safe in either order: it accepts 5 V inputs with its own supply at 0 V, and its outputs can never exceed the Pi's 3.3 V because that is its supply.

The Pi must not drive GPIO18/19. They are inputs by default and with this overlay. Remove any other I²S sound overlay (hifiberry, iqaudio, googlevoicehat, i2s-…) from `config.txt` before connecting, because a Pi configured as I²S master would fight the ADC's clock outputs.

## 3. Pi setup (once)

Copy this `pi/` folder to the Pi, then on the Pi:

```sh
sudo apt install device-tree-compiler python3-numpy
cd pi && ./install-overlay.sh
sudo reboot
```

`vinyl-adc-overlay.dts` is the capture twin of the stock `i2s-master-dac` overlay: I²S controller in clock-consumer mode, two 32-bit slots, with the S/PDIF receiver stub as a dummy capture codec.

After the reboot:

```sh
arecord -l        # expect: card N: vinyladc [vinyl-adc], device 0
```

## 4. Capture and decimate

```sh
arecord -D hw:CARD=vinyladc -c 2 -r 48000 -f S32_LE -t raw -d 10 capture.raw
python3 decimate.py capture.raw capture.wav
```

The 32-bit words are not PCM: each 64-bit frame carries 32 left and 32 right modulator bits at 1.536 MHz. `decimate.py` de-interleaves them and decimates by 32 (4th-order CIC to 192 kHz, then a 161-tap droop-compensating FIR), printing each bitstream's one-density and the DC, RMS and peak per channel before writing a 32-bit 48 kHz WAV. `python3 test_decimate.py` checks it against a synthetic stream (1 kHz at 0.5 FS and 18 kHz at 0.25 FS recover within 0.03 dB).

`python3 analyze_bitstream.py capture.raw` judges each modulator from the raw bits at 1.536 MHz: in-band floor, noise-shaping slope (about +60 dB/decade just above the audio band for a healthy third-order loop) and the idle tone, which sits at |DC| × 1.536 MHz.

**First capture, inputs still shorted:** expect both one-densities near 0.50 (the bench measured 0.50 and 0.53 per channel, 0.516 combined), a small DC term and a low RMS noise floor.

**Left/right:** by the divider's phase the first bit after the frame edge belongs to the left channel. Confirm by feeding a signal into the LEFT input only; if it appears on the right, add `--swap`.

## 5. The ripper and its dashboard

`vinyl-adc-ripper.service` starts at boot and owns the capture card. Dashboard: **http://vinyladc.local:8091**.

- **Automatic.** When the level stays above the start threshold for two seconds a *side* is recorded to `~/vinyl/sides/` (with 2.5 s of pre-roll); 30 s of silence (80 % of a 30 s window below −65 dB, a rule that survives the clicks of a lifted needle but not the long gap after a fade-out) closes it. The detector is treble-weighted, so mains hum cannot trigger it, and it uses a window rather than a run, so isolated clicks do not keep a finished side open. Sides shorter than 90 s are discarded.
- **The record identifies itself.** Two minutes into a side the ripper fingerprints the audio so far (Chromaprint's `fpcalc`, package `libchromaprint-tools`) and asks [AcoustID](https://acoustid.org) which recording it is. From the answer it picks the release (the album already in use wins if one of its recordings matched; otherwise a vinyl pressing is preferred), fetches the tracklist from MusicBrainz and knows which track the side started with. Playing side B first, or dropping the needle in the middle, therefore works. This needs a free AcoustID *application* key: register one at <https://acoustid.org/new-application> and write it to `~/vinyl/acoustid.key` on the Pi (one line), then restart the service. Without the key the dashboard says so and you pick the album by hand with the MusicBrainz search, before or after playing it.
- **Cutting.** After a side closes, the music's start and end are found from 3 s windows (single clicks do not count and fade-outs are kept), gaps are recomputed from the finished envelope and merged across clicks, and the side is matched to the tracks from its starting point by duration. Each cut is snapped to the quiet gap nearest the expected boundary (within 15 s); where tracks run into each other it lands on the quietest second near the expected time.
- **Nothing to do.** A side of a record whose tracks are already in the library is moved to the trash instead of being assigned again. An album that has not received a side for three hours is sent as it is, and so is an album in progress when a different record is identified, so one side played on its own still ends up in Jellyfin. When the disk drops below 3 GB free the ripper removes trash and the raw audio of albums already delivered, oldest first (`min_free_gb`).
- **Finishing.** When the last side is in, or on "Finish and send", all tracks get one common gain (album peak to −1 dBFS), are encoded to 24-bit 48 kHz FLAC, tagged (title, artist, album, track and disc numbers, date, MusicBrainz ids, `MEDIA=Vinyl`), given the Cover Art Archive front cover, and published under `~/vinyl/library/` and at `/outbox.json`.
- **Delivery.** `server/vinyl-pull.py` on the media server polls the outbox every two minutes and files albums under `/srv/media/music/Vinyl/Artist/Album (Year) [Vinyl]/`. See `server/README.md`.
- **Channel faults.** A channel whose bitstream is stuck or oscillating is detected from its run lengths; the healthy channel is then recorded to both sides (mono) and the dashboard says so. Runs of 7+ identical bits, which music never produces, are repaired in the bitstream before decimation.
- **For measurements** the ripper serves the last 60 s of decimated audio at `/api/audio?seconds=N` (float32 stereo, 48 kHz) and `/api/hold {seconds}` keeps it from recording test tones as a side; `assembly/bench/run.py audio` uses both.
- Offline tests: `python3 test_ripper.py` (identification, cutting, repeat plays) and `python3 ripper.py --replay capture.raw --fast --home /tmp/vinyl`.

`live.py` (`vinyl-adc-live.service`, disabled) is the diagnostic view with the modulator noise spectra; the two services conflict because only one process can hold the capture card: `sudo systemctl start vinyl-adc-live` stops the ripper, and starting the ripper again stops the live view.

## 6. If it does not work

| Symptom | Check |
|---|---|
| `arecord -l` shows no vinyl-adc card | `dmesg | grep -i -E 'i2s|asoc|simple-card|spdif'`; is `dtoverlay=vinyl-adc` in `config.txt`; is another sound overlay claiming I²S |
| `arecord` starts but writes nothing, then times out | The Pi is a clock consumer: no BCLK/LRCLK, no data. Check the stack is powered, J1 on 1–2, 3.3 V on J2.3, GPIO18/19 wiring |
| One-density 0.000 or 1.000 | Data line stuck: J2.6 ↔ GPIO20, that channel's J21 shunt, the bus |
| One channel fine, the other dead | That channel board or its J21 (left 1–2, right 2–3; pin 1 is the pin farthest from the bus) |
| Audio present but sounds like noise | Word alignment differs from the I²S assumption: try `--swap`; if still wrong, keep the `.raw` file, it contains everything needed to fix the unpacking offline |
