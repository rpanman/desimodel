# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-
"""Test desimodel.focalplane.
"""
import unittest
import numpy as np
from ..focalplane import FocalPlane


class TestFocalplane(unittest.TestCase):
    """Test desimodel.focalplane.
    """

    def test_xy2radec(self):
        """Test the consistency between the conversion functions
        radec2xy and xy2radec.
        """

        ra_list = np.array([0.0, 39.0, 300.0, 350.0, 359.9999, 20.0])
        dec_list = np.array([0.0, 45.0, 89.9999, -89.9999, 0.0, 89.9999])

        F = FocalPlane(ra_list, dec_list)

        # First test to check that it places x, y at the center.
        ra_obj = ra_list.copy()
        dec_obj = dec_list.copy()

        x_obj, y_obj = F.radec2xy(ra_obj, dec_obj)
        self.assertFalse(np.any(np.fabs(x_obj) > 1E-6) |
                         np.any(np.fabs(y_obj) > 1E-6),
                         ("Test Failed to recover position center with 1E-6 " +
                          "precision."))

        # Second test to check that it recovers input ra_obj,dec_obj.
        ra_out, dec_out = F.xy2radec(x_obj, y_obj)
        self.assertFalse(np.any(np.fabs(ra_out-ra_obj) > 1E-6) |
                         np.any(np.fabs(dec_out-dec_obj) >1E-6),
                         ("Test Failed to recover the input RA, Dec with " +
                          "1E-6 precision"))


if __name__ == '__main__':
    unittest.main()
