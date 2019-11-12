""" Tools for generating images.

    William Bishop
    bishopw@hhmi.org

"""

import copy
from typing import Sequence

import numpy as np
from PIL import Image
from PIL import ImageDraw


def alpha_composite(dest: np.ndarray, src: np.ndarray) -> np.ndarray:
    """ Performs alpha compositing with two RGBA images with alpha-premultiplicaiton applied.

    All values should be floating point in the range 0 - 1.

    Standard RGBA values of the form [R_s, G_s, B_s, A_s] can be converted to a
    pre-multiplied RGBA value as [R_s*A_s, G_s*A_s, B_s*A_s, A_s].

    Good notes can be found at: https://ipfs.io/ipfs/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/wiki/Alpha_compositing.html

    Args:
        dest: The bottom image of shape d_x*d_y*4

        src: The top image.  Must be of the same shape as dest_img.

    Returns: Nothing.  The dest array will be modified.

    """

    src_alpha = np.expand_dims(src[:, :, 3],2)
    dest[:] = src + dest*(1 - src_alpha)


def standard_rgba_to_premultiplied(img: np.ndarray) -> np.ndarray:
    """ Converts between standard and pre-multiplied RGBA representations.

    Args:
        img: Input image in standard RGBA format of shape d_x*d_y*4

    Returns: Nothing.  The image is modified in place.
    """

    alpha = np.expand_dims(img[:, :, 3], 2)
    img[:, :, 0:3] = img[:, :, 0:3]*alpha


def premultiplied_rgba_to_standard(img: np.ndarray) -> np.ndarray:
    """ Converts between pre-multiplied and standard RGBA representations.

    Args:
        img: Input image in pre-multiplied RGBA format of shape d_x*d_y*4

    Returns:
        img: Nothing.  The image is modified in place.
    """

    alpha = np.expand_dims(img[:, :, 3], 2)
    alpha_mask = img[:,:,3] != 0
    img[alpha_mask, 0:3] = img[alpha_mask, 0:3]/alpha[alpha_mask,:]

def generate_additive_dot_image(image_shape: Sequence[int], dot_ctrs: np.ndarray, dot_vls: np.ndarray,
                                dot_p_axis_lengths: Sequence[int]) -> np.ndarray:
    """
    Geneates a 3-d image of the sum of values in ellipsoids.


    Generates an image by associating an ellipsoid with a set of 3-d locations. Each of these locations
    has an associated value.  A pixel value in the final image is simply the sum of all all values associated
    with locations with ellipsoids that contain that pixel.

    Args:
        image_shape: The shape of the image to generate. Must be of length 3.

        dot_ctrs: The location of each ellipsoid center.  dot_ctrs[i,:] is the location
        for dot i.

        dot_vls: The value to associate with the locations.  dot_vls[i] is associated with the location
        dot_ctrs[i, :]

        dot_p_axis_lengths: The lengths of the principle axes of the ellipsoids to generate.
        The value of dot_p_axis_lengths[j] is the length for dimension j. dot_p_axis_lengths must be odd.

    Returns:
        img: The generated image.  Any pixel outside of an ellipsoid will have a value of nan.

    Raises:
        ValueError: If image_shape is not of length 3.
    """

    if len(image_shape) != 2:
        raise(ValueError('image must be 3-d'))

    for l in dot_p_axis_lengths:
        if l % 2 != 1:
            raise(ValueError('dot_p_axis_lengths must all be odd'))

    # Initialize the base image, setting all values initially to nan
    img = np.zeros(image_shape)
    img[:] = np.nan

    # Generate the basic ellipsoid we convolve throughout the image
    base_e_im_dims = [2*l for l in dot_p_axis_lengths]
    base_e_im = np.zeros(base_e_im_dims)




def generate_dot_image(image_shape: Sequence, dot_ctrs: np.ndarray, dot_clrs: np.ndarray,
                       dot_diameter: int) -> np.ndarray:
    """ Generates an image of dots over a transparent background.

    All position/size units are in pixels.

    Dots are layered according to their order in dot_ctrs with dot_ctrs[0,:] on the bottom.

    Args:
        image_shape: The [width, height] of the image in pixels

        dot_ctrs: dot_ctrs[i,:] gives the position of the center of the i^th dot

        dot_clrs: dot_clrs[i,:] gives the RGBA color of the i^th dot

        dot_diameter: The diameter of the dot to generate in pixel.  Must be an odd number.

    Returns:
        img: The generated image of shape [image_shape[0], image_shape[1], 4] where the last dimension is the RGBA
        value of each pixel.

    """

    img_w = image_shape[0]
    img_h = image_shape[1]

    # Run some checks
    if not isinstance(dot_diameter, int):
        raise(ValueError('dot_diameter must be an integer'))
    if dot_diameter % 2 != 1:
        raise(ValueError('dot diameter must be an odd number'))

    if any((dot_ctrs[:,0] < 0) | (dot_ctrs[:,0] > (img_w - 1))):
        raise(ValueError('All centers must be within image boundaries.'))
    if any((dot_ctrs[:,1] < 0) | (dot_ctrs[:,1] > (img_h - 1))):
        raise(ValueError('All centers must be within image boundaries.'))

    # ==================================================================================================
    # Generate the mask of the template dot we will use
    dot_img = Image.new('1', (dot_diameter, dot_diameter))
    dot_drawer = ImageDraw.Draw(dot_img)
    dot_drawer.ellipse((0, 0, dot_diameter, dot_diameter), 1)
    dot_mask = np.expand_dims(np.array(dot_img),2)

    # ==================================================================================================
    # Place the dots
    dot_ctrs_rnd  = np.round(dot_ctrs).astype('int')

    # Pad the image we will construct to account for edge effects
    img = np.zeros([image_shape[0] + dot_diameter - 1, image_shape[1] + dot_diameter - 1, 4])
    offset = np.floor(dot_diameter / 2).astype('int')

    # Premultiply alpha colors
    dot_clrs_pm = dot_clrs.copy()
    dot_clrs_pm[:, 0:3] = dot_clrs_pm[:, 0:3]*np.expand_dims(dot_clrs[:,3], 1)

    n_dots = dot_ctrs.shape[0]
    for d_i in range(n_dots):

        ctr_i = dot_ctrs_rnd[d_i, :] + offset
        dot_i = dot_mask*dot_clrs_pm[d_i, :]

        dot_slice_0 = slice(ctr_i[0] - offset, ctr_i[0] + offset + 1)
        dot_slice_1 = slice(ctr_i[1] - offset, ctr_i[1] + offset + 1)

        alpha_composite(img[dot_slice_0, dot_slice_1, :], dot_i)
        #print(img[dot_slice_0, dot_slice_1, 0])


    # ==================================================================================================

    # Convert to standard RGBA format
    premultiplied_rgba_to_standard(img)

    # Remove padding from the image
    img = img[offset:-offset, offset:-offset, :]

    return img


def generate_image_from_fcn(f, dim_sampling: Sequence[Sequence]):
    """ Generates a multi-d image from a function.

    The main use for this function is generating images for visualization.

    Args:
        f: The function to plot.

        dim_sampling: Each entry of dim_sampling specifies how to sample a dimension in the
        domain of the fuction.  Each entry is of the form [start, stop, int] where start and
        and stop are the start and stop of the range of values to sample from and int
        is the interval values are sampled from.

    Returns:

        im: The image

        coords: A list of coordinates along each dimension the function was sampled at.

    """

    # Determine coordinates we will sample from along each dimension
    coords = [np.arange(ds[0], ds[1], ds[2]) for ds in dim_sampling]
    n_coords_per_dim = [len(c) for c in coords]

    # Form coordinates of each point we will sample from in a single numpy array
    grid = np.meshgrid(*coords, indexing='ij')
    n_pts = grid[0].size
    flat_grid = np.concatenate([g.reshape([n_pts,1]) for g in grid], axis=1)

    # Evaluate the function
    y = f(flat_grid)

    # Shape y into the appropriate image size
    im = y.reshape(n_coords_per_dim)

    return [im, coords]


def generate_binary_color_rgba_image(a: np.ndarray, neg_clr: Sequence[float] = None, pos_clr: Sequence[float] = None):
    """ Generates an RGBA image of two colors from a 2-d numpy array.

    Negative values will be one color while positive values will be another.

    The alpha channel will be equal to the absolute value of entries of a, so all values of a must be in [-1, 1].

    The negative color will be assigned to entries strictly less than 0, while the positive channel will be assigned
    to entries greater than or equal to 0.

    Args:
        a: The array to binarize.

        neg_clr: A sequence of floats specifying the RGB values for the negative color.  All value should in [0, 1].
        If None, the negative color will be red.

        pos_clr: A sequence of floats specifying the RGB values for the positive color.  All value should in [0, 1].
        If None, the positive color will be green.

    Returns:
        im: The image of shape [a.shape[0], a.shape[1], 4]

    Raises:
         ValueError: If any entry in a is outside of [-1, 1]
         ValueError: If a is not a 2-d array.
    """

    if np.any(np.abs(a) > 1):
        raise(ValueError('All values in a must be in the range [-1, 1].'))

    if a.ndim != 2:
        raise(ValueError('Input a must be a 2-d array.'))

    im = np.zeros([a.shape[0], a.shape[1], 4])

    if neg_clr is None:
        neg_clr = np.asarray([1, 0, 0])
    else:
        neg_clr = np.asarray(neg_clr)

    if pos_clr is None:
        pos_clr = np.asarray([0, 1, 0])
    else:
        pos_clr = np.asarray(pos_clr)

    neg_vls = a < 0
    im[neg_vls, 0:3] = neg_clr

    pos_vls = a >= 0
    im[pos_vls, 0:3] = pos_clr

    im[:,:,3] = np.abs(a)

    return im


def max_project_pts(dot_positions: np.ndarray, dot_vls: np.ndarray, box_position: np.ndarray,
                    n_divisions: np.ndarray, dot_dim_width: np.ndarray) -> np.ndarray:
    """ Assigns a radius to points in 2-d space to make dots.  Then generates an image of max dot values in a grid.

    The motivation for this function is that there are times when physical objects in space (such as neurons) have
    been represented as finite points.  In these cases, we might desire to visualize how physical properties associated
    with each object are distributed in space.  There are three challenges we face when doing this:

    1) How to visualize a point.  We solve this by adding a radius to the points to make dots.

    2) How to make sense of over-lapping dots.  We do this by taking a "max projection" of the dots - that is
    at each point in space, we keep the value associated with the largest magnitude (so sign doesn't matter).

    3) How to go from continuous space to discrete space, so we can make images.  We solve this by allowing the
    user to specify a grid, defining discrete points in space we want to calculate a value for.

    The final question we need to consider is what to do with points in space that have no dot in them?  In this
    case, we will return an nan value.

    Args:

        dot_positions: The positions of dots, each column is a dimension.  Values must be floating point.

        dot_vls: The values associated with each point.  A 1-d array.

        box_position: The position of a box we define the grid in.  box_position[0,0] is the start of the side for
        dimension 0 and box_position[1,0] is the end of the side for dimension two.  box_position[:,1] contains the
        start and end of the side for dimension 1.

        n_divisions: The number of divisions to use for the grid.  n_divisions[i] is the number of divisions for
        dimension i.

        dot_dim_width: We allow dots to be ellipses.  dot_dim_width[i] is the width of a dot in dimension i.

    Returns:

        im: The final image, of shape n_divisions.

        inds: Same shape as im.  inds[i,j] is the index of the dot in dot_vls that the value of im[i,j] came from.
        Entries in im with nan values will also have nan values in inds.

    Raises:
        ValueError: If dot positions are not floating point.
        ValueError: If any dot position is outside of the boundaries of the box.

    """

    # Run some checks
    if not dot_positions.dtype == np.dtype('float'):
        raise(ValueError('Dot positions must be floating point numbers.'))

    if np.any(dot_positions[:,0] < box_position[0, 0]) or np.any(dot_positions[:, 0] >= box_position[1,0]):
        raise(ValueError('Dots must be contained within the box.'))

    if np.any(dot_positions[:, 1] < box_position[0, 1]) or np.any(dot_positions[:, 1] >= box_position[1,1]):
        raise(ValueError('Dots must be contained within the box.'))

    box_width = box_position[1, :] - box_position[0, :]

    # Transform points to a standard coordinate system, where lower left of box is at (0,0) and upper right is at (1,1)
    dot_positions = copy.deepcopy(dot_positions)
    dot_positions[:, 0] = dot_positions[:, 0] - box_position[0, 0]
    dot_positions[:, 1] = dot_positions[:, 1] - box_position[0, 1]

    dot_positions[:, 0] = dot_positions[:, 0]/box_width[0]
    dot_positions[:, 1] = dot_positions[:, 1]/box_width[1]

    div_lengths = np.asarray([1/n_divisions[0], 1/n_divisions[1]])

    # Generate a template binary mask of a dot
    dot_n_div = np.asarray([int(np.ceil((dot_dim_width[0]/box_width[0])/div_lengths[0])),
                            int(np.ceil((dot_dim_width[1]/box_width[1])/div_lengths[1]))])

    # Make sure we have an odd number of divisions
    if (dot_n_div[0] % 2) == 0:
        dot_n_div[0] += 1
    if (dot_n_div[1] % 2) == 0:
        dot_n_div[1] += 1

    dot_img = Image.new('1', (dot_n_div[0], dot_n_div[1]))
    dot_drawer = ImageDraw.Draw(dot_img)
    dot_drawer.ellipse((0, 0, dot_n_div[0], dot_n_div[1]), 1)
    dot_img_mask = np.array(dot_img).transpose()
    dot_img_float = dot_img_mask.astype('float')
    dot_img_float[dot_img == 0] = np.nan

    # Create the empty images of max values and indices - initially we add padding
    pad_width = np.floor(dot_n_div/2)
    im = np.zeros([int(n_divisions[0] + 2*pad_width[0]), int(n_divisions[1] + 2*pad_width[1])])
    im[:] = np.nan
    inds = np.zeros_like(im)
    inds[:] = np.nan

    # Now fill in the image
    n_pts = dot_positions.shape[0]
    for p_i in range(n_pts):
        # Calculate center grid square for each dot
        center = np.floor(dot_positions[p_i,:]/div_lengths) + pad_width
        dot_vl = dot_vls[p_i]

        # Calculate the selection coordinates for each grid
        d0_slice = slice(int(center[0] - pad_width[0]), int(center[0] + pad_width[0] + 1))
        d1_slice = slice(int(center[1] - pad_width[1]), int(center[1] + pad_width[1] + 1))

        # Indices where we actually need to do a comparison
        cmp_inds = np.logical_and(dot_img_mask, np.logical_not(np.isnan(im[d0_slice, d1_slice])))

        # See which of compare indices are set to dot values
        keep_cmp_inds = np.greater(np.abs(dot_vl*dot_img_float), np.abs(im[d0_slice, d1_slice]),
                                   where=cmp_inds)

        # See where we don't need to do a comparison
        non_cmp_inds = np.logical_and(dot_img_mask, np.isnan(im[d0_slice, d1_slice]))

        # Get set of all indices we are setting to dot value
        set_inds = np.logical_or(keep_cmp_inds, non_cmp_inds)

        im[d0_slice, d1_slice][set_inds] = dot_vl
        inds[d0_slice, d1_slice][set_inds] = p_i

    # Now remove padding
    d0_im_slice = slice(int(pad_width[0]), int(im.shape[0] - pad_width[0]))
    d1_im_slice = slice(int(pad_width[1]), int(im.shape[1] - pad_width[1]))

    non_padded_im = im[d0_im_slice, d1_im_slice]

    return [non_padded_im, inds]
