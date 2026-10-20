"""Rev D front panel: the ripper's three state LEDs and the USER button (README section 7).

    REC   GPIO17  on while a side is being recorded; flashes for 1 s after a peak above CLIP_DBFS
    BUSY  GPIO27  on while the worker identifies, cuts or encodes
    READY GPIO22  on when the capture card is open and nothing is recording; blinks when the ADC sends no clocks
    USER  GPIO23  press: start a side now, or stop the one being recorded (the dashboard's Record / Stop)

SW1 on GPIO3 is not handled here: `dtoverlay=gpio-shutdown` in config.txt makes it the power button.
Without gpiozero, or off a Pi (offline tests, --replay), the panel does nothing.
"""
import threading,time

CLIP_DBFS=-.3          # the dashboard's "■ CLIP" mark. Stands in for the CLIP L/R LEDs while U12 is out of its socket:
                       # rev D's LM339 window has its inputs swapped (bring-up log, rev D erratum) and lights them always

def start(rip):
    try:
        from gpiozero import LED,Button
        rec,busy,ready=LED(17),LED(27),LED(22);user=Button(23,pull_up=True,bounce_time=.05)
    except Exception as e:
        rip.log(f'Front panel not available ({e!r})');return
    def press():
        with rip.lock:
            if rip.status not in ('idle','recording'):return          # no clocks yet: a press must not start a side the moment they arrive
            rip.manual_from='front panel';rip.manual='stop' if rip.side else 'start'
    user.when_pressed=press
    def loop():
        blinking=False;clip_until=0.;tick=0
        while not rip.stop.is_set():
            with rip.lock:status=rip.status;working=rip.busy;m=rip.meters
            now=time.time();tick+=1
            if status in ('idle','recording') and m and max(m['peak_db'])>CLIP_DBFS:clip_until=now+1.
            rec.value=tick%2 if now<clip_until else status=='recording';busy.value=bool(working)
            if status=='waiting':
                if not blinking:ready.blink(.2,.8);blinking=True
            else:
                blinking=False;ready.value=status=='idle'
            time.sleep(.25)
        for led in (rec,busy,ready):led.off()
    threading.Thread(target=loop,daemon=True).start()
