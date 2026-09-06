#!/usr/bin/env python3
"""Interactive AD3 board tests. Run --help or a board with --plan first."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import os
# On this Arch installation Adept's libraries are not in the loader cache.
# Scope the workaround to this process; do not change system configuration.
if __name__=='__main__' and sys.platform.startswith('linux') and Path('/usr/lib/digilent/adept').is_dir():
    paths=os.environ.get('LD_LIBRARY_PATH','').split(':')
    if '/usr/lib/digilent/adept' not in paths:
        env=os.environ.copy();env['LD_LIBRARY_PATH']=':'.join(['/usr/lib/digilent/adept']+[x for x in paths if x])
        os.execve(sys.executable,[sys.executable,*sys.argv],env)
import uuid
import numpy as np
from analysis import bit,frequency,summary,sine_fit,mux_errors,channel_stream,dac_errors,stable_mask,clock_delay_ns
from dwf_device import AD3,SDK,InstrumentError
from simulate import SimulatedAD3

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PLANS=json.loads((HERE/'plans.json').read_text());LIMITS=json.loads((HERE/'limits.json').read_text())
class ScreenFailure(RuntimeError):pass

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def prompt(message,word):
    answer=input(f'\n{message}\nType {word} to continue, or q to stop: ').strip()
    if answer!=word:raise KeyboardInterrupt

class Run:
    def __init__(self,args):
        self.args=args;self.board=args.board;self.device=None;self.step=None;self.rail=None;self.current_samples=[]
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.run_id=f'{stamp}-{args.board}-{uuid.uuid4().hex[:8]}'
        self.folder=args.output/self.run_id;self.folder.mkdir(parents=True,exist_ok=False)
        snapshot=json.loads((HERE.parent/'generated/boards.json').read_text())['boards']
        relevant=['power'] if args.board=='power' else ['digital'] if args.board=='digital' else ['power','digital','channel_l']
        self.report={'format':'vinyl-adc-bench-report-v1','id':self.run_id,'board':args.board,'started':dt.datetime.now(dt.timezone.utc).isoformat(),'simulated':args.simulate,'status':'RUNNING','scope':'Assembly functional screening only; not production qualification, SNR, THD or 24-bit validation.','limits':LIMITS,'limits_sha256':sha(HERE/'limits.json'),'sources':{k:snapshot[k]['sha256'] for k in relevant},'steps':[],'supply':{'control':'manual','3v3_source':'AD3 V+' if args.ad3_3v3 else 'external regulated source','current_readings_ma':self.current_samples}}
        for k in relevant:
            if sha(ROOT/snapshot[k]['source'])!=snapshot[k]['sha256']:raise RuntimeError('PCB snapshot is stale. Regenerate it and review changed probe locations before testing.')
    def pause_off(self):
        if not self.args.simulate:prompt('Turn OFF the bench supply (all externally powered rails). Leave wiring alone until AD3 outputs are stopped.', 'OFF')
        self.device.wave_off()
        if self.args.ad3_3v3:self.device.supply_3v3(False)
    def setup(self,key,extra='',pump=False,wave=None):
        self.pause_off()
        step=next(s for s in PLANS['boards'][self.board]['steps'] if s['id']==key)
        print('\n'+step['title']+'\n'+step['instructions'])
        print(extra)
        for c in step['connections']:print(f"  {c['lead']:22s} → {c['ref']}.{c['pin']}  [{c['net']}]")
        print('  AD3 GND, 1−, 2− → board GND. Bench negative → same GND.')
        if not self.args.simulate:prompt('Complete the connections above with bench power OFF. W1 must connect ONLY where this step says; never to another driver.', 'READY')
        if self.args.ad3_3v3 and self.board!='power':self.device.supply_3v3(True)
        if not self.args.simulate:
            prompt('Set bench +5.00 V with the documented current limit. Turn on the supply and confirm it is stable in CV (not persistent CC).', 'ON')
            while True:
                current=input('Record +5 V bench current in mA (or q to abort): ').strip()
                if current.lower()=='q':raise KeyboardInterrupt
                try:
                    value=float(current)
                    if not np.isfinite(value) or value<0:raise ValueError()
                    self.current_samples.append({'step':key,'milliamps':value});break
                except ValueError:print('Enter a finite, nonnegative reading.')
        if pump:self.device.wave('square',192000,2.5,2.5)
        if wave is not None:self.device.wave('sine',1000,wave,0)
        if not self.args.simulate:
            import time
            time.sleep(.25)
    def begin(self,key):
        self.step={'id':key,'status':'RUNNING','metrics':[],'captures':[]};self.report['steps'].append(self.step)
    def measure(self,name,value,lo=None,hi=None,unit=''):
        value=float(value)
        passed=np.isfinite(value) and (lo is None or value>=lo) and (hi is None or value<=hi)
        m={'name':name,'value':value if np.isfinite(value) else None,'min':lo,'max':hi,'unit':unit,'status':'PASS' if passed else 'FAIL'};self.step['metrics'].append(m)
        print(f"  {m['status']:4s} {name}: {value:.6g} {unit}"+(f' [{lo}, {hi}]' if lo is not None or hi is not None else ''))
        if not passed:self.step['status']='FAIL';raise ScreenFailure(f'{name} outside screening limits')
        return value
    def window(self,name,value,key,unit='V'):return self.measure(name,value,*LIMITS[key],unit)
    def end(self):self.step['status']='PASS'
    def capture(self,name,values,rate):
        filename=f'{len(self.report["steps"]):02d}-{name}.npz';np.savez_compressed(self.folder/filename,samples=values,sample_rate_hz=rate)
        self.step['captures'].append({'file':filename,'sample_rate_hz':rate,'samples':values.shape[-1]})
    def scope(self,kind,rate=1e6):
        samples,rate=self.device.scope_fixture(kind,rate,8192) if self.args.simulate else self.device.scope(rate=rate)
        self.capture('scope-'+kind,samples,rate);return samples,rate
    def logic(self,kind,record=False):
        rate=4e6 if record else 50e6;duration=.12 if record else None
        samples,rate=self.device.logic_fixture(kind,rate,duration) if self.args.simulate else self.device.logic(rate,duration)
        self.capture('logic-'+kind+('-record' if record else '-fast'),samples,rate);return samples,rate
    def clock(self,name,x,rate,target):
        hz=frequency(x,rate);tol=LIMITS['clock_relative_error'];self.measure(name,hz,target*(1-tol),target*(1+tol),'Hz')
        self.window(name+' duty',np.mean(x),'clock_duty','fraction')
    def levels(self,name,x,rail,case=None):
        stats=summary(x)
        if case!=1:self.window(name+' LOW',stats['low_v'],'logic_low')
        if case!=0:self.window(name+' HIGH',stats['high_v'],'logic_high_'+rail)
        # Scope sample maxima expose overvoltage that a digital threshold would hide.
        self.measure(name+' observed maximum',np.max(x),None,5.5 if rail=='5v' else 3.8,'V')
    def rails(self):
        self.begin('rails');self.setup('rails',pump=self.board=='power')
        kind='digital' if self.board=='digital' else 'power' if self.board=='power' else 'channel'
        samples,_=self.scope('rails-'+kind)
        self.rail=self.window('+5 V',np.mean(samples[0]),'rail_5v')
        self.window('+3.3 V' if kind=='digital' else 'negative rail',np.mean(samples[1]),'rail_3v3' if kind=='digital' else 'negative_rail')
        for i in (0,1):self.measure(f'rail CH{i+1} gross ripple',np.ptp(samples[i]),0,LIMITS['ripple_vpp_max'],'Vpp')
        self.end()
    def references(self):
        self.begin('references');self.setup('references',pump=self.board=='power');samples,_=self.scope('references')
        for i,(name,k,sign) in enumerate([('VREF_P','reference_positive',1),('VREF_N','reference_negative',-1)]):
            mean=self.window(name,np.mean(samples[i]),k)
            self.measure(name+' ratio error',abs(mean-sign*self.rail/2)/(self.rail/2),0,LIMITS['reference_ratio_error'],'fraction')
            self.measure(name+' gross ripple',np.ptp(samples[i]),0,LIMITS['ripple_vpp_max'],'Vpp')
        self.end()
    def power(self):
        self.begin('pump-check')
        if not self.args.simulate:prompt('Bench OFF; W1 disconnected from every PCB. Wire scope 1+ to W1 and scope 1− to AD3 GND. W1 will output a 0–5 V, 192 kHz square wave.', 'READY')
        self.device.wave('square',192000,2.5,2.5);samples,rate=self.scope('pump-check',10e6)
        self.clock('pump stimulus',samples[0]>2.5,rate,192000);self.levels('pump stimulus',samples[0],'5v');self.device.wave_off();self.end()
        self.rails();self.references()
    def digital(self):
        self.rails();self.begin('clocks');self.setup('clocks')
        words,rate=self.logic('clocks')
        for channel,name,hz in [(0,'CLK6M',6144000),(1,'MCLK',1536000),(2,'BCLK',3072000),(3,'LRCLK',48000),(4,'PI_BCLK',3072000),(5,'PI_LRCLK',48000),(10,'PUMP',192000)]:self.clock(name,bit(words,channel),rate,hz)
        for src,dst,label in [(2,4,'PI_BCLK'),(3,5,'PI_LRCLK')]:
            self.measure(label+' rising-edge delay / polarity',clock_delay_ns(bit(words,src),bit(words,dst),rate),-1e9/rate,120,'ns')
        samples,_=self.scope('clocks',50e6)
        self.levels('PI_BCLK',samples[0],'3v3');self.levels('PI_LRCLK',samples[1],'3v3');self.end()
        for ql,qr in [(0,0),(1,0),(0,1),(1,1)]:
            case=f'mux-{ql}{qr}';self.begin(case)
            self.setup('mux',f'THIS CASE: QL (J4.12) → {"+5 V" if ql else "GND"}; QR (J4.14) → {"+5 V" if qr else "GND"}.')
            words,rate=self.logic(case)
            self.clock('MCLK during mux test',bit(words,1),rate,1536000)
            for channel,label,expected in [(7,'QL',ql),(8,'QR',qr)]:self.measure(label+' input mismatch',np.mean(bit(words,channel)!=expected),0,.001,'fraction')
            for name,value in mux_errors(words,rate).items():self.measure(name,value,0,LIMITS['logic_error_fraction_max'],'fraction')
            samples,_=self.scope(case,50e6)
            self.levels('DIN',samples[0],'5v',ql if ql==qr else None);self.levels('PI_DIN',samples[1],'3v3',ql if ql==qr else None)
            self.end()
    def channel(self):
        self.rails();self.references();self.begin('quiet')
        chosen=12 if self.board=='left' else 14;unused=14 if self.board=='left' else 12
        self.setup('quiet',f'J21 = {"1–2" if self.board=="left" else "2–3"}. DIO5 → J7.{chosen}. Remove any rail jumper from J4.{chosen}; it is now a driven output. The other, absent channel input J4.{unused} may be tied to GND.')
        self.feedback('quiet');words,rate=self.logic('quiet',True);stream=self.check_channel(words,rate)
        self.window('zero-input Q density',stream['density'],'quiet_density','fraction');self.end()
        amplitudes=[]
        for amp in [LIMITS['input_peak_low_v'],LIMITS['input_peak_high_v']]:
            name=f'tone-{amp}';self.begin(name);self.setup('tone',f'THIS PASS: W1 sine 1000 Hz, {amp} Vpeak, zero offset. RV20 unchanged.',wave=amp)
            samples,scope_rate=self.scope(name,100000)
            input_fit=sine_fit(samples[0],scope_rate,1000)
            self.measure('measured input peak',input_fit['amplitude'],amp*.8,amp*1.2,'Vpeak');self.measure('input sine fit R2',input_fit['r2'],.95,1.)
            self.window('+5 V during stimulus',np.mean(samples[1]),'rail_5v')
            self.feedback(name);words,rate=self.logic(name,True);stream=self.check_channel(words,rate)
            fit=sine_fit(stream['audio'],stream['audio_rate'],1000)
            self.measure('recovered 1 kHz amplitude',fit['amplitude'],LIMITS['tone_amplitude_min'],.45,'density peak')
            self.measure('recovered 1 kHz fit R2',fit['r2'],LIMITS['tone_r2_min'],1.)
            amplitudes.append(fit['amplitude'])
            self.capture('recovered-density-'+name,stream['audio'],stream['audio_rate']);self.end()
        self.begin('gain-response');self.window('output amplitude ratio for 2.5x input',amplitudes[1]/amplitudes[0],'tone_gain_ratio','ratio');self.end()
    def check_channel(self,words,rate):
        stream=channel_stream(words,rate)
        self.clock('MCLK',bit(words,0),rate,1536000)
        self.measure('Q transitions',stream['transitions'],100,None,'edges')
        return stream
    def feedback(self,kind):
        words,rate=self.logic(kind)
        for name,value in dac_errors(words).items():self.measure(name,value,0,LIMITS['logic_error_fraction_max'],'fraction')
        mask=stable_mask(words,[1,5],1)
        if np.count_nonzero(mask)<100:raise ValueError('No stable selected-bus samples')
        self.measure('selected channel bus mismatch',np.mean(bit(words,1)[mask]!=bit(words,5)[mask]),0,LIMITS['logic_error_fraction_max'],'fraction')
    def execute(self):
        device=SimulatedAD3(self.args.simulate_fault) if self.args.simulate else AD3(self.args.serial)
        try:
            if not self.args.simulate:
                print('\n'.join(PLANS['common']))
                prompt('Disconnect AD3 W1/W2/V+/V− from the boards; bench supply OFF. Close WaveForms. The script will take exclusive AD3 control and initially disable all its outputs.', 'READY')
            with device as self.device:
                self.report['device']=device.info
                if self.board=='power':self.power()
                elif self.board=='digital':self.digital()
                else:self.channel()
                self.pause_off()
            if device.cleanup_errors:raise InstrumentError('AD3 shutdown could not be verified: '+'; '.join(device.cleanup_errors))
            self.report['status']='PASS'
        except ScreenFailure as e:self.report.update(status='FAIL',error=str(e))
        except (KeyboardInterrupt,EOFError):self.report.update(status='ABORTED',error='Operator stopped the test; remaining checks were not performed.')
        except Exception as e:self.report.update(status='ERROR',error=str(e))
        finally:
            if self.step and self.step['status']=='RUNNING':self.step['status']=self.report['status']
            if device.cleanup_errors:self.report['cleanup_errors']=device.cleanup_errors
            self.report['finished']=dt.datetime.now(dt.timezone.utc).isoformat()
            if self.args.simulate:self.report['simulation_outcome']=self.report['status'];self.report['status']='SIMULATED'
            self.write_report()
            print('\n'+self.report['status']+': '+self.report.get('error','Finished screening sequence.'))
            print('TURN OFF THE BENCH SUPPLY. AD3 outputs have been shut down unless a cleanup error is reported. A disabled W1 is not guaranteed to be high impedance; disconnect it before other use.')
            if self.board=='digital':print('With power OFF, remove the temporary QL/QR test jumpers before connecting either channel board.')
            print('Report: '+str(self.folder/'report.json'))
        outcome=self.report.get('simulation_outcome',self.report['status'])
        return 0 if outcome=='PASS' else 1 if outcome=='FAIL' else 2
    def write_report(self):
        path=self.folder/'report.json';path.write_text(json.dumps(self.report,indent=2,allow_nan=False)+'\n')
        # Build an index from immutable per-run files; keep history, including failures.
        results=[]
        for p in self.args.output.glob('*/report.json'):
            try:
                r=json.loads(p.read_text());results.append({k:r.get(k) for k in ['id','board','started','finished','status','simulated','simulation_outcome','sources','error']})
            except (OSError,ValueError):continue
        results.sort(key=lambda r:r['started'],reverse=True)
        index=self.args.output/'index.json';tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(results,indent=2)+'\n');tmp.replace(index)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('board',choices=['devices','power','digital','left','right'])
    p.add_argument('--serial',help='AD3 serial number from devices')
    p.add_argument('--ad3-3v3',action='store_true',help='Explicitly use AD3 V+ at 3.3 V for digital J2.3; never in parallel with another supply')
    p.add_argument('--plan',action='store_true',help='Print fixture plan without opening any device')
    p.add_argument('--simulate',action='store_true',help='Use synthetic data only; report can never be a hardware PASS')
    p.add_argument('--simulate-fault',choices=['wrong-clock','bad-rail','swapped-mux','stuck-channel','missing-tone'])
    p.add_argument('--output',type=Path,default=HERE/'results')
    args=p.parse_args(argv)
    if args.simulate_fault and not args.simulate:p.error('--simulate-fault requires --simulate')
    if args.board=='power' and args.ad3_3v3:p.error('Power board has no +3.3 V inlet; omit --ad3-3v3')
    if args.board=='devices':
        try:print(json.dumps(SDK().devices(),indent=2));return 0
        except InstrumentError as e:print(e,file=sys.stderr);return 2
    if args.plan:
        print(json.dumps({'common':PLANS['common'],**PLANS['boards'][args.board]},indent=2));return 0
    try:return Run(args).execute()
    except Exception as e:print(str(e),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
