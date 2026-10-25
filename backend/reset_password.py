from app.core.supabase_client import supabase_admin

USER_ID = "b49f08ed-da1b-457b-90ea-d8f5baae0a10"
NEW_PASSWORD = "12345678"

response = supabase_admin.auth.admin.update_user_by_id(
    USER_ID,
    {
        "password": NEW_PASSWORD,
    },
)

print("Password changed successfully")
print(response.user.email if response.user else USER_ID)