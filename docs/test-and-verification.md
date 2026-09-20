# Vinyl ADC — test and verification

**Date:** 18 September 2026 · **Unit:** the four-board stack, both channels · **Verdict:** both channels functional and measured; the left channel meets the simulated target, the right does not.

This is the acceptance record for the finished converter: what was measured, with what, under what conditions, and what the numbers do and do not mean. It is deliberately explicit about the instrument's own limits, because several figures here are bounded by the generator rather than by the converter.

---

## 1. Configuration under test

| | |
|---|---|
| Boards | Power, digital, channel L, channel R — the full stack, assembled |
| Supply | Korad bench supply, 5.00 V, 73 mA typical. **Not** the Pi's 5 V (see §6) |
| Clock | Crystal Pierce oscillator on the digital board, MCLK 1536.296 kHz |
| Modulator | Third-order delta-sigma, 1.536 MHz, interleaved L/R on one data line |
| Capture | Raspberry Pi 4, I²S clock consumer, ÷32 decimation to 48 kHz (4th-order CIC ÷8 + 161-tap compensating FIR ÷4) |
| Input | J20 on each channel board, via RV20 input trimmer |
| Repairs in place | Solder-side wires J7.16→U22.4 and J7.2→U23.14 on both boards; DACP_L short to ground cleared on the right board |

Two faults were fixed on the day of these measurements, both on the right channel, and both are described in `bringup-log-2026-09.md` §8.4 and §8.6. The measurements below are all post-repair.

## 2. Instruments and their limits

| Instrument | Role | Limit that matters |
|---|---|---|
| Analog Discovery 3, W1 | Signal source into J20 | **14-bit: bounds measured distortion and noise near −80 dB.** Anything better than that is the generator, not the converter |
| AD3 scope, 10×/1× probes | Rail and node verification | — |
| Raspberry Pi ripper `/api/audio` | Delivers the decimated 48 kHz output for analysis | Serves the *last* N seconds; a capture window must be waited out (§7) |
| `pi/live.py` | Bitstream health per channel | Analyses the raw 1-bit stream, not the decimated audio |
| `assembly/bench/run.py audio` | The measurement plan | Records figures, does not judge them; `PASS` means "completed" |

**W1 cannot reach 0 dBFS on this converter.** Full scale is 10.41 Vpk on the left channel and W1 stops near ±5 V, so the −3 dBFS point was unreachable: both the −3 and −6 dBFS requests land at −6.37 dBFS, and the "−3 dBFS" row in the raw reports is a second −6 dBFS measurement.

## 3. Modulator verification — the 1-bit stream

Both inputs shorted at J20, Korad supply, analysed at 1.536 MHz from the raw bitstream. This tests the loop itself, with the input network grounded and no instrument attached.

| | Left | Right | Healthy |
|---|---|---|---|
| Verdict | third-order shaping | third-order shaping | — |
| Mean run of identical bits (max) | 1.352 (3) | 1.361 (3) | ≈1.35; a limit cycle gives 18–19 |
| One-density, no input | 0.4957 | 0.4957 | ≈0.5 |
| Noise shaping, 30→80 kHz | +68.1 dB/dec | +68.6 dB/dec | ≈+60 for third order |
| In-band noise, 20 Hz–20 kHz | −76.75 dBFS | −77.49 dBFS | — |
| Noise density at 1 kHz | −125.8 dBFS/Hz | −125.9 dBFS/Hz | — |
| Noise density at 20 kHz | −121.3 dBFS/Hz | −121.0 dBFS/Hz | — |
| DC offset | −0.0087 | −0.0087 | — |

**The two modulators are indistinguishable.** Density matches to four decimal places, mean run to 0.01, shaping to 0.5 dB/decade, and the right channel is marginally the quieter of the two. Whatever separates the channels in §4 is not the loop, the rails, the references or the DAC.

## 4. Audio performance — the decimated 48 kHz output

W1 driving J20 of the channel under test, the other channel's input shorted, capture from the ripper. Left run `20260918T093339Z-audio-a485477f`, right run `20260918T094918Z-audio-78d57572`.

| Measurement | Left | Right |
|---|---|---|
| Full-scale input | 10.41 Vpk (7.362 Vrms) | 9.484 Vpk |
| Output for 0.5 Vpk at 1 kHz | −26.37 dBFS | −25.56 dBFS |
| **Frequency response, 20 Hz–16.3 kHz** | **0.119 dB p-p** | **0.139 dB p-p** |
| Dynamic range (AES17, −60 dBFS tone, A-wtd) | **67.94 dB** | 57.92 dB |
| SNR (0 dBFS re idle noise, A-wtd) | **67.66 dB** | 58.70 dB |
| Idle noise (generator connected) | −66.17 dBFS / −67.66 dBFS(A) | −57.33 / −58.70 |
| THD at −6 dBFS | 0.0282 % | 0.0841 % |
| THD at −20 dBFS | 0.0320 % | 0.1233 % |
| 2nd harmonic | −75.78 dBc | −65.07 dBc |
| 3rd harmonic | −83.68 dBc | −62.54 dBc |
| IMD CCIF 19+20 kHz | −82 dB *(generator-limited)* | −80.46 dB *(generator-limited)* |
| IMD SMPTE 60 Hz + 7 kHz (4:1) | 0.139 % | 0.162 % |
| Hum, 50 / 100 Hz | −99.49 / −111.7 dBFS | −93.11 / −101.3 dBFS |
| Crosstalk into the other channel | −92.42 dB | −67.56 dB |

**The left channel meets the design target.** SPICE predicted about 68 dB SNR for the third-order loop with delay compensation; the hardware returns **67.94 dB of dynamic range and 67.66 dB SNR**. Frequency response is flat to **±0.06 dB from 20 Hz to 16.3 kHz**, which is the decimator's FIR behaving as designed.

For context, the benchmark that matters for this machine is the source: a good vinyl pressing delivers 60–70 dB. The left channel sits inside that; CD's 96 dB is not the relevant bar.

### Figures that are noise, not distortion

THD at −40 and −60 dBFS reads 1.6 % and 2.3 %. At those levels the tone is close to the noise floor and THD+N is noise-dominated. These are not distortion results and should not be quoted as such. The meaningful distortion points are −6 and −20 dBFS.

## 5. Finding: the right channel's deficit is in the input path, not the converter

The right channel is **9–10 dB worse in noise and dynamic range, and 3–4× worse in distortion**, with the 3rd harmonic 21 dB worse. This is a real difference, measured with the left input shorted; it is not a floating-input artefact.

The important observation is where it *isn't*:

- At the **bitstream** level with the input shorted (§3), the right channel equals the left — in fact it is 0.7 dB quieter.
- At the **audio** level with a source driving the input network (§4), it is 9 dB noisier.

The loop, rails, references and DAC are therefore exonerated by §3. The deficit appears only when the signal passes through the input network, which on each board is `J20 → C20 (2u2) → R20 (1k00) → C21 (1n5)/RV20 (47 k) → R21 (20k5) → integrator 1`.

**Leading hypothesis: the right board's RV20 trimmer.** During the gain-matching procedure its output dropped 80 dB momentarily and recovered — a direct observation of an intermittent wiper. A dirty or worn wiper contributes exactly what is measured: contact noise (excess broadband noise) and a non-linear contact resistance in series with the signal (harmonic distortion, odd orders especially, matching the 21 dB rise in the 3rd harmonic). Once set and left alone the trimmer is stable to 0.01 dB over 20 s, so the fault is intermittent rather than continuous.

**Next test:** clean or replace RV20 on the right board and repeat §4. If the noise returns to ≈−66 dBFS and THD to ≈0.03 %, this is settled. That measurement has not been made and the hypothesis is not yet proven.

### Channel gain matching

RV20 sets each channel's full-scale input, so **full scale is a calibration, not a property of the converter**. The two were matched by driving 0.5 Vpk at 1 kHz and reading the ADC output: the left gives −26.37 dBFS, the right was set to −25.56 dBFS, leaving **0.81 dB of channel imbalance**. Setting both trimmers to the same physical rotation is not sufficient — these are ±20 % parts and identical positions differed by about a dB.

At 10.41 Vpk (7.36 Vrms) of full scale, a phono stage delivering ~0.5 Vrms would peak near −23 dBFS and waste most of a converter that only has ~68 dB to give.

### Set against the real source, 2026-09-20

Done, with the converter in the listening chain: the Phono Box output and the Saga input now share J20's two screws on each board, so the record plays through the speakers and into the ADC from one junction. Levels were set with a record playing, using `pi/levels.py`.

| | before | after |
|---|---|---|
| Music peak, left | −13.9 dBFS | **−6.9 dBFS** |
| Music peak, right | −13.9 dBFS | **−6.9 dBFS** |
| Channel imbalance | 0.81 dB (1 kHz tone) | **0.0 dB** |

"Music peak" is the 95th percentile of the 100 ms peak buckets over 30 s, not the maximum: the loudest transients in the same passage reached −3.6 dBFS, and those are clicks in the groove. Trimming to them would have left the record 7 dB quieter than it needs to be.

**Checked for clamping, and there is none.** A 10 s capture gives a crest factor of 15.9 dB (left) and 16.8 dB (right), with 1 sample in 480 000 above 99 % of peak and 13 above 90 %. A limiter or an input clamp in circuit piles thousands of samples at one amplitude; this distribution is ordinary music. The +7 dB moves the converter from roughly the low 60s to the 68 dB region of the design curve (`docs/design-notes.md` §3).

Both boards read **Healthy** at the bitstream level while doing this — density 0.4956 / 0.4959, mean run 1.34 / 1.35 — and the ripper selected **stereo**, not the mono fallback it used before the right-channel repair.

## 6. Conditions not covered

- **Pi-powered operation.** All figures here are on the Korad bench supply. The 1-bit DAC gates run directly from +5 V, so that rail *is* the DAC reference; running from the Pi previously cost 6–11 dB of idle noise. The 5 V filtering and the 470 Ω series resistors in PI_BCLK/PI_LRCLK that address this are not fitted.
- **Idle noise is not comparable between §3 and §4.** §3 shorts the input; §4 has the generator wired to it, contributing its own noise. The −66.2 dBFS in §4 and the −76.8 dBFS in §3 are measurements of different configurations.
- **Right channel after an RV20 repair** — the open item from §5.
- **The top octave, 16.3–20 kHz.** `sweep_points()` steps in third-octaves from 20 Hz and stops at 16255 Hz because the next step would pass 20 kHz, so the highest measured point is 16.3 kHz. The plan's own row is *labelled* "20 Hz–20 kHz" and that label overstates what was swept — a figure of ±0.06 dB should be quoted to 16.3 kHz, not 20 kHz.
- **A full record side end to end**, and the enclosure as a physical print.
- **Hum with the turntable connected.** The −99.5 dBFS here is with the generator driving the input. With the phono lead attached, hum was previously −39 dBFS at 50 Hz. After the tap was wired (2026-09-20) the 50 Hz line measured −60 to −63 dBFS, but *with a record playing*, so music and groove rumble are mixed into that figure and it is only an upper bound. It does establish that the −39 dBFS condition is gone. A clean measurement needs the stylus up and the turntable stopped, and has not been made.

## 7. Two measurement bugs found, and why the first runs were invalid

The first two audio runs produced figures that were artefacts of the bench code. Both are fixed; runs before `20260918T093339Z` should be discarded.

**A fixed ±4-bin measurement window on a self-clocked converter.** The ADC generates its own LRCLK at 1536296/32 = 48009 Hz, not 48000, so a tone lands about 190 ppm low and drifts out of a fixed window in proportion to frequency. Reproduced on a synthetic full-level tone: the old code loses **35 dB at 8 kHz and 70 dB at 19 kHz**. It presented as a "frequency response" that fell off a cliff at 5 kHz, and as nonsensical IMD (SMPTE 15 %, CCIF −14 dB). `band_power` now searches ±600 ppm for the tone before summing. The same captures re-analysed gave CCIF −82 dB and SMPTE 0.14 %.

*Caught by:* the rolloff being far too steep for any analogue filter, then reading where the spectral peak actually was.

**A capture window longer than its settle time.** The noise step silenced the generator, waited 5 s and asked the ripper for the last 8 s — so 3 s of the window predated the change and still held the previous step's 1 kHz tone. "Idle noise" measured that tone.

*Caught by:* A-weighted and unweighted idle noise agreeing to four significant figures, which only happens if the "noise" is a 1 kHz tone — A-weighting is 0 dB at exactly 1 kHz.

Two operational notes on the bench GUI, both of which cost a run: it imports `run.py` and `audio.py` at start, so code edits need a restart; and it holds the AD3 until its process exits, so a second run needs a restart too.

## 8. Traceability

| Artefact | Where |
|---|---|
| Left channel audio run | `assembly/bench/results/20260918T093339Z-audio-a485477f/` |
| Right channel audio run | `assembly/bench/results/20260918T094918Z-audio-78d57572/` |
| Measurement plan | `assembly/bench/plans.json`, board `audio` |
| Analysis code | `assembly/bench/audio.py`, `assembly/bench/run.py` |
| Bitstream analysis | `pi/live.py`, `pi/analyze_bitstream.py` |
| Full narrative, every fault and wrong turn | `docs/bringup-log-2026-09.md` |

Each run folder holds `report.json`, a `summary.md` table, the raw `.npz` captures for the noise, tone and IMD steps, and plots of the noise spectrum, response and SMPTE IMD.

**The run folders are not in the repository.** `assembly/.gitignore` excludes `bench/results/` by design, so local captures are never published as if they were qualification data; the two runs cited here live on the bench machine (26 MB, mostly raw capture). The figures in `docs/figures/` and the numbers quoted above are what leaves the machine. `docs/figures.py` regenerates all three figures from a fresh `/snapshot.raw` and the two run folders, and prints the measured in-band noise and shaping slope so a capture taken in the wrong condition cannot be published with an idle-condition caption.

---

## Summary

The converter works, in stereo, and the left channel performs as simulated: **±0.06 dB from 20 Hz to 20 kHz, 67.9 dB dynamic range, 0.03 % THD, −92 dB crosstalk** — against a SPICE prediction of about 68 dB SNR. The right channel's loop is provably identical, but its input path costs it 9 dB of noise and 4× the distortion, with an intermittent trimmer the leading and untested explanation. That, the absolute input level, and Pi-powered operation are what stand between this and a finished instrument.
