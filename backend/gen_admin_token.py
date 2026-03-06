from app.core.auth import create_access_token, create_refresh_token

token = create_access_token(
    user_id="937be535-66c8-41b1-8d8c-c446034ec73d",
    family_id="__admin__",
    role="admin",
    scope="dashboard",
)
refresh, jti, exp = create_refresh_token(
    user_id="937be535-66c8-41b1-8d8c-c446034ec73d",
    family_id="__admin__",
    role="admin",
)

with open("admin_tokens.txt", "w") as f:
    f.write(f"{token}\n{refresh}\n")
print("Tokens saved to admin_tokens.txt")
