import os
import re
import uuid
import requests
from typing import Dict, Any
from decimal import Decimal
from agents.control import ToolDefinition


# ─── Duffel REST API Helpers ──────────────────────────────────────────

DUFFEL_API_BASE = "https://api.duffel.com"

# Caches for cross-tool state (search -> book)
_duffel_offer_cache = {}   # offer_id -> {"passenger_ids": [...], "total_amount": str, "total_currency": str, "expires_at": str}


def _duffel_headers():
    """Return authorization headers for all Duffel REST API calls."""
    token = os.getenv('DUFFEL_API_TOKEN', '')
    if not token:
        try:
            from django.conf import settings as djsettings
            token = getattr(djsettings, 'DUFFEL_API_TOKEN', '')
        except Exception:
            pass
    if not token:
        raise ValueError("DUFFEL_API_TOKEN is not set in the environment.")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _duffel_post(path, payload, timeout=30):
    """POST to the Duffel API and return (status_code, response_data_dict)."""
    resp = requests.post(f"{DUFFEL_API_BASE}{path}", headers=_duffel_headers(), json=payload, timeout=timeout)
    return resp.status_code, resp.json()


def _duffel_get(path, params=None, timeout=15):
    """GET from the Duffel API and return (status_code, response_data_dict)."""
    resp = requests.get(f"{DUFFEL_API_BASE}{path}", headers=_duffel_headers(), params=params, timeout=timeout)
    return resp.status_code, resp.json()


def _parse_iso_duration(iso_dur):
    """Convert ISO 8601 duration like 'PT2H26M' to '2h 26m'."""
    if not iso_dur:
        return ''
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_dur)
    if not m:
        return iso_dur
    hours = m.group(1) or '0'
    minutes = m.group(2) or '0'
    return f"{hours}h {minutes}m"


def search_flights_tool(args: Dict[str, Any]) -> str:
    """Search for flights using the Duffel REST API."""

    origin = args.get('origin', '').strip().upper()
    destination = args.get('destination', '').strip().upper()
    departure_date = args.get('departure_date', '').strip()
    return_date = args.get('return_date', '').strip() if args.get('return_date') else ''
    adults = int(args.get('adults', 1))
    cabin_class = args.get('cabin_class', 'economy').strip().lower()

    if not origin or not destination or not departure_date:
        return "Error: origin, destination, and departure_date are required."

    try:
        # Build request payload
        slices = [{"origin": origin, "destination": destination, "departure_date": departure_date}]
        if return_date:
            slices.append({"origin": destination, "destination": origin, "departure_date": return_date})

        payload = {
            "data": {
                "slices": slices,
                "passengers": [{"type": "adult"} for _ in range(adults)],
                "cabin_class": cabin_class,
                "return_offers": True,
            }
        }

        status, resp_json = _duffel_post("/air/offer_requests", payload, timeout=45)

        if status not in (200, 201):
            error_msg = resp_json.get("errors", [{}])[0].get("message", str(resp_json)) if resp_json.get("errors") else str(resp_json)
            return f"Flight search failed (HTTP {status}): {error_msg}"

        data = resp_json.get("data", {})
        offers = data.get("offers", [])

        if not offers:
            return (
                f"No flights found from {origin} to {destination} on {departure_date}. "
                f"No offers are available for these dates/route."
            )

        # Cache passenger IDs for later booking
        passenger_ids = [p["id"] for p in data.get("passengers", [])]

        # Sort offers by price
        sorted_offers = sorted(offers, key=lambda o: float(o.get("total_amount", "9999")))

        lines = [
            f"Found {len(sorted_offers)} flight offer(s) from {origin} to "
            f"{destination} on {departure_date}:\n"
        ]

        for idx, offer in enumerate(sorted_offers[:15], 1):
            offer_id = offer.get("id", "")
            airline = offer.get("owner", {}).get("name", "Unknown Airline")
            total = offer.get("total_amount", "?")
            currency = offer.get("total_currency", "USD")

            # Cache this offer for booking
            _duffel_offer_cache[offer_id] = {
                "passenger_ids": passenger_ids,
                "total_amount": total,
                "total_currency": currency,
                "expires_at": offer.get("expires_at", ""),
            }

            # Extract first slice details for display
            slices_data = offer.get("slices", [])
            first_slice = slices_data[0] if slices_data else {}

            dep_apt = first_slice.get("origin", {}).get("iata_code", origin)
            arr_apt = first_slice.get("destination", {}).get("iata_code", destination)
            duration = _parse_iso_duration(first_slice.get("duration", ""))
            segments = first_slice.get("segments", [])
            num_stops = max(0, len(segments) - 1)
            stops_text = 'Nonstop' if num_stops == 0 else f'{num_stops} stop{"s" if num_stops > 1 else ""}'

            if segments:
                dep_time_raw = segments[0].get("departing_at", "")
                arr_time_raw = segments[-1].get("arriving_at", "")
                dep_time = dep_time_raw[11:16] if len(dep_time_raw) > 16 else ''
                arr_time = arr_time_raw[11:16] if len(arr_time_raw) > 16 else ''
            else:
                dep_time = arr_time = ''

            lines.append(
                f"{idx}. **{airline}** | {dep_apt} {dep_time} \u2192 {arr_apt} {arr_time} | "
                f"{duration} | {stops_text} | **{total} {currency}** "
                f"[Offer: {offer_id}]"
            )

        expires = sorted_offers[0].get("expires_at", "")
        if expires:
            lines.append(f"\n*Offers expire at {expires}. Book promptly to secure these prices.*")

        return '\n'.join(lines)

    except Exception as exc:
        return f"Flight search failed: {exc}"


SEARCH_FLIGHTS_DEFINITION = ToolDefinition(
    name="search_flights",
    description=(
        "Search for flight offers between airports using the Duffel API. Returns a list of available "
        "flights with airlines, times, duration, stops, prices, and offer IDs for booking. "
        "Use IATA airport codes (e.g. LAX, JFK, SYD). Dates must be in YYYY-MM-DD format."
    ),
    parameters={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin IATA airport code (e.g. 'LAX', 'SYD', 'LHR')."
            },
            "destination": {
                "type": "string",
                "description": "Destination IATA airport code (e.g. 'JFK', 'NRT', 'CDG')."
            },
            "departure_date": {
                "type": "string",
                "description": "Departure date in YYYY-MM-DD format."
            },
            "return_date": {
                "type": "string",
                "description": "Optional return date in YYYY-MM-DD format for round trips."
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers (default 1)."
            },
            "cabin_class": {
                "type": "string",
                "description": "Cabin class: 'economy', 'premium_economy', 'business', or 'first' (default 'economy')."
            }
        },
        "required": ["origin", "destination", "departure_date"]
    },
    function=search_flights_tool,
    requires_approval=False
)


def book_travel_tool(args: Dict[str, Any]) -> str:
    """Book a flight via the Duffel API and persist to database."""
    from chat.models import Booking

    given_name = args.get('given_name', '')
    family_name = args.get('family_name', '')
    passenger_email = args.get('passenger_email', '')
    phone_number = args.get('phone_number', '')
    date_of_birth = args.get('date_of_birth', '')
    gender = args.get('gender', 'm')
    title = args.get('title', 'mr')
    card_last_four = args.get('card_last_four', '')
    card_holder_name = args.get('card_holder_name', '')

    # Duffel identifiers
    offer_id = args.get('offer_id', '')

    # Flight display fields
    airline = args.get('airline', '')
    origin = args.get('origin', '')
    destination = args.get('destination', '')
    departure_date = args.get('departure_date', '')
    departure_time = args.get('departure_time', '')
    arrival_time = args.get('arrival_time', '')
    stops = args.get('stops', 0)
    duration = args.get('duration', '')
    booking_class = args.get('booking_class', 'economy')

    # Validation
    if not given_name or not family_name:
        return "Error: both given_name and family_name are required."
    if not passenger_email:
        return "Error: passenger_email is required."
    if not card_last_four:
        return "Error: card_last_four is required for payment verification."
    if not offer_id:
        return "Error: offer_id is required for flight booking. Use search_flights first to get offer IDs."

    passenger_name = f"{given_name} {family_name}"

    cached = _duffel_offer_cache.get(offer_id)
    if not cached:
        return (
            "Error: Offer not found in cache. The offer may have expired. "
            "Please run search_flights again to get fresh offers."
        )

    try:
        passenger_data = [{
            "id": cached["passenger_ids"][0],
            "given_name": given_name,
            "family_name": family_name,
            "born_on": date_of_birth or "1990-01-01",
            "title": title.lower().rstrip('.'),
            "gender": gender[0].lower() if gender else "m",
            "email": passenger_email,
            "phone_number": phone_number or "+10000000000",
        }]

        # Add additional passengers if there are more cached passenger IDs
        for pid in cached["passenger_ids"][1:]:
            passenger_data.append({
                "id": pid,
                "given_name": given_name,
                "family_name": family_name,
                "born_on": date_of_birth or "1990-01-01",
                "title": title.lower().rstrip('.'),
                "gender": gender[0].lower() if gender else "m",
                "email": passenger_email,
                "phone_number": phone_number or "+10000000000",
            })

        order_payload = {
            "data": {
                "selected_offers": [offer_id],
                "passengers": passenger_data,
                "payments": [{
                    "type": "balance",
                    "currency": cached["total_currency"],
                    "amount": cached["total_amount"],
                }],
                "type": "instant",
            }
        }

        status, resp_json = _duffel_post("/air/orders", order_payload, timeout=45)

        if status not in (200, 201):
            error_msg = resp_json.get("errors", [{}])[0].get("message", str(resp_json)) if resp_json.get("errors") else str(resp_json)
            return f"Flight booking failed (HTTP {status}): {error_msg}"

        order_data = resp_json.get("data", {})
        booking_ref = order_data.get("booking_reference", "") or uuid.uuid4().hex[:10].upper()
        duffel_order_id = order_data.get("id", "")
        total_amount = order_data.get("total_amount", cached["total_amount"])
        total_currency = order_data.get("total_currency", cached["total_currency"])

        # Persist to database
        Booking.objects.create(
            booking_ref=booking_ref,
            booking_type='flight',
            duffel_order_id=duffel_order_id,
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            total_price=Decimal(str(total_amount)),
            currency=total_currency,
            status='confirmed',
            details={
                "duffel_order_id": duffel_order_id,
                "offer_id": offer_id,
                "airline": airline,
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "stops": stops,
                "duration": duration,
                "booking_class": booking_class,
                "card_last_four": card_last_four,
            },
        )

        # Remove from cache after successful booking
        _duffel_offer_cache.pop(offer_id, None)

        # Build confirmation
        lines = [
            "## Flight Booking Confirmed!",
            "",
            f"**Booking Reference (PNR):** `{booking_ref}`",
            f"**Duffel Order ID:** `{duffel_order_id}`",
            f"**Status:** Confirmed",
            f"**Passenger:** {passenger_name} ({passenger_email})",
            f"**Payment:** Card ending in ****{card_last_four}",
        ]
        if airline:
            lines.append(f"**Airline:** {airline}")
        if origin and destination:
            lines.append(f"**Route:** {origin} \u2192 {destination}")
        if departure_time:
            lines.append(f"**Departure:** {departure_date} {departure_time}")
        if arrival_time:
            lines.append(f"**Arrival:** {arrival_time}")
        if duration:
            lines.append(f"**Duration:** {duration}")
        stops_int = int(stops) if stops else 0
        stops_text = 'Nonstop' if stops_int == 0 else f'{stops_int} stop{"s" if stops_int > 1 else ""}'
        lines.append(f"**Stops:** {stops_text}")
        lines.append(f"**Class:** {booking_class}")
        lines.append(f"**Total Price:** {total_amount} {total_currency}")
        lines.append("")
        lines.append("*Booked via Duffel API. This booking is saved to the database.*")

        return '\n'.join(lines)

    except Exception as exc:
        return f"Flight booking failed: {exc}"


BOOK_TRAVEL_DEFINITION = ToolDefinition(
    name="book_travel",
    description=(
        "Book a flight via the Duffel API. Use this AFTER searching with "
        "search_flights. You need the offer_id from the search results.\n\n"
        "IMPORTANT - You MUST collect the passenger's booking details STEP BY STEP in this exact order. "
        "Ask ONE question at a time, wait for the user's response, then ask the next:\n"
        "  Step 1: Ask for the passenger's given name (first name) and family name (last name).\n"
        "  Step 2: Ask for their date of birth (YYYY-MM-DD), gender (male/female), and title (Mr/Ms/Mrs/Dr).\n"
        "  Step 3: Ask for their phone number and email address.\n"
        "  Step 4: Ask for their card details (card number, expiry, CVV) for verification. "
        "Store only the last 4 digits as card_last_four and the name on the card as card_holder_name.\n"
        "  Step 5: Confirm all details and total price with the user, then call this tool.\n\n"
        "Do NOT ask for multiple steps in the same message. Do NOT call this tool until ALL steps are completed. "
        "Returns a booking confirmation with the airline PNR."
    ),
    parameters={
        "type": "object",
        "properties": {
            "offer_id": {
                "type": "string",
                "description": "Duffel offer ID from search_flights results (e.g. 'off_00009xxx')."
            },
            "given_name": {
                "type": "string",
                "description": "Passenger's given (first) name (e.g. 'John')."
            },
            "family_name": {
                "type": "string",
                "description": "Passenger's family (last) name (e.g. 'Doe')."
            },
            "date_of_birth": {
                "type": "string",
                "description": "Date of birth in YYYY-MM-DD format."
            },
            "gender": {
                "type": "string",
                "description": "Gender: 'm' for male, 'f' for female."
            },
            "title": {
                "type": "string",
                "description": "Title: 'mr', 'ms', 'mrs', 'miss', or 'dr'."
            },
            "passenger_email": {
                "type": "string",
                "description": "Email address of the passenger."
            },
            "phone_number": {
                "type": "string",
                "description": "Phone number with country code (e.g. '+14155551234')."
            },
            "card_last_four": {
                "type": "string",
                "description": "Last 4 digits of the payment card number (e.g. '4242')."
            },
            "card_holder_name": {
                "type": "string",
                "description": "Name on the payment card."
            },
            "airline": {
                "type": "string",
                "description": "Airline name for display."
            },
            "origin": {
                "type": "string",
                "description": "Departure airport code."
            },
            "destination": {
                "type": "string",
                "description": "Arrival airport code."
            },
            "departure_date": {
                "type": "string",
                "description": "Departure date YYYY-MM-DD."
            },
            "departure_time": {
                "type": "string",
                "description": "Departure time e.g. '08:30'."
            },
            "arrival_time": {
                "type": "string",
                "description": "Arrival time e.g. '14:45'."
            },
            "stops": {
                "type": "integer",
                "description": "Number of stops."
            },
            "duration": {
                "type": "string",
                "description": "Flight duration e.g. '5h 30m'."
            },
            "booking_class": {
                "type": "string",
                "description": "Cabin class e.g. 'economy', 'business'."
            }
        },
        "required": ["offer_id", "given_name", "family_name", "passenger_email", "card_last_four"]
    },
    function=book_travel_tool,
    requires_approval=True
)


# ─── Booking Management Tools ────────────────────────────────────────

def get_booking_tool(args: Dict[str, Any]) -> str:
    """Retrieve booking details by reference code."""
    from chat.models import Booking

    booking_ref = args.get('booking_ref', '').strip()
    if not booking_ref:
        return "Error: booking_ref is required."

    try:
        booking = Booking.objects.get(booking_ref=booking_ref)
    except Booking.DoesNotExist:
        return f"No booking found with reference '{booking_ref}'."
    except Exception as exc:
        return f"Database lookup failed: {exc}"

    lines = [
        f"## Booking Details",
        "",
        f"**Reference:** `{booking.booking_ref}`",
        f"**Type:** {booking.booking_type.title()}",
        f"**Status:** {booking.status.title()}",
        f"**Passenger:** {booking.passenger_name} ({booking.passenger_email})",
        f"**Total Price:** {booking.total_price} {booking.currency}",
        f"**Booked On:** {booking.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]

    if booking.duffel_order_id:
        lines.append(f"**Duffel ID:** `{booking.duffel_order_id}`")

    details = booking.details or {}
    if details.get('airline'):
        lines.append(f"**Airline:** {details['airline']}")
    if details.get('origin') and details.get('destination'):
        lines.append(f"**Route:** {details['origin']} \u2192 {details['destination']}")
    if details.get('departure_date'):
        dep_line = details['departure_date']
        if details.get('departure_time'):
            dep_line += f" {details['departure_time']}"
        lines.append(f"**Departure:** {dep_line}")
    if details.get('arrival_time'):
        lines.append(f"**Arrival:** {details['arrival_time']}")
    if details.get('duration'):
        lines.append(f"**Duration:** {details['duration']}")
    if details.get('booking_class'):
        lines.append(f"**Class:** {details['booking_class']}")

    # Try to fetch live status from Duffel if it's a flight order
    if booking.booking_type == 'flight' and booking.duffel_order_id and booking.status != 'cancelled':
        try:
            status_code, order_resp = _duffel_get(f"/air/orders/{booking.duffel_order_id}")
            if status_code == 200:
                order_data = order_resp.get("data", {})
                live_status = "Live" if order_data.get("live_mode") else "Test"
                available_actions = order_data.get("available_actions", [])
                lines.append(f"**Mode:** {live_status}")
                if available_actions:
                    lines.append(f"**Available Actions:** {', '.join(available_actions)}")
        except Exception:
            pass

    return '\n'.join(lines)


GET_BOOKING_DEFINITION = ToolDefinition(
    name="get_booking",
    description="Retrieve details of an existing booking by its reference code. Shows booking status, passenger info, and travel details.",
    parameters={
        "type": "object",
        "properties": {
            "booking_ref": {
                "type": "string",
                "description": "The booking reference code (e.g. 'RZPNX8' or the code returned when booking was made)."
            }
        },
        "required": ["booking_ref"]
    },
    function=get_booking_tool,
    requires_approval=False
)


def cancel_booking_tool(args: Dict[str, Any]) -> str:
    """Cancel an existing booking via the Duffel API and update the database."""
    from chat.models import Booking

    booking_ref = args.get('booking_ref', '').strip()
    if not booking_ref:
        return "Error: booking_ref is required."

    try:
        booking = Booking.objects.get(booking_ref=booking_ref)
    except Booking.DoesNotExist:
        return f"No booking found with reference '{booking_ref}'."

    if booking.status == 'cancelled':
        return f"Booking '{booking_ref}' is already cancelled."

    if not booking.duffel_order_id:
        return f"Booking '{booking_ref}' has no Duffel ID — cannot cancel via API."

    try:
        # Step 1: Create cancellation (gets refund quote)
        cancel_payload = {"data": {"order_id": booking.duffel_order_id}}
        c_status, c_resp = _duffel_post("/air/order_cancellations", cancel_payload)
        if c_status not in (200, 201):
            error_msg = c_resp.get("errors", [{}])[0].get("message", str(c_resp)) if c_resp.get("errors") else str(c_resp)
            return f"Flight cancellation failed: {error_msg}"

        cancellation_data = c_resp.get("data", {})
        cancellation_id = cancellation_data.get("id", "")
        refund_amount = cancellation_data.get("refund_amount", "0")
        refund_currency = cancellation_data.get("refund_currency", booking.currency)

        # Step 2: Confirm the cancellation
        confirm_status, confirm_resp = _duffel_post(f"/air/order_cancellations/{cancellation_id}/actions/confirm", {})
        confirmed_data = confirm_resp.get("data", {}) if confirm_status in (200, 201) else {}

        booking.status = 'cancelled'
        booking.save()

        return (
            f"## Booking Cancelled\n\n"
            f"**Reference:** `{booking_ref}`\n"
            f"**Status:** Cancelled\n"
            f"**Refund:** {refund_amount} {refund_currency}\n"
            f"**Cancelled At:** {confirmed_data.get('confirmed_at', 'now')}"
        )

    except Exception as exc:
        return f"Cancellation failed: {exc}"


CANCEL_BOOKING_DEFINITION = ToolDefinition(
    name="cancel_booking",
    description="Cancel an existing flight booking. Cancels via the Duffel API and updates the database. Provide the booking reference code.",
    parameters={
        "type": "object",
        "properties": {
            "booking_ref": {
                "type": "string",
                "description": "The booking reference code to cancel."
            }
        },
        "required": ["booking_ref"]
    },
    function=cancel_booking_tool,
    requires_approval=True
)


def list_bookings_tool(args: Dict[str, Any]) -> str:
    """List all bookings from the database."""
    from chat.models import Booking

    bookings = Booking.objects.order_by('-created_at')[:20]

    if not bookings:
        return "No bookings found."

    lines = [f"## Bookings ({len(bookings)} found)\n"]
    for b in bookings:
        status_icon = '\u2705' if b.status == 'confirmed' else '\u274c' if b.status == 'cancelled' else '\u23f3'
        lines.append(
            f"- {status_icon} `{b.booking_ref}` | {b.booking_type.title()} | "
            f"{b.passenger_name} | {b.total_price} {b.currency} | "
            f"{b.status.title()} | {b.created_at.strftime('%Y-%m-%d')}"
        )

    return '\n'.join(lines)


LIST_BOOKINGS_DEFINITION = ToolDefinition(
    name="list_bookings",
    description="List all travel bookings stored in the database. Shows booking references, types, passengers, prices, and statuses.",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    function=list_bookings_tool,
    requires_approval=False
)
