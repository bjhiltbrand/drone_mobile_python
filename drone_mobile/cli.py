#!/usr/bin/env python
"""Command line interface for DroneMobile."""

import argparse
import logging
import sys

from . import DroneMobileClient, __version__
from .exceptions import DroneMobileException


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def list_vehicles(client: DroneMobileClient) -> None:
    """List all vehicles."""
    vehicles = client.get_vehicles()

    if not vehicles:
        print("No vehicles found.")
        return

    print(f"\nFound {len(vehicles)} vehicle(s):\n")
    for i, vehicle in enumerate(vehicles, 1):
        print(f"{i}. {vehicle}")
        print(f"   Vehicle ID: {vehicle.vehicle_id}")
        print(f"   Device Key: {vehicle.device_key}")
        if vehicle.info.vin:
            print(f"   VIN: {vehicle.info.vin}")
        print()


def show_status(client: DroneMobileClient, vehicle_id: str | None = None) -> None:  # noqa: C901
    """Show vehicle status."""
    if vehicle_id:
        vehicle = client.get_vehicle(vehicle_id)
        vehicles = [vehicle]
    else:
        vehicles = client.get_vehicles()

    for vehicle in vehicles:
        print(f"\n{'='*60}")
        print(f"Status for: {vehicle}")
        print(f"{'='*60}")

        status = vehicle.get_status()

        print(f"Running: {'Yes' if status.is_running else 'No'}")
        print(f"Locked: {'Yes' if status.is_locked else 'No'}")

        if status.battery_percent is not None:
            print(f"Battery: {status.battery_percent}%")
        elif status.battery_voltage is not None:
            print(f"Battery: {status.battery_voltage}V")

        if status.fuel_level is not None:
            print(f"Fuel Level: {status.fuel_level}%")

        if status.odometer is not None:
            print(f"Odometer: {status.odometer}")

        if status.interior_temperature is not None:
            print(f"Interior Temperature: {status.interior_temperature}°")

        if status.exterior_temperature is not None:
            print(f"Exterior Temperature: {status.exterior_temperature}°")

        if status.location:
            print(f"Location: {status.location.latitude}, {status.location.longitude}")

        if status.last_updated:
            print(f"Last Updated: {status.last_updated}")

        print()


def send_command(
    client: DroneMobileClient,
    command: str,
    vehicle_id: str | None = None,
) -> None:
    """Send a command to a vehicle."""
    if vehicle_id:
        vehicle = client.get_vehicle(vehicle_id)
    else:
        vehicles = client.get_vehicles()
        if not vehicles:
            print("No vehicles found.")
            return
        vehicle = vehicles[0]
        print(f"Using first vehicle: {vehicle}")

    print(f"\nSending {command} command to {vehicle.name}...")

    # Map command names to vehicle methods
    command_map = {
        "start": vehicle.start,
        "stop": vehicle.stop,
        "lock": vehicle.lock,
        "unlock": vehicle.unlock,
        "trunk": vehicle.trunk,
        "panic_on": vehicle.panic_on,
        "panic_off": vehicle.panic_off,
        "aux1": vehicle.aux1,
        "aux2": vehicle.aux2,
        "location": vehicle.get_location,
        "status": vehicle.poll_status,
    }

    if command not in command_map:
        print(f"Unknown command: {command}")
        print(f"Available commands: {', '.join(command_map.keys())}")
        return

    try:
        response = command_map[command]()
        print("✓ Command sent successfully")
        print(f"Message: {response.message}")
    except DroneMobileException as e:
        print(f"✗ Command failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DroneMobile CLI - Control your vehicle from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version=f"drone_mobile {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("username", help="DroneMobile username/email")
    parser.add_argument("password", help="DroneMobile password")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List vehicles
    subparsers.add_parser("list", help="List all vehicles")

    # Show status
    status_parser = subparsers.add_parser("status", help="Show vehicle status")
    status_parser.add_argument("--vehicle-id", help="Specific vehicle ID (optional)")

    # Send commands
    cmd_parser = subparsers.add_parser("cmd", help="Send a command to vehicle")
    cmd_parser.add_argument(
        "action",
        choices=[
            "start",
            "stop",
            "lock",
            "unlock",
            "trunk",
            "panic_on",
            "panic_off",
            "aux1",
            "aux2",
            "location",
            "status",
        ],
        help="Command to send",
    )
    cmd_parser.add_argument("--vehicle-id", help="Specific vehicle ID (optional)")

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        with DroneMobileClient(args.username, args.password) as client:
            if args.command == "list":
                list_vehicles(client)
            elif args.command == "status":
                show_status(client, getattr(args, "vehicle_id", None))
            elif args.command == "cmd":
                send_command(client, args.action, getattr(args, "vehicle_id", None))

    except DroneMobileException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
