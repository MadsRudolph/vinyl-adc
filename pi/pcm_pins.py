#!/usr/bin/env python3
"""Show whether the Pi 4's I2S clock pins are inputs (clock consumer) or outputs. Run with sudo.

The bcm2835-i2s driver only programs consumer mode when a stream is first opened; until then the block
keeps its reset state. Check this before wiring an external clock master to GPIO18/19.
"""
import mmap,os,struct
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
m=mmap.mmap(fd,4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=0xFE203000)   # PCM/I2S block on BCM2711
cs,=struct.unpack('<I',m[0:4]);mode,=struct.unpack('<I',m[8:12])
clk_in=(mode>>23)&1;fs_in=(mode>>21)&1
print(f'CS_A=0x{cs:08x} EN={cs&1} RXON={(cs>>1)&1}   MODE_A=0x{mode:08x} CLKM={clk_in} FSM={fs_in}')
print('PCM_CLK  (GPIO18):','INPUT, clock consumer' if clk_in else 'OUTPUT, clock master')
print('PCM_FS   (GPIO19):','INPUT, clock consumer' if fs_in else 'OUTPUT, clock master')
