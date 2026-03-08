import os
import requests
from PIL import Image, ImageDraw, ImageFont
import math



FONT_URL = "https://fonts.gstatic.com/s/opensans/v14/cJZKeOuBrn4kERxqtaUH3SZ2oysoEQEeKwjgmXLRnTc.ttf"
FONT_PATH = "OpenSans-Regular.ttf"


def download_font():
    if not os.path.exists(FONT_PATH):
        print("Downloading font...")
        resp = requests.get(FONT_URL)
        resp.raise_for_status()
        with open(FONT_PATH, "wb") as f:
            f.write(resp.content)
        print("Font downloaded:", FONT_PATH)
    else:
        print("Font already exists:", FONT_PATH)

download_font()

# --- Step 2: The renderer with markdown and card layout ---

def render_markdown_card(
    text: str,
    output_path: str,
    width=500,
    padding=40,
    collumns=8,
    bg_color=(35, 35, 35, 255),
    card_color=(255, 255, 255, 255),
    border_color=(200, 200, 200, 255),
):

    # Load the downloaded font
    font_normal = ImageFont.truetype(FONT_PATH, 28)
    font_bold   = ImageFont.truetype(FONT_PATH, 32)
    font_code   = ImageFont.truetype(FONT_PATH, 26)
    font_h1     = ImageFont.truetype(FONT_PATH, 44)
    font_h2     = ImageFont.truetype(FONT_PATH, 36)

    # Sample icons (make sure these exist in your project)
    """ icons = {
        "info": Image.open("icons/info.png").convert("RGBA"),
        "warning": Image.open("icons/warning.png").convert("RGBA"),
    } """

    img = Image.new("RGBA", (width*collumns + 2 * padding, 10000), bg_color)
    draw = ImageDraw.Draw(img)
    y = padding
    x = padding
    max_y = y
    player_list: list = text.split('\\')

    for i, player in enumerate(player_list):
        if i % math.floor(len(player_list)/collumns) == 0 and i != 0:
            max_y = y
            y = padding
            x += width
        for raw_line in player.split("\n"):
            line = raw_line.strip()
            if not line:
                y += 36
                continue

            # Headings
            if line.startswith("# "):
                draw.text((x + padding, y), line[2:], font=font_h1, fill="white")
                y += 60
                continue
            if line.startswith("## "):
                draw.text((x + padding, y), line[3:], font=font_h2, fill="white")
                y += 52
                continue

            if line.startswith("=="):
                y += 20
                draw.rectangle((x + padding, y - 4, x + width - padding, y + 2), fill=(230, 230, 230, 255))
                y += 50
                continue

            # List item
            if line.startswith("- "):
                draw.rectangle(
                    (x, y - 4, x + width - padding, y + 38),
                    #fill=(230, 230, 230, 255),
                )
                draw.text((x + padding + 20, y), line[2:], font=font_normal, fill="white")
                y += 46
                continue

            # Inline formatting

                # Default
            draw.text((x, y), line, font=font_normal, fill="white")

            y += 42

    
    total_width = collumns * width

    img.crop((0, 0, total_width + padding, max_y + padding)).save(output_path)
