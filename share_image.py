import os

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts")

COLOR_BG_TOP = (18, 14, 28)
COLOR_BG_BOTTOM = (8, 10, 20)
COLOR_A = (255, 212, 0)
COLOR_B = (255, 47, 146)
COLOR_A_TEXT = (26, 20, 0)
COLOR_B_TEXT = (42, 0, 22)
COLOR_TEXT = (242, 243, 250)
COLOR_TEXT_DIM = (154, 160, 184)
COLOR_TRACK = (42, 46, 66)

WIDTH, HEIGHT = 1200, 630


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _vertical_gradient(draw, width, height, top, bottom):
    for y in range(height):
        t = y / max(height - 1, 1)
        color = (_lerp(top[0], bottom[0], t), _lerp(top[1], bottom[1], t), _lerp(top[2], bottom[2], t))
        draw.line([(0, y), (width, y)], fill=color)


def _rounded_bar(width, height, radius, pct_a):
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=255)

    bar = Image.new("RGB", (width, height), COLOR_B)
    bar_draw = ImageDraw.Draw(bar)
    split = int(width * pct_a / 100)
    if split > 0:
        bar_draw.rectangle([0, 0, split, height], fill=COLOR_A)

    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.paste(bar, (0, 0), mask)
    return result


def generate_share_image(option_a, option_b, pct_a, pct_b, total_votes, label=None, date_label=None):
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG_TOP)
    draw = ImageDraw.Draw(img)
    _vertical_gradient(draw, WIDTH, HEIGHT, COLOR_BG_TOP, COLOR_BG_BOTTOM)

    margin = 64

    brand_font = _font("Poppins-ExtraBold.ttf", 28)
    draw.text((margin, 48), "LA PREGUNTA", font=brand_font, fill=COLOR_TEXT)
    brand_w = draw.textlength("LA PREGUNTA ", font=brand_font)
    draw.text((margin + brand_w, 48), "DEL DIA", font=brand_font, fill=(150, 160, 255))

    meta_font = _font("Poppins-Medium.ttf", 22)
    meta_parts = [p for p in [date_label, label] if p]
    if meta_parts:
        draw.text((margin, 90), "  ·  ".join(meta_parts), font=meta_font, fill=COLOR_TEXT_DIM)

    q_font = _font("Poppins-ExtraBold.ttf", 60)
    max_text_width = WIDTH - margin * 2
    y_cursor = 150

    def draw_wrapped(text, color, y):
        words = text.split()
        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=q_font) <= max_text_width or not line:
                line = trial
            else:
                draw.text((margin, y), line, font=q_font, fill=color)
                y = draw.textbbox((margin, y), line, font=q_font)[3] + 6
                line = word
        draw.text((margin, y), line, font=q_font, fill=color)
        return draw.textbbox((margin, y), line, font=q_font)[3]

    y_cursor = draw_wrapped(option_a, COLOR_A, y_cursor) + 10
    y_cursor = draw_wrapped("o " + option_b + "?", COLOR_B, y_cursor) + 50

    bar_x, bar_w, bar_h = margin, WIDTH - margin * 2, 76
    bar = _rounded_bar(bar_w, bar_h, radius=18, pct_a=pct_a)
    draw.rounded_rectangle(
        [bar_x, y_cursor, bar_x + bar_w, y_cursor + bar_h], radius=18, fill=COLOR_TRACK
    )
    img.paste(bar, (bar_x, y_cursor), bar)

    pct_font = _font("Poppins-ExtraBold.ttf", 32)
    pa_text = f"{pct_a}%"
    pb_text = f"{pct_b}%"
    draw.text((bar_x + 24, y_cursor + 20), pa_text, font=pct_font, fill=COLOR_A_TEXT)
    pb_w = draw.textlength(pb_text, font=pct_font)
    draw.text((bar_x + bar_w - 24 - pb_w, y_cursor + 20), pb_text, font=pct_font, fill=COLOR_B_TEXT)

    footer_font = _font("Poppins-Medium.ttf", 24)
    votes_label = f"{total_votes:,}".replace(",", ".") + " votos  ·  lapreguntadeldia.es"
    draw.text((margin, HEIGHT - 70), votes_label, font=footer_font, fill=COLOR_TEXT_DIM)

    return img
