#- Utility functions for working with the DESI footprint

import numpy as np
from . import focalplane
from . import io

def radec2pix(nside, ra, dec):
    '''Convert ra,dec to nested pixel number

    Args:
        ra: float or array, Right Accention in degrees
        dec: float or array, Declination in degrees

    Returns:
        array of integer pixel numbers using nested numbering scheme

    Note: this is syntactic sugar around
    `hp.ang2pix(nside, ra, dec, lonlat=True, nest=True)`, but also works
    with older versions of healpy that didn't have `lonlat` yet.
    '''
    import healpy as hp
    theta, phi = np.radians(90-dec), np.radians(ra)
    return hp.ang2pix(nside, theta, phi, nest=True)

def tiles2pix(nside, tiles=None, radius=None, per_tile=False):
    '''
    Returns sorted array of pixels that overlap the tiles

    Args:
        nside: integer healpix nside, 2**k where 0 < k < 30

    Optional:
        tiles:
            array-like integer tile IDs; or
            integer tile ID; or
            Table-like with RA,DEC columns; or
            None to use all DESI tiles from desimodel.io.load_tiles()
        radius: tile radius in degrees;
            if None use desimodel.focalplane.get_tile_radius_deg()
        per_tile: if True, return a list of arrays of pixels per tile

    Returns pixels:
        integer array of pixel numbers that cover these tiles; or
        if per_tile is True, returns list of arrays such that pixels[i]
            is an array of pixel numbers covering tiles[i]
    '''
    import healpy as hp
    if tiles is None:
        import desimodel.io
        tiles = desimodel.io.load_tiles()

    if radius is None:
        import desimodel.focalplane
        radius = desimodel.focalplane.get_tile_radius_deg()

    theta, phi = np.radians(90-tiles['DEC']), np.radians(tiles['RA'])
    vec = hp.ang2vec(theta, phi)
    ipix = [hp.query_disc(nside, vec[i], radius=np.radians(radius),
                inclusive=True, nest=True) for i in range(len(tiles))]
    if per_tile:
        return ipix
    else:
        return np.sort(np.unique(np.concatenate(ipix)))

def tileids2pix(nside, tileids, radius=None, per_tile=False):
    '''
    Like tiles2pix, but accept integer tileid or list of tileids instead
    of table of tiles
    '''
    import desimodel.io
    tiles = desimodel.io.load_tiles()
    ii = np.in1d(tiles['TILEID'], tileids)
    if np.count_nonzero(ii) > 0:
        return tiles2pix(nside, tiles[ii], radius=radius, per_tile=per_tile)
    else:
        raise ValueError('TILEID(s) {} not in DESI footprint'.format(tileids))


def pix2tiles(nside, pixels, tiles=None, radius=None):
    '''
    Returns subset of tiles that overlap the list of pixels

    Args:
        nside: integer healpix nside, 2**k with 1 <= k <= 30
        pixels: array of integer pixels using nested numbering scheme

    Optional:
        tiles:
            Table-like with RA,DEC columns; or
            None to use all DESI tiles from desimodel.io.load_tiles()
        radius: tile radius in degrees;
            if None use desimodel.focalplane.get_tile_radius_deg()

    Returns:
        table of tiles that cover these pixels

    TODO: add support for tiles as integers or list/array of integer TILEIDs
    '''
    import healpy as hp
    import desimodel.footprint

    if tiles is None:
        import desimodel.io
        tiles = desimodel.io.load_tiles()

    if radius is None:
        import desimodel.focalplane
        radius = desimodel.focalplane.get_tile_radius_deg()

    #- Trim tiles to ones that *might* overlap these pixels
    theta, phi = hp.pix2ang(nside, pixels, nest=True)
    ra, dec = np.degrees(phi), 90 - np.degrees(theta)
    pixsize = np.degrees(hp.nside2resol(nside))
    ii = desimodel.footprint.find_tiles_over_point(tiles, ra, dec, radius=radius+pixsize)
    if np.isscalar(pixels):
        tiles = tiles[ii]
    else:
        ii = np.unique(np.concatenate(ii))
        tiles = tiles[ii]

    #- Now check in detail
    theta, phi = np.radians(90-tiles['DEC']), np.radians(tiles['RA'])
    vec = hp.ang2vec(theta, phi)
    ii = list()
    for i in range(len(tiles)):
        tilepix = hp.query_disc(nside, vec[i], radius=np.radians(radius), inclusive=True, nest=True)
        if np.any(np.in1d(pixels, tilepix)):
            ii.append(i)
    return tiles[ii]

def _embed_sphere(ra, dec):
    """ embed RA DEC to a uniform sphere in three-d """
    phi = np.radians(np.asarray(ra))
    theta = np.radians(90.0 - np.asarray(dec))
    r = np.sin(theta)
    x = r * np.cos(phi)
    y = r * np.sin(phi)
    z = np.cos(theta)
    return np.array((x, y, z)).T

def is_point_in_desi(tiles, ra, dec, radius=None, return_tile_index=False):
    """Return if points given by ra, dec lie in the set of _tiles.

    This function is optimized to query a lot of points.
    radius is in units of degrees.

    `tiles` is the result of load_tiles.

    If a point is within `radius` distance from center of any tile,
    it is in desi.

    The shape of ra, dec must match. The current implementation
    works only if they are both 1d vectors or scalars.

    If return_tile_index is True, return the index of the nearest tile in tiles array.

    default radius is from desimodel.focalplane.get_tile_radius_deg()
    """
    from scipy.spatial import cKDTree as KDTree

    if radius is None:
        radius = focalplane.get_tile_radius_deg()

    tilecenters = _embed_sphere(tiles['RA'], tiles['DEC'])
    tree = KDTree(tilecenters)
    # radius to 3d distance
    threshold = 2.0 * np.sin(np.radians(radius) * 0.5)
    xyz = _embed_sphere(ra, dec)
    d, i = tree.query(xyz, k=1)

    indesi = d < threshold
    if return_tile_index:
        return indesi, i
    else:
        return indesi

def find_tiles_over_point(tiles, ra, dec, radius=None):
    """Return a list of indices of tiles that covers the points.

    This function is optimized to query a lot of points.
    radius is in units of degrees. The return value is an array
    of list objects that are the indices of tiles that cover each point.

    The indices are not sorted in any particular order.

    if ra, dec are scalars, a single list is returned.

    default radius is from desimodel.focalplane.get_tile_radius_deg()
    """
    from scipy.spatial import cKDTree as KDTree

    if radius is None:
        radius = focalplane.get_tile_radius_deg()

    tilecenters = _embed_sphere(tiles['RA'], tiles['DEC'])
    tree = KDTree(tilecenters)

    # radius to 3d distance
    threshold = 2.0 * np.sin(np.radians(radius) * 0.5)
    xyz = _embed_sphere(ra, dec)
    indices = tree.query_ball_point(xyz, threshold)
    return indices

def find_points_in_tiles(tiles, ra, dec, radius=None):
    """Return a list of indices of points that are within each provided tile(s).

    This function is optimized to query a lot of points with relatively few tiles.

    radius is in units of degrees. The return value is an array
    of lists that contains the index of points that are in each tile.
    The indices are not sorted in any particular order.

    if tiles is a scalar, a single list is returned.

    default radius is from desimodel.focalplane.get_tile_radius_deg()
    """
    from scipy.spatial import cKDTree as KDTree

    if radius is None:
        radius = focalplane.get_tile_radius_deg()

    # check for malformed input shapes. Sorry we currently only
    # deal with vector inputs. (for a sensible definition of indices)

    assert ra.ndim == 1
    assert dec.ndim == 1

    points = _embed_sphere(ra, dec)
    tree = KDTree(points)

    # radius to 3d distance
    threshold = 2.0 * np.sin(np.radians(radius) * 0.5)
    xyz = _embed_sphere(tiles['RA'], tiles['DEC'])
    indices = tree.query_ball_point(xyz, threshold)
    return indices

#
#
#
def get_tile_radec(tileid):
    """Return (ra, dec) in degrees for the requested tileid.

    If tileid is not in DESI, return (0.0, 0.0)
    TODO: should it raise and exception instead?
    """
    tiles = io.load_tiles()
    if tileid in tiles['TILEID']:
        i = np.where(tiles['TILEID'] == tileid)[0][0]
        return tiles[i]['RA'], tiles[i]['DEC']
    else:
        return (0.0, 0.0)

