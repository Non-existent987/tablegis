import tablegis as tg
import pytest
import pandas as pd
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from tablegis.utils import wgs84_to_gcj02, gcj02_to_wgs84, wgs84_to_bd09, bd09_to_wgs84, transform

def test_min_distance_onetable():
    """测试 min_distance_onetable 函数"""
    
    # 测试用例1: 基本功能测试 - 查找最近1个点
    df = pd.DataFrame({
        'id': ['p1', 'p2', 'p3'],
        'lon': [114.01, 114.05, 114.12],
        'lat': [30.01, 30.05, 30.12]
    })
    
    result = tg.min_distance_onetable(df, lon='lon', lat='lat', idname='id', n=1)
    
    # 验证返回的DataFrame包含正确的列
    assert 'nearest1_id' in result.columns
    assert 'nearest1_lon' in result.columns
    assert 'nearest1_lat' in result.columns
    assert 'nearest1_distance' in result.columns
    
    # 验证p1的最近点是p2
    assert result.loc[0, 'nearest1_id'] == 'p2'
    # 验证距离是正数
    assert result.loc[0, 'nearest1_distance'] > 0
    
    # 测试用例2: 查找最近2个点
    result2 = tg.min_distance_onetable(df, lon='lon', lat='lat', idname='id', n=2)
    
    # 验证包含mean_distance列
    assert 'mean_distance' in result2.columns
    assert 'nearest2_id' in result2.columns
    
    # 验证平均距离计算正确
    assert not pd.isna(result2.loc[0, 'mean_distance'])
    
    # 测试用例3: 包含自身点
    result3 = tg.min_distance_onetable(df, lon='lon', lat='lat', idname='id', n=1, include_self=True)
    
    # 验证每个点的最近点是自己
    for i in range(len(df)):
        assert result3.loc[i, 'nearest1_id'] == df.loc[i, 'id']
        assert result3.loc[i, 'nearest1_distance'] == 0.0
    
    # 测试用例4: 自定义列名
    df_custom = pd.DataFrame({
        'point_id': ['A', 'B', 'C'],
        'longitude': [116.403, 116.407, 116.404],
        'latitude': [39.914, 39.918, 39.916]
    })
    
    result4 = tg.min_distance_onetable(df_custom, lon='longitude', lat='latitude', idname='point_id', n=1)
    assert 'nearest1_point_id' in result4.columns
    
    # 测试用例5: 边界情况 - 空DataFrame
    df_empty = pd.DataFrame({'id': [], 'lon': [], 'lat': []})
    result5 = tg.min_distance_onetable(df_empty, lon='lon', lat='lat', idname='id', n=1)
    assert len(result5) == 0
    
    # 测试用例6: 边界情况 - 单个点
    df_single = pd.DataFrame({
        'id': ['p1'],
        'lon': [114.01],
        'lat': [30.01]
    })
    result6 = tg.min_distance_onetable(df_single, lon='lon', lat='lat', idname='id', n=1)
    assert pd.isna(result6.loc[0, 'nearest1_id'])
    
    # 测试用例7: 异常处理 - n < 1
    with pytest.raises(ValueError, match="n must be > 0"):
        tg.min_distance_onetable(df, lon='lon', lat='lat', idname='id', n=0)
    
    # 测试用例8: 异常处理 - 列名不存在
    with pytest.raises(ValueError, match="Longitude or latitude column not found"):
        tg.min_distance_onetable(df, lon='wrong_lon', lat='lat', idname='id', n=1)
    
    with pytest.raises(ValueError, match="ID column not found"):
        tg.min_distance_onetable(df, lon='lon', lat='lat', idname='wrong_id', n=1)
    
    print("✓ test_min_distance_onetable 所有测试通过!")


def test_min_distance_twotable():
    """测试 min_distance_twotable 函数"""
    
    # 测试用例1: 基本功能测试
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

    result = tg.min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', 
                                    lon2='lon2', lat2='lat2', df2_id='id', n=1)
    
    # 验证返回的DataFrame包含正确的列
    assert 'nearest1_id' in result.columns
    assert 'nearest1_lon2' in result.columns
    assert 'nearest1_lat2' in result.columns
    assert 'nearest1_distance' in result.columns
    
    # 验证原始df1的列都保留
    assert 'lon1' in result.columns
    assert 'lat1' in result.columns
    
    # 验证距离都是正数
    assert all(result['nearest1_distance'] >= 0)
    
    # 测试用例2: 查找最近2个点
    result2 = tg.min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', 
                                     lon2='lon2', lat2='lat2', df2_id='id', n=2)
    
    # 验证包含mean_distance列
    assert 'mean_distance' in result2.columns
    assert 'nearest2_id' in result2.columns
    
    # 验证平均距离不为空
    assert not pd.isna(result2.loc[0, 'mean_distance'])
    
    # 测试用例3: n大于df2的点数
    result3 = tg.min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', 
                                     lon2='lon2', lat2='lat2', df2_id='id', n=5)
    
    # 验证超出的列被填充为NaN
    assert pd.isna(result3.loc[0, 'nearest4_id'])
    assert pd.isna(result3.loc[0, 'nearest5_distance'])
    
    # 测试用例4: 边界情况 - 空DataFrame
    df_empty = pd.DataFrame({'id': [], 'lon2': [], 'lat2': []})
    result4 = tg.min_distance_twotable(df1, df_empty, lon1='lon1', lat1='lat1', 
                                     lon2='lon2', lat2='lat2', df2_id='id', n=1)
    assert pd.isna(result4.loc[0, 'nearest1_id'])
    
    # 测试用例5: 异常处理 - n < 1
    with pytest.raises(ValueError, match="The parameter n must be greater than or equal to 1."):
        tg.min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', 
                             lon2='lon2', lat2='lat2', df2_id='id', n=0)
    
    # 测试用例6: 指定CRS参数
    result6 = tg.min_distance_twotable(df1, df2, lon1='lon1', lat1='lat1', 
                                     lon2='lon2', lat2='lat2', df2_id='id', n=1,
                                     crs1='EPSG:4326', crs2='EPSG:4326')
    assert 'nearest1_distance' in result6.columns
    
    # 测试用例7: 自定义df2_id列名
    df2_custom = df2.copy()
    df2_custom = df2_custom.rename(columns={'id': 'point_name'})
    result7 = tg.min_distance_twotable(df1, df2_custom, lon1='lon1', lat1='lat1', 
                                     lon2='lon2', lat2='lat2', df2_id='point_name', n=1)
    assert 'nearest1_point_name' in result7.columns
    
    print("✓ test_min_distance_twotable 所有测试通过!")



def test_wgs84_to_gcj02_and_nan():
    df = pd.DataFrame({
        "lon": [116.397487, np.nan],
        "lat": [39.908722, np.nan],
    })
    out = tg.to_lonlat(df, "lon", "lat", from_crs="wgs84", to_crs="gcj02")
    # 第一个点与标量函数结果接近
    exp_lon, exp_lat = wgs84_to_gcj02(116.397487, 39.908722)
    assert np.isclose(out.loc[0, "gcj02_lon"], exp_lon, atol=1e-6)
    assert np.isclose(out.loc[0, "gcj02_lat"], exp_lat, atol=1e-6)
    # 第二行原本是 nan，目标列也是 nan
    assert np.isnan(out.loc[1, "gcj02_lon"])
    assert np.isnan(out.loc[1, "gcj02_lat"])
    print("✓ test_wgs84_to_gcj02_and_nan 所有测试通过!")

def test_bd09_to_wgs84_roundtrip():
    # 先由 WGS84 生成 BD09，再从 BD09 转回 WGS84
    lon, lat = 116.397487, 39.908722
    bd_lon, bd_lat = wgs84_to_bd09(lon, lat)
    df = pd.DataFrame({"lon": [bd_lon], "lat": [bd_lat]})
    out = tg.to_lonlat(df, "lon", "lat", from_crs="bd09", to_crs="wgs84")
    # 反算应接近原始 WGS84（允许少量偏差）
    assert np.isclose(out.loc[0, "wgs84_lon"], lon, atol=1e-6)
    assert np.isclose(out.loc[0, "wgs84_lat"], lat, atol=1e-6)
    print("✓ test_bd09_to_wgs84_roundtrip 所有测试通过!")

def test_webmercator_and_back():
    # WGS84 -> WebMercator -> WGS84
    lon, lat = 116.397487, 39.908722
    # 先生成 web mercator
    mx, my = transform(lon, lat, "wgs84", "web_mercator")
    df = pd.DataFrame({"lon": [mx], "lat": [my]})
    out = tg.to_lonlat(df, "lon", "lat", from_crs="web_mercator", to_crs="wgs84")
    assert np.isclose(out.loc[0, "wgs84_lon"], lon, atol=1e-6)
    assert np.isclose(out.loc[0, "wgs84_lat"], lat, atol=1e-6)
    print("✓ test_webmercator_and_back 所有测试通过!")

def test_unknown_crs_raises():
    df = pd.DataFrame({"lon": [116.4], "lat": [39.9]})
    with pytest.raises(ValueError):
        tg.to_lonlat(df, "lon", "lat", from_crs="unknown", to_crs="wgs84")
    with pytest.raises(ValueError):
        tg.to_lonlat(df, "lon", "lat", from_crs="wgs84", to_crs="unknown")
    print("✓ test_unknown_crs_raises 所有测试通过!")

def test_add_buffer():
    """测试 add_buffer 函数的基本功能"""
    import pandas as pd
    import geopandas as gpd
    import pytest
    
    # 测试1: 基本固定距离（整数）
    df = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'name': ['北京', '上海']
    })
    
    result = tg.add_buffer(df, lon='lon', lat='lat', dis=1000)
    
    assert isinstance(result, gpd.GeoDataFrame), "返回类型应该是 GeoDataFrame"
    assert result.crs.to_string() == "EPSG:4326", "CRS 应该是 EPSG:4326"
    assert len(result) == 2, "应该返回2行数据"
    assert all(result.geometry.geom_type == 'Polygon'), "几何类型应该是 Polygon"
    assert 'name' in result.columns, "原始列应该保留"
    
    # 测试1.5: 基本固定距离（浮点数）
    result_float = tg.add_buffer(df, lon='lon', lat='lat', dis=1000.5)
    assert isinstance(result_float, gpd.GeoDataFrame), "浮点数距离应该正常工作"
    assert len(result_float) == 2, "应该返回2行数据"
    
    # 测试2: 使用列名指定距离
    df2 = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'buffer_size': [500, 1000]
    })
    
    result2 = tg.add_buffer(df2, lon='lon', lat='lat', dis='buffer_size')
    assert len(result2) == 2, "应该返回2行数据"
    assert all(result2.geometry.geom_type == 'Polygon'), "几何类型应该是 Polygon"
    
    # 测试3: 错误处理 - 缺失列
    df3 = pd.DataFrame({'x': [116.4074], 'y': [39.9042]})
    with pytest.raises(ValueError, match="Missing columns"):
        tg.add_buffer(df3, lon='lon', lat='lat', dis=1000)
    
    # 测试4: 错误处理 - 无效经度（超出范围）
    df4 = pd.DataFrame({'lon': [200.0], 'lat': [39.9042]})
    with pytest.raises(ValueError, match="Coordinate data anomaly"):
        tg.add_buffer(df4, dis=1000)
    
    # 测试5: 错误处理 - 无效纬度（超出范围）
    df5 = pd.DataFrame({'lon': [116.4074], 'lat': [100.0]})
    with pytest.raises(ValueError, match="Coordinate data anomaly"):
        tg.add_buffer(df5, dis=1000)
    
    # 测试6: 错误处理 - 全部为空值
    df6 = pd.DataFrame({'lon': [None, None], 'lat': [None, None]})
    with pytest.raises(ValueError, match="contain all null values"):
        tg.add_buffer(df6, dis=1000)
    
    # 测试7: 错误处理 - 错误的 dis 类型
    df7 = pd.DataFrame({'lon': [116.4074], 'lat': [39.9042]})
    with pytest.raises(ValueError, match="type Error"):
        tg.add_buffer(df7, dis=[1000])  # 传入列表类型
    
    # 测试8: 包含部分空值的数据（应该正常处理非空值）
    df8 = pd.DataFrame({
        'lon': [116.4074, None, 121.4737],
        'lat': [39.9042, 31.2304, None],
        'name': ['北京', '天津', '上海']
    })
    result8 = tg.add_buffer(df8, lon='lon', lat='lat', dis=1000)
    assert len(result8) == 3, "应该返回所有行（包括空值行）"
    
    # 测试9: 自定义 geometry 列名
    df9 = pd.DataFrame({'lon': [116.4074], 'lat': [39.9042]})
    result9 = tg.add_buffer(df9, lon='lon', lat='lat', dis=1000, geometry='buffer_geom')
    assert 'buffer_geom' in result9.columns, "自定义 geometry 列名应该存在"

    # 测试10: numeric min_distance -> 画出圆环（内外半径）
    df_ring = pd.DataFrame({'lon': [116.4074], 'lat': [39.9042]})
    full = tg.add_buffer(df_ring, lon='lon', lat='lat', dis=1000)
    ring = tg.add_buffer(df_ring, lon='lon', lat='lat', dis=1000, min_distance=200)
    assert isinstance(ring, gpd.GeoDataFrame)
    assert ring.geometry.iloc[0].geom_type == 'Polygon'
    assert ring.geometry.iloc[0].area > 0
    assert ring.geometry.iloc[0].area < full.geometry.iloc[0].area

    # 测试11: min_distance 支持列名
    df_ring2 = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'out': [1000, 500],
        'inner': [200, 100]
    })
    res_ring2 = tg.add_buffer(df_ring2, lon='lon', lat='lat', dis='out', min_distance='inner')
    assert len(res_ring2) == 2
    assert all(res_ring2.geometry.geom_type == 'Polygon')

    # 测试12: min_distance 等于 0 时等价于普通 buffer
    ring0 = tg.add_buffer(df_ring, lon='lon', lat='lat', dis=1000, min_distance=0)
    assert np.isclose(ring0.geometry.iloc[0].area, full.geometry.iloc[0].area)

    # 测试13: 错误处理 - 无效 min_distance 类型
    with pytest.raises(ValueError, match="type Error"):
        tg.add_buffer(df7, dis=1000, min_distance=[100])  # 传入列表类型

    # 测试14: 错误处理 - 指定的 min_distance 列不存在
    with pytest.raises(KeyError):
        tg.add_buffer(df2, lon='lon', lat='lat', dis='buffer_size', min_distance='noexist')
    
    print("✓ test_add_buffer 所有测试通过!")


def test_add_points():
    """
    “添加点数”测试函数。
    测试基本功能、自定义列名以及错误处理机制。
    """
    
    # 测试 1：使用默认列名的基本功能
    df1 = pd.DataFrame({
        'lon': [116.4074, 121.4737, 113.2644],
        'lat': [39.9042, 31.2304, 23.1291],
        'city': ['Beijing', 'Shanghai', 'Guangzhou']
    })
    
    result1 = tg.add_points(df1)
    assert isinstance(result1, gpd.GeoDataFrame), "Result should be a GeoDataFrame"
    assert 'geometry' in result1.columns, "Geometry column should exist"
    assert len(result1) == 3, "Should have 3 rows"
    assert result1.crs.to_string() == "EPSG:4326", "CRS should be EPSG:4326"
    assert all(isinstance(geom, Point) for geom in result1.geometry), "All geometries should be Points"

    
    # 测试 2：自定义列名
    df2 = pd.DataFrame({
        'longitude': [0.0, 10.0],
        'latitude': [0.0, 20.0],
        'name': ['Point A', 'Point B']
    })
    
    result2 = tg.add_points(df2, lon='longitude', lat='latitude', geometry='geom')
    assert 'geom' in result2.columns, "Custom geometry column should exist"
    assert result2.geometry.name == 'geom', "Geometry column name should be 'geom'"

    
    # 测试 3：验证原始数据框未被修改
    df3 = pd.DataFrame({'lon': [1.0], 'lat': [2.0]})
    original_columns = df3.columns.tolist()
    tg.add_points(df3)
    assert df3.columns.tolist() == original_columns, "Original DataFrame should not be modified"

    
    # 测试 4：错误处理 - 缺失列
    df4 = pd.DataFrame({'x': [1.0], 'y': [2.0]})
    try:
        tg.add_points(df4)
        assert False, "Should raise KeyError for missing columns"
    except KeyError:
        pass
    
    # 测试 5：错误处理 - 空数据框
    df5 = pd.DataFrame({'lon': [], 'lat': []})
    try:
        tg.add_points(df5)
        assert False, "Should raise ValueError for empty DataFrame"
    except ValueError:
        pass
    
    # 测试 6：验证坐标值
    df6 = pd.DataFrame({'lon': [100.5], 'lat': [50.5]})
    result6 = tg.add_points(df6)
    point = result6.geometry.iloc[0]
    assert point.x == 100.5, "Longitude value should match"
    assert point.y == 50.5, "Latitude value should match"
    print("✓ test_add_points 所有测试通过!")

def test_add_buffer_groupbyid():
    """
    测试 add_buffer_groupbyid 函数的功能
    """
    
    # 准备测试数据
    test_data = pd.DataFrame({
        'lon': [116.40, 116.41, 116.50, 116.51],
        'lat': [39.90, 39.91, 39.95, 39.96],
        'name': ['A', 'B', 'C', 'D'],
        'value': [1, 2, 3, 4]
    })
    
    # 测试1: 不返回geometry
    result_no_geom = tg.add_buffer_groupbyid(
        test_data, 
        lon='lon', 
        lat='lat',
        distance=1000,
        geom=False
    )
    
    assert isinstance(result_no_geom, pd.DataFrame), "应该返回DataFrame"
    assert 'geometry' not in result_no_geom.columns, "不应包含geometry列"
    assert 'clusterid' in result_no_geom.columns, "应该包含聚合id列"
    assert all(col in result_no_geom.columns for col in test_data.columns), "应保留原始列"
    
    # 测试2: 返回geometry（多边形）
    result_with_geom = tg.add_buffer_groupbyid(
        test_data,
        lon='lon',
        lat='lat', 
        distance=1000,
        geom=True
    )
    
    assert isinstance(result_with_geom, gpd.GeoDataFrame), "应该返回GeoDataFrame"
    assert 'geometry' in result_with_geom.columns, "应该包含geometry列"
    assert 'clusterid' in result_with_geom.columns, "应该包含聚合id列"
    
    # 验证geometry是多边形而不是点
    for geom in result_with_geom.geometry.dropna():
        assert isinstance(geom, Polygon), f"geometry应该是Polygon类型，但是 {type(geom)}"
    
    # 测试3: 自定义列名和前缀
    result_custom = tg.add_buffer_groupbyid(
        test_data,
        columns_name='cluster_id',
        id_label_prefix='C_',
        geom=False
    )
    
    assert 'cluster_id' in result_custom.columns, "应该使用自定义列名"
    assert result_custom['cluster_id'].iloc[0].startswith('C_'), "应该使用自定义前缀"
    
    # 测试4: 验证点与多边形的对应关系
    result_check = tg.add_buffer_groupbyid(test_data, distance=1000, geom=True)
    
    # 每个点应该在其对应的聚合多边形内
    for idx, row in result_check.iterrows():
        if pd.notna(row['clusterid']) and pd.notna(row.geometry):
            point = Point(row['lon'], row['lat'])
            assert row.geometry.contains(point) or row.geometry.touches(point), \
                f"点 {row['name']} 应该在其聚合多边形内"
    print("✓ test_add_buffer_groupbyid 所有测试通过!")

def test_add_area():
    """测试为GeoDataFrame添加面积列"""
    
    # 测试1: 基本功能 - 自动选择坐标系
    polygon = Polygon([(111, 23), (111, 33), (112, 33), (112, 23)])
    gdf = gpd.GeoDataFrame({'id': [1], 'geometry': [polygon]}, crs="epsg:32650")
    
    result_gdf = tg.add_area(gdf, column='area')
    
    assert 'area' in result_gdf.columns
    assert result_gdf['area'].iloc[0] > 0
    print(type(result_gdf['area'].iloc[0]))
    assert isinstance(result_gdf['area'].iloc[0], (np.integer, np.floating))
    assert result_gdf.crs == gdf.crs  # 验证CRS保持不变
    
    # 测试2: 手动指定坐标系
    result_gdf_manual = tg.add_area(gdf, 'area_manual', crs_epsg=32650)
    assert 'area_manual' in result_gdf_manual.columns
    assert result_gdf_manual['area_manual'].iloc[0] > 0
    assert result_gdf_manual.crs == gdf.crs  # 验证返回原始CRS
    
    # 测试3: 测试area_type参数
    result_int = tg.add_area(gdf, 'area_int', area_type='int')
    assert result_int['area_int'].dtype == int
    
    result_float = tg.add_area(gdf, 'area_float', area_type='float')
    assert result_float['area_float'].dtype == float
    
    # 测试4: 多个多边形
    polygons = [
        Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
        Polygon([(2, 2), (2, 3), (3, 3), (3, 2)])
    ]
    gdf_multi = gpd.GeoDataFrame({'id': [1, 2], 'geometry': polygons}, crs="epsg:4326")
    result_multi = tg.add_area(gdf_multi, 'area')
    assert len(result_multi) == 2
    # assert all(result_multi['area'] > 0)
    
    print('✓ 所有测试通过!')
def test_add_sectors():
    """测试 add_sectors 函数的基本行为（扇形和扇弧形）"""
    df = pd.DataFrame({
        'lon': [116.397487, 116.398000],
        'lat': [39.908722, 39.909000],
        'az': [0, 90],
        'dist': [100, 200],
        'ang': [60, 45]
    })

    # 按列指定参数
    res = tg.add_sectors(df, lon='lon', lat='lat', azimuth='az', distance='dist', angle='ang')
    assert isinstance(res, gpd.GeoDataFrame)
    assert len(res) == 2
    assert all((g is None) or (g.geom_type == 'Polygon') for g in res.geometry)

    # 使用标量参数（统一设置）
    res2 = tg.add_sectors(df, lon='lon', lat='lat', azimuth=45.0, distance=150.0, angle=90.0)
    assert isinstance(res2, gpd.GeoDataFrame)

    # 扇弧形（内外半径差）
    df1 = pd.DataFrame({'lon': [116.397487], 'lat': [39.908722], 'az': [0], 'dist': [200], 'ang': [90], 'inner': [100]})
    res3 = tg.add_sectors(df1, lon='lon', lat='lat', azimuth='az', distance='dist', angle='ang', difference_distance='inner')
    assert isinstance(res3, gpd.GeoDataFrame)
    assert res3.geometry.iloc[0] is not None
    assert res3.geometry.iloc[0].area > 0
    print("✓ test_add_sectors 所有测试通过!")


def test_add_polygon():
    """测试 add_polygon 的基本功能与参数校验"""
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Polygon
    import pytest

    # 基本正方形测试（使用 radius）
    df = pd.DataFrame({'lon': [116.397487], 'lat': [39.908722]})
    res = tg.add_polygon(df, lon='lon', lat='lat', num_sides=4, radius=100)
    assert isinstance(res, gpd.GeoDataFrame)
    assert len(res) == 1
    assert isinstance(res.geometry.iloc[0], Polygon)
    assert res.geometry.iloc[0].area > 0

    # 使用 side_length 计算半径
    df2 = pd.DataFrame({'lon': [116.397487, 116.4], 'lat': [39.908722, 39.909]})
    res2 = tg.add_polygon(df2, lon='lon', lat='lat', num_sides=6, side_length=50)
    assert len(res2) == 2
    assert all(g is None or g.geom_type == 'Polygon' for g in res2.geometry)

    # 错误：边数不足
    with pytest.raises(ValueError):
        tg.add_polygon(df, num_sides=2, radius=10)

    # 错误：缺少列
    df3 = pd.DataFrame({'x': [1], 'y': [2]})
    with pytest.raises(ValueError):
        tg.add_polygon(df3, lon='lon', lat='lat', num_sides=3, radius=10)

    # 用户示例：五角星（内角模式）
    df_star = pd.DataFrame({'lon': [116.397487], 'lat': [39.908722]})
    res_star = tg.add_polygon(df_star, lon='lon', lat='lat', num_sides=5, radius=400, side_length=None, interior_angle=20, rotation=0)
    assert isinstance(res_star, gpd.GeoDataFrame)
    assert isinstance(res_star.geometry.iloc[0], Polygon)
    assert res_star.geometry.iloc[0].area > 0

    # 用户示例：正六边形（外角模式，按边长）
    df_hex = pd.DataFrame({'lon': [116.397487], 'lat': [39.908722]})
    res_hex = tg.add_polygon(df_hex, lon='lon', lat='lat', num_sides=6, radius=None, side_length=400, interior_angle=None, rotation=0)
    assert isinstance(res_hex, gpd.GeoDataFrame)
    assert isinstance(res_hex.geometry.iloc[0], Polygon)
    assert res_hex.geometry.iloc[0].area > 0

    print("✓ test_add_polygon 所有测试通过!")

def test_match_layer():
    """测试 match_layer 功能"""
    # Create dummy layer
    p1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]) # Square at 0,0 - 1,1
    p2 = Polygon([(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)]) # Square overlapping p1
    
    layer_df = gpd.GeoDataFrame({
        'id': [1, 2],
        'name': ['A', 'B'],
        'geometry': [p1, p2]
    }, crs="EPSG:4326")
    
    # Create dummy points
    df = pd.DataFrame({
        'lon': [0.2, 0.6, 1.2, 2.0],
        'lat': [0.2, 0.6, 1.2, 2.0],
        'val': [10, 20, 30, 40]
    })
    
    # Test 1: Match 'one' (default)
    res_one = tg.match_layer(df, layer_df, columns=['name'])
    assert len(res_one) == 4
    assert res_one.iloc[0]['name'] == 'A'
    assert res_one.iloc[2]['name'] == 'B'
    assert pd.isna(res_one.iloc[3]['name'])
    
    # Test 2: Match 'multi_cell'
    res_multi = tg.match_layer(df, layer_df, columns=['name'], match_method='multi_cell', sep=';')
    val = res_multi.iloc[1]['name']
    assert val == 'A;B' or val == 'B;A'
    
    # Test 3: Match 'multi_row'
    res_row = tg.match_layer(df, layer_df, columns=['name'], match_method='multi_row')
    # Point 2 matches 2 polygons, others match 1 or 0.
    # Total rows: 1 (pt1) + 2 (pt2) + 1 (pt3) + 1 (pt4) = 5 rows.
    assert len(res_row) == 5
    
    # Test 4: Default value
    res_default = tg.match_layer(df, layer_df, columns=['name'], default_value='None')
    assert res_default.iloc[3]['name'] == 'None'
    print("✓ test_match_layer 所有测试通过!")

def test_df_to_gdf():
    """测试 df_to_gdf 功能"""
    from shapely import wkt
    
    # 构造含WKT的DataFrame
    df = pd.DataFrame({
        'id': [1, 2],
        'wkt_geom': ['POINT(116.4 39.9)', 'POINT(121.5 31.2)']
    })
    
    # 正常转换
    gdf = tg.df_to_gdf(df, geometry='wkt_geom')
    
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs == "EPSG:4326"
    assert len(gdf) == 2
    assert isinstance(gdf.geometry.iloc[0], Point)
    assert gdf.geometry.iloc[0].x == 116.4
    
    # 错误：列不存在
    with pytest.raises(KeyError):
        tg.df_to_gdf(df, geometry='missing_col')
        
    # 错误：WKT格式错误
    df_bad = pd.DataFrame({'geom': ['NOT A WKT']})
    with pytest.raises(ValueError):
        tg.df_to_gdf(df_bad, geometry='geom')
        
    print("✓ test_df_to_gdf 所有测试通过!")

def test_match_layer_custom_geometry():
    """测试 match_layer 处理非标准 geometry 列名"""
    p1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    layer_df = gpd.GeoDataFrame({
        'id': [1],
        'val': ['A'],
        'geometry': [p1]
    }, crs="EPSG:4326")
    
    # 重命名 geometry 列
    layer_df = layer_df.rename_geometry('custom_geom')
    
    df = pd.DataFrame({'lon': [0.5], 'lat': [0.5]})
    
    # 应该能正常运行，不会因为找不到 'geometry' 列报错
    res = tg.match_layer(df, layer_df, columns=['val'])
    assert res.iloc[0]['val'] == 'A'
    print("✓ test_match_layer_custom_geometry 所有测试通过!")

def test_df_to_gdf_new_features():
    """测试 df_to_gdf 的新特性：crs 参数和列重命名"""
    df = pd.DataFrame({
        'wkt_col': ['POINT(116.4 39.9)']
    })
    
    # 测试自定义 CRS 和列重命名
    # 输入列名是 'wkt_col'，输出应该是 'geometry'
    gdf = tg.df_to_gdf(df, geometry='wkt_col', crs="EPSG:3857")
    
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs == "EPSG:3857"
    assert 'geometry' in gdf.columns
    assert gdf.geometry.name == 'geometry'
    # 确认原来的列名不再作为 geometry
    if 'wkt_col' in gdf.columns:
        # 如果原始列还保留（df_copy），它不再是 geometry 列
        assert gdf.geometry.name != 'wkt_col'
        
    print("✓ test_df_to_gdf_new_features 所有测试通过!")

if __name__ == "__main__":
    test_min_distance_onetable()
    test_min_distance_twotable()
    test_wgs84_to_gcj02_and_nan()
    test_bd09_to_wgs84_roundtrip()
    test_webmercator_and_back()
    test_unknown_crs_raises()
    test_add_buffer()
    test_add_points()
    test_add_buffer_groupbyid()
    test_add_area()
    test_add_sectors()
    test_add_polygon()
    test_match_layer()
    test_df_to_gdf()
    test_match_layer_custom_geometry()
    test_df_to_gdf_new_features()
