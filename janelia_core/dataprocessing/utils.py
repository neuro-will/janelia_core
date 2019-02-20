""" Utilities for working with imaging data:

    William Bishop
    bishopw@hhmi.org
"""

import pathlib
import types

import dipy
import h5py
import numpy as np
import os
import pyspark


from janelia_core.fileio.exp_reader import read_img_file

def get_image_data(image, img_slice: slice = slice(None, None, None), h5_data_group: str = 'default') -> np.ndarray:
    """ Gets image data for a single image.

    This is a wrapper that allows us to get image data for a single image from a file or from a numpy array
    seamlessly in our code.  If image is already a numpy array, image is simply returned
    as is.  Otherwise, image is assumed to be a path to a image which is opened and the data
    is loaded and returned as a numpy array.

    Args:
        image: Either a numpy array or path to the image.

        img_slice: The slice of the image that should be returned

        h5_data_group: The hdfs group holding image data in h5 files.

    Returns: The image data.
    """
    if isinstance(image, np.ndarray):
        return image[img_slice]
    else:
        return read_img_file(pathlib.Path(image), img_slice=img_slice, h5_data_group=h5_data_group)


def get_processed_image_data(images: list, func: types.FunctionType = None, img_slice = slice(None, None, None),
                             func_args: list = None, h5_data_group='default', sc: pyspark.SparkContext = None) -> list:
    """ Gets processed image data for multiple images.
    
    This is a wrapper that allows retrieving images from files or from numpy arrays,
    applying light processing independently to each image and returning the result.  
    
    Args:
        images: A list of images.  Each entry is either a numpy array or a path to an image file.
        
        func: A function to apply to each image.  If none, images will be returned unaltered.  Should accept input
        of the form func(image: np.ndarray, **keyword_args)

        img_slice: The slice of each image that should be returned before any processing is applied

        func_args: A list of extra keyword arguments to pass to the function for each image.  If None, no arguments
        will be passed.

        h5_data_group: The hdfs group holding image data in h5 files.
        
        sc: An optional pySpark.SparkContext object to use in speeding up reading of images.
        
    Returns: The processed image data as a list.  Each processed image is an entry in the list. 
    """

    if func is None:
        def func(x):
            return x

    if func_args is None:
        n_images = len(images)
        func_args = [dict()]*n_images

    if sc is None:
        return [func(get_image_data(img, img_slice=img_slice, h5_data_group=h5_data_group), **args) for
                img, args in zip(images, func_args)]
    else:
        def _process_img(input):
            img = input[0]
            args = input[1]
            return func(get_image_data(img, img_slice=img_slice, h5_data_group=h5_data_group), **args)

        return sc.parallelize(zip(images, func_args)).map(_process_img).collect()


def write_planes_to_files(planes: np.ndarray, files: list,
                          base_planes_dir: pathlib.Path, plane_suffix: str='plane',
                          skip_existing_files=False, sc: pyspark.SparkContext=None,
                          h5_data_group='data') -> list:
    """ Extracts one or more planes from image files, writing planes to seperate files.

    Args:
        planes: An array of indices of planes to extract.

        files: A list of original image files to pull planes from.

        base_planes_dir: The base directory to save plane files into.  Under this folder, seperate subfolders
        will be saved for each plane.

        plane_suffix: The suffix to append to the file name to indicate the file contains just one plane.

        skip_existing_files: If true, if a file for an extracted plane is found, it will not be overwritten.
        If false, then errors will be thrown if files for extracted planes are found to already exist. Setting
        this to true can be helpful if there is a need to run this function a second time to recover from an
        error.

        sc: An optional spark context to use to write files in parallel.

        h5_data_group: The h5_data_group that original images are stored under if reading in .h5 files.

    Returns:
        A list of the directories that images for each plane are saved into.
    """
    if not os.path.exists(base_planes_dir):
        os.makedirs(base_planes_dir)

    plane_dirs = []
    for plane in planes:
        plane_dir = base_planes_dir / (plane_suffix + str(plane))
        if not os.path.exists(plane_dir):
            os.makedirs(plane_dir)
        plane_dirs.append(plane_dir)

    if sc is None:
        for file in files:
            write_planes_for_one_file(file, planes, plane_dirs, '_' + plane_suffix, skip_existing_files,
                                      h5_data_group=h5_data_group)
    else:
        def write_plane_wrapper(file):
            write_planes_for_one_file(file, planes, plane_dirs, '_' + plane_suffix, skip_existing_files,
                                      h5_data_group=h5_data_group)
        sc.parallelize(files).foreach(write_plane_wrapper)

    return plane_dirs


def write_planes_for_one_file(file: pathlib.Path, planes: np.ndarray, plane_dirs: list,
                              plane_suffix: str='plane', skip_existing_files=False,
                              h5_data_group='default'):
    """ Writes specified planes from a 3d image file to separate .h5 files.

    The new files will have the same name as the original with an added suffix to indicate they contain
    just one plane.

    Args:
        planes: An array of indices of planes to extract.

        file: The original image file to pull planes from.

        plane_dirs: List of directories to save the file for each file into.

        plane_suffix: The suffix to append to the file name to indicate the file contains just one plane.

        skip_existing_files: If true, if a file for an extracted plane is found, it will not be overwritten.
        If false, then errors will be thrown if files for extracted planes are found to already exist. Setting
        this to true can be helpful if there is a need to run this function a second time to recover from an
        error.

        h5_data_group: The h5_data_group that original images are stored under if reading in .h5 files.

    """
    # Create names of the files the planes will be saved into
    new_file_name = file.name
    suffix_len = len(file.suffix)
    new_file_name = new_file_name[0:-suffix_len]
    plane_file_paths = [plane_dirs[i] / (new_file_name + plane_suffix + str(planes[i]) + '.h5')
                        for i in range(len(plane_dirs))]

    # Check if our files exist
    n_planes = len(planes)
    existing_plane_files = np.empty(n_planes, np.bool)
    some_plane_files_exist = False
    all_plane_files_exist = True
    for i, plane_file_path in enumerate(plane_file_paths):
        plane_file_exists = os.path.exists(plane_file_path)
        existing_plane_files[i] = plane_file_exists
        some_plane_files_exist = some_plane_files_exist or plane_file_exists
        all_plane_files_exist = all_plane_files_exist and plane_file_exists
    # Throw in an error if appropriate
    if some_plane_files_exist and not skip_existing_files:
        raise (RuntimeError('Files for extracted planes already exist for 3d image file ' + str(file)))

    # Write all planes that we need to to file
    if not all_plane_files_exist:
        image_3d = read_img_file(file, h5_data_group=h5_data_group)

        # Write planes to file
        for i, plane_file_path in enumerate(plane_file_paths):
            data_in_plane = np.expand_dims(image_3d[planes[i], :, :], 0)
            if not existing_plane_files[i]:
                with h5py.File(plane_file_path, 'w') as new_file:
                    new_file.create_dataset('data', data_in_plane.shape, data_in_plane.dtype, data_in_plane)

