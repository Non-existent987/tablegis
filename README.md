# tablegis

[![PyPI](https://img.shields.io/pypi/v/tablegis.svg)](https://pypi.org/project/tablegis/)
[![Tests](https://github.com/Non-existent987/tablegis/actions/workflows/test.yml/badge.svg)](https://github.com/Non-existent987/tablegis/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/Non-existent987/tablegis)](https://github.com/Non-existent987/tablegis/blob/main/LICENSE)

[English](README.md) | [简体中文](README.zh-CN.md)

`tablegis` is a Python package for geospatial data processing and analysis, built on `geopandas`, `pandas`, `shapely`, and `pyproj`. It provides a series of utility functions to simplify common GIS operations.

## Features

*   **Distance Calculation**: Efficiently compute the nearest distance between DataFrames.
*   **Spatial Analysis**: Create buffers (input in meters), Voronoi polygons, Delaunay triangulations, etc.
*   **Format Conversion**: Easily convert between `GeoDataFrame` and formats like `Shapefile`, `KML`, etc.
*   **Coordinate Aggregation**: Provides tools for aggregating coordinate points into grids.
*   **Geometric Operations**: Includes merging polygons, calculating centroids, adding sectors, etc.

## Installation

1. You can install `tablegis` from PyPI:

```bash
pip install tablegis
```

2. Or, install the latest version directly from the GitHub repository:

```bash
pip install git+https://github.com/Non-existent987/tablegis.git
```

3. After downloading the project, it is convenient to import from local files for modification.
```bash
import sys
import pandas as pd
# Find the file path of the tablegis you downloaded.
sys.path.insert(0, r'C:\Users\Administrator\Desktop\tablegis')
# Now it can be imported.
import tablegis as tg
```

## Quick Start

Here is a simple example of how to use `tablegis`:

### 1. Find the nearest point (in df2) for each point in df1 and add its ID, longitude, latitude, and distance.

```python
import pandas as pd
import tablegis as tg

# Create two example DataFrames
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

# Calculate the nearest points
result = tg.min_distance_twotable(
    df1, df2, 
    lon1='lon1', lat1='lat1', 
    lon2='lon2', lat2='lat2', 
    df2_id='id', 
    n=1
)

print(result)
```

**Result Display:**

<table>
<tr>
<td style="vertical-align: top; padding-right: 50px;">

**Table df1:**

| id | lon1  | lat1 |
|----|-------|------|
| A  | 114.0 | 30.0 |
| B  | 114.1 | 30.1 |

</td>
<td style="vertical-align: top;">

**Table df2:**

| id | lon2   | lat2  |
|----|--------|-------|
| p1 | 114.01 | 30.01 |
| p2 | 114.05 | 30.05 |
| p3 | 114.12 | 30.12 |

</td>
</tr>
</table>

**Nearest 1 point:**

| id | lon1  | lat1 | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance |
|----|-------|------|-------------|---------------|---------------|-------------------|
| A  | 114.0 | 30.0 | p1          | 114.01        | 30.01         | 1470.515926       |
| B  | 114.1 | 30.1 | p3          | 114.12        | 30.12         | 2939.507557       |

**Nearest 2 points:**

| id | lon1  | lat1 | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance | nearest2_id | nearest2_lon2 | nearest2_lat2 | nearest2_distance | mean_distance |
|----|-------|------|-------------|---------------|---------------|-------------------|-------------|---------------|---------------|-------------------|---------------|
| A  | 114.0 | 30.0 | p1          | 114.01        | 30.01         | 1470.515926       | p2          | 114.05        | 30.05         | 7351.852775       | 4411.184351   |
| B  | 114.1 | 30.1 | p3          | 114.12        | 30.12         | 2939.507557       | p2          | 114.05        | 30.05         | 7350.037700       | 5144.772629   |

### 2. Find the nearest point for each point within the same table and add its ID, longitude, latitude, and distance.

```python
import pandas as pd
import tablegis as tg

# Create an example DataFrame
df2 = pd.DataFrame({
    'id': ['A', 'B', 'C', 'D'],
    'lon2': [116.403, 116.407, 116.404, 116.408],
    'lat2': [39.914, 39.918, 39.916, 39.919]
})

# Calculate the nearest 1 point
result = tg.min_distance_onetable(df2, 'lon2', 'lat2', idname='id', n=1)
# Calculate the nearest 2 points
result2 = tg.min_distance_onetable(df2, 'lon2', 'lat2', idname='id', n=2)

print("\nExample result (distance in meters):")
print(result)
print(result2)
```

**Result Display:**

**Table df2:**

| id | lon2   | lat2  |
|----|--------|-------|
| p1 | 114.01 | 30.01 |
| p2 | 114.05 | 30.05 |
| p3 | 114.12 | 30.12 |

**Nearest 1 point:**

|    | id | lon2   | lat2  | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance |
|---:|----|--------|-------|-------------|---------------|---------------|-------------------|
|  0 | p1 | 114.01 | 30.01 | p2          | 114.05        | 30.05         | 5881.336911       |
|  1 | p2 | 114.05 | 30.05 | p1          | 114.01        | 30.01         | 5881.336911       |
|  2 | p3 | 114.12 | 30.12 | p2          | 114.05        | 30.05         | 10289.545038      |

**Nearest 2 points:**

|    | id | lon2   | lat2  | nearest1_id | nearest1_lon2 | nearest1_lat2 | nearest1_distance | nearest2_id | nearest2_lon2 | nearest2_lat2 | nearest2_distance | mean_distance |
|---:|----|--------|-------|-------------|---------------|---------------|-------------------|-------------|---------------|---------------|-------------------|---------------|
|  0 | p1 | 114.01 | 30.01 | p2          | 114.05        | 30.05         | 5881.336911       | p3          | 114.12        | 30.12         | 16170.880987      | 11026.108949  |
|  1 | p2 | 114.05 | 30.05 | p1          | 114.01        | 30.01         | 5881.336911       | p3          | 114.12        | 30.12         | 10289.545038      | 8085.440974   |
|  2 | p3 | 114.12 | 30.12 | p2          | 114.05        | 30.05         | 10289.545038      | p1          | 114.01        | 30.01         | 16170.880987      | 13230.213012  |

### 3. Replace the longitude and latitude columns in the table with the corresponding values in another coordinate system, and add a new column for longitude and latitude.
```python
import pandas as pd
import tablegis as tg

# Create two sample DataFrames
df = pd.DataFrame({
    'id': ['A', 'B', 'C', 'D'],
    'lon': [116.403, 116.407, 116.404, 116.408],
    'lat': [39.914, 39.918, 39.916, 39.919]
})

# Convert the latitude and longitude in the 84 coordinate system to the latitude and longitude in the web_mercator system.
result = tg.to_lonlat(df,'lon','lat', from_crs="wgs84", to_crs="web_mercator")
print(result)
```
**Result Display:**  
**Added two columns of "web_mercator"：**
| id  | lon      | lat      | web_mercator_lon | web_mercator_lat |
| --- | -------- | -------- | ---------------- | ---------------- |
| A   | 116.403  | 39.914   | 12957922.69      | 4853452.853      |
| B   | 116.407  | 39.918   | 12958367.96      | 4854033.408      |
| C   | 116.404  | 39.916   | 12958034.01      | 4853743.126      |
| D   | 116.408  | 39.919   | 12958479.28      | 4854178.552      |

### 4. Generate buffers of the specified range based on the longitude and latitude columns in the table and add the geometry.
```python
import pandas as pd
import tablegis as tg

df = pd.DataFrame({
        'lon': [116.4074, 121.4737],
        'lat': [39.9042, 31.2304],
        'buffer_size': [500, 1000]
    })
# Set a 100-meter buffer zone
res_100 = tg.add_buffer(df,'lon','lat',100) 
# Set the buffer range according to the numbers in the "buffer_size" column.
res_buffer_size = tg.add_buffer(df,'lon','lat','buffer_size')
print(res_100)
print(res_buffer_size)
```
**Result Display:**
## df table

|   | lon      | lat     | buffer_size |
|---|----------|---------|-------------|
| 0 | 116.4074 | 39.9042 | 500         |
| 1 | 121.4737 | 31.2304 | 1000        |

## Set a 100-meter buffer zone

|   | lon      | lat     | buffer_size | geometry                                        |
|---|----------|---------|-------------|-------------------------------------------------|
| 0 | 116.4074 | 39.9042 | 500         | POLYGON ((116.40857 39.90421, 116.40856 39.904... |
| 1 | 121.4737 | 31.2304 | 1000        | POLYGON ((121.47475 31.23036, 121.47474 31.230... |

## Set the buffer range according to the numbers in the "buffer_size" column.

|   | lon      | lat     | buffer_size | geometry                                        |
|---|----------|---------|-------------|-------------------------------------------------|
| 0 | 116.4074 | 39.9042 | 500         | POLYGON ((116.41325 39.90423, 116.41322 39.903... |
| 1 | 121.4737 | 31.2304 | 1000        | POLYGON ((121.48417 31.23003, 121.48408 31.229... |

### 5. Convert the latitude and longitude columns in the table into point-shaped geometries and then transform them into a gdf.
```python
import pandas as pd
import tablegis as tg

df = pd.DataFrame({
        'lon': [116.4074, 121.4737, 113.2644],
        'lat': [39.9042, 31.2304, 23.1291],
        'city': ['Beijing', 'Shanghai', 'Guangzhou']
    })
# Generate points based on latitude and longitude
result1 = tg.add_points(df)
print(result1)
```
**Result Display:**

| lon       | lat        | city      | geometry                     |
|-----------|------------|-----------|------------------------------|
| 116.4074  | 39.9042    | Beijing   | POINT (116.4074 39.9042)     |
| 121.4737  | 31.2304    | Shanghai  | POINT (121.4737 31.2304)     |
| 113.2644  | 23.1291    | Guangzhou | POINT (113.2644 23.1291)     |


### 6. Concentrate the latitude and longitude data in the table using the method of expansion and recombination, and add the fused id as well as the range geom.
```python
import pandas as pd
import tablegis as tg
# Prepare test data
test_data = pd.DataFrame({
    'lon': [116.40, 116.41, 116.50, 116.51],
    'lat': [39.90, 39.91, 39.95, 39.96],
    'name': ['A', 'B', 'C', 'D'],
    'value': [1, 2, 3, 4]
})

# Test 1: Return geometry
result_no_geom = tg.add_buffer_groupbyid(
    test_data, 
    lon='lon', 
    lat='lat',
    distance=1000,
    columns_name='group_id',
    id_label_prefix='id_',
    geom=True
)
# Test 2: Do not return geometry
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
**Result Display:**
## no geom
| lon   | lat   | name | value | group_id |
|-------|-------|------|-------|----------|
| 116.40| 39.90 | A    | 1     | id_0     |
| 116.41| 39.91 | B    | 2     | id_0     |
| 116.50| 39.95 | C    | 3     | id_1     |
| 116.51| 39.96 | D    | 4     | id_1     |

## geom
| lon   | lat   | name | value | group_id | geometry |
|-------|-------|------|-------|----------|---------|
| 116.40| 39.90 | A    | 1     | id_0     | POLYGON ((116.41149 39.8983, 116.41122 39.8974...) |
| 116.41| 39.91 | B    | 2     | id_0     | POLYGON ((116.41149 39.8983, 116.41122 39.8974...) |
| 116.50| 39.95 | C    | 3     | id_1     | POLYGON ((116.51149 39.94829, 116.51122 39.947...) |
| 116.51| 39.96 | D    | 4     | id_1     | POLYGON ((116.51149 39.94829, 116.51122 39.947...) |

### 7. Add a column for area to geopandas. The area is calculated based on the shape's area. The unit of the geographic coordinate system is meters, which is consistent with the units of both the horizontal and vertical planes.
```python
import tablegis as tg
import geopandas as gpd
from shapely.geometry import Polygon

polygon = Polygon([(113.343, 29.3434), (113.353, 29.3434), (113.353, 29.3534), (113.343, 29.3534)])
gdf = gpd.GeoDataFrame({'id': [1], 'geometry': [polygon]}, crs="epsg:4326")
# Test 1: Add Area Column (Automatically Select Coordinate System)
result_gdf = tg.add_area(gdf, 'area')
print('area:',result_gdf['area'].astype(int)[0])

# Test 2: Add column name for area and coordinate system
result_gdf = tg.add_area(gdf, 'area', crs_epsg=32650)
print('area:',result_gdf['area'].astype(int)[0])
```

### 8. Create sector (wedge) polygons around points with specified azimuth, distance, and angle.

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

# Create sectors with default parameters
result = tg.add_sectors(df, lon='lon', lat='lat', azimuth='azimuth', distance='distance', angle='angle')
print(result)
```

### 9. Play a built-in notification sound.

```python
import tablegis as tg

# Play the notification sound (Windows only)
tg.dog()
```

## Documentation

Detailed documentation is available in the [Wiki](https://github.com/Non-existent987/tablegis/wiki).

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a history of changes to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.