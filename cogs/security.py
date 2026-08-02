"""
cogs/security.py — Nexora Cloud
Security & moderation commands. Prefix-based: audit log, strikes, backup, suspicious flags.
Slash-based: mute, unmute, report.
"""

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import guild_data, save_guild, log_audit, WARNING, DANGER, PURPLE, SUCCESS


class Security(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !audit_log ─────────────────────────────────────────────────────────────────
    @commands.command(name="audit_log", help="Show last recorded bot actions.")
    @commands.has_permissions(manage_guild=True)
    async def audit_log(self, ctx: commands.Context):
        data = guild_data(ctx.guild.id)
        audits = data.get("audits", [])[-10:]
        if not audits:
            return await ctx.send("No audit entries yet.")
        lines = []
        for a in audits:
            t = a.get("time", "")[:16].replace("T", " ")
            lines.append(f"`[{t}]` **{a['action']}** — {a['user']} → {a.get('target', '')}")
        embed = discord.Embed(title="Bot Audit Log", description="\n".join(lines), color=PURPLE, timestamp=datetime.now(timezone.utc))
        await ctx.send(embed=embed)

    # ── /mute ──────────────────────────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout (mute) a member for a number of minutes.")
    @app_commands.describe(user="Member", minutes="Timeout minutes", reason="Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "No reason given"):
        if not (1 <= minutes <= 40320):
            return await interaction.response.send_message("Error: Minutes must be 1–40320.", ephemeral=True)
        await user.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"{user.mention} muted for **{minutes} minutes**.\nReason: {reason}", ephemeral=True)

    # ── /unmute ────────────────────────────────────────────────────────────────────
    @app_commands.command(name="unmute", description="Remove timeout from a member.")
    @app_commands.describe(user="Member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        await user.timeout(None)
        await interaction.response.send_message(f"{user.mention} has been unmuted.", ephemeral=True)

    # ── !strikes ───────────────────────────────────────────────────────────────────
    @commands.command(name="strikes", help="View a member's strike history. Usage: !strikes @user")
    @commands.has_permissions(kick_members=True)
    async def strikes(self, ctx: commands.Context, user: discord.Member):
        data = guild_data(ctx.guild.id)
        s = data.get("strikes", {}).get(str(user.id), [])
        if not s:
            return await ctx.send(f"{user.mention} has no strikes.")
        embed = discord.Embed(title=f"Strikes — {user.display_name}", description=f"Total strikes: **{len(s)}**", color=WARNING, timestamp=datetime.now(timezone.utc))
        for i, strike in enumerate(s, 1):
            embed.add_field(name=f"Strike #{i}", value=strike, inline=False)
        await ctx.send(embed=embed)

    # ── !add_strike ──────────────────────────────────────────────────────────────────
    @commands.command(name="add_strike", help="Add a strike to a member. Usage: !add_strike @user <reason>")
    @commands.has_permissions(kick_members=True)
    async def add_strike(self, ctx: commands.Context, user: discord.Member, *, reason: str):
        data = guild_data(ctx.guild.id)
        data["strikes"].setdefault(str(user.id), []).append(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')} — {reason} (by {ctx.author.display_name})")
        save_guild(ctx.guild.id, data)
        await ctx.send(f"Strike added to {user.mention}.\nReason: {reason}")

    # ── /report ──────────────────────────────────────────────────────────────────────
    @app_commands.command(name="report", description="Submit a staff report about a user.")
    @app_commands.describe(user="User", reason="Reason")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def report(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        log_audit(interaction.guild.id, "user_report", str(interaction.user), str(user), reason)
        await interaction.response.send_message(f"Report filed against {user.mention}.\nReason: {reason}", ephemeral=True)

    # ── !backup ──────────────────────────────────────────────────────────────────────
    @commands.command(name="backup", help="Trigger a backup reminder/report.")
    @commands.has_permissions(manage_guild=True)
    async def backup(self, ctx: commands.Context):
        embed = discord.Embed(title="Backup Check", description="Critical data backup reminder triggered.\n\nPlease confirm all customer databases and configs are backed up today.", color=SUCCESS, timestamp=datetime.now(timezone.utc))
        await ctx.send(embed=embed)

    # ── !suspicious ──────────────────────────────────────────────────────────────────
    @commands.command(name="suspicious", help="Flag a suspicious account for security review. Usage: !suspicious @user <reason>")
    @commands.has_permissions(manage_guild=True)
    async def suspicious(self, ctx: commands.Context, user: discord.Member, *, reason: str):
        log_audit(ctx.guild.id, "suspicious_flag", str(ctx.author), str(user), reason)
        embed = discord.Embed(title="Suspicious Account Flagged", description=f"**User:** {user.mention} (`{user.id}`)\n**Reason:** {reason}", color=DANGER, timestamp=datetime.now(timezone.utc))
        await ctx.send(embed=embed)

    # ── !clear_strikes ───────────────────────────────────────────────────────────────
    @commands.command(name="clear_strikes", help="Clear all strikes from a member. Usage: !clear_strikes @user")
    @commands.has_permissions(manage_guild=True)
    async def clear_strikes(self, ctx: commands.Context, user: discord.Member):
        data = guild_data(ctx.guild.id)
        data["strikes"].pop(str(user.id), None)
        save_guild(ctx.guild.id, data)
        await ctx.send(f"Strikes cleared for {user.mention}.")

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
    await bot.add_cog(Security(bot))
