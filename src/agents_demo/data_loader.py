"""
Data loader module for airline customer service system.
Provides unified access to flight, seat, meal, and customer profile data.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Define data directory path
DATA_DIR = Path(__file__).resolve().parent / "data"

# File paths
FLIGHTS_PATH = DATA_DIR / "flights.json"
SEATS_PATH = DATA_DIR / "seats.json"
MEALS_PATH = DATA_DIR / "meals.json"
CUSTOMER_PROFILES_PATH = DATA_DIR / "customer_profiles.json"


# ==========================================
# Data Loading Functions with Caching
# ==========================================

@lru_cache(maxsize=1)
def load_flights_data() -> List[Dict[str, Any]]:
    """
    Load flight data from JSON file.
    Uses caching to avoid repeated file reads.

    Returns:
        List of flight dictionaries
    """
    try:
        if not FLIGHTS_PATH.exists():
            logger.warning(f"Flights data file not found: {FLIGHTS_PATH}")
            return []

        with open(FLIGHTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.error("Flights data is not a list")
            return []

        logger.info(f"Loaded {len(data)} flights from {FLIGHTS_PATH}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding flights JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading flights data: {e}")
        return []


@lru_cache(maxsize=1)
def load_seats_data() -> Dict[str, Dict[str, Any]]:
    """
    Load seat layout data from JSON file.
    Uses caching to avoid repeated file reads.

    Returns:
        Dictionary mapping flight_number to seat layout data
    """
    try:
        if not SEATS_PATH.exists():
            logger.warning(f"Seats data file not found: {SEATS_PATH}")
            return {}

        with open(SEATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.error("Seats data is not a dictionary")
            return {}

        logger.info(f"Loaded seat data for {len(data)} flights from {SEATS_PATH}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding seats JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading seats data: {e}")
        return {}


@lru_cache(maxsize=1)
def load_meals_data() -> Dict[str, Any]:
    """
    Load meal menu data from JSON file.
    Uses caching to avoid repeated file reads.

    Returns:
        Dictionary with meal options organized by route_type and cabin_class
    """
    try:
        if not MEALS_PATH.exists():
            logger.warning(f"Meals data file not found: {MEALS_PATH}")
            return {}

        with open(MEALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.error("Meals data is not a dictionary")
            return {}

        logger.info(f"Loaded meal data from {MEALS_PATH}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding meals JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading meals data: {e}")
        return {}


@lru_cache(maxsize=1)
def load_customer_profiles() -> List[Dict[str, Any]]:
    """
    Load customer profile data from JSON file.
    Uses caching to avoid repeated file reads.

    Returns:
        List of customer profile dictionaries
    """
    try:
        if not CUSTOMER_PROFILES_PATH.exists():
            logger.warning(f"Customer profiles file not found: {CUSTOMER_PROFILES_PATH}")
            return []

        with open(CUSTOMER_PROFILES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.error("Customer profiles data is not a list")
            return []

        logger.info(f"Loaded {len(data)} customer profiles from {CUSTOMER_PROFILES_PATH}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding customer profiles JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading customer profiles: {e}")
        return []


# ==========================================
# Query Functions
# ==========================================

def get_flight_by_number(flight_number: str) -> Optional[Dict[str, Any]]:
    """
    Get flight information by flight number.

    Args:
        flight_number: Flight number (e.g., "FLT-238")

    Returns:
        Flight dictionary if found, None otherwise
    """
    if not flight_number:
        logger.warning("get_flight_by_number called with empty flight_number")
        return None

    flights = load_flights_data()
    flight = next((f for f in flights if f.get("flight_number") == flight_number), None)

    if flight:
        logger.debug(f"Found flight: {flight_number}")
    else:
        logger.warning(f"Flight not found: {flight_number}")

    return flight


def get_seats_by_flight(flight_number: str) -> Optional[Dict[str, Any]]:
    """
    Get seat layout information for a specific flight.

    Args:
        flight_number: Flight number (e.g., "FLT-238")

    Returns:
        Seat layout dictionary if found, None otherwise
    """
    if not flight_number:
        logger.warning("get_seats_by_flight called with empty flight_number")
        return None

    seats = load_seats_data()
    seat_layout = seats.get(flight_number)

    if seat_layout:
        logger.debug(f"Found seat layout for flight: {flight_number}")
    else:
        logger.warning(f"Seat layout not found for flight: {flight_number}")

    return seat_layout


def get_meals_by_route_and_class(route_type: str, cabin_class: str) -> List[Dict[str, Any]]:
    """
    Get meal options for a specific route type and cabin class.

    Args:
        route_type: "domestic" or "international"
        cabin_class: "business" or "economy"

    Returns:
        List of meal dictionaries
    """
    if not route_type or not cabin_class:
        logger.warning("get_meals_by_route_and_class called with empty parameters")
        return []

    meals_data = load_meals_data()

    # Normalize inputs
    route_type = route_type.lower()
    cabin_class = cabin_class.lower()

    # Validate parameters
    if route_type not in ["domestic", "international"]:
        logger.warning(f"Invalid route_type: {route_type}")
        return []

    if cabin_class not in ["business", "economy"]:
        logger.warning(f"Invalid cabin_class: {cabin_class}")
        return []

    # Get meals
    try:
        meals = meals_data.get(route_type, {}).get(cabin_class, [])
        logger.debug(f"Found {len(meals)} meals for {route_type}/{cabin_class}")
        return meals
    except Exception as e:
        logger.error(f"Error retrieving meals: {e}")
        return []


def check_seat_occupied(flight_number: str, seat_number: str) -> bool:
    """
    Check if a specific seat is occupied on a flight.

    Args:
        flight_number: Flight number (e.g., "FLT-238")
        seat_number: Seat number (e.g., "14C")

    Returns:
        True if seat is occupied, False if available
    """
    if not flight_number or not seat_number:
        logger.warning("check_seat_occupied called with empty parameters")
        return True  # Default to occupied for safety

    seat_layout = get_seats_by_flight(flight_number)
    if not seat_layout:
        logger.warning(f"No seat layout found for flight {flight_number}")
        return True  # Default to occupied if no data

    # Check all cabin classes
    for cabin in ["business", "economy"]:
        cabin_data = seat_layout.get(cabin, {})
        occupied_seats = cabin_data.get("occupied", [])

        if seat_number in occupied_seats:
            logger.debug(f"Seat {seat_number} is occupied on flight {flight_number}")
            return True

    logger.debug(f"Seat {seat_number} is available on flight {flight_number}")
    return False


def get_available_seats(flight_number: str, cabin_class: Optional[str] = None) -> List[str]:
    """
    Get list of available seats for a flight.

    Args:
        flight_number: Flight number (e.g., "FLT-238")
        cabin_class: Optional filter by "business" or "economy"

    Returns:
        List of available seat numbers
    """
    seat_layout = get_seats_by_flight(flight_number)
    if not seat_layout:
        logger.warning(f"No seat layout found for flight {flight_number}")
        return []

    available_seats = []

    # Determine which cabins to check
    cabins_to_check = [cabin_class] if cabin_class else ["business", "economy"]

    for cabin in cabins_to_check:
        cabin_data = seat_layout.get(cabin, {})
        if not cabin_data:
            continue

        rows = cabin_data.get("rows", [])
        seats_per_row = cabin_data.get("seats_per_row", [])
        occupied = cabin_data.get("occupied", [])

        # Generate all possible seats
        for row in rows:
            for seat_letter in seats_per_row:
                seat_number = f"{row}{seat_letter}"
                if seat_number not in occupied:
                    available_seats.append(seat_number)

    logger.debug(f"Found {len(available_seats)} available seats on flight {flight_number}")
    return available_seats


def get_customer_profile_by_account(account_number: str) -> Optional[Dict[str, Any]]:
    """
    Get customer profile by account number.

    Args:
        account_number: Customer account number

    Returns:
        Customer profile dictionary if found, None otherwise
    """
    if not account_number:
        logger.warning("get_customer_profile_by_account called with empty account_number")
        return None

    profiles = load_customer_profiles()
    profile = next((p for p in profiles if p.get("account_number") == account_number), None)

    if profile:
        logger.debug(f"Found customer profile for account: {account_number}")
    else:
        logger.warning(f"Customer profile not found for account: {account_number}")

    return profile


def get_special_dietary_options() -> Dict[str, Any]:
    """
    Get special dietary options information.

    Returns:
        Dictionary of special dietary options
    """
    meals_data = load_meals_data()
    return meals_data.get("special_dietary_options", {})


def validate_seat_number(flight_number: str, seat_number: str) -> bool:
    """
    Validate if a seat number is valid for a specific flight.

    Args:
        flight_number: Flight number
        seat_number: Seat number to validate

    Returns:
        True if seat number is valid, False otherwise
    """
    seat_layout = get_seats_by_flight(flight_number)
    if not seat_layout:
        return False

    # Parse seat number (e.g., "14C" -> row=14, letter="C")
    try:
        row_str = ''.join(filter(str.isdigit, seat_number))
        letter = ''.join(filter(str.isalpha, seat_number))

        if not row_str or not letter:
            return False

        row = int(row_str)

        # Check in all cabin classes
        for cabin in ["business", "economy"]:
            cabin_data = seat_layout.get(cabin, {})
            rows = cabin_data.get("rows", [])
            seats_per_row = cabin_data.get("seats_per_row", [])

            if row in rows and letter in seats_per_row:
                return True

        return False

    except (ValueError, TypeError):
        return False


# ==========================================
# Cache Management
# ==========================================

def clear_data_cache():
    """
    Clear all cached data to force reload from files.
    Useful when data files are updated during runtime.
    """
    load_flights_data.cache_clear()
    load_seats_data.cache_clear()
    load_meals_data.cache_clear()
    load_customer_profiles.cache_clear()
    logger.info("Data cache cleared")


# ==========================================
# Module-level test
# ==========================================

if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.DEBUG)

    print("=== Testing Data Loader ===\n")

    # Test flights
    print("1. Loading flights...")
    flights = load_flights_data()
    print(f"   Loaded {len(flights)} flights\n")

    # Test specific flight
    print("2. Getting flight FLT-238...")
    flight = get_flight_by_number("FLT-238")
    if flight:
        print(f"   Found: {flight['departure']} -> {flight['arrival']}, Status: {flight['status']}\n")

    # Test seats
    print("3. Getting seats for FLT-238...")
    seats = get_seats_by_flight("FLT-238")
    if seats:
        print(f"   Business rows: {seats['business']['rows']}")
        print(f"   Occupied seats: {len(seats['business']['occupied']) + len(seats['economy']['occupied'])}\n")

    # Test seat availability
    print("4. Checking seat availability...")
    is_occupied = check_seat_occupied("FLT-238", "14C")
    print(f"   Seat 14C occupied: {is_occupied}")
    available = get_available_seats("FLT-238", "economy")
    print(f"   Available economy seats: {len(available)}\n")

    # Test meals
    print("5. Getting meal options...")
    meals = get_meals_by_route_and_class("domestic", "business")
    print(f"   Domestic business meals: {len(meals)}")
    if meals:
        print(f"   First meal: {meals[0]['name']}\n")

    # Test customer profiles
    print("6. Getting customer profile...")
    profile = get_customer_profile_by_account("38249175")
    if profile:
        print(f"   Customer: {profile['passenger_name']}, Flight: {profile['flight_number']}\n")

    print("=== All tests completed ===")
