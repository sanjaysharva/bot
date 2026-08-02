"""
cogs/customer_relations.py — Nexora Cloud
Customer relations commands. Slash: status page, feedback requests, NPS, CSAT, churn alerts.
Prefix: set status page URL, schedule follow-ups.
"""

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import guild_data, save_guild, ACCENT, WARNING, PURPLE, CYAN


class CustomerRelations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /status_page ─────────────────────────────────────────────────────────────
    @app_commands.command(name="status_page", description="Send the status page link.")
    async def status_page(self, interaction: discord.Interaction):
        data = guild_data(interaction.guild.id)
        url = data.get("status_page", "https://status.nexora.cloud")
        await interaction.response.send_message(f"Nexora Cloud status page: {url}")

    # ── !set_status_page ─────────────────────────────────────────────────────────
    @commands.command(name="set_status_page", help="Set the status page URL. Usage: !set_status_page <url>")
    @commands.has_permissions(manage_guild=True)
    async def set_status_page(self, ctx: commands.Context, url: str):
        data = guild_data(ctx.guild.id)
        data["status_page"] = url
        save_guild(ctx.guild.id, data)
        await ctx.send(f"Status page URL set to {url}.")

    # ── /feedback_request ────────────────────────────────────────────────────────
    @app_commands.command(name="feedback_request", description="Request feedback via DM.")
    @app_commands.describe(user="Customer")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def feedback_request(self, interaction: discord.Interaction, user: discord.User):
        embed = discord.Embed(title="We Value Your Feedback", color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.description = (
            "Thanks for choosing Nexora Cloud!\n\n"
            "We would love to hear about your experience.\n"
            "Reply to this DM with a rating (1–5) and a short comment."
        )
        embed.set_footer(text="Nexora Cloud")
        try:
            await user.send(embed=embed)
            await interaction.response.send_message(f"Feedback request sent to {user.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Error: Could not DM that user.", ephemeral=True)

    # ── !follow_up ─────────────────────────────────────────────────────────────────
    @commands.command(name="follow_up", help="Schedule a customer follow-up. Usage: !follow_up @user YYYY-MM-DD \"<notes>\"")
    @commands.has_permissions(manage_messages=True)
    async def follow_up(self, ctx: commands.Context, user: discord.User, date: str, *, notes: str):
        embed = discord.Embed(title="Follow-Up Scheduled", color=CYAN, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Customer", value=user.mention, inline=True)
        embed.add_field(name="Date", value=date, inline=True)
        embed.add_field(name="Notes", value=notes, inline=False)
        await ctx.send(embed=embed)

    # ── /nps ───────────────────────────────────────────────────────────────────────
    @app_commands.command(name="nps", description="Send a Net Promoter Score survey via DM.")
    @app_commands.describe(user="Customer")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def nps(self, interaction: discord.Interaction, user: discord.User):
        embed = discord.Embed(title="Quick Survey — Nexora Cloud", color=PURPLE, timestamp=datetime.now(timezone.utc))
        embed.description = (
            "On a scale of **0–10**, how likely are you to recommend Nexora Cloud to a friend or colleague?\n\n"
            "Reply with a number and optionally a short reason."
        )
        embed.set_footer(text="Nexora Cloud — Customer Experience")
        try:
            await user.send(embed=embed)
            await interaction.response.send_message(f"NPS survey sent to {user.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Error: Could not DM that user.", ephemeral=True)

    # ── /churn_alert ───────────────────────────────────────────────────────────────
    @app_commands.command(name="churn_alert", description="Flag a customer at risk of leaving.")
    @app_commands.describe(user="Customer", reason="Why they're at risk")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def churn_alert(self, interaction: discord.Interaction, user: discord.User, reason: str):
        embed = discord.Embed(title="Churn Alert", color=WARNING, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Customer", value=user.mention, inline=True)
        embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Suggested Action", value="Follow up within 24 hours", inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /csat ──────────────────────────────────────────────────────────────────────
    @app_commands.command(name="csat", description="Send a CSAT (satisfaction) survey via DM.")
    @app_commands.describe(user="Customer")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def csat(self, interaction: discord.Interaction, user: discord.User):
        embed = discord.Embed(title="Customer Satisfaction Survey", color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.description = (
            "How satisfied were you with your recent support experience?\n\n"
            "Reply with a rating from **1 (Very Dissatisfied)** to **5 (Very Satisfied)** and any comments."
        )
        embed.set_footer(text="Nexora Cloud")
        try:
            await user.send(embed=embed)
            await interaction.response.send_message(f"CSAT survey sent to {user.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Error: Could not DM that user.", ephemeral=True)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You do not have permission for this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Error: Missing required argument `{error.param.name}`. Check `!help {ctx.command.name}`.")
        else:
            await ctx.send(f"Error: `{error}`")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = ("Error: You do not have permission for this command." if isinstance(error, app_commands.MissingPermissions) else f"Error: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomerRelations(bot))
