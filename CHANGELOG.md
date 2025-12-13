# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.7] - 2025-12-14

### Added
- Separate GitHub Actions workflows for publishing to TestPyPI and PyPI
- Enhanced project documentation with contribution guidelines and code of conduct
- Issue templates for bug reports and feature requests
- Professional badges in README

### Changed
- Updated minimum Python version requirement from 3.7 to 3.8
- Updated GitHub Actions workflows to use currently supported Python versions
- Improved GitHub Actions workflow to allow separate publishing to TestPyPI and PyPI
- Enhanced project metadata in pyproject.toml

### Deprecated
- N/A

### Removed
- Support for Python 3.7

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