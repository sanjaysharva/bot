"""
cogs/staff_manager.py — Nexora Cloud
Advanced staff management: auto-create roles, assign staff, create private personal + department channels,
powers per role, and professional staff commands.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import guild_data, save_guild, log_audit, ACCENT, SUCCESS, WARNING, DANGER, PURPLE, CYAN

STAFF_CFG_FILE = os.path.join(os.path.dirname(__file__), "..", "staff_config.json")


def _load_cfg() -> dict:
    if os.path.exists(STAFF_CFG_FILE):
        with open(STAFF_CFG_FILE) as f:
            return json.load(f)
    return {}


def _save_cfg(data: dict):
    with open(STAFF_CFG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_gcfg(guild_id: int) -> dict:
    return _load_cfg().get(str(guild_id), {})


def set_gcfg(guild_id: int, data: dict):
    cfg = _load_cfg()
    cfg[str(guild_id)] = data
    _save_cfg(cfg)


# ── Role definitions ───────────────────────────────────────────────────────────

STAFF_ROLES = {
    "Admin": {
        "color": 0xEF4444,
        "perms": discord.Permissions.all(),
        "powers": "Full server control, role management, channels, moderation, billing, and configuration.",
        "department": "Executive",
    },
    "General Manager": {
        "color": 0xF59E0B,
        "perms": discord.Permissions(
            manage_guild=True, manage_channels=True, manage_messages=True, manage_nicknames=True,
            moderate_members=True, kick_members=True, ban_members=True, view_audit_log=True,
            manage_roles=True, manage_webhooks=True, manage_emojis=True, view_guild_insights=True
        ),
        "powers": "Manage server, channels, roles, moderation, and view audit logs. Cannot delete server.",
        "department": "Executive",
    },
    "HR Manager": {
        "color": 0x8B5CF6,
        "perms": discord.Permissions(
            manage_roles=True, manage_nicknames=True, manage_messages=True, view_audit_log=True,
            moderate_members=True, kick_members=True
        ),
        "powers": "Manage staff roles, onboarding, vacations, performance reviews, and disciplinary actions.",
        "department": "Human Resources",
    },
    "Sales Manager": {
        "color": 0x10B981,
        "perms": discord.Permissions(
            manage_messages=True, manage_channels=True, manage_threads=True, mention_everyone=True
        ),
        "powers": "Manage sales records, quotes, invoices, refunds, discounts, and team announcements.",
        "department": "Sales",
    },
    "Sales Representative": {
        "color": 0x34D399,
        "perms": discord.Permissions(manage_messages=True, mention_everyone=False),
        "powers": "Create quotes, invoices, and update customer records. Reports to Sales Manager.",
        "department": "Sales",
    },
    "Marketing Manager": {
        "color": 0xEC4899,
        "perms": discord.Permissions(
            manage_messages=True, manage_channels=True, manage_threads=True, mention_everyone=True
        ),
        "powers": "Manage campaigns, announcements, surveys, and brand content.",
        "department": "Marketing",
    },
    "Marketing Specialist": {
        "color": 0xF472B6,
        "perms": discord.Permissions(manage_messages=True),
        "powers": "Create marketing content, surveys, and social posts. Reports to Marketing Manager.",
        "department": "Marketing",
    },
    "Support Lead": {
        "color": 0x06B6D4,
        "perms": discord.Permissions(
            manage_channels=True, manage_messages=True, moderate_members=True, manage_threads=True
        ),
        "powers": "Manage tickets, claim/transfer, escalate, and lead support agents.",
        "department": "Support",
    },
    "Support Agent": {
        "color": 0x22D3EE,
        "perms": discord.Permissions(manage_messages=True),
        "powers": "Respond to tickets and post internal notes. Reports to Support Lead.",
        "department": "Support",
    },
    "DevOps Engineer": {
        "color": 0x6366F1,
        "perms": discord.Permissions(
            manage_guild=True, manage_channels=True, manage_messages=True, manage_webhooks=True
        ),
        "powers": "Post status updates, incidents, maintenance, deploy notes, and manage IP lists.",
        "department": "Engineering",
    },
    "Developer": {
        "color": 0x818CF8,
        "perms": discord.Permissions(manage_messages=True),
        "powers": "Log deploy notes, incidents, and participate in engineering discussions.",
        "department": "Engineering",
    },
    "Moderator": {
        "color": 0x64748B,
        "perms": discord.Permissions(
            manage_messages=True, manage_threads=True, moderate_members=True, kick_members=True
        ),
        "powers": "Moderate chat, warn, kick, mute, and report suspicious activity.",
        "department": "Community",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _role_key(role_name: str) -> str:
    return role_name.lower().replace(" ", "_")


async def _ensure_staff_roles(guild: discord.Guild):
    """Create or update all staff roles and return a dict of role names to Role objects."""
    cfg = get_gcfg(guild.id)
    created = cfg.setdefault("roles", {})
    result = {}

    for name, meta in STAFF_ROLES.items():
        key = _role_key(name)
        role_id = created.get(key)
        role = guild.get_role(int(role_id)) if role_id else None

        if not role:
            try:
                role = await guild.create_role(
                    name=name,
                    color=discord.Color(meta["color"]),
                    permissions=meta["perms"],
                    hoist=True,
                    mentionable=True,
                    reason="Nexora Cloud staff role setup"
                )
                created[key] = role.id
                set_gcfg(guild.id, cfg)
                log_audit(guild.id, "staff_role_created", "Nexora Bot", name)
            except Exception as e:
                print(f"Failed to create role {name}: {e}")
        result[name] = role

    return result


async def _get_or_create_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    existing = discord.utils.get(guild.categories, name=name)
    if existing:
        return existing
    return await guild.create_category(name, reason="Nexora Cloud staff department category")


async def _create_personal_channel(guild: discord.Guild, member: discord.Member, role: discord.Role, department: str) -> discord.TextChannel:
    """Create a personal private channel for the staff member."""
    cfg = get_gcfg(guild.id)
    category = await _get_or_create_category(guild, "Staff Workspaces")
    channel_name = f"{member.name[:12]}-workspace".lower()

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True),
        member:             discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
    }
    # Add managers of same department and admins
    roles = await _ensure_staff_roles(guild)
    if "Admin" in roles:
        overwrites[roles["Admin"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    if "General Manager" in roles:
        overwrites[roles["General Manager"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    if department == "Human Resources" and "HR Manager" in roles:
        overwrites[roles["HR Manager"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    if department == "Sales" and "Sales Manager" in roles:
        overwrites[roles["Sales Manager"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    if department == "Marketing" and "Marketing Manager" in roles:
        overwrites[roles["Marketing Manager"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    if department == "Support" and "Support Lead" in roles:
        overwrites[roles["Support Lead"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    if department == "Engineering" and "DevOps Engineer" in roles:
        overwrites[roles["DevOps Engineer"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"Private workspace for {member.display_name} ({role.name}) — reports, updates, and files."
    )

    staff = cfg.setdefault("staff", {})
    staff[str(member.id)] = {
        "role": role.name,
        "department": department,
        "personal_channel_id": channel.id,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "added_by": None,
    }
    set_gcfg(guild.id, cfg)
    return channel


async def _get_or_create_department_channel(guild: discord.Guild, department: str) -> discord.TextChannel:
    cfg = get_gcfg(guild.id)
    dept_channels = cfg.setdefault("department_channels", {})
    channel_id = dept_channels.get(department)
    channel = guild.get_channel(int(channel_id)) if channel_id else None
    if channel:
        return channel

    roles = await _ensure_staff_roles(guild)
    category = await _get_or_create_category(guild, "Staff Departments")
    dept_slug = department.lower().replace(" ", "-")
    channel_name = f"{dept_slug}-department"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True),
    }
    if "Admin" in roles:
        overwrites[roles["Admin"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, mention_everyone=True)
    if "General Manager" in roles:
        overwrites[roles["General Manager"]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, mention_everyone=True)

    # Map department to relevant roles
    dept_roles = []
    if department == "Executive":
        dept_roles = ["Admin", "General Manager"]
    elif department == "Human Resources":
        dept_roles = ["HR Manager"]
    elif department == "Sales":
        dept_roles = ["Sales Manager", "Sales Representative"]
    elif department == "Marketing":
        dept_roles = ["Marketing Manager", "Marketing Specialist"]
    elif department == "Support":
        dept_roles = ["Support Lead", "Support Agent"]
    elif department == "Engineering":
        dept_roles = ["DevOps Engineer", "Developer"]
    elif department == "Community":
        dept_roles = ["Moderator"]

    for rname in dept_roles:
        if rname in roles and roles[rname]:
            overwrites[roles[rname]] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"Department channel for {department} — announcements, reports, and collaboration."
    )
    dept_channels[department] = channel.id
    set_gcfg(guild.id, cfg)
    return channel


class _InteractionContext:
    """Minimal context wrapper so prefix methods can be reused from slash commands."""
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.guild = interaction.guild
        self.author = interaction.user
        self.channel = interaction.channel
        self.bot = interaction.client

    async def send(self, *args, **kwargs):
        if self.interaction.response.is_done():
            return await self.interaction.followup.send(*args, **kwargs)
        await self.interaction.response.send_message(*args, **kwargs)
        return await self.interaction.original_response()


# ── Cog ───────────────────────────────────────────────────────────────────────

class StaffManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !setup_staff_roles ──────────────────────────────────────────────────────
    @commands.command(name="setup_staff_roles", help="Create all predefined Nexora Cloud staff roles.")
    @commands.has_permissions(administrator=True)
    async def setup_staff_roles(self, ctx: commands.Context):
        roles = await _ensure_staff_roles(ctx.guild)
        created = [f"{name}: {role.mention if role else '*failed*'}" for name, role in roles.items()]
        embed = discord.Embed(
            title="Staff Roles Created",
            description="\n".join(created),
            color=SUCCESS,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Nexora Cloud — Staff Management")
        await ctx.send(embed=embed)

    # ── !add_staff ─────────────────────────────────────────────────────────────
    @commands.command(name="add_staff", help="Add a member to a staff role and create their private workspace.")
    @commands.has_permissions(manage_roles=True)
    async def add_staff(self, ctx: commands.Context, member: discord.Member, *, role_name: str):
        roles = await _ensure_staff_roles(ctx.guild)
        matched = None
        for name in roles:
            if role_name.lower() in name.lower() or name.lower() in role_name.lower():
                matched = name
                break
        if not matched:
            available = ", ".join(f"`{n}`" for n in STAFF_ROLES.keys())
            return await ctx.send(f"Error: Unknown role. Available: {available}")

        role = roles[matched]
        if not role:
            return await ctx.send(f"Error: Could not find or create the {matched} role.")

        await member.add_roles(role, reason="Nexora Cloud staff assignment")
        department = STAFF_ROLES[matched]["department"]

        dept_channel = await _get_or_create_department_channel(ctx.guild, department)
        personal_channel = await _create_personal_channel(ctx.guild, member, role, department)

        cfg = get_gcfg(ctx.guild.id)
        staff = cfg.setdefault("staff", {})
        staff[str(member.id)] = {
            "role": matched,
            "department": department,
            "personal_channel_id": personal_channel.id,
            "department_channel_id": dept_channel.id,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "added_by": ctx.author.display_name,
        }
        set_gcfg(ctx.guild.id, cfg)
        log_audit(ctx.guild.id, "staff_added", str(ctx.author), str(member), matched)

        embed = discord.Embed(title="Staff Member Added", color=SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Department", value=department, inline=True)
        embed.add_field(name="Personal Channel", value=personal_channel.mention, inline=False)
        embed.add_field(name="Department Channel", value=dept_channel.mention, inline=False)
        await ctx.send(embed=embed)

        # Welcome DM
        try:
            welcome = discord.Embed(
                title="Welcome to the Nexora Cloud Staff Team",
                description=(
                    f"Congratulations, {member.mention}! You have been assigned as **{matched}** in the **{department}** department.\n\n"
                    f"**Your personal workspace:** {personal_channel.mention}\n"
                    f"**Your department channel:** {dept_channel.mention}\n\n"
                    f"Use your workspace for reports, files, and notes. Use the department channel for team collaboration."
                ),
                color=ACCENT,
                timestamp=datetime.now(timezone.utc)
            )
            await member.send(embed=welcome)
        except discord.Forbidden:
            pass

    # ── !remove_staff ──────────────────────────────────────────────────────────
    @commands.command(name="remove_staff", help="Remove a member from the staff program.")
    @commands.has_permissions(manage_roles=True)
    async def remove_staff(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Staff removal"):
        cfg = get_gcfg(ctx.guild.id)
        staff = cfg.get("staff", {})
        record = staff.pop(str(member.id), None)
        if not record:
            return await ctx.send(f"{member.mention} is not registered as staff.")

        # Remove staff roles that match our defined roles
        roles_to_remove = [r for r in member.roles if r.name in STAFF_ROLES]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=reason)

        # Optional: archive personal channel by renaming and locking
        personal_id = record.get("personal_channel_id")
        if personal_id:
            channel = ctx.guild.get_channel(int(personal_id))
            if channel:
                try:
                    await channel.edit(name=f"archived-{channel.name}", topic=f"Archived workspace for {member.display_name}. Reason: {reason}")
                    await channel.set_permissions(member, view_channel=False)
                except Exception:
                    pass

        set_gcfg(ctx.guild.id, cfg)
        log_audit(ctx.guild.id, "staff_removed", str(ctx.author), str(member), reason)
        await ctx.send(f"{member.mention} has been removed from staff. Reason: {reason}")

    # ── !staff_directory ───────────────────────────────────────────────────────
    @commands.command(name="staff_directory", help="Show all registered staff members by department.")
    @commands.has_permissions(manage_messages=True)
    async def staff_directory(self, ctx: commands.Context):
        cfg = get_gcfg(ctx.guild.id)
        staff = cfg.get("staff", {})
        if not staff:
            return await ctx.send("No staff members registered yet.")

        by_dept = {}
        for uid, record in staff.items():
            dept = record.get("department", "Unassigned")
            member = ctx.guild.get_member(int(uid))
            if not member:
                continue
            by_dept.setdefault(dept, []).append(f"{member.mention} — `{record['role']}`")

        embed = discord.Embed(title="Staff Directory", color=ACCENT, timestamp=datetime.now(timezone.utc))
        for dept, lines in sorted(by_dept.items()):
            embed.add_field(name=dept, value="\n".join(lines) or "None", inline=False)
        await ctx.send(embed=embed)

    # ── !role_info ─────────────────────────────────────────────────────────────
    @commands.command(name="role_info", help="Show powers and permissions for a staff role.")
    @commands.has_permissions(manage_messages=True)
    async def role_info(self, ctx: commands.Context, *, role_name: str):
        matched = None
        for name in STAFF_ROLES:
            if role_name.lower() in name.lower() or name.lower() in role_name.lower():
                matched = name
                break
        if not matched:
            return await ctx.send(f"Error: Unknown staff role. Available: {', '.join(f'`{n}`' for n in STAFF_ROLES)}")

        meta = STAFF_ROLES[matched]
        embed = discord.Embed(title=f"Staff Role — {matched}", color=meta["color"], timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Department", value=meta["department"], inline=True)
        embed.add_field(name="Powers", value=meta["powers"], inline=False)
        perms = ", ".join([p[0] for p in meta["perms"] if p[1]]) or "None"
        embed.add_field(name="Key Permissions", value=perms[:1024], inline=False)
        await ctx.send(embed=embed)

    # ── !department_announce ───────────────────────────────────────────────────
    @commands.command(name="department_announce", help="Send an announcement to a department channel. Usage: !department_announce \"<Department>\" \"<title>\" | \"<message>\"")
    @commands.has_permissions(manage_messages=True)
    async def department_announce(self, ctx: commands.Context, department: str, *, args: str):
        try:
            title, message = args.split(" | ", 1)
        except ValueError:
            return await ctx.send("Usage: !department_announce \"<Department>\" \"<title>\" | \"<message>\"")

        cfg = get_gcfg(ctx.guild.id)
        dept_channels = cfg.get("department_channels", {})
        channel_id = dept_channels.get(department)
        channel = ctx.guild.get_channel(int(channel_id)) if channel_id else None
        if not channel:
            return await ctx.send(f"Department channel for `{department}` not found. Use `!create_department_channels` first.")

        embed = discord.Embed(title=title, description=message, color=PURPLE, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Posted by {ctx.author.display_name} — {department}")
        await channel.send(content="@here", embed=embed)
        await ctx.send(f"Announcement sent to {channel.mention}.")

    # ── !create_department_channels ───────────────────────────────────────────
    @commands.command(name="create_department_channels", help="Create department channels for all staff departments.")
    @commands.has_permissions(administrator=True)
    async def create_department_channels(self, ctx: commands.Context):
        departments = sorted({meta["department"] for meta in STAFF_ROLES.values()})
        created = []
        for dept in departments:
            ch = await _get_or_create_department_channel(ctx.guild, dept)
            created.append(f"{dept}: {ch.mention}")
        embed = discord.Embed(title="Department Channels", description="\n".join(created), color=SUCCESS, timestamp=datetime.now(timezone.utc))
        await ctx.send(embed=embed)

    # ── !staff_report ───────────────────────────────────────────────────────────
    @commands.command(name="staff_report", help="Post a report to your personal workspace. Usage: !staff_report \"<title>\" \"<body>\"")
    @commands.has_permissions(manage_messages=True)
    async def staff_report(self, ctx: commands.Context, title: str, *, body: str):
        cfg = get_gcfg(ctx.guild.id)
        record = cfg.get("staff", {}).get(str(ctx.author.id))
        if not record:
            return await ctx.send("Error: You are not registered as staff.")
        channel = ctx.guild.get_channel(int(record.get("personal_channel_id", 0)))
        if not channel:
            return await ctx.send("Error: Your personal workspace was not found.")

        embed = discord.Embed(title=f"Staff Report — {title}", description=body, color=CYAN, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Submitted by {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send(f"Report posted to {channel.mention}.")

    # ── !shift_handover ───────────────────────────────────────────────────────
    @commands.command(name="shift_handover", help="Create a shift handover note. Usage: !shift_handover \"<summary>\" \"<pending>\" \"<notes>\"")
    @commands.has_permissions(manage_messages=True)
    async def shift_handover(self, ctx: commands.Context, summary: str, pending: str, *, notes: str = ""):
        cfg = get_gcfg(ctx.guild.id)
        record = cfg.get("staff", {}).get(str(ctx.author.id))
        if not record:
            return await ctx.send("Error: You are not registered as staff.")
        channel = ctx.guild.get_channel(int(record.get("personal_channel_id", 0)))
        if not channel:
            return await ctx.send("Error: Your personal workspace was not found.")

        embed = discord.Embed(title="Shift Handover", color=WARNING, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Summary", value=summary, inline=False)
        embed.add_field(name="Pending Items", value=pending, inline=False)
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        embed.set_footer(text=f"From {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send("Shift handover recorded.")

    # ── !task_assign ───────────────────────────────────────────────────────────
    @commands.command(name="task_assign", help="Assign a task to a staff member. Usage: !task_assign @user \"<task>\" [due_date]")
    @commands.has_permissions(manage_messages=True)
    async def task_assign(self, ctx: commands.Context, member: discord.Member, task: str, due_date: str = ""):
        cfg = get_gcfg(ctx.guild.id)
        record = cfg.get("staff", {}).get(str(member.id))
        if not record:
            return await ctx.send(f"Error: {member.mention} is not registered as staff.")
        channel = ctx.guild.get_channel(int(record.get("personal_channel_id", 0)))
        if not channel:
            return await ctx.send("Error: Their personal workspace was not found.")

        embed = discord.Embed(title="Task Assigned", color=PURPLE, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Task", value=task, inline=False)
        embed.add_field(name="Assigned by", value=ctx.author.mention, inline=True)
        if due_date:
            embed.add_field(name="Due", value=due_date, inline=True)
        embed.set_footer(text="Nexora Cloud — Task Management")
        await channel.send(content=member.mention, embed=embed)
        await ctx.send(f"Task assigned to {member.mention}.")

    # ── !performance_review ──────────────────────────────────────────────────────
    @commands.command(name="performance_review", help="Record a performance review. Usage: !performance_review @user <rating 1-5> \"<notes>\"")
    @commands.has_permissions(manage_roles=True)
    async def performance_review(self, ctx: commands.Context, member: discord.Member, rating: int, *, notes: str):
        if not (1 <= rating <= 5):
            return await ctx.send("Error: Rating must be 1–5.")
        cfg = get_gcfg(ctx.guild.id)
        record = cfg.get("staff", {}).get(str(member.id))
        if not record:
            return await ctx.send(f"Error: {member.mention} is not registered as staff.")
        channel = ctx.guild.get_channel(int(record.get("personal_channel_id", 0)))
        if not channel:
            return await ctx.send("Error: Their personal workspace was not found.")

        stars = "★" * rating + "☆" * (5 - rating)
        embed = discord.Embed(title="Performance Review", color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Employee", value=member.mention, inline=True)
        embed.add_field(name="Rating", value=f"{stars} ({rating}/5)", inline=True)
        embed.add_field(name="Notes", value=notes, inline=False)
        embed.set_footer(text=f"Reviewed by {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send(f"Performance review recorded for {member.mention}.")

    # ── !promote ───────────────────────────────────────────────────────────────
    @commands.command(name="promote", help="Promote/demote a staff member to a new role. Usage: !promote @user \"<New Role>\"")
    @commands.has_permissions(manage_roles=True)
    async def promote(self, ctx: commands.Context, member: discord.Member, *, new_role_name: str):
        roles = await _ensure_staff_roles(ctx.guild)
        matched = None
        for name in roles:
            if new_role_name.lower() in name.lower() or name.lower() in new_role_name.lower():
                matched = name
                break
        if not matched:
            return await ctx.send(f"Error: Unknown role. Available: {', '.join(f'`{n}`' for n in STAFF_ROLES)}")

        new_role = roles[matched]
        # Remove old staff roles
        old_roles = [r for r in member.roles if r.name in STAFF_ROLES]
        if old_roles:
            await member.remove_roles(*old_roles)
        await member.add_roles(new_role, reason="Nexora Cloud staff promotion")

        department = STAFF_ROLES[matched]["department"]
        dept_channel = await _get_or_create_department_channel(ctx.guild, department)

        cfg = get_gcfg(ctx.guild.id)
        staff = cfg.setdefault("staff", {})
        staff[str(member.id)] = staff.get(str(member.id), {})
        staff[str(member.id)].update({
            "role": matched,
            "department": department,
            "department_channel_id": dept_channel.id,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "promoted_by": ctx.author.display_name,
        })
        set_gcfg(ctx.guild.id, cfg)

        embed = discord.Embed(title="Staff Promotion", color=SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="New Role", value=new_role.mention, inline=True)
        embed.add_field(name="Department", value=department, inline=True)
        await ctx.send(embed=embed)

    # ── !staff_activity ─────────────────────────────────────────────────────────
    @commands.command(name="staff_activity", help="Log a staff activity or milestone. Usage: !staff_activity @user \"<activity>\"")
    @commands.has_permissions(manage_messages=True)
    async def staff_activity(self, ctx: commands.Context, member: discord.Member, *, activity: str):
        cfg = get_gcfg(ctx.guild.id)
        record = cfg.get("staff", {}).get(str(member.id))
        if not record:
            return await ctx.send(f"Error: {member.mention} is not registered as staff.")
        channel = ctx.guild.get_channel(int(record.get("personal_channel_id", 0)))
        if not channel:
            return await ctx.send("Error: Their personal workspace was not found.")

        embed = discord.Embed(title="Staff Activity Log", color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Activity", value=activity, inline=False)
        embed.set_footer(text=f"Logged by {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send(f"Activity logged for {member.mention}.")

    # ── /add_staff (slash) ───────────────────────────────────────────────────
    @app_commands.command(name="add_staff", description="Add a member to a staff role and create their workspace.")
    @app_commands.describe(member="The member to add", role_name="Staff role name")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def slash_add_staff(self, interaction: discord.Interaction, member: discord.Member, role_name: str):
        await interaction.response.defer(ephemeral=False)
        ctx = _InteractionContext(interaction)
        await self.add_staff(ctx, member, role_name=role_name)

    # ── /staff_directory (slash) ───────────────────────────────────────────────
    @app_commands.command(name="staff_directory", description="Show all registered staff members.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def slash_staff_directory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        ctx = _InteractionContext(interaction)
        await self.staff_directory(ctx)

    # ── /role_info (slash) ─────────────────────────────────────────────────────
    @app_commands.command(name="role_info", description="Show powers and permissions for a staff role.")
    @app_commands.describe(role_name="Staff role name")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def slash_role_info(self, interaction: discord.Interaction, role_name: str):
        await interaction.response.defer(ephemeral=False)
        ctx = _InteractionContext(interaction)
        await self.role_info(ctx, role_name=role_name)

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
    await bot.add_cog(StaffManager(bot))
