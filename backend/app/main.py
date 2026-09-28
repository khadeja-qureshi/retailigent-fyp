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

app = FastAPI(
    title="Retailigent API",
    description="Backend API for Retailigent",
    version="1.0.0",
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