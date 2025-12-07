#!/usr/bin/env python3
"""
DroneMobile API Demo Script

This script demonstrates the basic functionality of the drone_mobile package.
It shows how to authenticate, retrieve vehicle information, and send commands.

Usage:
    python demo.py <username> <password> [options]

Examples:
    # Basic usage - list vehicles
    python demo.py user@example.com mypassword

    # Show detailed status
    python demo.py user@example.com mypassword --status

    # Send a command
    python demo.py user@example.com mypassword --command start

    # Enable verbose logging
    python demo.py user@example.com mypassword --verbose
"""

import argparse
import json
import logging
import sys
from typing import List

from drone_mobile import DroneMobileClient
from drone_mobile.exceptions import (
    AuthenticationError,
    CommandFailedError,
    DroneMobileException,
    VehicleNotFoundError,
)
from drone_mobile.models import CommandResponse, VehicleStatus
from drone_mobile.vehicle import Vehicle

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
_LOGGER = logging.getLogger(__name__)


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def print_vehicle_list(vehicles: List[Vehicle]) -> None:
    """Print a formatted list of vehicles."""
    print_header("Available Vehicles")

    if not vehicles:
        print("No vehicles found in your account.\n")
        return

    for i, vehicle in enumerate(vehicles, 1):
        print(f"{i}. {vehicle}")
        print(f"   Vehicle ID: {vehicle.vehicle_id}")
        print(f"   Device Key: {vehicle.device_key}")

        if vehicle.info.make and vehicle.info.model and vehicle.info.year:
            print(f"   Details: {vehicle.info.year} {vehicle.info.make} {vehicle.info.model}")

        if vehicle.info.vin:
            print(f"   VIN: {vehicle.info.vin}")

        if vehicle.info.color:
            print(f"   Color: {vehicle.info.color}")

        print()


def print_vehicle_status(vehicle: Vehicle, status: VehicleStatus) -> None:
    """Print formatted vehicle status."""
    print_header(f"Status: {vehicle.name}")

    # Engine and ignition
    print("🚗 Engine & Ignition:")
    print(f"   Running: {'Yes ✓' if status.is_running else 'No ✗'}")
    print(f"   Locked: {'Yes 🔒' if status.is_locked else 'No 🔓'}")

    # Battery
    print("\n🔋 Battery:")
    if status.battery_percent is not None:
        print(f"   Level: {status.battery_percent}%")
    if status.battery_voltage is not None:
        print(f"   Voltage: {status.battery_voltage}V")

    # Fuel
    if status.fuel_level is not None:
        print(f"\n⛽ Fuel Level: {status.fuel_level}%")

    # Odometer
    if status.odometer is not None:
        print(f"\n📏 Odometer: {status.odometer:,.1f} miles")

    # Temperature
    if status.interior_temperature is not None:
        print("\n🌡️  Temperature:")
        print(f"   Interior: {status.interior_temperature}°C")
        if status.exterior_temperature is not None:
            print(f"   Exterior: {status.exterior_temperature}°C")

    # Location
    if status.location:
        print("\n📍 Location:")
        print(f"   Latitude: {status.location.latitude}")
        print(f"   Longitude: {status.location.longitude}")
        if status.location.accuracy:
            print(f"   Accuracy: {status.location.accuracy}m")

    # Last update
    if status.last_updated:
        print(f"\n🕐 Last Updated: {status.last_updated}")

    print()


def print_command_result(command: str, response: CommandResponse) -> None:
    """Print formatted command result."""
    print_header(f"Command: {command}")

    if response.success:
        print("✓ SUCCESS")
        print(f"   Message: {response.message}")
    else:
        print("✗ FAILED")
        print(f"   Message: {response.message}")

    if response.timestamp:
        print(f"   Timestamp: {response.timestamp}")

    print()


def export_data(vehicles: List[Vehicle], filename: str = "drone_mobile_export.json") -> None:
    """Export vehicle data to JSON file."""
    data = {
        "vehicles": [
            {
                "info": vehicle.info.raw_data,
                # NOTE: vehicle.get_status() makes an API call for every vehicle here.
                "status": vehicle.get_status().raw_data,
            }
            for vehicle in vehicles
        ]
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"✓ Data exported to {filename}\n")


def interactive_demo(client: DroneMobileClient) -> None:  # noqa: C901
    """Run an interactive demo."""
    print_header("DroneMobile Interactive Demo")

    # Get vehicles
    vehicles = client.get_vehicles()
    if not vehicles:
        print("No vehicles found in your account.\n")
        return

    print_vehicle_list(vehicles)

    # Select vehicle
    if len(vehicles) == 1:
        vehicle = vehicles[0]
        print(f"Using vehicle: {vehicle.name}\n")
    else:
        while True:
            try:
                choice = input(f"Select vehicle (1-{len(vehicles)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(vehicles):
                    vehicle = vehicles[idx]
                    break
                print("Invalid selection. Try again.")
            except (ValueError, KeyboardInterrupt):
                print("\nExiting.")
                return

    # Show status
    print("\nFetching vehicle status...")
    status = vehicle.get_status()
    print_vehicle_status(vehicle, status)

    # Command menu
    while True:
        print("\nAvailable Commands:")
        print("  1. Refresh Status")
        print("  2. Lock Doors")
        print("  3. Unlock Doors")
        print("  4. Start Engine")
        print("  5. Stop Engine")
        print("  6. Open Trunk")
        print("  7. Panic On")
        print("  8. Panic Off")
        print("  9. Export Data")
        print("  0. Exit")

        try:
            choice = input("\nSelect command: ").strip()

            if choice == "0":
                print("Exiting.")
                break
            elif choice == "1":
                print("\nRefreshing status...")
                status = vehicle.get_status()
                print_vehicle_status(vehicle, status)
            elif choice == "2":
                print("\nLocking doors...")
                response = vehicle.lock()
                print_command_result("LOCK", response)
            elif choice == "3":
                print("\nUnlocking doors...")
                response = vehicle.unlock()
                print_command_result("UNLOCK", response)
            elif choice == "4":
                confirm = input("⚠️  Start engine? (yes/no): ").strip().lower()
                if confirm == "yes":
                    print("\nStarting engine...")
                    response = vehicle.start()
                    print_command_result("START", response)
                else:
                    print("Cancelled.")
            elif choice == "5":
                confirm = input("⚠️  Stop engine? (yes/no): ").strip().lower()
                if confirm == "yes":
                    print("\nStopping engine...")
                    response = vehicle.stop()
                    print_command_result("STOP", response)
                else:
                    print("Cancelled.")
            elif choice == "6":
                print("\nOpening trunk...")
                response = vehicle.trunk()
                print_command_result("TRUNK", response)
            elif choice == "7":
                confirm = input("⚠️  Activate panic alarm? (yes/no): ").strip().lower()
                if confirm == "yes":
                    print("\nActivating panic...")
                    response = vehicle.panic_on()
                    print_command_result("PANIC ON", response)
                else:
                    print("Cancelled.")
            elif choice == "8":
                print("\nDeactivating panic...")
                response = vehicle.panic_off()
                print_command_result("PANIC OFF", response)
            elif choice == "9":
                filename = input("Export filename (default: drone_mobile_export.json): ").strip()
                if not filename:
                    filename = "drone_mobile_export.json"
                export_data(vehicles, filename)
            else:
                print("Invalid choice. Try again.")

        except KeyboardInterrupt:
            print("\n\nExiting.")
            break
        except CommandFailedError as e:
            print(f"\n✗ Command failed: {e}")
        except DroneMobileException as e:
            print(f"\n✗ Error: {e}")


def run_demo_modes(
    args: argparse.Namespace, client: DroneMobileClient, vehicles: List[Vehicle]
) -> int:
    """Handles the different execution modes based on command-line arguments."""

    # Select vehicle
    if args.vehicle_id:
        try:
            vehicle = client.get_vehicle(args.vehicle_id)
        except VehicleNotFoundError:
            print(f"✗ Vehicle with ID '{args.vehicle_id}' not found.")
            return 1
    else:
        # Default to the first vehicle if no ID is specified
        vehicle = vehicles[0]

    # Interactive mode
    if args.interactive:
        interactive_demo(client)
        return 0

    # Show vehicle list (default)
    if not args.status and not args.command and not args.export:
        print_vehicle_list(vehicles)
        print("Tip: Use --status to see detailed vehicle information")
        print("     Use --interactive for an interactive demo")
        print("     Use --help to see all options")
        return 0

    # Show status
    if args.status:
        status = vehicle.get_status()
        print_vehicle_status(vehicle, status)

    # Send command
    if args.command:
        print(f"Sending {args.command.upper()} command to {vehicle.name}...")

        command_map = {
            "start": vehicle.start,
            "stop": vehicle.stop,
            "lock": vehicle.lock,
            "unlock": vehicle.unlock,
            "trunk": vehicle.trunk,
            "panic_on": vehicle.panic_on,
            "panic_off": vehicle.panic_off,
        }

        response = command_map[args.command]()
        print_command_result(args.command.upper(), response)

    # Export data
    if args.export:
        export_data(vehicles, args.export)

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DroneMobile API Demo Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s user@example.com password
  %(prog)s user@example.com password --status
  %(prog)s user@example.com password --command start
  %(prog)s user@example.com password --interactive --verbose
        """,
    )

    parser.add_argument("username", help="DroneMobile account email")
    parser.add_argument("password", help="DroneMobile account password")

    parser.add_argument("-s", "--status", action="store_true", help="Show detailed vehicle status")

    parser.add_argument(
        "-c",
        "--command",
        choices=["start", "stop", "lock", "unlock", "trunk", "panic_on", "panic_off"],
        help="Send a command to the first vehicle",
    )

    parser.add_argument("-i", "--interactive", action="store_true", help="Run in interactive mode")

    parser.add_argument("-e", "--export", metavar="FILE", help="Export vehicle data to JSON file")

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    parser.add_argument("--vehicle-id", help="Specific vehicle ID to use (default: first vehicle)")

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger("drone_mobile").setLevel(logging.DEBUG)
        _LOGGER.setLevel(logging.DEBUG)

    # Authenticate
    try:
        print_header("DroneMobile API Demo")
        print("Authenticating...")

        with DroneMobileClient(args.username, args.password) as client:
            print("✓ Authentication successful\n")

            # Get vehicles
            vehicles = client.get_vehicles()

            if not vehicles:
                print("No vehicles found in your account.")
                return 1

            # Call the refactored helper function to handle all modes
            return run_demo_modes(args, client, vehicles)

    except AuthenticationError as e:
        print(f"\n✗ Authentication failed: {e}")
        print("  Please check your username and password.")
        return 1

    except CommandFailedError as e:
        print(f"\n✗ Command failed: {e}")
        return 1

    except VehicleNotFoundError as e:
        print(f"\n✗ Vehicle not found: {e}")
        return 1

    except DroneMobileException as e:
        print(f"\n✗ Error: {e}")
        return 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 130

    except Exception as e:
        _LOGGER.exception("Unexpected error occurred")
        print(f"\n✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
