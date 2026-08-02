"""
cogs/ticket_panel.py — Nexora Cloud
Ticket panel, dropdown, 3-step purchase flow, and persistent views.
"""

import asyncio
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import guild_data, save_guild, now_ts, is_ticket, ACCENT, SUCCESS, WARNING, DANGER, PURPLE


# ═══════════════════════════════════════════════════════════════════════════════
#   PURCHASE FLOW  (multi-step buttons + select)
# ═══════════════════════════════════════════════════════════════════════════════

PLAN_DATA = {
    "Starter":     {"value": "Starter",     "price": "$5/mo",  "desc": "Perfect for small projects & testing"},
    "Pro":         {"value": "Pro",         "price": "$15/mo", "desc": "Ideal for growing services"},
    "Business":    {"value": "Business",    "price": "$40/mo", "desc": "For serious production workloads"},
    "Enterprise":  {"value": "Enterprise",  "price": "$99/mo", "desc": "Maximum power & priority support"},
    "Custom":      {"value": "Custom",      "price": "Contact", "desc": "Tailored to your exact needs"},
}

SPEC_OPTIONS = [
    ("1 vCPU / 1 GB RAM", "nano"),
    ("2 vCPU / 2 GB RAM", "micro"),
    ("4 vCPU / 4 GB RAM", "small"),
    ("4 vCPU / 8 GB RAM", "medium"),
    ("8 vCPU / 16 GB RAM", "large"),
    ("16 vCPU / 32 GB RAM", "xlarge"),
    ("Custom Spec", "custom"),
]


class PlanButton(discord.ui.Button):
    def __init__(self, label: str, data: dict, channel: discord.TextChannel, opener: discord.Member):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.data    = data
        self.channel = channel
        self.opener  = opener

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.opener.id:
            await interaction.response.send_message("This isn't your ticket flow.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.message.delete()
        await _show_spec_step(self.channel, self.opener, self.data)


class PlanSelectView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, opener: discord.Member):
        super().__init__(timeout=180)
        for label, data in PLAN_DATA.items():
            self.add_item(PlanButton(label, data, channel, opener))


class SpecSelectView(discord.ui.View):
    def __init__(self, channel, opener, plan):
        super().__init__(timeout=180)
        self.channel = channel
        self.opener  = opener
        self.plan    = plan

        options = [discord.SelectOption(label=label, value=slug) for label, slug in SPEC_OPTIONS]
        select = discord.ui.Select(placeholder="Choose a server spec…", options=options, min_values=1, max_values=1)
        select.callback = self._spec_chosen
        self.add_item(select)

    async def _spec_chosen(self, interaction: discord.Interaction):
        if interaction.user.id != self.opener.id:
            await interaction.response.send_message("This isn't your ticket flow.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.message.delete()
        spec_slug  = interaction.data["values"][0]
        spec_label = next(label for label, slug in SPEC_OPTIONS if slug == spec_slug)
        await _show_confirm_step(self.channel, self.opener, self.plan, spec_label)


class ConfirmView(discord.ui.View):
    def __init__(self, channel, opener, plan, spec):
        super().__init__(timeout=180)
        self.channel = channel
        self.opener  = opener
        self.plan    = plan
        self.spec    = spec

    @discord.ui.button(label="Confirm Order", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opener.id:
            await interaction.response.send_message("This isn't your ticket.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.message.delete()
        embed = discord.Embed(
            title="Purchase Request Received",
            description=(
                f"Your order has been submitted successfully.\n\n"
                f"**Plan:** {self.plan['value']}\n"
                f"**Spec:** {self.spec}\n"
                f"**Price:** {self.plan['price']}\n\n"
                f"A member of staff will review and process your order shortly. Please keep this ticket open until you hear back."
            ),
            color=SUCCESS,
            timestamp=datetime.now(timezone.utc)
        )
        await self.channel.send(embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opener.id:
            await interaction.response.send_message("This isn't your ticket.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.message.delete()
        await self.channel.send(embed=discord.Embed(description="Order cancelled. Feel free to restart by opening a new ticket.", color=DANGER))


async def _show_plan_step(channel, opener):
    embed = discord.Embed(
        title="Choose Your Plan",
        description=(
            "```\n  Welcome to Nexora Cloud!\n  Select the plan that fits you best.\n```\n"
            + "\n".join(f"**{d['value']}**  —  {d['price']}\n   *{d['desc']}*" for d in PLAN_DATA.values())
        ),
        color=PURPLE,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name="Nexora Cloud — Purchase Flow")
    embed.set_footer(text="Step 1 of 3 — Pick a plan below")
    await channel.send(content=f"{opener.mention}", embed=embed, view=PlanSelectView(channel, opener))


async def _show_spec_step(channel, opener, plan):
    embed = discord.Embed(
        title=f"{plan['value']} — Pick Your Specs",
        description=(
            f"Plan locked in: **{plan['value']}** at **{plan['price']}**\n\n"
            "Now choose the server specification that fits your workload:\n\n"
            + "\n".join(f"**{label}**" for label, _ in SPEC_OPTIONS)
        ),
        color=ACCENT,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name="Nexora Cloud — Purchase Flow")
    embed.set_footer(text="Step 2 of 3 — Pick specs below")
    await channel.send(content=f"{opener.mention}", embed=embed, view=SpecSelectView(channel, opener, plan))


async def _show_confirm_step(channel, opener, plan, spec):
    embed = discord.Embed(
        title="Order Summary — Confirm?",
        description=(
            "```yaml\n"
            f"  Plan  :  {plan['value']}\n"
            f"  Spec  :  {spec}\n"
            f"  Price :  {plan['price']}\n"
            "```\nEverything look good? Hit **Confirm** to submit your order or **Cancel** to start over."
        ),
        color=SUCCESS,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name="Nexora Cloud — Purchase Flow")
    embed.set_footer(text="Step 3 of 3 — Confirm your order")
    await channel.send(content=f"{opener.mention}", embed=embed, view=ConfirmView(channel, opener, plan, spec))


# ═══════════════════════════════════════════════════════════════════════════════
#   TICKET PANEL DROPDOWN
# ═══════════════════════════════════════════════════════════════════════════════

class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support",  value="general",  description="Questions, help, or anything else", emoji="<a:msg:1529512238443139195> "),
            discord.SelectOption(label="Error / Bug Report", value="error", description="Report an issue or service error", emoji="<a:HelpHelp:1529509045575221478> "),
            discord.SelectOption(label="Purchase / Upgrade", value="purchase", description="Buy a plan or upgrade your service",emoji="<a:buyer:1529508251518111754>"),
        ]
        super().__init__(placeholder="Select a ticket category…", options=options, min_values=1, max_values=1, custom_id="nexora:ticket_type")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ticket_type = self.values[0]
        guild       = interaction.guild
        member      = interaction.user

        cfg = guild_data(guild.id, "ticket_config")
        staff_role_id = cfg.get("staff_role_id")
        category_id   = cfg.get("category_id")
        staff_role = guild.get_role(int(staff_role_id)) if staff_role_id else None
        category   = guild.get_channel(int(category_id)) if category_id else None

        # Blacklist check
        if member.id in cfg.get("blacklist", []):
            await interaction.followup.send("You are blacklisted from opening tickets. Contact an administrator.", ephemeral=True)
            return

        # Ticket limit check
        limit = cfg.get("ticket_limit")
        if limit:
            open_count = sum(1 for c in guild.channels if c.name.startswith("ticket-") and hasattr(c, "topic") and f"Opened by: {member}" in (c.topic or ""))
            if open_count >= limit:
                await interaction.followup.send(f"You already have **{limit}** open ticket(s). Please close one before opening another.", ephemeral=True)
                return

        # Staff role / category validation
        if not staff_role:
            await interaction.followup.send("Ticket staff role is not configured. Ask an admin to run `!ticket_setup` or `/ticket_panel`.", ephemeral=True)
            return
        if not category:
            await interaction.followup.send("Ticket category is not configured. Ask an admin to run `!ticket_setup` or `/ticket_panel`.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member:             discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
            guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True, manage_messages=True),
        }
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True, attach_files=True, embed_links=True)

        tid = str(now_ts())[-5:]
        type_labels = {"general": "general", "error": "error", "purchase": "purchase"}
        name = f"ticket-{type_labels[ticket_type]}-{member.name[:12]}-{tid}"

        try:
            channel = await guild.create_text_channel(name=name, overwrites=overwrites, category=category, topic=f"Ticket #{tid} | Type: {ticket_type} | Opened by: {member} ({member.id}) | Status: open")
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to create channels.", ephemeral=True)
            return

        # Persist ticket metadata
        cfg["tickets"] = cfg.get("tickets", {})
        cfg["tickets"][tid] = {
            "channel_id": channel.id,
            "opener_id": member.id,
            "type": ticket_type,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "status": "open",
            "priority": "Medium",
            "tags": [],
            "claimed_by": None,
        }
        save_guild(guild.id, cfg, "ticket_config")

        type_meta = {
            "general":  ("General Support", "Describe your question or issue below and a staff member will assist you shortly.", ACCENT),
            "error":    ("Error / Bug Report", "Please describe the error — include any messages, screenshots, or steps to reproduce.", WARNING),
            "purchase": ("Purchase Enquiry", "Let's get your order started! Follow the steps below.", PURPLE),
        }
        title, prompt, color = type_meta[ticket_type]

        welcome = cfg.get("welcome_message", "Welcome {user}!\n\n{prompt}\n\n> **Opened by:** {user}\n> **Category:** {type}\n> **Status:** Open\n> **Ticket ID:** {ticket_id}\n\n*Use the button below to close this ticket when resolved.*")
        welcome = welcome.replace("{user}", member.mention).replace("{type}", title).replace("{ticket_id}", tid).replace("{prompt}", prompt)

        embed = discord.Embed(
            title=f"{title} — Ticket #{tid}",
            description=welcome,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name="Nexora Cloud Support", icon_url=(guild.icon.url if guild.icon else None))
        embed.set_footer(text=f"Ticket ID: {tid}")

        ping = staff_role.mention
        msg = await channel.send(content=f"{ping} {member.mention}", embed=embed, view=TicketControlView(tid))
        await msg.pin()

        if ticket_type == "purchase":
            await asyncio.sleep(1)
            await _show_plan_step(channel, member)

        # Log to ticket log channel if configured
        log_id = cfg.get("log_channel_id")
        if log_id:
            log_channel = guild.get_channel(int(log_id))
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Ticket Created — #{tid}",
                    description=f"**Opener:** {member.mention}\n**Type:** {title}\n**Channel:** {channel.mention}",
                    color=SUCCESS,
                    timestamp=datetime.now(timezone.utc)
                )
                await log_channel.send(embed=log_embed)

        await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


class TicketControlView(discord.ui.View):
    def __init__(self, tid: str):
        super().__init__(timeout=None)
        self.tid = tid

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="nexora:close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        from ._shared import do_close
        await do_close(interaction, "Closed via button")


# ═══════════════════════════════════════════════════════════════════════════════
#   COG
# ═══════════════════════════════════════════════════════════════════════════════

class TicketPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketPanelView())

    @app_commands.command(name="ticket_panel", description="Post the Nexora Cloud support ticket panel.")
    @app_commands.describe(channel="Channel to post the panel in (defaults to current channel)", panel_title="Override the panel title", panel_description="Override the panel description")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        panel_title: str = None,
        panel_description: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        cfg = guild_data(interaction.guild.id, "ticket_config")
        title       = panel_title or cfg.get("panel_title", "Nexora Cloud — Support Center")
        description = panel_description or cfg.get("panel_description", None)
        color       = int(cfg.get("panel_color", "0xFAC234"), 16)

        if not description:
            description = (
                "```\n  Need help? We are here for you.\n  Select a category below to open a ticket.\n```\n"
                "**General Support**\nQuestions, guidance, account help\n\n"
                "**Error / Bug Report**\nReport an issue with your service\n\n"
                "**Purchase / Upgrade**\nBuy or upgrade your cloud plan\n\n"
                "*Tickets are private — only you and our staff can see them.*\n"
                "*Our team typically responds within 1–2 hours.*"
            )

        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_author(name="Nexora Cloud Support", icon_url=(interaction.guild.icon.url if interaction.guild.icon else None))
        embed.set_footer(text="Nexora Cloud — Professional Cloud Hosting")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        msg = await target.send(embed=embed, view=TicketPanelView())

        # Save panel message ID so it can be deleted/reposted later
        cfg["panel_message_id"] = msg.id
        cfg["panel_channel_id"] = target.id
        save_guild(interaction.guild.id, cfg, "ticket_config")

        await interaction.followup.send(f"Ticket panel posted in {target.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketPanel(bot))
