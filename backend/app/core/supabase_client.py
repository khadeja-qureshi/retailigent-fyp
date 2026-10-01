import httpx
from supabase import Client, ClientOptions, create_client

from app.config import settings


httpx_client = httpx.Client(
    http2=False,
)

supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_secret_key,
    options=ClientOptions(
        httpx_client=httpx_client,
    ),
)