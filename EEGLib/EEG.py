import mne
import scipy
from scipy import io
from mne import Epochs
from mne.channels import Layout
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt

from EEGLib.EE385VMatFile import EE385VMatFile
from EEGLib.Feature.STFTFeature import STFTFeature

channel_names_spellers = {
    'eeg:1' : 'Fz',
    'eeg:2' : 'FC3',
    'eeg:3' : 'FC1',
    'eeg:4' : 'FCz',
    'eeg:5' : 'FC2',
    'eeg:6' : 'FC4',
    'eeg:7' : 'C3',
    'eeg:8' : 'C1',
    'eeg:9' : 'Cz',
    'eeg:10' : 'C2',
    'eeg:11' : 'C4',
    'eeg:12' : 'CP3',
    'eeg:13' : 'CP1',
    'eeg:14' : 'CPz',
    'eeg:15' : 'CP2',
    'eeg:16' : 'CP4'
}

class EEG:
    def __init__(self):
        self.__gdf = mne.io.Raw
        self.__mat = EE385VMatFile
        self.__eeg = mne.io.Raw
        self.__trigger = mne.io.Raw

    def open(self, filepath, channel_names=None):
        '''
        @param filepath: Path to GDF or .MAT file
        @param channel_names: Name of the Channels, defaults to numeric
        @:return Tuple (EEG data scaled to V, trigger, EE385VMatFile)
        '''

        path = Path(filepath)

        gdf_path = os.path.basename(filepath)
        mat_path = os.path.basename(filepath)
        if path.suffix == '.gdf':
            gdf_path = filepath
            mat_path = str(path.parent) + '/' + str(path.stem) + '.mat'
        elif path.suffix == '.mat':
            mat_path = filepath
            gdf_path = str(path.parent) + '/' + str(path.stem) + '.gdf'
        else:
            raise IOError('Filepath needs to be either a .gdf or .mat file')

        gdf = mne.io.read_raw_gdf(gdf_path, preload=True)

        if channel_names:
            gdf.rename_channels(channel_names)

        self.__gdf = gdf
        # Scale to microvolts, see: https://github.com/mne-tools/mne-python/issues/5539
        self.__eeg, self.__trigger = self.splitTrigger(trigger='trigger')
        self.__eeg = self.__eeg.apply_function(lambda x: x / 1e6)
        self.__mat = EE385VMatFile(mat_path)
        return (self.__eeg, self.__trigger, self.__mat)

    def getChannelNames(self):
        '''
        :return: the channel names as a list of strings
        '''
        return self.__gdf.ch_names

    def printChannels(self):
        '''
        Convenience function to print the channel names
        :return:
        '''
        print('Availible Channels: ' + str(self.getChannelNames()))

    def getRawEEG(self, channels=['']):
        '''
        Packages https://mne.tools/stable/generated/mne.io.Raw.html#mne.io.Raw.get_data

        :param channels: String list of EEG channels to fetch
        :return: Tuple of ([EEG Channel, Data], Time)
        '''
        if channels == ['']:
            return self.__gdf.get_data(return_times=True)
        else:
            return self.__gdf.get_data(picks=channels, return_times=True)

    def splitTrigger(self, trigger='trigger'):
        '''
        Splits the trigger from the EEG signal

        :param trigger: Name of the trigger. i.e. trigger if the channel is trigger:1
        :return: Tuple (Data without Trigger, Trigger)
        '''
        for channels in self.getChannelNames():
            if trigger in channels:
                trigger = self.__gdf.get_data(picks=channels)
                data_no_trigger = self.__gdf.drop_channels(channels)
                return (data_no_trigger, trigger)


    def getEEGTrials(self, pretime=2, posttime=4, error=True, gdf=mne.io.Raw, offset=False, offset_value=30, plot=False, plot_trigger=0):
        '''

        :param pretime: Pre Trigger time in seconds. i.e. 2 -> T - 2s
        :param posttime: Post Trigger time in seconds
        :param error: Select trigger events where the error is either True or False
        :param gdf: mne.io.Raw gdf file
        :param plot: If True, plot some example data
        :param offset_value: Value, in microvolts, to add to each channel, used for visualization
        :param offset: Adds a 30uV offset to each EEG channel, easier for visualization, default is False
        :param plot_trigger: Selects the trigger event to display, 0 by default
        :return: Numpy array of (Trigger Event, EEG Channels, Samples)
        '''

        if gdf == mne.io.Raw:
            gdf_use = self.__gdf
        else:
            gdf_use = gdf

        pretime_s = self.timeToSample(pretime)*-1
        posttime_s = self.timeToSample(posttime)

        error_array, time = self.identifyErrors()

        time = self.timeArrayToSampleArray(time, 512)

        gdf_array = None

        for x in range(time.shape[0]):
            e = error_array[x]
            if e is not np.NaN:
                if e == error:
                    t = time[x]
                    start = int(t + pretime_s)
                    stop = int(t + posttime_s)
                    gdf_subset = gdf_use.get_data(start=start, stop=stop)

                    if gdf_subset.shape[1] == (pretime_s*-1 + posttime_s):
                        if plot or offset:
                            for y in range(gdf_subset.shape[0]):
                                gdf_subset[y, :] += y*offset_value*1e-6

                        if gdf_array is None:
                            gdf_array = np.expand_dims(gdf_subset, 0)
                        else:
                            gdf_subset = np.expand_dims(gdf_subset, 0)
                            gdf_array = np.append(gdf_array, gdf_subset, axis=0)

        if plot:
            slice = gdf_array[plot_trigger, :, :]
            plt.plot(slice.squeeze().T)
            plt.show()

        return gdf_array

    def CARFilter(self, eegVolume=np.ndarray):
        '''
        Common average reference filter. Takes all EEG in the given dataset and averages them in time and then
        subtracts the average from each EEG channel

        :param eegVolume: Numpy array of shape (trigger, eeg, time)
        :return: eegVolume with the applied CAR Filter
        '''
        filtered = np.zeros(eegVolume.shape)
        for trigger in range(eegVolume.shape[0]):
            eeg_slice = eegVolume[trigger, :, :]
            global_avg = np.mean(eeg_slice, axis=0)
            eeg_slice -= global_avg
            filtered[trigger, :, :] = eeg_slice

        return filtered

    def grandAverage(self, eegVolume=np.ndarray):
        '''
        Takes the average of each EEG channel across all trigger events.

        :param eegVolume: Numpy array of shape (trigger, eeg, time)
        :return: Numpy array of (eeg, time)
        '''
        grand_avg = np.mean(eegVolume, axis=0)
        return grand_avg

    def grandVariance(self, eegVolume=np.ndarray):
        '''
        Takes the variance of each EEG channel across all trigger events.

        :param eegVolume: Numpy array of shape (trigger, eeg, time)
        :return: Numpy array of (eeg, time)
        '''
        grand_var = np.var(eegVolume, axis=0)
        return grand_var

    def power(self, eegVolume=np.ndarray):
        pow = eegVolume**2
        pow = np.sqrt(pow)
        return pow

    def addOffset(self, eegVolume=np.ndarray, value=5e-6):
        for x in range(eegVolume.shape[0]):
            eegVolume[x, :] += value*x
        return  eegVolume

    def getAlpha(self):
        '''
        Filters the data for the alpha range of frequencies

        :return:
        '''
        return self.__gdf.filter(l_freq=8, h_freq=12)

    def getTheta(self):
        return self.__gdf.filter(l_freq=1, h_freq=8)

    def getBeta(self):
        return self.__gdf.filter(l_freq=12, h_freq=30)

    def timeToSample(self, time, fs=512):
        '''
        Converts single time in seconds to a sample point.

        :param time: Time in seconds
        :param fs: Sampling frequency
        :return: Time in samples
        '''
        return time*fs

    def timeArrayToSampleArray(self, time=np.ndarray, fs=512):
        '''
        Converts an array of times to an array of samples

        :param time: ndarray of time in seconds
        :param fs: Sampling frequency, default is 512 samples per second
        :return: ndarray of sample points
        '''
        return np.apply_along_axis(self.timeToSample, 0, time, fs=fs).astype(np.uint)

    def identifyErrors(self):
        '''
        Scans the matlab states array and identifies when the intent of the user differed from the actual
        results.

        :return: Tuple of 1D ndarrays (Error, Time of Error)
        '''
        annotation_time = self.__gdf.annotations.onset[1:]
        annotation_time = annotation_time[:-1]
        annotation_desc = self.__gdf.annotations.description[1:]
        annotation_desc = annotation_desc[:-1]
        intention = self.__mat.actions()
        states = self.__mat.states()[:, 1:]
        states = states[:, :len(intention)]
        error = []
        for x in range(states.shape[1]):
            if states[0, x] < 0:
                error.append(np.NaN)
            elif states[0, x] != states[1, x]:
                error.append(True)
            else:
                error.append(False)
        total_error = np.sum(error)
        return (error, annotation_time)


if __name__ == "__main__":
    e = EEG()
    (eeg, trig, mat) = e.open(
        '/home/amcelroy/Code/EE385V/BCI Course 2020/ErrPSpeller/Subject1/Offline/ad4_raser_offline_offline_171110_170617.gdf',
        channel_names=channel_names_spellers
    )

    theta = e.getTheta()

    error = e.getEEGTrials(
        pretime=.5,
        posttime=1,
        error=True,
        plot=False,
        gdf=theta,
    )
    no_error = e.getEEGTrials(pretime=.5, posttime=1, error=False, plot=False, gdf=theta)

    error = e.CARFilter(error)
    #error = e.power(error)
    no_error = e.CARFilter(no_error)
    #no_error = e.power(no_error)

    e.printChannels()
    # alpha = e.getAlpha()
    # alpha.plot(decim=1)

    averaged_error = np.mean(error, axis=0)
    averaged_error = e.addOffset(averaged_error, 1e-6)

    averaged_no_Error = np.mean(no_error, axis=0)
    averaged_no_Error = e.addOffset(averaged_no_Error, 1e-6)

    stftfeature = STFTFeature()
    spectro, freq, time, grand_avg, grand_var = stftfeature.extract(error, plot=False, window=512, overlap=468,
                     trigger_event=[np.arange(error.shape[0])], pre_trigger_time=.5, fs=512,
                     ac_filter=True)


    plt.imshow(grand_avg[9])
    plt.show()

    fig, ax = plt.subplots(1, 2)

    ax[0].plot(averaged_error.T)
    ax[0].set_title('Grand Average With Error')
    ax[1].plot(averaged_no_Error.T)
    ax[1].set_title('Grand Average With No Error')
    plt.show()

    theta = e.getTheta()
    theta.plot(decim=1)
    #gdf.printChannels()
    channels = e.getRawEEG()
    mat.targetLetter()
    mat.ringBuffer()
    #print(gdf.info)
