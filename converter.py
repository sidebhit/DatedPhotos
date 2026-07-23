"""Photo conversion: scale 4:3 images into 1800x1200 canvases with dated padding."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ExifTags

CANVAS_WIDTH = 1800
CANVAS_HEIGHT = 1200
CANVAS_ASPECT = CANVAS_WIDTH / CANVAS_HEIGHT  # 6:4 landscape page

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

EXIF_TAG_NAMES = {v: k for k, v in ExifTags.TAGS.items()}
EXIF_DATETIME_ORIGINAL = EXIF_TAG_NAMES.get("DateTimeOriginal", 36867)
EXIF_DATETIME = EXIF_TAG_NAMES.get("DateTime", 306)


@dataclass
class ConversionSettings:
    text_size: int = 48
    text_color: str = "#333333"
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


def _vertical_text_size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    """Width and height of text when rotated to run parallel to the page short edge."""
    bbox = font.getbbox(text)
    horizontal_w = bbox[2] - bbox[0]
    horizontal_h = bbox[3] - bbox[1]
    return horizontal_h, horizontal_w


def _draw_vertical_centered_text(
    canvas: Image.Image,
    text: str,
    region: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    color: str,
) -> None:
    """Draw text parallel to the page short edge, centered in region (left, top, right, bottom)."""
    left, top, right, bottom = region
    region_w = right - left
    region_h = bottom - top

    text_w, text_h = _vertical_text_size(text, font)
    if text_w == 0 or text_h == 0:
        return

    padding = 8
    scale = min((region_w - padding) / text_w, (region_h - padding) / text_h, 1.0)
    if scale < 1.0:
        new_size = max(int(font.size * scale), 8)
        font = _load_font(new_size)
        text_w, text_h = _vertical_text_size(text, font)

    text_img = Image.new("RGBA", (text_h + 4, text_w + 4), (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_img)
    draw.text((2, 2), text, font=font, fill=color)
    rotated = text_img.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    paste_x = left + (region_w - rotated.width) // 2
    paste_y = top + (region_h - rotated.height) // 2
    canvas.paste(rotated, (paste_x, paste_y), rotated)


def _landscape_strip_width() -> int:
    """Right-strip width when a 4:3 landscape photo fills the canvas height."""
    return CANVAS_WIDTH - round(CANVAS_HEIGHT * (4 / 3))


def _fit_image_dimensions(img_w: int, img_h: int, is_landscape: bool) -> tuple[int, int, int, int, int]:
    """
    Compute scaled image size and padding strip size.

    Landscape sources: image fills canvas height; white strip on the right.
    Portrait sources: image fits above a bottom strip sized to match the landscape strip.
    """
    if is_landscape:
        scaled_h = CANVAS_HEIGHT
        scaled_w = round(scaled_h * img_w / img_h)
        strip_w = CANVAS_WIDTH - scaled_w
        if strip_w < 0:
            scale = CANVAS_WIDTH / scaled_w
            scaled_w = CANVAS_WIDTH
            scaled_h = round(scaled_h * scale)
            strip_w = 0
        return scaled_w, scaled_h, strip_w, 0, 0

    strip_h = _landscape_strip_width()
    image_area_h = CANVAS_HEIGHT - strip_h
    scale = min(CANVAS_WIDTH / img_w, image_area_h / img_h)
    scaled_w = round(img_w * scale)
    scaled_h = round(img_h * scale)
    return scaled_w, scaled_h, 0, 0, CANVAS_HEIGHT - scaled_h


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

        scaled_w, scaled_h, strip_w, _, strip_h = _fit_image_dimensions(
            img_w, img_h, is_landscape
        )

        resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")

        if is_landscape:
            offset_x = 0
            offset_y = (CANVAS_HEIGHT - scaled_h) // 2
            canvas.paste(resized, (offset_x, offset_y))
            text_region = (
                CANVAS_WIDTH - strip_w,
                0,
                CANVAS_WIDTH,
                CANVAS_HEIGHT,
            )
        else:
            offset_x = (CANVAS_WIDTH - scaled_w) // 2
            offset_y = 0
            canvas.paste(resized, (offset_x, offset_y))
            text_region = (
                0,
                CANVAS_HEIGHT - strip_h,
                CANVAS_WIDTH,
                CANVAS_HEIGHT,
            )

        font = _load_font(settings.text_size)
        _draw_vertical_centered_text(canvas, date_text, text_region, font, settings.text_color)

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
