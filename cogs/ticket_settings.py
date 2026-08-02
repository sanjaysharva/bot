"""
cogs/ticket_settings.py — Nexora Cloud
Prefix-based ticket configuration: setup, role, category, embed, log channel, panel channel, blacklist, limits, auto-close, rating.
"""

from datetime import datetime, timezone

import discord
from discord.ext import commands

from ._shared import guild_data, save_guild, ACCENT, SUCCESS


class TicketSettings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── !ticket_setup ────────────────────────────────────────────────────────────
    @commands.command(name="ticket_setup", help="Configure the ticket system (staff role + category). Usage: !ticket_setup @role [category]")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx: commands.Context, staff_role: discord.Role, category: discord.CategoryChannel = None):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["staff_role_id"] = staff_role.id
        if category:
            cfg["category_id"] = category.id
        save_guild(ctx.guild.id, cfg, "ticket_config")
        embed = discord.Embed(
            title="Ticket System Configured",
            description=f"**Staff Role:** {staff_role.mention}\n**Category:** {category.mention if category else '*None*'}\n\nUse `!ticket_panel` to post the panel.",
            color=SUCCESS,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    # ── !ticket_role ─────────────────────────────────────────────────────────────
    @commands.command(name="ticket_role", help="Set or update the ticket staff role. Usage: !ticket_role @role")
    @commands.has_permissions(administrator=True)
    async def ticket_role(self, ctx: commands.Context, role: discord.Role):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["staff_role_id"] = role.id
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"Ticket staff role set to {role.mention}.")

    # ── !ticket_category ─────────────────────────────────────────────────────────
    @commands.command(name="ticket_category", help="Set or update the ticket category channel. Usage: !ticket_category #category")
    @commands.has_permissions(administrator=True)
    async def ticket_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["category_id"] = category.id
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"Ticket category set to {category.mention}.")

    # ── !ticket_panel_channel ──────────────────────────────────────────────────
    @commands.command(name="ticket_panel_channel", help="Set the channel where the ticket panel is posted. Usage: !ticket_panel_channel #channel")
    @commands.has_permissions(administrator=True)
    async def ticket_panel_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["panel_channel_id"] = channel.id
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"Ticket panel channel set to {channel.mention}.")

    # ── !ticket_log_channel ────────────────────────────────────────────────────
    @commands.command(name="ticket_log_channel", help="Set the channel for ticket transcripts and logs. Usage: !ticket_log_channel #channel")
    @commands.has_permissions(administrator=True)
    async def ticket_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["log_channel_id"] = channel.id
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"Ticket log channel set to {channel.mention}.")

    # ── !ticket_embed_setup ──────────────────────────────────────────────────────
    @commands.command(name="ticket_embed_setup", help="Customize the ticket panel embed. Usage: !ticket_embed_setup \"title\" \"description\" [#hexcolor] [\"footer\"]")
    @commands.has_permissions(administrator=True)
    async def ticket_embed_setup(self, ctx: commands.Context, title: str, description: str, color: str = "", footer: str = ""):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["panel_title"] = title
        cfg["panel_description"] = description.replace("\\n", "\n")
        if color:
            try:
                int(color.lstrip("#"), 16)
                cfg["panel_color"] = color
            except ValueError:
                return await ctx.send("Error: Invalid hex color.")
        if footer:
            cfg["panel_footer"] = footer
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send("Ticket panel embed settings saved. Use `!ticket_panel` to post it.")

    # ── !ticket_welcome_msg ──────────────────────────────────────────────────────
    @commands.command(name="ticket_welcome_msg", help="Customize the welcome message inside new tickets. Variables: {user}, {type}, {ticket_id}")
    @commands.has_permissions(administrator=True)
    async def ticket_welcome_msg(self, ctx: commands.Context, *, message: str):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["welcome_message"] = message.replace("\\n", "\n")
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send("Ticket welcome message updated. Variables: {user}, {type}, {ticket_id}")

    # ── !ticket_blacklist ───────────────────────────────────────────────────────
    @commands.command(name="ticket_blacklist", help="Prevent a user from opening tickets. Usage: !ticket_blacklist @user")
    @commands.has_permissions(administrator=True)
    async def ticket_blacklist(self, ctx: commands.Context, user: discord.User):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        blacklist = cfg.setdefault("blacklist", [])
        if user.id in blacklist:
            return await ctx.send(f"{user.mention} is already blacklisted.")
        blacklist.append(user.id)
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"{user.mention} has been blacklisted from opening tickets.")

    # ── !ticket_unblacklist ──────────────────────────────────────────────────────
    @commands.command(name="ticket_unblacklist", help="Remove a user from the ticket blacklist. Usage: !ticket_unblacklist @user")
    @commands.has_permissions(administrator=True)
    async def ticket_unblacklist(self, ctx: commands.Context, user: discord.User):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        blacklist = cfg.setdefault("blacklist", [])
        if user.id not in blacklist:
            return await ctx.send(f"{user.mention} is not blacklisted.")
        blacklist.remove(user.id)
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"{user.mention} has been removed from the ticket blacklist.")

    # ── !ticket_limit ────────────────────────────────────────────────────────────
    @commands.command(name="ticket_limit", help="Set the maximum number of open tickets per user. Usage: !ticket_limit <1-10>")
    @commands.has_permissions(administrator=True)
    async def ticket_limit(self, ctx: commands.Context, limit: int):
        if not (1 <= limit <= 10):
            return await ctx.send("Error: Limit must be between 1 and 10.")
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["ticket_limit"] = limit
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"Max open tickets per user set to **{limit}**.")

    # ── !ticket_auto_close ───────────────────────────────────────────────────────
    @commands.command(name="ticket_auto_close", help="Set hours of inactivity before auto-closing tickets. 0 disables it.")
    @commands.has_permissions(administrator=True)
    async def ticket_auto_close(self, ctx: commands.Context, hours: int):
        if hours < 0:
            return await ctx.send("Error: Hours must be 0 or more.")
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["auto_close_hours"] = hours
        save_guild(ctx.guild.id, cfg, "ticket_config")
        if hours == 0:
            await ctx.send("Auto-close is now disabled.")
        else:
            await ctx.send(f"Tickets will auto-close after **{hours} hours** of inactivity.")

    # ── !ticket_rating ───────────────────────────────────────────────────────────
    @commands.command(name="ticket_rating", help="Toggle the post-close satisfaction rating DM. Usage: !ticket_rating <on/off>")
    @commands.has_permissions(administrator=True)
    async def ticket_rating(self, ctx: commands.Context, enabled: str):
        flag = enabled.lower() in ("on", "true", "yes", "1", "enable")
        cfg = guild_data(ctx.guild.id, "ticket_config")
        cfg["rating_enabled"] = flag
        save_guild(ctx.guild.id, cfg, "ticket_config")
        await ctx.send(f"Post-close rating requests are now **{'enabled' if flag else 'disabled'}**.")

    # ── !ticket_config ───────────────────────────────────────────────────────────
    @commands.command(name="ticket_config", help="Show current ticket system configuration.")
    @commands.has_permissions(administrator=True)
    async def ticket_config(self, ctx: commands.Context):
        cfg = guild_data(ctx.guild.id, "ticket_config")
        role_id = cfg.get("staff_role_id")
        cat_id  = cfg.get("category_id")
        panel_id = cfg.get("panel_channel_id")
        log_id  = cfg.get("log_channel_id")
        role = ctx.guild.get_role(int(role_id)) if role_id else None
        cat  = ctx.guild.get_channel(int(cat_id)) if cat_id else None
        panel = ctx.guild.get_channel(int(panel_id)) if panel_id else None
        log = ctx.guild.get_channel(int(log_id)) if log_id else None
        embed = discord.Embed(
            title="Advanced Ticket Configuration",
            description="Current settings for the ticket system.",
            color=ACCENT,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Staff Role", value=role.mention if role else "*Not set*", inline=True)
        embed.add_field(name="Category", value=cat.mention if cat else "*Not set*", inline=True)
        embed.add_field(name="Panel Channel", value=panel.mention if panel else "*Not set*", inline=True)
        embed.add_field(name="Log Channel", value=log.mention if log else "*Not set*", inline=True)
        embed.add_field(name="Panel Title", value=cfg.get("panel_title", "Nexora Cloud — Support Center"), inline=False)
        embed.add_field(name="Panel Color", value=cfg.get("panel_color", "#5865F2"), inline=True)
        embed.add_field(name="Max Open Tickets", value=cfg.get("ticket_limit", "Unlimited"), inline=True)
        embed.add_field(name="Auto-Close", value=f"{cfg.get('auto_close_hours', 0)} hours" if cfg.get('auto_close_hours', 0) else "Disabled", inline=True)
        embed.add_field(name="Post-Close Rating", value="Enabled" if cfg.get("rating_enabled", False) else "Disabled", inline=True)
        embed.add_field(name="Blacklisted Users", value=str(len(cfg.get("blacklist", []))), inline=True)
        await ctx.send(embed=embed)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You need Administrator permission.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Error: Missing required argument `{error.param.name}`. Check `!help {ctx.command.name}`.")
        else:
            await ctx.send(f"Error: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketSettings(bot))
