"""
cogs/receipt.py — Nexora Cloud
Create receipt records around a bill image supplied by an administrator.
The bot does not generate or modify the bill image.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands


DELIVERY_CHOICES = [
    app_commands.Choice(name="Admin DM only", value="admin_dm"),
    app_commands.Choice(name="Post in this channel", value="channel"),
    app_commands.Choice(name="Customer DM only", value="customer_dm"),
    app_commands.Choice(name="Admin DM + Channel", value="admin_channel"),
    app_commands.Choice(name="Customer + Channel + Admin", value="all"),
]

ACCENT_EMBED = 0x2563EB
WARNING_EMBED = 0xF59E0B


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _attachment_is_image(attachment: discord.Attachment) -> bool:
    if attachment.content_type:
        return attachment.content_type.startswith("image/")
    return attachment.filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    )


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
    bill_image_url: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Nexora Receipt — {invoice_id}",
        description="Receipt details supplied by the administrator. The bill image was not generated or modified by Nexora.",
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
    embed.set_image(url=bill_image_url)
    embed.set_footer(text="Nexora Cloud — Supplied Bill Image")
    embed.set_thumbnail(url=customer.display_avatar.url)
    return embed


class Receipt(commands.Cog):
    """Receipt records that use an administrator-supplied bill image."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="receipt",
        description="Record receipt details and attach an uploaded or linked bill image.",
    )
    @app_commands.describe(
        customer="Select the customer user",
        plan="Plan name or description",
        price="Listed plan price in dollars",
        discount="Discount amount in dollars",
        invoice_id="Invoice ID shown on the receipt",
        final_price="Final amount charged in dollars",
        real_price="Real price before discount in dollars",
        addons="Addon names or details, separated by commas",
        bill_image="Upload the bill image",
        bill_image_url="Link to the bill image instead of uploading it",
        delivery_type="Where to deliver the receipt",
        status="Payment status, for example PAID",
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
        bill_image: discord.Attachment = None,
        bill_image_url: str = "",
        delivery_type: app_commands.Choice[str] = None,
        status: str = "PAID",
    ):
        await interaction.response.defer(ephemeral=True)

        inv_id = invoice_id.strip()
        plan_text = plan.strip()
        link_text = bill_image_url.strip()
        cashier_name = interaction.user.display_name
        delivery_value = delivery_type.value if delivery_type else "admin_channel"
        delivery_label = next(
            (choice.name for choice in DELIVERY_CHOICES if choice.value == delivery_value),
            "Admin DM + Channel",
        )

        if not inv_id:
            return await interaction.followup.send("Invoice ID cannot be empty.", ephemeral=True)
        if not plan_text:
            return await interaction.followup.send("Plan cannot be empty.", ephemeral=True)
        if min(price, discount, final_price, real_price) < 0:
            return await interaction.followup.send(
                "Price values cannot be negative.",
                ephemeral=True,
            )
        if bill_image and link_text:
            return await interaction.followup.send(
                "Provide either an uploaded bill image or a bill image link, not both.",
                ephemeral=True,
            )
        if not bill_image and not link_text:
            return await interaction.followup.send(
                "You must upload a bill image or provide a bill image link.",
                ephemeral=True,
            )
        if bill_image and not _attachment_is_image(bill_image):
            return await interaction.followup.send(
                "The uploaded file must be an image.",
                ephemeral=True,
            )
        if link_text and not _valid_http_url(link_text):
            return await interaction.followup.send(
                "Bill image link must be a valid http:// or https:// URL.",
                ephemeral=True,
            )

        bill_url = bill_image.url if bill_image else link_text
        addon_text = addons.strip() or "None"
        summary = _summary_embed(
            inv_id,
            customer,
            cashier_name,
            plan_text,
            price,
            discount,
            real_price,
            final_price,
            addon_text,
            delivery_label,
            status.strip() or "PAID",
            bill_url,
        )

        async def send_to_user(user: discord.User | discord.Member):
            try:
                await user.send(embed=summary)
            except discord.Forbidden:
                await interaction.followup.send(
                    f"Could not DM {user.mention}. Receipt posted here instead.",
                    ephemeral=True,
                )
                await interaction.channel.send(embed=summary)

        async def post_in_channel(channel):
            await channel.send(embed=summary)

        if delivery_value == "admin_dm":
            await interaction.user.send(embed=summary)
            destination = "your DM"
        elif delivery_value == "channel":
            await post_in_channel(interaction.channel)
            destination = "this channel"
        elif delivery_value == "customer_dm":
            await send_to_user(customer)
            destination = f"{customer.mention}'s DM"
        elif delivery_value == "admin_channel":
            await interaction.user.send(embed=summary)
            await post_in_channel(interaction.channel)
            destination = "your DM and this channel"
        elif delivery_value == "all":
            await send_to_user(customer)
            await interaction.user.send(embed=summary)
            await post_in_channel(interaction.channel)
            destination = "the customer, your DM, and this channel"
        else:
            await interaction.user.send(embed=summary)
            await post_in_channel(interaction.channel)
            destination = "your DM and this channel"

        await interaction.followup.send(
            f"Receipt recorded and delivered to {destination}. "
            f"Invoice `{inv_id}` — Final price: **${final_price:,.2f}**",
            ephemeral=True,
        )

    @receipt.error
    async def receipt_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        message = (
            "Error: You need Administrator permission."
            if isinstance(error, app_commands.MissingPermissions)
            else f"Error: `{error}`"
        )
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Receipt(bot))
