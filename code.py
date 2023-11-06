import pickle
from pathlib import Path
import time

import numpy as np

import pyvisa

from pipython import datarectools
from pipython.pidevice.gcscommands import GCSCommands
from pipython.pidevice.gcsmessages import GCSMessages
from pipython.pidevice.interfaces.pisocket import PISocket

from KS33500B import *
from pi_controller import *

def get_pi_controller_data(drec):

    drec.arm()
    drec.wait()
    header, data = drec.read()

    data = np.array(data)

    return header, data

def set_pi_controller(drec, numvalues=8192, sampletime=1e-6):
    '''
    drec.sources = [1, 2, 'A', 'B']

    drec.options = [datarectools.RecordOptions.PIEZO_VOLTAGE_7,
                    datarectools.RecordOptions.PIEZO_VOLTAGE_7,
                    datarectools.RecordOptions.ACTUAL_POSITION_2,
                    datarectools.RecordOptions.ACTUAL_POSITION_2]
    '''

    drec.sources = ['A', 'B', 1, 2]

    drec.options = [datarectools.RecordOptions.ACTUAL_POSITION_2,
                    datarectools.RecordOptions.ACTUAL_POSITION_2,
                    datarectools.RecordOptions.PIEZO_VOLTAGE_7,
                    datarectools.RecordOptions.PIEZO_VOLTAGE_7]

    drec.trigsources = datarectools.TriggerSources.TRIGGER_IMMEDIATELY_4

    drec.numvalues = numvalues
    drec.sampletime = sampletime

def main():

    # frequency range that is being iterated over
    freq_inc = 50
    freq_vals = np.arange(100, 2500+freq_inc, freq_inc)

    # voltage range that is being iterated over
    volt_inc = 1
    volt_vals = np.arange(1, 1+volt_inc, volt_inc)

    # data folder configuration
    data_folder = Path('/Users/jsn/landing/analyses/gpi2_modulation_stage_analysis_continued/data/pi_controller_data/')
    data_folder.mkdir(parents=True, exist_ok=True)

    # need this to read the connected devices over USB
    rm = pyvisa.ResourceManager()

    # Keysight AWG initialization

    # usb-based name
    #ks_name = 'USB0::0x0957::0x2607::MY59003494::INSTR' # awg
    #ks_name = rm.list_resources()[-1]

    # ip-based name
    ks_ip = '132.239.146.78'
    ks_name  = 'TCPIP::{}'.format(ks_ip)
    ks = rm.open_resource(ks_name) # need this to hand off the resources to a wrapper class

    awg = KS33500B(ks, abbreviated=True)

    ip = '132.239.146.72'
    with PISocket(host=ip, port=50000) as gateway:
        messages = GCSMessages(gateway)
        pidevice = GCSCommands(messages)
        drec = datarectools.Datarecorder(pidevice)

        print('Connected to PI Controller!')
        print(pidevice.qIDN())

        set_pi_controller(drec)

        # turn all the front panel outputs off to begin just in case
        awg.output.output(1 , 'OFF')
        awg.output.output(2 , 'OFF')
        awg.output.sync('OFF')
        awg.frequency.couple(1, 'ON')
        awg.frequency.couple(2, 'ON')

        i=0
        for volt in volt_vals:
            for freq in freq_vals:

                # limit the floats to 2 decimal points, should be good enough
                freq_str = '{:.6f} HZ'.format(freq)
                volt_str = '{:.6f} VPP'.format(volt)
                off_str = '{:.6f} V'.format(2.5) # we want the largest offset, (4.5V is max) to be in the middle of the range!

                # apply the sinusoid functions and couple the frequencies so they stay in sync
                awg.apply.sinusoid(1, [freq_str, volt_str, off_str])
                awg.apply.sinusoid(2, [freq_str, volt_str, off_str])

                # this is the calibrated phase value, add the corrections
                awg.phase.phase(2, 90)

                # synchronize every time we change the phase!
                # this is important! Might have to continuously send synchronization commands if imaging for a long time
                awg.phase.synchronize(1)
                awg.phase.synchronize(2)

                awg.output.output(1 , 'ON')
                awg.output.output(2 , 'ON')
                awg.output.sync('ON')

                time.sleep(2)

                header, data = get_pi_controller_data(drec)
                with open(data_folder / 'header_{:04}.pickle'.format(i), 'wb') as f:
                    pickle.dump(header, f)
                np.save(data_folder / 'raw_data_{:04}.npy'.format(i), data)
                i+=1

                # turn everything off at the end
                awg.output.output(1 , 'OFF')
                awg.output.output(2 , 'OFF')
                awg.output.sync('OFF')

if __name__=='__main__':
    main()