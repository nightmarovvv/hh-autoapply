"""API-клиент hh.ru с Android-маскировкой.

Притворяется официальным Android-приложением hh.ru.
Используется для: whoami, boost резюме, получение списка резюме.
Отклики идут через браузер — API только для сервисных операций.
"""

from __future__ import annotations

import json
import random
import time
import uuid
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode, urljoin

import logging
import warnings
warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*")
import requests

logger = logging.getLogger("hh_apply.api")

# Ключи из APK hh.ru Android
ANDROID_CLIENT_ID = "HIOMIAS39CA9DICTA7JIO64LQKQJF5AGIK74G9ITJKLNEDAOH5FHS5G1JI7FOEGD"
ANDROID_CLIENT_SECRET = "V9M870DE342BGHFRUJ5FTCGCUA1482AN0DI8C5TFI9ULMA89H10N60NOP8I4JMVS"

HH_API_URL = "https://api.hh.ru/"
HH_OAUTH_URL = "https://hh.ru/oauth/"
DEFAULT_DELAY = 0.345  # Минимальная задержка между запросами (антиDDoS)

ANDROID_SCHEME = "hhandroid"


def generate_android_ua() -> str:
    """Генерирует User-Agent как у Android-приложения hh.ru."""
    devices = ["23053RN02A", "23053RN02Y", "23053RN02I", "SM-A556B", "Pixel 8"]
    device = random.choice(devices)
    minor = random.randint(100, 150)
    patch = random.randint(10000, 15000)
    android = random.randint(12, 15)
    return f"ru.hh.android/7.{minor}.{patch}, Device: {device}, Android OS: {android} (UUID: {uuid.uuid4()})"


class HHApiClient:
    """Thread-safe API клиент для hh.ru с Android-маскировкой."""

    def __init__(self, token_path: "str | Path"):
        self.token_path = Path(token_path)
        self.session = requests.Session()
        self.user_agent = generate_android_ua()
        self.access_token = None
        self.refresh_token = None
        self.access_expires_at = 0
        self._lock = Lock()
        self._last_request_time = 0.0
        self._load_token()


    def _load_token(self):
        if self.token_path.exists():
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.access_expires_at = data.get("access_expires_at", 0)

    def _save_token(self):
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        import os as _os
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "access_expires_at": self.access_expires_at,
        }
        self.token_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            _os.chmod(str(self.token_path), 0o600)
        except OSError:
            pass

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.access_expires_at

    @property
    def authorize_url(self) -> str:
        params = {
            "client_id": ANDROID_CLIENT_ID,
            "response_type": "code",
        }
        return f"{HH_OAUTH_URL}authorize?{urlencode(params)}"

    def exchange_code(self, code: str):
        """Обмен authorization code на токены."""
        resp = self.session.post(
            f"{HH_OAUTH_URL}token",
            data={
                "client_id": ANDROID_CLIENT_ID,
                "client_secret": ANDROID_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            },
            headers={"User-Agent": self.user_agent},
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        self.access_expires_at = int(time.time()) + data.get("expires_in", 1209600)
        self._save_token()

    def do_refresh_token(self):
        """Обновляет access_token через refresh_token."""
        if not self.refresh_token:
            raise RuntimeError("Нет refresh_token. Выполните: hh-apply api-login")
        resp = self.session.post(
            f"{HH_OAUTH_URL}token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            headers={"User-Agent": self.user_agent},
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self.access_expires_at = int(time.time()) + data.get("expires_in", 1209600)
        self._save_token()

    def _headers(self) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "X-HH-App-Active": "true",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Thread-safe API запрос с задержкой."""
        url = urljoin(HH_API_URL, endpoint.lstrip("/"))
        with self._lock:
            # Антифлуд задержка
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < DEFAULT_DELAY:
                time.sleep(DEFAULT_DELAY - elapsed)

            resp = self.session.request(
                method, url,
                headers=self._headers(),
                allow_redirects=False,
                **kwargs,
            )
            self._last_request_time = time.monotonic()
            logger.debug("API %s %s → %d", method, endpoint, resp.status_code)

        # Авто-рефреш при 401/403
        if resp.status_code in (401, 403) and self.refresh_token:
            with self._lock:
                self.do_refresh_token()
                logger.info("Token refreshed")
                resp = self.session.request(
                    method, url,
                    headers=self._headers(),
                    allow_redirects=False,
                    **kwargs,
                )
                self._last_request_time = time.monotonic()

        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def get(self, endpoint: str, **kwargs) -> dict:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> dict:
        return self.request("POST", endpoint, **kwargs)

    # === Высокоуровневые методы ===

    def whoami(self) -> dict:
        """GET /me — информация о текущем пользователе."""
        return self.get("/me")

    def get_resumes(self) -> list:
        """GET /resumes/mine — список резюме."""
        data = self.get("/resumes/mine")
        return data.get("items", [])

    def boost_resume(self, resume_id: str) -> bool:
        """POST /resumes/{id}/publish — поднять резюме."""
        self.post(f"/resumes/{resume_id}/publish")
        return True
