#!/usr/bin/env python3
"""Clock the ADC from the Pi: GPCLK0 on GPIO4 (pin 7), for J1 in its Pi-clock position (bring-up fallback).

    sudo python3 gpclk.py            # 6.144 MHz = 128 x 48 kHz
    sudo python3 gpclk.py 0          # stop it

GPCLK0 comes from PLLD through a fractional divider with MASH 1, so its edges carry ~1 ns of jitter: enough to
bring a board up, not to measure it (design-notes section 5 puts it at a 68 dB ceiling). Pi 4 / BCM2711 only.
Nothing claims the clock in the kernel, so it runs until the next reboot or `gpclk.py 0`.
"""
import mmap,os,struct,subprocess,sys,time

CM=0xFE101000;CTL,DIV=0x70,0x74;PASSWD=0x5A000000;PLLD=6;BUSY,ENAB=1<<7,1<<4

def plld_hz():
    for name in ('plld_per','plld'):
        try:return int(open(f'/sys/kernel/debug/clk/{name}/clk_rate').read())
        except OSError:pass
    return 750_000_000                                       # BCM2711's PLLD_PER

def main():
    want=float(sys.argv[1]) if len(sys.argv)>1 else 6.144e6
    fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC);m=mmap.mmap(fd,4096,offset=CM)
    rd=lambda o:struct.unpack_from('<I',m,o)[0]
    def wr(o,v):struct.pack_into('<I',m,o,PASSWD|v)
    wr(CTL,rd(CTL)&~ENAB&0xffffff)
    while rd(CTL)&BUSY:time.sleep(.001)
    if not want:print('GPCLK0 stopped');return
    src=plld_hz();div=round(src/want*4096);divi,divf=div>>12,div&0xfff
    wr(DIV,divi<<12|divf);wr(CTL,1<<9|PLLD);wr(CTL,1<<9|PLLD|ENAB)
    subprocess.run(['pinctrl','set','4','a0'],check=True)
    print(f'GPCLK0 on GPIO4: {src/1e6:g} MHz / {div/4096:.4f} = {src*4096/div/1e6:.6f} MHz (CTL {rd(CTL):#x})')

if __name__=='__main__':main()
