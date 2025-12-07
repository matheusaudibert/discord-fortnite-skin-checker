import os
import asyncio
import discord
import aiohttp
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv
from src.epic_auth import EpicGenerator, EpicUser

from src.fortnite_api import (
    get_account_info,
    get_vbucks_info,
    get_profile_info,
    get_account_stats,
    grab_profile,
    download_and_prepare_banners,
    sort_ids_by_rarity,
)
from src.config import (
    mask_account_id,
    bool_to_emoji,
    country_to_flag,
    ID_PATTERN,
    get_cosmetic_type,
)
from src.image_utils import create_checker_image

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
EMBED_COLOR = discord.Colour(int(os.getenv("EMBED_COLOR", "0x531925"), 16))
BOT_NAME = os.getenv("BOT_NAME", "Fortnite Checker")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

USER_CACHE = {}

BTN_INFO = "btn_account_info"
BTN_SKINS = "btn_skins"
BTN_PICKAXES = "btn_pickaxes"
BTN_BACKBLINGS = "btn_backblings"
BTN_GLIDERS = "btn_gliders"
BTN_EMOTES = "btn_emotes"
BTN_BANNERS = "btn_banners"
BTN_ALL = "btn_all_cosmetics"
BTN_EXIT = "btn_exit_session"

CATEGORY_MAP = {
    BTN_SKINS: "Skins",
    BTN_PICKAXES: "Pickaxes",
    BTN_BACKBLINGS: "Back Blings",
    BTN_GLIDERS: "Gliders",
    BTN_EMOTES: "Emotes",
    BTN_BANNERS: "Banners",
    BTN_ALL: "All Cosmetics"
}

class MainMenu(discord.ui.LayoutView):    
    container1 = discord.ui.Container(
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                media="https://pbs.twimg.com/media/GMuuzoJaMAIsBbk?format=jpg&name=4096x4096",
            ),
        ),
        discord.ui.TextDisplay(content=f"# Welcome to {BOT_NAME}"),
        discord.ui.TextDisplay(content="A fast and reliable Fortnite account checker for Discord."),
        discord.ui.TextDisplay(content="### What This Bot Does:\n- Check Fortnite accounts instantly\n- View skins, emotes, pickaxes, gliders & more\n- Auto-detect rarity, sets and exclusives\n- Clean locker previews with images\n- No data stored"),
        discord.ui.TextDisplay(content="-# Need help? Join our Support Server: https://discord.gg/YOURSERVER"),
        accent_colour=EMBED_COLOR,
    )
    
    action_row1 = discord.ui.ActionRow(
            discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Connect account",
                custom_id="fd57fbb23dcc4db1ffa4e3db7580d965",
            ),
            discord.ui.Button(
                url="https://github.com/matheusaudibert/discord-fortnite-skin-checker",
                style=discord.ButtonStyle.link,
                label="Github repository",
            ),
    )

def create_panel_view(username: str, content_type: str, text_content: str = None, image_filename: str = None):    
    is_info = content_type == "info"
    
    if is_info:
        container_items = [
            discord.ui.TextDisplay(content=f"# <:menu:1446733907847544964> {username}'s panel"),
            discord.ui.TextDisplay(content="Use the selection menu below to access your account information."),
            discord.ui.TextDisplay(content="## Account informations"),
            discord.ui.TextDisplay(content=text_content)
        ]
    else:
        container_items = [
            discord.ui.TextDisplay(content=f"# <:menu:1446733907847544964> {username}'s panel"),
            discord.ui.TextDisplay(content="Use the selection menu below to access your account information."),
            discord.ui.TextDisplay(content=f"## {content_type} gallery"),
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=f"attachment://{image_filename}",
                ),
            )
        ]

    class PanelView(discord.ui.LayoutView):
        container1 = discord.ui.Container(*container_items, accent_colour=EMBED_COLOR)
        
        action_row1 = discord.ui.ActionRow(
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Account informations", disabled=is_info, custom_id=BTN_INFO),
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Skins", disabled=(content_type == "Skins"), custom_id=BTN_SKINS),
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Pickaxes", disabled=(content_type == "Pickaxes"), custom_id=BTN_PICKAXES),
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Back Blings", disabled=(content_type == "Back Blings"), custom_id=BTN_BACKBLINGS),
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Gliders", disabled=(content_type == "Gliders"), custom_id=BTN_GLIDERS),
        )
        
        action_row2 = discord.ui.ActionRow(
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Emotes", disabled=(content_type == "Emotes"), custom_id=BTN_EMOTES),
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="Banners", disabled=(content_type == "Banners"), custom_id=BTN_BANNERS),
            discord.ui.Button(style=discord.ButtonStyle.secondary, label="All cosmetics", disabled=(content_type == "All Cosmetics"), custom_id=BTN_ALL),
            discord.ui.Button(style=discord.ButtonStyle.danger, label="Exit", custom_id=BTN_EXIT),
        )
    
    return PanelView()

async def fetch_user_data(user: EpicUser):
    print(f"[DEBUG] Fetching user data for {user.display_name}...")
    async with aiohttp.ClientSession() as session:
        account_info = await get_account_info(session, user)
        if "error" in account_info:
            print(f"[DEBUG] Error fetching account info: {account_info['error']}")
            return None, account_info["error"]

        print("[DEBUG] Account info fetched.")
        vbucks_info = await get_vbucks_info(session, user)
        stats = await get_account_stats(session, user)
        
        profile_info = await get_profile_info(session, user)
        creation_date = profile_info.get("creation_date", account_info.get("creation_date", "Unknown"))
        
        ext_auths = account_info.get("externalAuths", [])
        psn_txt = "N/A"
        xbox_txt = "N/A"
        
        for auth in ext_auths:
            atype = auth.get("type", "").lower()
            name = auth.get("externalDisplayName", "Unknown")
            date = auth.get("dateAdded", "Unknown")
            if date != "Unknown":
                try:
                    dt = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    date = dt.strftime("%d/%m/%Y")
                except: pass
            
            if atype == "psn":
                psn_txt = f"{name} ({date})"
            elif atype == "xbl":
                xbox_txt = f"{name} ({date})"

        info_str = (
            f"- <:id:1446748683415715892> **Account ID**: {mask_account_id(user.account_id)}\n"
            f"- <:mail:1446748626867982376> **Email**: {account_info.get('email', 'Unknown')}\n"
            f"- <:emoji:1446751218553720962> **Username**: {user.display_name}\n"
            f"- <:popout:1446751906465710090> **Verified email**: {bool_to_emoji(account_info.get('emailVerified', False))}\n"
            f"- <:private:1446748531674185803> **2FA**: {bool_to_emoji(account_info.get('tfaEnabled', False))}\n"
            f"- <:parental_control:1446748409120821258> **Parental control**: {bool_to_emoji(account_info.get('minorVerified', False))}\n"
            f"- <:member:1446748467434360862> **Name**: {account_info.get('name', 'Unknown')}\n"
            f"- <:location:1446748563903221811> **Country**: {account_info.get('country', 'Unknown')} {country_to_flag(account_info.get('country', ''))}\n"
            f"- <:shop:1446750337125056582> **V-Bucks**: {vbucks_info.get('totalAmount', 0)}\n"
            f"- <:date:1446748494470709429> **Creation date**: {creation_date}\n"
            f"- <:game:1446748596895613070> **Playstation**: {psn_txt}\n"
            f"- <:game:1446748596895613070> **Xbox**: {xbox_txt}\n"
            f"- <:help:1446751192414945280> **Account level**: {stats.get('account_level', 0)}\n"
            f"- <:trophy:1446748325851300002> **Total Wins**: {stats.get('total_wins', 0)}\n"
            f"- <:time:1446748659407654942> **Last match played**: {stats.get('last_played_info', 'N/A')}"
        )

        athena_profile = await grab_profile(session, {"account_id": user.account_id, "access_token": user.access_token}, "athena")
        if isinstance(athena_profile, str):
            print(f"[DEBUG] Error fetching athena profile: {athena_profile}")
            return None, "Error fetching profile"

        print("[DEBUG] Athena profile fetched. Parsing items...")
        items = {}
        for item_data in athena_profile["profileChanges"][0]["profile"]["items"].values():
            tid = item_data.get("templateId", "").lower()
            if "loadingscreen_character_lineup" in tid:
                continue
            if ID_PATTERN.match(tid):
                cosmetic_id = tid.split(":")[1]
                ctype = get_cosmetic_type(tid)
                items.setdefault(ctype, []).append(cosmetic_id)

        banner_ids = await download_and_prepare_banners(session, user)
        if banner_ids:
            items.setdefault("Banners", []).extend(banner_ids)
            
        print(f"[DEBUG] Data fetch complete. Found {sum(len(v) for v in items.values())} items.")
        return {
            "info_str": info_str,
            "items": items,
            "username": user.display_name,
            "epic_user": user,
            "image_paths": {} 
        }, None

async def pre_generate_category(user_id: int, category: str):
    if user_id not in USER_CACHE:
        return
    
    data = USER_CACHE[user_id]
    if category in data["image_paths"]:
        return

    ids_to_show = []
    if category == "All Cosmetics":
        order = ["Skins", "Back Blings", "Pickaxes", "Emotes", "Gliders", "Banners"]
        for grp in order:
            ids_to_show.extend(data["items"].get(grp, []))
    else:
        ids_to_show = data["items"].get(category, [])
    
    if not ids_to_show:
        return

    try:
        async with aiohttp.ClientSession() as session:
            order = ["Skins", "Back Blings", "Pickaxes", "Emotes", "Gliders", "Banners"]
            sorted_ids = await sort_ids_by_rarity(ids_to_show, session, item_order=order)
            
            output_dir = "output"
            path = await create_checker_image(
                sorted_ids,
                session,
                username=data["username"],
                group_name=category,
                output_dir=output_dir,
                footer_text=category
            )
            if path:
                data["image_paths"][category] = path
                print(f"[DEBUG] Pre-generated {category} image at {path}")
    except Exception as e:
        print(f"Failed to generate {category}: {e}")

async def wait_for_login(interaction: discord.Interaction, generator: EpicGenerator, device_code: str, message: discord.WebhookMessage):
    try:
        print(f"[DEBUG] Waiting for device code completion: {device_code}")
        user = await generator.wait_for_device_code_completion(device_code)
        print(f"[DEBUG] User logged in: {user.display_name} ({user.account_id})")
        
        data, error = await fetch_user_data(user)
        if error:
            print(f"[DEBUG] Error in fetch_user_data: {error}")
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        print("[DEBUG] Storing user data in cache and updating view.")
        USER_CACHE[interaction.user.id] = data
        
        view = create_panel_view(user.display_name, "info", text_content=data["info_str"])
        await message.edit(view=view)
        print("[DEBUG] View updated.")

        asyncio.create_task(pre_generate_category(interaction.user.id, "Skins"))
        
    except Exception as e:
        print(f"[DEBUG] Exception in wait_for_login: {e}")
        await interaction.followup.send(f"❌ Login failed or timed out: {e}", ephemeral=True)
    finally:
        await generator.close()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        try:
            await channel.purge(limit=None)
        except Exception as e:
            print(f"Error purging channel: {e}")
            
        await channel.send(view=MainMenu())
    else:
        print(f"Channel with ID {CHANNEL_ID} not found.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        print(f"[DEBUG] Interaction received: {custom_id} from {interaction.user}")
        user_id = interaction.user.id
        
        if custom_id == "fd57fbb23dcc4db1ffa4e3db7580d965":
            print("[DEBUG] Starting login flow...")
            await interaction.response.defer(ephemeral=True)
            generator = EpicGenerator()
            await generator.start()
            try:
                verification_url, device_code = await generator.create_device_code()
                print(f"[DEBUG] Device code created: {device_code}")
                
                class VerificationMenu(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="# <a:prints:1446916170069315676> Waiting for verification"),
                        discord.ui.TextDisplay(content="Click the button below to connect to your Fortnite account."),
                        accent_colour=EMBED_COLOR,
                    )
                    action_row1 = discord.ui.ActionRow(
                        discord.ui.Button(url=verification_url, style=discord.ButtonStyle.link, label="Epic Game login"),
                    )

                view = VerificationMenu()
                message = await interaction.followup.send(view=view, ephemeral=True)
                asyncio.create_task(wait_for_login(interaction, generator, device_code, message))
            except Exception as e:
                await interaction.followup.send(f"Error initializing login: {e}", ephemeral=True)
                await generator.close()

        elif custom_id == BTN_EXIT:
            if user_id in USER_CACHE:
                data = USER_CACHE[user_id]
                for path in data.get("image_paths", {}).values():
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except Exception as e:
                        print(f"Error deleting file {path}: {e}")
                
                del USER_CACHE[user_id]
            
            class ExitView(discord.ui.LayoutView):    
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"# <:like:1446905773044269217> Thanks for using {BOT_NAME}"),
                    discord.ui.TextDisplay(content="We’re grateful you trusted our bot to check your account."),
                    accent_colour=EMBED_COLOR,
                )
                
                action_row1 = discord.ui.ActionRow(
                        discord.ui.Button(
                            url="https://github.com/matheusaudibert/discord-fortnite-skin-checker",
                            style=discord.ButtonStyle.link,
                            label="Give us a star",
                        ),
                )
            
            await interaction.response.edit_message(view=ExitView(), attachments=[])
                
        elif custom_id in [BTN_INFO, BTN_SKINS, BTN_PICKAXES, BTN_BACKBLINGS, BTN_GLIDERS, BTN_EMOTES, BTN_BANNERS, BTN_ALL]:
            if user_id not in USER_CACHE:
                await interaction.response.send_message("❌ Session expired or data not found. Please login again.", ephemeral=True)
                return
            
            data = USER_CACHE[user_id]
            username = data["username"]
            
            if custom_id == BTN_INFO:
                view = create_panel_view(username, "info", text_content=data["info_str"])
                await interaction.response.edit_message(view=view, attachments=[])
            else:
                category = CATEGORY_MAP[custom_id]
                
                if category in data["image_paths"]:
                    path = data["image_paths"][category]
                    filename = os.path.basename(path)
                    file = discord.File(path, filename=filename)
                    view = create_panel_view(username, category, image_filename=filename)
                    await interaction.response.edit_message(view=view, attachments=[file])
                    return

                await interaction.response.defer()
                
                ids_to_show = []
                if category == "All Cosmetics":
                    order = ["Skins", "Back Blings", "Pickaxes", "Emotes", "Gliders", "Banners"]
                    for grp in order:
                        ids_to_show.extend(data["items"].get(grp, []))
                else:
                    ids_to_show = data["items"].get(category, [])
                
                if not ids_to_show:
                    await interaction.followup.send(f"No items found for {category}.", ephemeral=True)
                    return

                async with aiohttp.ClientSession() as session:
                    order = ["Skins", "Back Blings", "Pickaxes", "Emotes", "Gliders", "Banners"]
                    sorted_ids = await sort_ids_by_rarity(ids_to_show, session, item_order=order)
                    
                    output_dir = "output"
                    path = await create_checker_image(
                        sorted_ids,
                        session,
                        username=username,
                        group_name=category,
                        output_dir=output_dir,
                        footer_text=category
                    )
                
                if path:
                    data["image_paths"][category] = path
                    
                    filename = os.path.basename(path)
                    file = discord.File(path, filename=filename)
                    view = create_panel_view(username, category, image_filename=filename)
                    await interaction.edit_original_response(view=view, attachments=[file])
                else:
                    await interaction.followup.send("Failed to generate image.", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)