#!/usr/bin/env python
# coding: utf-8
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
from scipy.spatial import cKDTree
import pyproj
# from .utils import *
from tablegis.utils import *
from typing import Optional
from tablegis import __path__
import warnings



def min_distance_onetable(df, lon='lon', lat='lat', idname='id', n=1, include_self=False) -> pd.DataFrame:
    """Find the nearest n neighbors for each point in a DataFrame.

    This function computes the nearest n points for every row in the input
    DataFrame using a KD-tree. Optionally the point itself can be included
    among the neighbors.

    Parameters
    ----------
    df : DataFrame
        Input data containing point coordinates.
    lon : str
        Longitude column name.
    lat : str
        Latitude column name.
    idname : str
        Identifier column name (default 'id').
    n : int
        Number of nearest neighbors to find.
    include_self : bool
        Whether to include the point itself among neighbors.

    Returns
    -------
    DataFrame
        A copy of the input DataFrame with additional columns for nearest
        neighbor ids, coordinates and distances (in meters).
    """
    # parameter validation
    if n < 1:
        raise ValueError("n must be > 0")
    if lon not in df.columns or lat not in df.columns:
        raise ValueError("Longitude or latitude column not found")
    if idname not in df.columns:
        raise ValueError("ID column not found")
    if df.empty:
        return df  # return empty DataFrame instead of raising
    detected_crs = detect_crs(df, lon, lat)
    # create result copy
    result = df.copy()
    
    # handle empty data or insufficient number of points
    if len(df) == 0 or (len(df) == 1 and not include_self):
        for i in range(1, n+1):
            result[f'nearest{i}_{idname}'] = np.nan
            result[f'nearest{i}_{lon}'] = np.nan
            result[f'nearest{i}_{lat}'] = np.nan
            result[f'nearest{i}_distance'] = np.nan
        if n > 1:
            result['mean_distance'] = np.nan
        return result
    
    # extract coordinate points
    points, proj_crs = create_projected_kdtree(result, lon, lat)

    # create KDTree
    tree = cKDTree(points)
    
    # compute number of neighbors to query
    # if not including self, query one extra because the first neighbor is self
    k_query = n + (0 if include_self else 1)
    # ensure the query size does not exceed dataset size
    k_query = min(k_query, len(df))
    
    # query the k nearest neighbors
    distances, indices = tree.query(points, k=k_query, workers=-1)
    
    # handle single-neighbor case (ensure arrays are 2D)
    if k_query == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)
    
    # if not including self, skip the first column (the point itself)
    if not include_self and k_query > 1:
        distances = distances[:, 1:]
        indices = indices[:, 1:]
    
    # ensure correct number of result columns
    current_k = distances.shape[1] if len(distances.shape) > 1 else 1
    
    # initialize result arrays
    result_indices = np.full((len(df), n), -1, dtype=int)
    result_distances = np.full((len(df), n), np.nan)
    
    # fill valid data
    valid_cols = min(current_k, n)
    if valid_cols > 0:
        if len(distances.shape) == 1:
            result_indices[:, 0] = indices
            result_distances[:, 0] = distances
        else:
            result_indices[:, :valid_cols] = indices[:, :valid_cols]
            result_distances[:, :valid_cols] = distances[:, :valid_cols]
    
    # add nearest neighbor information to the result DataFrame
    for i in range(n):
        # get the index for this neighbor column
        col_indices = result_indices[:, i]
        
        # initialize column value lists
        id_values = []
        lon_values = []
        lat_values = []
        
        # populate values
        for idx in col_indices:
            if idx >= 0:
                id_values.append(df.iloc[idx][idname])
                lon_values.append(df.iloc[idx][lon])
                lat_values.append(df.iloc[idx][lat])
            else:
                id_values.append(np.nan)
                lon_values.append(np.nan)
                lat_values.append(np.nan)

        result[f'nearest{i+1}_{idname}'] = id_values
        result[f'nearest{i+1}_{lon}'] = lon_values
        result[f'nearest{i+1}_{lat}'] = lat_values
        result[f'nearest{i+1}_distance'] = result_distances[:, i]

    # add mean distance (when n > 1)
    if n > 1:
        dist_cols = [f'nearest{j+1}_distance' for j in range(n)]
        result['mean_distance'] = result[dist_cols].mean(axis=1)

    return result


def min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', lon2='lon2', lat2='lat2', df2_id='id', n=1,
                          crs1: Optional[str]=None, crs2: Optional[str]=None) -> pd.DataFrame:
    """Compute distances from each point in df1 to the nearest n points in df2.

    This function uses a KD-tree for efficient nearest-neighbor searches. Input
    coordinate reference systems should match; WGS84 (EPSG:4326) is expected
    when using geographic coordinates. Distances are calculated in meters by
    projecting coordinates to an appropriate UTM zone.

    Parameters
    ----------
    df1 : pd.DataFrame
        Source DataFrame containing query points.
    df2 : pd.DataFrame
        Target DataFrame containing reference points.
    lon1, lat1 : str
        Longitude/latitude column names for df1.
    lon2, lat2 : str
        Longitude/latitude column names for df2.
    df2_id : str
        Identifier column in df2.
    n : int
        Number of nearest neighbors to find.
    crs1, crs2 : str, optional
        Optionally enforce expected CRS for df1 and df2 (e.g. 'EPSG:4326').

    Returns
    -------
    pd.DataFrame
        A copy of df1 with added columns for the nearest neighbor ids, their
        coordinates and distances (in meters). When n > 1, a 'mean_distance'
        column is also provided.

    Raises
    ------
    ValueError
        If n < 1 or if the two DataFrames have inconsistent coordinate systems.

    Notes
    -----
    - Distances are computed in UTM (meters) for accuracy.
    - Uses cKDTree for efficient nearest-neighbor queries.
    - Missing neighbors (when n > len(df2)) are filled with NaN.
    """
    # validate inputs
    if n < 1:
        raise ValueError("The parameter n must be greater than or equal to 1.")
    # handle empty data cases
    if len(df2) == 0 or len(df1) == 0:
        for i in range(1, n + 1):
            df1[f'nearest{i}_{df2_id}'] = np.nan
            df1[f'nearest{i}_{lon2}'] = np.nan
            df1[f'nearest{i}_{lat2}'] = np.nan
            df1[f'nearest{i}_distance'] = np.nan
        if n > 1:
            df1['mean_distance'] = np.nan
        return df1
    # detect or validate CRS
    detected_crs1 = detect_crs(df1, lon1, lat1)
    detected_crs2 = detect_crs(df2, lon2, lat2)
    
    # if user specified CRS, verify it matches detected CRS
    if crs1 is not None and crs1 != detected_crs1:
        raise ValueError(
            f"The designated CRS1={crs1} In conjunction with the detected coordinate system {detected_crs1} parameters not compatible"
        )
    if crs2 is not None and crs2 != detected_crs2:
        raise ValueError(
            f"The designated crs2={crs2} In conjunction with the detected coordinate system {detected_crs2} parameters not compatible"
        )
    
    # check that both DataFrames use the same CRS
    if detected_crs1 != detected_crs2:
        raise ValueError(
            f"The coordinate systems of the two DataFrames are not consistent!\n"
            f"df1 crs: {detected_crs1}\n"
            f"df2 crs: {detected_crs2}\n"
            f"Make sure that the two datasets use the same coordinate system."
        )
    
    # create result copy
    result = df1.copy()
    
    
    # project df1 coordinates to UTM (units: meters)
    A_points, proj_crs = create_projected_kdtree(df1, lon1, lat1)
    
    # create transformer for df2 (use same UTM projection)
    transformer_b = pyproj.Transformer.from_crs(
        "EPSG:4326", 
        proj_crs, 
        always_xy=True
    )
    lons_b = df2[lon2].values
    lats_b = df2[lat2].values
    x_b, y_b = transformer_b.transform(lons_b, lats_b)
    B_points = np.column_stack((x_b, y_b))
    
    # build KDTree for efficient search
    tree = cKDTree(B_points)
    
    # query nearest n points
    k = min(n, len(df2))
    distances, indices = tree.query(A_points, k=k, workers=-1)
    
    # handle dimensionality when k == 1
    if k == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)

    # add nearest neighbor information
    for i in range(k):
        nearest_points = df2.iloc[indices[:, i]]
        result[f'nearest{i+1}_{df2_id}'] = nearest_points[df2_id].values
        result[f'nearest{i+1}_{lon2}'] = nearest_points[lon2].values
        result[f'nearest{i+1}_{lat2}'] = nearest_points[lat2].values
        result[f'nearest{i+1}_distance'] = distances[:, i]  # units: meters
    
    # add missing columns when n > k
    for i in range(k, n):
        result[f'nearest{i+1}_{df2_id}'] = np.nan
        result[f'nearest{i+1}_{lon2}'] = np.nan
        result[f'nearest{i+1}_{lat2}'] = np.nan
        result[f'nearest{i+1}_distance'] = np.nan
    
    # add mean distance (when n > 1)
    if n > 1:
        dist_cols = [f'nearest{i+1}_distance' for i in range(min(n, k))]
        if dist_cols:
            result['mean_distance'] = result[dist_cols].mean(axis=1)
        else:
            result['mean_distance'] = np.nan
    
    return result

def to_lonlat(df, lon, lat, from_crs, to_crs):
    """Wrapper that adds converted longitude/latitude columns to a DataFrame.

    This function delegates to :func:`to_lonlat_utils` for the actual
    conversion. See that function for supported CRS identifiers and details.
    """
    return to_lonlat_utils(df, lon, lat, from_crs, to_crs)


def add_buffer(df, lon='lon', lat='lat', dis=None, min_distance=None, geometry='geometry'):
    """
    Create accurate buffers in meters using an appropriate UTM projection.
    Optimized for performance using vectorized operations.
    Parameters
    ----------
    df : DataFrame
        DataFrame containing longitude/latitude columns.
    lon, lat : str
        Names of longitude and latitude columns.
    dis : str or number
        If string, interpreted as a column name containing outer radii; if
        numeric, treated as a fixed outer buffer distance in meters.
    min_distance : str or number, optional
        If provided (string or numeric) creates a ring between `min_distance`
        (inner radius) and `dis` (outer radius). If `None` (default) behaves
        like a normal filled buffer. Supports column name (str) or scalar
        numeric value. Values must be >= 0.
    geometry : str
        Name for the output geometry column.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame of buffer polygons in CRS EPSG:4326.
    """
    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Missing columns: {lon}, {lat}")

    # Preserve original rows: create geometry only for valid rows, keep others as None
    df_all = df.copy().reset_index(drop=True)
    mask_valid = df_all[lon].notna() & df_all[lat].notna()
    if not mask_valid.any():
        raise ValueError("The latitude and longitude columns contain all null values.")

    # Validate coordinate ranges on valid rows
    lon_vals, lat_vals = df_all.loc[mask_valid, lon], df_all.loc[mask_valid, lat]
    if (lon_vals.min() < -180) or (lon_vals.max() > 180) or \
       (lat_vals.min() < -90) or (lat_vals.max() > 90):
        error_msg = f"Coordinate data anomaly:\n"
        error_msg += f"  lon range: [{lon_vals.min():.4f}, {lon_vals.max():.4f}] ( -180 - 180)\n"
        error_msg += f"  lat range: [{lat_vals.min():.4f}, {lat_vals.max():.4f}] ( -90 - 90)\n"
        raise ValueError(error_msg)

    # Build geometry series: Point for valid rows, None for invalid
    geom_series = [None] * len(df_all)
    from shapely.geometry import Point as _Point
    valid_positions = df_all.index[mask_valid]
    for pos in valid_positions:
        geom_series[pos] = _Point(df_all.at[pos, lon], df_all.at[pos, lat])

    gdf = gpd.GeoDataFrame(df_all, geometry=geom_series, crs="EPSG:4326")

    # Estimate best UTM CRS (robust to edge cases)
    try:
        utm_crs = gdf.estimate_utm_crs()
    except Exception as e:
        # Fallback: use centroid-based UTM (your original logic)
        center_lon = df[lon].mean()
        center_lat = df[lat].mean()
        utm_zone = int((center_lon + 180) // 6) + 1
        hemisphere = 32600 if center_lat >= 0 else 32700
        utm_crs = f"EPSG:{hemisphere + utm_zone}"
        print(f"Falling back to manual UTM: {utm_crs}")

    print(f"Using UTM CRS: {utm_crs}")
    gdf_utm = gdf.to_crs(utm_crs)

    # Helper: extract radius as Series (scalar or column)
    def _resolve_radius(val, default_name):
        if val is None:
            return None
        if isinstance(val, str):
            if val not in df_all.columns:
                raise KeyError(f"Column '{val}' not found for {default_name}")
            series = df_all[val].astype(float)
        else:
            try:
                scalar = float(val)
            except Exception:
                raise ValueError(f"type Error: {val}")
            series = pd.Series([scalar] * len(df_all), index=df_all.index)
        return series

    outer_series = _resolve_radius(dis, 'dis')
    inner_series = _resolve_radius(min_distance, 'min_distance') if min_distance is not None else pd.Series(0.0, index=df_all.index)

    # Validate radii
    if (outer_series < 0).any() or (inner_series < 0).any():
        raise ValueError("Buffer distances must be >= 0")

    if (inner_series > outer_series).any():
        # Optional: warn or set to 0
        print("Warning: Some inner_radius > outer_radius → resulting in empty rings.")
        # You could clip: inner_series = inner_series.clip(upper=outer_series)

    # Vectorized buffer creation only for valid rows
    valid_idx = list(gdf[gdf.geometry.notna()].index)
    # prepare per-row outer/inner arrays aligned to valid_idx
    outer_vals = outer_series.loc[valid_idx].values if outer_series is not None else None
    inner_vals = inner_series.loc[valid_idx].values if inner_series is not None else None

    outer_geom = gdf_utm.geometry.buffer(outer_vals)
    if min_distance is None or (inner_series is not None and (inner_series.loc[valid_idx] == 0).all()):
        buffered_valid = outer_geom
    else:
        inner_geom = gdf_utm.geometry.buffer(inner_vals)
        buffered_valid = outer_geom.difference(inner_geom)

    # assign buffered geometries back to full GeoDataFrame
    gdf_utm.loc[valid_idx, geometry] = buffered_valid
    result = gdf_utm.to_crs("EPSG:4326").set_geometry(geometry)
    return result


def add_sectors(df, lon='lon', lat='lat', azimuth='azimuth', distance='distance', angle='angle', difference_distance=None, base_arc_points=36, geometry='geometry'):
    """Create sector (wedge) polygons around points.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame with point coordinates.
    lon, lat : str
        Column names for longitude and latitude.
    azimuth : str or float
        Column name for bearing (degrees, 0 = north clockwise) or a scalar
        float to apply to all rows.
    distance : str or float
        Column name or scalar for outer radius in meters.
    angle : str or float
        Column name or scalar for total sector angle in degrees.
    difference_distance : str or float, optional
        If provided, creates a ring-sector between `difference_distance`
        (inner radius) and `distance` (outer radius). If None, creates a
        filled sector from the center to `distance`.
    base_arc_points : int
        Base number of points to use along a full 360° arc (default 36).
    geometry : str
        Name of the output geometry column.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with sector polygons in EPSG:4326.
    """
    df = df.copy()
    # validate lon/lat
    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Missing columns: {lon}, {lat}")

    # detect CRS (expects WGS84 lon/lat ranges)
    detected_crs = detect_crs(df, lon, lat)

    # prepare azimuth, distance, angle, inner radius arrays or scalars
    def _get_array_or_scalar(col_or_val, name):
        if isinstance(col_or_val, str):
            if col_or_val not in df.columns:
                raise KeyError(f"Missing column for {name}: {col_or_val}")
            return df[col_or_val].to_numpy()
        else:
            return float(col_or_val)

    az_arr = _get_array_or_scalar(azimuth, 'azimuth')
    dist_arr = _get_array_or_scalar(distance, 'distance')
    ang_arr = _get_array_or_scalar(angle, 'angle')
    inner_arr = None if difference_distance is None else _get_array_or_scalar(difference_distance, 'difference_distance')

    # project to local UTM for meter units
    points_proj, proj_crs = create_projected_kdtree(df, lon, lat)
    transformer = pyproj.Transformer.from_crs("EPSG:4326", proj_crs, always_xy=True)
    lons = df[lon].to_numpy()
    lats = df[lat].to_numpy()
    xs, ys = transformer.transform(lons, lats)

    from shapely.geometry import Polygon
    polys = []

    n = len(df)
    for i in range(n):
        cx = xs[i]
        cy = ys[i]

        # extract per-row or scalar parameters
        az = az_arr[i] if isinstance(az_arr, np.ndarray) else az_arr
        r = dist_arr[i] if isinstance(dist_arr, np.ndarray) else dist_arr
        a = ang_arr[i] if isinstance(ang_arr, np.ndarray) else ang_arr
        inner = None
        if inner_arr is not None:
            inner = inner_arr[i] if isinstance(inner_arr, np.ndarray) else inner_arr

        if np.isnan(cx) or np.isnan(cy):
            polys.append(None)
            continue

        # guard r and a
        if r is None or np.isnan(r) or r <= 0:
            polys.append(None)
            continue
        if a is None or np.isnan(a) or a <= 0:
            polys.append(None)
            continue

        # compute start and end angles in degrees (bearing: 0=north clockwise)
        start_deg = (az - a / 2.0) % 360
        end_deg = (az + a / 2.0) % 360

        # create linearized angle array handling wrap-around
        if end_deg < start_deg:
            end_deg += 360
        angs = np.linspace(start_deg, end_deg, max(4, int(base_arc_points * (a / 360.0))))

        # convert bearing (clockwise from north) to math angle measured from +x (east)
        thetas = np.deg2rad(90.0 - angs)

        # outer arc points
        outer_pts = [(cx + r * np.cos(t), cy + r * np.sin(t)) for t in thetas]

        if inner is None or inner <= 0:
            # sector polygon: center -> outer arc -> center
            coords = [(cx, cy)] + outer_pts + [(cx, cy)]
            poly = Polygon(coords)
            polys.append(poly)
        else:
            # build ring-sector between inner and outer radius
            # inner arc in reverse order to form a proper ring
            inner_thetas = thetas[::-1]
            inner_pts = [(cx + inner * np.cos(t), cy + inner * np.sin(t)) for t in inner_thetas]
            shell = outer_pts + inner_pts
            try:
                poly = Polygon(shell)
            except Exception:
                # fallback: create outer polygon to avoid failing
                coords = [(cx, cy)] + outer_pts + [(cx, cy)]
                poly = Polygon(coords)
            polys.append(poly)

    # construct GeoDataFrame, set projected CRS then convert to WGS84
    gdf_proj = gpd.GeoDataFrame(df.copy(), geometry=polys, crs=proj_crs)
    result = gdf_proj.set_geometry('geometry').to_crs('EPSG:4326')
    # rename geometry column if requested
    if geometry != 'geometry':
        result = result.rename_geometry(geometry)
    return result


def add_polygon(df, lon='lon', lat='lat', num_sides=4, radius=None, side_length=None, interior_angle=None, rotation=0.0, geometry='geometry'):

    """Create regular polygons around points.

    Parameters
    ----------
    df : pandas.DataFrame
        Input table with lon/lat columns.
    lon, lat : str
        Longitude and latitude column names.
    num_sides : int
        Number of polygon sides (>=3).
    radius : float, str, or None, default None
        Radius of the polygon in projected coordinates. Can be a scalar value or
        column name (str). Either 'radius' or 'side_length' must be provided.
    side_length : float, str, or None, default None
        Side length of the polygon in projected coordinates. Can be a scalar value or
        column name (str). If provided and radius is None, radius is computed as
        s / (2*sin(pi/n)). Either 'radius' or 'side_length' must be provided.
    interior_angle : float, str, or None, default None
        Interior angle in degrees for interior-mode (star/concave polygons).
        Can be a scalar value or column name (str). If `None` the function
        operates in exterior/regular mode. When provided, an inner radius is
        computed so the outer vertex apex has the specified interior angle.
    rotation : float or str, default 0.0
        Additional rotation in degrees applied to all polygons. Can be a scalar value
        or column name (str) for per-row rotation.
    
    geometry : str, default 'geometry'
        Name of the geometry column in the output GeoDataFrame.
        GeoDataFrame with polygon geometries projected to and output in EPSG:4326.
    Raises
    ------
    ValueError
        If lon or lat columns are missing, num_sides < 3, or neither radius nor
        side_length is provided.
    KeyError
        If a column name is referenced but does not exist in the input DataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with polygon geometries in EPSG:4326.
    """
    df = df.copy()
    # validations
    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Missing columns: {lon}, {lat}")
    if not isinstance(num_sides, int) or num_sides < 3:
        raise ValueError("num_sides must be an integer >= 3")

    # prepare projected coords
    points_proj, proj_crs = create_projected_kdtree(df, lon, lat)
    transformer = pyproj.Transformer.from_crs("EPSG:4326", proj_crs, always_xy=True)
    lons = df[lon].to_numpy()
    lats = df[lat].to_numpy()
    xs, ys = transformer.transform(lons, lats)

    # helpers to resolve scalar or column
    def _resolve(val, name):
        if val is None:
            return None
        if isinstance(val, str):
            if val not in df.columns:
                raise KeyError(f"Missing column for {name}: {val}")
            return df[val].to_numpy()
        else:
            return np.array([float(val)] * len(df))

    radius_arr = _resolve(radius, 'radius')
    side_arr = _resolve(side_length, 'side_length')

    if radius_arr is None and side_arr is None:
        raise ValueError("Either 'radius' or 'side_length' must be provided")
    if radius_arr is not None and side_arr is not None:
        raise ValueError("Provide only one of 'radius' or 'side_length' (set the other to None)")
    if radius_arr is None:
        # compute radius from side length: R = s / (2*sin(pi/n))
        radius_arr = side_arr / (2.0 * np.sin(np.pi / num_sides))

    # angle/rotation handling and default orientation:
    # - If `interior_angle` is provided -> interior-mode (star): compute an
    #   inner radius so the outer apex angle equals interior_angle.
    # - If `interior_angle` is None -> exterior/regular mode.
    # - `rotation` is an overall rotation (degrees) applied after a
    #   parity-based orientation offset (odd: vertex at north; even: top edge
    #   horizontal).
    if interior_angle is None:
        interior_arr = None
        # interior_angle affects shape (inner radius) only; no extra base rotation
        base_rot = np.zeros(len(df))
    else:
        interior_arr = _resolve(interior_angle, 'interior_angle')
        # For interior (star) mode, apply a default half-step rotation so an
        # outer vertex points to the top. Example: pentagram -> 360/5/2 = 36°.
        base_rot = np.full(len(df), 360.0 / float(num_sides) / 2.0)

    # resolve rotation (scalar or column)
    if isinstance(rotation, str):
        if rotation not in df.columns:
            raise KeyError(f"Missing column for rotation: {rotation}")
        rot_vals = df[rotation].to_numpy(dtype=float)
    else:
        rot_vals = np.array([float(rotation)] * len(df))

    # orientation baseline: vertex-up for odd n, flat-top for even n
    if num_sides % 2 == 1:
        orientation_base = 90.0
    else:
        orientation_base = 90.0 - 180.0 / float(num_sides)
    rot_deg = orientation_base + base_rot + rot_vals
    # user expects `rotation` to be clockwise degrees; convert to radians
    # math positive rotation is CCW, so negate to get clockwise rotation
    rot_arr = -np.deg2rad(rot_deg)

    # build polygons per row
    # Vectorized polygon vertex computation to reduce per-row trig calls
    from shapely.geometry import Polygon
    polys = [None] * len(df)

    # ensure arrays are numpy float arrays
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    radius_arr = np.asarray(radius_arr, dtype=float)
    rot_arr = np.asarray(rot_arr, dtype=float)

    # mask valid rows (finite center and positive radius)
    valid_mask = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(radius_arr) & (radius_arr > 0)
    if valid_mask.any():
        xs_valid = xs[valid_mask]
        ys_valid = ys[valid_mask]
        radii_valid = radius_arr[valid_mask]
        rot_valid = rot_arr[valid_mask]
        rot_exp = np.exp(1j * rot_valid)

        valid_indices = np.nonzero(valid_mask)[0]

        # handle exterior (regular) rows: num_sides vertices at radius R
        exterior_mask = (interior_arr is None)
        if interior_arr is not None:
            interior_arr_np = np.asarray(interior_arr, dtype=float)
        else:
            interior_arr_np = None

        # For rows where interior_angle is provided, build 2*num_sides vertices
        # alternating between outer radius R and computed inner radius r.
        base_angles_exterior = np.linspace(0.0, 2.0 * np.pi, num_sides, endpoint=False)
        base_complex_exterior = np.exp(1j * base_angles_exterior)

        base_angles_star = np.linspace(0.0, 2.0 * np.pi, 2 * num_sides, endpoint=False)
        base_complex_star = np.exp(1j * base_angles_star)

        for idx_row, i in enumerate(valid_indices):
            R = float(radii_valid[idx_row])
            rx = xs_valid[idx_row]
            ry = ys_valid[idx_row]
            rot_factor = rot_exp[idx_row]

            if interior_arr_np is None or np.isnan(interior_arr_np[i]):
                # exterior regular polygon
                complex_coords = (R * base_complex_exterior) * rot_factor
                vx = rx + complex_coords.real
                vy = ry + complex_coords.imag
                pts = list(zip(vx.tolist(), vy.tolist()))
                try:
                    polys[i] = Polygon(pts)
                except Exception:
                    polys[i] = None
            else:
                # interior (star-like) polygon: compute inner radius r per formula
                alpha_deg = float(interior_arr_np[i])
                phi = np.pi / float(num_sides)
                C = np.cos(phi)
                D = np.cos(2.0 * phi)
                A = np.cos(np.deg2rad(alpha_deg))

                a = (A - D)
                b = 2.0 * R * C * (1.0 - A)
                c = (A - 1.0) * (R * R)

                disc = b * b - 4.0 * a * c
                if disc < 0:
                    # numeric safety: skip invalid
                    polys[i] = None
                    continue
                r_inner = (-b + np.sqrt(disc)) / (2.0 * a)
                if r_inner <= 0 or not np.isfinite(r_inner):
                    polys[i] = None
                    continue

                radii_seq = np.empty(2 * num_sides, dtype=float)
                radii_seq[::2] = R
                radii_seq[1::2] = r_inner

                complex_coords = (radii_seq[None, :] * base_complex_star[None, :])[0] * rot_factor
                vx = rx + complex_coords.real
                vy = ry + complex_coords.imag
                pts = list(zip(vx.tolist(), vy.tolist()))
                try:
                    polys[i] = Polygon(pts)
                except Exception:
                    polys[i] = None

    gdf_proj = gpd.GeoDataFrame(df.copy(), geometry=polys, crs=proj_crs)
    result = gdf_proj.set_geometry('geometry').to_crs('EPSG:4326')
    # rename geometry if requested
    if geometry != 'geometry':
        result = result.rename_geometry(geometry)
    return result

def add_points(df1, lon='lon', lat='lat', geometry='geometry',crs='epsg:4326'):
    """Convert a DataFrame with longitude/latitude columns to a GeoDataFrame

    Parameters
    ----------
    df1 : pandas.DataFrame
        Input DataFrame containing coordinate columns.
    lon : str
        Longitude column name.
    lat : str
        Latitude column name.
    geometry : str
        Name of the geometry column to create.
    crs : str
        Coordinate reference system for the output GeoDataFrame (default 'epsg:4326').

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with Point geometries constructed from the provided lon/lat.
    """
    # validate inputs
    if df1 is None or df1.empty:
        raise ValueError("Input DataFrame is empty or None")
    
    if lon not in df1.columns:
        raise KeyError(f"Longitude column '{lon}' not found in DataFrame")
    
    if lat not in df1.columns:
        raise KeyError(f"Latitude column '{lat}' not found in DataFrame")
    
    # create a copy to avoid mutating the original DataFrame
    df = df1.copy()
    
    # create point geometries
    df[geometry] = [Point(x, y) for x, y in zip(df[lon], df[lat])]
    
    # create GeoDataFrame
    df_p = gpd.GeoDataFrame(df, crs="epsg:4326", geometry=geometry)
    
    return df_p

def add_buffer_groupbyid(df, lon='lon', lat='lat', distance=50,
                         columns_name='clusterid', id_label_prefix='cluster_', geom=False):
    """Group points into clusters by buffer distance and assign cluster IDs.

    This function creates buffers around points, dissolves overlapping
    buffers to form cluster polygons, and associates original points with
    their cluster polygons via a spatial join.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing longitude/latitude columns.
    lon, lat : str, optional
        Names of longitude and latitude columns (defaults 'lon'/'lat').
    distance : float, optional
        Buffer distance used for grouping (units depend on CRS), default 50.
    columns_name : str, optional
        Name of the output cluster ID column.
    id_label_prefix : str, optional
        Prefix used to construct cluster labels (e.g. 'cluster_0').
    geom : bool, optional
        If True, return a GeoDataFrame including cluster polygon geometries;
        otherwise return a plain DataFrame without geometry.

    Returns
    -------
    pd.DataFrame or geopandas.GeoDataFrame
        Input rows annotated with cluster IDs. If `geom=True`, the result
        includes cluster polygon geometries.
    """

    # validate input columns
    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Columns '{lon}' and '{lat}' must exist in dataframe")

    # create buffers around points
    data_buffer = add_buffer(df, lon, lat, distance)

    # dissolve overlapping buffers into cluster polygons
    data_dissolve = data_buffer[['geometry']].dissolve()

    # explode multi-part geometries into singlepart polygons
    data_explode = data_dissolve.explode(index_parts=False).reset_index(drop=True)[['geometry']]

    # assign cluster ids
    data_explode[columns_name] = id_label_prefix + data_explode.index.astype(str)

    # create point GeoDataFrame from original data
    data_points = add_points(df, lon, lat)

    # spatial join: associate points with cluster polygons
    data_sjoin = gpd.sjoin(data_points, data_explode, how='left', predicate='intersects')

    if geom:
        # keep geometry column but replace point geometry with cluster polygon
        data_columns = list(df.columns) + [columns_name]
        result = data_sjoin[data_columns].copy()

        # merge polygon geometry back via cluster id
        result = result.merge(
            data_explode[[columns_name, 'geometry']], 
            on=columns_name, 
            how='left'
        )

        # convert to GeoDataFrame
        result = gpd.GeoDataFrame(result, geometry='geometry', crs=data_explode.crs)
    else:
        # drop geometry column
        data_columns = list(df.columns) + [columns_name]
        result = data_sjoin[data_columns].copy()

    return result

def dog():
    try:
        import winsound
        # print("{}/tmp.wav".format(__path__[0]))
        winsound.PlaySound("{}/tmp.wav".format(__path__[0]), winsound.SND_FILENAME)
    except:
        print('播放失败')

def add_area(gdf, column='add_area', crs_epsg=None, area_type='int'):
    '''Add an area column (in square meters) to a GeoDataFrame.

    The geometry is temporarily projected to a suitable projected CRS to
    calculate areas in meters, then converted back to the original CRS.

    Parameters
    ----------
    gdf : GeoDataFrame
        Input GeoDataFrame with polygon geometries.
    column : str
        Name of the output area column.
    crs_epsg : int, optional
        Optional EPSG code for the projection to use for area calculation.
        If not provided, an appropriate UTM zone is chosen automatically.
    area_type : {'int', 'float'}
        Output data type for the area column.

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with the added area column (in square meters).
    '''
    # validate input
    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError("The input must be of the GeoDataFrame type.")

    if gdf.empty:
        warnings.warn("The input GeoDataFrame is empty.")
        gdf[column] = []
        return gdf

    # ensure geometries are polygons for area calculation
    if not all(geom.geom_type in ['Polygon', 'MultiPolygon'] for geom in gdf.geometry):
        raise ValueError("All geometries must be of the Polygon or MultiPolygon type in order to calculate the area.")

    # preserve original CRS
    original_crs = gdf.crs

    # if no explicit crs_epsg provided, choose an appropriate UTM zone
    if crs_epsg is None:
        # compute centroid to determine best UTM zone
        bounds = gdf.total_bounds  # minx, miny, maxx, maxy
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2

        # determine UTM zone number
        utm_zone = int((center_lon + 180) // 6) + 1
        # Northern hemisphere -> EPSG:326XX, southern -> EPSG:327XX
        hemisphere = 32600 if center_lat >= 0 else 32700
        target_crs = f"EPSG:{hemisphere + utm_zone}"
        print(f"Center: ({center_lon:.4f}, {center_lat:.4f}) → UTM Zone {utm_zone} {'N' if center_lat>=0 else 'S'} → {target_crs}")
    else:
        target_crs = f"EPSG:{crs_epsg}"

    # project to target CRS and compute area
    gdf_projected = gdf.to_crs(target_crs)
    gdf_projected[column] = gdf_projected.area

    # convert back to original CRS
    result = gdf_projected.to_crs(original_crs)
    if area_type == 'int':
        result[column] = result[column].astype(int)
    elif area_type == 'float':
        result[column] = result[column].astype(float)
    else:
        result[column] = result[column].astype(int)
    return result


def match_layer(df, layer, lon='lon', lat='lat', columns=None, default_value=None, match_method='one', sep=',', predicate='intersects'):
    """Match points in a DataFrame to a spatial layer (e.g., polygons) and add attributes.

    Parameters
    ----------
    df : pandas.DataFrame
        Input table with longitude and latitude.
    layer : str or geopandas.GeoDataFrame
        Path to spatial file (shp, geojson, etc.) or a GeoDataFrame.
    lon, lat : str
        Column names for coordinates in `df`.
    columns : str or list of str, optional
        Columns from the layer to add to `df`. If None, adds all columns (excluding geometry).
    default_value : scalar, optional
        Value to fill if no match is found.
    match_method : {'one', 'multi_cell', 'multi_row'}, default 'one'
        How to handle multiple matches for a single point:
        - 'one': Keep only one match (the first one found).
        - 'multi_cell': Combine values from multiple matches into a single string separated by `sep`.
        - 'multi_row': Expand the row for each match (explode).
    sep : str, default ','
        Separator used when match_method is 'multi_cell'.
    predicate : str, default 'intersects'
        Spatial predicate to use for the join (e.g., 'intersects', 'within').

    Returns
    -------
    pandas.DataFrame
        Input DataFrame with added columns from the matched layer.
    """
    if df.empty:
        return df

    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Columns {lon} and {lat} not found in DataFrame")

    # Prepare layer
    if isinstance(layer, str):
        # Handle file paths
        import os
        if not os.path.exists(layer):
            raise FileNotFoundError(f"Layer file not found: {layer}")
        layer_gdf = gpd.read_file(layer)
    elif isinstance(layer, gpd.GeoDataFrame):
        layer_gdf = layer.copy()
    else:
        raise TypeError("layer must be a file path or GeoDataFrame")

    # Standardize CRS to EPSG:4326 for matching
    if layer_gdf.crs is None:
         warnings.warn("Layer has no CRS, assuming EPSG:4326")
         layer_gdf.set_crs("EPSG:4326", inplace=True)
    elif layer_gdf.crs != "EPSG:4326":
        layer_gdf = layer_gdf.to_crs("EPSG:4326")

    # Determine columns to add
    geom_col = layer_gdf.geometry.name
    available_cols = [c for c in layer_gdf.columns if c != geom_col]
    if columns is None:
        target_cols = available_cols
    else:
        if isinstance(columns, str):
            columns = [columns]
        target_cols = columns
        # Check availability
        missing = [c for c in target_cols if c not in layer_gdf.columns]
        if missing:
            raise KeyError(f"Columns not found in layer: {missing}")

    # Keep only necessary columns in layer (plus geometry)
    layer_gdf = layer_gdf[target_cols + [geom_col]]

    # Prepare points
    temp_id = '___temp_id___'
    df_temp = df.copy()
    df_temp[temp_id] = range(len(df_temp))
    
    # Use existing add_points function
    points_gdf = add_points(df_temp, lon, lat)

    # Spatial Join
    try:
        joined = gpd.sjoin(points_gdf, layer_gdf, how='left', predicate=predicate)
    except Exception as e:
        raise RuntimeError(f"Spatial join failed: {e}")

    # Process results
    if match_method == 'one':
        # Drop duplicates, keeping first match
        result_joined = joined.drop_duplicates(subset=[temp_id])
        # Drop helper columns
        drop_cols = ['geometry', 'index_right', temp_id]
        result_joined = result_joined.drop(columns=[c for c in drop_cols if c in result_joined.columns])
        result = result_joined
        
    elif match_method == 'multi_row':
        # Expand rows
        result_joined = joined
        drop_cols = ['geometry', 'index_right', temp_id]
        result_joined = result_joined.drop(columns=[c for c in drop_cols if c in result_joined.columns])
        result = result_joined

    elif match_method == 'multi_cell':
        # Aggregate
        def agg_func(x):
            # Filter NaNs and convert to string
            valid = [str(v) for v in x if pd.notna(v)]
            # Unique values
            unique = sorted(list(set(valid)))
            if not unique:
                return np.nan
            return sep.join(unique)

        agg_dict = {col: agg_func for col in target_cols}
        
        # Group by temp_id
        grouped = joined.groupby(temp_id)[target_cols].agg(agg_dict).reset_index()
        
        # Merge back to original df (via df_temp which has temp_id)
        result = df_temp.merge(grouped, on=temp_id, how='left')
        result = result.drop(columns=[temp_id])
        
    else:
        raise ValueError(f"Invalid match_method: {match_method}. Must be 'one', 'multi_cell', or 'multi_row'.")

    # Handle default value for NaNs in target columns
    if default_value is not None:
        for col in target_cols:
            if col in result.columns:
                result[col] = result[col].fillna(default_value)

    return result


def df_to_gdf(df, geometry='geometry', crs="epsg:4326"): 
    """Convert a DataFrame with a WKT geometry column to a GeoDataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame containing a column with WKT strings.
    geometry : str, default 'geometry'
        Name of the column containing WKT geometries.
    crs : str, default 'epsg:4326'
        Coordinate reference system to assign to the GeoDataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with parsed geometries. The geometry column will be renamed to 'geometry'.
    """
    if df.empty:
        return gpd.GeoDataFrame(df, geometry=geometry, crs=crs)

    if geometry not in df.columns:
        raise KeyError(f"Column '{geometry}' not found in DataFrame")

    df_copy = df.copy()
    try:
        df_copy[geometry] = df_copy[geometry].apply(wkt.loads)
    except Exception as e:
        raise ValueError(f"Failed to parse WKT in column '{geometry}': {e}")
        
    gdf = gpd.GeoDataFrame(df_copy, crs=crs, geometry=geometry)
    
    # Rename geometry column to 'geometry' if it has a different name
    if geometry != 'geometry':
        gdf = gdf.rename_geometry('geometry')
        
    return gdf


def buffer(gdf, distance, geometry_col='geometry'):
    """Expand or shrink existing geometries by a buffer distance in meters.
    
    This function takes a GeoDataFrame with existing geometries, projects them
    to an appropriate UTM zone, applies a buffer, and projects back to the
    original CRS. All buffer operations are performed in projected coordinates
    (UTM) to ensure accurate meter-based distances.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Input GeoDataFrame with geometries to buffer.
    distance : float or int
        Buffer distance in meters. Positive values expand geometries,
        negative values shrink geometries (inner buffer).
    geometry_col : str, default 'geometry'
        Name of the geometry column to buffer.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with buffered geometries in the original CRS.

    Raises
    ------
    ValueError
        If input GeoDataFrame is empty.
    KeyError
        If geometry_col does not exist in the GeoDataFrame.

    Examples
    --------
    >>> import geopandas as gpd
    >>> import pandas as pd
    >>> from shapely.geometry import Point
    >>> import tablegis as tg
    
    >>> # Create a simple GeoDataFrame with points
    >>> gdf = gpd.GeoDataFrame(
    ...     {'id': [1, 2]},
    ...     geometry=[Point(0, 0), Point(1, 1)],
    ...     crs='EPSG:4326'
    ... )
    
    >>> # Expand buffer by 100 meters
    >>> gdf_expanded = tg.buffer(gdf, 100)
    
    >>> # Shrink buffer by 50 meters
    >>> gdf_shrunk = tg.buffer(gdf, -50)
    
    Notes
    -----
    - Buffer distance is specified in meters regardless of the input CRS.
    - For geographic CRS (e.g., EPSG:4326), coordinates are automatically
      projected to the appropriate UTM zone for accurate calculations.
    - If a GeoDataFrame has no CRS, it is assumed to be EPSG:4326.
    """
    if gdf.empty:
        raise ValueError("Input GeoDataFrame is empty")
    
    if geometry_col not in gdf.columns:
        raise KeyError(f"Geometry column '{geometry_col}' not found")
    
    # Preserve original CRS
    original_crs = gdf.crs
    if original_crs is None:
        warnings.warn("GeoDataFrame has no CRS, assuming EPSG:4326")
        original_crs = "EPSG:4326"
        gdf = gdf.set_crs(original_crs)
    
    # Estimate best UTM CRS
    try:
        utm_crs = gdf.estimate_utm_crs()
    except Exception as e:
        # Fallback: use centroid-based UTM
        bounds = gdf.total_bounds  # minx, miny, maxx, maxy
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        utm_zone = int((center_lon + 180) // 6) + 1
        hemisphere = 32600 if center_lat >= 0 else 32700
        utm_crs = f"EPSG:{hemisphere + utm_zone}"
        print(f"Fallback UTM CRS: {utm_crs}")
    
    # Project to UTM for meter-based buffer
    gdf_utm = gdf.to_crs(utm_crs)
    
    # Apply buffer
    gdf_utm[geometry_col] = gdf_utm[geometry_col].buffer(distance)
    
    # Project back to original CRS
    result = gdf_utm.to_crs(original_crs)
    
    return result


