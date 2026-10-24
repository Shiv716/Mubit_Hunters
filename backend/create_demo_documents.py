"""Render the fixed, fictional demo documents. Run when changing sample.json."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DIRECTORY = Path(__file__).resolve().parent / "data" / "consumer-demo"


def sheet(title, lines, filename):
    image = Image.new("RGB", (1200, 1500), "#fffdf7")
    draw = ImageDraw.Draw(image)
    def text(x, y, value, size, color="#242820"):
        draw.text((x, y), value, font=ImageFont.load_default(size=size), fill=color)
    draw.rounded_rectangle((50, 50, 1150, 1450), radius=20, outline="#242820", width=3)
    draw.rectangle((70, 70, 1130, 155), fill="#d8f76d")
    text(100, 95, "FICTIONAL DEMO / NOT A REAL CHARGE", 32)
    text(100, 205, "WILLOW YARD", 58)
    text(100, 280, "Parking (fictional)", 28, "#686e60")
    text(100, 370, title, 39, "#4355eb")
    for index, (label, value) in enumerate(lines):
        text(100, 470 + index * 112, label.upper(), 21, "#686e60")
        text(100, 506 + index * 112, value, 31)
    draw.line((100, 1305, 1100, 1305), fill="#a4a89d", width=2)
    text(100, 1340, "CIVIC SAMPLE / NO PAYMENT OR SUBMISSION REQUIRED", 22, "#686e60")
    image.save(DIRECTORY / filename, quality=94)


if __name__ == "__main__":
    sheet("PRIVATE PARKING CHARGE NOTICE", [
        ("Notice reference / issue date", "DEMO-001 / 20 October 2026"),
        ("Vehicle registration", "DEMO123"),
        ("Location", "Willow Yard, London (fictional)"),
        ("Observed / alleged reason", "20 Oct 2026, 11:15 / No valid payment"),
        ("Amount / discounted amount", "GBP 100 / GBP 60 until 3 November 2026"),
        ("Challenge deadline printed on notice", "17 November 2026"),
        ("Stage", "First notice / initial challenge"),
    ], "ticket.jpg")
    sheet("PARKING PAYMENT RECEIPT", [
        ("Receipt reference", "DEMO-PAY-001"),
        ("Vehicle registration", "DEMO123"),
        ("Location", "Willow Yard, London (fictional)"),
        ("Payment received", "20 October 2026 at 09:55"),
        ("Parking session", "20 October 2026, 10:00 to 13:00"),
        ("Amount paid", "GBP 6.00"),
        ("Status", "Payment recorded / fictional sample"),
    ], "receipt.jpg")
