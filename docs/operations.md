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