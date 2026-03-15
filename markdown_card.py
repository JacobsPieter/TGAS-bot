"""
Markdown Card Renderer Module

Provides functionality to render markdown-formatted text into styled image cards
for Discord bot usage. This module handles font downloading, text rendering, and
image generation with support for basic markdown formatting including headings,
separators, and list items.

The renderer creates multi-column layouts with customizable styling options
including background colors, padding, and column widths. 
TODO:It automatically downloads the required OpenSans font from Google Fonts if not already present.

Usage:
    render_markdown_card(
        text="Your markdown content here",
        output_path="output.png",
        width=500,
        padding=40,
        columns=8
    )
"""

import math

from PIL import Image, ImageDraw, ImageFont



FONT_URL = "https://fonts.gstatic.com/s/opensans/v14/cJZK" \
            "eOuBrn4kERxqtaUH3SZ2oysoEQEeKwjgmXLRnTc.ttf"
FONT_PATH = "OpenSans-Regular.ttf"

def render_markdown_card(
    text: str,
    output_path: str,
    width=500,
    padding=40,
    collumns=8,
    bg_color=(35, 35, 35, 255),
):
    """
    Render markdown-formatted text into a styled image card.
    
    Supports basic markdown formatting including headings, separators, and list items.
    The text is rendered in a multi-column layout with customizable styling.
    
    Args:
        text (str): The markdown-formatted text to render
        output_path (str): Path where the output image will be saved
        width (int, optional): Width of each column in pixels. Defaults to 500.
        padding (int, optional): Padding around the content in pixels. Defaults to 40.
        collumns (int, optional): Number of columns in the layout. Defaults to 8.
        bg_color (tuple, optional): Background color as RGBA tuple. Defaults to dark gray.
    """

    # Load the downloaded font
    font_normal = ImageFont.truetype(FONT_PATH, 28)
    font_h1     = ImageFont.truetype(FONT_PATH, 44)
    font_h2     = ImageFont.truetype(FONT_PATH, 36)


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
                draw.rectangle((x + padding, y - 4, x + width - padding, y + 2),
                               fill=(230, 230, 230, 255))
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
