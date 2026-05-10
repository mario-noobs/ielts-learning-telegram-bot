"""Firebase Admin SDK init for **Auth-only** use (M8 decommission #234).

Post-cutover the Firestore product is disabled. The only Firebase
service the app still uses is **Identity Platform / Auth** —
``firebase_admin.auth.verify_id_token`` to validate ID tokens minted
by the web client.

This module owns the lazy ``ensure_admin_initialized()`` helper that
boots the Admin SDK *without* touching Firestore. Callers
(``api.auth``, ``api.routes.auth``, anywhere that needs Auth) should
call it before invoking ``firebase_admin.auth.*``.

The legacy ``firebase_service._get_db()`` shim still exists for
backwards compatibility but is a no-op forwarder to this function.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials

import config

logger = logging.getLogger("firebase_auth")

_initialized = False


def _resolve_credential() -> Optional[credentials.Certificate]:
    """Build a ``credentials.Certificate`` from env, or return None.

    Tries the base64-encoded ``FIREBASE_CREDENTIALS_JSON`` first
    (containerized deploys), then the on-disk
    ``FIREBASE_CREDENTIALS_PATH`` (local dev). Returns None when
    neither is set — the caller decides what to do (e.g. allow
    emulator init without real creds).
    """
    json_b64 = getattr(config, "FIREBASE_CREDENTIALS_JSON", None)
    if json_b64:
        cred_dict = json.loads(base64.b64decode(json_b64))
        return credentials.Certificate(cred_dict)
    path = getattr(config, "FIREBASE_CREDENTIALS_PATH", None)
    if path and os.path.exists(path):
        return credentials.Certificate(path)
    return None


def ensure_admin_initialized() -> None:
    """Idempotent boot of the Firebase Admin app for Auth use.

    Safe to call from request handlers — the underlying ``firebase_admin``
    library tracks ``_apps`` internally and we wrap it with our own
    sentinel for the fast path.
    """
    global _initialized
    if _initialized:
        return
    if not firebase_admin._apps:
        cred = _resolve_credential()
        if getattr(config, "USE_FIREBASE_EMULATOR", False):
            opts = {"projectId": config.FIREBASE_EMULATOR_PROJECT_ID}
            if cred is not None:
                firebase_admin.initialize_app(cred, options=opts)
            else:
                firebase_admin.initialize_app(options=opts)
        else:
            if cred is None:
                raise RuntimeError(
                    "Firebase credentials not found. Set "
                    "FIREBASE_CREDENTIALS_JSON (base64) or place a "
                    "service-account JSON at "
                    f"{getattr(config, 'FIREBASE_CREDENTIALS_PATH', '<unset>')!r}.",
                )
            firebase_admin.initialize_app(cred)
    _initialized = True


__all__ = ["ensure_admin_initialized"]
