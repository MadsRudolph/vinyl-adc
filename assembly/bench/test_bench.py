"""Offline regression tests. No test opens USB or turns on an instrument."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from analysis import frequency,sine_fit,channel_stream,clock_delay_ns
from dwf_device import AD3,InstrumentError,I
from run import main

class AnalysisTests(unittest.TestCase):
    def test_missing_clock_is_not_zero_error(self):
        with self.assertRaises(ValueError):frequency(np.zeros(4096),50e6)
    def test_frequency_uses_real_sample_rate(self):
        rate=62.5e6;t=np.arange(32768)/rate
        self.assertAlmostEqual(frequency((t*1536000)%1<.5,rate)/1536000,1,places=3)
    def test_sine_fit_rejects_dc_and_wrong_frequency(self):
        t=np.arange(1200)/12000
        self.assertEqual(sine_fit(np.ones(1200),12000,1000)['r2'],0)
        self.assertLess(sine_fit(np.sin(2*np.pi*1200*t),12000,1000)['r2'],.01)
        self.assertGreater(sine_fit(.15*np.sin(2*np.pi*1000*t+.8)+.4,12000,1000)['r2'],.999)
    def test_inverted_pi_clock_is_not_accepted_as_delay(self):
        t=np.arange(32768)/50e6;x=((t*3072000)%1<.5).astype(np.uint8)
        self.assertGreater(abs(clock_delay_ns(x,1-x,50e6)),120)
    def test_plan_probe_nets_match_pcb(self):
        root=Path(__file__).resolve().parents[1]
        plans=json.loads((root/'bench/plans.json').read_text())['boards']
        boards=json.loads((root/'generated/boards.json').read_text())['boards']
        for name,plan in plans.items():
            b=boards['channel_l' if name in ['left','right'] else name]
            for step in plan['steps']:
                for c in step['connections']:
                    part=next(p for p in b['parts'] if p['ref']==c['ref'])
                    pad=next(p for p in part['pads'] if p['pin']==c['pin'])
                    self.assertEqual(pad['net'],c['net'],(name,step['id'],c))
    def test_insufficient_channel_record_rejected(self):
        with self.assertRaises(ValueError):channel_stream(np.zeros(20,dtype=np.uint16),4e6)

class RunnerTests(unittest.TestCase):
    def run_fixture(self,board,fault=None):
        with tempfile.TemporaryDirectory() as d:
            args=[board,'--simulate','--output',d]
            if fault:args+=['--simulate-fault',fault]
            with contextlib.redirect_stdout(io.StringIO()):code=main(args)
            report=json.loads(next(Path(d).glob('*/report.json')).read_text())
            self.assertEqual(report['status'],'SIMULATED');self.assertTrue(report['simulated'])
            self.assertTrue(report['sources']);self.assertTrue(report['limits_sha256'])
            return code,report
    def test_healthy_sequences(self):
        for board in ['power','digital','left','right']:
            with self.subTest(board=board):
                code,r=self.run_fixture(board)
                self.assertEqual(code,0);self.assertEqual(r['simulation_outcome'],'PASS')
                self.assertTrue(all(s['status']=='PASS' for s in r['steps']))
    def test_faults_fail_and_stop(self):
        for board,fault in [('power','bad-rail'),('digital','wrong-clock'),('digital','swapped-mux'),('left','stuck-channel'),('right','missing-tone')]:
            with self.subTest(board=board,fault=fault):
                code,r=self.run_fixture(board,fault)
                self.assertEqual(code,1);self.assertEqual(r['simulation_outcome'],'FAIL')
                self.assertEqual(r['steps'][-1]['status'],'FAIL')
    def test_plan_never_constructs_instrument(self):
        with patch('run.AD3',side_effect=AssertionError('Must not open hardware')),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(['left','--plan']),0)

class DriverTests(unittest.TestCase):
    def device(self):
        with patch('dwf_device.SDK'):device=AD3()
        device.handle=I(123);return device
    def test_all_cleanup_attempted_after_disconnect(self):
        d=self.device();calls=[]
        def call(name,*args):
            calls.append(name)
            if name=='AnalogOutReset':raise InstrumentError('USB disconnected')
        d.call=call;d.close()
        self.assertIn('AnalogIOEnableSet',calls);self.assertEqual(calls[-1],'DeviceClose');self.assertTrue(d.cleanup_errors)
    def test_record_loss_is_fatal(self):
        d=self.device()
        def call(name,*args):
            if name=='DigitalInInternalClockInfo':args[0]._obj.value=100e6
            elif name=='DigitalInDividerGet':args[0]._obj.value=25
            elif name=='DigitalInStatus':args[1]._obj.value=3
            elif name=='DigitalInStatusRecord':
                args[0]._obj.value=100;args[1]._obj.value=1;args[2]._obj.value=0
        d.call=call
        with self.assertRaisesRegex(InstrumentError,'lost 1'):d.logic(4e6,.1)
    def test_output_range_guard(self):
        d=self.device()
        with self.assertRaises(ValueError):d.wave('square',192000,3,3)

if __name__=='__main__':unittest.main()
