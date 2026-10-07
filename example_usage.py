"""
Dealer Studio API Example Usage Script
----------------------------------------
This script demonstrates how to call each API endpoint in the Dealer Studio platform.

To run with your credentials:
1. Copy .env.example to .env
2. Add your DEALERSTUDIO_API_KEY and optionally DEALERSTUDIO_DEALERSHIP_ID
3. Run: python example_usage.py
"""

import os
from dealerstudio_client import (
    DealerStudioClient,
    DealerStudioError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    RateLimitError
)

def run_examples():
    api_key = os.getenv("DEALERSTUDIO_API_KEY", "YOUR_BEARER_TOKEN_HERE")
    dealership_id = os.getenv("DEALERSTUDIO_DEALERSHIP_ID", "123")

    print("[*] Initializing Dealer Studio Client...")
    client = DealerStudioClient(
        api_key=api_key,
        default_dealership_id=dealership_id
    )

    # ==========================================
    # 1. LEADS MANAGEMENT
    # ==========================================
    print("\n--- 1. Leads Management ---")
    try:
        # A. Create a new lead
        print("[*] Creating a lead...")
        created_lead = client.leads.create(
            name="John Doe",
            email="john.doe@example.com",
            phone="0412345678",
            dealership_id=dealership_id,
            brand="Toyota",
            model="RAV4",
            source="Website Form",
            comments="Interested in 2024 Cruiser Hybrid",
            trade_in={
                "owner": "John Doe",
                "kmReading": 45000,
                "fuelType": "Petrol",
                "tradeInValue": 18000,
                "remarks": "Good condition, regular logbook service"
            },
            fields={
                "country": "Australia",
                "showroom": "Main Showroom"
            }
        )
        print("[OK] Lead created:", created_lead)

        # B. List leads
        print("[*] Listing recent leads...")
        leads_list = client.leads.list(page=1, per_page=5)
        print("[OK] Leads list retrieved:", leads_list)

        # C. Update a lead
        lead_id = created_lead.get("id", 1)
        print(f"[*] Updating lead {lead_id}...")
        updated = client.leads.update(
            lead_id=lead_id,
            lead_data={
                "comments": "Customer prefers morning test drive"
            }
        )
        print("[OK] Lead updated:", updated)

    except AuthenticationError as e:
        print(f"[!] Authentication required: {e}")
    except ValidationError as e:
        print(f"[!] Validation error: {e}")
    except DealerStudioError as e:
        print(f"[!] API Error: {e}")

    # ==========================================
    # 2. VEHICLE INVENTORY & CARS
    # ==========================================
    print("\n--- 2. Vehicle Inventory & Stock ---")
    try:
        # A. Search & List Cars
        print("[*] Searching inventory...")
        inventory = client.cars.list(
            page=1,
            per_page=5,
            make="Toyota",
            status="active"
        )
        print("[OK] Inventory:", inventory)

        # B. Get car details by ID or slug
        car_id = "sample-car-id"
        print(f"[*] Fetching car details for {car_id}...")
        car_details = client.cars.get(car_id=car_id)
        print("[OK] Car Details:", car_details)

        # C. Lookup by stock number
        stock_number = "STK-9901"
        print(f"[*] Finding car with stock number {stock_number}...")
        stock_info = client.cars.get_by_stock_number(stock_number=stock_number)
        print("[OK] Stock Lookup:", stock_info)

        # D. Get similar cars
        print(f"[*] Finding similar cars for {car_id}...")
        similar = client.cars.list_similar(car_id=car_id)
        print("[OK] Similar cars:", similar)

        # E. Get performance & payment processor info
        print(f"[*] Fetching performance metrics for {car_id}...")
        perf = client.cars.get_performance(car_id=car_id)
        print("[OK] Performance metrics:", perf)

    except AuthenticationError as e:
        print(f"[!] Authentication required: {e}")
    except NotFoundError as e:
        print(f"[!] Vehicle not found: {e}")
    except DealerStudioError as e:
        print(f"[!] API Error: {e}")

    # ==========================================
    # 3. SERVICE BOOKING & WORKSHOP
    # ==========================================
    print("\n--- 3. Service Bookings & DMS Integration ---")
    try:
        # A. Resolve vehicle by Registration Plate or VIN
        rego = "ABC123"
        print(f"[*] Resolving vehicle details for rego: {rego}...")
        vehicle_res = client.service_bookings.resolve_vehicle(
            dealership_id=dealership_id,
            registration_number=rego
        )
        print("[OK] Resolved Vehicle:", vehicle_res)

        # B. List available service offerings
        print("[*] Listing available service packages...")
        services = client.service_bookings.list_services(
            dealership_id=dealership_id,
            registration_number=rego
        )
        print("[OK] Services:", services)

        # C. List workshops / service centers
        print("[*] Listing dealership workshops...")
        workshops = client.service_bookings.list_workshops(
            dealership_id=dealership_id
        )
        print("[OK] Workshops:", workshops)

        # D. Check booking capabilities & slots
        print("[*] Checking DMS capabilities...")
        capabilities = client.service_bookings.get_capabilities(
            dealership_id=dealership_id
        )
        print("[OK] Capabilities:", capabilities)

        # E. Create a service booking
        print("[*] Booking a service appointment...")
        booking = client.service_bookings.create_booking(
            dealership_id=dealership_id,
            customer_name="Jane Smith",
            customer_email="jane.smith@example.com",
            customer_phone="0423456789",
            workshop_id=1,
            booking_date="2026-11-15T09:00:00Z",
            service_ids=[101],
            vehicle_details={
                "registration_number": rego,
                "make": "Toyota",
                "model": "Corolla",
                "year": 2021
            }
        )
        print("[OK] Booking created:", booking)

    except AuthenticationError as e:
        print(f"[!] Authentication required: {e}")
    except DealerStudioError as e:
        print(f"[!] API Error: {e}")

    # ==========================================
    # 4. DEALERSHIPS & VALUATIONS
    # ==========================================
    print("\n--- 4. Dealerships & Valuations ---")
    try:
        # A. List accessible dealerships
        print("[*] Fetching accessible dealerships...")
        dealerships = client.dealerships.list()
        print("[OK] Dealerships:", dealerships)

        # B. Get trade-in valuation settings
        print(f"[*] Getting valuation settings for dealership {dealership_id}...")
        valuation_settings = client.dealerships.get_valuation_settings(dealership_id)
        print("[OK] Valuation Settings:", valuation_settings)

    except AuthenticationError as e:
        print(f"[!] Authentication required: {e}")
    except DealerStudioError as e:
        print(f"[!] API Error: {e}")

    # ==========================================
    # 5. WATCHLIST MANAGEMENT
    # ==========================================
    print("\n--- 5. Customer Watchlist ---")
    try:
        # A. Add vehicle to watchlist
        website_slug = "motorama"
        phone_identity_id = "pid-12345"
        car_id = "sample-car-id"

        print(f"[*] Adding car {car_id} to watchlist for user {phone_identity_id}...")
        watch_add = client.watchlist.add_to_watchlist(
            website=website_slug,
            phone_identity_id=phone_identity_id,
            car_id=car_id
        )
        print("[OK] Added to watchlist:", watch_add)

    except AuthenticationError as e:
        print(f"[!] Authentication required: {e}")
    except DealerStudioError as e:
        print(f"[!] API Error: {e}")

    print("\n[OK] Example script execution completed.")


if __name__ == "__main__":
    run_examples()
