# tablegis

[English](README.md) | [简体中文](README.zh-CN.md)

`tablegis` 是一个用于地理空间数据处理和分析的Python包，它基于 `geopandas` 、`pandas`、`shapely`、`pyproj`等构建，提供了一系列简化常见GIS操作的工具函数。

## 功能

*   **距离计算**: 高效计算df之间的最近距离。
*   **空间分析**: 创建缓冲区(输入米)、泰森多边形、Delaunay三角网等。
*   **格式转换**: 方便地在 `GeoDataFrame` 与 `Shapefile`, `KML` 等格式之间转换。
*   **坐标聚合**: 提供将坐标点聚合到网格的工具。
*   **几何操作**: 包括合并多边形、计算质心、添加扇区等。

## 安装

1、你可以通过pip从PyPI安装 `tablegis`:

```bash
pip install tablegis
```

2、或者，直接从GitHub仓库安装最新版本：

```bash
pip install git+https://github.com/Non-existent987/tablegis.git
```
3、下载项目后从本地文件导入方便修改
```bash
import sys
import pandas as pd
# 找到你下载的tablegis文件路径
sys.path.insert(0, r'C:\Users\Administrator\Desktop\tablegis')
# 现在可以导入了
import tablegis as tg
```


## 快速开始

以下是一个如何使用 `tablegis` 的简单示例：

### 1、把距离表1每个点最近的点（表2中）找出来并添加id、经纬度和距离。
```python
import pandas as pd
import tablegis as tg

# 创建两个示例DataFrame
df1 = pd.DataFrame({
    'id': [1, 2, 3],
    'lon1': [116.404, 116.405, 116.406],
    'lat1': [39.915, 39.916, 39.917]
})

df2 = pd.DataFrame({
    'id': ['A', 'B', 'C', 'D'],
    'lon2': [116.403, 116.407, 116.404, 116.408],
    'lat2': [39.914, 39.918, 39.916, 39.919]
})

# 计算最近的1个点
result = tg.min_distance_twotable(df1, df2,lon1='lon1', lat1='lat1', lon2='lon2', lat2='lat2', df2_id='id', n=1)
# 计算最近的2个点
result2 = tg.min_distance_twotable(df1, df2,lon1='lon1', lat1='lat1', lon2='lon2', lat2='lat2', df2_id='id', n=2)
print("\n结果示例（距离单位：米）:")
print(result)
print(result2)
```
结果展示：
<table>
<tr>
<td style="vertical-align: top; padding-right: 50px;">

**df1表格：**

| id | lon1  | lat1 |
|----|-------|------|
| A  | 114.0 | 30.0 |
| B  | 114.1 | 30.1 |

</td>
<td style="vertical-align: top;">

**df2表格：**

| id | lon2   | lat2  |
|----|--------|-------|
| p1 | 114.01 | 30.01 |
| p2 | 114.05 | 30.05 |
| p3 | 114.12 | 30.12 |

</td>
</tr>
</table>


**最近的1个点：**

| id | lon1  | lat1 | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance |
|----|-------|------|-------------|---------------|---------------|-------------------|
| A  | 114.0 | 30.0 | p1          | 114.01        | 30.01         | 1470.515926       |
| B  | 114.1 | 30.1 | p3          | 114.12        | 30.12         | 2939.507557       |

**最近的2个点：**

| id | lon1  | lat1 | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance | nearest2_id | nearest2_lon2 | nearest2_lat2 | nearest2_distance | mean_distance |
|----|-------|------|-------------|---------------|---------------|-------------------|-------------|---------------|---------------|-------------------|---------------|
| A  | 114.0 | 30.0 | p1          | 114.01        | 30.01         | 1470.515926       | p2          | 114.05        | 30.05         | 7351.852775       | 4411.184351   |
| B  | 114.1 | 30.1 | p3          | 114.12        | 30.12         | 2939.507557       | p2          | 114.05        | 30.05         | 7350.037700       | 5144.772629   |

### 2、在表中找到每个点的最近的点（自身表），并添加id、经纬度和距离。
```python
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
# 计算最近的2个点
result2 = tg.min_distance_onetable(df2,'lon2','lat2',idname='id',n=2)
print("\n结果示例（距离单位：米）:")
print(result)
print(result2)
```
结果展示：  
**df2表格：**

| id | lon2   | lat2  |
|----|--------|-------|
| p1 | 114.01 | 30.01 |
| p2 | 114.05 | 30.05 |
| p3 | 114.12 | 30.12 |

**最近1个点**

| | id | lon2 | lat2 | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance |
|---|-------|--------|-------|-------------|---------------|---------------|-------------------|
| 0 | p1 | 114.01 | 30.01 | p2 | 114.05 | 30.05 | 5881.336911 |
| 1 | p2 | 114.05 | 30.05 | p1 | 114.01 | 30.01 | 5881.336911 |
| 2 | p3 | 114.12 | 30.12 | p2 | 114.05 | 30.05 | 10289.545038 |

**最近2个点**

| | id | lon2 | lat2 | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance | nearest2_id | nearest2_lon2 | nearest2_lat2 | nearest2_distance | mean_distance |
|---|-------|--------|-------|-------------|---------------|---------------|-------------------|-------------|---------------|---------------|-------------------|---------------|
| 0 | p1 | 114.01 | 30.01 | p2 | 114.05 | 30.05 | 5881.336911 | p3 | 114.12 | 30.12 | 16170.880987 | 11026.108949 |
| 1 | p2 | 114.05 | 30.05 | p1 | 114.01 | 30.01 | 5881.336911 | p3 | 114.12 | 30.12 | 10289.545038 | 8085.440974 |
| 2 | p3 | 114.12 | 30.12 | p2 | 114.05 | 30.05 | 10289.545038 | p1 | 114.01 | 30.01 | 16170.880987 | 13230.213012 |

### 3、将表格中的经纬度列站换乘其他坐标系的经纬度，并添加新的经纬度列。
```python
import pandas as pd
import tablegis as tg

# 创建示例DataFrame
df = pd.DataFrame({
    'id': ['A', 'B', 'C', 'D'],
    'lon': [116.403, 116.407, 116.404, 116.408],
    'lat': [39.914, 39.918, 39.916, 39.919]
})

# 将84坐标系的经纬度转换成web_mercator的经纬度
result = tg.to_lonlat(df,'lon','lat', from_crs="wgs84", to_crs="web_mercator")
print(result)
```
结果展示：  
**添加了web_mercator两列：**
| id  | lon      | lat      | web_mercator_lon | web_mercator_lat |
| --- | -------- | -------- | ---------------- | ---------------- |
| A   | 116.403  | 39.914   | 12957922.69      | 4853452.853      |
| B   | 116.407  | 39.918   | 12958367.96      | 4854033.408      |
| C   | 116.404  | 39.916   | 12958034.01      | 4853743.126      |
| D   | 116.408  | 39.919   | 12958479.28      | 4854178.552      |



### 4、将表格中的经纬度列生成指定范围的buffer并添加geometry
```python
import pandas as pd
import tablegis as tg

df = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'buffer_size': [500, 1000]
    })
# 固定100米buffer
res_100 = tg.add_buffer(df,'lon','lat',100) 
# 按照buffer_size列的数字来定buffer范围
res_buffer_size = tg.add_buffer(df,'lon','lat','buffer_size')
print(res_100)
print(res_buffer_size)
```
结果展示：  
## df表格

|   | lon      | lat     | buffer_size |
|---|----------|---------|-------------|
| 0 | 116.4074 | 39.9042 | 500         |
| 1 | 121.4737 | 31.2304 | 1000        |

## 固定100米buffer

|   | lon      | lat     | buffer_size | geometry                                        |
|---|----------|---------|-------------|-------------------------------------------------|
| 0 | 116.4074 | 39.9042 | 500         | POLYGON ((116.40857 39.90421, 116.40856 39.904... |
| 1 | 121.4737 | 31.2304 | 1000        | POLYGON ((121.47475 31.23036, 121.47474 31.230... |

## 按照buffer_size列的数字来定buffer范围

|   | lon      | lat     | buffer_size | geometry                                        |
|---|----------|---------|-------------|-------------------------------------------------|
| 0 | 116.4074 | 39.9042 | 500         | POLYGON ((116.41325 39.90423, 116.41322 39.903... |
| 1 | 121.4737 | 31.2304 | 1000        | POLYGON ((121.48417 31.23003, 121.48408 31.229... |



### 5、将表格中的经纬度列生成点状geometry变成gdf
```python
import pandas as pd
import tablegis as tg

df = pd.DataFrame({
        'lon': [116.4074, 121.4737, 113.2644],
        'lat': [39.9042, 31.2304, 23.1291],
        'city': ['Beijing', 'Shanghai', 'Guangzhou']
    })
# 按照经纬度生成点 
result1 = tg.add_points(df)
print(result1)
```
结果展示：  

| lon       | lat        | city      | geometry                     |
|-----------|------------|-----------|------------------------------|
| 116.4074  | 39.9042    | Beijing   | POINT (116.4074 39.9042)     |
| 121.4737  | 31.2304    | Shanghai  | POINT (121.4737 31.2304)     |
| 113.2644  | 23.1291    | Guangzhou | POINT (113.2644 23.1291)     |


### 6、将表格中的经纬度进行汇聚使用扩充再融合的方法，添加融合后的id以及范围geom
```python
import pandas as pd
import tablegis as tg
# 准备测试数据
test_data = pd.DataFrame({
    'lon': [116.40, 116.41, 116.50, 116.51],
    'lat': [39.90, 39.91, 39.95, 39.96],
    'name': ['A', 'B', 'C', 'D'],
    'value': [1, 2, 3, 4]
})

# 测试1: 返回geometry
result_no_geom = tg.add_buffer_groupbyid(
    test_data, 
    lon='lon', 
    lat='lat',
    distance=1000,
    columns_name='group_id',
    id_label_prefix='id_',
    geom=True
)
# 测试1: 不返回geometry
result_geom = tg.add_buffer_groupbyid(
    test_data, 
    lon='lon', 
    lat='lat',
    distance=1000,
    columns_name='group_id',
    id_label_prefix='id_',
    geom=False
)
```
结果展示：  
## 不带geom
| lon   | lat   | name | value | group_id |
|-------|-------|------|-------|----------|
| 116.40| 39.90 | A    | 1     | id_0     |
| 116.41| 39.91 | B    | 2     | id_0     |
| 116.50| 39.95 | C    | 3     | id_1     |
| 116.51| 39.96 | D    | 4     | id_1     |

## 带geom
| lon   | lat   | name | value | group_id | geometry |
|-------|-------|------|-------|----------|---------|
| 116.40| 39.90 | A    | 1     | id_0     | POLYGON ((116.41149 39.8983, 116.41122 39.8974...) |
| 116.41| 39.91 | B    | 2     | id_0     | POLYGON ((116.41149 39.8983, 116.41122 39.8974...) |
| 116.50| 39.95 | C    | 3     | id_1     | POLYGON ((116.51149 39.94829, 116.51122 39.947...) |
| 116.51| 39.96 | D    | 4     | id_1     | POLYGON ((116.51149 39.94829, 116.51122 39.947...) |


### 7、将geopandas添加一列面积根据图形的area计算单位地理坐标系是米，平面与平面单位一致
```python
import tablegis as tg
import geopandas as gpd
polygon = Polygon([(113.343, 29.3434), (113.353, 29.3434), (113.353, 29.3534), (113.343, 29.3534)])
gdf = gpd.GeoDataFrame({'id': [1], 'geometry': [polygon]}, crs="epsg:4326")
# 测试1:添加面积列（自动选择坐标系）
result_gdf = tg.add_area(gdf, 'area')
print('area:',result_gdf['area'].astype(int)[0])

# 测试2:添加面积列名和坐标系
result_gdf = tg.add_area(gdf, 'area', crs_epsg=32650)
print('area:',result_gdf['area'].astype(int)[0])

```
结果展示：  
## 添加面积列（自动选择坐标系）
```
Center: (113.3480, 29.3484) → UTM Zone 49 N → EPSG:32649
area: 1076905
```

## 添加面积列名和坐标系
```
area: 1078867
```




### 8、根据指定的方位角、距离和角度在点周围创建扇形（楔形）多边形。

```python
import pandas as pd
import tablegis as tg

df = pd.DataFrame({
    'lon': [116.4074, 121.4737],
    'lat': [39.9042, 31.2304],
    'azimuth': [45, 90],
    'distance': [1000, 1500],
    'angle': [60, 45]
})

# 使用默认参数创建扇形
result = tg.add_sectors(df, lon='lon', lat='lat', azimuth='azimuth', distance='distance', angle='angle')
print(result)
```

### 9、播放内置的提示音。

```python
import tablegis as tg

# 播放提示音(仅限Windows)
tg.dog()
```


## 贡献

欢迎各种形式的贡献，包括功能请求、错误报告和代码贡献。

## 许可证

本项目使用MIT许可证。
