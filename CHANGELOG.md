# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2024-12-03

### Added
- Complete refactoring with modern Python best practices
- Type hints throughout the codebase
- Custom exception classes for better error handling
- Data models (VehicleInfo, VehicleStatus, Location, CommandResponse, AuthToken)
- Separate `DroneMobileClient` and `Vehicle` classes for better organization
- Command-line interface (CLI) tool
- Comprehensive unit tests with pytest
- Context manager support for client
- Secure token storage with proper file permissions
- Token migration from legacy format
- Pre-commit hooks configuration
- Modern packaging with pyproject.toml
- Development tooling (black, ruff, mypy)

### Changed
- Moved token storage from current directory to `~/.config/drone_mobile/`
- Renamed methods to follow PEP 8 snake_case convention (breaking change)
- Improved authentication flow with better token refresh handling
- Enhanced error messages and logging
- Token expiry safety margin is now configurable

### Fixed
- Thread-safe token file operations
- Better handling of expired tokens
- More robust token data parsing
- Proper HTTP session management

### Security
- Secure file permissions on token directory and files (0700/0600)
- No longer logs sensitive authentication data

## [0.2.30] - Previous Release

### Features
- Basic DroneMobile API wrapper
- Vehicle status retrieval
- Remote start/stop
- Lock/unlock commands
- Trunk, panic, and auxiliary commands

---

## Migration Guide from 0.2.x to 0.3.0

### Breaking Changes

1. **Import Changes**:
   ```python
   # Old way
   from drone_mobile import Vehicle
   vehicleObject = Vehicle(username, password)
   vehicleObject.auth()
   vehicles = vehicleObject.getAllVehicles()

   # New way
   from drone_mobile import DroneMobileClient
   client = DroneMobileClient(username, password)
   vehicles = client.get_vehicles()
   ```

2. **Method Names** (now use snake_case):
   - `getAllVehicles()` → `get_vehicles()`
   - `vehicle_status()` → `get_vehicle_status()`
   - `sendCommand()` → `send_command()`

3. **Return Types**:
   - Methods now return typed objects instead of raw dictionaries
   - Use `.raw_data` attribute to access original API response

4. **Token Storage**:
   - Tokens now stored in `~/.config/drone_mobile/` by default
   - Old tokens are automatically migrated

### New Features

1. **Better Error Handling**:
   ```python
   from drone_mobile.exceptions import CommandFailedError, AuthenticationError

   try:
       vehicle.start()
   except CommandFailedError as e:
       print(f"Command failed: {e}")
   ```

2. **Context Manager**:
   ```python
   with DroneMobileClient(username, password) as client:
       vehicles = client.get_vehicles()
       for vehicle in vehicles:
           print(vehicle.get_status())
   ```

3. **CLI Tool**:
   ```bash
   drone-mobile-demo user@example.com password list
   drone-mobile-demo user@example.com password status
   drone-mobile-demo user@example.com password cmd start
   ```
