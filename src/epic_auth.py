import os
import platform
import aiohttp
import asyncio
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

SWITCH_TOKEN = os.getenv("SWITCH_TOKEN")
IOS_TOKEN = os.getenv("IOS_TOKEN")

@dataclass
class EpicUser:
    raw: dict
    access_token: str
    expires_in: int
    expires_at: str
    token_type: str
    refresh_token: str
    refresh_expires: int
    refresh_expires_at: str
    account_id: str
    client_id: str
    internal_client: bool
    client_service: str
    display_name: str
    app: str
    in_app_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "EpicUser":
        return cls(
            raw=data,
            access_token=data.get("access_token", ""),
            expires_in=data.get("expires_in", 0),
            expires_at=data.get("expires_at", ""),
            token_type=data.get("token_type", ""),
            refresh_token=data.get("refresh_token", ""),
            refresh_expires=data.get("refresh_expires", 0),
            refresh_expires_at=data.get("refresh_expires_at", ""),
            account_id=data.get("account_id", ""),
            client_id=data.get("client_id", ""),
            internal_client=data.get("internal_client", False),
            client_service=data.get("client_service", ""),
            display_name=data.get("displayName", ""),
            app=data.get("app", ""),
            in_app_id=data.get("in_app_id", ""),
        )


class EpicGenerator:
    def __init__(self) -> None:
        self.http: aiohttp.ClientSession | None = None
        self.user_agent = f"DeviceAuthGenerator/{platform.system()}/{platform.version()}"
        self.access_token = ""

    async def start(self) -> None:
        self.http = aiohttp.ClientSession(headers={"User-Agent": self.user_agent})
        self.access_token = await self.get_access_token()

    async def close(self) -> None:
        if self.http and not self.http.closed:
            await self.http.close()

    async def get_access_token(self) -> str:
        assert self.http is not None
        async with self.http.post(
            "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"basic {SWITCH_TOKEN}",
            },
            data={"grant_type": "client_credentials"},
        ) as response:
            data = await response.json()
            return data["access_token"]

    async def create_device_code(self) -> tuple[str, str]:
        assert self.http is not None
        async with self.http.post(
            "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/deviceAuthorization",
            headers={
                "Authorization": f"bearer {self.access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ) as response:
            data = await response.json()
            return data["verification_uri_complete"], data["device_code"]

    async def wait_for_device_code_completion(self, code: str) -> EpicUser:
        assert self.http is not None
        print("[DEBUG] Polling Epic Games for token...")
        while True:
            async with self.http.post(
                "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token",
                headers={
                    "Authorization": f"basic {SWITCH_TOKEN}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "device_code", "device_code": code},
            ) as request:
                token = await request.json()
                if request.status == 200:
                    print("[DEBUG] Token received successfully.")
                    break
            await asyncio.sleep(5)

        print("[DEBUG] Exchanging token...")
        async with self.http.get(
            "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/exchange",
            headers={"Authorization": f"bearer {token['access_token']}"},
        ) as request:
            exchange = await request.json()

        print("[DEBUG] Getting final auth information...")
        async with self.http.post(
            "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token",
            headers={
                "Authorization": f"basic {IOS_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "exchange_code", "exchange_code": exchange["code"]},
        ) as request:
            auth_information = await request.json()
            return EpicUser.from_dict(auth_information)

    async def create_exchange_code(self, user: EpicUser) -> str:
        assert self.http is not None
        async with self.http.get(
            "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/exchange",
            headers={"Authorization": f"bearer {user.access_token}"},
        ) as response:
            data = await response.json()
            return data["code"]
