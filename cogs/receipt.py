"""
cogs/receipt.py — Nexora Cloud
Generate a professional invoice-style receipt with manually entered plan,
pricing, addons, customer, and delivery details.
"""

import io
import os
import re
from datetime import datetime, timezone

import barcode
import discord
from barcode.writer import ImageWriter
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont


DELIVERY_CHOICES = [
    app_commands.Choice(name="Admin DM only", value="admin_dm"),
    app_commands.Choice(name="Post in this channel", value="channel"),
    app_commands.Choice(name="Customer DM only", value="customer_dm"),
    app_commands.Choice(name="Admin DM + Channel", value="admin_channel"),
    app_commands.Choice(name="Customer + Channel + Admin", value="all"),
]

ACCENT_EMBED = 0x2563EB
SUCCESS_EMBED = 0x10B981
GOLD_EMBED = 0xF59E0B


def _load_fonts():
    """Load a clean sans-serif font."""
    candidates = [
        "C:/Windows/fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/arial.ttf",
        "arial.ttf",
    ]
    path = None
    for c in candidates:
        if os.path.exists(c):
            path = c
            break
    if not path:
        path = candidates[1]
    return {
        "h1": ImageFont.truetype(path, 32),
        "h2": ImageFont.truetype(path, 22),
        "reg": ImageFont.truetype(path, 17),
        "sm": ImageFont.truetype(path, 14),
        "xs": ImageFont.truetype(path, 12),
    }


def _draw_hexagon(draw, cx, cy, radius, color, outline=None):
    import math
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=color, outline=outline)


def _make_barcode(data: str) -> Image.Image:
    data = re.sub(r"[^A-Za-z0-9\-]", "", data) or "NEXORA"
    writer = ImageWriter()
    writer.set_options({
        "write_text": False,
        "module_height": 12,
        "quiet_zone": 2,
        "module_width": 0.25,
    })
    code = barcode.get("code128", data, writer=writer)
    buf = io.BytesIO()
    code.write(buf)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    padded = Image.new("RGB", (img.width, img.height + 10), (255, 255, 255))
    padded.paste(img, (0, 5))
    return padded


def generate_invoice(
    invoice_id: str,
    customer: str,
    cashier: str,
    items: list,
    price: float | None = None,
    discount: float = 0.0,
    real_price: float = 0.0,
    final_price: float = 0.0,
    status: str = "PAID",
) -> io.BytesIO:
    """Render a Nexora invoice with manually entered pricing."""
    W, H = 560, 840
    WHITE = (255, 255, 255)
    BLACK = (33, 33, 33)
    GREY = (100, 100, 100)
    BLUE = (66, 133, 244)
    DASH = (180, 180, 180)

    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    fn = _load_fonts()
    pad = 50

    # Header
    hex_y = 70
    hex_r = 28
    _draw_hexagon(d, pad + hex_r, hex_y, hex_r, BLUE)
    d.text((pad + hex_r - 7, hex_y - 12), "N", font=fn["h2"], fill=WHITE)
    d.text((pad + 70, hex_y - 18), "NEXORA", font=fn["h1"], fill=BLACK)
    d.text((pad + 70, hex_y + 16), "Cloud Hosting  Pakistan", font=fn["sm"], fill=GREY)
    d.text((pad + 70, hex_y + 34), "nexora.host   billing@nexora.host", font=fn["xs"], fill=GREY)

    y = 140

    def dashed_line(yy):
        x = pad
        while x < W - pad:
            d.line([(x, yy), (x + 4, yy)], fill=DASH, width=1)
            x += 8

    dashed_line(y)
    y += 22

    def detail_row(left, right):
        nonlocal y
        d.text((pad, y), left, font=fn["reg"], fill=GREY)
        d.text((W - pad - d.textlength(right, font=fn["reg"]), y), right, font=fn["reg"], fill=BLACK)
        y += 24

    detail_row("Invoice", invoice_id)
    detail_row("Date", datetime.now(timezone.utc).strftime("%a, %b %d, %Y,  %H:%M:%S %Z"))
    detail_row("Cashier", cashier)
    detail_row("Customer", customer)
    detail_row("Status", status)

    y += 10
    dashed_line(y)
    y += 22

    # Table header
    d.text((pad, y), "ITEM", font=fn["sm"], fill=GREY)
    d.text((W // 2 - 10, y), "QTY", font=fn["sm"], fill=GREY)
    d.text((W - pad - d.textlength("AMOUNT", font=fn["sm"]), y), "AMOUNT", font=fn["sm"], fill=GREY)
    y += 22
    dashed_line(y)
    y += 16

    subtotal = 0.0
    for item, qty, unit_price in items:
        line_total = unit_price * qty
        subtotal += line_total
        d.text((pad, y), item[:40], font=fn["reg"], fill=BLACK)
        d.text((W // 2 - 10, y), str(qty), font=fn["reg"], fill=BLACK)
        amount_w = d.textlength(f"${line_total:,.2f}", font=fn["reg"])
        d.text((W - pad - amount_w, y), f"${line_total:,.2f}", font=fn["reg"], fill=BLACK)
        y += 34

    dashed_line(y)
    y += 18

    def total_row(left, right, bold=False, color=BLACK):
        nonlocal y
        font = fn["h2"] if bold else fn["reg"]
        d.text((pad, y), left, font=font, fill=color)
        right_w = d.textlength(right, font=font)
        d.text((W - pad - right_w, y), right, font=font, fill=color)
        y += 26

    total_row("Price", f"${(subtotal if price is None else price):,.2f}")
    total_row("Real Price", f"${real_price:,.2f}")
    total_row("Discount", f"-${discount:,.2f}")
    y += 6
    d.line([(pad, y), (W - pad, y)], fill=BLACK, width=2)
    y += 14
    total_row("FINAL PRICE", f"${final_price:,.2f}", bold=True)
    y += 10

    barcode_img = _make_barcode(invoice_id)
    bw, bh = barcode_img.size
    target_w = W - 2 * pad
    barcode_img = barcode_img.resize((target_w, int(bh * target_w / bw)), Image.LANCZOS)
    img.paste(barcode_img, (pad, y))
    y += barcode_img.height + 10

    barcode_text = invoice_id
    btw = d.textlength(barcode_text, font=fn["reg"])
    d.text(((W - btw) // 2, y), barcode_text, font=fn["reg"], fill=BLACK)
    y += 28

    d.text((pad, y), "Thank you for choosing NEXORA", font=fn["sm"], fill=GREY)
    y += 18
    d.text((pad, y), "Keep this slip for warranty & support", font=fn["xs"], fill=GREY)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def _summary_embed(
    invoice_id: str,
    customer: discord.Member,
    cashier: str,
    plan: str,
    price: float,
    discount: float,
    real_price: float,
    final_price: float,
    addons: str,
    delivery_type: str,
    status: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Nexora Invoice — {invoice_id}",
        description="A professional receipt has been generated for the selected customer.",
        color=ACCENT_EMBED,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Customer", value=customer.mention, inline=True)
    embed.add_field(name="Cashier", value=cashier, inline=True)
    embed.add_field(name="Plan", value=plan, inline=True)
    embed.add_field(name="Price", value=f"${price:,.2f}", inline=True)
    embed.add_field(name="Discount", value=f"${discount:,.2f}", inline=True)
    embed.add_field(name="Real Price", value=f"${real_price:,.2f}", inline=True)
    embed.add_field(name="Final Price", value=f"**${final_price:,.2f}**", inline=True)
    embed.add_field(name="Addons", value=addons or "None", inline=False)
    embed.add_field(name="Delivery Type", value=delivery_type, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.set_footer(text="Nexora Cloud — Premium Cloud Hosting")
    embed.set_thumbnail(url=customer.display_avatar.url)
    return embed


class Receipt(commands.Cog):
    """Receipt / invoice generation with manually entered pricing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="receipt", description="Generate a Nexora receipt with custom pricing and delivery.")
    @app_commands.describe(
        customer="Select the customer user",
        plan="Plan name or description",
        price="Listed plan price in dollars",
        discount="Discount amount in dollars",
        invoice_id="Invoice ID shown on the receipt",
        final_price="Final amount charged in dollars",
        real_price="Real price before discount in dollars",
        addons="Addon names or details, separated by commas",
        delivery_type="Where to deliver the receipt",
        status="Payment status (default PAID)",
    )
    @app_commands.choices(delivery_type=DELIVERY_CHOICES)
    @app_commands.checks.has_permissions(administrator=True)
    async def receipt(
        self,
        interaction: discord.Interaction,
        customer: discord.Member,
        plan: str,
        price: float,
        discount: float,
        invoice_id: str,
        final_price: float,
        real_price: float,
        addons: str = "None",
        delivery_type: app_commands.Choice[str] = None,
        status: str = "PAID",
    ):
        await interaction.response.defer(ephemeral=True)

        inv_id = invoice_id.strip()
        cashier_name = interaction.user.display_name
        delivery_value = delivery_type.value if delivery_type else "admin_channel"
        delivery_label = next(
            (choice.name for choice in DELIVERY_CHOICES if choice.value == delivery_value),
            "Admin DM + Channel",
        )

        if not inv_id:
            return await interaction.followup.send("Invoice ID cannot be empty.", ephemeral=True)
        if not plan.strip():
            return await interaction.followup.send("Plan cannot be empty.", ephemeral=True)
        if min(price, discount, final_price, real_price) < 0:
            return await interaction.followup.send("Price values cannot be negative.", ephemeral=True)

        addon_text = addons.strip() or "None"
        items = [(plan.strip(), 1, price)]
        if addon_text.lower() not in {"none", "no", "n/a"}:
            items.append((f"Addons: {addon_text}", 1, max(0.0, real_price - price)))

        buf = generate_invoice(
            invoice_id=inv_id,
            customer=customer.display_name,
            cashier=cashier_name,
            items=items,
            price=price,
            discount=discount,
            real_price=real_price,
            final_price=final_price,
            status=status,
        )
        file = discord.File(buf, filename=f"{inv_id}.png")

        summary = _summary_embed(
            inv_id,
            customer,
            cashier_name,
            plan.strip(),
            price,
            discount,
            real_price,
            final_price,
            addon_text,
            delivery_label,
            status,
        )

        def fresh_file():
            buf.seek(0)
            return discord.File(buf, filename=f"{inv_id}.png")

        async def send_to_user(user: discord.User):
            try:
                await user.send(embed=summary, file=fresh_file())
            except discord.Forbidden:
                await interaction.followup.send(f"Could not DM {user.mention}. Receipt posted here instead.", ephemeral=True)
                await interaction.channel.send(embed=summary, file=fresh_file())

        async def post_in_channel(channel: discord.TextChannel):
            await channel.send(embed=summary, file=fresh_file())

        if delivery_value == "admin_dm":
            await interaction.user.send(embed=summary, file=fresh_file())
            await interaction.followup.send(f"Receipt sent to your DM. Invoice `{inv_id}` — Final price: **${final_price:,.2f}**", ephemeral=True)
        elif delivery_value == "channel":
            await post_in_channel(interaction.channel)
            await interaction.followup.send(f"Receipt posted in this channel. Invoice `{inv_id}` — Final price: **${final_price:,.2f}**", ephemeral=True)
        elif delivery_value == "customer_dm":
            await send_to_user(customer)
            await interaction.followup.send(f"Receipt sent to {customer.mention} via DM. Invoice `{inv_id}` — Final price: **${final_price:,.2f}**", ephemeral=True)
        elif delivery_value == "admin_channel":
            await interaction.user.send(embed=summary, file=fresh_file())
            await post_in_channel(interaction.channel)
            await interaction.followup.send(f"Receipt sent to your DM and posted in this channel. Invoice `{inv_id}` — Final price: **${final_price:,.2f}**", ephemeral=True)
        elif delivery_value == "all":
            await send_to_user(customer)
            await interaction.user.send(embed=summary, file=fresh_file())
            await post_in_channel(interaction.channel)
            await interaction.followup.send(f"Receipt sent to customer, admin DM, and channel. Invoice `{inv_id}` — Final price: **${final_price:,.2f}**", ephemeral=True)
        else:
            await interaction.user.send(embed=summary, file=fresh_file())
            await post_in_channel(interaction.channel)
            await interaction.followup.send(f"Receipt sent to admin and channel. Invoice `{inv_id}` — Final price: **${final_price:,.2f}**", ephemeral=True)

    @receipt.error
    async def receipt_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = (
            "Error: You need Administrator permission."
            if isinstance(error, app_commands.MissingPermissions)
            else f"Error: `{error}`"
        )
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Receipt(bot))
