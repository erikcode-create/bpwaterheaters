# BP Water Heaters Live Cutover Runbook

## Deployed Code

- VPS: `76.13.24.125`
- ERP compose path: `/srv/bpwaterheaters-erp/gitops`
- Current ERP image: `bpwaterheaters-erp:bpwh-20260503k`
- ERP site: `erp-staging.bpwaterheaters.com`

## DNS Records

Authoritative DNS is currently GreenGeeks.

Set:

- `bpwaterheaters.com` A `76.13.24.125`
- `www.bpwaterheaters.com` CNAME `bpwaterheaters.com`
- `portal.bpwaterheaters.com` A `76.13.24.125`

Current observed state before DNS cutover:

- `bpwaterheaters.com` A `108.178.20.198`
- `www.bpwaterheaters.com` CNAME `bpwaterheaters.com`, resolving to `108.178.20.198`
- `portal.bpwaterheaters.com` no record
- `erp-staging.bpwaterheaters.com` A `76.13.24.125`

## Site Config Already Set

```bash
bench --site erp-staging.bpwaterheaters.com set-config bpwh_public_base_url https://bpwaterheaters.com
bench --site erp-staging.bpwaterheaters.com set-config bpwh_portal_base_url https://portal.bpwaterheaters.com
bench --site erp-staging.bpwaterheaters.com set-config bpwh_plaid_environment production
bench --site erp-staging.bpwaterheaters.com set-config bpwh_mobile_redirect_uri bpwhadmin://auth
```

## Remaining Secret Config

Set these only after creating live keys/apps in the vendor accounts:

```bash
bench --site erp-staging.bpwaterheaters.com set-config bpwh_stripe_secret_key 'rk_live_...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_stripe_webhook_secret 'whsec_...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_microsoft_tenant_id '...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_microsoft_client_id '...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_microsoft_client_secret '...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_mobile_microsoft_client_id '...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_plaid_client_id '...'
bench --site erp-staging.bpwaterheaters.com set-config bpwh_plaid_secret '...'
```

Then run:

```bash
bench --site erp-staging.bpwaterheaters.com migrate
bench --site erp-staging.bpwaterheaters.com clear-cache
```

## Password Login Disable

Do this only after both Microsoft admins successfully log in:

```bash
bench --site erp-staging.bpwaterheaters.com set-config bpwh_disable_password_login_after_microsoft 1
bench --site erp-staging.bpwaterheaters.com migrate
```

Emergency recovery over SSH:

```bash
bench --site erp-staging.bpwaterheaters.com set-config bpwh_disable_password_login_after_microsoft 0
bench --site erp-staging.bpwaterheaters.com set-config disable_user_pass_login 0
bench --site erp-staging.bpwaterheaters.com clear-cache
```

## Stripe

Create a live restricted key with enough access for Checkout Sessions, Customers, PaymentIntents, PaymentMethods, Refund/Dispute reads, and Webhook Endpoint verification.

Webhook URL:

```text
https://portal.bpwaterheaters.com/api/method/bp_water_heaters.api.booking.stripe_webhook
```

Register events:

- `checkout.session.completed`
- `checkout.session.expired`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `payment_intent.payment_failed`
- `charge.refunded`
- `charge.dispute.created`

## Microsoft Entra

Create:

- A single-tenant web app for ERP Office 365 login.
- A public/native mobile app for the iPhone PKCE flow with redirect URI `bpwhadmin://auth`.
- A separate app/Connected App for Microsoft 365 outbound email as `curtis@bpwaterheaters.com`.

Allowed admins:

- `chase@bluebergconstruction.com`
- `curtis@bpwaterheaters.com`

## Plaid

Plaid is server-side only. Use production credentials in site config, then open the admin Plaid Link flow:

- `bp_water_heaters.api.plaid.create_link_token`
- `bp_water_heaters.api.plaid.exchange_public_token`
- `bp_water_heaters.api.plaid.list_plaid_accounts`
- `bp_water_heaters.api.plaid.map_plaid_account`
- `bp_water_heaters.api.plaid.sync_bank_transactions`

Imported `Bank Transaction` rows are keyed by Plaid `transaction_id` and do not create GL entries.

## TestFlight

Bundle ID:

```text
com.blueberg.bpwaterheaters.admin
```

Before upload:

- Create the App Store Connect app `BP Water Heaters Admin`.
- Add Apple team signing to the Xcode project.
- Confirm Microsoft mobile client ID is set in ERP site config.
