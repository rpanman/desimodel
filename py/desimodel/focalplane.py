# License information goes here
# -*- coding: utf-8 -*-
"""
====================
desimodel.focalplane
====================

Provides FocalPlane class to model the DESI focal plane.
"""
#
from __future__ import absolute_import, division, print_function, unicode_literals
# The line above will help with 2to3 support.
import os
import numpy as np
from astropy.io import fits
#
#
#
class FocalPlane():
    """
    A class for modeling the DESI focal plane and converting between
    focal plane coordinates (in mm) and ra,dec on the sky (in degrees).
    Provides utility functions for mapping which positioners cover
    which (ra,dec) or (x,y) locations and vice versa.
    """
    def __init__(self, ra=0.0, dec=0.0):
        """
        Initialize DESI focal plane model with the telescope pointing
        at (ra, dec) in degrees.
        """
        #- Read $DESIMODEL/data/focalplane/fiberpos.fits and platescale.txt
        #- to construct focal plane model.  May also need data/desi.yaml .
        self._check_radec(ra, dec)
        self.ra = ra
        self.dec = dec
        self.fiberpos = fits.getdata(os.getenv('DESIMODEL')+'/data/focalplane/fiberpos.fits')

    def _check_radec(self, ra, dec):
        """Raise ValueError if RA or dec are out of bounds"""
        if np.any( (ra < 0) | (ra >= 360) ):
            raise ValueError("RA must be 0 <= RA < 360")
        if np.any( (dec < -90) | (dec > +90) ):
            raise ValueError("dec must be -90 <= dec <= 90")

    def set_tele_pointing(self, ra, dec):
        """
        Set telescope pointing to (ra, dec) in degrees
        """
        self._check_radec(ra, dec)
            
        self.ra = ra
        self.dec = dec

    def plate_dist(self, theta):
        """
        Returns the radial distance on the plate (mm) given the angle (radians).
        This is a fit to some data, it should be calculated on the fly at __init__
        """
        p = np.array([8.297E5,-1750.0,1.394E4,0.0])
        radius = 0.0
        for i in range(4):
            radius = theta*radius + p[i]
        return radius

    def plate_angle(self, radius):
        """
        Returns the angular distance on the plate (radians) given the
        radial distance to the plate (mm). 

        It uses a Newton-Raphson method.
        """
        angle_guess = 0.0 * radius
        dist_guess = self.plate_dist(angle_guess) - radius
        while(np.any(np.fabs(dist_guess)>1E-8)):
            derivative = (self.plate_dist(angle_guess+1E-5) - self.plate_dist(angle_guess))/1E-5 
            delta_guess = - dist_guess/derivative
            angle_guess = angle_guess + delta_guess        
            dist_guess = self.plate_dist(angle_guess) - radius

        return angle_guess


    def radec2xy(self, ra, dec):
        """
        Convert (ra, dec) in degrees to (x, y) in mm on the focal plane
        given the current telescope pointing.

        If ra and dec are floats, returns a tuple (x, y) of floats
        If ra and dec are numpy arrays, returns a tuple (x, y) of numpy arrays
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

        #we make a rotation on o_hat, so that t_hat ends up aligned with
        #the unit vector along z. This is composed by a first rotation around z
        #of an angle pi/2 - phi and a second rotation around x by an angle theta,
        #where theta and phi are the angles describin t_hat.

        costheta = t_hat2
        sintheta = np.sqrt(1.0-costheta*costheta) + 1E-12
        cosphi = t_hat0/sintheta
        sinphi = t_hat1/sintheta
        #First rotation, taking into account that cos(pi/2 -phi) = sin(phi) and sin(pi/2-phi)=cos(phi)
        n_hat0 = sinphi*o_hat0 - cosphi*o_hat1
        n_hat1 = cosphi*o_hat0 + sinphi*o_hat1
        n_hat2 = o_hat2
        #Second rotation
        nn_hat0 = n_hat0
        nn_hat1 = costheta*n_hat1 - sintheta*n_hat2
        nn_hat2 = sintheta*n_hat1 + costheta*n_hat2
        #Now find the radius on the plate
        theta = np.sqrt(nn_hat0*nn_hat0 + nn_hat1*nn_hat1)
        radius = self.plate_dist(theta)
        x = radius * nn_hat0/theta
        y = radius * nn_hat1/theta
        return (x,y)

    def xy2radec(self, x, y):
        """
        Convert (x,y) in mm on the focal plane 
        to (ra_object, dec_object) in deg on the sky
        given the current telescope pointing towards (ra,dec).

        x,y must be floats. This function is vectorized in xy2radec().
        """

        self._check_radec(self.ra, self.dec)
        
        # The implementation of this function takes the same conventions
        # as radec2xy to make rotations, only that it happens in the reverse
        # order
        
        
        # This is the final position of the tile vector, which starts
        # parallel to  z_hat. 
        tile_theta = (90.0 - self.dec)*np.pi/180.0
        tile_phi = self.ra*np.pi/180.0
        t_hat0 = np.sin(tile_theta)*np.cos(tile_phi)
        t_hat1 = np.sin(tile_theta)*np.sin(tile_phi)
        t_hat2 = np.cos(tile_theta)
        
        #define sin and cos of the angles for the final tile vector.
        costheta = t_hat2
        sintheta = np.sqrt(1.0-costheta*costheta) + 1E-10
        cosphi = t_hat0/sintheta
        sinphi = t_hat1/sintheta
        
        # Find the initial position of the object vector when the tile
        # starts parallel to z_hat 
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
    
         #Second rotation around z_hat by -(pi/2-phi), taking into
         #account that cos(pi/2 -phi) = sin(phi) and
         #sin(pi/2-phi)=cos(phi) 
        nn_hat0 = sinphi*n_hat0 + cosphi*n_hat1
        nn_hat1 = -cosphi*n_hat0 + sinphi*n_hat1
        nn_hat2 = n_hat2
    
        #convert from unit vectors to ra, dec
        object_theta = np.arccos(nn_hat2)  
        object_phi = np.arctan2(nn_hat1, nn_hat0)
        
        object_dec = 90.0 - (180.0/np.pi)*object_theta
        # due to rounding imprecisions the remainder has to be taken
        # two times (!)
        object_ra = np.remainder((object_phi*180.0/np.pi),360.0)
        object_ra = np.remainder(object_ra,360.0) 

    
        self._check_radec(object_ra, object_dec)
  
        return (object_ra, object_dec)


    def radec2pos(ra, dec):
        """
        Identify which positioners cover (ra, dec)

        If ra,dec are floats, return an array of positioner IDs that cover it.
        The array could be empty if no positioner covers that location.

        If ra,dec are numpy arrays, return a list of arrays.  The ith element
        is an array of positioner IDs that cover (ra[i], dec[i]).
        """
        raise NotImplementedError

    #- Not sure what to call it, but it would also be useful to have a
    #- function that takes (ra, dec) arrays and returns a list with one
    #- element per positioner, giving the indices of the (ra,dec) arrays
    #- that that positioner covers.

    #- ditto for xy2pos(), xy2fiber(), etc.
    #- positioner = thing on the focal plane
    #- fiber = numerically increasing in order on the spectrograph CCDs


def test_xy2radec():
    """
    Tests the consistency between the conversion functions 
    radec2xy and xy2radec
    """

    ra_list = np.array([0.0,39.0,300.0, 350.0,359.9999, 20.0])
    dec_list = np.array([0.0,45.0, 89.9999,-89.9999,0.0, 89.9999])

    F = FocalPlane(ra_list,dec_list)

    #first test to check that it places x,y at the center
    ra_obj = ra_list.copy()
    dec_obj = dec_list.copy()

    x_obj,y_obj = F.radec2xy(ra_obj, dec_obj)
    if(np.any(np.fabs(x_obj)>1E-6)|np.any(np.fabs(y_obj)>1E-6)):
        raise ValueError("Test Failed to recover position center with 1E-6 precision")        

    #second test to check that it recovers input ra_obj,dec_obj
    ra_out,dec_out = F.xy2radec(x_obj, y_obj)
    if(np.any(np.fabs(ra_out-ra_obj)>1E-6)|np.any(np.fabs(dec_out-dec_obj)>1E-6)):
        raise ValueError("Test Failed to recover the input ra, dec with 1E-6 precision")        

    return True
        