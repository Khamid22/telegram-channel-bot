from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    template_dir = Path("assets/templates")
    template_dir.mkdir(parents=True, exist_ok=True)
    output = template_dir / "default.png"

    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), "#F7F9FC")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width, 160), fill="#0B4A6F")
    draw.rectangle((0, 160, width, height), fill="#F7F9FC")
    draw.rounded_rectangle((72, 210, 1008, 1220), radius=36, fill="#FFFFFF", outline="#D0D5DD", width=3)
    draw.rounded_rectangle((92, 1128, 300, 1194), radius=24, fill="#ECFDF3")
    draw.line((100, 540, 980, 540), fill="#EAECF0", width=3)
    draw.line((100, 860, 980, 860), fill="#EAECF0", width=3)
    draw.rectangle((72, 1236, 1008, 1242), fill="#0B4A6F")
    draw.ellipse((855, 54, 965, 164), fill="#B3E5FC")
    draw.ellipse((905, 74, 1005, 174), fill="#D1FADF")

    image.save(output, "PNG", optimize=True)
    print(f"Created {output}")


if __name__ == "__main__":
    main()
