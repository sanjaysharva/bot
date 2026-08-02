"""
cogs/server_panel.py — Nexora Cloud
Per-user Pterodactyl server control. Every user links their own panel Client API key,
runs `!server` to pick one of their Pterodactyl servers, and gets a private channel with
power/control buttons. No shared password is needed.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from ._shared import ACCENT, SUCCESS, DANGER, WARNING, CYAN, log_audit
from ._pterodactyl import (
    get_user_config,
    set_user_config,
    power_action,
    send_command,
    list_servers,
    server_details,
    server_resources,
    test_connection,
    request_upload_url,
    upload_to_signed_url,
)

UPLOAD_DIRECTORIES = [
    ("/", "Root directory"),
    ("/config", "Config files"),
    ("/plugins", "Plugins"),
    ("/mods", "Mods"),
    ("/world", "World data"),
    ("/logs", "Log files"),
    ("/backups", "Backups"),
]

SERVER_FILE = os.path.join(os.path.dirname(__file__), "..", "server_data.json")


# ── Data helpers ──────────────────────────────────────────────────────────────


def _load_data() -> dict:
    if os.path.exists(SERVER_FILE):
        with open(SERVER_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_data(data: dict):
    with open(SERVER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_guild_data(guild_id: int) -> dict:
    all_data = _load_data()
    key = str(guild_id)
    if key not in all_data:
        all_data[key] = {"pool": [], "user_panels": {}}
        _save_data(all_data)
    return all_data[key]


def _save_guild_data(guild_id: int, data: dict):
    all_data = _load_data()
    all_data[str(guild_id)] = data
    _save_data(all_data)


def _generate_server_id(guild_data: dict) -> str:
    count = len(guild_data.get("pool", [])) + 1
    return f"srv-{count:04d}"


def _find_server(guild_data: dict, server_id: str) -> Optional[dict]:
    for srv in guild_data.get("pool", []):
        if srv.get("id") == server_id:
            return srv
    return None


def _get_user_panels(guild_data: dict) -> dict:
    return guild_data.setdefault("user_panels", {})


def _find_user_panel(guild_data: dict, channel_id: int) -> Optional[dict]:
    return _get_user_panels(guild_data).get(str(channel_id))


def _find_user_panel_by_identifier(guild_data: dict, user_id: int, identifier: str) -> Optional[dict]:
    for panel in _get_user_panels(guild_data).values():
        if panel.get("user_id") == user_id and panel.get("identifier") == identifier:
            return panel
    return None


def _slug(name: str) -> str:
    return "".join(c for c in name.lower().replace(" ", "-") if c.isalnum() or c == "-")[:20]


def _status_style(state: Optional[str]) -> tuple:
    if not state:
        return ("Unknown", 0x808080)
    state = state.lower()
    if state == "running":
        return ("Online", SUCCESS)
    if state == "starting":
        return ("Starting", WARNING)
    if state == "stopping":
        return ("Stopping", WARNING)
    if state == "offline":
        return ("Offline", DANGER)
    return (state.capitalize(), CYAN)


async def _get_or_create_category(guild: discord.Guild) -> discord.CategoryChannel:
    existing = discord.utils.get(guild.categories, name="Server Panels")
    if existing:
        return existing
    return await guild.create_category("Server Panels", reason="Nexora Cloud server control panels")


async def _create_private_panel_channel(guild: discord.Guild, name: str, owner: discord.Member) -> discord.TextChannel:
    category = await _get_or_create_category(guild)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True, attach_files=True, embed_links=True),
        owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
    }
    return await guild.create_text_channel(
        name=_slug(name),
        category=category,
        overwrites=overwrites,
        topic=f"Personal Pterodactyl server panel for {owner.display_name}."
    )


async def _create_pool_panel_channel(guild: discord.Guild, name: str, owner: discord.Member, admin_roles: list) -> discord.TextChannel:
    category = await _get_or_create_category(guild)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True, attach_files=True, embed_links=True),
        owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
    }
    for role in admin_roles:
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, attach_files=True, embed_links=True)
    return await guild.create_text_channel(
        name=_slug(name),
        category=category,
        overwrites=overwrites,
        topic=f"Pterodactyl-linked server control panel for {name}."
    )


# ── Views ─────────────────────────────────────────────────────────────────────


class UserServerSelect(discord.ui.Select):
    """Dropdown of the user's Pterodactyl servers."""

    def __init__(self, ptero_servers: list, user: discord.Member, channel: discord.TextChannel):
        select_options = []
        for srv in ptero_servers[:25]:
            attr = srv.get("attributes", {})
            name = attr.get("name", "Unnamed")[:25]
            identifier = attr.get("identifier", "unknown")
            description = f"ID: {identifier}"[:50]
            select_options.append(discord.SelectOption(label=name, value=identifier, description=description))
        super().__init__(placeholder="Choose your Pterodactyl server...", options=select_options, min_values=1, max_values=1)
        self.user = user
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        identifier = self.values[0]
        cog = interaction.client.get_cog("ServerPanel")
        if not cog:
            return await interaction.followup.send("Error: ServerPanel cog not loaded.", ephemeral=True)
        await cog._create_user_panel(interaction, self.user, identifier)


class UserServerView(discord.ui.View):
    def __init__(self, ptero_servers: list, user: discord.Member, channel: discord.TextChannel):
        super().__init__(timeout=180)
        if not ptero_servers:
            self.add_item(discord.ui.Button(label="No servers found in your Pterodactyl account", disabled=True))
            return
        self.add_item(UserServerSelect(ptero_servers, user, channel))


class UploadDirectorySelect(discord.ui.Select):
    """Dropdown to choose the directory for file uploads."""

    def __init__(self, channel_id: int):
        select_options = []
        for path, description in UPLOAD_DIRECTORIES:
            select_options.append(discord.SelectOption(label=path or "/", value=path, description=description))
        super().__init__(placeholder="Select folder to upload files to...", options=select_options, min_values=1, max_values=1)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("ServerPanel")
        if not cog:
            return await interaction.followup.send("Error: ServerPanel cog not loaded.", ephemeral=True)
        directory = self.values[0]
        cog._pending_upload_dirs[self.channel_id] = directory
        await interaction.followup.send(
            f"Upload target set to `{directory}`. Attach your file(s) in this channel and the bot will upload them to the server.",
            ephemeral=True,
        )


class UploadDirectoryView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=180)
        self.add_item(UploadDirectorySelect(channel_id))


class UserRunCommandModal(discord.ui.Modal, title="Run Server Command"):
    command = discord.ui.TextInput(label="Command", required=True, placeholder="e.g. say Server restarting", style=discord.TextStyle.paragraph)

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("ServerPanel")
        if not cog:
            return await interaction.followup.send("Error: ServerPanel cog not loaded.", ephemeral=True)
        await cog._run_user_command(interaction, self.channel_id, self.command.value)


class UserServerControlView(discord.ui.View):
    """Buttons for a user's personal Pterodactyl server panel."""

    def __init__(self, channel_id: int, timeout: float = None):
        super().__init__(timeout=timeout)
        self.channel_id = channel_id

    async def _panel(self, interaction: discord.Interaction) -> Optional[dict]:
        guild_data = _get_guild_data(interaction.guild.id)
        return _find_user_panel(guild_data, self.channel_id)

    async def _can_use(self, interaction: discord.Interaction) -> bool:
        panel = await self._panel(interaction)
        if not panel:
            return False
        return interaction.user.id == panel.get("user_id") or interaction.user.guild_permissions.administrator

    async def _ptero_action(self, interaction: discord.Interaction, signal: str, title: str, color: int):
        if not await self._can_use(interaction):
            return await interaction.response.send_message("You cannot use this panel.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        panel = _find_user_panel(guild_data, self.channel_id)
        if not panel:
            return await interaction.followup.send("Error: Panel not found.", ephemeral=True)

        user_id = panel.get("user_id")
        identifier = panel.get("identifier")
        past_tense = {"start": "started", "stop": "stopped", "restart": "restarted", "kill": "killed"}.get(signal, f"{signal}ed")
        status_text = f"server {past_tense}"

        try:
            await power_action(identifier, signal, user_id=user_id)
        except Exception as e:
            status_text = f"Pterodactyl error: {e}"

        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            try:
                await _refresh_user_panel_embed(channel, panel, guild_id)
            except Exception:
                pass
            embed = discord.Embed(title=f"Server {title}", color=color, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Server", value=panel.get("name", "Unknown"), inline=True)
            embed.add_field(name="Action by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Status", value=status_text, inline=True)
            await channel.send(embed=embed)

        await interaction.followup.send(f"Server `{panel.get('name')}` — {status_text}.", ephemeral=True)
        log_audit(guild_id, f"server_{signal}", str(interaction.user), panel.get("name"), f"channel:{self.channel_id}")

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green, custom_id="nexora:user_server_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._ptero_action(interaction, "start", "Started", SUCCESS)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, custom_id="nexora:user_server_stop")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._ptero_action(interaction, "stop", "Stopped", DANGER)

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.blurple, custom_id="nexora:user_server_restart")
    async def restart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._ptero_action(interaction, "restart", "Restarted", WARNING)

    @discord.ui.button(label="Run Command", style=discord.ButtonStyle.gray, custom_id="nexora:user_server_run")
    async def run_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._can_use(interaction):
            return await interaction.response.send_message("You cannot use this panel.", ephemeral=True)
        modal = UserRunCommandModal(self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Upload File", style=discord.ButtonStyle.gray, custom_id="nexora:user_server_upload", emoji="📤")
    async def upload_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._can_use(interaction):
            return await interaction.response.send_message("You cannot use this panel.", ephemeral=True)
        await interaction.response.send_message(
            "Select the folder you want to upload files to, then attach your files in this channel.",
            view=UploadDirectoryView(self.channel_id),
            ephemeral=True,
        )

    @discord.ui.button(label="Close Panel", style=discord.ButtonStyle.red, custom_id="nexora:user_server_close", emoji="🔒")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._can_use(interaction):
            return await interaction.response.send_message("You cannot use this panel.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        panel = _find_user_panel(guild_data, self.channel_id)
        if not panel:
            return await interaction.followup.send("Error: Panel not found.", ephemeral=True)

        channel = interaction.guild.get_channel(self.channel_id)
        if channel:
            await channel.send(f"Panel closed by {interaction.user.mention}. This channel will be deleted.")
            await channel.delete(reason="Nexora Cloud user server panel closed")

        _get_user_panels(guild_data).pop(str(self.channel_id), None)
        _save_guild_data(guild_id, guild_data)
        cog = interaction.client.get_cog("ServerPanel")
        if cog:
            cog._pending_upload_dirs.pop(self.channel_id, None)
        await interaction.followup.send("Server panel closed.", ephemeral=True)
        log_audit(guild_id, "user_server_panel_closed", str(interaction.user), panel.get("name"), f"channel:{self.channel_id}")


# ── Pool views (legacy admin pool) ─────────────────────────────────────────────


class ServerPoolSelect(discord.ui.Select):
    def __init__(self, options: list, user: discord.Member, channel: discord.TextChannel):
        select_options = []
        for srv in options[:25]:
            status = srv.get("status", "available")
            label = f"{srv['name']} ({status})"
            description = f"IP: {srv.get('ip', 'N/A')}"
            select_options.append(discord.SelectOption(label=label[:25], value=srv["id"], description=description[:50]))
        super().__init__(placeholder="Choose an available server to connect...", options=select_options, min_values=1, max_values=1)
        self.user = user
        self.channel = channel

    async def callback(self, interaction: discord.Interaction):
        server_id = self.values[0]
        cog = interaction.client.get_cog("ServerPanel")
        if not cog:
            return await interaction.response.send_message("Error: ServerPanel cog not loaded.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await cog._connect_pool_server(interaction, self.user, server_id)


class ServerPoolView(discord.ui.View):
    def __init__(self, options: list, user: discord.Member, channel: discord.TextChannel):
        super().__init__(timeout=180)
        if not options:
            self.add_item(discord.ui.Button(label="No servers available", disabled=True))
            return
        self.add_item(ServerPoolSelect(options, user, channel))


class PterodactylImportSelect(discord.ui.Select):
    def __init__(self, ptero_servers: list):
        select_options = []
        for srv in ptero_servers[:25]:
            attr = srv.get("attributes", {})
            name = attr.get("name", "Unnamed")[:25]
            identifier = attr.get("identifier", "unknown")
            description = f"ID: {identifier}"[:50]
            select_options.append(discord.SelectOption(label=name, value=identifier, description=description))
        super().__init__(placeholder="Choose an existing Pterodactyl server to import...", options=select_options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("ServerPanel")
        if not cog:
            return await interaction.followup.send("Error: ServerPanel cog not loaded.", ephemeral=True)
        identifier = self.values[0]
        try:
            details = await server_details(identifier, user_id=interaction.user.id)
            attr = details.get("attributes", {})
            name = attr.get("name", f"Server-{identifier}")
            ip = attr.get("sftp_details", {}).get("ip", "Set manually") or "Set manually"
            await cog._import_pterodactyl_server(interaction, name, ip, identifier)
        except Exception as e:
            await interaction.followup.send(f"Error importing server: {e}", ephemeral=True)


class PterodactylImportView(discord.ui.View):
    def __init__(self, ptero_servers: list):
        super().__init__(timeout=180)
        if not ptero_servers:
            self.add_item(discord.ui.Button(label="No Pterodactyl servers found", disabled=True))
            return
        self.add_item(PterodactylImportSelect(ptero_servers))


class RunCommandModal(discord.ui.Modal, title="Run Server Command"):
    command = discord.ui.TextInput(label="Command", required=True, placeholder="e.g. say Server restarting", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("ServerPanel")
        if not cog:
            return await interaction.followup.send("Error: ServerPanel cog not loaded.", ephemeral=True)
        await cog._run_command_for_panel(interaction, self.server_id, self.command.value)


class ServerControlView(discord.ui.View):
    def __init__(self, server_id: str, timeout: float = None):
        super().__init__(timeout=timeout)
        self.server_id = server_id

    async def _ptero_action(self, interaction: discord.Interaction, signal: str, title: str, color: int):
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        record = _find_server(guild_data, self.server_id)
        if not record:
            return await interaction.response.send_message("Error: Server not found.", ephemeral=True)

        ptero_id = record.get("pterodactyl_id")
        channel = interaction.guild.get_channel(int(record.get("channel_id", 0)))
        past_tense = {"start": "started", "stop": "stopped", "restart": "restarted", "kill": "killed"}.get(signal, f"{signal}ed")
        status_text = f"server {past_tense}"

        if ptero_id:
            try:
                user_id = record.get("assigned_to") if record.get("assigned_to") else None
                await power_action(ptero_id, user_id=user_id, guild_id=guild_id)
            except Exception as e:
                status_text = f"Pterodactyl error: {e}"
        else:
            status_text = f"server {past_tense} (no Pterodactyl link set)"

        if channel:
            await _refresh_pool_panel_embed(channel, record, guild_id)
            embed = discord.Embed(title=f"Server {title}", color=color, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Server", value=record["name"], inline=True)
            embed.add_field(name="IP", value=f"`{record['ip']}`", inline=True)
            embed.add_field(name="Action by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Status", value=status_text, inline=True)
            await channel.send(embed=embed)

        await interaction.response.send_message(f"Server `{record['name']}` — {status_text}.", ephemeral=True)
        log_audit(guild_id, f"server_{signal}", str(interaction.user), record["name"])

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green, custom_id="nexora:server_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._ptero_action(interaction, "start", "Started", SUCCESS)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, custom_id="nexora:server_stop")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._ptero_action(interaction, "stop", "Stopped", DANGER)

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.blurple, custom_id="nexora:server_restart")
    async def restart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._ptero_action(interaction, "restart", "Restarted", WARNING)

    @discord.ui.button(label="Run Command", style=discord.ButtonStyle.gray, custom_id="nexora:server_run")
    async def run_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RunCommandModal()
        modal.server_id = self.server_id
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Link", style=discord.ButtonStyle.gray, custom_id="nexora:server_edit")
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Only admins can edit the server link.", ephemeral=True)
        modal = EditPterodactylLinkModal(self.server_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Upload File", style=discord.ButtonStyle.gray, custom_id="nexora:server_upload")
    async def upload_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        record = _find_server(guild_data, self.server_id)
        if not record:
            return await interaction.response.send_message("Error: Server not found.", ephemeral=True)
        channel = interaction.guild.get_channel(int(record.get("channel_id", 0)))
        if channel:
            await channel.send(
                f"{interaction.user.mention} requested to upload a file to server `{record['name']}`. "
                f"Please attach the file directly in this channel."
            )
        await interaction.response.send_message("Upload request posted.", ephemeral=True)

    @discord.ui.button(label="Close Panel", style=discord.ButtonStyle.red, custom_id="nexora:server_close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        record = _find_server(guild_data, self.server_id)
        if not record:
            return await interaction.response.send_message("Error: Server not found.", ephemeral=True)

        if not interaction.user.guild_permissions.administrator and record.get("assigned_to") != interaction.user.id:
            return await interaction.response.send_message("Only admins or the assigned user can close this panel.", ephemeral=True)

        channel = interaction.guild.get_channel(int(record.get("channel_id", 0)))
        if channel:
            await channel.send(f"Panel closed by {interaction.user.mention}. This channel will be deleted.")
            await channel.delete(reason="Nexora Cloud server panel closed")

        record["status"] = "available"
        record["assigned_to"] = None
        record["assigned_at"] = None
        record["channel_id"] = None
        _save_guild_data(guild_id, guild_data)
        await interaction.response.send_message("Server panel closed and returned to the pool.", ephemeral=True)
        log_audit(guild_id, "server_panel_closed", str(interaction.user), record["name"])


class EditPterodactylLinkModal(discord.ui.Modal, title="Edit Pterodactyl Link"):
    pterodactyl_id = discord.ui.TextInput(label="Pterodactyl Identifier", required=True, placeholder="abc123def")

    def __init__(self, server_id: str):
        super().__init__()
        self.server_id = server_id

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        record = _find_server(guild_data, self.server_id)
        if not record:
            return await interaction.response.send_message("Server not found.", ephemeral=True)
        record["pterodactyl_id"] = self.pterodactyl_id.value.strip()
        _save_guild_data(guild_id, guild_data)
        channel = interaction.guild.get_channel(int(record.get("channel_id", 0)))
        if channel:
            await _refresh_pool_panel_embed(channel, record, guild_id)
        await interaction.response.send_message(f"Pterodactyl link updated for `{record['name']}`.", ephemeral=True)
        log_audit(guild_id, "pterodactyl_link_updated", str(interaction.user), record["name"], self.pterodactyl_id.value)


# ── Cog ───────────────────────────────────────────────────────────────────────


class ServerPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending_upload_dirs: dict[int, str] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.attachments:
            return
        channel_id = message.channel.id
        if channel_id not in self._pending_upload_dirs:
            return

        guild_data = _get_guild_data(message.guild.id)
        panel = _find_user_panel(guild_data, channel_id)
        if not panel:
            self._pending_upload_dirs.pop(channel_id, None)
            return
        if message.author.id != panel.get("user_id") and not message.author.guild_permissions.administrator:
            return

        directory = self._pending_upload_dirs.get(channel_id, "/")
        uploaded = []
        failed = []
        status_msg = await message.channel.send(f"Uploading {len(message.attachments)} file(s) to `{directory}`...")

        for attachment in message.attachments:
            try:
                file_bytes = await attachment.read()
                upload_url = await request_upload_url(panel["identifier"], directory, user_id=panel["user_id"])
                await upload_to_signed_url(upload_url, attachment.filename, file_bytes)
                uploaded.append(attachment.filename)
            except Exception as e:
                failed.append(f"{attachment.filename} (`{e}`)")

        self._pending_upload_dirs.pop(channel_id, None)
        embed = discord.Embed(title="File Upload Report", color=SUCCESS if not failed else WARNING, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Directory", value=f"`{directory}`", inline=False)
        if uploaded:
            embed.add_field(name="Uploaded", value="\n".join(f"✅ `{f}`" for f in uploaded) or "None", inline=False)
        if failed:
            embed.add_field(name="Failed", value="\n".join(f"❌ {f}`" for f in failed) or "None", inline=False)
        await status_msg.edit(content=None, embed=embed)
        log_audit(message.guild.id, "user_server_file_upload", str(message.author), panel.get("name"), f"dir:{directory} files:{len(uploaded)}")

    def _admin_roles(self, guild: discord.Guild) -> list:
        candidates = ["Admin", "General Manager", "DevOps Engineer", "Support Lead"]
        return [r for r in guild.roles if r.name in candidates]

    async def _import_pterodactyl_server(self, ctx_or_interaction, name: str, ip: str, pterodactyl_id: str, password: str = "Set manually"):
        guild = ctx_or_interaction.guild
        guild_id = guild.id
        guild_data = _get_guild_data(guild_id)
        server_id = _generate_server_id(guild_data)
        author = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author

        guild_data["pool"].append({
            "id": server_id,
            "name": name,
            "ip": ip,
            "password": password,
            "pterodactyl_id": pterodactyl_id.strip(),
            "status": "available",
            "assigned_to": None,
            "assigned_at": None,
            "channel_id": None,
            "added_by": author.display_name,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "imported_from": "pterodactyl",
        })
        _save_guild_data(guild_id, guild_data)
        log_audit(guild_id, "server_imported_from_pterodactyl", str(author), name, f"ID:{server_id} Ptero:{pterodactyl_id}")
        await self._send(ctx_or_interaction, f"Imported Pterodactyl server into pool: `{server_id}` — **{name}** | Ptero: `{pterodactyl_id}`", ephemeral=True)

    async def _connect_pool_server(self, ctx_or_interaction, user: discord.Member, server_id: str):
        guild = ctx_or_interaction.guild
        guild_id = guild.id
        guild_data = _get_guild_data(guild_id)
        record = _find_server(guild_data, server_id)
        if not record:
            return await self._send(ctx_or_interaction, "Error: Server not found.", ephemeral=True)
        if record.get("status") != "available":
            owner = guild.get_member(int(record.get("assigned_to", 0)))
            return await self._send(ctx_or_interaction, f"Server is already assigned to {owner.mention if owner else 'someone else'}.", ephemeral=True)

        author = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author

        record["status"] = "assigned"
        record["assigned_to"] = user.id
        record["assigned_at"] = datetime.now(timezone.utc).isoformat()
        _save_guild_data(guild_id, guild_data)

        channel = await _create_pool_panel_channel(guild, record["name"], user, self._admin_roles(guild))
        record["channel_id"] = channel.id
        _save_guild_data(guild_id, guild_data)

        embed = await _build_pool_panel_embed(record, guild_id)
        view = ServerControlView(server_id, timeout=None)
        await channel.send(content=user.mention, embed=embed, view=view)

        log_audit(guild_id, "server_connected", str(author), record["name"], f"user:{user.id}")
        await self._send(ctx_or_interaction, f"Server `{record['name']}` connected for {user.mention}. Panel: {channel.mention}", ephemeral=True)

    async def _create_user_panel(self, ctx_or_interaction, user: discord.Member, identifier: str):
        guild = ctx_or_interaction.guild
        guild_id = guild.id
        guild_data = _get_guild_data(guild_id)

        existing = _find_user_panel_by_identifier(guild_data, user.id, identifier)
        if existing:
            channel = guild.get_channel(int(existing["channel_id"]))
            if channel:
                return await self._send(ctx_or_interaction, f"You already have a panel for this server: {channel.mention}", ephemeral=True)

        try:
            details = await server_details(identifier, user_id=user.id)
        except Exception as e:
            return await self._send(ctx_or_interaction, f"Error fetching server details: `{e}`", ephemeral=True)

        attr = details.get("attributes", {})
        name = attr.get("name", f"Server-{identifier}")

        channel = await _create_private_panel_channel(guild, name, user)
        panel = {
            "user_id": user.id,
            "identifier": identifier,
            "name": name,
            "channel_id": channel.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _get_user_panels(guild_data)[str(channel.id)] = panel
        _save_guild_data(guild_id, guild_data)

        # Decorative welcome banner
        welcome = discord.Embed(
            title=f"🎮 {name}",
            description=(
                f"Welcome to your private server control panel, {user.mention}.\n\n"
                "Use the buttons below to control your server or upload files.\n"
                "Click **Upload File** to choose a folder, then attach your file(s) in this channel."
            ),
            color=ACCENT,
            timestamp=datetime.now(timezone.utc)
        )
        welcome.set_thumbnail(url=user.display_avatar.url)
        welcome.set_footer(text="Nexora Cloud • Pterodactyl Server Panel")
        await channel.send(embed=welcome)

        embed = await _build_user_panel_embed(panel, guild_id)
        view = UserServerControlView(channel.id, timeout=None)
        await channel.send(embed=embed, view=view)

        log_audit(guild_id, "user_server_panel_created", str(user), name, f"identifier:{identifier}")
        await self._send(ctx_or_interaction, f"Private panel created for `{name}`: {channel.mention}", ephemeral=True)

    async def _run_user_command(self, interaction: discord.Interaction, channel_id: int, command: str):
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        panel = _find_user_panel(guild_data, channel_id)
        if not panel:
            return await interaction.followup.send("Error: Panel not found.", ephemeral=True)
        if interaction.user.id != panel.get("user_id") and not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("You cannot use this panel.", ephemeral=True)

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.followup.send("Error: Panel channel not found.", ephemeral=True)

        try:
            await send_command(panel["identifier"], command, user_id=panel["user_id"])
            status = "command sent to Pterodactyl server"
        except Exception as e:
            status = f"Pterodactyl error: {e}"

        embed = discord.Embed(title="Server Command", color=CYAN, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Command", value=f"`{command}`", inline=False)
        embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Server", value=panel.get("name", "Unknown"), inline=True)
        await channel.send(embed=embed)
        await interaction.followup.send(f"Command handled. {status}.", ephemeral=True)
        log_audit(guild_id, "user_server_command", str(interaction.user), panel.get("name"), command)

    async def _run_command_for_panel(self, interaction: discord.Interaction, server_id: str, command: str):
        guild_id = interaction.guild.id
        guild_data = _get_guild_data(guild_id)
        record = _find_server(guild_data, server_id)
        if not record:
            return await interaction.followup.send("Error: Server not found.", ephemeral=True)
        ptero_id = record.get("pterodactyl_id")
        channel = interaction.guild.get_channel(int(record.get("channel_id", 0)))
        if not channel:
            return await interaction.followup.send("Error: Server channel not found.", ephemeral=True)

        status = "command request recorded"
        if ptero_id:
            try:
                user_id = record.get("assigned_to") if record.get("assigned_to") else None
                await send_command(ptero_id, command, user_id=user_id, guild_id=guild_id)
                status = "command sent to Pterodactyl server"
            except Exception as e:
                status = f"Pterodactyl error: {e}"

        embed = discord.Embed(title="Server Command", color=CYAN, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Command", value=f"`{command}`", inline=False)
        embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="IP", value=f"`{record['ip']}`", inline=True)
        await channel.send(embed=embed)
        await interaction.followup.send(f"Command handled. {status}.", ephemeral=True)
        log_audit(guild_id, "server_command_requested", str(interaction.user), record["name"], command)

    async def _send(self, ctx_or_interaction, text: str, ephemeral: bool = False):
        if isinstance(ctx_or_interaction, discord.Interaction):
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(text, ephemeral=ephemeral)
            else:
                await ctx_or_interaction.response.send_message(text, ephemeral=ephemeral)
        else:
            await ctx_or_interaction.send(text)

    # ── User Pterodactyl setup ──
    @commands.command(name="pterodactyl_setup", help="Link your own Pterodactyl panel. Usage: !pterodactyl_setup <panel_url> <api_key>")
    async def pterodactyl_setup(self, ctx: commands.Context, panel_url: str, api_key: str):
        await ctx.send("Processing `!pterodactyl_setup`...")
        try:
            if not panel_url or not api_key:
                return await ctx.send("Error: Missing panel URL or API key.")
            cfg = get_user_config(ctx.author.id)
            cfg["panel_url"] = panel_url.rstrip("/")
            cfg["api_key"] = api_key
            set_user_config(ctx.author.id, cfg)
            try:
                account = await test_connection(user_id=ctx.author.id)
                await ctx.send(f"Pterodactyl connected. Account: `{account.get('attributes', {}).get('username', 'unknown')}`")
            except Exception as e:
                await ctx.send(f"Config saved, but connection test failed: `{e}`")
        except Exception as e:
            await ctx.send(f"Error in `!pterodactyl_setup`: `{e}`")

    @commands.command(name="pterodactyl_servers", help="List your own Pterodactyl servers.")
    async def pterodactyl_servers(self, ctx: commands.Context):
        await ctx.send("Processing `!pterodactyl_servers`...")
        try:
            cfg = get_user_config(ctx.author.id)
            if not cfg.get("panel_url") or not cfg.get("api_key"):
                return await ctx.send("Error: Pterodactyl not configured. Use `!pterodactyl_setup <url> <api_key>` first.")
            servers = await list_servers(user_id=ctx.author.id)
            if not servers:
                return await ctx.send("No servers found in your Pterodactyl account.")
            embed = discord.Embed(title="Your Pterodactyl Servers", color=ACCENT, timestamp=datetime.now(timezone.utc))
            for srv in servers[:25]:
                attr = srv.get("attributes", {})
                name = attr.get("name", "Unnamed")
                identifier = attr.get("identifier", "unknown")
                status = attr.get("status", "unknown")
                embed.add_field(name=name, value=f"ID: `{identifier}` | Status: {status}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error in `!pterodactyl_servers`: `{e}`")

    @commands.command(name="pterodactyl_test", help="Test your Pterodactyl API connection.")
    async def pterodactyl_test(self, ctx: commands.Context):
        await ctx.send("Processing `!pterodactyl_test`...")
        try:
            cfg = get_user_config(ctx.author.id)
            if not cfg.get("panel_url") or not cfg.get("api_key"):
                return await ctx.send("Error: Pterodactyl not configured. Use `!pterodactyl_setup <url> <api_key>` first.")
            account = await test_connection(user_id=ctx.author.id)
            await ctx.send(f"Connection OK. User: `{account.get('attributes', {}).get('username', 'unknown')}`")
        except Exception as e:
            await ctx.send(f"Connection failed: `{e}`")

    # ── User server commands ──
    @commands.command(name="server", help="List your Pterodactyl servers and create a private control panel. Usage: !server")
    async def user_server(self, ctx: commands.Context):
        await ctx.send("Processing `!server`...")
        try:
            cfg = get_user_config(ctx.author.id)
            if not cfg.get("panel_url") or not cfg.get("api_key"):
                return await ctx.send("Error: Pterodactyl not configured. Use `!pterodactyl_setup <url> <api_key>` first.")
            servers = await list_servers(user_id=ctx.author.id)
            if not servers:
                return await ctx.send("No servers found in your Pterodactyl account.")
            view = UserServerView(servers, ctx.author, ctx.channel)
            await ctx.send(f"{ctx.author.mention}, select a server to create your private control panel:", view=view)
        except Exception as e:
            await ctx.send(f"Error in `!server`: `{e}`")

    @commands.command(name="server_list", help="List your private server panels.")
    async def server_list(self, ctx: commands.Context):
        await ctx.send("Processing `!server_list`...")
        try:
            guild_data = _get_guild_data(ctx.guild.id)
            panels = _get_user_panels(guild_data)
            mine = [p for p in panels.values() if p.get("user_id") == ctx.author.id]
            is_admin = ctx.author.guild_permissions.administrator
            if is_admin:
                mine = list(panels.values())
            if not mine:
                return await ctx.send("No private server panels found. Use `!server` to create one.")
            embed = discord.Embed(title="Your Server Panels", color=ACCENT, timestamp=datetime.now(timezone.utc))
            for panel in mine:
                channel = ctx.guild.get_channel(int(panel.get("channel_id", 0)))
                embed.add_field(name=panel.get("name", "Unknown"), value=f"ID: `{panel.get('identifier')}` | Channel: {channel.mention if channel else 'N/A'}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error in `!server_list`: `{e}`")

    @commands.command(name="server_info", help="Show details for one of your private server panels. Usage: !server_info <channel_id>")
    async def server_info(self, ctx: commands.Context, channel_id: int):
        await ctx.send("Processing `!server_info`...")
        try:
            if not channel_id:
                return await ctx.send("Error: Usage: `!server_info <channel_id>`")
            guild_data = _get_guild_data(ctx.guild.id)
            panel = _find_user_panel(guild_data, channel_id)
            if not panel:
                return await ctx.send("Error: Panel not found.")
            if ctx.author.id != panel.get("user_id") and not ctx.author.guild_permissions.administrator:
                return await ctx.send("You can only view your own panels.")
            embed = await _build_user_panel_embed(panel, ctx.guild.id)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error in `!server_info`: `{e}`")

    @commands.command(name="server_power", help="Send a power signal to a private panel server. Usage: !server_power <channel_id> <start|stop|restart|kill>")
    async def server_power(self, ctx: commands.Context, channel_id: int, signal: str):
        await ctx.send("Processing `!server_power`...")
        try:
            if not channel_id or not signal:
                return await ctx.send("Error: Usage: `!server_power <channel_id> <start|stop|restart|kill>`")
            guild_data = _get_guild_data(ctx.guild.id)
            panel = _find_user_panel(guild_data, channel_id)
            if not panel:
                return await ctx.send("Error: Panel not found.")
            if ctx.author.id != panel.get("user_id") and not ctx.author.guild_permissions.administrator:
                return await ctx.send("You can only control your own panels.")
            await power_action(panel["identifier"], signal, user_id=panel["user_id"])
            await ctx.send(f"Sent `{signal}` to `{panel.get('name')}`.")
            log_audit(ctx.guild.id, f"server_{signal}", str(ctx.author), panel.get("name"), f"channel:{channel_id}")
        except Exception as e:
            await ctx.send(f"Error in `!server_power`: `{e}`")

    @commands.command(name="server_run", help="Send a command to a private panel server. Usage: !server_run <channel_id> <command>")
    async def server_run(self, ctx: commands.Context, channel_id: int, *, command: str):
        await ctx.send("Processing `!server_run`...")
        try:
            if not channel_id or not command:
                return await ctx.send("Error: Usage: `!server_run <channel_id> <command>`")
            guild_data = _get_guild_data(ctx.guild.id)
            panel = _find_user_panel(guild_data, channel_id)
            if not panel:
                return await ctx.send("Error: Panel not found.")
            if ctx.author.id != panel.get("user_id") and not ctx.author.guild_permissions.administrator:
                return await ctx.send("You can only control your own panels.")
            await send_command(panel["identifier"], command, user_id=panel["user_id"])
            await ctx.send(f"Command sent to `{panel.get('name')}`.")
            log_audit(ctx.guild.id, "server_command", str(ctx.author), panel.get("name"), command)
        except Exception as e:
            await ctx.send(f"Error in `!server_run`: `{e}`")

    # ── Admin pool management (legacy) ──
    @commands.command(name="server_add", help="Add a server to the pool. Usage: !server_add <name> <ip> <password> [pterodactyl_id]")
    @commands.has_permissions(administrator=True)
    async def server_add(self, ctx: commands.Context, name: str, ip: str, password: str, pterodactyl_id: str = ""):
        await ctx.send("Processing `!server_add`...")
        try:
            if not name or not ip or not password:
                return await ctx.send("Error: Missing data. Usage: `!server_add <name> <ip> <password> [pterodactyl_id]`")
            guild_data = _get_guild_data(ctx.guild.id)
            server_id = _generate_server_id(guild_data)
            guild_data["pool"].append({
                "id": server_id,
                "name": name,
                "ip": ip,
                "password": password,
                "pterodactyl_id": pterodactyl_id.strip(),
                "status": "available",
                "assigned_to": None,
                "assigned_at": None,
                "channel_id": None,
                "added_by": ctx.author.display_name,
                "added_at": datetime.now(timezone.utc).isoformat(),
            })
            _save_guild_data(ctx.guild.id, guild_data)
            await ctx.send(f"Server added to pool: `{server_id}` — **{name}** | IP: `{ip}`")
            log_audit(ctx.guild.id, "server_added_to_pool", str(ctx.author), name, f"ID:{server_id}")
        except Exception as e:
            await ctx.send(f"Error in `!server_add`: `{e}`")

    @commands.command(name="server_import", help="Import an existing Pterodactyl server into the pool via dropdown.")
    @commands.has_permissions(administrator=True)
    async def server_import(self, ctx: commands.Context):
        await ctx.send("Processing `!server_import`...")
        try:
            cfg = get_user_config(ctx.author.id)
            if not cfg.get("panel_url") or not cfg.get("api_key"):
                return await ctx.send("Error: Pterodactyl not configured for you. Use `!pterodactyl_setup <url> <api_key>` first.")
            ptero_servers = await list_servers(user_id=ctx.author.id)
            if not ptero_servers:
                return await ctx.send("No servers found in your Pterodactyl account.")
            view = PterodactylImportView(ptero_servers)
            await ctx.send("Select an existing Pterodactyl server to import into the pool:", view=view)
        except Exception as e:
            await ctx.send(f"Error in `!server_import`: `{e}`")

    @commands.command(name="server_import_all", help="Import ALL existing Pterodactyl servers into the pool at once.")
    @commands.has_permissions(administrator=True)
    async def server_import_all(self, ctx: commands.Context):
        await ctx.send("Processing `!server_import_all`...")
        try:
            cfg = get_user_config(ctx.author.id)
            if not cfg.get("panel_url") or not cfg.get("api_key"):
                return await ctx.send("Error: Pterodactyl not configured for you. Use `!pterodactyl_setup <url> <api_key>` first.")
            ptero_servers = await list_servers(user_id=ctx.author.id)
            if not ptero_servers:
                return await ctx.send("No servers found in your Pterodactyl account.")
            imported = []
            for srv in ptero_servers:
                attr = srv.get("attributes", {})
                name = attr.get("name", f"Server-{attr.get('identifier', 'unknown')}")
                identifier = attr.get("identifier", "")
                ip = attr.get("sftp_details", {}).get("ip", "Set manually") or "Set manually"
                await self._import_pterodactyl_server(ctx, name, ip, identifier, password="Set manually")
                imported.append(name)
            await ctx.send(f"Imported {len(imported)} Pterodactyl servers into the pool: {', '.join(imported)}")
        except Exception as e:
            await ctx.send(f"Error in `!server_import_all`: `{e}`")

    @commands.command(name="server_remove", help="Remove a server from the pool. Usage: !server_remove <server_id>")
    @commands.has_permissions(administrator=True)
    async def server_remove(self, ctx: commands.Context, server_id: str):
        await ctx.send("Processing `!server_remove`...")
        try:
            if not server_id:
                return await ctx.send("Error: Please provide a server ID. Usage: `!server_remove <server_id>`")
            guild_data = _get_guild_data(ctx.guild.id)
            record = _find_server(guild_data, server_id)
            if not record:
                return await ctx.send("Error: Server not found.")
            if record.get("channel_id"):
                channel = ctx.guild.get_channel(int(record["channel_id"]))
                if channel:
                    await channel.delete(reason="Server removed from pool")
            guild_data["pool"] = [s for s in guild_data["pool"] if s.get("id") != server_id]
            _save_guild_data(ctx.guild.id, guild_data)
            await ctx.send(f"Server `{server_id}` removed from pool.")
            log_audit(ctx.guild.id, "server_removed_from_pool", str(ctx.author), record["name"])
        except Exception as e:
            await ctx.send(f"Error in `!server_remove`: `{e}`")

    @commands.command(name="server_pool", help="List all servers in the pool.")
    @commands.has_permissions(administrator=True)
    async def server_pool(self, ctx: commands.Context):
        await ctx.send("Processing `!server_pool`...")
        try:
            guild_data = _get_guild_data(ctx.guild.id)
            pool = guild_data.get("pool", [])
            if not pool:
                return await ctx.send("No servers in the pool. Add one with `!server_add`.")
            embed = discord.Embed(title="Server Pool", color=ACCENT, timestamp=datetime.now(timezone.utc))
            for srv in pool:
                status = srv.get("status", "available")
                assigned = ctx.guild.get_member(int(srv.get("assigned_to", 0)))
                value = f"IP: `{srv['ip']}` | Ptero: `{srv.get('pterodactyl_id') or 'none'}` | Status: `{status}`"
                if assigned:
                    value += f" | Assigned: {assigned.mention}"
                embed.add_field(name=f"{srv['name']} (`{srv['id']}`)", value=value, inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error in `!server_pool`: `{e}`")

    @commands.command(name="server_assign", help="Manually assign a server to a user. Usage: !server_assign <server_id> @user")
    @commands.has_permissions(administrator=True)
    async def server_assign(self, ctx: commands.Context, server_id: str, user: discord.Member):
        await ctx.send("Processing `!server_assign`...")
        try:
            if not server_id or not user:
                return await ctx.send("Error: Usage: `!server_assign <server_id> @user`")
            await self._connect_pool_server(ctx, user, server_id)
        except Exception as e:
            await ctx.send(f"Error in `!server_assign`: `{e}`")

    @commands.command(name="server_unassign", help="Return an assigned server to the pool. Usage: !server_unassign <server_id>")
    @commands.has_permissions(administrator=True)
    async def server_unassign(self, ctx: commands.Context, server_id: str):
        await ctx.send("Processing `!server_unassign`...")
        try:
            if not server_id:
                return await ctx.send("Error: Usage: `!server_unassign <server_id>`")
            guild_data = _get_guild_data(ctx.guild.id)
            record = _find_server(guild_data, server_id)
            if not record:
                return await ctx.send("Error: Server not found.")
            if record.get("channel_id"):
                channel = ctx.guild.get_channel(int(record["channel_id"]))
                if channel:
                    await channel.delete(reason="Server unassigned from user")
            record["status"] = "available"
            record["assigned_to"] = None
            record["assigned_at"] = None
            record["channel_id"] = None
            _save_guild_data(ctx.guild.id, guild_data)
            await ctx.send(f"Server `{server_id}` is now available in the pool.")
            log_audit(ctx.guild.id, "server_unassigned", str(ctx.author), record["name"])
        except Exception as e:
            await ctx.send(f"Error in `!server_unassign`: `{e}`")

    @commands.command(name="server_edit", help="Edit a pool server's IP and password. Usage: !server_edit <server_id> <ip> <password>")
    @commands.has_permissions(administrator=True)
    async def server_edit(self, ctx: commands.Context, server_id: str, ip: str, password: str):
        await ctx.send("Processing `!server_edit`...")
        try:
            if not server_id or not ip or not password:
                return await ctx.send("Error: Usage: `!server_edit <server_id> <ip> <password>`")
            guild_data = _get_guild_data(ctx.guild.id)
            record = _find_server(guild_data, server_id)
            if not record:
                return await ctx.send("Error: Server not found.")
            record["ip"] = ip
            record["password"] = password
            _save_guild_data(ctx.guild.id, guild_data)
            channel = ctx.guild.get_channel(int(record.get("channel_id", 0)))
            if channel:
                await _refresh_pool_panel_embed(channel, record, ctx.guild.id)
            await ctx.send(f"Server `{server_id}` updated. IP: `{ip}` | Password updated.")
            log_audit(ctx.guild.id, "server_edited", str(ctx.author), record["name"])
        except Exception as e:
            await ctx.send(f"Error in `!server_edit`: `{e}`")

    @commands.command(name="pterodactyl_link", help="Link a pool server to a Pterodactyl server. Usage: !pterodactyl_link <server_id> <pterodactyl_identifier>")
    @commands.has_permissions(administrator=True)
    async def pterodactyl_link(self, ctx: commands.Context, server_id: str, pterodactyl_id: str):
        await ctx.send("Processing `!pterodactyl_link`...")
        try:
            if not server_id or not pterodactyl_id:
                return await ctx.send("Error: Usage: `!pterodactyl_link <server_id> <pterodactyl_identifier>`")
            guild_data = _get_guild_data(ctx.guild.id)
            record = _find_server(guild_data, server_id)
            if not record:
                return await ctx.send("Error: Server not found.")
            record["pterodactyl_id"] = pterodactyl_id
            _save_guild_data(ctx.guild.id, guild_data)
            channel = ctx.guild.get_channel(int(record.get("channel_id", 0)))
            if channel:
                await _refresh_pool_panel_embed(channel, record, ctx.guild.id)
            await ctx.send(f"Server `{record['name']}` linked to Pterodactyl identifier `{pterodactyl_id}`.")
        except Exception as e:
            await ctx.send(f"Error in `!pterodactyl_link`: `{e}`")

    @commands.command(name="server_sync", help="Refresh all assigned pool panel statuses from Pterodactyl.")
    @commands.has_permissions(administrator=True)
    async def server_sync(self, ctx: commands.Context):
        await ctx.send("Processing `!server_sync`...")
        try:
            guild_data = _get_guild_data(ctx.guild.id)
            updated = 0
            for srv in guild_data.get("pool", []):
                if srv.get("status") != "assigned" or not srv.get("channel_id"):
                    continue
                channel = ctx.guild.get_channel(int(srv["channel_id"]))
                if not channel:
                    continue
                try:
                    await _refresh_pool_panel_embed(channel, srv, ctx.guild.id)
                    updated += 1
                except Exception:
                    continue
            await ctx.send(f"Synced {updated} assigned panels.")
            log_audit(ctx.guild.id, "server_sync", str(ctx.author), details=f"{updated} panels")
        except Exception as e:
            await ctx.send(f"Error in `!server_sync`: `{e}`")

    @commands.command(name="server_debug", help="Debug the ServerPanel cog and check data files.")
    async def server_debug(self, ctx: commands.Context):
        await ctx.send("Processing `!server_debug`...")
        try:
            cog = ctx.bot.get_cog("ServerPanel")
            if not cog:
                return await ctx.send("Error: ServerPanel cog is not loaded.")
            guild_data = _get_guild_data(ctx.guild.id)
            pool = guild_data.get("pool", [])
            panels = _get_user_panels(guild_data)
            my_panels = [p for p in panels.values() if p.get("user_id") == ctx.author.id]
            cfg = get_user_config(ctx.author.id)
            ptero_cfg = "Configured" if cfg.get("panel_url") and cfg.get("api_key") else "Not configured"
            embed = discord.Embed(title="ServerPanel Debug", color=ACCENT, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Cog loaded", value="Yes", inline=True)
            embed.add_field(name="Pool count", value=str(len(pool)), inline=True)
            embed.add_field(name="Your panels", value=str(len(my_panels)), inline=True)
            embed.add_field(name="Pterodactyl config", value=ptero_cfg, inline=True)
            embed.add_field(name="Data file", value=SERVER_FILE, inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error in `!server_debug`: `{e}`")

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You need Administrator permission for this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Error: Missing required argument `{error.param.name}`. Check `!help {ctx.command.name}`.")
        else:
            await ctx.send(f"Error: `{error}`")


async def _build_pool_panel_embed(record: dict, guild_id: int) -> discord.Embed:
    ptero_id = record.get("pterodactyl_id")
    status_text = "Not linked"
    status_color = 0x808080
    ptero_name = None

    if ptero_id:
        try:
            user_id = record.get("assigned_to") if record.get("assigned_to") else None
            details = await server_details(ptero_id, user_id=user_id, guild_id=guild_id)
            ptero_name = details.get("attributes", {}).get("name", "")
            resources = await server_resources(ptero_id, user_id=user_id, guild_id=guild_id)
            state = resources.get("current_state")
            status_text, status_color = _status_style(state)
        except Exception:
            status_text = "Pterodactyl link failed"
            status_color = DANGER

    embed = discord.Embed(
        title=f"Server Panel — {record['name']}",
        color=status_color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Server ID", value=f"`{record['id']}`", inline=False)
    embed.add_field(name="IP Address", value=f"`{record['ip']}`", inline=True)
    embed.add_field(name="Password", value=f"`{record['password']}`", inline=True)
    embed.add_field(name="Pterodactyl ID", value=f"`{ptero_id}`" if ptero_id else "Not linked", inline=True)
    if ptero_name and ptero_name != record["name"]:
        embed.add_field(name="Pterodactyl Name", value=ptero_name, inline=True)
    embed.add_field(name="Live Status", value=status_text, inline=True)
    embed.add_field(name="Assigned", value=f"<@{record.get('assigned_to')}>" if record.get("assigned_to") else "Unassigned", inline=True)
    embed.set_footer(text="Buttons control the real server if a Pterodactyl ID is linked.")
    return embed


async def _build_user_panel_embed(panel: dict, guild_id: int) -> discord.Embed:
    identifier = panel.get("identifier")
    user_id = panel.get("user_id")
    status_text = "❓ Unknown"
    status_color = 0x808080
    status_emoji = "⚪"
    details_text = ""
    resources_text = ""

    try:
        details = await server_details(identifier, user_id=user_id)
        attr = details.get("attributes", {})
        description = attr.get("description", "No description")
        node = attr.get("node", "Unknown")
        resources = await server_resources(identifier, user_id=user_id)
        state = resources.get("current_state")
        status_text, status_color = _status_style(state)
        status_emoji = {"Online": "🟢", "Starting": "🟡", "Stopping": "🟡", "Offline": "🔴"}.get(status_text, "⚪")
        status_text = f"{status_emoji} {status_text}"
        details_text = f"**Description:** {description}\n**Node:** `{node}`"
        res_attr = resources.get("attributes", {})
        cpu = res_attr.get("cpu_absolute", 0)
        mem = res_attr.get("memory_bytes", 0) / (1024 ** 2) if res_attr.get("memory_bytes") else 0
        disk = res_attr.get("disk_bytes", 0) / (1024 ** 2) if res_attr.get("disk_bytes") else 0
        resources_text = f"CPU: `{cpu:.1f}%` | RAM: `{mem:.1f} MB` | Disk: `{disk:.1f} MB`"
    except Exception:
        status_text = "🔴 Pterodactyl link failed"
        status_color = DANGER

    embed = discord.Embed(
        title=f"🎛️ Server Control Panel — {panel.get('name', 'Unknown')}",
        description=details_text,
        color=status_color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Identifier", value=f"`{identifier}`", inline=True)
    embed.add_field(name="Live Status", value=status_text, inline=True)
    embed.add_field(name="Owner", value=f"<@{user_id}>" if user_id else "Unknown", inline=True)
    if resources_text:
        embed.add_field(name="Resources", value=resources_text, inline=False)
    embed.set_footer(text="Nexora Cloud • Private Pterodactyl Server Panel • Refresh with Start/Stop/Restart")
    return embed


async def _refresh_pool_panel_embed(channel: discord.TextChannel, record: dict, guild_id: int):
    try:
        async for msg in channel.history(limit=20, oldest_first=True):
            if msg.author == channel.guild.me and msg.embeds and msg.embeds[0].title and msg.embeds[0].title.startswith("Server Panel"):
                view = ServerControlView(record["id"], timeout=None)
                await msg.edit(embed=await _build_pool_panel_embed(record, guild_id), view=view)
                return
    except Exception:
        pass


async def _refresh_user_panel_embed(channel: discord.TextChannel, panel: dict, guild_id: int):
    try:
        async for msg in channel.history(limit=20, oldest_first=True):
            if msg.author == channel.guild.me and msg.embeds and msg.embeds[0].title and "Server Control Panel" in msg.embeds[0].title:
                view = UserServerControlView(channel.id, timeout=None)
                await msg.edit(embed=await _build_user_panel_embed(panel, guild_id), view=view)
                return
    except Exception:
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerPanel(bot))
