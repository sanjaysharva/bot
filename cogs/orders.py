"""
cogs/orders.py — Nexora Cloud
/complete_order  —  mark an order complete and optionally notify the customer
"""

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

PLANS = [
    app_commands.Choice(name="Starter",    value="Starter"),
    app_commands.Choice(name="Pro",        value="Pro"),
    app_commands.Choice(name="Business",   value="Business"),
    app_commands.Choice(name="Enterprise", value="Enterprise"),
    app_commands.Choice(name="Custom",     value="Custom"),
]

SPECS = [
    app_commands.Choice(name="1 vCPU / 1GB RAM",   value="1 vCPU / 1GB RAM"),
    app_commands.Choice(name="2 vCPU / 4GB RAM",   value="2 vCPU / 4GB RAM"),
    app_commands.Choice(name="4 vCPU / 8GB RAM",   value="4 vCPU / 8GB RAM"),
    app_commands.Choice(name="8 vCPU / 16GB RAM",  value="8 vCPU / 16GB RAM"),
    app_commands.Choice(name="16 vCPU / 32GB RAM", value="16 vCPU / 32GB RAM"),
    app_commands.Choice(name="Custom Spec",         value="Custom Spec"),
]


class Orders(commands.Cog):
    """Order management commands for Nexora Cloud."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="complete_order",
        description="Mark an order as complete and optionally notify the customer via DM."
    )
    @app_commands.describe(
        username="Customer's name (for display on the embed)",
        plan="Plan ordered",
        spec="Server specification",
        paid="Has the customer paid? (optional, default: yes)",
        user="Tag the Discord user to DM a completion notice (optional)",
        notes="Additional order notes (optional)"
    )
    @app_commands.choices(plan=PLANS, spec=SPECS)
    @app_commands.checks.has_permissions(administrator=True)
    async def complete_order(
        self,
        interaction: discord.Interaction,
        username: str,
        plan: app_commands.Choice[str],
        spec: app_commands.Choice[str],
        paid: bool = True,
        user: discord.User = None,
        notes: str = ""
    ):
        await interaction.response.defer(ephemeral=False)

        order_id     = str(int(datetime.utcnow().timestamp()))[-6:]
        status_label = "Paid" if paid else "Unpaid"

        # ── Channel embed ──────────────────────────────────────────────────────
        embed = discord.Embed(
            title="Order Completed — Nexora Cloud",
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Customer",   value=username,      inline=True)
        embed.add_field(name="Order ID",   value=f"#{order_id}", inline=True)
        embed.add_field(name="Plan",       value=plan.value,    inline=True)
        embed.add_field(name="Spec",       value=spec.value,    inline=True)
        embed.add_field(name="Payment",    value=status_label,  inline=True)
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        embed.set_footer(text=f"Completed by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

        # ── DM customer ────────────────────────────────────────────────────────
        if user:
            dm_embed = discord.Embed(
                title="Your Nexora Cloud Order is Complete!",
                description=(
                    f"Hey **{username}**, great news — your order is ready!\n\n"
                    f"**Plan:** {plan.value}\n"
                    f"**Spec:** {spec.value}\n"
                    f"**Status:** {status_label}\n"
                    + (f"**Notes:** {notes}\n" if notes else "")
                    + f"\nOrder ID: `#{order_id}`\n\n"
                    f"Questions? Open a support ticket anytime.\n"
                    f"Thank you for choosing **Nexora Cloud**!"
                ),
                color=0x22C55E,
                timestamp=datetime.utcnow()
            )
            dm_embed.set_author(
                name="Nexora Cloud",
                icon_url=(interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
            )
            try:
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                await interaction.followup.send(
                    "Warning: Could not DM the user — their DMs are closed.",
                    ephemeral=True
                )

    @complete_order.error
    async def complete_order_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = ("Error: You need Administrator permission." if isinstance(error, app_commands.MissingPermissions)
               else f"Error: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Orders(bot))
