"""Photo conversion: scale images into dated canvases with colored padding."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ExifTags

LANDSCAPE_WIDTH = 1800
LANDSCAPE_HEIGHT = 1200
PORTRAIT_WIDTH = 1200
PORTRAIT_HEIGHT = 1800
LANDSCAPE_ASPECT = 4 / 3
PORTRAIT_ASPECT = 3 / 4
MAX_WORK_DIMENSION = 4000
MIN_TEXT_STRIP = 50

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

EXIF_TAG_NAMES = {v: k for k, v in ExifTags.TAGS.items()}
EXIF_DATETIME_ORIGINAL = EXIF_TAG_NAMES.get("DateTimeOriginal", 36867)
EXIF_DATETIME = EXIF_TAG_NAMES.get("DateTime", 306)


class LayoutMode(Enum):
    """How an image is placed on the output canvas."""

    LANDSCAPE_STANDARD = "landscape_standard"  # up to 4:3: strip on right
    LANDSCAPE_WIDE = "landscape_wide"  # wider than 4:3 (e.g. 16:9): strip on bottom
    PORTRAIT_STANDARD = "portrait_standard"  # up to 3:4: strip on bottom
    PORTRAIT_TALL = "portrait_tall"  # taller than 3:4 (e.g. 9:16): strip on right


@dataclass
class LayoutPlan:
    mode: LayoutMode
    canvas_w: int
    canvas_h: int
    scaled_w: int
    scaled_h: int
    image_x: int
    image_y: int
    text_region: tuple[int, int, int, int]
    vertical_text: bool


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


def _limit_image_size(img: Image.Image, max_dim: int = MAX_WORK_DIMENSION) -> Image.Image:
    """Downscale very large inputs so processing stays fast and reliable."""
    img_w, img_h = img.size
    longest = max(img_w, img_h)
    if longest <= max_dim:
        return img
    scale = max_dim / longest
    return img.resize(
        (max(1, round(img_w * scale)), max(1, round(img_h * scale))),
        Image.Resampling.LANCZOS,
    )


def _choose_layout_mode(img_w: int, img_h: int) -> LayoutMode:
    aspect = img_w / img_h
    if img_w >= img_h:
        if aspect > LANDSCAPE_ASPECT:
            return LayoutMode.LANDSCAPE_WIDE
        return LayoutMode.LANDSCAPE_STANDARD
    if aspect < PORTRAIT_ASPECT:
        return LayoutMode.PORTRAIT_TALL
    return LayoutMode.PORTRAIT_STANDARD


def _ensure_min_strip(strip: int, content_size: int, canvas_size: int) -> tuple[int, int]:
    """Shrink content slightly so the text strip meets the minimum width/height."""
    if strip <= 0 or strip >= MIN_TEXT_STRIP:
        return content_size, strip
    content_size = round(content_size * (canvas_size - MIN_TEXT_STRIP) / canvas_size)
    strip = canvas_size - content_size
    return content_size, strip


def _plan_layout(img_w: int, img_h: int) -> LayoutPlan:
    mode = _choose_layout_mode(img_w, img_h)

    if mode == LayoutMode.LANDSCAPE_STANDARD:
        canvas_w, canvas_h = LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT
        scaled_h = canvas_h
        scaled_w = round(scaled_h * img_w / img_h)
        strip_w = canvas_w - scaled_w
        if strip_w < 0:
            scale = canvas_w / scaled_w
            scaled_w = canvas_w
            scaled_h = round(scaled_h * scale)
            strip_w = 0
        scaled_w, strip_w = _ensure_min_strip(strip_w, scaled_w, canvas_w)
        scaled_h = round(scaled_w * img_h / img_w)
        return LayoutPlan(
            mode=mode,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            scaled_w=scaled_w,
            scaled_h=scaled_h,
            image_x=0,
            image_y=(canvas_h - scaled_h) // 2,
            text_region=(canvas_w - strip_w, 0, canvas_w, canvas_h),
            vertical_text=True,
        )

    if mode == LayoutMode.LANDSCAPE_WIDE:
        canvas_w, canvas_h = LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT
        scaled_w = canvas_w
        scaled_h = round(scaled_w * img_h / img_w)
        strip_h = canvas_h - scaled_h
        if strip_h < 0:
            scale = canvas_h / scaled_h
            scaled_h = canvas_h
            scaled_w = round(scaled_w * scale)
            strip_h = 0
        scaled_h, strip_h = _ensure_min_strip(strip_h, scaled_h, canvas_h)
        scaled_w = round(scaled_h * img_w / img_h)
        return LayoutPlan(
            mode=mode,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            scaled_w=scaled_w,
            scaled_h=scaled_h,
            image_x=(canvas_w - scaled_w) // 2,
            image_y=0,
            text_region=(0, canvas_h - strip_h, canvas_w, canvas_h),
            vertical_text=True,
        )

    if mode == LayoutMode.PORTRAIT_STANDARD:
        canvas_w, canvas_h = PORTRAIT_WIDTH, PORTRAIT_HEIGHT
        scaled_w = canvas_w
        scaled_h = round(scaled_w * img_h / img_w)
        strip_h = canvas_h - scaled_h
        if strip_h < 0:
            scale = canvas_h / scaled_h
            scaled_h = canvas_h
            scaled_w = round(scaled_w * scale)
            strip_h = 0
        scaled_h, strip_h = _ensure_min_strip(strip_h, scaled_h, canvas_h)
        scaled_w = round(scaled_h * img_w / img_h)
        return LayoutPlan(
            mode=mode,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            scaled_w=scaled_w,
            scaled_h=scaled_h,
            image_x=(canvas_w - scaled_w) // 2,
            image_y=0,
            text_region=(0, canvas_h - strip_h, canvas_w, canvas_h),
            vertical_text=False,
        )

    canvas_w, canvas_h = PORTRAIT_WIDTH, PORTRAIT_HEIGHT
    scaled_h = canvas_h
    scaled_w = round(scaled_h * img_w / img_h)
    strip_w = canvas_w - scaled_w
    if strip_w < 0:
        scale = canvas_w / scaled_w
        scaled_w = canvas_w
        scaled_h = round(scaled_h * scale)
        strip_w = 0
    scaled_w, strip_w = _ensure_min_strip(strip_w, scaled_w, canvas_w)
    scaled_h = round(scaled_w * img_h / img_w)
    return LayoutPlan(
        mode=LayoutMode.PORTRAIT_TALL,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        scaled_w=scaled_w,
        scaled_h=scaled_h,
        image_x=0,
        image_y=(canvas_h - scaled_h) // 2,
        text_region=(canvas_w - strip_w, 0, canvas_w, canvas_h),
        vertical_text=True,
    )


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


def _font_edge_padding(font: ImageFont.ImageFont) -> int:
    size = getattr(font, "size", 48) or 48
    return max(4, round(size * 0.15))


def _font_descender_padding(font: ImageFont.ImageFont) -> int:
    size = getattr(font, "size", 48) or 48
    return round(size * 0.35)


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

    edge_pad = _font_edge_padding(font)
    descender_pad = _font_descender_padding(font)
    padding_w = edge_pad * 2
    padding_h = edge_pad + descender_pad

    if region_w <= padding_w or region_h <= padding_h:
        return _load_font(8)

    scale = min(
        (region_w - padding_w) / text_w,
        (region_h - padding_h) / text_h,
        1.0,
    )
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
    if text_w == 0 or text_h == 0:
        return

    edge_pad = _font_edge_padding(font)
    descender_pad = _font_descender_padding(font)

    pad_left = edge_pad - bbox[0]
    pad_top = edge_pad - bbox[1]
    pad_right = edge_pad
    pad_bottom = descender_pad

    text_img = Image.new(
        "RGBA",
        (text_w + pad_left + pad_right, text_h + pad_top + pad_bottom),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(text_img)
    draw.text((pad_left, pad_top), text, font=font, fill=color)

    center_offset_y = descender_pad // 2
    paste_x = left + (region_w - text_img.width) // 2
    paste_y = top + (region_h - text_img.height) // 2 + center_offset_y
    paste_y = min(max(paste_y, top), top + max(region_h - text_img.height, 0))
    canvas.paste(text_img, (paste_x, paste_y), text_img)


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

    edge_pad = _font_edge_padding(font)
    descender_pad = _font_descender_padding(font)

    pad_left = edge_pad - bbox[0]
    pad_top = edge_pad - bbox[1]
    pad_right = edge_pad
    pad_bottom = descender_pad

    text_img = Image.new(
        "RGBA",
        (text_w + pad_left + pad_right, text_h + pad_top + pad_bottom),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(text_img)
    draw.text((pad_left, pad_top), text, font=font, fill=color)
    rotated = text_img.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    center_offset = descender_pad // 2
    paste_x = left + (region_w - rotated.width) // 2 + center_offset
    paste_x = min(max(paste_x, left), left + max(region_w - rotated.width, 0))
    paste_y = top + max((region_h - rotated.height) // 2, 0)
    canvas.paste(rotated, (paste_x, paste_y), rotated)


def convert_image(
    source_path: Path,
    dest_path: Path,
    settings: ConversionSettings,
) -> None:
    with Image.open(source_path) as img:
        img = img.convert("RGB")
        photo_date = get_photo_date(source_path, img)
        date_text = format_photo_date(photo_date)

        img = _limit_image_size(img)
        img_w, img_h = img.size
        plan = _plan_layout(img_w, img_h)

        resized = img.resize((plan.scaled_w, plan.scaled_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (plan.canvas_w, plan.canvas_h), settings.background_color)
        canvas.paste(resized, (plan.image_x, plan.image_y))
        font = _load_font(settings.text_size)

        if plan.vertical_text:
            _draw_vertical_centered_text(
                canvas,
                date_text,
                plan.text_region,
                font,
                settings.text_color,
                settings.background_color,
            )
        else:
            _draw_horizontal_centered_text(
                canvas,
                date_text,
                plan.text_region,
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
) -> tuple[int, Path, list[str]]:
    images = list_images(source_dir)
    output_dir = source_dir / settings.output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    failures: list[str] = []

    for index, image_path in enumerate(images, start=1):
        dest_name = image_path.stem + ".jpg"
        dest_path = output_dir / dest_name
        try:
            convert_image(image_path, dest_path, settings)
            converted += 1
        except Exception as exc:
            failures.append(f"{image_path.name}: {exc}")
        if progress_callback:
            progress_callback(index, len(images), image_path.name)

    return converted, output_dir, failures
