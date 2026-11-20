/* vinyl-stream: low-latency live output of the Vinyl ADC.

   Captures the ADC's I2S words (the same `hw:CARD=vinyladc`, 2 x S32_LE, 48 kHz that arecord read),
   and does two things with every period of about 2.7 ms:

     1. writes the raw words unchanged to stdout, so the ripper reads exactly what arecord gave it;
     2. de-interleaves the two 1-bit modulator streams, decimates them to 48 kHz with the ripper's
        filter (4th-order CIC /8, then the 161-tap compensating FIR /4, see decimate.py), removes DC,
        and sends the audio as RTP (L24, 48 kHz, stereo, 1 ms packets) to --dest.

   On a PC running PipeWire, libpipewire-module-rtp-source turns the stream into an input device
   ("Vinyl ADC") that any DAW can record (stream/pc/vinyl-adc-rtp.conf).

   Build:  make -C stream            (needs libasound2-dev)
   Usage:  vinyl-stream --dest 192.168.50.153:46000            # ripper mode: raw words on stdout
           vinyl-stream --dest HOST:PORT --no-raw              # stream only
           vinyl-stream --replay capture.raw --pcm-out out.f32 --no-raw   # offline test, no ALSA, no network
*/
#define _GNU_SOURCE
#include <alsa/asoundlib.h>
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <netdb.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include "fir_taps.h"

#define CIC_ORDER 4
#define CIC_R 8
#define FIR_R 4
#define CIC_GAIN 4096.0            /* CIC_R ** CIC_ORDER */
#define RATE 48000
#define PACKET_FRAMES 48           /* 1 ms of audio per RTP packet (AES67 default packet time) */
#define RTP_PT 96

typedef struct {
    uint32_t integ[CIC_ORDER], comb[CIC_ORDER];   /* unsigned: Hogenauer wrap-around is exact modulo 2^32 */
    int cic_phase;
    double hist[2 * FIR_TAPS];                    /* FIR input, written twice so the newest FIR_TAPS are contiguous */
    int hpos;
    long fir_count;
    double hp_x, hp_y;                            /* DC blocker state */
} chan_t;

static double hp_a;

/* one modulator bit (+1/-1) in; returns 1 and sets *out when a 48 kHz sample is ready */
static inline int chan_push(chan_t *c, int v, double *out)
{
    uint32_t x = (uint32_t)v;
    c->integ[0] += x; c->integ[1] += c->integ[0]; c->integ[2] += c->integ[1]; c->integ[3] += c->integ[2];
    if (++c->cic_phase < CIC_R) return 0;
    c->cic_phase = 0;
    uint32_t y = c->integ[3];
    for (int k = 0; k < CIC_ORDER; k++) { uint32_t t = y; y = y - c->comb[k]; c->comb[k] = t; }
    double s = (double)(int32_t)y / CIC_GAIN;     /* 192 kHz, full scale +-1 */

    c->hpos = (c->hpos == 0) ? FIR_TAPS - 1 : c->hpos - 1;
    c->hist[c->hpos] = c->hist[c->hpos + FIR_TAPS] = s;
    long n = c->fir_count++;
    if (n % FIR_R) return 0;
    const double *x0 = &c->hist[c->hpos];         /* x0[j] = x[n - j] */
    double acc = 0;
    for (int j = 0; j < FIR_TAPS; j++) acc += fir_h[j] * x0[j];
    double o = acc - c->hp_x + hp_a * c->hp_y;    /* 1-pole high-pass, ~2 Hz: the ripper removes DC too */
    c->hp_x = acc; c->hp_y = o;
    *out = o;
    return 1;
}

static int write_all(int fd, const void *buf, size_t n)
{
    const char *p = buf;
    while (n) {
        ssize_t w = write(fd, p, n);
        if (w < 0) { if (errno == EINTR) continue; return -1; }
        p += w; n -= (size_t)w;
    }
    return 0;
}

static void usage(void)
{
    fprintf(stderr, "usage: vinyl-stream [--dest HOST:PORT] [--device NAME] [--period FRAMES] [--no-raw]\n"
                    "                    [--replay FILE] [--pcm-out FILE] [--gain-db DB]\n");
    exit(2);
}

int main(int argc, char **argv)
{
    const char *device = "hw:CARD=vinyladc", *dest = NULL, *replay = NULL, *pcm_out = NULL;
    int period = 128, raw = 1;
    double gain = 1.0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--dest") && i + 1 < argc) dest = argv[++i];
        else if (!strcmp(argv[i], "--device") && i + 1 < argc) device = argv[++i];
        else if (!strcmp(argv[i], "--period") && i + 1 < argc) period = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--replay") && i + 1 < argc) replay = argv[++i];
        else if (!strcmp(argv[i], "--pcm-out") && i + 1 < argc) pcm_out = argv[++i];
        else if (!strcmp(argv[i], "--gain-db") && i + 1 < argc) gain = pow(10, atof(argv[++i]) / 20);
        else if (!strcmp(argv[i], "--no-raw")) raw = 0;
        else usage();
    }
    if (period < 16 || period > 4800) usage();
    signal(SIGPIPE, SIG_IGN);
    hp_a = 1.0 - 2 * M_PI * 2.0 / RATE;

    /* the ripper reads 0.5 s blocks and then spends ~0.25 s decimating: give the pipe room for that */
    if (raw) fcntl(1, F_SETPIPE_SZ, 1 << 20);

    int sock = -1;
    struct sockaddr_storage to; socklen_t tolen = 0;
    if (dest) {
        char host[256]; const char *colon = strrchr(dest, ':');
        if (!colon || colon == dest || (size_t)(colon - dest) >= sizeof host) { fprintf(stderr, "--dest must be HOST:PORT\n"); return 2; }
        memcpy(host, dest, (size_t)(colon - dest)); host[colon - dest] = 0;
        struct addrinfo hints = {.ai_family = AF_UNSPEC, .ai_socktype = SOCK_DGRAM}, *ai;
        int e = getaddrinfo(host, colon + 1, &hints, &ai);
        if (e) { fprintf(stderr, "vinyl-stream: %s: %s\n", dest, gai_strerror(e)); return 1; }
        memcpy(&to, ai->ai_addr, ai->ai_addrlen); tolen = ai->ai_addrlen;
        sock = socket(ai->ai_family, SOCK_DGRAM, 0);
        freeaddrinfo(ai);
        if (sock < 0) { perror("vinyl-stream: socket"); return 1; }
        int tos = 0xb8;                           /* DSCP EF, as AES67 senders do */
        setsockopt(sock, IPPROTO_IP, IP_TOS, &tos, sizeof tos);
    }
    FILE *pcm = pcm_out ? fopen(pcm_out, "wb") : NULL;
    if (pcm_out && !pcm) { perror(pcm_out); return 1; }

    snd_pcm_t *h = NULL; FILE *rf = NULL;
    if (replay) {
        if (!(rf = fopen(replay, "rb"))) { perror(replay); return 1; }
    } else {
        int e;
        if ((e = snd_pcm_open(&h, device, SND_PCM_STREAM_CAPTURE, 0)) < 0) { fprintf(stderr, "vinyl-stream: %s: %s\n", device, snd_strerror(e)); return 1; }
        snd_pcm_hw_params_t *hw; snd_pcm_hw_params_alloca(&hw);
        snd_pcm_hw_params_any(h, hw);
        unsigned rate = RATE; snd_pcm_uframes_t per = (snd_pcm_uframes_t)period, buf = RATE;  /* 1 s of slack */
        if ((e = snd_pcm_hw_params_set_access(h, hw, SND_PCM_ACCESS_RW_INTERLEAVED)) < 0 ||
            (e = snd_pcm_hw_params_set_format(h, hw, SND_PCM_FORMAT_S32_LE)) < 0 ||
            (e = snd_pcm_hw_params_set_channels(h, hw, 2)) < 0 ||
            (e = snd_pcm_hw_params_set_rate_near(h, hw, &rate, 0)) < 0 ||
            (e = snd_pcm_hw_params_set_period_size_near(h, hw, &per, 0)) < 0 ||
            (e = snd_pcm_hw_params_set_buffer_size_near(h, hw, &buf)) < 0 ||
            (e = snd_pcm_hw_params(h, hw)) < 0) { fprintf(stderr, "vinyl-stream: hw params: %s\n", snd_strerror(e)); return 1; }
        period = (int)per;
        fprintf(stderr, "vinyl-stream: %s, %u Hz, period %d frames (%.2f ms), buffer %lu%s%s\n", device, rate, period,
                1000.0 * period / rate, (unsigned long)buf, dest ? ", RTP to " : "", dest ? dest : "");
    }

    uint32_t *words = malloc((size_t)period * 8);
    static chan_t ch[2];
    uint8_t pkt[12 + PACKET_FRAMES * 6];
    float fbuf[2 * 4800];
    int pf = 0;
    uint16_t seq = (uint16_t)rand(); uint32_t ts = 0;
    srand((unsigned)time(NULL) ^ (unsigned)getpid());
    uint32_t ssrc = ((uint32_t)rand() << 16) ^ (uint32_t)rand();
    long overruns = 0;

    for (;;) {
        long got;
        if (rf) {
            got = (long)(fread(words, 8, (size_t)period, rf));
            if (got <= 0) break;
        } else {
            got = snd_pcm_readi(h, words, (snd_pcm_uframes_t)period);
            if (got == -EPIPE) { overruns++; fprintf(stderr, "vinyl-stream: overrun %ld\n", overruns); snd_pcm_prepare(h); continue; }
            if (got < 0) { fprintf(stderr, "vinyl-stream: read: %s\n", snd_strerror((int)got)); return 1; }   /* no clocks: the ripper restarts us */
        }
        if (raw && write_all(1, words, (size_t)got * 8)) return 0;     /* the ripper went away */

        int nout = 0;
        for (long f = 0; f < got; f++) {
            uint32_t w[2] = {words[2 * f], words[2 * f + 1]};
            double o;
            /* frame = left word then right word, MSB first on the wire; even bit positions are the left modulator */
            for (int wi = 0; wi < 2; wi++)
                for (int b = 31; b >= 1; b -= 2) {
                    if (chan_push(&ch[0], ((w[wi] >> b) & 1) ? 1 : -1, &o)) fbuf[2 * nout] = (float)(o * gain);
                    if (chan_push(&ch[1], ((w[wi] >> (b - 1)) & 1) ? 1 : -1, &o)) fbuf[2 * nout++ + 1] = (float)(o * gain);
                }
        }
        if (pcm) fwrite(fbuf, sizeof(float), (size_t)nout * 2, pcm);
        if (sock < 0) continue;
        for (int i = 0; i < nout; i++) {
            for (int c = 0; c < 2; c++) {
                double v = fbuf[2 * i + c] * 8388607.0;
                int32_t s = v > 8388607 ? 8388607 : v < -8388608 ? -8388608 : (int32_t)lrint(v);
                uint8_t *p = &pkt[12 + pf * 6 + c * 3];
                p[0] = (uint8_t)(s >> 16); p[1] = (uint8_t)(s >> 8); p[2] = (uint8_t)s;
            }
            if (++pf == PACKET_FRAMES) {
                pkt[0] = 0x80; pkt[1] = RTP_PT;
                pkt[2] = (uint8_t)(seq >> 8); pkt[3] = (uint8_t)seq;
                pkt[4] = (uint8_t)(ts >> 24); pkt[5] = (uint8_t)(ts >> 16); pkt[6] = (uint8_t)(ts >> 8); pkt[7] = (uint8_t)ts;
                pkt[8] = (uint8_t)(ssrc >> 24); pkt[9] = (uint8_t)(ssrc >> 16); pkt[10] = (uint8_t)(ssrc >> 8); pkt[11] = (uint8_t)ssrc;
                sendto(sock, pkt, sizeof pkt, MSG_DONTWAIT, (struct sockaddr *)&to, tolen);   /* PC off or busy: drop, never stall capture */
                seq++; ts += PACKET_FRAMES; pf = 0;
            }
        }
    }
    if (pcm) fclose(pcm);
    return 0;
}
