"""
cogs/tech_ops.py — Nexora Cloud
Technical / DevOps commands. Slash: status, incidents, maintenance, uptime, monitor_alert.
Prefix: deploy notes, IP blacklist/whitelist/lists.
"""

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import guild_data, save_guild, ACCENT, SUCCESS, WARNING, DANGER, STATUS_CHOICES, SEVERITY_CHOICES


class TechOps(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /server_status ─────────────────────────────────────────────────────────
    @app_commands.command(name="server_status", description="Post a service status update.")
    @app_commands.describe(service="Service name", status="Operational / Degraded / Major Outage / Maintenance", message="Details")
    @app_commands.choices(status=STATUS_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def server_status(self, interaction: discord.Interaction, service: str, status: app_commands.Choice[str], message: str = ""):
        color = {"Operational": SUCCESS, "Degraded": WARNING, "Major Outage": DANGER, "Maintenance": ACCENT}[status.value]
        embed = discord.Embed(title=f"Service Status: {service}", color=color, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Status", value=status.value, inline=True)
        if message:
            embed.add_field(name="Details", value=message, inline=False)
        embed.set_footer(text="Nexora Cloud — Status Update")
        await interaction.response.send_message(embed=embed)

    # ── /incident ───────────────────────────────────────────────────────────────
    @app_commands.command(name="incident", description="Declare a technical incident.")
    @app_commands.describe(service="Affected service", severity="P1–P4", description="What happened")
    @app_commands.choices(severity=SEVERITY_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def incident(self, interaction: discord.Interaction, service: str, severity: app_commands.Choice[str], description: str):
        embed = discord.Embed(title=f"Incident Declared: {service}", color=DANGER, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Severity", value=severity.value, inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text=f"Declared by {interaction.user.display_name}")
        await interaction.response.send_message(content="@here", embed=embed)

    # ── /maintenance ────────────────────────────────────────────────────────────
    @app_commands.command(name="maintenance", description="Announce scheduled maintenance.")
    @app_commands.describe(service="Service", duration="Duration", window="Time window", notes="Notes")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def maintenance(self, interaction: discord.Interaction, service: str, duration: str, window: str, notes: str = ""):
        embed = discord.Embed(title=f"Scheduled Maintenance: {service}", color=WARNING, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Window", value=window, inline=True)
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        embed.set_footer(text="Nexora Cloud — Maintenance")
        await interaction.response.send_message(content="@here", embed=embed)

    # ── !deploy_note ───────────────────────────────────────────────────────────
    @commands.command(name="deploy_note", help="Log a deployment note. Usage: !deploy_note \"<version>\" \"<notes>\"")
    @commands.has_permissions(manage_messages=True)
    async def deploy_note(self, ctx: commands.Context, version: str, *, notes: str):
        data = guild_data(ctx.guild.id)
        data.setdefault("deployments", []).append({
            "version": version,
            "notes": notes,
            "by": ctx.author.display_name,
            "at": datetime.now(timezone.utc).isoformat()
        })
        save_guild(ctx.guild.id, data)
        embed = discord.Embed(title=f"Deployment Note — {version}", description=notes, color=SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Logged by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ── /monitor_alert ──────────────────────────────────────────────────────────
    @app_commands.command(name="monitor_alert", description="Send a formatted monitoring alert.")
    @app_commands.describe(service="Service", severity="P1–P4", message="Alert message")
    @app_commands.choices(severity=SEVERITY_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def monitor_alert(self, interaction: discord.Interaction, service: str, severity: app_commands.Choice[str], message: str):
        embed = discord.Embed(title=f"Monitoring Alert: {service}", color=DANGER, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Severity", value=severity.value, inline=True)
        embed.add_field(name="Message", value=message, inline=False)
        await interaction.response.send_message(content="@here", embed=embed)

    # ── /uptime ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="uptime", description="Show bot uptime.")
    async def uptime(self, interaction: discord.Interaction):
        delta = datetime.now(timezone.utc) - interaction.client.started_at
        await interaction.response.send_message(f"Bot uptime: `{delta}`")

    # ── !blacklist_ip ───────────────────────────────────────────────────────────
    @commands.command(name="blacklist_ip", help="Add an IP to the blacklist. Usage: !blacklist_ip <ip>")
    @commands.has_permissions(manage_guild=True)
    async def blacklist_ip(self, ctx: commands.Context, ip: str):
        data = guild_data(ctx.guild.id)
        bl = data.setdefault("blacklist", [])
        if ip in bl:
            return await ctx.send(f"IP `{ip}` is already blacklisted.")
        bl.append(ip)
        save_guild(ctx.guild.id, data)
        await ctx.send(f"IP `{ip}` added to the blacklist.")

    # ── !whitelist_ip ───────────────────────────────────────────────────────────
    @commands.command(name="whitelist_ip", help="Add an IP to the whitelist. Usage: !whitelist_ip <ip>")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_ip(self, ctx: commands.Context, ip: str):
        data = guild_data(ctx.guild.id)
        wl = data.setdefault("whitelist", [])
        if ip in wl:
            return await ctx.send(f"IP `{ip}` is already whitelisted.")
        wl.append(ip)
        save_guild(ctx.guild.id, data)
        await ctx.send(f"IP `{ip}` added to the whitelist.")

    # ── !ip_list ────────────────────────────────────────────────────────────────
    @commands.command(name="ip_list", help="Show the blacklisted and whitelisted IPs.")
    @commands.has_permissions(manage_guild=True)
    async def ip_list(self, ctx: commands.Context):
        data = guild_data(ctx.guild.id)
        bl = data.get("blacklist", [])
        wl = data.get("whitelist", [])
        embed = discord.Embed(title="IP Lists", color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Blacklist", value="\n".join(f"`{ip}`" for ip in bl) or "Empty", inline=True)
        embed.add_field(name="Whitelist", value="\n".join(f"`{ip}`" for ip in wl) or "Empty", inline=True)
        await ctx.send(embed=embed)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You do not have permission for this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Error: Missing required argument `{error.param.name}`. Check `!help {ctx.command.name}`.")
        else:
            await ctx.send(f"Error: `{error}`")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = ("Error: You don't have permission for this command." if isinstance(error, app_commands.MissingPermissions) else f"Error: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    bot.started_at = datetime.now(timezone.utc)
    await bot.add_cog(TechOps(bot))
