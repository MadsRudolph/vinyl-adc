#!/usr/bin/env python3
"""Level-setting dashboard: set RV20 on each channel board with a record playing.

    python3 levels.py                                        # on the Pi, beside the ripper
    python3 levels.py --ripper http://vinyladc.local:8091    # from anywhere else

RV20 sets each channel's full scale, so it is a calibration rather than a property of the
converter, and it has never been set for the real source. Full scale measured on the bench is
10.41 Vpk; a phono stage delivers a fraction of a volt, which lands every rip near -23 dBFS on a
converter that only has 68 dB to give. Turning the trimmer up until the music peaks reach -6 dBFS
is worth about 13 dB of recording quality and costs one screwdriver. This page is the meter for
doing that.

It reads the ripper's /api/state rather than the capture card: the card has one reader and the
ripper owns it. Nothing about a running rip changes, and this can be started and stopped freely.

Two things this does that a plain peak meter does not:

*   **It tunes on a percentile, not the maximum.** A vinyl click runs far above the music. Trim so
    the loudest transient reaches -6 dBFS and every record ends up ten decibels too quiet. The
    number to set is the 95th percentile of the 100 ms peak buckets - the level the music actually
    keeps reaching - with the absolute maximum shown separately so clicks stay visible.

*   **It puts the ceiling at -3 dBFS, not 0.** This is a third-order delta-sigma loop, and it goes
    unstable before the arithmetic runs out: the simulation overloads at -3.1 dBFS input while
    -4.4 dBFS is still clean at 71.6 dB. Clicks above that are expected and survivable - the input
    clamp was added exactly so one click does not latch the loop - but the music must stay under.

It also holds the needle detector off while the page is open, because a record playing into the
input is precisely what tells the ripper to start recording a side.
"""
import argparse, json, math, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

TARGET, TOL, CEILING = -6., 2., -3.      # aim, how close counts as set, where the modulator gives up
FLOOR = -60.                             # below this the needle is up
PCTL = 95                                # percentile of the 100 ms peak buckets that the trim follows


def db(linear):
    """dBFS of a linear peak, where 1.0 is digital full scale (the ripper normalises to +-1)."""
    return 20. * math.log10(max(float(linear), 1e-12))


def percentile(sorted_vals, q):
    """Linear-interpolated percentile of an already-sorted list; avoids a numpy import for one number."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q / 100.
    lo = int(pos); hi = min(lo + 1, len(sorted_vals) - 1); f = pos - lo
    return sorted_vals[lo] * (1 - f) + sorted_vals[hi] * f


def verdict(music, over):
    """What to say about one channel: the words the person at the screwdriver needs."""
    if over:
        return 'over', 'Clipping — back it off'
    if music is None or music < FLOOR:
        return 'silent', 'No signal — drop the needle'
    if music > CEILING:
        return 'over', f'Too hot — back off {music - TARGET:.1f} dB'
    if music > TARGET + TOL:
        return 'hot', f'Back off {music - TARGET:.1f} dB'
    if music < TARGET - TOL:
        return 'low', f'Turn up {TARGET - music:.1f} dB'
    return 'ok', 'On target'


class Reader:
    """Polls the ripper and turns its state into the handful of numbers this page needs."""

    def __init__(self, base, window):
        self.base, self.window = base.rstrip('/'), window
        self.lock = threading.Lock()
        self.data = {'ok': False, 'error': 'connecting…', 'base': self.base}
        self.hold = True
        self.stop = threading.Event()

    def get(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.loads(r.read() or b'{}')

    def loop(self):
        last_hold = 0.
        while not self.stop.is_set():
            try:
                state = self.get('/api/state')
                # keep the needle detector off: a record playing is exactly what starts a side
                if self.hold and time.time() - last_hold > 30:
                    try:
                        self.get('/api/hold', {'seconds': 90}); last_hold = time.time()
                    except Exception:
                        pass
                with self.lock:
                    self.data = self.reduce(state)
            except urllib.error.URLError as e:
                with self.lock:
                    self.data = {'ok': False, 'base': self.base,
                                 'error': f'No answer from the ripper at {self.base} ({e.reason}). Is vinyl-adc-ripper running?'}
            except Exception as e:
                with self.lock:
                    self.data = {'ok': False, 'base': self.base, 'error': repr(e)}
            self.stop.wait(0.25)

    def reduce(self, state):
        wave = state.get('wave') or {}
        step = float(wave.get('step_s') or 0.1)
        keep = max(1, int(round(self.window / step)))
        chans = []
        history = {'step_s': step, 'left': [], 'right': []}
        for key, name in (('left', 'Left'), ('right', 'Right')):
            buckets = [float(v) for v in (wave.get(key) or [])][-keep:]
            history[key] = [round(db(v), 1) for v in buckets]
            if buckets:
                ordered = sorted(buckets)
                music = db(percentile(ordered, PCTL))
                peak = db(ordered[-1])
                over = sum(1 for v in buckets if v >= 0.999)
            else:
                music = peak = None; over = 0
            kind, says = verdict(music, over)
            chans.append({'name': name, 'music': None if music is None else round(music, 1),
                          'max': None if peak is None else round(peak, 1),
                          'over': over, 'verdict': kind, 'says': says,
                          'delta': None if music is None or music < FLOOR else round(TARGET - music, 1)})
        meters = state.get('meters') or {}
        live = [round(float(v), 1) for v in (meters.get('peak_db') or [])] or None
        both = [c['music'] for c in chans]
        balance = round(both[0] - both[1], 1) if all(v is not None and v > FLOOR for v in both) else None
        return {'ok': True, 'base': self.base, 'status': state.get('status'), 'message': state.get('message') or '',
                'hold': round(float(state.get('hold') or 0.), 1), 'holding': self.hold,
                'mode': meters.get('mode'), 'live': live, 'window_s': self.window,
                'samples': len(history['left']), 'ch': chans, 'balance': balance,
                'target': TARGET, 'tol': TOL, 'ceiling': CEILING, 'floor': FLOOR, 'pctl': PCTL,
                'history': history}


def make_handler(reader):
    page = (Path(__file__).with_name('levels.html')).read_bytes

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, body, ctype='application/json', code=200):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code); self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if self.path == '/':
                return self.reply(page(), 'text/html; charset=utf-8')
            if self.path.startswith('/api/levels'):
                with reader.lock:
                    return self.reply(reader.data)
            self.reply({'error': 'not found'}, code=404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
            if self.path == '/api/holding':
                reader.hold = bool(body.get('on'))
                if not reader.hold:
                    try:
                        reader.get('/api/hold', {'seconds': 0})      # release it now rather than waiting it out
                    except Exception:
                        pass
                return self.reply({'ok': True, 'holding': reader.hold})
            if self.path == '/api/window':
                reader.window = max(5., min(60., float(body.get('seconds', 30))))
                return self.reply({'ok': True, 'window_s': reader.window})
            self.reply({'error': 'not found'}, code=404)

    return H


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--port', type=int, default=8092)
    p.add_argument('--ripper', default='http://127.0.0.1:8091')
    p.add_argument('--window', type=float, default=30., help='seconds of peak history the trim follows')
    a = p.parse_args()
    reader = Reader(a.ripper, a.window)
    threading.Thread(target=reader.loop, daemon=True).start()
    print(f'Level dashboard on http://0.0.0.0:{a.port}  (reading {a.ripper})')
    try:
        ThreadingHTTPServer(('0.0.0.0', a.port), make_handler(reader)).serve_forever()
    except KeyboardInterrupt:
        reader.stop.set()
        try:
            reader.get('/api/hold', {'seconds': 0})                  # never leave the ripper held off
        except Exception:
            pass
        print('\nhold released, bye')


if __name__ == '__main__':
    main()
