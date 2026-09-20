# Home Assistant

Two separate paths, deliberately, because they need different trust.

## Notifications — no credential anywhere

The ripper POSTs JSON to an HA **webhook** (`notify_url` in its config) when a side starts,
a side finishes, the needle crosses into a new track, or an album reaches the library.
Webhooks are unauthenticated by design, so the Pi holds no token at all. The HA automation
`vinyl_rip_notifications` turns the payload into a push notification.

A finished side carries `channel_gap_db`; past 4 dB the notification is sent red and at high
importance. That exists because on 2026-09-20 the left channel's input came loose 33 minutes
into a rip and nothing said so until the record was already in the library.

## Dashboard sensors — a token, and not on the Pi

`vinyl-ha-bridge` polls the ripper and pushes `sensor.vinyl_ripper`,
`sensor.vinyl_{left,right}_peak` and `binary_sensor.vinyl_channel_fault` into HA through its
states API. That needs a long-lived token, which is full admin access to Home Assistant.

**It runs on the Proxmox host, not on the Pi.** The Pi serves an unauthenticated dashboard to
the whole LAN, so a token there would mean anything reaching the ripper could control the
house. The host already has root over every guest, so the token adds no exposure there that
does not already exist.

    scp integrations/vinyl-ha-bridge.py    root@192.168.50.200:/usr/local/bin/vinyl-ha-bridge
    scp integrations/vinyl-ha-bridge.*     root@192.168.50.200:/etc/systemd/system/
    # the token goes to /etc/vinyl-ha-token, mode 600, and is never echoed
    ssh root@192.168.50.200 'systemctl daemon-reload && systemctl enable --now vinyl-ha-bridge.timer'

These entities come from the states API rather than an integration, so an HA restart drops
them and the timer puts them back within 30 s. That is the trade for needing no YAML in
`configuration.yaml`, which no HA API can write.
