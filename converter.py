"""Photo conversion: scale images into dated canvases with colored padding."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ExifTags

LANDSCAPE_WIDTH = 1800
LANDSCAPE_HEIGHT = 1200
PORTRAIT_WIDTH = 1200
PORTRAIT_HEIGHT = 1800

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

EXIF_TAG_NAMES = {v: k for k, v in ExifTags.TAGS.items()}
EXIF_DATETIME_ORIGINAL = EXIF_TAG_NAMES.get("DateTimeOriginal", 36867)
EXIF_DATETIME = EXIF_TAG_NAMES.get("DateTime", 306)


@dataclass
class ConversionSettings:
    text_size: int = 48
    text_color: str = "#333333"
    background_color: str = "#FFFFFF"
    output_subdir: str = "converted"


def _parse_exif_datetime(value: str | bytes | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    value = str(value).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def get_photo_date(image_path: Path, image: Image.Image) -> datetime:
    """Return EXIF capture date, falling back to file modification time."""
    try:
        exif = image.getexif()
        if exif:
            for tag in (EXIF_DATETIME_ORIGINAL, EXIF_DATETIME):
                if tag in exif:
                    parsed = _parse_exif_datetime(exif.get(tag))
                    if parsed:
                        return parsed
    except Exception:
        pass

    mtime = os.path.getmtime(image_path)
    return datetime.fromtimestamp(mtime)


def format_photo_date(dt: datetime) -> str:
    return dt.strftime("%B %d, %Y")


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text_bbox(text: str, font: ImageFont.ImageFont) -> tuple[int, int, int, int]:
    """Return left, top, right, bottom bbox for rendered text."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    return draw.textbbox((0, 0), text, font=font)


def _fit_font_to_region(
    text: str,
    font: ImageFont.ImageFont,
    region_w: int,
    region_h: int,
) -> ImageFont.ImageFont:
    bbox = _text_bbox(text, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    if text_w == 0 or text_h == 0:
        return font

    padding = 16
    scale = min((region_w - padding) / text_w, (region_h - padding) / text_h, 1.0)
    if scale < 1.0:
        new_size = max(int(font.size * scale), 8)
        return _load_font(new_size)
    return font


def _fill_region(
    canvas: Image.Image,
    region: tuple[int, int, int, int],
    color: str,
) -> None:
    left, top, right, bottom = region
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((left, top, right - 1, bottom - 1), fill=color)


def _draw_horizontal_centered_text(
    canvas: Image.Image,
    text: str,
    region: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    color: str,
    background_color: str,
) -> None:
    """Draw horizontal text centered in region (parallel to the page short edge)."""
    _fill_region(canvas, region, background_color)
    left, top, right, bottom = region
    region_w = right - left
    region_h = bottom - top

    font = _fit_font_to_region(text, font, region_w, region_h)
    bbox = _text_bbox(text, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    draw = ImageDraw.Draw(canvas)
    draw.text(
        (
            left + (region_w - text_w) // 2 - bbox[0],
            top + (region_h - text_h) // 2 - bbox[1],
        ),
        text,
        font=font,
        fill=color,
    )


def _draw_vertical_centered_text(
    canvas: Image.Image,
    text: str,
    region: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    color: str,
    background_color: str,
) -> None:
    """Draw vertical text centered in region (parallel to the page short edge)."""
    _fill_region(canvas, region, background_color)
    left, top, right, bottom = region
    region_w = right - left
    region_h = bottom - top

    font = _fit_font_to_region(text, font, region_h, region_w)
    bbox = _text_bbox(text, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    if text_w == 0 or text_h == 0:
        return

    # Extra padding on the bottom before rotation becomes the outer (right) edge,
    # where descenders end up after a 90-degree counter-clockwise rotation.
    pad_left = 8 - bbox[0]
    pad_top = 8 - bbox[1]
    pad_right = 8
    pad_bottom = max(20, int(font.size * 0.35))

    text_img = Image.new(
        "RGBA",
        (text_w + pad_left + pad_right, text_h + pad_top + pad_bottom),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(text_img)
    draw.text((pad_left, pad_top), text, font=font, fill=color)
    rotated = text_img.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    # Descender padding ends up on the right after rotation, so compensate when
    # centering the glyphs left-to-right in the narrow strip.
    paste_x = left + (region_w - rotated.width) // 2 + pad_bottom // 2
    paste_x = min(max(paste_x, left), left + max(region_w - rotated.width, 0))
    paste_y = top + max((region_h - rotated.height) // 2, 0)
    canvas.paste(rotated, (paste_x, paste_y), rotated)


def _fit_landscape(img_w: int, img_h: int) -> tuple[int, int, int, int, int, int, int]:
    """Return canvas size, scaled image size, and right strip width."""
    canvas_w, canvas_h = LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT
    scaled_h = canvas_h
    scaled_w = round(scaled_h * img_w / img_h)
    strip_w = canvas_w - scaled_w
    if strip_w < 0:
        scale = canvas_w / scaled_w
        scaled_w = canvas_w
        scaled_h = round(scaled_h * scale)
        strip_w = 0
    return canvas_w, canvas_h, scaled_w, scaled_h, strip_w, 0, 0


def _fit_portrait(img_w: int, img_h: int) -> tuple[int, int, int, int, int, int, int]:
    """Return canvas size, scaled image size, and bottom strip height."""
    canvas_w, canvas_h = PORTRAIT_WIDTH, PORTRAIT_HEIGHT
    scaled_w = canvas_w
    scaled_h = round(scaled_w * img_h / img_w)
    strip_h = canvas_h - scaled_h
    if strip_h < 0:
        scale = canvas_h / scaled_h
        scaled_h = canvas_h
        scaled_w = round(scaled_w * scale)
        strip_h = 0
    return canvas_w, canvas_h, scaled_w, scaled_h, 0, 0, strip_h


def convert_image(
    source_path: Path,
    dest_path: Path,
    settings: ConversionSettings,
) -> None:
    with Image.open(source_path) as img:
        img = img.convert("RGB")
        photo_date = get_photo_date(source_path, img)
        date_text = format_photo_date(photo_date)

        img_w, img_h = img.size
        is_landscape = img_w >= img_h

        if is_landscape:
            canvas_w, canvas_h, scaled_w, scaled_h, strip_w, _, _ = _fit_landscape(
                img_w, img_h
            )
        else:
            canvas_w, canvas_h, scaled_w, scaled_h, _, _, strip_h = _fit_portrait(
                img_w, img_h
            )
            strip_w = 0

        resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (canvas_w, canvas_h), settings.background_color)
        font = _load_font(settings.text_size)

        if is_landscape:
            offset_x = 0
            offset_y = (canvas_h - scaled_h) // 2
            canvas.paste(resized, (offset_x, offset_y))
            text_region = (canvas_w - strip_w, 0, canvas_w, canvas_h)
            _draw_vertical_centered_text(
                canvas,
                date_text,
                text_region,
                font,
                settings.text_color,
                settings.background_color,
            )
        else:
            offset_x = (canvas_w - scaled_w) // 2
            offset_y = 0
            canvas.paste(resized, (offset_x, offset_y))
            text_region = (0, canvas_h - strip_h, canvas_w, canvas_h)
            _draw_horizontal_centered_text(
                canvas,
                date_text,
                text_region,
                font,
                settings.text_color,
                settings.background_color,
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dest_path, "JPEG", quality=95, optimize=True)


def list_images(directory: Path) -> list[Path]:
    images = []
    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            images.append(entry)
    return images


def convert_directory(
    source_dir: Path,
    settings: ConversionSettings,
    progress_callback=None,
) -> tuple[int, Path]:
    images = list_images(source_dir)
    output_dir = source_dir / settings.output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, image_path in enumerate(images, start=1):
        dest_name = image_path.stem + ".jpg"
        dest_path = output_dir / dest_name
        convert_image(image_path, dest_path, settings)
        if progress_callback:
            progress_callback(index, len(images), image_path.name)

    return len(images), output_dir
