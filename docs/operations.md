# Retailigent Operations Guide

## Scope

This document describes the background jobs finalized in Phase 17 and the operational checks required to run Retailigent safely.

## Background jobs

Retailigent starts background jobs from the FastAPI lifespan in `backend/app/main.py`.

| Job | Purpose | Default interval |
| --- | --- | --- |
| `smart_cart_auto_buy` | Process triggered auto-buy Smart Cart rules | 10 seconds recommended in development |
| `notification_delivery` | Deliver queued in-app/email notifications | 10 seconds recommended in development |
| `promotion_activation` | Call `activate_due_promotions()` | 60 seconds |
| `reservation_expiry` | Call `release_expired_reservations()` | 30 seconds |

The PostgreSQL layer remains authoritative for inventory, reservations, prices, promotions and notification queue state.

## Environment

Recommended development settings:

```env
SCHEDULER_ENABLED=true
PROMOTION_ACTIVATION_INTERVAL_SECONDS=60
RESERVATION_EXPIRY_INTERVAL_SECONDS=30
JOB_HEALTH_STALE_MULTIPLIER=3

SMART_CART_WORKER_ENABLED=true
SMART_CART_WORKER_INTERVAL_SECONDS=10

NOTIFICATION_WORKER_ENABLED=true
NOTIFICATION_WORKER_INTERVAL_SECONDS=10
NOTIFICATION_BATCH_SIZE=20
NOTIFICATION_MAX_ATTEMPTS=5
NOTIFICATION_BACKOFF_SECONDS=30
NOTIFICATION_STALE_PROCESSING_SECONDS=300

## Health monitoring

Check the job health endpoint on the running backend:

```http
GET /health/jobs
```

The response includes an overall status and a jobs object containing the state of each background job. Each job reports whether it is enabled, its current status, and execution information.

- **healthy**: enabled jobs are operating within their expected health intervals.

- **degraded**: at least one enabled job is failing or stale.

- **disabled**: the job is intentionally disabled by its configuration. Disabled jobs do not make the overall health status degraded.

The endpoint reports process-local job state. Check the backend logs and database state when investigating an incident; a healthy response alone does not prove that every queued notification has reached its recipient.

## Notification delivery and retries

The notification worker claims queued deliveries and processes them independently. Successful deliveries are marked as sent. Failed attempts are retried according to the configured backoff and maximum-attempt settings.

When the maximum number of attempts is exhausted, the worker marks the delivery as dead_letter. Review the delivery's error message and investigate the underlying provider, configuration, or recipient problem before deciding whether to retry it.

Email delivery respects customer notification preferences. Do not bypass a customer's email opt-in preference while troubleshooting.

The dead-letter transition is performed through a database function restricted to service_role. Do not grant that function to anon or authenticated, and do not modify notification delivery records directly from the frontend.

## Troubleshooting checklist

Request GET /health/jobs and inspect the affected job's status, enabled, and last error information.

Check backend logs for worker startup, repeated exceptions, and shutdown messages.

Confirm the relevant worker is enabled and its interval and retry settings are appropriate.

For notification failures, inspect delivery status, attempt count, and error message using an authorized backend or database administration path.

For reservation expiry or promotion activation, verify the database state and relevant service/RPC logs. Database operations remain authoritative.

If a worker is stale or repeatedly failing, investigate the cause before restarting the backend. Restarting resets in-memory job-health history.

## Shutdown

FastAPI's lifespan cancels background tasks during application shutdown and waits for their cancellation. Allow the process to shut down cleanly so worker tasks can stop without being abruptly terminated.
