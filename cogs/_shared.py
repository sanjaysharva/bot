"""
cogs/_shared.py — Nexora Cloud
Common helpers used by the split company/support cogs.
"""

import asyncio
import json
import os
from datetime import datetime, timezone

import discord
from discord import app_commands

DATA_DIR = os.path.dirname(__file__)


def load_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, "..", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(filename: str, data: dict):
    path = os.path.join(DATA_DIR, "..", filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def guild_data(guild_id: int, data_name: str = "company_data") -> dict:
    all_data = load_json(f"{data_name}.json")
    g = all_data.setdefault(str(guild_id), {
        "orders": {},
        "blacklist": [],
        "whitelist": [],
        "strikes": {},
        "incidents": [],
        "audits": [],
        "kpi": {"orders": 0, "tickets": 0, "refunds": 0, "incidents": 0, "feedback": 0},
        "meetings": [],
        "vacations": {},
        "shifts": {},
        "status_page": "https://status.nexora.cloud",
    })
    return g


def save_guild(guild_id: int, data: dict, data_name: str = "company_data"):
    all_data = load_json(f"{data_name}.json")
    all_data[str(guild_id)] = data
    save_json(f"{data_name}.json", all_data)


def log_audit(guild_id: int, action: str, user: str, target: str = "", details: str = ""):
    data = guild_data(guild_id)
    data["audits"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user": user,
        "target": target,
        "details": details,
    })
    data["audits"] = data["audits"][-50:]
    save_guild(guild_id, data)


def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def is_ticket(channel) -> bool:
    return hasattr(channel, "topic") and channel.topic and "Opened by:" in channel.topic


async def build_transcript(channel: discord.TextChannel) -> str:
    """Build a text transcript of a ticket channel."""
    guild = channel.guild
    lines = [
        f"NEXORA CLOUD TICKET TRANSCRIPT",
        f"Channel: #{channel.name}",
        f"Guild: {guild.name}",
        f"Topic: {channel.topic or 'N/A'}",
        f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        "=" * 60,
    ]
    async for msg in channel.history(limit=500, oldest_first=True):
        time = msg.created_at.strftime('%Y-%m-%d %H:%M')
        content = msg.content or ""
        if msg.attachments:
            content += "\n[Attachments: " + ", ".join(a.url for a in msg.attachments) + "]"
        if msg.embeds:
            content += "\n[Embedded message]"
        lines.append(f"[{time}] {msg.author.display_name} ({msg.author.id}): {content}")
    return "\n".join(lines)


def parse_ticket_topic(channel: discord.TextChannel):
    """Extract ticket_id and opener_id from a ticket channel topic."""
    opener_id = None
    ticket_id = None
    for part in (channel.topic or "").split("|"):
        part = part.strip()
        if part.startswith("Opened by:"):
            try:
                opener_id = int(part.split("(")[-1].rstrip(")"))
            except Exception:
                pass
        if part.startswith("Ticket #"):
            try:
                ticket_id = part.split("#")[-1].strip()
            except Exception:
                pass
    return ticket_id, opener_id


async def close_ticket_channel(channel: discord.TextChannel, closed_by: discord.Member, reason: str = "Resolved"):
    """Core logic to close a ticket channel and save a transcript. Returns the opener_id or None."""
    guild = channel.guild
    ticket_id, opener_id = parse_ticket_topic(channel)
    transcript_text = await build_transcript(channel)

    closed_embed = discord.Embed(
        title="Ticket Closed — Nexora Cloud",
        description=(
            f"**Ticket:** `#{ticket_id or 'N/A'}`\n"
            f"**Channel:** #{channel.name}\n"
            f"**Closed by:** {closed_by.display_name}\n"
            f"**Reason:** {reason}\n"
            f"**Closed at:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"Thank you for reaching out to **Nexora Cloud**.\n"
            f"If you have further questions, open a new ticket anytime."
        ),
        color=DANGER,
        timestamp=datetime.now(timezone.utc)
    )
    closed_embed.set_author(name="Nexora Cloud Support", icon_url=(guild.icon.url if guild.icon else None))

    # Send transcript to log channel
    cfg = guild_data(guild.id, "ticket_config")
    log_id = cfg.get("log_channel_id")
    if log_id:
        log_channel = guild.get_channel(int(log_id))
        if log_channel:
            log_embed = discord.Embed(
                title=f"Ticket Transcript — #{ticket_id or 'N/A'}",
                description=f"**Channel:** #{channel.name}\n**Closed by:** {closed_by.display_name}\n**Reason:** {reason}",
                color=PURPLE,
                timestamp=datetime.now(timezone.utc)
            )
            log_embed.set_footer(text=f"Ticket ID: {ticket_id}")
            file = None
            if len(transcript_text) > 2000:
                from io import BytesIO
                file = discord.File(BytesIO(transcript_text.encode("utf-8")), filename=f"ticket-{ticket_id or 'unknown'}.txt")
            else:
                log_embed.add_field(name="Transcript", value=f"```{transcript_text[:1018]}```", inline=False)
            try:
                if file:
                    await log_channel.send(embed=log_embed, file=file)
                else:
                    await log_channel.send(embed=log_embed)
            except Exception:
                pass

    # DM opener
    if opener_id:
        try:
            opener = await guild.fetch_member(opener_id)
            await opener.send(embed=closed_embed)
        except Exception:
            pass

    # Update KPI
    data = guild_data(guild.id)
    data["kpi"]["tickets"] = data["kpi"].get("tickets", 0) + 1
    save_guild(guild.id, data)

    # Update metadata status
    if ticket_id and cfg.get("tickets", {}).get(ticket_id):
        cfg["tickets"][ticket_id]["status"] = "closed"
        cfg["tickets"][ticket_id]["closed_at"] = datetime.now(timezone.utc).isoformat()
        cfg["tickets"][ticket_id]["closed_by"] = closed_by.id
        save_guild(guild.id, cfg, "ticket_config")

    closing_embed = discord.Embed(
        title="Ticket Closing",
        description=f"This ticket is being closed by **{closed_by.display_name}**.\nReason: *{reason}*\n\nThe channel will be deleted in **5 seconds**.",
        color=DANGER,
        timestamp=datetime.now(timezone.utc)
    )
    await channel.send(embed=closing_embed)

    await asyncio.sleep(5)
    try:
        await channel.delete(reason=f"Ticket closed by {closed_by}")
    except Exception:
        pass

    return opener_id


async def do_close(interaction: discord.Interaction, reason: str = "Resolved"):
    """Close a ticket channel from a slash command or button interaction."""
    channel = interaction.channel
    guild   = interaction.guild

    if not is_ticket(channel):
        await interaction.response.send_message("Error: This is not a ticket channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await close_ticket_channel(channel, interaction.user, reason)
    await interaction.followup.send("Ticket is closing.", ephemeral=True)


# Common colors
ACCENT  = 0x5865F2
SUCCESS = 0x22C55E
WARNING = 0xF59E0B
DANGER  = 0xEF4444
PURPLE  = 0x8B5CF6
CYAN    = 0x06B6D4

# Common choices
PRIORITY_CHOICES = [
    app_commands.Choice(name="Low", value="Low"),
    app_commands.Choice(name="Medium", value="Medium"),
    app_commands.Choice(name="High", value="High"),
    app_commands.Choice(name="Critical", value="Critical"),
]

TAG_CHOICES = [
    app_commands.Choice(name="Billing", value="billing"),
    app_commands.Choice(name="Technical", value="technical"),
    app_commands.Choice(name="Sales", value="sales"),
    app_commands.Choice(name="Urgent", value="urgent"),
    app_commands.Choice(name="Provisioning", value="provisioning"),
]

STATUS_CHOICES = [
    app_commands.Choice(name="Operational", value="Operational"),
    app_commands.Choice(name="Degraded", value="Degraded"),
    app_commands.Choice(name="Major Outage", value="Major Outage"),
    app_commands.Choice(name="Maintenance", value="Maintenance"),
]

SEVERITY_CHOICES = [
    app_commands.Choice(name="P4 — Low", value="P4"),
    app_commands.Choice(name="P3 — Medium", value="P3"),
    app_commands.Choice(name="P2 — High", value="P2"),
    app_commands.Choice(name="P1 — Critical", value="P1"),
]

PLAN_CHOICES = [
    app_commands.Choice(name="Starter", value="Starter"),
    app_commands.Choice(name="Pro", value="Pro"),
    app_commands.Choice(name="Business", value="Business"),
    app_commands.Choice(name="Enterprise", value="Enterprise"),
    app_commands.Choice(name="Custom", value="Custom"),
]

SPEC_CHOICES = [
    app_commands.Choice(name="1 vCPU / 1 GB", value="1 vCPU / 1 GB"),
    app_commands.Choice(name="2 vCPU / 4 GB", value="2 vCPU / 4 GB"),
    app_commands.Choice(name="4 vCPU / 8 GB", value="4 vCPU / 8 GB"),
    app_commands.Choice(name="8 vCPU / 16 GB", value="8 vCPU / 16 GB"),
    app_commands.Choice(name="16 vCPU / 32 GB", value="16 vCPU / 32 GB"),
    app_commands.Choice(name="Custom Spec", value="Custom Spec"),
]
