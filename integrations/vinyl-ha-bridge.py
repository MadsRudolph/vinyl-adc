#!/usr/bin/env python3
"""Mirror the Vinyl ADC ripper's state into Home Assistant as sensor entities.

Runs on the Proxmox host, not on the Pi. This needs a full-access Home Assistant
long-lived token, and the Pi serves an unauthenticated dashboard to the whole LAN;
the host already has root over every guest, so the token adds nothing there that is
not already true. That is the only reason this file lives here.

The entities are pushed through HA's states API rather than backed by an integration,
so they vanish when HA restarts and are recreated on the next run of the timer.
"""
import json, os, urllib.request, urllib.error

RIPPER = os.environ.get('VINYL_PI', 'http://192.168.50.137:8091')
HA     = os.environ.get('HA_URL', 'http://192.168.50.203:8123')
TOKEN  = open('/etc/vinyl-ha-token').read().strip()

def ha(entity, state, attrs):
    body = json.dumps({'state': state, 'attributes': attrs}).encode()
    req = urllib.request.Request(f'{HA}/api/states/{entity}', data=body,
                                 headers={'Authorization': 'Bearer ' + TOKEN,
                                          'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status

def main():
    try:
        with urllib.request.urlopen(f'{RIPPER}/api/state', timeout=8) as r:
            d = json.loads(r.read())
        online = True
    except Exception as e:
        d, online = {}, False

    rec  = d.get('recording') or {}
    now  = d.get('now') or {}
    trk  = now.get('track') or {}
    met  = d.get('meters') or {}
    peak = met.get('peak_db') or []
    health = met.get('health') or []
    healthy = bool(health) and all(h.get('ok') for h in health)
    gap = round(peak[0] - peak[1], 1) if len(peak) == 2 else None

    state = (d.get('status') or 'unknown') if online else 'offline'
    ha('sensor.vinyl_ripper', state, {
        'friendly_name': 'Vinyl ripper',
        'icon': 'mdi:album' if state == 'recording' else 'mdi:record-player',
        'artist': now.get('artist') or '', 'album': now.get('title') or '',
        'track': trk.get('title') or '', 'track_number': trk.get('number_in_album'),
        'track_elapsed_s': trk.get('elapsed'),
        'side': rec.get('id') or '', 'side_seconds': int(rec.get('seconds') or 0),
        'channel_gap_db': gap, 'bitstream_healthy': healthy,
    })
    for ent, name, val in (('sensor.vinyl_left_peak', 'Vinyl left peak',  peak[0] if len(peak) == 2 else None),
                           ('sensor.vinyl_right_peak', 'Vinyl right peak', peak[1] if len(peak) == 2 else None)):
        ha(ent, 'unknown' if val is None else round(val, 1),
           {'friendly_name': name, 'unit_of_measurement': 'dBFS',
            'state_class': 'measurement', 'icon': 'mdi:sine-wave'})
    fault = online and (not healthy or (gap is not None and abs(gap) > 4))
    ha('binary_sensor.vinyl_channel_fault', 'on' if fault else 'off',
       {'friendly_name': 'Vinyl channel fault', 'device_class': 'problem',
        'icon': 'mdi:alert-circle' if fault else 'mdi:check-circle'})
    print(f'{state}  gap={gap}  healthy={healthy}  fault={fault}')

if __name__ == '__main__':
    main()
