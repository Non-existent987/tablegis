#!/usr/bin/env python
# coding: utf-8
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from scipy.spatial import cKDTree
import pyproj
# from .utils import *
from tablegis.utils import *
from typing import Optional
from tablegis import __path__
import warnings



def min_distance_onetable(df, lon='lon', lat='lat', idname='id', n=1, include_self=False) -> pd.DataFrame:
    """
    计算DataFrame中每个点的最近n个点(可选择是否包含自身)
    
    参数:
    df (DataFrame): 输入数据
    lon (str): 经度列名
    lat (str): 纬度列名
    id (str): ID列名，默认为'id'
    n (int): 要查找的最近邻数量
    include_self (bool): 是否包含自身点，默认为False
    
    返回:
    DataFrame: 添加了最近邻信息的副本
    示例：
    import pandas as pd
    import tablegis as tg

    # 创建两个示例DataFrame
    df2 = pd.DataFrame({
        'id': ['A', 'B', 'C', 'D'],
        'lon2': [116.403, 116.407, 116.404, 116.408],
        'lat2': [39.914, 39.918, 39.916, 39.919]
    })

    # 计算最近的1个点
    result = tg.min_distance_onetable(df2,'lon2','lat2',idname='id',n=1)
    print("结果示例（距离单位：米）:")
    print(result)
    print(result2)
    结果展示：
    **最近1个点**
    id	lon2	lat2	nearest1_id	nearest1_lon2	nearest1_lat2	nearest1_distance
    0	p1	114.01	30.01	p2	114.05	30.05	5881.336911
    1	p2	114.05	30.05	p1	114.01	30.01	5881.336911
    2	p3	114.12	30.12	p2	114.05	30.05	10289.545038

    """
    # 参数验证
    if n < 1:
        raise ValueError("n must be > 0")
    if lon not in df.columns or lat not in df.columns:
        raise ValueError("Longitude or latitude column not found")
    if idname not in df.columns:
        raise ValueError("ID column not found")
    if df.empty:
        return df  # 返回空 DataFrame 而不是抛出异常
    detected_crs = detect_crs(df, lon, lat)
    # 创建结果副本
    result = df.copy()
    
    # 处理空数据或数据量不足的情况
    if len(df) == 0 or (len(df) == 1 and not include_self):
        for i in range(1, n+1):
            result[f'nearest{i}_{idname}'] = np.nan
            result[f'nearest{i}_{lon}'] = np.nan
            result[f'nearest{i}_{lat}'] = np.nan
            result[f'nearest{i}_distance'] = np.nan
        if n > 1:
            result['mean_distance'] = np.nan
        return result
    
    # 提取坐标点
    points, proj_crs = create_projected_kdtree(result, lon, lat)

    # 创建KDTree
    tree = cKDTree(points)
    
    # 计算要查询的邻居数量
    # 如果不包含自身，需要额外查询1个点(因为第一个是自身)
    k_query = n + (0 if include_self else 1)
    # 确保不超过数据集大小
    k_query = min(k_query, len(df))
    
    # 查询最近的k个点
    distances, indices = tree.query(points, k=k_query, workers=-1)
    
    # 处理单个邻居的情况(确保是二维数组)
    if k_query == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)
    
    # 如果不包含自身，跳过第一列(自身点)
    if not include_self and k_query > 1:
        distances = distances[:, 1:]
        indices = indices[:, 1:]
    
    # 确保结果有正确的列数
    current_k = distances.shape[1] if len(distances.shape) > 1 else 1
    
    # 初始化结果数组
    result_indices = np.full((len(df), n), -1, dtype=int)
    result_distances = np.full((len(df), n), np.nan)
    
    # 填充有效数据
    valid_cols = min(current_k, n)
    if valid_cols > 0:
        if len(distances.shape) == 1:
            result_indices[:, 0] = indices
            result_distances[:, 0] = distances
        else:
            result_indices[:, :valid_cols] = indices[:, :valid_cols]
            result_distances[:, :valid_cols] = distances[:, :valid_cols]
    
    # 添加最近邻信息到结果DataFrame
    for i in range(n):
        # 获取当前列的索引
        col_indices = result_indices[:, i]
        
        # 初始化列
        id_values = []
        lon_values = []
        lat_values = []
        
        # 填充数据
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

    # 添加平均距离(当n>1时)
    if n > 1:
        dist_cols = [f'nearest{j+1}_distance' for j in range(n)]
        result['mean_distance'] = result[dist_cols].mean(axis=1)

    return result


def min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', lon2='lon2', lat2='lat2', df2_id='id', n=1,
                          crs1: Optional[str]=None, crs2: Optional[str]=None) -> pd.DataFrame:
    """
    计算df1中每个点到df2中最近的n个点的距离
    
    该函数使用KDTree算法高效计算两个DataFrame之间的最近邻距离。
    坐标系统必须一致（当前仅支持WGS84/EPSG:4326）。
    距离通过UTM投影计算，单位为米。
    
    Parameters
    ----------
    df1 : pd.DataFrame
        源数据表，包含待查询的坐标点
    df2 : pd.DataFrame
        目标数据表，包含参考坐标点
    lon1 : str, default='lon1'
        df1的经度列名
    lat1 : str, default='lat1'
        df1的纬度列名
    lon2 : str, default='lon2'
        df2的经度列名
    lat2 : str, default='lat2'
        df2的纬度列名
    df2_id : str, default='id'
        df2中用于标识点的ID列名
    n : int, default=1
        要查找的最近邻数量
    crs1 : str, optional
        df1的坐标系统，如 'EPSG:4326'。如果为None则自动检测
    crs2 : str, optional
        df2的坐标系统，如 'EPSG:4326'。如果为None则自动检测
    
    Returns
    -------
    pd.DataFrame
        返回df1的副本，添加以下列：
        - nearest{i}_{df2_id} : 第i近的点的ID
        - nearest{i}_{lon2} : 第i近的点的经度
        - nearest{i}_{lat2} : 第i近的点的纬度
        - nearest{i}_distance : 距离（米）
        - mean_distance : 前n个最近点的平均距离（当n>1时）
    
    Raises
    ------
    ValueError
        - 如果n < 1
        - 如果两个DataFrame的坐标系不一致
        - 如果坐标范围不符合WGS84标准
    
    Examples
    --------
    import pandas as pd
    df1 = pd.DataFrame({
        'id': [1, 2, 3],
        'lon1': [116.404, 116.405, 116.406],
        'lat1': [39.915, 39.916, 39.917]
    })
    df2 = pd.DataFrame({
        'id': ['A', 'B', 'C'],
        'lon2': [116.403, 116.407, 116.404],
        'lat2': [39.914, 39.918, 39.916]
    })
    # 计算df1中每个点到df2中最近的那个点
    result = tg.min_distance_twotable(df1, df2,lon1='lon1', lat1='lat1', lon2='lon2', lat2='lat2', df2_id='id', n=1)
    print(result)
    
    Notes
    -----
    - 距离计算使用UTM投影，确保精度
    - 使用cKDTree进行高效的最近邻搜索
    - 当n大于df2的点数时，缺失的邻居会用NaN填充
    - 坐标系统必须为WGS84 (EPSG:4326)
    """
    # 验证输入
    if n < 1:
        raise ValueError("参数 n 必须大于等于 1")
    # 处理空数据情况
    if len(df2) == 0 or len(df1) == 0:
        for i in range(1, n + 1):
            df1[f'nearest{i}_{df2_id}'] = np.nan
            df1[f'nearest{i}_{lon2}'] = np.nan
            df1[f'nearest{i}_{lat2}'] = np.nan
            df1[f'nearest{i}_distance'] = np.nan
        if n > 1:
            df1['mean_distance'] = np.nan
        return df1
    # 检测或验证坐标系
    detected_crs1 = detect_crs(df1, lon1, lat1)
    detected_crs2 = detect_crs(df2, lon2, lat2)
    
    # 如果用户指定了CRS，验证是否匹配
    if crs1 is not None and crs1 != detected_crs1:
        raise ValueError(
            f"指定的 crs1={crs1} 与检测到的坐标系 {detected_crs1} 不匹配"
        )
    if crs2 is not None and crs2 != detected_crs2:
        raise ValueError(
            f"指定的 crs2={crs2} 与检测到的坐标系 {detected_crs2} 不匹配"
        )
    
    # 检查两个DataFrame的坐标系是否一致
    if detected_crs1 != detected_crs2:
        raise ValueError(
            f"两个DataFrame的坐标系不一致！\n"
            f"df1 坐标系: {detected_crs1}\n"
            f"df2 坐标系: {detected_crs2}\n"
            f"请确保两个数据集使用相同的坐标系统。"
        )
    
    # 创建结果副本
    result = df1.copy()
    
    
    # 将df1坐标投影到UTM（单位：米）
    A_points, proj_crs = create_projected_kdtree(df1, lon1, lat1)
    
    # 为df2创建转换器（使用相同的UTM投影）
    transformer_b = pyproj.Transformer.from_crs(
        "EPSG:4326", 
        proj_crs, 
        always_xy=True
    )
    lons_b = df2[lon2].values
    lats_b = df2[lat2].values
    x_b, y_b = transformer_b.transform(lons_b, lats_b)
    B_points = np.column_stack((x_b, y_b))
    
    # 创建KDTree进行高效搜索
    tree = cKDTree(B_points)
    
    # 查询最近的n个点
    k = min(n, len(df2))
    distances, indices = tree.query(A_points, k=k, workers=-1)
    
    # 处理k=1时的维度问题
    if k == 1:
        distances = distances.reshape(-1, 1)
        indices = indices.reshape(-1, 1)

    # 添加最近邻信息
    for i in range(k):
        nearest_points = df2.iloc[indices[:, i]]
        result[f'nearest{i+1}_{df2_id}'] = nearest_points[df2_id].values
        result[f'nearest{i+1}_{lon2}'] = nearest_points[lon2].values
        result[f'nearest{i+1}_{lat2}'] = nearest_points[lat2].values
        result[f'nearest{i+1}_distance'] = distances[:, i]  # 单位：米
    
    # 添加缺失的列（当n > k时）
    for i in range(k, n):
        result[f'nearest{i+1}_{df2_id}'] = np.nan
        result[f'nearest{i+1}_{lon2}'] = np.nan
        result[f'nearest{i+1}_{lat2}'] = np.nan
        result[f'nearest{i+1}_distance'] = np.nan
    
    # 添加平均距离（当n > 1时）
    if n > 1:
        dist_cols = [f'nearest{i+1}_distance' for i in range(min(n, k))]
        if dist_cols:
            result['mean_distance'] = result[dist_cols].mean(axis=1)
        else:
            result['mean_distance'] = np.nan
    
    return result

def to_lonlat(df, lon, lat, from_crs, to_crs):
    """
    作用：在df上添加转换后的经纬度'。
    - df:DataFrame
    - lon, lat: 列名（字符串）
    - from_crs, to_crs: 支持的坐标系标识{"wgs84", "web_mercator", "cgcs2000", "gcj02", "bd09"}
        - "wgs84"       : EPSG:4326 (经纬度，WGS84，GPS 设备、北斗原始数据，通俗意义上的经纬度)
        - "web_mercator": EPSG:3857 (Web Mercator，Web地图采用，单位：米)
        - "cgcs2000"    : EPSG:4490 (中国国家大地坐标系，用于官方测绘、国土等领域)
        - "gcj02"       : 中国火星坐标系（加密偏移，高德、腾讯、谷歌中国地图等采用）
        - "bd09"        : 百度坐标系（在 GCJ02 基础上再加密，百度地图专用）
    返回：带新增列的 DataFrame
    抛错：当 from_crs 或 to_crs 非支持集合时抛 ValueError
    """
    return to_lonlat_utils(df, lon, lat, from_crs, to_crs)


def add_buffer(df, lon='lon', lat='lat',dis=None, geometry='geometry'):
    """
    创建精确的以“米”为单位的 buffer，基于正确的 UTM 投影。

    参数:
        df: DataFrame 含经纬度
        lon, lat: 经纬度列名
        dis: 字符串表示用距离的字段，数字表示固定距离单位（米）
        geometry: 输出几何列名

    返回:
        GeoDataFrame: 包含精确 buffer 的多边形，CRS=4326
    """
    df = df.copy()
    # 检查列是否存在
    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Missing columns: {lon}, {lat}")
    # 2. 数据验证
    lon_values = df[lon].dropna()
    lat_values = df[lat].dropna()
    
    # 检查是否有空值
    if len(lon_values) == 0 or len(lat_values) == 0:
        raise ValueError("经纬度列包含全部空值")
    # 检查经度范围 (-180 到 180)
    lon_min, lon_max = lon_values.min(), lon_values.max()
    lat_min, lat_max = lat_values.min(), lat_values.max()
    
    invalid_lon = (lon_min < -180) or (lon_max > 180)
    invalid_lat = (lat_min < -90) or (lat_max > 90)

    # 3. 处理异常情况
    if invalid_lon or invalid_lat:
        error_msg = f"坐标数据异常:\n"
        error_msg += f"  经度范围: [{lon_min:.4f}, {lon_max:.4f}] (标准: -180 到 180)\n"
        error_msg += f"  纬度范围: [{lat_min:.4f}, {lat_max:.4f}] (标准: -90 到 90)\n"
        raise ValueError(error_msg)

    # 计算中心点以确定最佳 UTM zone
    center_lon = df[lon].mean()
    center_lat = df[lat].mean()
    # 判断 UTM zone number
    utm_zone = int((center_lon + 180) // 6) + 1
    # 北半球 EPSG: 326XX；南半球 EPSG: 327XX
    hemisphere = 32600 if center_lat >= 0 else 32700
    target_crs = f"EPSG:{hemisphere + utm_zone}"
    print(f"Center: ({center_lon:.4f}, {center_lat:.4f}) → UTM Zone {utm_zone} {'N' if center_lat>=0 else 'S'} → {target_crs}")
    # 创建点并指定原始 CRS
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[lon], df[lat]),
        crs="EPSG:4326"
    )
    # 转到 UTM 进行 buffer（此时单位是米）
    gdf_utm = gdf.to_crs(target_crs)
    if type(dis) == str:
        gdf_utm[geometry] = gdf_utm[[geometry, dis]].apply(lambda x: x.iloc[0].buffer(x.iloc[1]), axis=1)
    elif type(dis) == float or type(dis) == int:
        gdf_utm[geometry] = gdf_utm.geometry.buffer(dis)
    else:
        raise ValueError(f"type Error: {dis}")
    
    # 转回 WGS84 便于可视化
    result = gdf_utm.set_geometry(geometry).to_crs("EPSG:4326")
    return result

def add_points(df1, lon='lon', lat='lat', geometry='geometry',crs='epsg:4326'):
    """
    将具有经度和纬度列的 DataFrame 转换为具有 Point 几何图形的 GeoDataFrame。
    
    参数
    ----------
    df1 : pandas.DataFrame
    lon : str, 填写精度的列名
    lat : str, 填写纬度的列名
    geometry : str, 默认geometry,添加的geometry列名
    crs : str,默认使用4326
    
    返回：geopandas.GeoDataFrame
    
    报错
    ------
    列名错误
        如果指定的经度或纬度列不在数据框中。
    值错误
        如果数据框为空，或者坐标值无效。
    
    举例
    --------
    import pandas as pd
    df = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'city': ['Beijing', 'Shanghai']
    })
    gdf = add_points(df)
    print(type(gdf))
    <class 'geopandas.geodataframe.GeoDataFrame'>
    
    # 使用自定义列名
    df2 = pd.DataFrame({
        'longitude': [116.4074],
        'latitude': [39.9042]
    })
    gdf2 = add_points(df2, lon='longitude', lat='latitude')
    
    说明
    -----
    - 坐标值应为有效的经度（-180 至 180）和纬度（-90 至 90）。
    """
    # 验证输入
    if df1 is None or df1.empty:
        raise ValueError("Input DataFrame is empty or None")
    
    if lon not in df1.columns:
        raise KeyError(f"Longitude column '{lon}' not found in DataFrame")
    
    if lat not in df1.columns:
        raise KeyError(f"Latitude column '{lat}' not found in DataFrame")
    
    # 创建一个副本以避免修改原始的数据框
    df = df1.copy()
    
    # 创建点几何体
    df[geometry] = [Point(x, y) for x, y in zip(df[lon], df[lat])]
    
    # 创建地理数据框
    df_p = gpd.GeoDataFrame(df, crs="epsg:4326", geometry=geometry)
    
    return df_p

def add_buffer_groupbyid(df, lon='lon', lat='lat', distance=50,
                         columns_name='聚合id', id_label_prefix='聚合_', geom=False):
    """
    按照给定的距离将点位聚合在一起，添加聚合ID列用于标识。
    该函数通过创建缓冲区、融合重叠区域、然后将原始点位与聚合区域关联，
    实现点位的空间聚类。
    
    参数
    ----------
    df : pd.DataFrame
        包含经纬度信息的DataFrame
    lon : str, optional
        经度字段名，默认为 'lon'
    lat : str, optional
        纬度字段名，默认为 'lat'
    distance : float, optional
        聚合的缓冲距离（单位取决于坐标系统），默认为 50
    columns_name : str, optional
        添加的聚合ID列名，默认为 '聚合id'
    id_label_prefix : str, optional
        聚合ID的前缀，默认为 '聚合_'
        例如：'聚合_' 会生成 '聚合_0', '聚合_1' 等
    geom : bool, optional
        是否返回包含geometry列的GeoDataFrame，默认为 False
        当为 True 时，geometry列包含聚合后的多边形区域
        当为 False 时，不包含geometry列
    
    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        添加了聚合ID列的数据框
        如果 geom=True，返回GeoDataFrame且geometry列为聚合多边形
        如果 geom=False，返回DataFrame且不包含geometry列
    
    举例
    --------
    import pandas as pd
    data = pd.DataFrame({
        'lon': [116.40, 116.41, 116.50],
        'lat': [39.90, 39.91, 39.95],
        'name': ['A', 'B', 'C']
    })
    
    # 不返回几何信息
    result = add_buffer_groupbyid(data, distance=1000)
    
    # 返回聚合多边形几何信息
    result_with_geom = add_buffer_groupbyid(data, distance=1000, geom=True)
    """
    
    # 参数验证
    if lon not in df.columns or lat not in df.columns:
        raise ValueError(f"Columns '{lon}' and '{lat}' must exist in dataframe")
    
    # 创建缓冲区
    data_buffer = add_buffer(df, lon, lat, distance)
    
    # 融合重叠的缓冲区
    data_dissolve = data_buffer[['geometry']].dissolve()
    
    # 分解多部件几何为单个几何
    data_explode = data_dissolve.explode(index_parts=False).reset_index(drop=True)[['geometry']]
    
    # 添加聚合ID
    data_explode[columns_name] = id_label_prefix + data_explode.index.astype(str)
    
    # 创建点几何
    data_points = add_points(df, lon, lat)
    
    # 空间连接：将点与聚合区域关联
    data_sjoin = gpd.sjoin(data_points, data_explode, how='left', predicate='intersects')
    
    if geom:
        # 保留geometry列，但使用聚合多边形替换点几何
        # 先获取原始数据列和聚合ID
        data_columns = list(df.columns) + [columns_name]
        result = data_sjoin[data_columns].copy()
        
        # 通过聚合ID关联回多边形geometry
        result = result.merge(
            data_explode[[columns_name, 'geometry']], 
            on=columns_name, 
            how='left'
        )
        
        # 转换为GeoDataFrame
        result = gpd.GeoDataFrame(result, geometry='geometry', crs=data_explode.crs)
    else:
        # 不保留geometry列
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

def add_area(gdf, column='面积', crs_epsg=None):
    '''把gdf新增一列'面积'单位是平方米
    临时转换成指定的投影坐标系计算面积后再转回原来的坐标系
    
    参数:
        gdf: GeoDataFrame
        column: str 输出面积列名
        crs_epsg: int 可选的投影坐标系EPSG代码，默认会根据数据自动选择UTM投影，常用的有32650
        
    返回:
        GeoDataFrame: 添加了面积列的GeoDataFrame
    '''
    # 检查输入
    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError("输入必须是GeoDataFrame类型")
        
    if gdf.empty:
        warnings.warn("输入GeoDataFrame为空")
        gdf[column] = []
        return gdf
        
    # 检查几何类型
    if not all(geom.geom_type in ['Polygon', 'MultiPolygon'] for geom in gdf.geometry):
        raise ValueError("所有几何必须是Polygon或MultiPolygon类型以计算面积")
    
    # 保存原始坐标系
    original_crs = gdf.crs
    
    # 如果没有指定crs_epsg，则自动计算最适合的UTM区域
    if crs_epsg is None:
        # 计算中心点以确定最佳 UTM zone
        bounds = gdf.total_bounds  # minx, miny, maxx, maxy
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # 判断 UTM zone number
        utm_zone = int((center_lon + 180) // 6) + 1
        # 北半球 EPSG: 326XX；南半球 EPSG: 327XX
        hemisphere = 32600 if center_lat >= 0 else 32700
        target_crs = f"EPSG:{hemisphere + utm_zone}"
        print(f"Center: ({center_lon:.4f}, {center_lat:.4f}) → UTM Zone {utm_zone} {'N' if center_lat>=0 else 'S'} → {target_crs}")
    else:
        target_crs = f"EPSG:{crs_epsg}"
        
    # 转换到目标坐标系并计算面积
    gdf_projected = gdf.to_crs(target_crs)
    gdf_projected[column] = gdf_projected.area
    
    # 转回原始坐标系
    result = gdf_projected.to_crs(original_crs)
    return result


