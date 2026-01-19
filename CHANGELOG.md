# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- `buffer`: New function to expand/shrink existing GeoDataFrame geometries by a distance in meters. Automatically projects to UTM for accurate meter-based operations, supporting both positive (expand) and negative (shrink) distances.
- `match_layer`: Match spatial layer attributes to a DataFrame based on spatial relationship (intersects/contains/within). Supports multiple matches handling (first/merge/explode) and dynamic geometry column detection.
- `df_to_gdf`: Convert a DataFrame with WKT geometry column to a GeoDataFrame. Supports custom CRS and automatically renames the geometry column to 'geometry'.
- `add_polygon`: new function to generate regular polygons by `radius` or `side_length`. Vectorized vertex computation for better performance on large datasets.
- Documentation updates for `add_buffer.min_distance` and `add_polygon`.

### Changed
- `add_polygon` API: `angle_value` is now interpreted as an *interior angle* when provided (entering interior-mode). A new `rotation` parameter (scalar or column) was added for overall orientation; when `angle_value=None` the function operates in exterior/regular mode. Both `angle_value` and `rotation` support scalar or per-row column inputs.

### Packaging
- Added guidance to README for preparing releases to PyPI and GitHub (include `pyproject.toml` metadata, build wheel and sdist, tag GitHub release).
### Added
- `add_buffer`: new optional `min_distance` parameter to create ring buffers (supports scalar or column name). When omitted, behavior unchanged.

## [0.0.7] - 2025-12-14

### Added
- Separate GitHub Actions workflows for publishing to TestPyPI and PyPI
- Enhanced project documentation with contribution guidelines and code of conduct
- Issue templates for bug reports and feature requests
- Professional badges in README

### Changed
- Updated minimum Python version requirement from 3.8 to 3.9
- Updated GitHub Actions workflows to use currently supported Python versions (3.9, 3.10, 3.11, 3.12)
- Updated GitHub Actions workflows to use ubuntu-20.04 runner to fix Python installation issues
- Improved GitHub Actions workflow to allow separate publishing to TestPyPI and PyPI
- Enhanced project metadata in pyproject.toml

### Deprecated
- N/A

### Removed
- Support for Python 3.7 and 3.8

### Fixed
- N/A

### Security
- N/A

## [0.0.6] - 2025-12-14

### Added
- Initial release of tablegis
- Distance calculation functions (`min_distance_onetable`, `min_distance_twotable`)
- Coordinate transformation functions (`to_lonlat`)
- Buffer creation functions (`add_buffer`, `add_buffer_groupbyid`)
- Geometry creation functions (`add_points`)
- Area calculation functions (`add_area`)
- Comprehensive test suite covering all major functions
- Documentation with examples

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A