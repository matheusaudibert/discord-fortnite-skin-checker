import aiohttp
import asyncio
import os

if not os.path.exists("cache"):
    os.makedirs("cache")

def read_skin_ids(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]

async def download_image(session, skin_id):
    imgpath = f"./cache/{skin_id}.png"

    if os.path.exists(imgpath) and os.path.isfile(imgpath):
        return

    urls = [
        f"https://fortnite-api.com/images/cosmetics/br/{skin_id}/icon.png",
        f"https://fortnite-api.com/images/cosmetics/br/{skin_id}/smallicon.png"
    ]

    for url in urls:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(imgpath, "wb") as f:
                    f.write(await resp.read())
                print(f"Image loaded: {imgpath}")
                return

    placeholder_path = "src/placeholder.png"
    
    if not os.path.exists(placeholder_path):
        raise FileNotFoundError("ERROR: src/placeholder.png not found!")
    
    with open(imgpath, "wb") as f:
        f.write(open(placeholder_path, "rb").read())

    print(f"Could not download image for {skin_id}, using placeholder.")

async def main():
    skin_ids = read_skin_ids("skins.txt")

    async with aiohttp.ClientSession() as session:
        tasks = [download_image(session, sid) for sid in skin_ids]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
