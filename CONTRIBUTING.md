# Contributing to tablegis

Thank you for considering contributing to tablegis! We welcome contributions from everyone.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue on our GitHub repository with:

1. A clear and descriptive title
2. Steps to reproduce the bug
3. Expected behavior
4. Actual behavior
5. Your environment information (OS, Python version, package versions)

### Suggesting Enhancements

We welcome ideas for new features or improvements. Please open an issue with:

1. A clear and descriptive title
2. Detailed explanation of the proposed feature
3. Use cases for the feature
4. Potential implementation approach (optional)

### Code Contributions

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass
6. Update documentation as needed
7. Submit a pull request

## Development Setup

1. Clone your fork of the repository
2. Install dependencies:
   ```bash
   pip install -e .
   pip install pytest
   ```
3. Run tests to ensure everything works:
   ```bash
   pytest
   ```

## Code Style

- Follow PEP 8 guidelines
- Write clear docstrings for all public functions
- Include type hints where appropriate
- Keep functions focused and small

## Testing

- All new features must include comprehensive tests
- Tests should cover normal cases, edge cases, and error conditions
- Run all tests before submitting a pull request

## Documentation

- Update README.md if you change functionality
- Document new functions with clear examples
- Keep the CHANGELOG.md up to date with notable changes

## Pull Request Process

1. Ensure any install or build dependencies are removed
2. Update the CHANGELOG.md with details of changes
3. Increase the version numbers in any examples files and the README.md to the new version
4. Your pull request will be reviewed by maintainers before merging

## Questions?

Feel free to contact the maintainers if you have any questions or need help!