# Live stream to a DAW

`vinyl-stream` (C, ALSA) takes over capture from `arecord`. Every ~2.7 ms period it

1. writes the raw I2S words to stdout unchanged, so the ripper reads exactly what it always did, and
2. decimates them with the ripper's own filter (CIC ÷8 + the 161-tap compensating FIR ÷4, taps generated
   from `decimate.py` into `fir_taps.h` by `gen_fir.py`), removes DC with a 2 Hz high-pass, and sends
   RTP: L24, 48 kHz, stereo, 1 ms packets, unicast to `stream_dest`.

Against `decimate.py` on a synthesised modulator bitstream it matches to 0.001 dB; the only difference is
the high-pass's phase (≤ 0.1° at 1 kHz). Expected latency to a DAW: ~2.7 ms period + 1 ms packet +
the receiver's 10 ms jitter buffer ≈ 15 ms.

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
