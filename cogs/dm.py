"""
cogs/dm.py — Nexora Cloud
DM commands: /dm_user, /dm_all, /dm_staff
"""

import asyncio
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import guild_data, ACCENT


class DM(commands.Cog):
    """Direct message commands for Nexora Cloud."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /dm_user ─────────────────────────────────────────────────────────────

    @app_commands.command(name="dm_user", description="Send a direct message to a specific user.")
    @app_commands.describe(
        user="The user to DM",
        message="The message content to send"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def dm_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        message: str
    ):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            description=message,
            color=ACCENT,
            timestamp=datetime.utcnow()
        )
        embed.set_author(
            name="Nexora Cloud",
            icon_url=(interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
        )
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")

        try:
            await user.send(embed=embed)
            await interaction.followup.send(
                f"DM sent to **{user.display_name}**.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"Could not DM **{user.display_name}** — their DMs may be closed.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"Error: `{e}`", ephemeral=True)

    # ─── /dm_all ──────────────────────────────────────────────────────────────

    @app_commands.command(name="dm_all", description="Broadcast a direct message to ALL members in the server.")
    @app_commands.describe(message="The message to broadcast to every member")
    @app_commands.checks.has_permissions(administrator=True)
    async def dm_all(
        self,
        interaction: discord.Interaction,
        message: str
    ):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send(
                "Error: This command must be used inside a server.", ephemeral=True
            )
            return

        embed = discord.Embed(
            description=message,
            color=ACCENT,
            timestamp=datetime.utcnow()
        )
        embed.set_author(
            name="Nexora Cloud",
            icon_url=(interaction.guild.icon.url if interaction.guild.icon else None)
        )
        embed.set_footer(text=f"Broadcast by {interaction.user.display_name}")

        members = [m for m in interaction.guild.members if not m.bot]
        await interaction.followup.send(
            f"Sending DMs to **{len(members)}** members... this may take a moment.",
            ephemeral=True
        )

        sent, failed = 0, 0
        for member in members:
            try:
                await member.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.5)   # rate-limit safety

        await interaction.followup.send(
            f"Broadcast complete!\n"
            f"- Delivered: **{sent}**\n"
            f"- Failed (DMs closed): **{failed}**",
            ephemeral=True
        )

    # ─── /dm_staff ────────────────────────────────────────────────────────────────

    @app_commands.command(name="dm_staff", description="Send a DM to all members with the configured staff role (owner/admins only).")
    @app_commands.describe(
        message="Message to broadcast",
        role="Optional: a specific role to target (defaults to configured ticket staff role)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def dm_staff(
        self,
        interaction: discord.Interaction,
        message: str,
        role: discord.Role = None
    ):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("Error: This command must be used inside a server.", ephemeral=True)
            return

        target_role = role
        if not target_role:
            cfg = guild_data(interaction.guild.id, "ticket_config")
            role_id = cfg.get("staff_role_id")
            if role_id:
                target_role = interaction.guild.get_role(int(role_id))
            if not target_role:
                await interaction.followup.send(
                    "Error: No staff role configured. Run /ticket_setup or /ticket_role, or pass a role manually.",
                    ephemeral=True
                )
                return

        members = [m for m in target_role.members if not m.bot]
        if not members:
            await interaction.followup.send(f"Error: No members found in {target_role.mention}.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Staff Message — Nexora Cloud",
            description=message,
            color=ACCENT,
            timestamp=datetime.utcnow()
        )
        embed.set_author(
            name="Nexora Cloud",
            icon_url=(interaction.guild.icon.url if interaction.guild.icon else None)
        )
        embed.set_footer(text=f"Staff broadcast by {interaction.user.display_name}")

        await interaction.followup.send(
            f"Sending DMs to **{len(members)}** staff member(s) in {target_role.mention}...",
            ephemeral=True
        )

        sent, failed = 0, 0
        for member in members:
            try:
                await member.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.5)

        await interaction.followup.send(
            f"Staff DM broadcast complete!\n"
            f"- Role: {target_role.mention}\n"
            f"- Delivered: **{sent}**\n"
            f"- Failed (DMs closed): **{failed}**",
            ephemeral=True
        )

    # ─── Error handler ────────────────────────────────────────────────────────

    @dm_user.error
    @dm_all.error
    @dm_staff.error
    async def dm_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "Error: You need Administrator permission to use this command."
        else:
            msg = f"Error: `{error}`"

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DM(bot))
