"""
cogs/ticket_commands.py — Nexora Cloud
Ticket actions: add, remove, close, transfer, priority, note, claim, tag, escalate, reopen, stats, ping, rename, hold/unhold, bulk close.
"""

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import (
    guild_data, save_guild, log_audit, now_ts, is_ticket, do_close, close_ticket_channel,
    ACCENT, SUCCESS, WARNING, DANGER, CYAN, PURPLE,
    PRIORITY_CHOICES, TAG_CHOICES,
)


class TicketCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /add_member ────────────────────────────────────────────────────────────
    @app_commands.command(name="add_member", description="Add a user to the current ticket channel.")
    @app_commands.describe(user="The user to add")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def add_member(self, interaction: discord.Interaction, user: discord.Member):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"{user.mention} has been added to this ticket by {interaction.user.mention}.",
            color=SUCCESS, timestamp=datetime.now(timezone.utc)))

    # ── /remove_member ───────────────────────────────────────────────────────────
    @app_commands.command(name="remove_member", description="Remove a user from the current ticket channel.")
    @app_commands.describe(user="The user to remove")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def remove_member(self, interaction: discord.Interaction, user: discord.Member):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"{user.mention} has been removed from this ticket by {interaction.user.mention}.",
            color=DANGER, timestamp=datetime.now(timezone.utc)))

    # ── /close ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="close", description="Close the current ticket.")
    @app_commands.describe(reason="Reason for closing (optional)")
    async def close(self, interaction: discord.Interaction, reason: str = "Resolved"):
        await do_close(interaction, reason=reason)

    # ── /ticket_transfer ─────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_transfer", description="Transfer the current ticket to another staff member.")
    @app_commands.describe(new_owner="The staff member taking over")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_transfer(self, interaction: discord.Interaction, new_owner: discord.Member):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        await interaction.channel.send(embed=discord.Embed(
            description=f"Ticket transferred to {new_owner.mention} by {interaction.user.mention}.",
            color=CYAN, timestamp=datetime.now(timezone.utc)))
        await interaction.channel.edit(topic=f"{interaction.channel.topic} | Owner: {new_owner.id}")
        log_audit(interaction.guild.id, "ticket_transfer", str(interaction.user), str(new_owner), interaction.channel.name)
        await interaction.response.send_message(f"Transferred to {new_owner.mention}.", ephemeral=True)

    # ── /ticket_priority ─────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_priority", description="Set the priority of the current ticket.")
    @app_commands.describe(priority="Priority level")
    @app_commands.choices(priority=PRIORITY_CHOICES)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_priority(self, interaction: discord.Interaction, priority: app_commands.Choice[str]):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        await interaction.channel.send(embed=discord.Embed(
            description=f"Priority set to **{priority.value}** by {interaction.user.mention}.",
            color=WARNING if priority.value in ["High", "Critical"] else ACCENT,
            timestamp=datetime.now(timezone.utc)))
        await interaction.response.send_message("Priority updated.", ephemeral=True)

    # ── /ticket_note ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_note", description="Add an internal staff-only note to the current ticket.")
    @app_commands.describe(note="Internal note")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_note(self, interaction: discord.Interaction, note: str):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        embed = discord.Embed(title="Internal Note", description=note, color=PURPLE, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Staff-only — {interaction.user.display_name}")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Internal note added.", ephemeral=True)

    # ── /ticket_claim ────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_claim", description="Claim ownership of the current ticket.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_claim(self, interaction: discord.Interaction):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        cfg = guild_data(interaction.guild.id, "ticket_config")
        tid = self._ticket_id_from_channel(interaction.channel)
        if tid and cfg.get("tickets", {}).get(tid):
            cfg["tickets"][tid]["claimed_by"] = interaction.user.id
            save_guild(interaction.guild.id, cfg, "ticket_config")
        await interaction.channel.send(embed=discord.Embed(
            description=f"**{interaction.user.mention}** claimed this ticket.",
            color=SUCCESS, timestamp=datetime.now(timezone.utc)))
        await interaction.channel.edit(topic=f"{interaction.channel.topic} | Owner: {interaction.user.id}")
        await interaction.response.send_message("Ticket claimed.", ephemeral=True)

    # ── /ticket_tag ──────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_tag", description="Tag the current ticket with a category label.")
    @app_commands.describe(tag="Tag to apply")
    @app_commands.choices(tag=TAG_CHOICES)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_tag(self, interaction: discord.Interaction, tag: app_commands.Choice[str]):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        await interaction.channel.send(embed=discord.Embed(
            description=f"Tag added: **{tag.value}** by {interaction.user.mention}.",
            color=ACCENT, timestamp=datetime.now(timezone.utc)))
        await interaction.response.send_message("Tag applied.", ephemeral=True)

    # ── /ticket_escalate ─────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_escalate", description="Escalate the current ticket to senior staff.")
    @app_commands.describe(reason="Reason for escalation")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_escalate(self, interaction: discord.Interaction, reason: str = "Needs senior attention"):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        await interaction.channel.send(embed=discord.Embed(
            title="Ticket Escalated",
            description=f"**Reason:** {reason}\n**Escalated by:** {interaction.user.mention}\n\nSenior staff, please review.",
            color=DANGER, timestamp=datetime.now(timezone.utc)))
        await interaction.response.send_message("Ticket escalated.", ephemeral=True)

    # ── /ticket_unclaim ──────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_unclaim", description="Unclaim the current ticket.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_unclaim(self, interaction: discord.Interaction):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        cfg = guild_data(interaction.guild.id, "ticket_config")
        tid = self._ticket_id_from_channel(interaction.channel)
        if tid and cfg.get("tickets", {}).get(tid):
            cfg["tickets"][tid]["claimed_by"] = None
            save_guild(interaction.guild.id, cfg, "ticket_config")
        await interaction.channel.send(embed=discord.Embed(
            description=f"Ticket is now unclaimed by {interaction.user.mention}.",
            color=WARNING, timestamp=datetime.now(timezone.utc)))
        await interaction.response.send_message("Ticket unclaimed.", ephemeral=True)

    # ── /ticket_hold ───────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_hold", description="Place the ticket on hold (pauses auto-close).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_hold(self, interaction: discord.Interaction):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        cfg = guild_data(interaction.guild.id, "ticket_config")
        tid = self._ticket_id_from_channel(interaction.channel)
        if tid and cfg.get("tickets", {}).get(tid):
            cfg["tickets"][tid]["status"] = "on-hold"
            save_guild(interaction.guild.id, cfg, "ticket_config")
        await interaction.channel.send(embed=discord.Embed(
            description=f"Ticket placed on hold by {interaction.user.mention}.",
            color=WARNING, timestamp=datetime.now(timezone.utc)))
        await interaction.response.send_message("Ticket is on hold.", ephemeral=True)

    # ── /ticket_unhold ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_unhold", description="Remove the ticket from hold.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_unhold(self, interaction: discord.Interaction):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        cfg = guild_data(interaction.guild.id, "ticket_config")
        tid = self._ticket_id_from_channel(interaction.channel)
        if tid and cfg.get("tickets", {}).get(tid):
            cfg["tickets"][tid]["status"] = "open"
            save_guild(interaction.guild.id, cfg, "ticket_config")
        await interaction.channel.send(embed=discord.Embed(
            description=f"Ticket is now active again by {interaction.user.mention}.",
            color=SUCCESS, timestamp=datetime.now(timezone.utc)))
        await interaction.response.send_message("Ticket taken off hold.", ephemeral=True)

    # ── /ticket_list ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_list", description="List all open tickets.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_list(self, interaction: discord.Interaction):
        tickets = [c for c in interaction.guild.channels if c.name.startswith("ticket-")]
        if not tickets:
            return await interaction.response.send_message("No open tickets.", ephemeral=True)
        lines = [f"{c.mention} — `#{c.name.split('-')[-1]}`" for c in tickets[:25]]
        embed = discord.Embed(
            title="Open Tickets",
            description=f"**Total open:** {len(tickets)}\n\n" + "\n".join(lines),
            color=ACCENT, timestamp=datetime.now(timezone.utc))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /ticket_bulk_close ───────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_bulk_close", description="Close all open tickets matching a reason prefix.")
    @app_commands.describe(reason="Reason applied to all closed tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_bulk_close(self, interaction: discord.Interaction, reason: str = "Bulk close"):
        await interaction.response.defer(ephemeral=True)
        tickets = [c for c in interaction.guild.channels if c.name.startswith("ticket-")]
        if not tickets:
            return await interaction.followup.send("No open tickets to close.", ephemeral=True)
        closed = 0
        for channel in tickets:
            if not is_ticket(channel):
                continue
            try:
                await close_ticket_channel(channel, interaction.user, reason)
                closed += 1
            except Exception:
                pass
        await interaction.followup.send(f"Bulk closed **{closed}** ticket(s).", ephemeral=True)

    # ── /ticket_reopen ───────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_reopen", description="Guidance to reopen a recently closed ticket.")
    @app_commands.describe(name="Closed ticket channel name")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_reopen(self, interaction: discord.Interaction, name: str):
        await interaction.response.send_message(
            f"To reopen, manually create a new ticket and reference the old ID `#{name.split('-')[-1]}`. "
            "Or use `/ticket_panel` to let the user open a follow-up ticket.", ephemeral=True)

    # ── /ticket_stats ────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_stats", description="Show advanced ticket statistics.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_stats(self, interaction: discord.Interaction):
        data = guild_data(interaction.guild.id)
        kpi = data.get("kpi", {})
        cfg = guild_data(interaction.guild.id, "ticket_config")
        tickets = cfg.get("tickets", {})
        open_count = len([c for c in interaction.guild.channels if c.name.startswith("ticket-")])
        closed_count = len([t for t in tickets.values() if t.get("status") in ("closed", "resolved")])
        claimed = len([t for t in tickets.values() if t.get("claimed_by")])
        on_hold = len([t for t in tickets.values() if t.get("status") == "on-hold"])
        embed = discord.Embed(
            title="Advanced Ticket Statistics",
            description="Real-time metrics for the ticket system.",
            color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Open", value=str(open_count), inline=True)
        embed.add_field(name="Closed", value=str(closed_count), inline=True)
        embed.add_field(name="Claimed", value=str(claimed), inline=True)
        embed.add_field(name="On Hold", value=str(on_hold), inline=True)
        embed.add_field(name="Resolved Today", value=str(kpi.get('tickets', 0)), inline=True)
        embed.add_field(name="Blacklisted", value=str(len(cfg.get("blacklist", []))), inline=True)
        embed.set_footer(text=f"Updated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _ticket_id_from_channel(self, channel):
        if not channel.topic:
            return None
        for part in channel.topic.split("|"):
            part = part.strip()
            if part.startswith("Ticket #"):
                return part.split("#")[-1].strip()
        return None

    # ── /ticket_ping ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_ping", description="Ping the configured ticket staff role in this ticket.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_ping(self, interaction: discord.Interaction):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        cfg = guild_data(interaction.guild.id, "ticket_config")
        role_id = cfg.get("staff_role_id")
        role = interaction.guild.get_role(int(role_id)) if role_id else None
        ping = role.mention if role else "@here"
        await interaction.channel.send(f"{ping} — attention needed in this ticket by {interaction.user.mention}.")
        await interaction.response.send_message("Staff pinged.", ephemeral=True)

    # ── /ticket_rename ───────────────────────────────────────────────────────────
    @app_commands.command(name="ticket_rename", description="Rename the current ticket channel.")
    @app_commands.describe(name="New channel name")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_rename(self, interaction: discord.Interaction, name: str):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        old = interaction.channel.name
        await interaction.channel.edit(name=name)
        await interaction.response.send_message(f"Ticket renamed from `#{old}` to `#{name}`.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = ("Error: You need Manage Channels or Administrator permission."
               if isinstance(error, app_commands.MissingPermissions) else f"Error: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCommands(bot))
