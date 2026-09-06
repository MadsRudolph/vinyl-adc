"""Small checked ctypes interface to Digilent WaveForms SDK 3.25.1.

Only an explicitly selected Analog Discovery 3 may be opened. DIO pins are
always inputs. W1 and (optionally) V+ are the only enabled outputs.
"""
import ctypes as C
import ctypes.util
import os
import sys
import time
from pathlib import Path
import numpy as np

class InstrumentError(RuntimeError): pass

I,U,B,D,V,S=C.c_int,C.c_uint,C.c_ubyte,C.c_double,C.c_void_p,C.c_char_p
PI,PD,PB=C.POINTER(I),C.POINTER(D),C.POINTER(B)
SIGNATURES={
 'GetVersion':[V], 'GetLastErrorMsg':[V], 'Enum':[I,PI], 'EnumDeviceType':[I,PI,PI],
 'EnumDeviceName':[I,V], 'EnumSN':[I,V], 'EnumDeviceIsOpened':[I,PI],
 'ParamSet':[I,I], 'DeviceOpen':[I,PI], 'DeviceClose':[I],
 'DeviceAutoConfigureSet':[I,I], 'DeviceParamSet':[I,I,I],
 'AnalogOutReset':[I,I], 'AnalogOutConfigure':[I,I,I],
 'AnalogOutNodeEnableSet':[I,I,I,I], 'AnalogOutNodeFunctionSet':[I,I,I,B],
 'AnalogOutNodeFrequencySet':[I,I,I,D], 'AnalogOutNodeAmplitudeSet':[I,I,I,D],
 'AnalogOutNodeOffsetSet':[I,I,I,D], 'AnalogOutNodeSymmetrySet':[I,I,I,D],
 'AnalogOutIdleSet':[I,I,I],
 'AnalogIOReset':[I], 'AnalogIOChannelNodeSet':[I,I,I,D], 'AnalogIOEnableSet':[I,I],
 'DigitalOutReset':[I], 'DigitalIOOutputEnableSet':[I,U], 'DigitalIOConfigure':[I],
 'DigitalIOPullSet':[I,U,U],
 'AnalogInReset':[I], 'AnalogInChannelEnableSet':[I,I,I],
 'AnalogInChannelRangeSet':[I,I,D], 'AnalogInChannelRangeGet':[I,I,PD],
 'AnalogInChannelOffsetSet':[I,I,D], 'AnalogInFrequencySet':[I,D], 'AnalogInFrequencyGet':[I,PD],
 'AnalogInBufferSizeInfo':[I,PI,PI], 'AnalogInBufferSizeSet':[I,I], 'AnalogInBufferSizeGet':[I,PI],
 'AnalogInAcquisitionModeSet':[I,I], 'AnalogInTriggerSourceSet':[I,B],
 'AnalogInConfigure':[I,I,I], 'AnalogInStatus':[I,I,PB],
 'AnalogInStatusSamplesValid':[I,PI], 'AnalogInStatusData':[I,I,V,I],
 'DigitalInReset':[I], 'DigitalInInternalClockInfo':[I,PD],
 'DigitalInDividerSet':[I,U], 'DigitalInDividerGet':[I,C.POINTER(U)],
 'DigitalInSampleFormatSet':[I,I], 'DigitalInSampleModeSet':[I,I],
 'DigitalInBufferSizeInfo':[I,PI], 'DigitalInBufferSizeSet':[I,I], 'DigitalInBufferSizeGet':[I,PI],
 'DigitalInAcquisitionModeSet':[I,I], 'DigitalInTriggerSourceSet':[I,B],
 'DigitalInTriggerPositionSet':[I,U], 'DigitalInTriggerPrefillSet':[I,U],
 'DigitalInConfigure':[I,I,I], 'DigitalInStatus':[I,I,PB],
 'DigitalInStatusSamplesValid':[I,PI], 'DigitalInStatusData':[I,V,I],
 'DigitalInStatusRecord':[I,PI,PI,PI],
}

def load_library():
    candidates=[os.environ.get('DWF_LIBRARY')]
    if sys.platform=='win32': candidates+=['dwf.dll']
    elif sys.platform=='darwin': candidates+=['/Library/Frameworks/dwf.framework/dwf','/Applications/WaveForms.app/Contents/Frameworks/dwf.framework/dwf']
    else: candidates+=[ctypes.util.find_library('dwf'),'libdwf.so']
    errors=[]
    for path in filter(None,candidates):
        try:
            lib=C.CDLL(path)
            for name,args in SIGNATURES.items():
                fn=getattr(lib,'FDwf'+name);fn.argtypes=args;fn.restype=I
            return lib
        except (OSError,AttributeError) as e: errors.append(str(e))
    raise InstrumentError('WaveForms Runtime not available. Install WaveForms + Adept Runtime; see assembly/downloads/README.md. '+ '; '.join(errors))

class SDK:
    def __init__(self): self.lib=load_library()
    def call(self,name,*args):
        if getattr(self.lib,'FDwf'+name)(*args)!=1:
            err=C.create_string_buffer(512);self.lib.FDwfGetLastErrorMsg(err)
            raise InstrumentError(f'FDwf{name}: {err.value.decode(errors="replace")}')
    def devices(self):
        version=C.create_string_buffer(32);self.call('GetVersion',version)
        count=I();self.call('Enum',0,C.byref(count));devices=[]
        for i in range(count.value):
            devid,revision,used=I(),I(),I();name=C.create_string_buffer(64);serial=C.create_string_buffer(64)
            self.call('EnumDeviceType',i,C.byref(devid),C.byref(revision));self.call('EnumDeviceName',i,name)
            self.call('EnumSN',i,serial);self.call('EnumDeviceIsOpened',i,C.byref(used))
            devices.append({'index':i,'id':devid.value,'name':name.value.decode(),'serial':serial.value.decode(),'in_use':bool(used.value)})
        return {'sdk':version.value.decode(),'devices':devices}

class AD3:
    def __init__(self,serial=None): self.sdk=SDK();self.handle=I();self.serial=serial;self.info=None;self.cleanup_errors=[]
    def call(self,name,*args): return self.sdk.call(name,self.handle,*args)
    def __enter__(self):
        listing=self.sdk.devices();devices=[d for d in listing['devices'] if d['id']==10 and (not self.serial or d['serial']==self.serial)]
        if len(devices)!=1: raise InstrumentError('Connect exactly one AD3 or select --serial from the devices command.')
        if devices[0]['in_use']: raise InstrumentError('AD3 is in use. Close WaveForms and other SDK scripts first.')
        self.info={**devices[0],'sdk':listing['sdk']}
        self.sdk.call('ParamSet',4,2)  # OnClose = shutdown, never leave outputs running.
        self.sdk.call('DeviceOpen',devices[0]['index'],C.byref(self.handle))
        try:
            self.call('DeviceAutoConfigureSet',1)
            self.call('AnalogOutReset',-1);self.call('AnalogIOReset');self.call('AnalogIOEnableSet',0)
            self.call('DigitalOutReset');self.call('DigitalIOOutputEnableSet',0);self.call('DigitalIOPullSet',0,0);self.call('DigitalIOConfigure')
        except BaseException:
            self.close();raise
        return self
    def close(self):
        if not self.handle.value:return
        for name,args in [('AnalogOutReset',(-1,)),('DigitalOutReset',()),('DigitalIOOutputEnableSet',(0,)),('DigitalIOConfigure',()),('AnalogIOEnableSet',(0,)),('DeviceClose',())]:
            try:self.call(name,*args)
            except Exception as e:self.cleanup_errors.append(str(e))
        self.handle=I()
    def __exit__(self,*exc): self.close()
    def wave(self,kind,frequency,amplitude,offset=0):
        if kind not in ['sine','square','dc'] or abs(offset)+amplitude>5 or amplitude<0:raise ValueError('Invalid W1 setting')
        self.call('AnalogOutConfigure',0,0)
        self.call('AnalogOutNodeEnableSet',0,0,1)
        self.call('AnalogOutNodeFunctionSet',0,0,{'dc':0,'sine':1,'square':2}[kind])
        self.call('AnalogOutNodeFrequencySet',0,0,float(frequency))
        self.call('AnalogOutNodeAmplitudeSet',0,0,float(amplitude))
        self.call('AnalogOutNodeOffsetSet',0,0,float(offset))
        self.call('AnalogOutNodeSymmetrySet',0,0,50.)
        self.call('AnalogOutIdleSet',0,0)  # idle disabled, not hold last value
        self.call('AnalogOutConfigure',0,1)
    def wave_off(self):self.call('AnalogOutReset',0)
    def supply_3v3(self,enabled):
        self.call('AnalogIOEnableSet',0)
        self.call('AnalogIOChannelNodeSet',1,0,0.)
        self.call('AnalogIOChannelNodeSet',0,1,3.3)
        self.call('AnalogIOChannelNodeSet',0,0,float(bool(enabled)))
        self.call('AnalogIOEnableSet',int(bool(enabled)))
    def scope(self,rate=1e6,count=8192):
        self.call('AnalogInReset')
        for channel in (0,1):
            self.call('AnalogInChannelEnableSet',channel,1)
            self.call('AnalogInChannelRangeSet',channel,20.)
            self.call('AnalogInChannelOffsetSet',channel,0.)
        lo,hi=I(),I();self.call('AnalogInBufferSizeInfo',C.byref(lo),C.byref(hi))
        self.call('AnalogInBufferSizeSet',min(count,hi.value));actual_count=I();self.call('AnalogInBufferSizeGet',C.byref(actual_count))
        self.call('AnalogInFrequencySet',float(rate));actual_rate=D();self.call('AnalogInFrequencyGet',C.byref(actual_rate))
        self.call('AnalogInAcquisitionModeSet',0);self.call('AnalogInTriggerSourceSet',0)
        self.call('AnalogInConfigure',1,0);time.sleep(2)  # SDK offset settling guidance
        self.call('AnalogInConfigure',0,1)
        self._wait('AnalogInStatus',5)
        valid=I();self.call('AnalogInStatusSamplesValid',C.byref(valid))
        if valid.value<actual_count.value:raise InstrumentError('Incomplete scope acquisition')
        arrays=[]
        for channel in (0,1):
            buf=np.empty(actual_count.value,dtype=np.float64)
            self.call('AnalogInStatusData',channel,buf.ctypes.data_as(V),len(buf));arrays.append(buf)
        return np.array(arrays),actual_rate.value
    def _wait(self,status_call,timeout):
        deadline=time.monotonic()+timeout;status=B()
        while time.monotonic()<deadline:
            self.call(status_call,1,C.byref(status))
            if status.value==2:return
            time.sleep(.001)
        raise InstrumentError('Acquisition timed out; no pass can be inferred')
    def logic(self,rate=50e6,duration=None):
        self.call('DigitalInReset');clock=D();self.call('DigitalInInternalClockInfo',C.byref(clock))
        divider=max(1,round(clock.value/rate));self.call('DigitalInDividerSet',divider)
        actual_divider=U();self.call('DigitalInDividerGet',C.byref(actual_divider));rate=clock.value/actual_divider.value
        self.call('DigitalInSampleFormatSet',16);self.call('DigitalInSampleModeSet',0)
        self.call('DigitalInTriggerSourceSet',0);self.call('DigitalInTriggerPrefillSet',0)
        if duration is None:
            maxcount=I();self.call('DigitalInBufferSizeInfo',C.byref(maxcount))
            self.call('DigitalInBufferSizeSet',min(32768,maxcount.value));count=I();self.call('DigitalInBufferSizeGet',C.byref(count));count=count.value
            self.call('DigitalInAcquisitionModeSet',0);self.call('DigitalInTriggerPositionSet',count)
            self.call('DigitalInConfigure',1,1);self._wait('DigitalInStatus',5)
            valid=I();self.call('DigitalInStatusSamplesValid',C.byref(valid))
            if valid.value<count:raise InstrumentError('Incomplete digital acquisition')
            buf=np.empty(count,dtype=np.uint16);self.call('DigitalInStatusData',buf.ctypes.data_as(V),buf.nbytes)
        else:
            count=round(rate*duration);buf=np.empty(count,dtype=np.uint16)
            self.call('DigitalInAcquisitionModeSet',3);self.call('DigitalInTriggerPositionSet',count)
            self.call('DigitalInConfigure',1,1)
            n=0;deadline=time.monotonic()+duration+8;status=B()
            while n<count:
                if time.monotonic()>deadline:raise InstrumentError('Digital record timed out')
                self.call('DigitalInStatus',1,C.byref(status))
                if status.value in (4,5,1):continue
                available,lost,corrupt=I(),I(),I();self.call('DigitalInStatusRecord',C.byref(available),C.byref(lost),C.byref(corrupt))
                if lost.value or corrupt.value:raise InstrumentError(f'Digital record lost {lost.value} / corrupt {corrupt.value} samples; capture rejected')
                size=min(available.value,count-n)
                if size:
                    self.call('DigitalInStatusData',V(buf.ctypes.data+n*2),size*2);n+=size
                elif status.value==2:raise InstrumentError('Digital record ended before requested samples arrived')
                else:time.sleep(.0005)
            self.call('DigitalInConfigure',0,0)
        return buf,rate
