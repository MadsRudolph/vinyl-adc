#!/usr/bin/env python3
"""Bench card for the two underside supply wires on the channel boards.

Reads assembly/generated/boards.json (the KiCad snapshot) and draws the channel
board as seen from BELOW, with the two wires that take the +5 V and -5 V rails
off their single component-side joints at the bus header.

    python3 assembly/underside_wires.py        # -> docs/underside-wires.html
"""
from pathlib import Path
import json, math

ROOT = Path(__file__).resolve().parents[1]
BOARD = json.loads((ROOT / 'assembly/generated/boards.json').read_text())['boards']['channel_l']
OUT = ROOT / 'docs/underside-wires.html'

PADS = {(p['ref'], p['pin']): p for part in BOARD['parts'] for p in part['pads']}
X0, Y0, W, H = BOARD['bounds']
MIRROR = 2 * X0 + W            # x' = MIRROR - x  (the view flips left/right)

def mx(x): return round(MIRROR - x, 3)

def at(ref, pin):
    a = PADS[(ref, pin)]['at']
    return (mx(a[0]), a[1])

def span(a, b):
    (x1, y1), (x2, y2) = at(*a), at(*b)
    return math.hypot(x1 - x2, y1 - y2)

# The two joints that carry a whole rail through one pin of the stacking header.
WIRES = [
    dict(net='-5V', frm=('J7', '16'), to=('U22', '4'), colour='var(--wire-neg)',
         why='The entire negative rail enters here. Its only copper is a component-side trace to U22 pin 4, '
             'reached through an unplated hole under the header body, and the stack flexes that joint every time '
             'it is pushed together.'),
    dict(net='+5V', frm=('J7', '2'), to=('U23', '14'), colour='var(--wire-pos)',
         why='The same arrangement on the positive rail: one component-side joint feeds U21, C27 and R37. '
             'It has not failed yet, and it is the same joint.'),
]
for w in WIRES:
    w['mm'] = span(w['frm'], w['to'])

def svg(highlight=None):
    o = []
    o.append(f'<svg viewBox="{X0-9} {Y0-9} {W+18} {H+22}" role="img" '
             f'aria-label="Channel board seen from below">')
    # board
    o.append(f'<rect x="{X0}" y="{Y0}" width="{W}" height="{H}" rx="2.5" '
             f'fill="var(--fr4)" stroke="var(--edge)" stroke-width="0.6"/>')
    # bottom copper: bare on a milled board, so an uninsulated wire would short to it
    o.append('<g stroke="var(--copper)" stroke-width="0.85" stroke-linecap="round" opacity="0.5" fill="none">')
    for t in BOARD['tracks']:
        if t['layer'] != 'bottom': continue
        o.append(f'<path d="M{mx(t["a"][0])} {t["a"][1]} L{mx(t["b"][0])} {t["b"][1]}"/>')
    o.append('</g>')
    # the top-side runs these wires replace, dashed
    for w in WIRES:
        for t in BOARD['tracks']:
            if t['layer'] == 'top' and t['net'] == w['net']:
                o.append(f'<path d="M{mx(t["a"][0])} {t["a"][1]} L{mx(t["b"][0])} {t["b"][1]}" '
                         f'stroke="{w["colour"]}" stroke-width="0.7" opacity="0.32" '
                         f'stroke-dasharray="1.6 1.4" fill="none"/>')
    # pads
    o.append('<g fill="var(--pad)">')
    for p in PADS.values():
        x, y = mx(p['at'][0]), p['at'][1]
        o.append(f'<circle cx="{x}" cy="{y}" r="0.82"/>')
    o.append('</g><g fill="var(--fr4)">')
    for p in PADS.values():
        x, y = mx(p['at'][0]), p['at'][1]
        o.append(f'<circle cx="{x}" cy="{y}" r="0.4"/>')
    o.append('</g>')
    # mounting holes
    for ref in ('H1', 'H2', 'H3', 'H4'):
        part = next(p for p in BOARD['parts'] if p['ref'] == ref)
        x, y = mx(part['at'][0]), part['at'][1]
        o.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="none" stroke="var(--edge)" stroke-width="0.4"/>')
    # part designators
    o.append('<g class="ref">')
    for part in BOARD['parts']:
        if part['kind'] not in ('socket', 'connector') or part['ref'].startswith('H'): continue
        xs = [mx(p['at'][0]) for p in part['pads']]
        ys = [p['at'][1] for p in part['pads']]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        o.append(f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="central">{part["ref"]}</text>')
    o.append('</g>')
    if highlight:
        # every pad and trace of one net, plus the ground pads that sit closest to it
        for t in BOARD['tracks']:
            if t['net'] != highlight: continue
            o.append(f'<path d="M{mx(t["a"][0])} {t["a"][1]} L{mx(t["b"][0])} {t["b"][1]}" '
                     f'stroke="var(--bad)" stroke-width="1.5" fill="none" stroke-linecap="round" '
                     f'opacity="{0.95 if t["layer"]=="bottom" else 0.4}" '
                     f'{"" if t["layer"]=="bottom" else chr(115)+"troke-dasharray=\"1.6 1.2\""}/>')
        for p in PADS.values():
            if p['net'] != highlight: continue
            x, y = mx(p['at'][0]), p['at'][1]
            o.append(f'<circle cx="{x}" cy="{y}" r="2.2" fill="none" stroke="var(--bad)" stroke-width="0.8"/>')
            o.append(f'<text class="callout" x="{x}" y="{y-3.6:.2f}" text-anchor="middle" '
                     f'fill="var(--bad)">{p["ref"]}.{p["pin"]}</text>')
        return '\n'.join(o + ['</svg>'])

    # the wires
    for w in WIRES:
        (x1, y1), (x2, y2) = at(*w['frm']), at(*w['to'])
        o.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{w["colour"]}" stroke-width="1.9" '
                 f'stroke-linecap="round" fill="none" opacity="0.92"/>')
        for (x, y), (ref, pin) in (((x1, y1), w['frm']), ((x2, y2), w['to'])):
            o.append(f'<circle cx="{x}" cy="{y}" r="2.4" fill="none" stroke="{w["colour"]}" stroke-width="0.7"/>')
    # endpoint labels, placed clear of the board's busy middle
    labels = [(WIRES[0]['frm'], 'above', WIRES[0]['colour']), (WIRES[0]['to'], 'below', WIRES[0]['colour']),
              (WIRES[1]['frm'], 'above', WIRES[1]['colour']), (WIRES[1]['to'], 'right', WIRES[1]['colour'])]
    off = {'above': (0, -4.2), 'below': (0, 5.4), 'left': (-4.4, 1.2), 'right': (4.4, 1.2)}
    anchor = {'above': 'middle', 'below': 'middle', 'left': 'end', 'right': 'start'}
    for (ref, pin), where, colour in labels:
        x, y = at(ref, pin)
        dx, dy = off[where]
        o.append(f'<text class="callout" x="{x+dx:.2f}" y="{y+dy:.2f}" text-anchor="{anchor[where]}" '
                 f'fill="{colour}">{ref}.{pin}</text>')
    # edge orientation cues
    o.append(f'<text class="edge" x="{X0+W/2}" y="{Y0-3.4}" text-anchor="middle">bus header J7 — this edge plugs into the stack</text>')
    o.append(f'<text class="edge" x="{X0+W/2}" y="{Y0+H+6.4}" text-anchor="middle">'
             f'viewed from the solder side &#8212; LINE IN is at the far left</text>')
    o.append('</svg>')
    return '\n'.join(o)

STYLE = """
:root{
  color-scheme:dark;
  --bg:#0e1413; --panel:#19211f; --panel-2:#141c1a; --line:#2c3833; --line-soft:#212b28;
  --text:#e8efe7; --text-2:#b6c6bb; --muted:#8fa298;
  --accent:#bef58b; --amber:#ffc477;
  --fr4:#1b2522; --copper:#c08f5c; --pad:#c9a678; --edge:#3c4b45;
  --wire-neg:#ffc477; --wire-pos:#79cfe4;
  --ok:#8fd46a; --bad:#e8734d;
  --xsub:#2e2a24; --xmetal:#aab6b1; --xbody:#34383a; --xsolder:#8d979b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.55}
code,.mono,.ref,.callout,.edge{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
.wrap{max-width:1180px;margin:0 auto;padding-block:26px 56px;padding-left:20px;padding-right:20px}

header.top{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:26px}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:2.4px;text-transform:uppercase;
  color:var(--muted);margin:0 0 10px}
h1{font-size:clamp(25px,4.4vw,36px);font-weight:600;letter-spacing:-0.7px;margin:0 0 8px;text-wrap:balance}
.standfirst{color:var(--text-2);max-width:66ch;margin:0}

.layout{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:28px;align-items:start}
@media(max-width:900px){.layout{grid-template-columns:1fr}}

figure.board{margin:0;background:var(--panel-2);border:1px solid var(--line);border-radius:12px;padding:14px}
figure.board svg{display:block;width:100%;height:auto;max-width:100%}
svg .ref{font-size:2.5px;fill:var(--muted)}
svg .callout{font-size:3.6px;font-weight:600;paint-order:stroke;stroke:var(--fr4);stroke-width:1px;stroke-linejoin:round}
svg .edge{font-size:2.9px;fill:var(--muted)}
figcaption{color:var(--muted);font-size:12.5px;margin-top:10px;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.key{display:inline-flex;align-items:center;gap:6px}
.key i{width:16px;height:3px;border-radius:2px;display:inline-block}
.key i.dash{background:none;border-top:2px dashed var(--wire-neg);height:0}

h2{font-size:17px;font-weight:600;margin:0 0 6px;letter-spacing:-0.2px}
h2 .n{font-family:"IBM Plex Mono",monospace;color:var(--accent);margin-right:8px;font-size:15px}
section+section{margin-top:26px}
p{margin:0 0 12px;max-width:66ch}

.wires{display:grid;gap:12px;margin:0 0 22px}
.wire{border:1px solid var(--line);border-left:3px solid var(--w);border-radius:9px;padding:13px 15px;background:var(--panel)}
.wire h3{margin:0 0 4px;font-size:15px;font-weight:600;display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.wire .path{font-family:"IBM Plex Mono",monospace;color:var(--w);font-size:15px}
.wire .len{margin-left:auto;color:var(--muted);font-size:12.5px;font-variant-numeric:tabular-nums}
.wire p{margin:0;color:var(--text-2);font-size:13.5px}

ol.steps{list-style:none;counter-reset:s;margin:0;padding:0}
ol.steps li{counter-increment:s;position:relative;padding:0 0 14px 34px;margin:0}
ol.steps li::before{content:counter(s);position:absolute;left:0;top:1px;width:22px;height:22px;border-radius:6px;
  background:var(--panel);border:1px solid var(--line);color:var(--accent);
  font-family:"IBM Plex Mono",monospace;font-size:12px;display:grid;place-items:center}
ol.steps li strong{font-weight:600}
ol.steps li span{display:block;color:var(--text-2);font-size:13.5px;margin-top:2px}

.warn{background:#2a2113;border:1px solid #6b5031;border-left:3px solid var(--amber);border-radius:9px;
  padding:14px 16px;margin:0 0 20px}
.warn strong{color:var(--amber);display:block;margin-bottom:4px}
p.aside{color:var(--text-2);font-size:13.5px;border-left:2px solid var(--line);padding-left:13px;margin:0 0 16px}
ol.steps+p.aside{margin-top:6px}
.warn p{color:#f3ddb6;margin:0;font-size:13.5px}
figure.xsec{margin:18px 0 0;background:var(--panel-2);border:1px solid var(--line);border-radius:12px;padding:16px 16px 12px;max-width:820px}
figure.xsec svg{display:block;width:100%;height:auto}
svg .xl{font-family:"IBM Plex Mono",monospace;font-size:6px}
section.why h2{margin-bottom:10px}

table{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line-soft)}
th{color:var(--muted);font-weight:500;font-size:12px;letter-spacing:0.4px;text-transform:uppercase}
td.num{text-align:right}
.ok{color:var(--ok)}.bad{color:var(--bad)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}

pre.cmd{background:var(--panel-2);border:1px solid var(--line);border-radius:8px;padding:12px 14px;
  font-family:"IBM Plex Mono",monospace;font-size:13px;overflow-x:auto;margin:0 0 12px;color:var(--text-2)}
pre.cmd b{color:var(--accent);font-weight:400}

footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
footer code{color:var(--text-2)}
"""

def crosssection():
    """A section through bus pin J7.16, at ten units per millimetre.

    Drill 1.0 mm, pin 0.64 mm square, pad 1.7 mm, board 1.6 mm: the numbers are
    the footprint's own, so the 0.1 mm gap the solder has to wick up is to scale.
    """
    o = ['<svg viewBox="-12 36 320 120" role="img" aria-label="Section through bus pin J7.16 '
         'showing the unplated hole, the component-side trace and the new wire">']
    o.append('<rect x="92" y="56" width="58" height="30" rx="2" fill="var(--xbody)"/>')
    o.append('<text class="xl" x="121" y="50" text-anchor="middle" fill="var(--muted)">'
             'bus header body &#8212; it covers the pads</text>')
    # substrate, drilled through
    o.append('<rect x="-8" y="90" width="113" height="16" fill="var(--xsub)"/>')
    o.append('<rect x="115" y="90" width="185" height="16" fill="var(--xsub)"/>')
    # copper: component side carries the ring and the trace, solder side only an island
    o.append('<rect x="101.5" y="86" width="3.5" height="4" fill="var(--copper)"/>')
    o.append('<rect x="115" y="86" width="185" height="4" fill="var(--copper)"/>')
    o.append('<rect x="101.5" y="106" width="3.5" height="4" fill="var(--copper)"/>')
    o.append('<rect x="115" y="106" width="3.5" height="4" fill="var(--copper)"/>')
    # the pin, and the solder that has to wick the full 1.6 mm to reach the trace
    o.append('<rect x="106.8" y="60" width="6.4" height="52" fill="var(--xmetal)"/>')
    o.append('<rect x="105" y="86" width="1.8" height="20" fill="var(--bad)" opacity="0.85"/>')
    o.append('<rect x="113.2" y="86" width="1.8" height="20" fill="var(--bad)" opacity="0.85"/>')
    # the new joint, on the face that is reachable
    o.append('<ellipse cx="110" cy="111" rx="9" ry="5" fill="var(--xsolder)"/>')
    o.append('<path d="M110 113 L72 121 L-10 121" stroke="var(--wire-neg)" stroke-width="3.4" '
             'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    # annotation
    # the gap is drawn to scale, so ring it or the eye never finds it
    o.append('<rect x="102.6" y="83" width="14.8" height="26" rx="2.5" fill="none" '
             'stroke="var(--bad)" stroke-width="0.7" opacity="0.65"/>')
    o.append('<text class="xl" x="298" y="80" text-anchor="end" fill="var(--muted)">top copper &#8594; U22.4</text>')
    o.append('<text class="xl" x="30" y="134" text-anchor="middle" fill="var(--wire-neg)">the new wire &#8594; U22.4</text>')
    o.append('<path d="M170 131 L136 114 L118 109.5" stroke="var(--bad)" stroke-width="0.8" fill="none" opacity="0.75"/>')
    o.append('<text class="xl" x="205" y="134" text-anchor="middle" fill="var(--bad)">the hole is unplated:</text>')
    o.append('<text class="xl" x="205" y="143" text-anchor="middle" fill="var(--bad)">only wicked solder joins pin to trace</text>')
    o.append('</svg>')
    return '\n'.join(o)

def html():
    wires = '\n'.join(
        f'''<div class="wire" style="--w:{w['colour']}">
  <h3><span class="path">{w['frm'][0]}.{w['frm'][1]} &rarr; {w['to'][0]}.{w['to'][1]}</span>
      <span class="len">{w['net']} &middot; {w['mm']:.0f} mm apart</span></h3>
  <p>{w['why']}</p>
</div>''' for w in WIRES)

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Underside Supply Wires</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{STYLE}</style></head>
<body><div class="wrap">

<header class="top">
  <p class="eyebrow">Vinyl ADC &middot; channel board &middot; open item 1</p>
  <h1>Take both rails off their single header joint</h1>
  <p class="standfirst">The right channel's loop is not wrong. Its negative rail arrives through solder that has
  wicked up one unplated hole at bus pin J7.16 &mdash; under the header body, where no iron reaches &mdash; and
  that joint lets go when the stack is pressed together. Two insulated wires on the solder side make both rails
  independent of it &mdash; on <strong>both</strong> channel boards, four wires in all.</p>
</header>

<div class="layout">
  <figure class="board">
    {svg()}
    <figcaption>
      <span class="key"><i style="background:var(--wire-neg)"></i>&minus;5 V wire</span>
      <span class="key"><i style="background:var(--wire-pos)"></i>+5 V wire</span>
      <span class="key"><i class="dash"></i>the top-side run it bypasses</span>
      <span class="key"><i style="background:var(--copper)"></i>bottom copper</span>
    </figcaption>
  </figure>

  <div>
    <section>
      <h2><span class="n">01</span>The two wires</h2>
      <div class="wires">{wires}</div>
    </section>

    <section>
      <div class="warn">
        <strong>The whole solder side is a bare ground pour</strong>
        <p>These boards are milled, so there is no solder mask: an uninsulated wire lying across the underside
        shorts the rail it carries straight to ground. Use insulated wire &mdash; 30 AWG Kynar or any thin
        stranded hook-up wire &mdash; and strip only the last 2 mm at each end.</p>
      </div>

      <h2><span class="n">02</span>Fitting them</h2>
      <p class="aside">With the bus header off the board, these pads are completely clear &mdash; this is the
      easiest moment to do it, so fit the wires before the header goes back.</p>
      <ol class="steps">
        <li><strong>Work on the board alone, solder side up.</strong>
            <span>If the header is still fitted, unplug the board from the stack and leave the header in place;
            the pads are reachable from below either way.</span></li>
        <li><strong>Cut the &minus;5 V wire about 60 mm long, the +5 V wire about 30 mm.</strong>
            <span>Straight-line spans are {WIRES[0]['mm']:.0f} mm and {WIRES[1]['mm']:.0f} mm; the extra is slack for routing.</span></li>
        <li><strong>Tin the four pads and both wire ends first.</strong>
            <span>The header pins take heat well from below; the socket pins need a moment longer.</span></li>
        <li><strong>Solder the &minus;5 V wire: J7 pin 16 to U22 pin 4.</strong>
            <span>In the view at left, J7 pin 16 is the corner pin at the right-hand end of the header's inner row.</span></li>
        <li><strong>Solder the +5 V wire: J7 pin 2 to U23 pin 14.</strong>
            <span>U23 pin 14 is the corner of the 74HC74 nearest the header.</span></li>
        <li><strong>Press the wires flat and tack them down.</strong>
            <span>They must not stand proud enough to touch the neighbouring board in the stack.</span></li>
        <li><strong>If the header came off, refit it and solder all 16 pins from the solder side only.</strong>
            <span>Check the sixteen copper rings on the solder side first &mdash; a ring that lifted during
            desoldering breaks whatever it fed, and pins 4 to 14 each carry a reference or a clock.</span></li>
        <li><strong>Repeat all of it on the other channel board.</strong></li>
      </ol>
      <p class="aside"><strong>Nothing on this header needs soldering on the component side once the wires are in.</strong>
      Fourteen of the sixteen pins never did: the eight ground pins meet the pour, and pins 4, 6, 8, 10, 12 and 14
      each reach their destination through bottom copper. Only pins 2 and 16 were carried by a top-side joint, and
      that is what the two wires replace.</p>
    </section>
  </div>
</div>

<section class="why">
  <p class="eyebrow">Why a wire, when the trace is already there</p>
  <h2>The trace was never the problem</h2>
  <p>Copper is copper: the run from J7.16 to U22.4 carries the rail perfectly well. The question is how the
  current gets from the header pin into that copper at all &mdash; and on this board there is only one answer,
  and it is a bad one.</p>
  <p>These holes are drilled, not plated. Nothing joins the two faces of the board. The solder-side ring at
  J7.16 is an island connected to nothing, and the trace leaves from the component-side ring, which the header
  body covers: the body outline clears the pad by 0.42 mm, so once the header is seated there is no reaching
  that joint with an iron. What has been carrying the negative rail all along is solder that wicked 1.6 mm up
  the 0.1 mm gap between the pin and the hole wall &mdash; invisible, unverifiable, and squeezed every time the
  stack is pressed together. That is why reflowing pin 16 from below never held: it was reflowing a joint it
  could not see.</p>
  <figure class="xsec">
    {crosssection()}
    <figcaption>A section through J7.16, drawn to the footprint's own dimensions. The wire does not replace the
    trace &mdash; it replaces the wicked solder, giving the pin a second route into the board on the one face an
    iron can reach.</figcaption>
  </figure>
  <p>Bridging the pin to the trace on the component side would be electrically sound, and it would still need a
  joint on that pin, on that face, under that body, taking that same flex &mdash; and whatever you leave standing
  up there is what the next board in the stack presses against.</p>
</section>

<section class="why">
  <p class="eyebrow">18 September &middot; hunting the DACP_L short</p>
  <h2>Where a short to ground can hide on this net</h2>
  <p>With U24 out of its socket, socket pin 4 still reads short to ground, so the fault is in the board's own
  copper. DACP_L is only three pads and two runs, but the solder-side half is about 45 mm of bare trace with the
  ground pour 0.5 mm away along both edges and no mask in between. Solid red is solder-side copper, dashed is
  component-side.</p>
  <figure class="board" style="max-width:640px">
    {svg('DACP_L')}
    <figcaption>DACP_L on the solder-side view: U24.4 &rarr; R25.1 on the component side, R25.1 &rarr; R34.1 underneath.</figcaption>
  </figure>
  <p>Search in this order: <strong>U24 pins 4 and 5</strong> first &mdash; they are adjacent and pin 5 is ground,
  so one bridge does it, and the socket's own contacts count too. Then <strong>R25.1</strong>, where the
  component-side run meets the solder-side trace. Then the trace itself, following it up to
  <strong>R34.1</strong>. A whisker across 0.5 mm of bare copper is the likeliest thing you will find.</p>
</section>

<section>
  <h2><span class="n">03</span>Before it goes back in the stack</h2>
  <p>Meter on resistance, board still unplugged. The first two confirm the wires do something; the last two
  confirm they did not do something else.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Between</th><th>Expect</th><th>Means</th></tr></thead>
    <tbody>
      <tr><td class="mono">J7.16 &harr; U22.4</td><td class="ok">near 0 &#8486;</td><td>the negative rail no longer depends on the top joint</td></tr>
      <tr><td class="mono">J7.2 &harr; U23.14</td><td class="ok">near 0 &#8486;</td><td>same for the positive rail</td></tr>
      <tr><td class="mono">J7.16 &harr; J7.15 (GND)</td><td class="bad">not 0 &#8486;</td><td>the &minus;5 V wire is not touching the pour</td></tr>
      <tr><td class="mono">J7.2 &harr; J7.1 (GND)</td><td class="bad">not 0 &#8486;</td><td>the +5 V wire is not touching the pour</td></tr>
      <tr><td class="mono">J7.2 &harr; J7.16</td><td class="bad">not 0 &#8486;</td><td>the two rails are not bridged to each other</td></tr>
    </tbody>
  </table></div>
</section>

<section>
  <h2><span class="n">04</span>Then ask the bitstream</h2>
  <p>Boot the Pi first, then power the ADC. Stop the ripper so it releases the capture card, and run the live view
  on the same port:</p>
  <pre class="cmd">ssh mads@vinyladc.local
sudo systemctl stop vinyl-adc-ripper
python3 ~/pi/live.py          <b># then open http://vinyladc.local:8091</b></pre>
  <p>The right channel should stop looking like the middle column and start looking like the left one. Mean run
  length is the quickest tell &mdash; a limit cycle shows as long solid bars in the bit view.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Reading</th><th class="num">Left, healthy</th><th class="num">Right, faulty</th><th>What it means</th></tr></thead>
    <tbody>
      <tr><td>Mean run of identical bits</td><td class="num ok">1.35</td><td class="num bad">18.5&ndash;19.5</td><td>a rail-to-rail oscillation near 41&ndash;45 kHz</td></tr>
      <tr><td>One-density, no input</td><td class="num ok">0.496</td><td class="num bad">0.56&ndash;0.57</td><td>the loop is overloaded, not modulating</td></tr>
      <tr><td>Shaping, 30&rarr;80 kHz</td><td class="num ok">+69 dB/dec</td><td class="num bad">flat</td><td>third order, versus no shaping at all</td></tr>
      <tr><td>Idle noise, 20 Hz&ndash;20 kHz</td><td class="num ok">&minus;79.6 dBFS</td><td class="num bad">&mdash;</td><td>the number to beat on the right</td></tr>
    </tbody>
  </table></div>
  <p>When the ripper goes back on, remember it holds the card: <code class="mono">sudo systemctl start vinyl-adc-ripper</code>.</p>
</section>

<footer>
  Drawn from <code>assembly/generated/boards.json</code> (KiCad snapshot of
  <code>hardware/kicad/channel_l</code>) by <code>assembly/underside_wires.py</code>. Both channel boards are cut
  from this one artwork. Background: bring-up log &sect;8.4, open item 1.
</footer>

</div></body></html>
'''

OUT.write_text(html())
print(f'wrote {OUT.relative_to(ROOT)}')
for w in WIRES:
    print(f"  {w['net']:<4} {w['frm'][0]}.{w['frm'][1]} -> {w['to'][0]}.{w['to'][1]}  {w['mm']:.1f} mm")
