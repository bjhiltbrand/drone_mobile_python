# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.4] - 2026-04-10

### Added
- **MFA / 2-factor authentication support** for DroneMobile accounts that have
  Cognito MFA enabled
  - Supports `SMS_MFA` (one-time code via SMS) and `SOFTWARE_TOKEN_MFA`
    (TOTP from an authenticator app such as Google Authenticator or Authy)
  - New `mfa_callback` parameter on both `AuthenticationManager` and
    `DroneMobileClient`; receives the Cognito challenge name and must return
    the OTP code as a string
  - If MFA is triggered and no callback is configured, the new
    `MFARequiredError` exception is raised so callers can handle it at a
    higher level
- New `MFARequiredError` exception class (subclass of `AuthenticationError`)
  that carries the `challenge_name` attribute for the triggered Cognito
  challenge
- `MFA_CHALLENGE_HEADERS` constant in `const.py` with the correct
  `X-Amz-Target: AWSCognitoIdentityProviderService.RespondToAuthChallenge`
  header required by the Cognito `RespondToAuthChallenge` endpoint
- `SUPPORTED_MFA_CHALLENGES` frozenset in `const.py` enumerating the
  challenge types the library handles (`SMS_MFA`, `SOFTWARE_TOKEN_MFA`)
- `cli_mfa_callback` in `cli.py`: interactive OTP prompt for the CLI tool
  that presents a human-readable label based on the challenge type
- Comprehensive MFA test suite in `tests/test_auth.py` covering:
  - SMS and TOTP success flows
  - Missing callback → `MFARequiredError`
  - Wrong/expired code → `AuthenticationError`
  - Network error during challenge response → `NetworkError`
  - Empty code from callback → `AuthenticationError`
  - Unsupported Cognito challenge type → `AuthenticationError`
  - Callback receives the correct challenge name

### Changed
- `AuthenticationManager.__init__` accepts a new optional `mfa_callback`
  parameter (default `None`); existing callers are unaffected
- `DroneMobileClient.__init__` accepts a new optional `mfa_callback`
  parameter that is forwarded to `AuthenticationManager`
- `AsyncDroneMobileClient.__init__` signature updated to match (no behaviour
  change for callers that do not use MFA)
- CLI `main()` now passes `cli_mfa_callback` to `DroneMobileClient` so the
  command-line tool handles MFA transparently without any extra flags
- `_authenticate_new` in `auth.py` now detects a `ChallengeName` key in the
  Cognito response and delegates to `_respond_to_mfa_challenge` rather than
  treating it as an error

### Security
- MFA OTP codes are never written to logs at any level
- The Cognito `Session` token (opaque challenge state) is passed through in
  memory only and is not persisted to disk
- `ChallengeParameters` (which may contain a masked SMS destination) are
  logged only at `DEBUG` level, matching existing token-handling log verbosity

### Migration Guide (0.3.3 → 0.3.4)

No breaking changes. This release is fully backward-compatible.

If your DroneMobile account does not use MFA, nothing changes — the new
`mfa_callback` parameter defaults to `None` and the existing authentication
path is taken.

To opt in to MFA handling, supply a callback:

```python
# Synchronous client
def prompt_mfa(challenge_name: str) -> str:
    label = "SMS code" if challenge_name == "SMS_MFA" else "Authenticator code"
    return input(f"Two-factor authentication required. Enter {label}: ").strip()

client = DroneMobileClient(email, password, mfa_callback=prompt_mfa)

# Async client
async with AsyncDroneMobileClient(email, password, mfa_callback=prompt_mfa) as client:
    vehicles = await client.get_vehicles()
```

To handle the case where MFA is required but you haven't supplied a callback:

```python
from drone_mobile.exceptions import MFARequiredError

try:
    client = DroneMobileClient(email, password)
    vehicles = client.get_vehicles()
except MFARequiredError as e:
    print(f"MFA required: {e.challenge_name}")
    # Re-create the client with a callback and retry
```

---

## [0.3.0] - 2026-01-03

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
