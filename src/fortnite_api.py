import aiohttp
import os
from datetime import datetime
import asyncio

from src.config import (
    mask_email,
    mask_account_id,
    bool_to_emoji,
    country_to_flag,
    RARITY_PRIORITY,
    SUB_ORDER,
    get_cosmetic_type,
    mythic_ids,
)
from src.epic_auth import EpicUser


async def set_affiliate(session: aiohttp.ClientSession, account_id: str, access_token: str,
                        affiliate_name: str = "Kayysito") -> dict | str:
    async with session.post(
        f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{account_id}/client/SetAffiliateName?profileId=common_core",
        headers={
            "Authorization": f"Bearer {access_token}",
            "content-type": "application/json",
        },
        json={"affiliateName": affiliate_name},
    ) as resp:
        if resp.status != 200:
            return f"Error setting affiliate name ({resp.status})"
        return await resp.json()


async def grab_profile(session: aiohttp.ClientSession, info: dict, profile_id: str = "athena") -> dict | str:
    async with session.post(
        f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{info['account_id']}/client/QueryProfile?profileId={profile_id}",
        headers={
            "Authorization": f"bearer {info['access_token']}",
            "content-type": "application/json",
        },
        json={},
    ) as resp:
        if resp.status != 200:
            return f"Error ({resp.status})"
        return await resp.json()


async def get_account_info(session: aiohttp.ClientSession, user: EpicUser) -> dict:
    async with session.get(
        f"https://account-public-service-prod03.ol.epicgames.com/account/api/public/account/{user.account_id}",
        headers={"Authorization": f"bearer {user.access_token}"},
    ) as resp:
        if resp.status != 200:
            return {"error": f"Error fetching account info ({resp.status})"}

        account_info = await resp.json()
        if "email" in account_info:
            account_info["email"] = mask_email(account_info["email"])

        creation_date = account_info.get("created", "Unknown")
        if creation_date != "Unknown":
            creation_date = datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d/%m/%Y")
        account_info["creation_date"] = creation_date

    external_auths_url = f"https://account-public-service-prod03.ol.epicgames.com/account/api/public/account/{user.account_id}/externalAuths"
    async with session.get(external_auths_url, headers={"Authorization": f"bearer {user.access_token}"}) as ext_resp:
        if ext_resp.status == 200:
            account_info["externalAuths"] = await ext_resp.json()
        else:
            account_info["externalAuths"] = []

    return account_info


async def get_vbucks_info(session: aiohttp.ClientSession, user: EpicUser) -> dict:
    async with session.post(
        f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{user.account_id}/client/QueryProfile?profileId=common_core&rvn=-1",
        headers={"Authorization": f"bearer {user.access_token}", "Content-Type": "application/json"},
        json={},
    ) as resp:
        if resp.status != 200:
            return {"error": f"Error fetching V-Bucks info ({resp.status})"}
        data = await resp.json()

    vbucks_categories = [
        "Currency:MtxPurchased",
        "Currency:MtxEarned",
        "Currency:MtxGiveaway",
        "Currency:MtxPurchaseBonus",
    ]
    total_vbucks = 0
    items_data = data.get("profileChanges", [{}])[0].get("profile", {}).get("items", {})
    for item_data in items_data.values():
        if item_data.get("templateId") in vbucks_categories:
            total_vbucks += item_data.get("quantity", 0)

    return {"totalAmount": total_vbucks}


async def get_profile_info(session: aiohttp.ClientSession, user: EpicUser) -> dict:
    async with session.post(
        f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{user.account_id}/client/QueryProfile?profileId=common_core&rvn=-1",
        headers={"Authorization": f"bearer {user.access_token}"},
        json={},
    ) as resp:
        if resp.status != 200:
            return {"error": f"Error fetching profile info ({resp.status})"}
        profile_info = await resp.json()

    creation_date = profile_info.get("profileChanges", [{}])[0].get("profile", {}).get("created", "Unknown")
    if creation_date != "Unknown":
        creation_date = datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d/%m/%Y")
    profile_info["creation_date"] = creation_date

    external_auths_url = f"https://account-public-service-prod03.ol.epicgames.com/account/api/public/account/{user.account_id}/externalAuths"
    async with session.get(external_auths_url, headers={"Authorization": f"bearer {user.access_token}"}) as external_resp:
        if external_resp.status == 200:
            profile_info["externalAuths"] = await external_resp.json()
        else:
            profile_info["externalAuths"] = []

    return profile_info


async def get_account_stats(session: aiohttp.ClientSession, user: EpicUser) -> dict:
    async with session.post(
        f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{user.account_id}/client/QueryProfile?profileId=athena&rvn=-1",
        headers={"Authorization": f"bearer {user.access_token}", "Content-Type": "application/json"},
        json={},
    ) as resp:
        if resp.status != 200:
            return {"error": f"Error fetching account stats ({resp.status})"}

        data = await resp.json()

    attributes = data.get("profileChanges", [{}])[0].get("profile", {}).get("stats", {}).get("attributes", {})
    account_level = attributes.get("accountLevel", 0)
    past_seasons = attributes.get("past_seasons", [])

    total_wins = sum(season.get("numWins", 0) for season in past_seasons)
    total_matches = sum(
        season.get("numHighBracket", 0) + season.get("numLowBracket", 0)
        for season in past_seasons
    )

    try:
        last_login_raw = attributes.get("last_match_end_datetime", "N/A")
        if last_login_raw != "N/A":
            last_played_date = datetime.strptime(last_login_raw, "%Y-%m-%dT%H:%M:%S.%fZ")
            last_played_str = last_played_date.strftime("%d/%m/%y")
            days_since_last_played = (datetime.utcnow() - last_played_date).days
            last_played_info = f"{last_played_str} ({days_since_last_played} days ago)"
        else:
            last_played_info = "N/A"
    except Exception:
        last_played_info = "N/A"

    seasons_info = []
    for season in past_seasons:
        season_info = (
            f"Season {season.get('seasonNumber', 'Unknown')}\n"
            f"  • Level: {season.get('seasonLevel', 'Unknown')}\n"
            f"  • Battle Pass purchased: {bool_to_emoji(season.get('purchasedVIP', False))}\n"
            f"  • Wins: {season.get('numWins', 0)}\n"
        )
        seasons_info.append(season_info)

    return {
        "account_level": account_level,
        "total_wins": total_wins,
        "total_matches": total_matches,
        "last_played_info": last_played_info,
        "seasons_info": seasons_info,
    }


async def get_banners_from_common_core(session: aiohttp.ClientSession, user: EpicUser) -> list[str]:
    url = f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{user.account_id}/client/QueryProfile?profileId=common_core&rvn=-1"
    async with session.post(
        url,
        headers={"Authorization": f"bearer {user.access_token}"},
        json={},
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()

    items = data.get("profileChanges", [{}])[0].get("profile", {}).get("items", {})
    result = []
    for _, info_item in items.items():
        template_id = info_item.get("templateId", "").lower()
        if template_id.startswith("homebasebanner:") or template_id.startswith("homebasebannericon:"):
            splitted = template_id.split(":")
            if len(splitted) == 2:
                banner_id = splitted[1]
                result.append(banner_id)
    return result


async def download_and_prepare_banners(session: aiohttp.ClientSession, user: EpicUser) -> list[str]:
    from src.config import CACHE_DIR, banner_name_map
    banner_ids_in_profile = await get_banners_from_common_core(session, user)
    if not banner_ids_in_profile:
        return []

    async with session.get("https://fortnite-api.com/v1/banners") as resp:
        if resp.status != 200:
            all_data = {}
        else:
            full_data = await resp.json()
            all_data = {b["id"].lower(): b for b in full_data.get("data", [])}

    os.makedirs(CACHE_DIR, exist_ok=True)

    final_ids = []
    for bn in banner_ids_in_profile:
        cid = f"banner_{bn.lower()}"
        path_img = os.path.join(CACHE_DIR, f"{cid}.png")
        info = all_data.get(bn.lower())
        if not info:
            continue

        banner_name = info.get("devName", f"Banner {cid}")
        banner_name_map[cid] = banner_name

        icon_url = info.get("images", {}).get("icon")
        if not icon_url:
            continue

        if os.path.exists(path_img) and os.path.getsize(path_img) > 0:
            final_ids.append(cid)
            continue

        async with session.get(icon_url) as r2:
            if r2.status == 200:
                content = await r2.read()
                with open(path_img, "wb") as f:
                    f.write(content)
                final_ids.append(cid)

    return final_ids


async def get_cosmetic_info(cosmetic_id: str, session: aiohttp.ClientSession) -> dict:
    from src.config import banner_name_map

    cid_lower = cosmetic_id.lower()
    if cid_lower.startswith("banner_"):
        if cid_lower in banner_name_map:
            real_name = banner_name_map[cid_lower]
        else:
            real_name = f"Banner {cosmetic_id}"

        rarity = "Mythic" if cid_lower in [m.lower() for m in mythic_ids] else "Uncommon"
        return {"id": cosmetic_id, "rarity": rarity, "name": real_name}

    url = f"https://fortnite-api.com/v2/cosmetics/br/{cosmetic_id}"
    async with session.get(url) as resp:
        if resp.status != 200:
            return {"id": cosmetic_id, "rarity": "Common", "name": "Unknown"}
        data = await resp.json()

    rarity = data.get("data", {}).get("rarity", {}).get("displayValue", "Common")
    name = data.get("data", {}).get("name", "Unknown")

    if cid_lower in [m.lower() for m in mythic_ids]:
        rarity = "Mythic"

    if name == "Unknown":
        name = cosmetic_id
    return {"id": cosmetic_id, "rarity": rarity, "name": name}


async def download_cosmetic_images(ids: list[str], session: aiohttp.ClientSession):
    import os
    from src.config import CACHE_DIR, PLACEHOLDER_IMAGE

    os.makedirs(CACHE_DIR, exist_ok=True)

    async def _download(cid: str):
        cid_lower = cid.lower()
        if cid_lower.startswith("banner_"):
            return  # already handled as banner icon

        img_path = os.path.join(CACHE_DIR, f"{cid}.png")
        if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
            return

        urls = [
            f"https://fortnite-api.com/images/cosmetics/br/{cid}/icon.png",
            f"https://fortnite-api.com/images/cosmetics/br/{cid}/smallicon.png",
        ]
        for url in urls:
            async with session.get(url) as r2:
                if r2.status == 200:
                    content = await r2.read()
                    with open(img_path, "wb") as f:
                        f.write(content)
                    return

        with open(img_path, "wb") as f_dst, open(PLACEHOLDER_IMAGE, "rb") as f_src:
            f_dst.write(f_src.read())

    await asyncio.gather(*[_download(i) for i in ids])


async def sort_ids_by_rarity(ids: list[str], session: aiohttp.ClientSession, item_order: list[str]) -> list[str]:
    info_list = await asyncio.gather(*[get_cosmetic_info(i, session) for i in ids])

    def get_sort_key(info: dict):
        rarity = info.get("rarity", "Common")
        cid = info.get("id", "")
        ctype = get_cosmetic_type(cid)
        item_order_rank = item_order.index(ctype) if ctype in item_order else len(item_order)
        rarity_rank = RARITY_PRIORITY.get(rarity, 999)
        sub_rank = SUB_ORDER.get(cid.lower(), 9999)
        return (item_order_rank, rarity_rank, sub_rank)

    sorted_info = sorted(info_list, key=get_sort_key)
    return [x["id"] for x in sorted_info]
