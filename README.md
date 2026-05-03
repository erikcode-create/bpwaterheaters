# BP Water Heaters ERP System

Private ERP, website, booking, payment, portal, and admin tooling for BP Water
Heaters.

This repository is the BP Water Heaters system of record. It includes a custom
BP app layered onto ERPNext so the business can keep customers, booking holds,
confirmed estimates, Stripe payment metadata, tax rules, portal access, and
admin/mobile workflows in one operational system.

## Repository Layout

- `apps/bp_water_heaters` - BP Water Heaters custom app, public site pages,
  booking APIs, portal APIs, payment hooks, branding, and BP-specific DocTypes.
- `erpnext` - vendored ERPNext application code required by the ERP runtime.
- `deploy/bpwh-erp` - Docker overlay that installs the BP custom app into the
  ERPNext image used for deployment.
- `ios/BPWaterHeatersAdmin` - native iPhone admin app for internal BP Water
  Heaters workflows.
- `docs` - BP Water Heaters launch, brand, and implementation notes.

## Runtime Notes

ERPNext runs on a third-party framework runtime. Some package, Bench, Docker,
hook, and upstream module identifiers must remain exactly as the runtime expects.
Those references are wiring, not BP Water Heaters branding.

Do not remove these required runtime references as part of a branding cleanup:

- Python framework imports used by ERPNext
- Bench metadata used by ERPNext
- Docker base image names required by the ERP runtime
- ERPNext app/package identifiers such as `erpnext`
- Framework user and filesystem paths inside the ERPNext container

## Development

Use this repository, not the public ERPNext repository, for BP Water Heaters
changes:

```sh
git clone https://github.com/erikcode-create/bpwaterheaters.git
```

The BP custom app is the primary development surface for customer-facing pages,
booking flow, portal behavior, accounting integration, and admin APIs. Changes
to vendored ERPNext core should be limited and intentional.

## Deployment

The production image is built from `deploy/bpwh-erp/Dockerfile`. That image starts
from the ERPNext runtime image, installs `apps/bp_water_heaters`, and exposes the
BP Water Heaters assets under the expected ERPNext asset path.

Deployment should preserve ERPNext as the operational source of truth while
presenting BP Water Heaters branding to customers, admins, and internal users.

## Security

This is a private business system. Do not report BP Water Heaters security
issues to public ERPNext or community trackers. Report issues through the private
repository or the internal BP Water Heaters operations channel.

Never include customer payment data, credentials, session tokens, portal tokens,
or private customer details in issues, commits, screenshots, logs, or PR text.

## Licensing And Attribution

This repository includes vendored ERPNext code and related attribution,
trademark, and license documents. Keep those legal notices intact unless a
separate licensing review explicitly approves a change.
