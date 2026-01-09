from __future__ import annotations

import inspect
import logging
import os
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from agents_demo.data_loader import (
    get_customer_profile_by_account,
    get_flight_by_number,
    get_meals_by_route_and_class,
    get_seats_by_flight,
    get_special_dietary_options,
)
from agents_demo.storage import record_meal_order

logger = logging.getLogger(__name__)

mcp = FastMCP("Food Service MCP")


def _resolve_asgi_app(server: FastMCP):
    for attr in ("app", "asgi_app", "_app"):
        app = getattr(server, attr, None)
        if app is not None:
            return app
    return server


app = _resolve_asgi_app(mcp)


def _infer_cabin_class(flight_number: str, seat_number: Optional[str]) -> str:
    if not flight_number or not seat_number:
        return "economy"
    seat_layout = get_seats_by_flight(flight_number)
    if not seat_layout:
        return "economy"
    business_rows = seat_layout.get("business", {}).get("rows", [])
    try:
        row_num = int("".join(ch for ch in seat_number if ch.isdigit()))
    except ValueError:
        return "economy"
    return "business" if row_num in business_rows else "economy"


def _format_menu(meals: list[Dict[str, Any]]) -> list[str]:
    formatted = []
    for idx, meal in enumerate(meals, start=1):
        name = meal.get("name", "Unknown")
        tags = meal.get("dietary_tags", [])
        tag_text = f" ({', '.join(tags)})" if tags else ""
        formatted.append(f"{idx}) {name}{tag_text}")
    return formatted


@mcp.tool()
def fetch_customer_profile(account_number: str) -> Dict[str, Any]:
    """Fetch a customer profile by account number."""
    profile = get_customer_profile_by_account(account_number)
    if not profile:
        return {"error": f"No stored profile found for account {account_number}."}
    summary = (
        f"Profile loaded for {profile.get('passenger_name', 'the passenger')} "
        f"(account {profile.get('account_number', account_number)}). Confirmation "
        f"{profile.get('confirmation_number', 'unknown')}, flight "
        f"{profile.get('flight_number', 'unknown')}, seat "
        f"{profile.get('seat_number', 'unknown')}; meal preference: "
        f"{profile.get('meal_preference', 'unspecified')}."
    )
    return {"summary": summary, "profile": profile}


@mcp.tool()
def check_menu_options(
    flight_number: str,
    seat_number: Optional[str] = None,
    cabin_class: Optional[str] = None,
) -> Dict[str, Any]:
    """Return meal options for the specified flight/cabin."""
    if not flight_number:
        return {"error": "Flight number is required to check menu options."}
    flight = get_flight_by_number(flight_number)
    if not flight:
        return {"error": f"Flight {flight_number} not found. Unable to retrieve menu options."}

    route_type = flight.get("route_type", "domestic")
    resolved_cabin = (cabin_class or _infer_cabin_class(flight_number, seat_number)).lower()
    meals = get_meals_by_route_and_class(route_type, resolved_cabin)
    if not meals:
        return {"error": f"No meal data for {route_type} {resolved_cabin} class."}

    formatted = _format_menu(meals)
    special = get_special_dietary_options() or {}
    special_notes = []
    for key in ("nut_free", "low_sodium", "kosher", "halal"):
        entry = special.get(key, {})
        desc = entry.get("description")
        if desc:
            special_notes.append(desc)

    return {
        "flight_number": flight_number,
        "route_type": route_type,
        "cabin_class": resolved_cabin,
        "menu": formatted,
        "special_options": special_notes or ["Special dietary requests available upon advance notice."],
    }


@mcp.tool()
def record_meal_preference(
    meal_choice: str,
    conversation_id: Optional[str] = None,
    account_number: Optional[str] = None,
    confirmation_number: Optional[str] = None,
    flight_number: Optional[str] = None,
    seat_number: Optional[str] = None,
    dietary_notes: Optional[str] = None,
    special_requests: Optional[str] = None,
) -> Dict[str, Any]:
    """Store a meal preference before final confirmation."""
    saved = record_meal_order(
        conversation_id=conversation_id,
        account_number=account_number,
        confirmation_number=confirmation_number,
        flight_number=flight_number,
        seat_number=seat_number,
        meal_choice=meal_choice,
        dietary_notes=dietary_notes,
        special_requests=special_requests,
        status="pending_confirmation",
    )
    return {
        "status": "pending_confirmation",
        "meal_choice": meal_choice,
        "order_saved": saved,
    }


@mcp.tool()
def confirm_meal_selection(
    meal_choice: str,
    conversation_id: Optional[str] = None,
    account_number: Optional[str] = None,
    confirmation_number: Optional[str] = None,
    flight_number: Optional[str] = None,
    seat_number: Optional[str] = None,
    dietary_notes: Optional[str] = None,
    special_requests: Optional[str] = None,
) -> Dict[str, Any]:
    """Confirm a meal selection and persist the order."""
    saved = record_meal_order(
        conversation_id=conversation_id,
        account_number=account_number,
        confirmation_number=confirmation_number,
        flight_number=flight_number,
        seat_number=seat_number,
        meal_choice=meal_choice,
        dietary_notes=dietary_notes,
        special_requests=special_requests,
        status="ordered",
    )
    return {
        "status": "ordered",
        "meal_choice": meal_choice,
        "order_saved": saved,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    host = os.getenv("FOOD_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("FOOD_MCP_PORT", "8007"))
    transport = os.getenv("FOOD_MCP_TRANSPORT", "streamable-http")
    run_sig = inspect.signature(mcp.run)
    accepts_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in run_sig.parameters.values()
    )
    kwargs = {}
    if "transport" in run_sig.parameters or accepts_kwargs:
        kwargs["transport"] = transport
    if "host" in run_sig.parameters or accepts_kwargs:
        kwargs["host"] = host
    if "port" in run_sig.parameters or accepts_kwargs:
        kwargs["port"] = port

    if "host" not in kwargs or "port" not in kwargs:
        if transport == "streamable-http":
            try:
                import uvicorn
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("uvicorn is required to bind host/port: %s", exc)
                raise
            logger.info("Starting Food MCP server on %s:%s (%s)", host, port, transport)
            uvicorn.run(app, host=host, port=port)
            return
    if "host" in kwargs and "port" in kwargs:
        logger.info("Starting Food MCP server on %s:%s (%s)", host, port, transport)
    else:
        logger.info(
            "Starting Food MCP server with transport=%s (host/port handled by MCP defaults)",
            transport,
        )
    mcp.run(**kwargs)


if __name__ == "__main__":
    main()
