# BP Water Heaters Frappe Site Design

## Scope

Build BP Water Heaters as a custom Frappe app installed on the ERPNext site. ERPNext remains the source of truth for booking holds, confirmed estimates, contact requests, Stripe metadata, customers, and later admin/mobile workflows.

## Launch Rules

- Service area: Nevada and California.
- Crew capacity: one crew.
- Online booking hours: Monday through Friday, 9 AM to 5 PM.
- Appointment type: one-hour estimate.
- Buffer: 30 minutes before and after each estimate.
- Call-out fee: $85.
- Payment: Stripe Checkout through the existing Blueberg Construction Stripe account, tagged with BP Water Heaters metadata.

## Architecture

The app adds public website pages and guest-safe API methods under `bp_water_heaters.api.booking`. Public booking creates a `BPWH Booking` in `Pending Payment` state with a 15-minute hold. If Stripe credentials are configured, the API creates a hosted Stripe Checkout Session and redirects the customer to pay. Stripe webhooks update the booking to `Confirmed`.

The first deploy keeps DNS unchanged. The app is verified at the ERPNext staging host before the public `bpwaterheaters.com` DNS is pointed to the VPS.

## Follow-Up

The next implementation slice should add Microsoft-only admin login, full Stripe accounting reconciliation into Sales Invoice and Payment Entry records, live chat records, and the Swift iPhone admin app API.
