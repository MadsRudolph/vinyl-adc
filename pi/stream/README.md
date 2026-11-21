# Live stream to a DAW

`vinyl-stream` (C, ALSA) takes over capture from `arecord`. Every ~2.7 ms period it

1. writes the raw I2S words to stdout unchanged, so the ripper reads exactly what it always did, and
2. decimates them with the ripper's own filter (CIC ÷8 + the 161-tap compensating FIR ÷4, taps generated
   from `decimate.py` into `fir_taps.h` by `gen_fir.py`), removes DC with a 2 Hz high-pass, and sends
   RTP: L24, 48 kHz, stereo, 1 ms packets, unicast to `stream_dest`.

Against `decimate.py` on a synthesised modulator bitstream it matches to 0.001 dB; the only difference is
the high-pass's phase (≤ 0.1° at 1 kHz). Expected latency to a DAW: ~2.7 ms period + 1 ms packet +
the receiver's jitter buffer (40 ms: it must exceed the PC's graph quantum, and a DAW at 1024 frames needs ~32 ms; at 5 ms the input went silent).

## Pi

    make -C ~/pi/stream                       # needs libasound2-dev
    curl -X POST http://vinyladc.local:8091/api/config -d '{"stream_dest":"192.168.50.153:46000"}'

With `stream_dest` empty, or the binary missing, the ripper captures with `arecord` as before. Changing it
restarts the capture at once when no side is open; mid-side it waits until the next restart.

## PC (PipeWire)

    cp pc/vinyl-adc-rtp.conf ~/.config/pipewire/pipewire.conf.d/
    systemctl --user restart pipewire pipewire-pulse wireplumber
    sudo ufw allow from 192.168.50.136 to any port 46000 proto udp comment 'Vinyl ADC RTP'

The input appears as **Vinyl ADC** (node `vinyl-adc`). DAWs reach it through PipeWire's JACK
(`pw-jack <daw>` if a DAW insists on its own ALSA backend, which cannot see it).
Check: `pw-record --target vinyl-adc --format s32 test.wav`.

## Measured latency (2026-11-20)

Needle in the run-out groove; the Pi's packet capture (tcpdump on eth0) against a JACK client on the PC
(`pw-jack`, callback timestamps), clocks matched by a UDP exchange (0.12 ms round trip, Pi 7.7 ms ahead),
the two signals aligned above 2 kHz in 100 ms windows (correlation > 0.8). From a packet leaving the Pi
to the DAW's callback holding it:

| DAW buffer | windows | median | max |
|---|---|---|---|
| 128 frames (2.7 ms) | 22 | 17.0 ms | 19.7 ms |
| 256 frames (5.3 ms) | 37 | 12.5 ms | 15.7 ms |
| 1024 frames (21 ms) | 111 | 21.4 ms | 32.3 ms |

Add the Pi's own share, not measured: up to one 2.7 ms capture period plus 0.4 ms of FIR delay. So the
needle reaches a DAW in roughly **15–25 ms**, most of it the PC's jitter buffer (10 ms during the test; now 40 ms so any DAW buffer size works, which adds ~30 ms)
(`sess.latency.msec`) and the DAW's own buffer. The run-out signal is almost all below 200 Hz (motor
rumble), which repeats and fools a plain correlation; only the faint broadband part aligns reliably.

## DAW gotcha: the clock (2026-11-21)

The RTP input has no hardware clock, so PipeWire runs it on its Dummy-Driver, whose `priority.driver`
is 200000. Once a DAW linked it into the same graph as the Scarlett (default 1100), the Dummy-Driver
became the clock for everything, sat idle, and the Scarlett froze (`/proc/asound/card0/pcm0p/sub0/status`
PREPARED or XRUN with `hw_ptr` stuck): Ardour's buttons did nothing and every app went silent.
`pc/51-scarlett-no-suspend.conf` (to `~/.config/wireplumber/wireplumber.conf.d/`) gives the Scarlett
priority 300000 and turns off its idle suspend, so it always drives; the input also no longer sets
`node.always-process`. In `pw-top` the Scarlett should be the driver with `+ vinyl-adc` and `+ ardour` under it.
Ardour also auto-connects every hardware input to new tracks: set Preferences → Signal Flow to connect
track inputs manually and pick only Vinyl ADC.

### And the buffer size

With the DAW at 1024 frames the input overflowed its 40 ms buffer (`mod.rtp-source: receiver read overrun`)
and sounded robotic. `pc/10-vinyl-quantum.conf` caps PipeWire at 256 frames. `pc/52-only-scarlett.conf`
switches off every other sound card (webcam mic at 32 kHz, the dock, onboard and HDMI audio), because
Ardour links every physical input it finds into its graph and those clocks made the same mess.
