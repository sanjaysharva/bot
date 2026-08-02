"""
cogs/admin.py — Nexora Cloud
Admin & utility commands. Slash: serverinfo, userinfo, botinfo, ping, purge, warn, kick, ban, unban, poll, giveaway, help.
Prefix: say, embed, announce, slowmode, lock, unlock, remind.
"""

import asyncio
import os
import platform
import random
import textwrap
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands


# ─── Embed helpers ────────────────────────────────────────────────────────────

ACCENT  = 0x5865F2
SUCCESS = 0x22C55E
WARNING = 0xF59E0B
DANGER  = 0xEF4444
PURPLE  = 0x8B5CF6


def dt_now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
#   ADVANCED HELP VIEW
# ═══════════════════════════════════════════════════════════════════════════════

HELP_CATEGORIES = {
    "home": {
        "title": "Nexora Cloud — Command Center",
        "description": (
            "Welcome to the **Nexora Cloud** command center.\n\n"
            "Commands are split into two types:\n"
            "**Slash commands** — type `/` to see them; used for public and ticket actions.\n"
            "**Prefix commands** — use `!` prefix; used for admin configuration and management.\n\n"
            "Select a category below to browse available commands and required permissions."
        ),
    },
    "tickets": {
        "title": "Ticket System",
        "description": "Create and manage private support tickets.",
        "slash": [
            ("/ticket_panel", "Post the ticket panel", "Administrator"),
            ("/add_member", "Add user to ticket", "Manage Channels"),
            ("/remove_member", "Remove user from ticket", "Manage Channels"),
            ("/close", "Close ticket with transcript and DM", "Ticket member"),
            ("/ticket_transfer", "Transfer ticket", "Manage Channels"),
            ("/ticket_priority", "Set priority", "Manage Channels"),
            ("/ticket_note", "Internal staff note", "Manage Channels"),
            ("/ticket_claim", "Claim ticket", "Manage Channels"),
            ("/ticket_unclaim", "Unclaim ticket", "Manage Channels"),
            ("/ticket_tag", "Tag ticket", "Manage Channels"),
            ("/ticket_escalate", "Escalate ticket", "Manage Channels"),
            ("/ticket_ping", "Ping staff in ticket", "Manage Channels"),
            ("/ticket_rename", "Rename ticket", "Manage Channels"),
            ("/ticket_hold", "Place ticket on hold", "Manage Channels"),
            ("/ticket_unhold", "Remove hold", "Manage Channels"),
        ],
        "prefix": [
            ("!ticket_setup", "Configure staff role and category", "Administrator"),
            ("!ticket_role", "Set ticket staff role", "Administrator"),
            ("!ticket_category", "Set ticket category", "Administrator"),
            ("!ticket_panel_channel", "Set panel channel", "Administrator"),
            ("!ticket_log_channel", "Set transcript log channel", "Administrator"),
            ("!ticket_embed_setup", "Customize panel embed", "Administrator"),
            ("!ticket_welcome_msg", "Customize ticket welcome message", "Administrator"),
            ("!ticket_config", "Show full configuration", "Administrator"),
            ("!ticket_blacklist", "Blacklist user from tickets", "Administrator"),
            ("!ticket_unblacklist", "Remove user from blacklist", "Administrator"),
            ("!ticket_limit", "Max open tickets per user", "Administrator"),
            ("!ticket_auto_close", "Auto-close after inactivity hours", "Administrator"),
            ("!ticket_rating", "Toggle post-close rating", "Administrator"),
            ("!ticket_list", "List open tickets", "Manage Channels"),
            ("!ticket_bulk_close", "Close all open tickets", "Administrator"),
            ("!ticket_reopen", "Reopen guidance", "Manage Channels"),
            ("!ticket_stats", "Advanced ticket statistics", "Manage Channels"),
        ],
    },
    "orders": {
        "title": "Orders, Receipts & Sales",
        "description": "Manage customer orders, receipts, invoices, and refunds.",
        "slash": [
            ("/receipt", "Generate invoice with fixed plans, addons, and user select", "Administrator"),
            ("/complete_order", "Mark order complete and notify customer", "Administrator"),
            ("/quote", "Generate price quote", "Manage Messages"),
            ("/order_status", "Look up order status", "Everyone"),
        ],
        "prefix": [
            ("!invoice", "Create invoice record", "Manage Messages"),
            ("!refund", "Process refund", "Manage Messages"),
            ("!discount", "Apply discount to order", "Manage Messages"),
            ("!upgrade_order", "Upgrade customer plan", "Manage Messages"),
            ("!cancel_order", "Cancel order", "Manage Messages"),
            ("!sales_report", "Sales summary", "Manage Messages"),
        ],
    },
    "dm": {
        "title": "DM & Reminders",
        "description": "Send direct messages and reminders to users or groups.",
        "slash": [
            ("/dm_user", "DM a specific user", "Administrator"),
            ("/dm_all", "DM all non-bot members", "Administrator"),
            ("/reminder", "Send reminder DM to user", "Administrator"),
        ],
        "prefix": [
            ("!remind", "Set a personal DM reminder", "Everyone"),
            ("!dm_staff <message>", "DM all members of the configured staff role", "Administrator"),
            ("!dmstaff @user <message>", "DM one configured staff member", "Administrator"),
            ("!dm_all <message>", "DM every non-bot member in the server", "Administrator"),
        ],
    },
    "staff": {
        "title": "Staff Operations",
        "description": "Manage the staff role, private workspaces, targets, sales decisions, and daily reports.",
        "slash": [],
        "prefix": [
            ("!staff_role @role", "Set the normal staff role", "Administrator"),
            ("!staffrole_make <role name>", "Create one predefined staff role and save it", "Administrator"),
            ("!staff @user", "Assign staff and create a private workspace", "Administrator"),
            ("!target <number>", "Set the daily target using the 2T + ½T formula", "Administrator"),
            ("!target_status", "Show individual message counts and target progress", "Everyone"),
            ("!sales_representativechannel #channel", "Set the sales-representative announcement channel", "Administrator"),
            ("!sr @role", "Set the sales representative role", "Administrator"),
            ("!invade <serverlink> <owneruserid> <accept|eject>", "Announce a server invasion decision", "Admin or sales role"),
            ("!daily_report channel #channel [hour]", "Configure daily report reminders", "Administrator"),
            ("!daily_report_status", "Show today's report submissions", "Administrator"),
        ],
    },
    "server": {
        "title": "Server Control Panels",
        "description": "Each user links their own Pterodactyl Client API key and gets private server control panels. Admins can still manage a legacy pool.",
        "slash": [],
        "prefix": [
            ("!pterodactyl_setup", "Link your own Pterodactyl panel URL and API key", "Everyone"),
            ("!pterodactyl_servers", "List your own Pterodactyl servers", "Everyone"),
            ("!pterodactyl_test", "Test your Pterodactyl connection", "Everyone"),
            ("!server", "List your Pterodactyl servers and create a private panel", "Everyone"),
            ("!server_list", "List your private server panels", "Everyone"),
            ("!server_info", "Show details for one of your private panels (use channel ID)", "Everyone"),
            ("!server_power", "Send power signal to a private panel server (use channel ID)", "Everyone"),
            ("!server_run", "Send a command to a private panel server (use channel ID)", "Everyone"),
            ("!server_debug", "Debug the ServerPanel cog and your data", "Everyone"),
            ("Upload File", "Click the button in a private panel to choose a folder and upload files", "Everyone"),
            ("!server_add", "Add a server to the admin pool (legacy)", "Administrator"),
            ("!server_import", "Import a Pterodactyl server into the admin pool (legacy)", "Administrator"),
            ("!server_import_all", "Import all Pterodactyl servers into the pool (legacy)", "Administrator"),
            ("!server_remove", "Remove a server from the admin pool", "Administrator"),
            ("!server_pool", "List all servers in the admin pool", "Administrator"),
            ("!server_assign", "Manually assign a pool server to a user", "Administrator"),
            ("!server_unassign", "Return a pool server to the pool", "Administrator"),
            ("!server_edit", "Edit a pool server's IP and password", "Administrator"),
            ("!pterodactyl_link", "Link a pool server to Pterodactyl", "Administrator"),
            ("!server_sync", "Refresh all pool panel statuses from Pterodactyl", "Administrator"),
        ],
    },
    "admin": {
        "title": "Admin & Moderation",
        "description": "Server management, moderation, and utility tools.",
        "slash": [
            ("/serverinfo", "Server statistics", "Everyone"),
            ("/userinfo", "User information", "Everyone"),
            ("/botinfo", "Bot statistics", "Everyone"),
            ("/ping", "Check latency", "Everyone"),
            ("/purge", "Bulk delete messages", "Manage Messages"),
            ("/warn", "Warn member and DM them", "Kick Members"),
            ("/kick", "Kick member", "Kick Members"),
            ("/ban", "Ban member", "Ban Members"),
            ("/unban", "Unban by ID", "Ban Members"),
            ("/poll", "Create reaction poll", "Everyone"),
            ("/giveaway", "Start a giveaway", "Manage Messages"),
            ("/help", "Show this command center", "Everyone"),
        ],
        "prefix": [
            ("!say", "Send bot message to channel", "Manage Messages"),
            ("!embed", "Send custom embed to channel", "Manage Messages"),
            ("!announce", "Post announcement in channel", "Manage Messages"),
            ("!slowmode", "Set channel slowmode", "Manage Channels"),
            ("!lock", "Lock current channel", "Manage Channels"),
            ("!unlock", "Unlock current channel", "Manage Channels"),
        ],
    },
    "tech": {
        "title": "Technical / DevOps",
        "description": "Status updates, incidents, maintenance, and IP management.",
        "slash": [
            ("/server_status", "Post service status", "Manage Messages"),
            ("/incident", "Declare incident", "Manage Messages"),
            ("/maintenance", "Announce maintenance", "Manage Messages"),
            ("/monitor_alert", "Send monitoring alert", "Manage Messages"),
            ("/uptime", "Show bot uptime", "Everyone"),
        ],
        "prefix": [
            ("!deploy_note", "Log deployment note", "Manage Messages"),
            ("!blacklist_ip", "Blacklist an IP", "Manage Server"),
            ("!whitelist_ip", "Whitelist an IP", "Manage Server"),
            ("!ip_list", "Show IP lists", "Manage Server"),
        ],
    },
    "security": {
        "title": "Security & Moderation",
        "description": "Audit logs, strikes, timeouts, and suspicious activity flags.",
        "slash": [
            ("/mute", "Timeout member", "Moderate Members"),
            ("/unmute", "Remove timeout", "Moderate Members"),
            ("/report", "Submit user report", "Manage Messages"),
        ],
        "prefix": [
            ("!audit_log", "Show bot audit log", "Manage Server"),
            ("!strikes", "View member strikes", "Kick Members"),
            ("!add_strike", "Add strike to member", "Kick Members"),
            ("!clear_strikes", "Clear member strikes", "Manage Server"),
            ("!backup", "Backup reminder", "Manage Server"),
            ("!suspicious", "Flag suspicious account", "Manage Server"),
        ],
    },
    "cr": {
        "title": "Customer Relations",
        "description": "Status page, feedback requests, surveys, and churn alerts.",
        "slash": [
            ("/status_page", "Send status page link", "Everyone"),
            ("/feedback_request", "Request feedback via DM", "Manage Messages"),
            ("/nps", "Send NPS survey", "Manage Messages"),
            ("/csat", "Send CSAT survey", "Manage Messages"),
            ("/churn_alert", "Flag churn risk", "Manage Messages"),
        ],
        "prefix": [
            ("!set_status_page", "Set status page URL", "Manage Server"),
            ("!follow_up", "Schedule customer follow-up", "Manage Messages"),
        ],
    },
}


class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{data['title']}",
                value=key,
                description=data['description'][:50]
            )
            for key, data in HELP_CATEGORIES.items()
            if key != "home"
        ]
        options.insert(0, discord.SelectOption(label="Home", value="home", description="Return to overview"))
        super().__init__(placeholder="Select a command category...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        await interaction.response.edit_message(embed=view.build_category_embed(self.values[0]), view=view)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect())
        self.add_item(HelpHomeButton())

    def build_main_embed(self) -> discord.Embed:
        home = HELP_CATEGORIES["home"]
        embed = discord.Embed(
            title=home['title'],
            description=home["description"],
            color=ACCENT,
            timestamp=dt_now()
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
        for key, data in HELP_CATEGORIES.items():
            if key == "home":
                continue
            slash_count = len(data.get("slash", []))
            prefix_count = len(data.get("prefix", []))
            value = f"{data['description']}\n`{slash_count} slash / {prefix_count} prefix`"
            embed.add_field(name=data['title'], value=value, inline=True)
        embed.set_footer(text="Use the dropdown above to explore each category — Nexora Cloud")
        return embed

    def build_category_embed(self, key: str) -> discord.Embed:
        data = HELP_CATEGORIES[key]
        embed = discord.Embed(
            title=data['title'],
            description=data["description"],
            color=ACCENT,
            timestamp=dt_now()
        )
        slash = data.get("slash", [])
        prefix = data.get("prefix", [])
        if slash:
            embed.add_field(
                name="Slash Commands",
                value="\n".join(f"**{cmd}** — {desc}\n`Permission: {perm}`" for cmd, desc, perm in slash)[:1024],
                inline=False
            )
        if prefix:
            embed.add_field(
                name="Prefix Commands",
                value="\n".join(f"**{cmd}** — {desc}\n`Permission: {perm}`" for cmd, desc, perm in prefix)[:1024],
                inline=False
            )
        embed.set_footer(text="Nexora Cloud — Use the dropdown or Home button to navigate")
        return embed


class HelpHomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Home", style=discord.ButtonStyle.primary, custom_id="nexora_help_home")

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        await interaction.response.edit_message(embed=view.build_main_embed(), view=view)


# ═══════════════════════════════════════════════════════════════════════════════
#   COG
# ═══════════════════════════════════════════════════════════════════════════════

class Admin(commands.Cog):
    """Utility, moderation, and staff helper commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /serverinfo ────────────────────────────────────────────────────────────

    @app_commands.command(name="serverinfo", description="Show information about this server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        bots  = sum(1 for m in guild.members if m.bot)
        humans = total - bots if total else 0

        embed = discord.Embed(
            title=f"Server Info — {guild.name}",
            color=ACCENT,
            timestamp=dt_now()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner",      value=guild.owner.mention if guild.owner else "N/A", inline=True)
        embed.add_field(name="Members",    value=f"{total:,}\nHumans: {humans:,}\nBots: {bots:,}", inline=True)
        embed.add_field(name="Channels",   value=f"{len(guild.channels)} total\nText: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}", inline=True)
        embed.add_field(name="Roles",      value=f"{len(guild.roles)} roles", inline=True)
        embed.add_field(name="Boosts",     value=f"Level {guild.premium_tier}  —  {guild.premium_subscription_count or 0} boosts", inline=True)
        embed.add_field(name="Created",    value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"Guild ID: {guild.id}")

        await interaction.response.send_message(embed=embed)

    # ── /userinfo ──────────────────────────────────────────────────────────────

    @app_commands.command(name="userinfo", description="Show information about a user.")
    @app_commands.describe(user="The user to inspect (defaults to you)")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        roles = [r.mention for r in user.roles if not r.is_default()]
        roles_str = ", ".join(roles[:10]) or "None"
        if len(roles) > 10:
            roles_str += f" (+{len(roles)-10} more)"

        embed = discord.Embed(
            title=f"User Info — {user.display_name}",
            color=ACCENT,
            timestamp=dt_now()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Username",  value=f"{user.name}\n{user.mention}", inline=True)
        embed.add_field(name="User ID",   value=f"`{user.id}`", inline=True)
        embed.add_field(name="Status",    value=f"{str(user.status).title()}\nDesktop: {user.desktop_status.name if user.desktop_status else 'N/A'}", inline=True)
        embed.add_field(name="Joined",    value=f"<t:{int(user.joined_at.timestamp())}:R>" if user.joined_at else "N/A", inline=True)
        embed.add_field(name="Created",   value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Roles",     value=roles_str, inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    # ── !say ───────────────────────────────────────────────────────────────────

    @commands.command(name="say", help="Make the bot send a message in a channel. Usage: !say #channel <message>")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        await channel.send(message)
        await ctx.send(f"Message sent to {channel.mention}.")

    # ── !embed ─────────────────────────────────────────────────────────────────

    @commands.command(name="embed", help="Send a custom embed to a channel. Usage: !embed #channel \"<title>\" \"<description>\" [#hexcolor] [\"footer\"]")
    @commands.has_permissions(manage_messages=True)
    async def embed(self, ctx: commands.Context, channel: discord.TextChannel, title: str, description: str, color: str = "#5865F2", *, footer: str = "Nexora Cloud"):
        try:
            c = int(color.lstrip("#"), 16)
        except ValueError:
            c = ACCENT

        em = discord.Embed(title=title, description=description, color=c, timestamp=dt_now())
        em.set_footer(text=footer)
        await channel.send(embed=em)
        await ctx.send(f"Embed sent to {channel.mention}.")

    # ── /purge ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="purge", description="Delete a number of messages from the current channel.")
    @app_commands.describe(amount="Number of messages to delete (1–100)", user="Only delete messages from this user (optional)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int, user: discord.Member = None):
        if not (1 <= amount <= 100):
            await interaction.response.send_message("Error: Amount must be between 1 and 100.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        def check(m: discord.Message):
            if m.pinned:
                return False
            if user:
                return m.author.id == user.id
            return True

        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(f"Deleted **{len(deleted)}** messages.", ephemeral=True)

    # ── /warn ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Warn a member and DM them the reason.")
    @app_commands.describe(user="Member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(kick_members=True)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason given"):
        embed = discord.Embed(
            title="Warning — Nexora Cloud",
            description=(
                f"You have been warned in **{interaction.guild.name}**.\n\n"
                f"**Reason:** {reason}\n"
                f"**Warned by:** {interaction.user.display_name}\n"
                f"**Date:** {dt_now().strftime('%Y-%m-%d %H:%M')} UTC\n\n"
                f"Please review the server rules to avoid further action."
            ),
            color=WARNING,
            timestamp=dt_now()
        )
        embed.set_footer(text="Nexora Cloud")

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

        public = discord.Embed(
            description=f"**{user.mention}** has been warned.\n**Reason:** {reason}",
            color=WARNING,
            timestamp=dt_now()
        )
        await interaction.response.send_message(embed=public)

    # ── /kick ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(user="Member to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason given"):
        await user.kick(reason=reason)
        embed = discord.Embed(
            description=f"**{user.mention}** has been kicked.\n**Reason:** {reason}",
            color=DANGER,
            timestamp=dt_now()
        )
        await interaction.response.send_message(embed=embed)

    # ── /ban ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(user="Member to ban", reason="Reason for the ban", delete_days="Days of messages to delete (0–7, default 0)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason given", delete_days: int = 0):
        if not (0 <= delete_days <= 7):
            await interaction.response.send_message("Error: delete_days must be 0–7.", ephemeral=True)
            return

        await user.ban(reason=reason, delete_message_days=delete_days)
        embed = discord.Embed(
            description=f"**{user.mention}** has been banned.\n**Reason:** {reason}",
            color=DANGER,
            timestamp=dt_now()
        )
        await interaction.response.send_message(embed=embed)

    # ── /unban ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="unban", description="Unban a user by their ID or username.")
    @app_commands.describe(user_id="User ID to unban", reason="Reason for unban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason given"):
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("Error: Invalid user ID.", ephemeral=True)
            return

        user = discord.Object(id=uid)
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(
            description=f"User ID `{uid}` has been unbanned.\n**Reason:** {reason}",
            color=SUCCESS,
            timestamp=dt_now()
        )
        await interaction.response.send_message(embed=embed)

    # ── !slowmode ──────────────────────────────────────────────────────────────

    @commands.command(name="slowmode", help="Set slowmode in the current channel. Usage: !slowmode <seconds>")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        label = "disabled" if seconds == 0 else f"set to {seconds}s"
        await ctx.send(f"Slowmode {label}.")

    # ── !lock ──────────────────────────────────────────────────────────────────

    @commands.command(name="lock", help="Lock the current channel. Usage: !lock [reason]")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, *, reason: str = "No reason given"):
        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            send_messages=False,
            reason=reason
        )
        embed = discord.Embed(
            description=f"Channel locked.\n**Reason:** {reason}",
            color=DANGER,
            timestamp=dt_now()
        )
        await ctx.send(embed=embed)

    # ── !unlock ───────────────────────────────────────────────────────────────

    @commands.command(name="unlock", help="Unlock the current channel.")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            send_messages=None
        )
        await ctx.send("Channel unlocked.")

    # ── /ping ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Check bot latency and uptime.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000, 1)
        embed = discord.Embed(
            title="Pong!",
            description=f"**Latency:** `{latency} ms`\n**Gateway:** Connected",
            color=SUCCESS,
            timestamp=dt_now()
        )
        await interaction.response.send_message(embed=embed)

    # ── /botinfo ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="botinfo", description="Show bot statistics and system info.")
    async def botinfo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Bot Info — Nexora Cloud",
            color=ACCENT,
            timestamp=dt_now()
        )
        embed.add_field(name="Bot Name",   value=self.bot.user.name, inline=True)
        embed.add_field(name="Bot ID",     value=f"`{self.bot.user.id}`", inline=True)
        embed.add_field(name="Servers",    value=f"{len(self.bot.guilds)}", inline=True)
        embed.add_field(name="Latency",    value=f"{round(self.bot.latency * 1000, 1)} ms", inline=True)
        embed.add_field(name="Python",     value=platform.python_version(), inline=True)
        embed.add_field(name="Library",    value=f"discord.py v{discord.__version__}", inline=True)
        embed.set_footer(text="Nexora Cloud — Premium Discord Bot")
        await interaction.response.send_message(embed=embed)

    # ── !announce ───────────────────────────────────────────────────────────────

    @commands.command(name="announce", help="Post an announcement. Usage: !announce #channel \"<title>\" | \"<message>\" [@everyone?]")
    @commands.has_permissions(manage_messages=True)
    async def announce(self, ctx: commands.Context, channel: discord.TextChannel, *, args: str):
        parts = args.split(" | ", 2)
        if len(parts) < 2:
            return await ctx.send("Usage: !announce #channel \"<title>\" | \"<message>\" | @everyone (optional)")
        title, message = parts[0], parts[1]
        mention = "@everyone" if len(parts) > 2 and "everyone" in parts[2].lower() else None
        embed = discord.Embed(title=title, description=message, color=PURPLE, timestamp=dt_now())
        embed.set_footer(text="Nexora Cloud — Official Announcement")
        await channel.send(content=mention, embed=embed)
        await ctx.send(f"Announcement posted in {channel.mention}.")

    # ── /poll ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="poll", description="Create a simple reaction poll with up to 4 options.")
    @app_commands.describe(
        question="Poll question",
        option1="Option 1",
        option2="Option 2",
        option3="Option 3 (optional)",
        option4="Option 4 (optional)"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = "",
        option4: str = ""
    ):
        options = [o for o in (option1, option2, option3, option4) if o.strip()]
        emojis = ["1", "2", "3", "4"]

        desc = "\n".join(f"{emojis[i]}. {opt}" for i, opt in enumerate(options))
        embed = discord.Embed(
            title=f"Poll: {question}",
            description=desc,
            color=ACCENT,
            timestamp=dt_now()
        )
        embed.set_footer(text=f"Poll by {interaction.user.display_name} — React to vote")
        msg = await interaction.channel.send(embed=embed)
        for i in range(len(options)):
            await msg.add_reaction(f"{i+1}\u20e3")  # 1️⃣ 2️⃣ 3️⃣ 4️⃣

        await interaction.response.send_message("Poll created.", ephemeral=True)

    # ── /giveaway ──────────────────────────────────────────────────────────────

    @app_commands.command(name="giveaway", description="Start a simple giveaway with a duration and prize.")
    @app_commands.describe(
        duration_minutes="How long the giveaway lasts in minutes",
        prize="What is being given away",
        winners="Number of winners (default 1, max 5)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def giveaway(
        self,
        interaction: discord.Interaction,
        duration_minutes: int,
        prize: str,
        winners: int = 1
    ):
        if not (1 <= winners <= 5):
            await interaction.response.send_message("Error: Winners must be 1–5.", ephemeral=True)
            return
        if duration_minutes < 1:
            await interaction.response.send_message("Error: Duration must be at least 1 minute.", ephemeral=True)
            return

        end = dt_now() + timedelta(minutes=duration_minutes)
        embed = discord.Embed(
            title="Giveaway!",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{int(end.timestamp())}:R>\n\n"
                f"React with the gift emoji to enter!"
            ),
            color=PURPLE,
            timestamp=end
        )
        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")
        msg = await interaction.channel.send(content="**GIVEAWAY**", embed=embed)
        await msg.add_reaction("🎁")
        await interaction.response.send_message("Giveaway started!", ephemeral=True)

        await asyncio.sleep(duration_minutes * 60)

        try:
            msg = await interaction.channel.fetch_message(msg.id)
            reaction = discord.utils.get(msg.reactions, emoji="🎁")
            if not reaction or not reaction.users:
                await msg.reply("No one entered the giveaway.")
                return

            users = [u async for u in reaction.users() if not u.bot]
            if not users:
                await msg.reply("No valid entries found.")
                return

            picked = random.sample(users, min(winners, len(users)))
            mentions = ", ".join(u.mention for u in picked)
            await msg.reply(f"Congratulations {mentions}! You won: **{prize}**!")
        except Exception:
            pass

    # ── !remind ────────────────────────────────────────────────────────────────

    @commands.command(name="remind", help="Set a personal reminder DM. Usage: !remind <minutes> <message>")
    async def remind(self, ctx: commands.Context, minutes: int, *, message: str):
        if minutes < 1 or minutes > 10080:
            return await ctx.send("Error: Must be between 1 minute and 7 days.")

        await ctx.send(f"I will DM you in **{minutes}** minute(s).")
        await asyncio.sleep(minutes * 60)
        try:
            embed = discord.Embed(
                title="Reminder",
                description=message,
                color=WARNING,
                timestamp=dt_now()
            )
            embed.set_footer(text="Nexora Cloud")
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            pass

    # ── /help ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Show the advanced Nexora Cloud command center.")
    async def help_command(self, interaction: discord.Interaction):
        view = HelpView()
        await interaction.response.send_message(embed=view.build_main_embed(), view=view, ephemeral=True)

    # ── Error handlers ──────────────────────────────────────────────────────────

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You do not have permission for this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Error: Missing required argument `{error.param.name}`. Check `!help {ctx.command.name}`.")
        else:
            await ctx.send(f"Error: `{error}`")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "Error: You don't have permission to use this command."
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = "Error: I don't have the required permissions to do that."
        else:
            msg = f"Error: `{error}`"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
