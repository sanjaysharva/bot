"""
cogs/managment.py — Nexora Cloud

Staff performance reporting. The filename is kept for compatibility with the
existing project layout; this cog intentionally owns only !performance.
"""

from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from .staff import get_scfg, set_scfg
from ._shared import SUCCESS, WARNING, DANGER


ACTIVE_STATUSES = {
    discord.Status.online,
    discord.Status.idle,
    discord.Status.dnd,
}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _staff_role(guild: discord.Guild, cfg: dict) -> discord.Role | None:
    role_id = cfg.get("staff_role_id")
    return guild.get_role(int(role_id)) if role_id else None


def _active_now(status: discord.Status) -> bool:
    return status in ACTIVE_STATUSES


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _flush_online_sessions(cfg: dict, date_key: str, now: datetime) -> None:
    """Persist elapsed time without closing sessions that are still active."""
    entries = cfg.setdefault("online_time", {}).setdefault(date_key, {})
    for entry in entries.values():
        active_since = _parse_timestamp(entry.get("active_since"))
        if not active_since:
            continue
        elapsed = max(0, int((now - active_since).total_seconds()))
        entry["total_seconds"] = int(entry.get("total_seconds", 0)) + elapsed
        entry["active_since"] = now.isoformat()


def _online_seconds(cfg: dict, user_id: int, date_key: str, now: datetime) -> int:
    entry = cfg.get("online_time", {}).get(date_key, {}).get(str(user_id), {})
    total = int(entry.get("total_seconds", 0))
    active_since = _parse_timestamp(entry.get("active_since"))
    if active_since:
        total += max(0, int((now - active_since).total_seconds()))
    return total


def _format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m"


def _invasion_counts(cfg: dict, user_id: int, date_key: str) -> tuple[int, int]:
    accepted = 0
    ejected = 0
    for record in cfg.get("invasions", []):
        if str(record.get("reviewer_id")) != str(user_id):
            continue
        timestamp = _parse_timestamp(record.get("timestamp"))
        if timestamp and timestamp.date().isoformat() != date_key:
            continue
        if record.get("decision") == "accept":
            accepted += 1
        elif record.get("decision") == "eject":
            ejected += 1
    return accepted, ejected


def _metrics(cfg: dict, member: discord.Member, date_key: str, now: datetime) -> dict:
    target = max(1, int(cfg.get("dynamic_target", 113)))
    messages = int(cfg.get("counts", {}).get(date_key, {}).get(str(member.id), 0))
    accepted, ejected = _invasion_counts(cfg, member.id, date_key)
    online_seconds = _online_seconds(cfg, member.id, date_key, now)

    target_points = min(50.0, (messages / target) * 50)
    invasion_points = min(30.0, (accepted * 10) + (ejected * 5))
    online_points = min(20.0, (online_seconds / (8 * 3600)) * 20)
    score = round(target_points + invasion_points + online_points, 1)

    return {
        "member": member,
        "messages": messages,
        "target": target,
        "target_percent": min(100, round((messages / target) * 100)),
        "accepted": accepted,
        "ejected": ejected,
        "online_seconds": online_seconds,
        "target_points": round(target_points, 1),
        "invasion_points": round(invasion_points, 1),
        "online_points": round(online_points, 1),
        "score": score,
    }


class Management(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.online_flush_task.start()

    def cog_unload(self):
        self.online_flush_task.cancel()

    async def _update_presence(
        self,
        member: discord.Member,
        status: discord.Status,
    ) -> None:
        if member.bot or not member.guild:
            return
        cfg = get_scfg(member.guild.id)
        role = _staff_role(member.guild, cfg)
        if not role or role not in member.roles:
            return

        date_key = _today()
        now = datetime.now(timezone.utc)
        entries = cfg.setdefault("online_time", {}).setdefault(date_key, {})
        entry = entries.setdefault(str(member.id), {"total_seconds": 0, "active_since": None})
        currently_active = bool(entry.get("active_since"))
        should_be_active = _active_now(status)

        if should_be_active and not currently_active:
            entry["active_since"] = now.isoformat()
        elif not should_be_active and currently_active:
            active_since = _parse_timestamp(entry.get("active_since"))
            if active_since:
                entry["total_seconds"] = int(entry.get("total_seconds", 0)) + max(
                    0, int((now - active_since).total_seconds())
                )
            entry["active_since"] = None
        set_scfg(member.guild.id, cfg)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.status != after.status:
            await self._update_presence(after, after.status)

    @commands.Cog.listener()
    async def on_ready(self):
        """Start sessions for staff who were already active at bot startup."""
        for guild in self.bot.guilds:
            cfg = get_scfg(guild.id)
            role = _staff_role(guild, cfg)
            if not role:
                continue
            now = datetime.now(timezone.utc)
            date_key = now.date().isoformat()
            entries = cfg.setdefault("online_time", {}).setdefault(date_key, {})
            changed = False
            for member in role.members:
                if member.bot or not _active_now(member.status):
                    continue
                entry = entries.setdefault(
                    str(member.id),
                    {"total_seconds": 0, "active_since": None},
                )
                if not entry.get("active_since"):
                    entry["active_since"] = now.isoformat()
                    changed = True
            if changed:
                set_scfg(guild.id, cfg)

    @tasks.loop(minutes=1)
    async def online_flush_task(self):
        now = datetime.now(timezone.utc)
        date_key = now.date().isoformat()
        for guild in self.bot.guilds:
            cfg = get_scfg(guild.id)
            if cfg.get("online_time", {}).get(date_key):
                _flush_online_sessions(cfg, date_key, now)
                set_scfg(guild.id, cfg)

    @online_flush_task.before_loop
    async def before_online_flush_task(self):
        await self.bot.wait_until_ready()

    @commands.command(
        name="performance",
        help="Show the staff leaderboard or one staff member. Usage: !performance [@user]",
    )
    @commands.has_permissions(manage_guild=True)
    async def performance(
        self,
        ctx: commands.Context,
        member: discord.Member = None,
    ):
        if not ctx.guild:
            return await ctx.send("This command must be used inside a server.")

        cfg = get_scfg(ctx.guild.id)
        role = _staff_role(ctx.guild, cfg)
        if not role:
            return await ctx.send(
                embed=discord.Embed(
                    title="Staff Role Required",
                    description="Configure the normal staff role first with `!staff_role @role`.",
                    color=WARNING,
                )
            )

        now = datetime.now(timezone.utc)
        date_key = _today()
        _flush_online_sessions(cfg, date_key, now)
        set_scfg(ctx.guild.id, cfg)

        members = [item for item in role.members if not item.bot]
        if member:
            if member.bot or member not in members:
                return await ctx.send(
                    embed=discord.Embed(
                        title="Not a Staff Member",
                        description=f"{member.mention} is not in the configured staff role {role.mention}.",
                        color=DANGER,
                    )
                )
            stats = _metrics(cfg, member, date_key, now)
            embed = discord.Embed(
                title=f"Performance — {member.display_name}",
                description=(
                    f"Daily performance breakdown for {date_key}.\n"
                    "Score: **50 target + 30 invasion + 20 online points**."
                ),
                color=SUCCESS,
                timestamp=now,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name="Target Progress",
                value=(
                    f"**{stats['messages']} / {stats['target']} messages** "
                    f"({stats['target_percent']}%)\n"
                    f"Points: **{stats['target_points']} / 50**"
                ),
                inline=False,
            )
            embed.add_field(
                name="Invasion Decisions",
                value=(
                    f"Accepted: **{stats['accepted']}**\n"
                    f"Ejected: **{stats['ejected']}**\n"
                    f"Points: **{stats['invasion_points']} / 30**"
                ),
                inline=True,
            )
            embed.add_field(
                name="Online Time",
                value=(
                    f"**{_format_duration(stats['online_seconds'])}**\n"
                    f"Points: **{stats['online_points']} / 20**"
                ),
                inline=True,
            )
            embed.add_field(name="Total Score", value=f"**{stats['score']} / 100**", inline=False)
            embed.set_footer(text=f"Nexora Cloud • Staff Performance • {role.name}")
            return await ctx.send(embed=embed)

        leaderboard = sorted(
            (_metrics(cfg, item, date_key, now) for item in members),
            key=lambda item: (-item["score"], -item["messages"], item["member"].display_name.casefold()),
        )
        if not leaderboard:
            return await ctx.send(
                embed=discord.Embed(
                    title="Staff Performance Leaderboard",
                    description=f"No members are assigned to {role.mention}.",
                    color=WARNING,
                )
            )

        lines = []
        for index, stats in enumerate(leaderboard[:25], start=1):
            member = stats["member"]
            lines.append(
                f"`#{index}` {member.mention} — **{stats['score']} / 100**\n"
                f" Target: {stats['messages']}/{stats['target']} • "
                f"Invades: {stats['accepted']} accepted / {stats['ejected']} ejected • "
                f"Online: {_format_duration(stats['online_seconds'])}"
            )

        embed = discord.Embed(
            title="Staff Performance Leaderboard",
            description=(
                f"Daily ranking for **{date_key}** • Role: {role.mention}\n"
                "Score weights: target **50%**, invasions **30%**, online time **20%**.\n\n"
                + "\n".join(lines)
            ),
            color=SUCCESS,
            timestamp=now,
        )
        embed.set_footer(text="Use !performance @user for an individual breakdown.")
        await ctx.send(embed=embed)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You need Manage Server permission to use `!performance`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Error: Mention a valid server member.")
        else:
            await ctx.send(f"Performance error: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))