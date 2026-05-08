"""
Smoke tests: allauth account URL names resolve and respond without server error.

Key-based routes use placeholder path segments; some return 404 — that is acceptable.
"""

import pytest
from django.test import Client
from django.urls import NoReverseMatch, reverse


def _reverse_or_skip(name, kwargs=None, args=None):
    try:
        if kwargs is not None:
            return reverse(name, kwargs=kwargs)
        if args is not None:
            return reverse(name, args=args)
        return reverse(name)
    except NoReverseMatch:
        pytest.skip(f"URL {name} not configured")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,kw,args",
    [
        ("account_login", None, None),
        ("account_logout", None, None),
        ("account_inactive", None, None),
        ("account_signup", None, None),
        ("account_reauthenticate", None, None),
        ("account_email", None, None),
        ("account_email_verification_sent", None, None),
        ("account_change_password", None, None),
        ("account_set_password", None, None),
        ("account_reset_password", None, None),
        ("account_reset_password_done", None, None),
        ("account_reset_password_from_key_done", None, None),
        ("account_confirm_login_code", None, None),
        # needs key in path (overridden pattern [^/]+)
        ("account_confirm_email", None, ["test-confirm-key"]),
        ("account_reset_password_from_key", None, ["1", "reset-key-token"]),
    ],
)
def test_allauth_get_smoke(name, kw, args):
    from allauth.account import app_settings as aas

    if name == "account_confirm_email" and getattr(
        aas, "EMAIL_VERIFICATION_BY_CODE_ENABLED", False
    ):
        pytest.skip("confirm email link disabled when verification-by-code")

    url = _reverse_or_skip(name, kwargs=kw, args=args)
    c = Client()
    r = c.get(url)
    assert r.status_code in (
        200,
        302,
        301,
        403,
        404,
        405,
    ), f"{name} returned {r.status_code}"
