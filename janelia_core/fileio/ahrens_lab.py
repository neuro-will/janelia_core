""" Tools for reading in Ahrens lab experimental data.

    William Bishop
    bishopw@hhmi.org
"""

import glob
import pathlib

import h5py
import numpy as np

import janelia_core.dataprocessing.dataset
import janelia_core.dataprocessing.dataset as dataset
from janelia_core.fileio.shared_lab import read_imaging_metadata
from janelia_core.fileio.shared_lab import find_images

# Constants for reading a stack frequency file
STACK_FREQ_STACK_FREQ_LINE = 0
STACK_FREQ_EXP_DURATION_LINE = 1
STACK_FREQ_N_IMAGES_LINE = 2


def read_exp(image_folder: pathlib.Path, ephys_folder: pathlib.Path = None, ephys_var_name: str = 'frame_swim',
             image_ext: str = '.h5', metadata_file: str = 'ch0.xml',
             stack_freq_file: str = 'Stack_frequency.txt', ephys_file : str = 'frame_swim.mat',
             verbose: bool = True) -> janelia_core.dataprocessing.dataset.DataSet:
    """Reads in Ahrens lab experimental data to a Dataset object.

    Args:
        image_folder: The folder holding the images, metadata file and stack frequency file.

        ephys_folder: The folder holder the ephys data.

        ephys_var_name: The variable name holding ephys data in ephys_file.

        image_ext: The extension to use when looking for image files.

        metadata_file: The name of the .xml file holding metadata.

        stack_freq_file: The name of the file holding stack frequency information.

        ephys_file: The name of the file holding ephys data.  If this is None, no ephys data will be loaded.

        verbose: True if progress updates should be printed to screen.

    Returns:
        A Dataset object.  A DataSet object representing the experiment.  The data dictionary will have an entry 'imgs'
        'imgs' containing the file names for the images. If ephys data was available, an entry 'ephys' will also contain
        the ephys data.  The metadata for the experiment will have an entry 'stack_freq_info' with the information from
        the stack frequency file.
    """

    # Read in all of the raw data
    metadata = read_imaging_metadata(image_folder / metadata_file)

    stack_freq_info = read_stack_freq(image_folder / stack_freq_file)

    image_names_sorted = find_images(image_folder, image_ext, image_folder_depth=0, verbose=verbose)

    n_images = len(image_names_sorted)
    time_stamps = np.asarray([float(i / stack_freq_info['smp_freq']) for i in range(n_images)])

    if ephys_file is not None:
        ephys_data = read_ephys_data(ephys_folder / ephys_file, ephys_var_name, verbose=verbose)
        n_ephys_smps = ephys_data.shape[0]
        if n_ephys_smps != n_images:
            raise (RuntimeError('Found ' + str(n_images) + ' image files but ' + str(n_ephys_smps) + ' ephys data points.'))
        ephys_dict = {'ts': time_stamps, 'vls': ephys_data}

    # Check to make we found the right number of images
    if n_images != stack_freq_info['n_images']:
        raise (RuntimeError('Found ' + str(n_images) + ' image files but stack frequency file specified ' +
                            str(stack_freq_info['n_images']) + ' time stamps.'))

    # Create an instance of Dataset
    im_dict = {'ts': time_stamps, 'vls': image_names_sorted}
    data_dict = {'imgs': im_dict}
    if ephys_file is not None:
        data_dict['ephys'] = ephys_dict

    metadata['stack_freq_info'] = stack_freq_info

    return dataset.DataSet(data_dict, metadata)


def read_ephys_data(ephys_file: pathlib.Path, var_name: str = 'frame_swim', verbose: bool = True):
    """ Reads in electophysiological data for an Ahrens lab experiment.

    Args:
        ephys_file: The path to the .mat file holding the data

        var_name: The name of the variable in the .mat file holding the
        ephys_data

    Returns:
        A numpy.ndarray with the data
    """
    if verbose:
        print('Reading ephys data.')

    with h5py.File(ephys_file) as f:
        data = f[var_name][:]
        data = data.T
        return data


def read_stack_freq(stack_freq_file: pathlib.Path):
    """ Reads in stack frequency inforation from file.

    Args:
        stack_freq_file: The file with stack frequency information.

    Returns:
        A dictionary with the stack frequency information.
    """

    with open(stack_freq_file, 'r') as f:
        txt_lines = f.readlines()

        smp_freq = float(txt_lines[STACK_FREQ_STACK_FREQ_LINE])
        exp_duration = float(txt_lines[STACK_FREQ_EXP_DURATION_LINE])
        n_images = int(txt_lines[STACK_FREQ_N_IMAGES_LINE])

        return {'smp_freq': smp_freq, 'exp_duration' : exp_duration, 'n_images' : n_images}
