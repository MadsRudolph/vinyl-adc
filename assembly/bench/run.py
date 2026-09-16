#!/usr/bin/env python3
"""Interactive AD3 board tests. Run --help or a board with --plan first.

Prompts come from an operator object: the terminal by default, or the local
browser GUI in gui.py. Both only relay the operator's READY / ON / OFF
confirmations; neither turns the bench supply on or off.
"""
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
import time
import uuid
import numpy as np
from analysis import bit,frequency,summary,sine_fit,mux_errors,channel_stream,dac_errors,stable_mask,clock_delay_ns,digitize,follow_error,mux_case_error
from dwf_device import AD3,SDK,InstrumentError
from simulate import SimulatedAD3

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PLANS=json.loads((HERE/'plans.json').read_text());LIMITS=json.loads((HERE/'limits.json').read_text())
STEP_ORDER={'power':['pump-check','rails','references'],'digital':['rails','pi-clocks','bus-clocks'],'stack':['rails','references','pi-clocks','pi-data'],
            'left':['rails','references','quiet','tone-0.1','tone-0.25','gain-response'],'right':['rails','references','quiet','tone-0.1','tone-0.25','gain-response']}
class ScreenFailure(RuntimeError):pass

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def probe_setting(text):
    try:values=tuple(int(x) for x in str(text).split(','))
    except ValueError:raise argparse.ArgumentTypeError('use 1, 10 or two comma-separated values such as 10,1')
    if len(values)==1:values=values*2
    if len(values)!=2 or any(v not in (1,10) for v in values):raise argparse.ArgumentTypeError('each scope channel must be 1 or 10')
    return values

class TerminalOperator:
    """Prompts on stdin/stdout. Confirmation words are case-insensitive; q aborts."""
    def say(self,text):print(text)
    def show_step(self,step,extra):
        print('\n'+step['title']+'\n'+step['instructions'])
        if extra:print(extra)
        for c in step['connections']:print(f"  {c['lead']:22s} → {c['ref']}.{c['pin']}  [{c['net']}]")
        print('  AD3 GND, 1−, 2− → board GND. Bench negative → same GND.')
    def prompt(self,message,word):
        answer=input(f'\n{message}\nType {word} to continue, or q to stop: ').strip()
        if answer.upper()!=word:raise KeyboardInterrupt
    def ask_current(self):
        while True:
            current=input('Record +5 V bench current in mA (or q to abort): ').strip()
            if current.lower()=='q':raise KeyboardInterrupt
            try:
                value=float(current)
                if not np.isfinite(value) or value<0:raise ValueError()
                return value
            except ValueError:print('Enter a finite, nonnegative reading.')
    def metric(self,m):pass
    def finished(self,report):pass

class Run:
    def __init__(self,args,operator=None):
        self.args=args;self.board=args.board;self.device=None;self.step=None;self.rail=None;self.current_samples=[];self.op=operator or TerminalOperator()
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.run_id=f'{stamp}-{args.board}-{uuid.uuid4().hex[:8]}'
        self.folder=args.output/self.run_id;self.folder.mkdir(parents=True,exist_ok=False)
        snapshot=json.loads((HERE.parent/'generated/boards.json').read_text())['boards']
        relevant=['power'] if args.board=='power' else ['digital'] if args.board=='digital' else ['power','digital','channel_l']  # stack and channels need all three
        self.report={'format':'vinyl-adc-bench-report-v1','id':self.run_id,'board':args.board,'started':dt.datetime.now(dt.timezone.utc).isoformat(),'simulated':args.simulate,'status':'RUNNING','scope':'Assembly functional screening only; not production qualification, SNR, THD or 24-bit validation.','limits':LIMITS,'limits_sha256':sha(HERE/'limits.json'),'sources':{k:snapshot[k]['sha256'] for k in relevant},'steps':[],'supply':{'control':'manual','3v3_source':'AD3 V+' if args.ad3_3v3 else 'external regulated source','current_readings_ma':self.current_samples},'scope_inputs':{'probe_attenuation':{'scope_1':args.probe[0],'scope_2':args.probe[1]},'fixture':'direct 1x flywires' if tuple(args.probe)==(1,1) else f'BNC adapter: scope 1 probe {args.probe[0]}x, scope 2 probe {args.probe[1]}x'}}
        for k in relevant:
            if sha(ROOT/snapshot[k]['source'])!=snapshot[k]['sha256']:raise RuntimeError('PCB snapshot is stale. Regenerate it and review changed probe locations before testing.')
        self.carry={}
        if getattr(args,'resume',None):self.load_resume(args.resume)
    def load_resume(self,run_id):
        """Carry PASS steps from an earlier, comparable run of the same board so only the remaining steps are repeated."""
        path=self.args.output/run_id/'report.json'
        if not path.is_file():raise RuntimeError(f'No report found for {run_id}')
        prior=json.loads(path.read_text())
        if prior.get('simulated') or self.args.simulate:raise RuntimeError('Simulated runs cannot be resumed or carried over')
        if prior.get('board')!=self.board:raise RuntimeError(f'{run_id} tested the {prior.get("board")} board, not {self.board}')
        if prior.get('sources')!=self.report['sources']:raise RuntimeError(f'{run_id} was recorded on a different PCB snapshot; its steps cannot be carried over')
        if prior.get('limits_sha256')!=self.report['limits_sha256']:raise RuntimeError(f'{run_id} used different screening limits; its steps cannot be carried over')
        if prior.get('scope_inputs')!=self.report['scope_inputs'] or prior.get('supply',{}).get('3v3_source')!=self.report['supply']['3v3_source']:raise RuntimeError(f'{run_id} used a different probe or 3.3 V fixture; rerun it completely')
        order=STEP_ORDER[self.board];passed={s['id']:s for s in prior.get('steps',[]) if s.get('status')=='PASS'}
        for key in order:
            if key not in passed:break
            self.carry[key]=dict(passed[key],carried_from=run_id)
        if not self.carry:raise RuntimeError(f'{run_id} has no leading PASS steps to carry over')
        self.report['resumed_from']={'id':run_id,'carried_steps':list(self.carry)}
        for r in prior.get('supply',{}).get('current_readings_ma',[]):
            if r.get('step') in self.carry:self.current_samples.append(dict(r,carried_from=run_id))
        self.say(f'Carrying over from {run_id}: '+', '.join(self.carry)+'. Those steps are not repeated.')
    def carried(self,key):
        if key not in self.carry:return False
        self.report['steps'].append(self.carry[key]);self.say(f'  CARRIED {key}: passed in {self.carry[key]["carried_from"]}')
        return True
    def carried_value(self,key,name):
        m=next((m for m in self.carry[key]['metrics'] if m['name']==name),None)
        if m is None or m['value'] is None:raise RuntimeError(f'Carried step {key} has no usable {name} value')
        return m['value']
    def say(self,text):self.op.say(text)
    def prompt(self,message,word):
        if not self.args.simulate:self.op.prompt(message,word)
    def pause_off(self):
        self.prompt('Turn OFF the bench supply (all externally powered rails). Leave wiring alone until AD3 outputs are stopped.', 'OFF')
        self.device.wave_off()
        if self.args.ad3_3v3:self.device.supply_3v3(False)
    def setup(self,key,extra='',pump=False,wave=None):
        self.pause_off()
        step=next(s for s in PLANS['boards'][self.board]['steps'] if s['id']==key)
        self.op.show_step(step,extra)
        self.prompt('Complete the connections above with bench power OFF. W1 must connect ONLY where this step says; never to another driver.', 'READY')
        if self.args.ad3_3v3 and self.board!='power':self.device.supply_3v3(True)
        if not self.args.simulate:
            self.prompt('Set bench +5.00 V with the documented current limit. Turn on the supply and confirm it is stable in CV (not persistent CC).', 'ON')
            self.current_samples.append({'step':key,'milliamps':self.op.ask_current()})
            if self.args.ad3_3v3 and self.board!='power':
                time.sleep(.3);v,i=self.device.supply_status()
                self.current_samples[-1]['ad3_vplus_v']=v;self.current_samples[-1]['ad3_vplus_ma']=i*1000
                self.say(f'  AD3 V+ as reported by the instrument: {v:.3f} V, {i*1000:.1f} mA')
                if v<LIMITS['rail_3v3'][0]:self.say('  AD3 V+ has not reached 3.3 V at the instrument: the +3.3 V wire is probably shorted on the board (V+ folds back) or V+ is not enabled. (A reading near 0 mA is normal: the 3.3 V side is one CMOS buffer.)')
        if pump:self.device.wave('square',192000,2.5,2.5)
        if wave is not None:self.device.wave('sine',1000,wave,0)
        if not self.args.simulate:time.sleep(.25)
    def begin(self,key):
        self.step={'id':key,'status':'RUNNING','metrics':[],'captures':[]};self.report['steps'].append(self.step)
    def measure(self,name,value,lo=None,hi=None,unit=''):
        value=float(value)
        passed=np.isfinite(value) and (lo is None or value>=lo) and (hi is None or value<=hi)
        m={'name':name,'value':value if np.isfinite(value) else None,'min':lo,'max':hi,'unit':unit,'status':'PASS' if passed else 'FAIL'};self.step['metrics'].append(m)
        self.say(f"  {m['status']:4s} {name}: {value:.6g} {unit}"+(f' [{lo}, {hi}]' if lo is not None or hi is not None else ''));self.op.metric(m)
        if not passed:self.step['status']='FAIL';raise ScreenFailure(f'{name} outside screening limits')
        return value
    def window(self,name,value,key,unit='V'):return self.measure(name,value,*LIMITS[key],unit)
    def end(self):self.step['status']='PASS'
    def capture(self,name,values,rate):
        filename=f'{len(self.report["steps"]):02d}-{name}.npz';np.savez_compressed(self.folder/filename,samples=values,sample_rate_hz=rate)
        self.step['captures'].append({'file':filename,'sample_rate_hz':rate,'samples':values.shape[-1]})
    def scope(self,kind,rate=1e6,count=8192):
        samples,rate=self.device.scope_fixture(kind,rate,count) if self.args.simulate else self.device.scope(rate=rate,count=count)
        self.capture('scope-'+kind,samples,rate);return samples,rate
    def logic(self,kind,record=False):
        rate=4e6 if record else 50e6;duration=.12 if record else None
        words,rate=self.device.logic_fixture(kind,rate,duration) if self.args.simulate else self.device.logic(rate,duration)
        self.capture('logic-'+kind,words,rate);return words,rate
    def clock(self,name,bits,rate,hz):
        f=frequency(bits,rate)
        if f is None:raise ValueError(f'{name}: no clock edges captured')
        self.measure(name+' frequency',f,hz*(1-LIMITS['clock_relative_error']),hz*(1+LIMITS['clock_relative_error']),'Hz')
        self.window(name+' duty',np.mean(bits),'clock_duty','fraction')
    def levels(self,name,x,rail,case=None):
        stats=summary(x)
        if case!=1:self.window(name+' LOW',stats['low_v'],'logic_low')
        if case!=0:self.window(name+' HIGH',stats['high_v'],'logic_high_'+rail)
        # Scope sample maxima expose overvoltage that a digital threshold would hide.
        self.measure(name+' observed maximum',np.max(x),None,5.5 if rail=='5v' else 3.8,'V')
    def rails(self):
        if self.carried('rails'):self.rail=self.carried_value('rails','+5 V');return
        self.begin('rails');self.setup('rails',pump=self.board=='power')
        kind='digital' if self.board=='digital' else 'power' if self.board=='power' else 'channel'
        samples,_=self.scope('rails-'+kind)
        self.rail=self.window('+5 V',np.mean(samples[0]),'rail_5v')
        self.window('+3.3 V' if kind=='digital' else 'negative rail',np.mean(samples[1]),'rail_3v3' if kind=='digital' else 'negative_rail')
        for i in (0,1):self.measure(f'rail CH{i+1} gross ripple',np.ptp(samples[i]),0,LIMITS['ripple_vpp_max'],'Vpp')
        self.end()
    def references(self):
        if self.carried('references'):return
        self.begin('references');self.setup('references',pump=self.board=='power');samples,_=self.scope('references')
        for i,(name,k,sign) in enumerate([('VREF_P','reference_positive',1),('VREF_N','reference_negative',-1)]):
            mean=self.window(name,np.mean(samples[i]),k)
            self.measure(name+' ratio error',abs(mean-sign*self.rail/2)/(self.rail/2),0,LIMITS['reference_ratio_error'],'fraction')
            self.measure(name+' gross ripple',np.ptp(samples[i]),0,LIMITS['ripple_vpp_max'],'Vpp')
        self.end()
    def power(self):
        if not self.carried('pump-check'):
            self.begin('pump-check')
            self.prompt('Bench OFF; W1 disconnected from every PCB. Wire scope 1+ to W1 and scope 1− to AD3 GND. W1 will output a 0–5 V, 192 kHz square wave.', 'READY')
            self.device.wave('square',192000,2.5,2.5);samples,rate=self.scope('pump-check',10e6)
            self.clock('pump stimulus',samples[0]>2.5,rate,192000);self.levels('pump stimulus',samples[0],'5v');self.device.wave_off();self.end()
        self.rails();self.references()
    # Two scope probes on header pins only; each step is one power-off probe move. No DIO harness, no rail ties.
    def clock_pair(self,key,name_a,hz_a,rail_a,name_b,hz_b,rail_b,rate=50e6):
        if self.carried(key):return
        self.begin(key);self.setup(key);samples,rate=self.scope(key,rate,32768)
        for name,x in [(name_a,samples[0]),(name_b,samples[1])]:
            st=summary(x);self.measure(name+' logic swing',st['high_v']-st['low_v'],1.0,None,'V')  # a stuck line fails here with its level visible in the log
        a=digitize(samples[0]);b=digitize(samples[1])
        self.clock(name_a,a,rate,hz_a);self.levels(name_a,samples[0],rail_a)
        self.clock(name_b,b,rate,hz_b);self.levels(name_b,samples[1],rail_b);self.end()
    def pi_clocks(self):self.clock_pair('pi-clocks','PI_BCLK',3072000,'3v3','PI_LRCLK',48000,'3v3')
    def digital(self):
        self.rails();self.pi_clocks()
        self.clock_pair('bus-clocks','MCLK',1536000,'5v','PUMP',192000,'5v')
    def stack(self):
        self.rails();self.references();self.pi_clocks()
        if self.carried('pi-data'):return
        self.begin('pi-data');self.setup('pi-data');samples,rate=self.scope('pi-data',50e6,32768)
        data=(samples[0]>1.65).astype(np.uint8);self.clock('PI_BCLK during data check',digitize(samples[1]),rate,3072000)  # fixed 3.3 V midpoint so a stuck line fails on edges, not on thresholding
        self.measure('PI_DIN transitions',np.count_nonzero(np.diff(data)),100,None,'edges')
        self.measure('PI_DIN one-density',np.mean(data),.1,.9,'fraction')
        self.levels('PI_DIN',samples[0],'3v3');self.levels('PI_BCLK',samples[1],'3v3');self.end()
    def channel(self):
        self.rails();self.references()
        chosen=12 if self.board=='left' else 14;unused=14 if self.board=='left' else 12
        if not self.carried('quiet'):
            self.begin('quiet')
            self.setup('quiet',f'J21 = {"1–2" if self.board=="left" else "2–3"}. DIO5 → J7.{chosen}. Remove any rail jumper from J4.{chosen}; it is now a driven output. The other, absent channel input J4.{unused} may be tied to GND.')
            self.feedback('quiet');words,rate=self.logic('quiet',True);stream=self.check_channel(words,rate)
            self.window('zero-input Q density',stream['density'],'quiet_density','fraction');self.end()
        amplitudes=[]
        for amp in [LIMITS['input_peak_low_v'],LIMITS['input_peak_high_v']]:
            name=f'tone-{amp}'
            if self.carried(name):amplitudes.append(self.carried_value(name,'recovered 1 kHz amplitude'));continue
            self.begin(name);self.setup('tone',f'THIS PASS: W1 sine 1000 Hz, {amp} Vpeak, zero offset. RV20 unchanged.',wave=amp)
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
        if self.carried('gain-response'):return
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
        device=SimulatedAD3(self.args.simulate_fault) if self.args.simulate else AD3(self.args.serial,self.args.probe)
        try:
            if not self.args.simulate:
                self.say('\n'.join(PLANS['common']))
                self.say(f"\nScope inputs for this run: scope 1 = {self.args.probe[0]}x, scope 2 = {self.args.probe[1]}x ({self.report['scope_inputs']['fixture']}). Each physical probe switch must match its channel.")
                self.prompt('Disconnect AD3 W1/W2/V+/V− from the boards; bench supply OFF. Close WaveForms. The script will take exclusive AD3 control and initially disable all its outputs.', 'READY')
            with device as self.device:
                self.report['device']=device.info
                if self.board=='power':self.power()
                elif self.board=='digital':self.digital()
                elif self.board=='stack':self.stack()
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
            self.say('\n'+self.report['status']+': '+self.report.get('error','Finished screening sequence.'))
            self.say('TURN OFF THE BENCH SUPPLY. AD3 outputs have been shut down unless a cleanup error is reported. A disabled W1 is not guaranteed to be high impedance; disconnect it before other use.')
            self.say('Report: '+str(self.folder/'report.json'))
            self.op.finished(self.report)
        outcome=self.report.get('simulation_outcome',self.report['status'])
        return 0 if outcome=='PASS' else 1 if outcome=='FAIL' else 2
    def write_report(self):
        path=self.folder/'report.json';path.write_text(json.dumps(self.report,indent=2,allow_nan=False)+'\n')
        write_index(self.args.output)

def write_index(output):
    # Build an index from immutable per-run files; keep history, including failures.
    results=[]
    for p in output.glob('*/report.json'):
        try:
            r=json.loads(p.read_text());results.append({k:r.get(k) for k in ['id','board','started','finished','status','simulated','simulation_outcome','sources','error','resumed_from','scope_inputs']})
        except (OSError,ValueError):continue
    results.sort(key=lambda r:r['started'],reverse=True)
    index=output/'index.json';tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(results,indent=2)+'\n');tmp.replace(index)
    return results

def build_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('board',choices=['devices','power','digital','left','right','stack'])
    p.add_argument('--serial',help='AD3 serial number from devices')
    p.add_argument('--ad3-3v3',action='store_true',help='Explicitly use AD3 V+ at 3.3 V for digital J2.3; never in parallel with another supply')
    p.add_argument('--probe',type=probe_setting,default=(1,1),help='Scope probe attenuation per channel: 1 (default, direct flywires), 10 (both 10x probes), or two values such as 10,1 for scope 1 at 10x and scope 2 at 1x')
    p.add_argument('--resume',metavar='RUN_ID',help='Carry the leading PASS steps of an earlier run of this board (same PCB snapshot, limits and fixture) and repeat only the rest')
    p.add_argument('--plan',action='store_true',help='Print fixture plan without opening any device')
    p.add_argument('--simulate',action='store_true',help='Use synthetic data only; report can never be a hardware PASS')
    p.add_argument('--simulate-fault',choices=['wrong-clock','bad-rail','swapped-mux','stuck-channel','missing-tone'])
    p.add_argument('--output',type=Path,default=HERE/'results')
    return p

def validate_args(p,args):
    if args.simulate_fault and not args.simulate:p.error('--simulate-fault requires --simulate')
    if args.board=='power' and args.ad3_3v3:p.error('Power board has no +3.3 V inlet; omit --ad3-3v3')

def main(argv=None):
    p=build_parser();args=p.parse_args(argv);validate_args(p,args)
    if args.board=='devices':
        try:print(json.dumps(SDK().devices(),indent=2));return 0
        except InstrumentError as e:print(e,file=sys.stderr);return 2
    if args.plan:
        print(json.dumps({'common':PLANS['common'],**PLANS['boards'][args.board]},indent=2));return 0
    try:return Run(args).execute()
    except Exception as e:print(str(e),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
