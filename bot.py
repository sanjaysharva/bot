import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# Load variables from .env
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN2")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. Add it to your .env file."
    )


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced!")


bot = MyBot()


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")


# =========================
# /clear
# =========================

@bot.tree.command(
    name="clear",
    description="Delete messages from this channel"
)
@app_commands.describe(
    amount="Number of messages to delete"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def clear(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):
    channel = interaction.channel

    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command can only be used in a text channel.",
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    deleted = await channel.purge(limit=amount)

    await interaction.followup.send(
        f"🧹 Deleted **{len(deleted)}** messages.",
        ephemeral=True
    )

# =========================
# /tickets
# =========================

@bot.tree.command(name="tickets", description="Rename a channel using a category count")
@app_commands.describe(
    category="Category used only for counting channels",
    name="New base name",
    channel="Channel to rename"
)
@app_commands.checks.has_permissions(manage_channels=True)
async def tickets(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    name: str,
    channel: discord.abc.GuildChannel
):
    # Count channels inside the selected category
    count = len(category.channels) + 1

    # New channel name
    new_name = f"{name} {count}"

    try:
        await channel.edit(name=new_name)

        await interaction.response.send_message(
            f"✅ Renamed {channel.mention} to **{new_name}**\n"
            f"📁 Counted from category: **{category.name}**",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to rename that channel.",
            ephemeral=True
        )

# =========================
# /customer
# =========================

@bot.tree.command(name="customer", description="Create multiple customer channels")
@app_commands.describe(
    channel="Category where channels will be created",
    name="Base name for the channels",
    no="Number of channels to create"
)
@app_commands.checks.has_permissions(manage_channels=True)
async def customer(
    interaction: discord.Interaction,
    channel: discord.abc.GuildChannel,
    name: str,
    no: app_commands.Range[int, 1, 50]
):
    await interaction.response.defer(ephemeral=True)

    created = []

    # Start after existing channels
    start_count = len(channel.channels) + 1

    for i in range(no):
        channel_name = f"{name}-{start_count + i}"

        new_channel = await channel.create_text_channel(
            name=channel_name
        )

        created.append(new_channel.mention)

    await interaction.followup.send(
        f"✅ Created **{len(created)}** customer channels:\n"
        + "\n".join(created),
        ephemeral=True
    )
# =========================
# /lock
# =========================

@bot.tree.command(
    name="lock",
    description="Lock the current channel"
)
@app_commands.checks.has_permissions(
    manage_channels=True
)
async def lock(interaction: discord.Interaction):

    channel = interaction.channel

    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command can only be used in a text channel.",
            ephemeral=True
        )

    overwrite = channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    await channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        "🔒 This channel has been locked."
    )


# =========================
# /unlock
# =========================

@bot.tree.command(
    name="unlock",
    description="Unlock the current channel"
)
@app_commands.checks.has_permissions(
    manage_channels=True
)
async def unlock(interaction: discord.Interaction):

    channel = interaction.channel

    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message(
            "❌ This command can only be used in a text channel.",
            ephemeral=True
        )

    overwrite = channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = None

    await channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        "🔓 This channel has been unlocked."
    )


# =========================
# Error Handler
# =========================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):
        message = "❌ You don't have permission to use this command."

    else:
        print(f"Command error: {error}")
        message = "❌ Something went wrong."

    if interaction.response.is_done():
        await interaction.followup.send(
            message,
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True
        )


# =========================
# Start Bot
# =========================

bot.run(TOKEN)
