"""Renders a ToyRobotEnv's state as a simple 2D PNG image.

This is intentionally minimal (colored rectangles + text labels, no fancy
graphics) -- the point is to give a vision-language model a genuine image
to interpret, not to produce a polished illustration. Locations are drawn
as boxes in a row; each box lists the objects currently there; the robot is
drawn as a filled circle in whichever box it currently occupies.

``Pillow`` is only imported inside ``render_scene()``, not at module import
time, so the rest of the package (and any command that doesn't render a
scene) works without Pillow installed. Install it with
``pip install -e ".[vision]"``.
"""

from __future__ import annotations

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import GeniacCapError

BOX_WIDTH = 220
BOX_HEIGHT = 160
BOX_MARGIN = 20
TOP_MARGIN = 60
LOCATION_FILL = (235, 245, 255)
CONTAINER_FILL = (255, 240, 225)
BORDER_COLOR = (60, 60, 60)
ROBOT_COLOR = (200, 40, 40)
TEXT_COLOR = (20, 20, 20)


class RenderingError(GeniacCapError):
    """Raised when the scene cannot be rendered (e.g. Pillow missing)."""


def render_scene(env: ToyRobotEnv) -> bytes:
    """Render ``env``'s current state as PNG image bytes.

    Layout: one box per known location (sorted alphabetically, left to
    right), each labeled with its name and listing the objects currently
    there. The robot is drawn as a red circle inside its current location's
    box, with "(holding: X)" noted if it's carrying something.
    """

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RenderingError(
            "The 'Pillow' package is not installed. Install it with: "
            "pip install -e '.[vision]'"
        ) from exc

    locations = sorted(env.state.locations)
    if not locations:
        raise RenderingError("Cannot render a scene with no known locations")

    width = BOX_MARGIN + len(locations) * (BOX_WIDTH + BOX_MARGIN)
    height = TOP_MARGIN + BOX_HEIGHT + BOX_MARGIN

    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.text(
        (BOX_MARGIN, 15), "Toy Robot Environment -- current state", fill=TEXT_COLOR, font=font
    )

    objects_by_location: dict[str, list[str]] = {loc: [] for loc in locations}
    for obj, loc in env.state.object_locations.items():
        objects_by_location.setdefault(loc, []).append(obj)

    for i, location in enumerate(locations):
        x0 = BOX_MARGIN + i * (BOX_WIDTH + BOX_MARGIN)
        y0 = TOP_MARGIN
        x1 = x0 + BOX_WIDTH
        y1 = y0 + BOX_HEIGHT

        is_container = location in getattr(env, "_containers", set())
        fill = CONTAINER_FILL if is_container else LOCATION_FILL
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=BORDER_COLOR, width=2)

        label = location
        if is_container:
            state = "open" if env.state.container_open.get(location) else "closed"
            label = f"{location} ({state} container)"
        draw.text((x0 + 8, y0 + 6), label, fill=TEXT_COLOR, font=font)

        text_y = y0 + 26
        for obj in objects_by_location.get(location, []):
            draw.text((x0 + 8, text_y), f"- {obj}", fill=TEXT_COLOR, font=font)
            text_y += 16

        if location == env.state.robot_location:
            cx, cy = x0 + BOX_WIDTH - 30, y1 - 30
            draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=ROBOT_COLOR)
            draw.text((cx - 10, cy - 6), "R", fill=(255, 255, 255), font=font)
            if env.state.held_object:
                draw.text(
                    (x0 + 8, y1 - 18),
                    f"(holding: {env.state.held_object})",
                    fill=ROBOT_COLOR,
                    font=font,
                )

    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
