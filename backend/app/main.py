from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.supabase_client import supabase_admin
from app.api.v1.auth import router as auth_router
from app.api.v1.products import router as products_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.search import router as search_router
from app.api.v1.pricing import router as pricing_router
from app.api.v1.cart import router as cart_router
from app.api.v1.wishlist import router as wishlist_router
from app.api.v1.reservation import (
    router as reservation_router,
)
from app.api.v1.purchase import router as purchase_router
from app.api.v1.orders import router as orders_router
from app.api.v1.smart_cart import (
    router as smart_cart_router,
)

from app.api.v1.alerts import (
    router as alerts_router,
)
from app.api.v1.notifications import (
    router as notifications_router,
)



import asyncio

from contextlib import (
    asynccontextmanager,
    suppress,
)

from app.workers.smart_cart_worker import (
    auto_buy_loop,
)
from app.workers.notification_worker import (
    notification_loop,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []

    if settings.smart_cart_worker_enabled:
        tasks.append(
            asyncio.create_task(
                auto_buy_loop(
                    settings
                    .smart_cart_worker_interval_seconds
                )
            )
        )

    if settings.notification_worker_enabled:
        tasks.append(
            asyncio.create_task(
                notification_loop(
                    settings
                    .notification_worker_interval_seconds
                )
            )
        )

    try:
        yield

    finally:
        for task in tasks:
            task.cancel()

        for task in tasks:
            with suppress(
                asyncio.CancelledError
            ):
                await task

app = FastAPI(
    title="Retailigent API",
    description="Backend API for Retailigent",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        settings.admin_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(products_router)
app.include_router(inventory_router)
app.include_router(search_router)
app.include_router(pricing_router)
app.include_router(cart_router)
app.include_router(wishlist_router)
app.include_router(reservation_router)
app.include_router(purchase_router)
app.include_router(orders_router)
app.include_router(
    smart_cart_router
)

app.include_router(
    alerts_router
)

app.include_router(
    notifications_router
)

@app.get("/")
def root():
    return {
        "application": "Retailigent",
        "status": "running",
    }


@app.get("/health")
def health():
    try:
        response = (
            supabase_admin
            .table("branches")
            .select("id")
            .limit(1)
            .execute()
        )

        return {
            "status": "healthy",
            "api": "running",
            "database": "connected",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(exc)}",
        )