"""
cogs/staff.py — Nexora Cloud

Single-purpose staff operations:
- configure one normal staff role
- assign staff and create private staff workspaces
- count individual staff messages across all visible channels
- calculate the daily target using 2T + 1/2T
- create one predefined staff role at a time
- configure sales-representative invasion announcements
- configure daily-report reminders and DM staff automatically
"""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from ._shared import ACCENT, SUCCESS, WARNING, DANGER, CYAN, log_audit

STAFF_CFG_FILE = os.path.join(os.path.dirname(__file__), "..", "staff_config.json")

# These are the supported Nexora Cloud roles. They are intentionally created
# one at a time with !staffrole_make instead of all being created automatically.
STAFF_ROLE_DEFINITIONS = {
    "Admin": {
        "color": 0xEF4444,
        "permissions": discord.Permissions.all(),
        "department": "Executive",
        "powers": "Full server control, role management, channels, moderation, billing, and configuration.",
    },
    "General Manager": {
        "color": 0xF59E0B,
        "permissions": discord.Permissions(
            manage_guild=True, manage_channels=True, manage_messages=True,
            manage_nicknames=True, moderate_members=True, kick_members=True,
            ban_members=True, view_audit_log=True, manage_roles=True,
            manage_webhooks=True, manage_emojis=True, view_guild_insights=True,
        ),
        "department": "Executive",
        "powers": "Manage server, channels, roles, moderation, and view audit logs.",
    },
    "HR Manager": {
        "color": 0x8B5CF6,
        "permissions": discord.Permissions(
            manage_roles=True, manage_nicknames=True, manage_messages=True,
            view_audit_log=True, moderate_members=True, kick_members=True,
        ),
        "department": "Human Resources",
        "powers": "Manage staff roles, onboarding, vacations, performance reviews, and disciplinary actions.",
    },
    "Sales Manager": {
        "color": 0x10B981,
        "permissions": discord.Permissions(
            manage_messages=True, manage_channels=True, manage_threads=True,
            mention_everyone=True,
        ),
        "department": "Sales",
        "powers": "Manage sales records, quotes, invoices, refunds, discounts, and team announcements.",
    },
    "Sales Representative": {
        "color": 0x34D399,
        "permissions": discord.Permissions(manage_messages=True),
        "department": "Sales",
        "powers": "Create quotes, invoices, and update customer records.",
    },
    "Marketing Manager": {
        "color": 0xEC4899,
        "permissions": discord.Permissions(
            manage_messages=True, manage_channels=True, manage_threads=True,
            mention_everyone=True,
        ),
        "department": "Marketing",
        "powers": "Manage campaigns, announcements, surveys, and brand content.",
    },
    "Marketing Specialist": {
        "color": 0xF472B6,
        "permissions": discord.Permissions(manage_messages=True),
        "department": "Marketing",
        "powers": "Create marketing content, surveys, and social posts.",
    },
    "Support Lead": {
        "color": 0x06B6D4,
        "permissions": discord.Permissions(
            manage_channels=True, manage_messages=True, moderate_members=True,
            manage_threads=True,
        ),
        "department": "Support",
        "powers": "Manage tickets, claims, transfers, escalations, and support agents.",
    },
    "Support Agent": {
        "color": 0x22D3EE,
        "permissions": discord.Permissions(manage_messages=True),
        "department": "Support",
        "powers": "Respond to tickets and post internal notes.",
    },
    "DevOps Engineer": {
        "color": 0x6366F1,
        "permissions": discord.Permissions(
            manage_guild=True, manage_channels=True, manage_messages=True,
            manage_webhooks=True,
        ),
        "department": "Engineering",
        "powers": "Post status updates, incidents, maintenance, deploy notes, and manage IP lists.",
    },
    "Developer": {
        "color": 0x818CF8,
        "permissions": discord.Permissions(manage_messages=True),
        "department": "Engineering",
        "powers": "Log deploy notes, incidents, and participate in engineering discussions.",
    },
    "Moderator": {
        "color": 0x64748B,
        "permissions": discord.Permissions(
            manage_messages=True, manage_threads=True, moderate_members=True,
            kick_members=True,
        ),
        "department": "Community",
        "powers": "Moderate chat, warn, kick, mute, and report suspicious activity.",
    },
}


def _load_all() -> dict:
    if os.path.exists(STAFF_CFG_FILE):
        with open(STAFF_CFG_FILE, encoding="utf-8") as file:
            return json.load(file)
    return {}


def _save_all(data: dict):
    with open(STAFF_CFG_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, default=str)


def _defaults() -> dict:
    return {
        "staff_role_id": None,
        "created_roles": {},
        "staff": {},
        "base_target": 45,
        "dynamic_target": 113,
        "daily_report_channel_id": None,
        "daily_report_hour": 9,
        "counts": {},
        "reports": {},
        "last_reminder_date": None,
    }


def get_scfg(guild_id: int) -> dict:
    all_data = _load_all()
    cfg = all_data.setdefault(str(guild_id), _defaults())
    for key, value in _defaults().items():
        cfg.setdefault(key, value)
    return cfg


def set_scfg(guild_id: int, cfg: dict):
    all_data = _load_all()
    all_data[str(guild_id)] = cfg
    _save_all(all_data)


def _embed(title: str, description: str, color: int = ACCENT) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="Nexora Cloud • Staff Operations")
    return embed


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _staff_role(guild: discord.Guild, cfg: dict) -> Optional[discord.Role]:
    role_id = cfg.get("staff_role_id")
    return guild.get_role(int(role_id)) if role_id else None


def _is_staff(member: discord.Member, role: Optional[discord.Role]) -> bool:
    return bool(role and any(item.id == role.id for item in member.roles))


def _find_staff_definition(role_name: str) -> tuple[str, dict] | tuple[None, None]:
    normalized = " ".join(role_name.split()).casefold()
    for name, definition in STAFF_ROLE_DEFINITIONS.items():
        if name.casefold() == normalized:
            return name, definition
    return None, None


def _effective_target(base_target: int) -> int:
    # Requested formula: 2T + 1/2T. Discord targets must be whole numbers.
    return (base_target * 2) + ((base_target + 1) // 2)


def _admin_overwrites(guild: discord.Guild) -> dict:
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
            embed_links=True,
            attach_files=True,
        ),
    }
    if guild.owner:
        overwrites[guild.owner] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        )
    for role in guild.roles:
        if role.is_default():
            continue
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
            )
    return overwrites


async def _create_staff_workspace(
    guild: discord.Guild,
    member: discord.Member,
    staff_role: discord.Role,
) -> discord.TextChannel:
    category = discord.utils.get(guild.categories, name="Staff Workspaces")
    if not category:
        category = await guild.create_category(
            "Staff Workspaces",
            overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)},
            reason="Nexora Cloud staff workspace setup",
        )

    overwrites = _admin_overwrites(guild)
    overwrites[staff_role] = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        embed_links=True,
    )
    channel = await guild.create_text_channel(
        f"staff-{member.display_name.lower().replace(' ', '-')[:18]}",
        category=category,
        overwrites=overwrites,
        topic=f"Private workspace for {member} • Nexora Cloud staff",
        reason="Nexora Cloud private staff workspace",
    )
    welcome = _embed(
        f"🛡️ Private Staff Workspace",
        (
            f"Welcome, {member.mention}.\n\n"
            "This channel is visible only to you, administrators, and the Nexora bot.\n"
            "Use it for internal updates, blockers, and work coordination.\n\n"
            "**Daily report format**\n"
            "```text\n"
            "Dc Username :\n"
            "Current Role :\n"
            "Time Active :\n"
            "Clients Daily :\n"
            "Servers Invaded :\n"
            "```"
        ),
        0x55FF55,
    )

Extra Notes :
    welcome.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=welcome)
    return channel


async def _count_staff_messages(guild: discord.Guild, role: discord.Role) -> dict[str, int]:
    counts = {str(member.id): 0 for member in role.members if not member.bot}
    start = datetime.combine(
        datetime.now(timezone.utc).date(),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    for channel in guild.text_channels:
        permissions = channel.permissions_for(guild.me)
        if not permissions.read_message_history:
            continue
        try:
            async for message in channel.history(after=start, limit=None):
                if message.author.bot:
                    continue
                key = str(message.author.id)
                if key in counts:
                    counts[key] += 1
        except (discord.Forbidden, discord.HTTPException):
            continue
    return counts


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_report_task.start()

    def cog_unload(self):
        self.daily_report_task.cancel()

    async def _admin_error(self, ctx: commands.Context):
        await ctx.send(embed=_embed("🚫 Access Denied", "This command requires **Administrator** permission.", DANGER))

    @commands.command(name="staff_role", help="Set the normal staff role. Usage: !staff_role @role")
    @commands.has_permissions(administrator=True)
    async def staff_role(self, ctx: commands.Context, role: discord.Role):
        cfg = get_scfg(ctx.guild.id)
        cfg["staff_role_id"] = role.id
        set_scfg(ctx.guild.id, cfg)
        await ctx.send(embed=_embed("✅ Staff Role Set", f"Normal staff role is now {role.mention}.\nMembers of this role receive daily report DMs.", SUCCESS))
        log_audit(ctx.guild.id, "staff_role_set", str(ctx.author), role.name)

    @commands.command(
        name="staffrole_make",
        help="Create one predefined staff role. Usage: !staffrole_make <role name>",
    )
    @commands.has_permissions(administrator=True)
    async def staffrole_make(self, ctx: commands.Context, *, role_name: str):
        """Create exactly one catalog role and persist its guild-specific ID."""
        canonical_name, definition = _find_staff_definition(role_name)
        if not definition:
            available = ", ".join(f"`{name}`" for name in STAFF_ROLE_DEFINITIONS)
            return await ctx.send(
                embed=_embed(
                    "⚠️ Unknown Staff Role",
                    f"Use one of the predefined role names:\n{available}",
                    WARNING,
                )
            )

        cfg = get_scfg(ctx.guild.id)
        created_roles = cfg.setdefault("created_roles", {})
        role_key = canonical_name.casefold()

        saved_role_id = created_roles.get(role_key, {}).get("role_id")
        role = ctx.guild.get_role(int(saved_role_id)) if saved_role_id else None
        if role is None:
            role = discord.utils.find(
                lambda item: item.name.casefold() == canonical_name.casefold(),
                ctx.guild.roles,
            )

        try:
            if role is None:
                role = await ctx.guild.create_role(
                    name=canonical_name,
                    colour=discord.Colour(definition["color"]),
                    permissions=definition["permissions"],
                    hoist=False,
                    mentionable=False,
                    reason=f"Nexora Cloud staff role created by {ctx.author}",
                )
                action = "created"
                log_audit(ctx.guild.id, "staff_role_created", str(ctx.author), canonical_name)
            else:
                action = "already exists"

            created_roles[role_key] = {
                "role_id": role.id,
                "name": canonical_name,
                "department": definition["department"],
                "powers": definition["powers"],
                "created_at": created_roles.get(role_key, {}).get(
                    "created_at", datetime.now(timezone.utc).isoformat()
                ),
            }
            set_scfg(ctx.guild.id, cfg)

            embed = _embed(
                f"✅ Staff Role {action.title()}",
                f"{role.mention} is ready for the **{definition['department']}** department.",
                SUCCESS,
            )
            embed.add_field(name="Role", value=canonical_name, inline=True)
            embed.add_field(name="Department", value=definition["department"], inline=True)
            embed.add_field(name="Powers", value=definition["powers"], inline=False)
            embed.set_footer(text="Saved in staff_config.json • Nexora Cloud Staff Operations")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(
                embed=_embed(
                    "❌ Permission Error",
                    "I cannot create staff roles. Grant **Manage Roles** and move the bot role above the roles it must manage.",
                    DANGER,
                )
            )

    @commands.command(name="staff", help="Add a user to staff and create a private workspace. Usage: !staff @user")
    @commands.has_permissions(administrator=True)
    async def staff(self, ctx: commands.Context, member: discord.Member):
        cfg = get_scfg(ctx.guild.id)
        role = _staff_role(ctx.guild, cfg)
        if not role:
            return await ctx.send(embed=_embed("⚠️ Staff Role Required", "Set the role first with `!staff_role @role`.", WARNING))
        try:
            await member.add_roles(role, reason=f"Staff assigned by {ctx.author}")
            existing_id = cfg.get("staff", {}).get(str(member.id), {}).get("channel_id")
            channel = ctx.guild.get_channel(int(existing_id)) if existing_id else None
            if not channel:
                channel = await _create_staff_workspace(ctx.guild, member, role)
            cfg.setdefault("staff", {})[str(member.id)] = {
                "role_id": role.id,
                "channel_id": channel.id,
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
            set_scfg(ctx.guild.id, cfg)
            await ctx.send(embed=_embed("✅ Staff Member Added", f"{member.mention} now has {role.mention}.\nPrivate workspace: {channel.mention}", SUCCESS))
            log_audit(ctx.guild.id, "staff_member_added", str(ctx.author), str(member), channel.mention)
        except discord.Forbidden:
            await ctx.send(embed=_embed("❌ Permission Error", "I cannot assign that role or create the private workspace. Move my bot role above the staff role and grant Manage Channels.", DANGER))

    @commands.command(name="target", help="Set the daily target. Usage: !target 45")
    @commands.has_permissions(administrator=True)
    async def target(self, ctx: commands.Context, base_target: int):
        if base_target < 1:
            return await ctx.send(embed=_embed("⚠️ Invalid Target", "Target must be at least 1.", WARNING))
        cfg = get_scfg(ctx.guild.id)
        role = _staff_role(ctx.guild, cfg)
        if not role:
            return await ctx.send(embed=_embed("⚠️ Staff Role Required", "Set the role first with `!staff_role @role`.", WARNING))
        cfg["base_target"] = base_target
        cfg["dynamic_target"] = _effective_target(base_target)
        cfg["counts"][_today()] = await _count_staff_messages(ctx.guild, role)
        set_scfg(ctx.guild.id, cfg)
        await self._send_target_embed(ctx, cfg, role, "🎯 Daily Target Updated")

    @commands.command(name="target_status", help="Show individual staff message counts and target progress.")
    async def target_status(self, ctx: commands.Context):
        cfg = get_scfg(ctx.guild.id)
        role = _staff_role(ctx.guild, cfg)
        if not role:
            return await ctx.send(embed=_embed("⚠️ Staff Role Required", "Set the role first with `!staff_role @role`.", WARNING))
        cfg["counts"][_today()] = await _count_staff_messages(ctx.guild, role)
        set_scfg(ctx.guild.id, cfg)
        await self._send_target_embed(ctx, cfg, role, "📊 Staff Target Status")

    async def _send_target_embed(self, ctx: commands.Context, cfg: dict, role: discord.Role, title: str):
        counts = cfg.get("counts", {}).get(_today(), {})
        target = int(cfg.get("dynamic_target", _effective_target(int(cfg.get("base_target", 45)))))
        embed = discord.Embed(
            title=title,
            description=f"Formula: **2T + ½T**\nBase target: `{cfg.get('base_target', 45)}` • Dynamic target: `{target}`\nCounting messages from all readable channels today.",
            color=ACCENT,
            timestamp=datetime.now(timezone.utc),
        )
        for member in role.members[:25]:
            count = int(counts.get(str(member.id), 0))
            percentage = min(100, int((count / max(target, 1)) * 100))
            bar = "█" * (percentage // 10) + "░" * (10 - (percentage // 10))
            embed.add_field(name=member.display_name, value=f"`{count}` messages\n`[{bar}] {percentage}%` of `{target}`", inline=True)
        embed.set_footer(text="Nexora Cloud • Individual staff activity tracking")
        await ctx.send(embed=embed)

    @commands.command(name="sales_representativechannel", help="Set the sales representative channel. Usage: !sales_representativechannel #channel")
    @commands.has_permissions(administrator=True)
    async def sales_representativechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        cfg = get_scfg(ctx.guild.id)
        cfg["sales_channel_id"] = channel.id
        set_scfg(ctx.guild.id, cfg)
        await ctx.send(embed=_embed("✅ Sales Channel Set", f"Invade decisions will be announced in {channel.mention}.", SUCCESS))

    @commands.command(name="sr", help="Set the sales representative role. Usage: !sr @role")
    @commands.has_permissions(administrator=True)
    async def sr(self, ctx: commands.Context, role: discord.Role):
        cfg = get_scfg(ctx.guild.id)
        cfg["sales_role_id"] = role.id
        set_scfg(ctx.guild.id, cfg)
        await ctx.send(embed=_embed("✅ Sales Role Set", f"Only administrators and {role.mention} can use `!invade`.", SUCCESS))

    @commands.command(name="invade", help="Announce a server invasion decision. Usage: !invade <serverlink> <owneruserid> <accept|eject>")
    async def invade(self, ctx: commands.Context, server_link: str, owner_user_id: int, decision: str):
        cfg = get_scfg(ctx.guild.id)
        role = ctx.guild.get_role(int(cfg.get("sales_role_id", 0))) if cfg.get("sales_role_id") else None
        if not ctx.author.guild_permissions.administrator and not (role and role in ctx.author.roles):
            return await ctx.send(embed=_embed("🚫 Access Denied", "Only administrators or the configured sales representative role can use `!invade`.", DANGER))
        decision = decision.lower()
        if decision not in {"accept", "eject"}:
            return await ctx.send(embed=_embed("⚠️ Invalid Decision", "Use either `accept` or `eject`.", WARNING))
        channel = ctx.guild.get_channel(int(cfg.get("sales_channel_id", 0))) if cfg.get("sales_channel_id") else None
        if not channel:
            return await ctx.send(embed=_embed("⚠️ Sales Channel Required", "Set it first with `!sales_representativechannel #channel`.", WARNING))
        try:
            owner = ctx.guild.get_member(owner_user_id) or await self.bot.fetch_user(owner_user_id)
            owner_name = f"{owner} (`{owner.id}`)"
        except (discord.NotFound, discord.HTTPException):
            owner_name = f"Unknown owner (`{owner_user_id}`)"
        accepted = decision == "accept"
        result = "accepted" if accepted else "ejected"
        announcement = _embed(
            f"{'✅' if accepted else '⛔'} Server Invasion {'Accepted' if accepted else 'Ejected'}",
            f"**{ctx.author.mention}** has {result} this server invasion.",
            SUCCESS if accepted else DANGER,
        )
        announcement.add_field(name="Server Link", value=server_link, inline=False)
        announcement.add_field(name="Owner", value=owner_name, inline=True)
        announcement.add_field(name="Decision", value=decision.upper(), inline=True)
        announcement.add_field(name="Reviewed by", value=ctx.author.mention, inline=True)
        await channel.send(embed=announcement)
        await ctx.send(embed=_embed("✅ Invasion Recorded", f"The decision was announced in {channel.mention}.", SUCCESS))
        log_audit(ctx.guild.id, "server_invasion_decision", str(ctx.author), owner_name, f"{decision}:{server_link}")

    @commands.command(name="daily_report", help="Set the daily report channel. Usage: !daily_report channel #channel [hour]")
    @commands.has_permissions(administrator=True)
    async def daily_report(self, ctx: commands.Context, action: str, channel: discord.TextChannel, reminder_hour: int = 9):
        if action.lower() != "channel":
            return await ctx.send(embed=_embed("⚠️ Invalid Format", "Use `!daily_report channel #channel [hour]`.", WARNING))
        if reminder_hour < 0 or reminder_hour > 23:
            return await ctx.send(embed=_embed("⚠️ Invalid Hour", "Hour must be between 0 and 23 UTC.", WARNING))
        cfg = get_scfg(ctx.guild.id)
        cfg["daily_report_channel_id"] = channel.id
        cfg["daily_report_hour"] = reminder_hour
        set_scfg(ctx.guild.id, cfg)
        await ctx.send(embed=_embed("✅ Daily Reports Configured", f"Reports are checked in {channel.mention}.\nDaily staff DMs are sent at **{reminder_hour:02d}:00 UTC**.", SUCCESS))

    @commands.command(name="daily_report_status", help="Show today's daily report submissions.")
    @commands.has_permissions(administrator=True)
    async def daily_report_status(self, ctx: commands.Context):
        cfg = get_scfg(ctx.guild.id)
        role = _staff_role(ctx.guild, cfg)
        if not role:
            return await ctx.send(embed=_embed("⚠️ Staff Role Required", "Set the role first with `!staff_role @role`.", WARNING))
        submitted = cfg.get("reports", {}).get(_today(), {})
        embed = _embed("📝 Daily Report Status", f"Date: `{_today()}`", ACCENT)
        for member in role.members[:25]:
            embed.add_field(name=member.display_name, value="✅ Submitted" if str(member.id) in submitted else "⏳ Pending", inline=True)
        await ctx.send(embed=embed)

    async def _send_daily_report_reminders(self, guild: discord.Guild, cfg: dict):
        role = _staff_role(guild, cfg)
        channel = guild.get_channel(int(cfg.get("daily_report_channel_id", 0))) if cfg.get("daily_report_channel_id") else None
        if not role or not channel:
            return
        date_label = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
        report_embed = _embed(
            "📋 Daily Report Required",
            f"Please submit your report for **{date_label}** in {channel.mention}.",
            WARNING,
        )
        report_embed.add_field(
            name="Required format",
            value="```text\nTasks completed:\nBlockers / issues:\nOrders or tickets handled:\nNotes for tomorrow:\n```",
            inline=False,
        )
        report_embed.set_footer(text="Nexora Cloud • Daily staff reminder")
        for member in role.members:
            try:
                await member.send(embed=report_embed)
            except (discord.Forbidden, discord.HTTPException):
                continue
        await channel.send(content=role.mention, embed=report_embed)

    @tasks.loop(minutes=1)
    async def daily_report_task(self):
        now = datetime.now(timezone.utc)
        if now.minute != 0:
            return
        for guild_id, raw_cfg in _load_all().items():
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            cfg = get_scfg(guild.id)
            if now.hour != int(cfg.get("daily_report_hour", 9)) or cfg.get("last_reminder_date") == _today():
                continue
            role = _staff_role(guild, cfg)
            if role:
                cfg["counts"][_today()] = await _count_staff_messages(guild, role)
            await self._send_daily_report_reminders(guild, cfg)
            cfg["last_reminder_date"] = _today()
            set_scfg(guild.id, cfg)

    @daily_report_task.before_loop
    async def before_daily_report_task(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        cfg = get_scfg(message.guild.id)
        role = _staff_role(message.guild, cfg)
        if not role or not _is_staff(message.author, role):
            return
        today = _today()
        cfg.setdefault("counts", {}).setdefault(today, {})
        key = str(message.author.id)
        cfg["counts"][today][key] = int(cfg["counts"][today].get(key, 0)) + 1
        report_channel_id = cfg.get("daily_report_channel_id")
        if report_channel_id and message.channel.id == int(report_channel_id):
            cfg.setdefault("reports", {}).setdefault(today, {})[key] = message.id
        set_scfg(message.guild.id, cfg)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await self._admin_error(ctx)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=_embed("⚠️ Missing Argument", f"Missing `{error.param.name}`. Check `!help {ctx.command.name}`.", WARNING))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=_embed("⚠️ Invalid Data", "Check the command format and try again.", WARNING))
        else:
            await ctx.send(embed=_embed("❌ Staff Command Error", f"`{error}`", DANGER))


async def setup(bot: commands.Bot):
    await bot.add_cog(Staff(bot))
