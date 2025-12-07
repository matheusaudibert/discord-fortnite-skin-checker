import io
import math
import os
import asyncio
from concurrent.futures import ProcessPoolExecutor

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from src.config import (
    CACHE_DIR,
    FONT_PATH,
    PLACEHOLDER_IMAGE,
    RARITY_BACKGROUNDS_V1,
)
from src.config import get_cosmetic_type 
from src.fortnite_api import get_cosmetic_info, download_cosmetic_images


def combine_with_background(
    foreground: Image.Image,
    background: Image.Image,
    name: str,
    rarity: str,
    is_banner: bool = False,
) -> Image.Image:
    bg = background.convert("RGBA")
    fg = foreground.convert("RGBA")

    if not is_banner:
        fg = fg.resize(bg.size, Image.Resampling.LANCZOS)
        bg.paste(fg, (0, 0), fg)
    else:
        fg = fg.resize((192, 192), Image.Resampling.LANCZOS)
        bg.paste(fg, (32, 12), fg)

    draw = ImageDraw.Draw(bg)

    special_rarities = {
        "ICON SERIES",
        "DARK SERIES",
        "STAR WARS SERIES",
        "GAMING LEGENDS SERIES",
        "MARVEL SERIES",
        "DC SERIES",
        "SHADOW SERIES",
        "SLURP SERIES",
        "LAVA SERIES",
        "FROZEN SERIES",
    }

    base_max_font_size = 80 if rarity.upper() in special_rarities else 40

    name = name.upper()
    font_size = base_max_font_size
    while font_size > 10:
        try:
            font = ImageFont.truetype(FONT_PATH, size=font_size)
        except IOError:
            font = ImageFont.load_default()
            break
        text_bbox = draw.textbbox((0, 0), name, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        if text_width <= bg.width - 20:
            break
        font_size -= 1

    try:
        font = ImageFont.truetype(FONT_PATH, size=font_size)
    except IOError:
        font = ImageFont.load_default()

    text_bbox = draw.textbbox((0, 0), name, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (bg.width - text_width) // 2

    bar_y = int(bg.height * 0.80)
    bar_height = bg.height - bar_y

    bar = Image.new("RGBA", (bg.width, bar_height), (0, 0, 0, int(255 * 0.7)))
    bg.paste(bar, (0, bar_y), bar)

    text_y = bar_y + (bar_height - text_height) // 2
    draw.text((text_x, text_y), name, fill="white", font=font)

    return bg


def combine_images(
    images,
    username: str,
    item_count: int,
    logo_path: str,
) -> Image.Image:
    max_width = 1848
    max_height = 2048

    num_items = len(images)
    max_cols = 6
    num_rows = math.ceil(num_items / max_cols)

    while num_rows > max_cols:
        max_cols += 1
        num_rows = math.ceil(num_items / max_cols)

    item_width = max_width // max_cols
    item_height = max_height // num_rows
    image_size = min(item_width, item_height)

    total_width = max_cols * image_size
    total_height = num_rows * image_size
    footer_height = image_size
    total_height += footer_height

    combined = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 255))

    for idx, img in enumerate(images):
        col = idx % max_cols
        row = idx // max_cols
        pos = (col * image_size, row * image_size)
        resized = img.resize((image_size, image_size), Image.Resampling.LANCZOS)
        combined.paste(resized, pos, resized)

    try:
        logo = Image.open(logo_path).convert("RGBA")
    except FileNotFoundError:
        logo = Image.new("RGBA", (100, 100), (255, 255, 255, 255))

    logo_height = int(footer_height * 0.6)
    logo_width = int((logo_height / logo.height) * logo.width)
    logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

    logo_position = (10, total_height - footer_height + (footer_height - logo_height) // 2)
    combined.paste(logo, logo_position, logo)

    from datetime import datetime

    text1 = f"Total items: {item_count}"
    text2 = f"Checked by {username} ({datetime.now().strftime('%d/%m/%y - %H:%M')})"
    text3 = f"discord.gg/{os.getenv('DISCORD_INVITE', '')}"

    draw = ImageDraw.Draw(combined)
    font_size = logo_height // 3

    try:
        font = ImageFont.truetype(FONT_PATH, size=font_size)
    except IOError:
        font = ImageFont.load_default()

    def measure(txt: str):
        bbox = font.getbbox(txt)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    w1, h1 = measure(text1)
    w2, h2 = measure(text2)
    w3, h3 = measure(text3)

    max_text_width = total_width - (logo_position[0] + logo_width + 20)
    while (w1 > max_text_width or w2 > max_text_width or w3 > max_text_width) and font_size > 8:
        font_size -= 1
        try:
            font = ImageFont.truetype(FONT_PATH, size=font_size)
        except IOError:
            font = ImageFont.load_default()
            break
        w1, h1 = measure(text1)
        w2, h2 = measure(text2)
        w3, h3 = measure(text3)

    total_text_height = h1 + h2 + h3 + 10
    text_y_start = total_height - footer_height + (footer_height - total_text_height) // 2
    text_x = logo_position[0] + logo_width + 10

    draw.text((text_x, text_y_start), text1, fill="white", font=font)
    draw.text((text_x, text_y_start + h1 + 5), text2, fill="white", font=font)
    draw.text((text_x, text_y_start + h1 + 5 + h2 + 5), text3, fill="white", font=font)

    return combined


def _process_cosmetic_item(args: dict) -> Image.Image:
    cid = args["cid"]
    name = args["name"]
    rarity = args["rarity"]
    background_path = args["background_path"]
    substitute_path = args.get("substitute_image_path")

    img_path = os.path.join(CACHE_DIR, f"{cid}.png")

    try:
        if substitute_path:
            img = Image.open(substitute_path).convert("RGBA")
        else:
            img = Image.open(img_path).convert("RGBA")

        if img.size == (1, 1):
            raise IOError("1x1 placeholder image")
    except (UnidentifiedImageError, IOError):
        img = Image.open(PLACEHOLDER_IMAGE).convert("RGBA")

    try:
        background = Image.open(background_path).convert("RGBA")
    except (UnidentifiedImageError, IOError):
        background = Image.new("RGBA", (512, 512), (0, 0, 0, 0))

    is_banner = cid.lower().startswith("banner_")
    return combine_with_background(img, background, name, rarity, is_banner=is_banner)


async def create_checker_image(
    ids: list[str],
    session,
    username: str,
    group_name: str,
    output_dir: str = "output",
    footer_text: str = "Generated by Fortnite Locker Checker",
) -> str | None:
    os.makedirs(output_dir, exist_ok=True)

    if not ids:
        return None

    await download_cosmetic_images(ids, session)
    info_list = await asyncio.gather(*[get_cosmetic_info(cid, session) for cid in ids])

    valid_info = [c for c in info_list if c["name"].strip().lower() != "unknown"]
    if not valid_info:
        return None

    work_args = []
    for cosmetic in valid_info:
        rarity = cosmetic.get("rarity", "Common")
        background_path = RARITY_BACKGROUNDS_V1.get(rarity, RARITY_BACKGROUNDS_V1["Common"])
        work_args.append(
            {
                "cid": cosmetic["id"],
                "name": cosmetic["name"],
                "rarity": rarity,
                "background_path": background_path,
                "substitute_image_path": None, 
            }
        )

    images = []
    with ProcessPoolExecutor(max_workers=4) as executor:
        for final_img in executor.map(_process_cosmetic_item, work_args):
            images.append(final_img)

    if not images:
        return None

    logo_path = os.path.join(output_dir, "logo.png")
    if not os.path.exists(logo_path):
        root_logo = os.path.join(os.path.dirname(__file__), "logo.png")
        if os.path.exists(root_logo):
            from shutil import copyfile
            copyfile(root_logo, logo_path)

    final_image = combine_images(
        images,
        username=username,
        item_count=len(valid_info),
        logo_path=logo_path,
    )

    output_path = os.path.join(output_dir, f"{group_name.replace(' ', '_').lower()}.png")
    final_image.save(output_path, "PNG")
    return output_path
