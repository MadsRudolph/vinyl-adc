# Media-server side

`vinyl-pull.py` runs on the Proxmox host as root from `vinyl-pull.timer`, every two minutes, in the same style as the host's autorip service. It **pulls** from the Pi, so no server credentials live on the Pi.

It reads the Pi's `/outbox.json`, downloads every file of a finished album next to its final place, checks size and SHA-256, moves it in, gives it the library's ownership and tells the Pi the album has arrived. It never deletes anything and never overwrites a file that differs. Names from the Pi are validated before they touch the filesystem.

Albums land in `/srv/media/music/Vinyl/Artist/Album (Year) [Vinyl]/`. Jellyfin's Music library already includes `/media/music` with real-time monitoring, so they appear without a manual scan.

Install:

```sh
install -D -m 755 vinyl-pull.py /opt/vinyl-pull/vinyl-pull.py
install -m 644 vinyl-pull.service vinyl-pull.timer /etc/systemd/system/
echo 'VINYL_PI=http://192.168.50.137:8091' > /etc/default/vinyl-pull     # the Pi; give it a DHCP reservation
systemctl daemon-reload && systemctl enable --now vinyl-pull.timer
journalctl -u vinyl-pull.service -n 20        # what it did
```
