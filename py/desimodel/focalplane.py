# See LICENSE.rst for BSD 3-clause license info
# -*- coding: utf-8 -*-
"""
====================
desimodel.focalplane
====================

Provides utilities to model the DESI focal plane.
"""


import os
import numpy as np
from astropy.io import fits
import astropy.units as u

# Define this here to avoid a problem with Sphinx compilation.
try:
    default_offset = 10.886*u.um
except TypeError:
    default_offset = 10.886


def generate_random_vector_field(rms, exponent, n, seed=None, smoothing=0.05):
    """Generate a pair dx, dy of 2D Gaussian random field.

    The random field is generated with a power spectrum P(k) ~ r ** exponent
    and normalized to the specified RMS value.  Smoothing is applied to minimize
    grid artifacts.

    Parameters
    ----------
    rms : float or astropy quantity
        Desired RMS of the generated field values.
    exponent : float
        Exponent of the power spectrum scaling with radius.
    n : int
        Size of the generated array along each axis.
    seed : int
        Random number seed to use. Generated fields should be portable
        across python versions and platforms.
    smoothing : float
        Length scale for smoothing the generated field expressed
        as a fraction of the full width of the field.  Implemented
        as a Gaussian convolution.  No smoothing is applied when
        smoothing is zero.

    Returns
    -------
    tuple
        Tuple dx, dy of 2D arrays containing the generated Gaussian
        random field values. Arrays will have the same units as the
        rms parameter, if any.
    """
    A = np.zeros((n, n), complex)
    kvec = np.fft.fftfreq(n)
    kx, ky = np.meshgrid(kvec, kvec, sparse=True, copy=False)
    ksq = kx ** 2 + ky ** 2
    m = ksq > 0
    gen = np.random.RandomState(seed=seed)
    phase = 2 * np.pi * gen.uniform(size=(n, n))
    A[m] = (ksq[m] ** (exponent / 2) * gen.normal(size=(n, n))[m] *
            np.exp(1.j * phase[m]))
    if smoothing > 0:
        var = (n * smoothing) ** 2 / 2
        A[m] *= np.exp(-ksq[m] * var) / (2 * np.pi)
    offsets = np.fft.ifft2(A)

    # Rescale to the specified RMS radial offset.
    dr2 = (offsets.real**2 + offsets.imag**2).flatten()
    rescale = rms / np.sqrt(np.average(dr2))
    dx = offsets.real * rescale
    dy = offsets.imag * rescale

    return dx, dy


def generate_random_centroid_offsets(rms_offset=default_offset, seed=123):
    """Generate random centroid offsets.

    Calls :func:`generate_random_vector_field` to generate offsets with
    a power spectrum exponent of -1 in the expected format.

    The arrays in the files $DESIMODEL/data/throughput/DESI-0347_random_offset_<n>.fits
    were generated by this method with seeds n=1,2,3.

    The default RMS offset value is the quadrature sum of the achromatic
    contributions in cells B43:B72 of the throughput sheet in DESI-0347-v10.

    Parameters
    ----------
    rms_offset : :class:`astropy.Quantity` instance.
        RMS that the generated offsets should have, including units.
    seed : :class:`int`
        Random number seed to use. Generated offsets should be portable
        across python versions and platforms.

    Returns
    -------
    tuple
        Tuple dx, dy of centroid offset arrays with units.
    """
    return generate_random_vector_field(
        rms_offset, exponent=-1.0, n=256, seed=seed, smoothing=0.05)

_tile_radius_deg = None
_tile_radius_mm = None

def get_tile_radius_mm():
    '''Returns radius in mm to the middle of the outermost positioner'''
    global _tile_radius_mm
    if _tile_radius_mm is None:
        import desimodel.io
        fp = desimodel.io.load_fiberpos()
        p = desimodel.io.load_desiparams()
        _tile_radius_mm = np.sqrt(np.max(fp['X']**2 + fp['Y']**2))  # + p['positioners']['radius_max']

    return _tile_radius_mm

def get_tile_radius_deg():
    '''Returns radius in degrees to the middle of the outermost positioner'''
    global _tile_radius_deg
    if _tile_radius_deg is None:
        import scipy.interpolate
        import desimodel.io
        rmax = get_tile_radius_mm()
        platescale = desimodel.io.load_platescale()
        fn = scipy.interpolate.interp1d(platescale['radius'], platescale['theta'], kind='quadratic')
        _tile_radius_deg = float(fn(rmax))

    return _tile_radius_deg

class FocalPlane(object):
    """A class for modeling the DESI focal plane and converting between
    focal plane coordinates (in mm) and RA, Dec on the sky (in degrees).
    Provides utility functions for mapping which positioners cover
    which (RA, Dec) or (x, y) locations and vice versa.

    Parameters
    ----------
    ra, dec : :class:`float`
        Initialize DESI focal plane model with the telescope pointing
        at (`ra`, `dec`) in degrees.
    """

    def __init__(self, ra=0.0, dec=0.0):
        """
        """
        # Read $DESIMODEL/data/focalplane/fiberpos.fits and platescale.txt
        # to construct focal plane model.  May also need data/desi.yaml .
        self._check_radec(ra, dec)
        self.ra = ra
        self.dec = dec
        self._fiberpos_file = os.path.join(os.environ['DESIMODEL'],
                                           'data', 'focalplane',
                                           'fiberpos.fits')
        with fits.open(self._fiberpos_file) as hdulist:
            self.fiberpos = hdulist[1].data

    def _check_radec(self, ra, dec):
        """Raise ValueError if RA or dec are out of bounds.
        """
        if np.any( (ra < 0) | (ra >= 360) ):
            raise ValueError("RA must be 0 <= RA < 360")
        if np.any( (dec < -90) | (dec > +90) ):
            raise ValueError("Dec must be -90 <= dec <= 90")

    def set_tele_pointing(self, ra, dec):
        """Set telescope pointing to (RA, Dec) in degrees.

        Parameters
        ----------
        ra
        dec : :class:`float`
            Telescope pointing in degrees.
        """
        self._check_radec(ra, dec)
        self.ra = ra
        self.dec = dec

    def plate_dist(self, theta):
        """Returns the radial distance on the plate (mm) given the angle
        (radians). This is a fit to some data, it should be calculated on the
        fly at __init__.

        Parameters
        ----------
        theta : :class:`float`
            Angle in radians.

        Returns
        -------
        :class:`float`
            Radial distance in mm.
        """
        p = np.array([8.297E5, -1750.0, 1.394E4, 0.0])
        radius = 0.0
        for i in range(4):
            radius = theta*radius + p[i]
        return radius

    def plate_angle(self, radius):
        """Returns the angular distance on the plate (radians) given the
        radial distance to the plate (mm).

        It uses a Newton-Raphson method.

        Parameters
        ----------
        radius : :class:`float`
            Plate distance in mm.

        Returns
        -------
        :class:`float`
            Angular distance in radians.
        """
        angle_guess = 0.0 * radius
        dist_guess = self.plate_dist(angle_guess) - radius
        while np.any(np.fabs(dist_guess) > 1E-8):
            derivative = (self.plate_dist(angle_guess+1E-5) -
                          self.plate_dist(angle_guess))/1E-5
            delta_guess = - dist_guess/derivative
            angle_guess = angle_guess + delta_guess
            dist_guess = self.plate_dist(angle_guess) - radius
        return angle_guess

    def radec2xy(self, ra, dec):
        """Convert (RA, Dec) in degrees to (x, y) in mm on the focal plane
        given the current telescope pointing.

        If RA and Dec are floats, returns a tuple (x, y) of floats
        If RA and Dec are numpy arrays, returns a tuple (x, y) of numpy arrays

        Parameters
        ----------
        ra, dec : :class:`float` or :class:`numpy.ndarray`
            Sky position.

        Returns
        -------
        :func:`tuple`
            A tuple containing the (x, y) coordinates in mm.
        """
        self._check_radec(ra, dec)

        object_theta = (90.0 - dec)*np.pi/180.0
        object_phi = ra*np.pi/180.0
        o_hat0 = np.sin(object_theta)*np.cos(object_phi)
        o_hat1 = np.sin(object_theta)*np.sin(object_phi)
        o_hat2 = np.cos(object_theta)

        tile_theta = (90.0 - self.dec)* np.pi/180.0
        tile_phi = self.ra * np.pi/180.0
        t_hat0 = np.sin(tile_theta)*np.cos(tile_phi)
        t_hat1 = np.sin(tile_theta)*np.sin(tile_phi)
        t_hat2 = np.cos(tile_theta)

        # We make a rotation on o_hat, so that t_hat ends up aligned with
        # the unit vector along z. This is composed by a first rotation around
        # z of an angle pi/2 - phi and a second rotation around x by an angle
        # theta, where theta and phi are the angles describin t_hat.

        costheta = t_hat2
        sintheta = np.sqrt(1.0-costheta*costheta) + 1E-12
        cosphi = t_hat0/sintheta
        sinphi = t_hat1/sintheta
        # First rotation, taking into account that cos(pi/2 -phi) =
        # sin(phi) and sin(pi/2-phi)=cos(phi)
        n_hat0 = sinphi*o_hat0 - cosphi*o_hat1
        n_hat1 = cosphi*o_hat0 + sinphi*o_hat1
        n_hat2 = o_hat2
        # Second rotation
        nn_hat0 = n_hat0
        nn_hat1 = costheta*n_hat1 - sintheta*n_hat2
        nn_hat2 = sintheta*n_hat1 + costheta*n_hat2
        # Now find the radius on the plate
        theta = np.sqrt(nn_hat0*nn_hat0 + nn_hat1*nn_hat1)
        radius = self.plate_dist(theta)
        x = radius * nn_hat0/theta
        y = radius * nn_hat1/theta
        return (x, y)

    def xy2radec(self, x, y):
        """Convert (x, y) in mm on the focal plane to (ra_object, dec_object)
        in degrees on the sky given the current telescope pointing towards
        (RA, Dec).

        `x`, `y` must be floats. This function is vectorized in xy2radec(),
        which doesn't appear to exist.

        Parameters
        ----------
        x, y : :class:`float`
            Position on the focal plane in mm.

        Returns
        -------
        :func:`tuple`
            Coordinates of object.
        """
        self._check_radec(self.ra, self.dec)
        # The implementation of this function takes the same conventions
        # as radec2xy to make rotations, only that it happens in the reverse
        # order.
        #
        # This is the final position of the tile vector, which starts
        # parallel to  z_hat.
        tile_theta = (90.0 - self.dec)*np.pi/180.0
        tile_phi = self.ra*np.pi/180.0
        t_hat0 = np.sin(tile_theta)*np.cos(tile_phi)
        t_hat1 = np.sin(tile_theta)*np.sin(tile_phi)
        t_hat2 = np.cos(tile_theta)
        # Define sin and cos of the angles for the final tile vector.
        costheta = t_hat2
        sintheta = np.sqrt(1.0-costheta*costheta) + 1E-10
        cosphi = t_hat0/sintheta
        sinphi = t_hat1/sintheta
        # Find the initial position of the object vector when the tile
        # starts parallel to z_hat.
        radius = np.sqrt(x*x + y*y)
        object_theta = self.plate_angle(radius)
        object_phi = np.arctan2(y, x)
        o_hat0 = np.sin(object_theta)*np.cos(object_phi)
        o_hat1 = np.sin(object_theta)*np.sin(object_phi)
        o_hat2 = np.cos(object_theta)
        # First rotation, around x by an angle -theta.
        n_hat0 = o_hat0
        n_hat1 = costheta*o_hat1 + sintheta*o_hat2
        n_hat2 = -sintheta*o_hat1 + costheta*o_hat2
        # Second rotation around z_hat by -(pi/2-phi), taking into
        # account that cos(pi/2 -phi) = sin(phi) and
        # sin(pi/2-phi)=cos(phi).
        nn_hat0 = sinphi*n_hat0 + cosphi*n_hat1
        nn_hat1 = -cosphi*n_hat0 + sinphi*n_hat1
        nn_hat2 = n_hat2
        # Convert from unit vectors to ra, dec.
        object_theta = np.arccos(nn_hat2)
        object_phi = np.arctan2(nn_hat1, nn_hat0)
        object_dec = 90.0 - (180.0/np.pi)*object_theta
        # Due to rounding imprecisions the remainder has to be taken
        # two times (!).
        object_ra = np.remainder((object_phi*180.0/np.pi), 360.0)
        object_ra = np.remainder(object_ra, 360.0)
        self._check_radec(object_ra, object_dec)
        return (object_ra, object_dec)

    def radec2pos(self, ra, dec):
        """Identify which positioners cover (`ra`, `dec`).

        If `ra`, `dec` are floats, return an array of positioner IDs that
        cover it. The array could be empty if no positioner covers that
        location.

        If `ra`, `dec` are numpy arrays, return a list of arrays.
        The ith element is an array of positioner IDs that cover
        (ra[i], dec[i]).

        .. warning:: This method is not implemented!
        """
        raise NotImplementedError


# Not sure what to call it, but it would also be useful to have a
# function that takes (ra, dec) arrays and returns a list with one
# element per positioner, giving the indices of the (ra,dec) arrays
# that that positioner covers.
#
# ditto for xy2pos(), xy2fiber(), etc.
# positioner = thing on the focal plane
# fiber = numerically increasing in order on the spectrograph CCDs
