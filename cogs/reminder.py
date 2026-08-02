"""
cogs/reminder.py — Nexora Cloud
/reminder  —  send a reminder DM to a specific user
"""

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands


class Reminder(commands.Cog):
    """Reminder commands for Nexora Cloud."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reminder", description="Send a reminder DM to a specific user.")
    @app_commands.describe(
        user="The user to remind",
        message="The reminder message content",
        reason="Reason for the reminder, e.g. 'Unpaid invoice' or 'Renewal due' (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reminder(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        message: str,
        reason: str = ""
    ):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Reminder from Nexora Cloud",
            description=message,
            color=0xF59E0B,
            timestamp=datetime.utcnow()
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_author(
            name="Nexora Cloud",
            icon_url=(interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
        )
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")

        try:
            await user.send(embed=embed)
            await interaction.followup.send(
                f"Reminder sent to **{user.display_name}**."
                + (f"  Reason: *{reason}*" if reason else ""),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"Could not DM **{user.display_name}** — their DMs may be closed.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error: `{e}`", ephemeral=True)

    @reminder.error
    async def reminder_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = ("Error: You need Administrator permission." if isinstance(error, app_commands.MissingPermissions)
               else f"Error: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
