import os

from fastapi_plugin import Auth0FastAPI

# Read with os.environ[...] so a backend without Auth0 settings refuses to
# start instead of serving the admin routes unprotected.
_auth0 = Auth0FastAPI(
    domain=os.environ["AUTH0_DOMAIN"],
    audience=os.environ["AUTH0_AUDIENCE"],
    # The admin frontend only sends Bearer tokens.
    dpop_enabled=False,
)

# The single place that decides who may call the admin API: a request needs a
# valid Auth0 access token issued by our tenant for our API. This is separate
# from the chat's identity gate and never touches a ChatSession.
require_admin = _auth0.require_auth()
