import asyncio
import logging

from contextlib import (
    asynccontextmanager,
    suppress,
)

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)


from app.config import (
    settings,
)

from app.core.supabase_client import (
    supabase_admin,
)


from app.api.v1.alerts import (
    router as alerts_router,
)

from app.api.v1.analytics import (
    router as analytics_router,
)

from app.api.v1.audit import (
    router as audit_router,
)

from app.api.v1.auth import (
    router as auth_router,
)

from app.api.v1.cart import (
    router as cart_router,
)

from app.api.v1.chat import (
    router as chat_router,
)

from app.api.v1.feedback import (
    router as feedback_router,
)

from app.api.v1.inventory import (
    router as inventory_router,
)

from app.api.v1.memory import (
    router as memory_router,
)

from app.api.v1.notifications import (
    router as notifications_router,
)

from app.api.v1.orders import (
    router as orders_router,
)

from app.api.v1.pricing import (
    router as pricing_router,
)

from app.api.v1.products import (
    router as products_router,
)

from app.api.v1.purchase import (
    router as purchase_router,
)

from app.api.v1.reservation import (
    router as reservation_router,
)

from app.api.v1.search import (
    router as search_router,
)

from app.api.v1.smart_cart import (
    router as smart_cart_router,
)

from app.api.v1.support import (
    router as support_router,
)

from app.api.v1.wishlist import (
    router as wishlist_router,
)


from app.workers.job_state import (
    get_job_states,
    register_job,
)

from app.workers.notification_worker import (
    notification_loop,
)

from app.workers.scheduler import (
    promotion_scheduler_loop,
    reservation_scheduler_loop,
)

from app.workers.smart_cart_worker import (
    auto_buy_loop,
)


# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)


logger = logging.getLogger(
    __name__
)


# ============================================================================
# Phase 17 worker registration
# ============================================================================

register_job(
    "smart_cart_auto_buy"
)

register_job(
    "notification_delivery"
)

register_job(
    "promotion_activation"
)

register_job(
    "reservation_expiry"
)


# ============================================================================
# Application lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    tasks: list[
        asyncio.Task
    ] = []


    # ------------------------------------------------------------------------
    # Smart Cart worker
    # ------------------------------------------------------------------------

    if (
        settings.smart_cart_worker_enabled
    ):
        tasks.append(
            asyncio.create_task(
                auto_buy_loop(
                    settings
                    .smart_cart_worker_interval_seconds
                ),
                name=(
                    "smart-cart-auto-buy-worker"
                ),
            )
        )


    # ------------------------------------------------------------------------
    # Notification worker
    # ------------------------------------------------------------------------

    if (
        settings.notification_worker_enabled
    ):
        tasks.append(
            asyncio.create_task(
                notification_loop(
                    settings
                    .notification_worker_interval_seconds
                ),
                name=(
                    "notification-delivery-worker"
                ),
            )
        )


    # ------------------------------------------------------------------------
    # Phase 17 scheduled jobs
    # ------------------------------------------------------------------------

    if (
        settings.scheduler_enabled
    ):
        tasks.append(
            asyncio.create_task(
                promotion_scheduler_loop(
                    settings
                    .promotion_activation_interval_seconds
                ),
                name=(
                    "promotion-activation-scheduler"
                ),
            )
        )


        tasks.append(
            asyncio.create_task(
                reservation_scheduler_loop(
                    settings
                    .reservation_expiry_interval_seconds
                ),
                name=(
                    "reservation-expiry-scheduler"
                ),
            )
        )


    logger.info(
        "Retailigent background jobs started: %s",
        [
            task.get_name()
            for task in tasks
        ],
    )


    try:
        yield


    finally:
        logger.info(
            "Stopping Retailigent background jobs"
        )


        for task in tasks:
            task.cancel()


        for task in tasks:
            with suppress(
                asyncio.CancelledError
            ):
                await task


        logger.info(
            "Retailigent background jobs stopped"
        )


# ============================================================================
# FastAPI application
# ============================================================================

app = FastAPI(
    title=(
        "Retailigent API"
    ),
    description=(
        "Backend API for Retailigent"
    ),
    version=(
        "1.0.0"
    ),
    lifespan=lifespan,
)


# ============================================================================
# CORS
# ============================================================================

#
# During development, localhost and 127.0.0.1 are different browser origins.
#
# The frontend may run as:
#
#   http://localhost:3000
#
# while the backend runs as:
#
#   http://127.0.0.1:8000
#
# We explicitly allow both local frontend forms.
#

DEVELOPMENT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "http://localhost:3001",
    "http://127.0.0.1:3001",
]


CONFIGURED_ORIGINS = [
    settings.frontend_url,
    settings.admin_url,
]


allowed_origins = list({
    origin.rstrip("/")
    for origin in (
        DEVELOPMENT_ORIGINS
        +
        CONFIGURED_ORIGINS
    )
    if origin
})


logger.info(
    "Allowed frontend origins: %s",
    sorted(
        allowed_origins
    ),
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=
        allowed_origins,

    allow_credentials=
        True,

    allow_methods=[
        "*",
    ],

    allow_headers=[
        "*",
    ],
)


# ============================================================================
# API routers
# ============================================================================

app.include_router(
    auth_router
)

app.include_router(
    products_router
)

app.include_router(
    inventory_router
)

app.include_router(
    search_router
)

app.include_router(
    pricing_router
)

app.include_router(
    cart_router
)

app.include_router(
    wishlist_router
)

app.include_router(
    reservation_router
)

app.include_router(
    purchase_router
)

app.include_router(
    orders_router
)

app.include_router(
    smart_cart_router
)

app.include_router(
    alerts_router
)

app.include_router(
    notifications_router
)

app.include_router(
    chat_router
)

app.include_router(
    memory_router
)

app.include_router(
    feedback_router
)

app.include_router(
    analytics_router
)

app.include_router(
    support_router
)

app.include_router(
    audit_router
)


# ============================================================================
# Root
# ============================================================================

@app.get("/")
def root():
    return {
        "application":
            "Retailigent",

        "status":
            "running",
    }


# ============================================================================
# Database health
# ============================================================================

@app.get(
    "/health"
)
def health():
    try:
        (
            supabase_admin
            .table(
                "branches"
            )
            .select(
                "id"
            )
            .limit(
                1
            )
            .execute()
        )


        return {
            "status":
                "healthy",

            "api":
                "running",

            "database":
                "connected",
        }


    except Exception as exc:
        logger.exception(
            "Database health check failed"
        )


        raise HTTPException(
            status_code=503,
            detail=(
                "Database connection failed: "
                f"{exc}"
            ),
        ) from exc


# ============================================================================
# Phase 17 worker health
# ============================================================================

@app.get(
    "/health/jobs"
)
def jobs_health():
    expected_intervals = {
        "smart_cart_auto_buy":
            (
                settings
                .smart_cart_worker_interval_seconds
            ),

        "notification_delivery":
            (
                settings
                .notification_worker_interval_seconds
            ),

        "promotion_activation":
            (
                settings
                .promotion_activation_interval_seconds
            ),

        "reservation_expiry":
            (
                settings
                .reservation_expiry_interval_seconds
            ),
    }


    jobs = (
        get_job_states(
            expected_intervals=
                expected_intervals,

            stale_multiplier=
                settings
                .job_health_stale_multiplier,
        )
    )


    enabled = {
        "smart_cart_auto_buy":
            (
                settings
                .smart_cart_worker_enabled
            ),

        "notification_delivery":
            (
                settings
                .notification_worker_enabled
            ),

        "promotion_activation":
            (
                settings
                .scheduler_enabled
            ),

        "reservation_expiry":
            (
                settings
                .scheduler_enabled
            ),
    }


    overall_healthy = (
        True
    )


    for (
        job_name,
        job,
    ) in jobs.items():

        is_enabled = (
            enabled.get(
                job_name,
                False,
            )
        )


        job[
            "enabled"
        ] = is_enabled


        if not is_enabled:
            job[
                "status"
            ] = "disabled"

            continue


        if (
            job[
                "status"
            ]
            in {
                "failing",
                "stale",
            }
        ):
            overall_healthy = (
                False
            )


    return {
        "status":
            (
                "healthy"
                if overall_healthy
                else
                "degraded"
            ),

        "jobs":
            jobs,
    }