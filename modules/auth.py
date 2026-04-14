"""
auth.py — Authentication for BioSafe Primer
Handles: email/password login, Google OAuth 2.0, session management.

Secrets required in .streamlit/secrets.toml:
    [google]
    client_id     = "..."
    client_secret = "..."
    redirect_uri  = "https://your-app.streamlit.app/"
"""

import os
import secrets
import bcrypt
import requests as http
import streamlit as st
from urllib.parse import urlencode

from modules.database import get_user_by_email, create_user, get_user_by_id

# ── Admin ─────────────────────────────────────────────────────────────────────
# Replace with your institutional email before deployment.
ADMIN_EMAIL = "crisprramesh@gmail.com"

# ── Google OAuth endpoints ─────────────────────────────────────────────────────
_GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── Secret loader (Streamlit Cloud secrets or env vars) ───────────────────────
def _secret(section: str, key: str, fallback: str = "") -> str:
    """Read from st.secrets first, fall back to environment variable."""
    try:
        return st.secrets[section][key]
    except Exception:
        return os.environ.get(f"{section.upper()}_{key.upper()}", fallback)


def _google_client_id()     -> str: return _secret("google", "client_id")
def _google_client_secret() -> str: return _secret("google", "client_secret")
def _google_redirect_uri()  -> str: return _secret("google", "redirect_uri",
                                                     "http://localhost:8501")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return True if password matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Google OAuth ──────────────────────────────────────────────────────────────

def google_is_configured() -> bool:
    """Return True only if Google OAuth credentials are present."""
    return bool(_google_client_id() and _google_client_secret())


def get_google_auth_url() -> str:
    """
    Build and return the Google OAuth 2.0 authorisation URL.
    A fresh CSRF state token is stored in session_state on every call.
    """
    state = secrets.token_urlsafe(16)
    st.session_state["oauth_state"] = state
    params = {
        "client_id":     _google_client_id(),
        "redirect_uri":  _google_redirect_uri(),
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",   # always show account picker
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def handle_google_callback(code: str) -> dict | None:
    """
    Exchange the authorisation code for an access token, then fetch
    the Google userinfo. Returns a dict with 'email', 'name', etc.,
    or None on any failure.
    """
    try:
        # Step 1 — exchange code for token
        token_resp = http.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     _google_client_id(),
            "client_secret": _google_client_secret(),
            "redirect_uri":  _google_redirect_uri(),
            "grant_type":    "authorization_code",
        }, timeout=10)
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            return None

        # Step 2 — fetch user profile
        info_resp = http.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        info_resp.raise_for_status()
        return info_resp.json()

    except Exception:
        return None


def login_with_google(userinfo: dict) -> dict | None:
    """
    Given Google userinfo, find or create a local account, and return
    the user record. Returns None if email is missing.
    """
    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        return None

    name = userinfo.get("name") or email.split("@")[0]
    user = get_user_by_email(email)

    if not user:
        # First-time Google sign-in → auto-create account
        uid  = create_user(name, email, password_hash=None, auth_provider="google")
        user = get_user_by_id(uid)

    return user


# ── Email / password auth ─────────────────────────────────────────────────────

def login_with_password(email: str, password: str) -> dict | None:
    """
    Validate email + password. Returns user record on success, None otherwise.
    Also returns None for Google-only accounts so the caller can show
    a meaningful error.
    """
    user = get_user_by_email(email.strip().lower())
    if not user:
        return None
    if user.get("auth_provider") == "google":
        # Signal that this account exists but is Google-only
        return "google_account"
    if not verify_password(password, user.get("password_hash") or ""):
        return None
    return user


def register_with_password(name: str, email: str,
                             password: str) -> tuple:
    """
    Register a new email/password account.
    Returns (user_dict, error_string). On success error_string is "".
    """
    email = email.strip().lower()

    if get_user_by_email(email):
        return None, "This email is already registered. Please sign in instead."
    if len(password) < 8:
        return None, "Password must be at least 8 characters long."

    uid  = create_user(name.strip(), email, hash_password(password), "email")
    user = get_user_by_id(uid)
    return user, ""


# ── Session helpers ───────────────────────────────────────────────────────────

def set_session_user(user: dict) -> None:
    """Store authenticated user in Streamlit session state."""
    st.session_state["auth_user"] = user
    st.session_state["user_id"]   = user["id"]
    st.session_state["is_admin"]  = (user.get("email", "").lower() ==
                                      ADMIN_EMAIL.lower())


def get_session_user() -> dict | None:
    """Return the currently authenticated user dict, or None."""
    return st.session_state.get("auth_user")


def logout() -> None:
    """Clear all auth and app state from session."""
    keys_to_clear = [
        "auth_user", "user_id", "is_admin",
        "project_id", "seq_info", "primers",
        "oauth_state",
    ]
    for k in keys_to_clear:
        st.session_state.pop(k, None)

    # Clear any transient redesign preview keys
    stale = [k for k in st.session_state
             if k.startswith(("redesign_preview_", "confirm_del_"))]
    for k in stale:
        st.session_state.pop(k, None)
