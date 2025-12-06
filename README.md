# drone_mobile-python

[![Upload Python Package](https://github.com/bjhiltbrand/drone_mobile_python/actions/workflows/python-publish.yml/badge.svg)](https://github.com/bjhiltbrand/drone_mobile_python/actions/workflows/python-publish.yml)
[![PyPI version](https://badge.fury.io/py/drone-mobile.svg)](https://badge.fury.io/py/drone-mobile)
[![Python Versions](https://img.shields.io/pypi/pyversions/drone-mobile.svg)](https://pypi.org/project/drone-mobile/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, fully-typed Python wrapper for the DroneMobile API. Control your Firstech/Compustar remote start system from Python.

## ⚠️ Disclaimer

The code here is based off of an unsupported API from [DroneMobile](https://www.dronemobile.com/) and is subject to change without notice. The authors claim no responsibility for damages to your vehicle by use of the code within.

## ✨ Features

- 🔐 **Secure Authentication** - Automatic token management with secure storage
- 🚗 **Vehicle Control** - Start/stop engine, lock/unlock doors, and more
- 📊 **Status Monitoring** - Get detailed vehicle status information
- 🎯 **Type Safe** - Full type hints for better IDE support
- 🧪 **Well Tested** - Comprehensive test suite
- 🛠️ **CLI Tool** - Command-line interface for quick operations
- 🔄 **Context Manager** - Clean resource management
- 📝 **Detailed Logging** - Debug and track API interactions

## 📦 Installation

```bash
pip install drone_mobile
```

For development:
```bash
pip install drone_mobile[dev]
```

## 🚀 Quick Start

### Basic Usage

```python
from drone_mobile import DroneMobileClient

# Create a client and authenticate
client = DroneMobileClient("your_email@example.com", "your_password")

# Get all vehicles
vehicles = client.get_vehicles()

# Work with the first vehicle
vehicle = vehicles[0]
print(f"Vehicle: {vehicle.name}")

# Get status
status = vehicle.get_status()
print(f"Running: {status.is_running}")
print(f"Locked: {status.is_locked}")
print(f"Battery: {status.battery_percent}%")

# Control the vehicle
vehicle.start()  # Start the engine
vehicle.unlock()  # Unlock doors
vehicle.lock()  # Lock doors
vehicle.stop()  # Stop the engine
```

### Using Context Manager

```python
from drone_mobile import DroneMobileClient

# Automatically handles cleanup
with DroneMobileClient("email@example.com", "password") as client:
    vehicles = client.get_vehicles()
    for vehicle in vehicles:
        status = vehicle.get_status()
        print(f"{vehicle.name}: {'Running' if status.is_running else 'Stopped'}")
```

### Error Handling

```python
from drone_mobile import DroneMobileClient
from drone_mobile.exceptions import (
    AuthenticationError,
    CommandFailedError,
    VehicleNotFoundError
)

try:
    client = DroneMobileClient("email@example.com", "password")
    vehicle = client.get_vehicle("vehicle_id")
    vehicle.start()
except AuthenticationError:
    print("Invalid credentials")
except CommandFailedError as e:
    print(f"Command failed: {e}")
except VehicleNotFoundError:
    print("Vehicle not found")
```

## 🖥️ Command Line Interface

The package includes a CLI tool for quick operations:

```bash
# List all vehicles
drone-mobile-demo user@example.com password list

# Show vehicle status
drone-mobile-demo user@example.com password status

# Send commands
drone-mobile-demo user@example.com password cmd start
drone-mobile-demo user@example.com password cmd lock
drone-mobile-demo user@example.com password cmd unlock
drone-mobile-demo user@example.com password cmd stop

# Use verbose logging
drone-mobile-demo -v user@example.com password status
```

## 📚 API Reference

### DroneMobileClient

Main client for interacting with the DroneMobile API.

#### Methods

- `get_vehicles() -> List[Vehicle]` - Get all vehicles
- `get_vehicle(vehicle_id: str) -> Vehicle` - Get specific vehicle
- `get_vehicle_status(vehicle_id: str) -> VehicleStatus` - Get vehicle status
- `send_command(device_key: str, command: str) -> CommandResponse` - Send command

### Vehicle

Represents a vehicle with control methods.

#### Properties

- `vehicle_id: str` - Unique vehicle identifier
- `device_key: str` - Device key for commands
- `name: str` - Vehicle name
- `info: VehicleInfo` - Detailed vehicle information

#### Methods

- `get_status() -> VehicleStatus` - Get current status
- `start() -> CommandResponse` - Start engine
- `stop() -> CommandResponse` - Stop engine
- `lock() -> CommandResponse` - Lock doors
- `unlock() -> CommandResponse` - Unlock doors
- `trunk() -> CommandResponse` - Open trunk
- `panic_on() -> CommandResponse` - Activate panic
- `panic_off() -> CommandResponse` - Deactivate panic
- `aux1() -> CommandResponse` - Trigger auxiliary 1
- `aux2() -> CommandResponse` - Trigger auxiliary 2
- `get_location() -> CommandResponse` - Get GPS location

### Data Models

#### VehicleStatus

```python
@dataclass
class VehicleStatus:
    vehicle_id: str
    device_key: str
    is_running: bool
    is_locked: bool
    battery_voltage: Optional[float]
    battery_percent: Optional[int]
    odometer: Optional[float]
    fuel_level: Optional[int]
    interior_temperature: Optional[float]
    exterior_temperature: Optional[float]
    location: Optional[Location]
    last_updated: Optional[datetime]
    raw_data: Dict[str, Any]
```

#### VehicleInfo

```python
@dataclass
class VehicleInfo:
    vehicle_id: str
    device_key: str
    name: str
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    color: Optional[str]
    vin: Optional[str]
    raw_data: Dict[str, Any]
```

## 🔒 Security

- Tokens are stored securely in `~/.config/drone_mobile/` with restrictive permissions (0600)
- Sensitive data is never logged
- Automatic token refresh prevents credential exposure

## 🧪 Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/bjhiltbrand/drone_mobile_python.git
cd drone_mobile_python

# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=drone_mobile --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

### Code Quality

```bash
# Format code
black drone_mobile/ tests/

# Lint
ruff check drone_mobile/

# Type check
mypy drone_mobile/

# Run all checks
make format lint type-check test
```

## 📝 Migration from 0.2.x

If you're upgrading from version 0.2.x, see [CHANGELOG.md](CHANGELOG.md) for a detailed migration guide.

Quick changes:
- Import `DroneMobileClient` instead of `Vehicle`
- Use `get_vehicles()` instead of `getAllVehicles()`
- Methods now return typed objects instead of raw dicts
- Token storage moved to `~/.config/drone_mobile/`

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## 🙏 Acknowledgments

- Original API reverse engineering by the community
- Thanks to all contributors

## 📮 Support

- 🐛 [Report bugs](https://github.com/bjhiltbrand/drone_mobile_python/issues)
- 💡 [Request features](https://github.com/bjhiltbrand/drone_mobile_python/issues)
- 📖 [Documentation](https://github.com/bjhiltbrand/drone_mobile_python#readme)

## ⚖️ Legal

This is an unofficial API wrapper and is not affiliated with, endorsed by, or connected to DroneMobile, Firstech, or Compustar in any way.
