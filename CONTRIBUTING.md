# Contributing to drone_mobile-python

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/drone_mobile_python.git
cd drone_mobile_python
```

### 2. Set Up Development Environment

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=drone_mobile --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_auth.py::TestAuthenticationManager::test_authenticate_success
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Format code (automatically fixes issues)
black drone_mobile/ tests/

# Lint code (checks for issues)
ruff check drone_mobile/

# Fix auto-fixable linting issues
ruff check --fix drone_mobile/

# Type checking
mypy drone_mobile/

# Run all checks at once
make format lint type-check test
```

### Pre-commit Hooks

Pre-commit hooks will automatically run on every commit. If they fail:

1. Review the errors
2. Make necessary fixes
3. Stage the changes: `git add .`
4. Commit again: `git commit -m "your message"`

To run hooks manually:
```bash
pre-commit run --all-files
```

## Writing Code

### Code Style

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Maximum line length: 100 characters

Example:
```python
def get_vehicle_status(self, vehicle_id: str) -> VehicleStatus:
    """
    Get the current status of a vehicle.

    Args:
        vehicle_id: The vehicle's unique identifier

    Returns:
        VehicleStatus object containing current vehicle state

    Raises:
        VehicleNotFoundError: If vehicle is not found
        APIError: If API request fails
    """
    # Implementation here
    pass
```

### Writing Tests

- Write tests for all new features
- Aim for >80% code coverage
- Use descriptive test names
- Test both success and failure cases
- Use fixtures for common setup

Example:
```python
import pytest
from drone_mobile.exceptions import VehicleNotFoundError


class TestVehicleOperations:
    """Tests for vehicle operations."""

    def test_get_vehicle_success(self, client, mock_vehicle_data):
        """Test successfully retrieving a vehicle."""
        vehicle = client.get_vehicle("123")
        assert vehicle.vehicle_id == "123"
        assert vehicle.name == "Test Vehicle"

    def test_get_vehicle_not_found(self, client):
        """Test handling of non-existent vehicle."""
        with pytest.raises(VehicleNotFoundError):
            client.get_vehicle("nonexistent")
```

### Error Handling

- Use custom exceptions from `drone_mobile.exceptions`
- Provide helpful error messages
- Log errors appropriately
- Don't catch exceptions unless you can handle them

```python
from .exceptions import APIError, VehicleNotFoundError

try:
    response = self._session.get(url)
    response.raise_for_status()
except requests.HTTPError:
    if response.status_code == 404:
        raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
    raise APIError(f"API request failed: {response.text}")
```

## Pull Request Process

### Before Submitting

1. **Update documentation** if you've changed the API
2. **Add tests** for new functionality
3. **Update CHANGELOG.md** with your changes
4. **Run all tests and checks**:
   ```bash
   make format lint type-check test
   ```

### Submitting

1. Push your branch to your fork
2. Open a pull request against the `main` branch
3. Fill out the PR template completely
4. Link any related issues

### PR Checklist

- [ ] Code follows the style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages are clear and descriptive
- [ ] No unnecessary dependencies added

## Commit Messages

Write clear, descriptive commit messages:

```
Add support for vehicle location tracking

- Implement get_location() method on Vehicle class
- Add Location model with GPS coordinates
- Update documentation with location examples
- Add tests for location functionality

Fixes #123
```

Format:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed description (wrap at 72 chars)
- Reference issues at the end

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def send_command(self, device_key: str, command: str) -> CommandResponse:
    """
    Send a command to a vehicle.

    Args:
        device_key: The device key for the vehicle
        command: The command to send (must be in AVAILABLE_COMMANDS)

    Returns:
        CommandResponse object with command result

    Raises:
        InvalidCommandError: If command is not valid
        CommandFailedError: If command execution fails
        APIError: If API request fails

    Example:
        >>> client = DroneMobileClient("user@example.com", "password")
        >>> vehicle = client.get_vehicles()[0]
        >>> response = client.send_command(vehicle.device_key, "REMOTE_START")
        >>> print(response.success)
        True
    """
```

### README Updates

If your changes affect user-facing functionality:
- Update code examples
- Add new features to the feature list
- Update API reference if needed

## Reporting Issues

### Bug Reports

Include:
- Python version
- Package version
- Operating system
- Minimal code to reproduce
- Expected vs actual behavior
- Full error traceback

### Feature Requests

Include:
- Use case description
- Proposed API/interface
- Why this feature would be useful
- Any alternatives you've considered

## Questions?

- Open an issue for general questions
- Tag with "question" label
- Be specific and provide context

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🎉
