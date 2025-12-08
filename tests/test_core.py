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
    with pytest.raises(ValueError, match="参数 n 必须大于等于 1"):
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
    
    # 测试1: 基本固定距离
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
    
    # 测试2: 使用列名指定距离
    df2 = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'buffer_size': [500, 1000]
    })
    
    result2 = tg.add_buffer(df2, lon='lon', lat='lat', dis='buffer_size')
    assert len(result2) == 2, "应该返回2行数据"
    
    # 测试3: 错误处理 - 缺失列
    df3 = pd.DataFrame({'x': [116.4074], 'y': [39.9042]})
    try:
        tg.add_buffer(df3, lon='lon', lat='lat', dis=1000)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "Missing columns" in str(e)
    
    # 测试4: 错误处理 - 无效经度
    df4 = pd.DataFrame({'lon': [200.0], 'lat': [39.9042]})
    try:
        tg.add_buffer(df4, dis=1000)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "坐标数据异常" in str(e)
    
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
    assert '聚合id' in result_no_geom.columns, "应该包含聚合id列"
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
    assert '聚合id' in result_with_geom.columns, "应该包含聚合id列"
    
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
        if pd.notna(row['聚合id']) and pd.notna(row.geometry):
            point = Point(row['lon'], row['lat'])
            assert row.geometry.contains(point) or row.geometry.touches(point), \
                f"点 {row['name']} 应该在其聚合多边形内"
    print("✓ test_add_buffer_groupbyid 所有测试通过!")
def test_add_area():
    """测试为GeoDataFrame添加面积列"""
    # 创建一个多边形
    polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    gdf = gpd.GeoDataFrame({'id': [1], 'geometry': [polygon]}, crs="epsg:4326")
    
    # 添加面积列（自动选择坐标系）
    result_gdf = tg.add_area(gdf, 'area')
    
    # 验证结果
    assert 'area' in result_gdf.columns
    assert result_gdf['area'].iloc[0] > 0  # 面积应该为正值
    
    # 测试手动指定坐标系
    result_gdf_manual = tg.add_area(gdf, 'area_manual', crs_epsg=32650)
    assert 'area_manual' in result_gdf_manual.columns
    assert result_gdf_manual['area_manual'].iloc[0] > 0  # 面积应该为正值
    
    # 测试错误处理 - 输入类型错误
    with pytest.raises(TypeError):
        tg.add_area(pd.DataFrame())
        
    # 测试错误处理 - 几何类型错误
    point_gdf = gpd.GeoDataFrame({'geometry': [Point(0, 0)]})
    with pytest.raises(ValueError):
        tg.add_area(point_gdf)
        
    # 测试警告 - 空GeoDataFrame
    empty_gdf = gpd.GeoDataFrame({'geometry': []})
    with pytest.warns(UserWarning):
        tg.add_area(empty_gdf)
    print('成功')
    print("✓ test_add_area 所有测试通过!")

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
