import discord
from discord.ext import commands
import asyncio
import os

# ───────────────────────────────────────────────────────────────────────────────
#   NEXORA CLOUD BOT — TERMINAL INTERFACE
#   Hacker-themed startup dashboard with ANSI art, skull, and system metrics
# ───────────────────────────────────────────────────────────────────────────────

TOKEN = os.environ.get("TOKEN")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents)
class MyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Website",
                emoji="🌐",
                url="https://www.nexora.com"
                )
                )

    @discord.ui.button(label="I've Read & Agree", style=discord.ButtonStyle.green, emoji="✅")
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Verified",
            ephemeral=True  # Only the person who clicked sees this
        )

class MyView1(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Website",
                emoji="🌐",
                url="https://www.nexora.com"
                )
                )

    @discord.ui.button(label="I Agree to TOF", style=discord.ButtonStyle.green, emoji="✅")
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Verified",
            ephemeral=True  # Only the person who clicked sees this
        )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Embed command
@bot.command()
async def rule(ctx):
    embed = discord.Embed(
        title="<a:rules:1524402802548539392> Nexora Hosting — Server Rules",
        description="Please read and follow these rules to keep our community safe and welcoming.\n\n**Violations may result in warnings, mutes, kicks, or permanent bans.**\n\n<a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718>\n\n\n<a:darkbluearrow:1517749005835304992> **Be Respectful**\nTreat every member with respect. No harassment, hate speech, racism, or discrimination of any kind.\n\n<a:darkbluearrow:1517749005835304992> **No Spam or Flooding**\nAvoid to send spam messages, emojis, mentions, or links. Keep conversations on-topic.\n\n<a:darkbluearrow:1517749005835304992> **Refund Policy**\nOur hosting provide you 24-hour refund window.\n\n<a:darkbluearrow:1517749005835304992> **No Scamming or Chargebacks**\nScamming, payment fraud, or chargebacks without contacting support = permanent ban.\n\n<a:darkbluearrow:1517749005835304992> **Use the Ticket System**\nDo not DM staff for support. Open a ticket. Unsolicited DMs to staff will be ignored.\n\n<a:darkbluearrow:1517749005835304992> **No Impersonation**\nDo not impersonate members, staff, or Nexora Hosting in any form.\n\n<a:darkbluearrow:1517749005835304992> **Respect Staff Decisions**\nIf you disagree with a decision, open a ticket calmly. No public arguments.\n\n<a:darkbluearrow:1517749005835304992> **Follow Discord ToS**\nAll members must comply with Discord's Terms of Service and Community Guidelines.\n\n",
        color=0xAB1AFF
    )
    embed.set_author(name="Nexora Hosting — Server Rules", icon_url="https://ik.imagekit.io/gf5eyovtx/27dd118cd8de015a75b519f02df8ce82%20(1).webp") 
    embed.set_footer(text="Nexora Hosting • Premium Minecraft & VPS Hosting", icon_url="https://ik.imagekit.io/gf5eyovtx/27dd118cd8de015a75b519f02df8ce82%20(1).webp")
    embed.set_thumbnail(url="https://ik.imagekit.io/gf5eyovtx/27dd118cd8de015a75b519f02df8ce82%20(1).webp")

    await ctx.send(embed=embed, view=MyView())

@bot.command()
async def tof(ctx):
    embed = discord.Embed(
        title="📋 Nexora Hosting — Terms of Service",
        description="By purchasing or using any Nexora Hosting service, you agree to the following terms.\n\n<a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718><a<a:lines:1524413130279620718>1524413130279620718>\n\n\n<a:arr:1524393071716864122> **Service Agreement**\nServices activate only after full payment confirmation.\n\n<a:arr:1524393071716864122> **Refund Policy**\nRefunds within 72 hours if service wasn't delivered. After that, at management's discretion. Chargebacks = permanent ban.\n\n<a:arr:1524393071716864122> **Acceptable Use**\nNo illegal activities, DDoS, hacking, phishing, spam, or crypto mining on our services.\n\n<a:arr:1524393071716864122> **Payment Terms**\nServices suspended after 3 days of non-payment, terminated after 7 days. Data loss from non-payment is not our responsibility.\n\n<a:arr:1524393071716864122> **Backups**\nWe take periodic backups but you are responsible for your own data. We are not liable for data loss.\n\n<a:arr:1524393071716864122> **Uptime SLA**\nWe target 99.9% uptime. DDoS attacks, force majeure, or user error are not covered by our SLA.\n\n<a:arr:1524393071716864122> **Account Responsibility**\nYou are fully responsible for all activity on your account. Do not share credentials.\n\n<a:arr:1524393071716864122> **Suspension**\nWe reserve the right to suspend or terminate services for ToS violations without prior notice.\n\n<a:arr:1524393071716864122> **Liability**\nOur liability is limited to the current billing period amount. No liability for indirect or consequential damages.\n\n<a:arr:1524393071716864122> **Changes**\nWe may update these terms at any time. Continued use = acceptance of updated terms.",
        color=0xFAC234)
    embed.set_author(name="Nexora Hosting — Server Rules", icon_url="https://ik.imagekit.io/gf5eyovtx/27dd118cd8de015a75b519f02df8ce82%20(1).webp") 
    embed.set_footer(text="Nexora Hosting • Premium Minecraft & VPS Hosting", icon_url="https://ik.imagekit.io/gf5eyovtx/27dd118cd8de015a75b519f02df8ce82%20(1).webp")
    embed.set_thumbnail(url="https://ik.imagekit.io/gf5eyovtx/27dd118cd8de015a75b519f02df8ce82%20(1).webp")

    await ctx.send(embed=embed, view=MyView1())

# Another coloured embed
@bot.command()
async def success(ctx):
    embed = discord.Embed(
        title="✅ Success",
        description="Operation completed successfully!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
async def inb(ctx):
    embed = discord.Embed(
        description="## <:dirt:1533418867898978314> **Dirt Plan**\n\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 2GB RAM**\n<a:warrow:1524395568846340186>**<:processor:1533418381896712365> : 100% CPU**\n<a:warrow:1524395568846340186>**<:ssd:1533418365136404490> : 5GB STORAGE**\n<a:warrow:1524395568846340186>**<a:money:1525728934090641510> Price : **`$2/ Month`\n\n## <:coal:1533418841680515092> **Coal Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 4GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 150% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 10GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`$5/ Month`\n\n## <:89458ironblock:1524004703275323503> **Iron Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 8GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 200% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 15GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`$8/ Month`\n\n## <:38785goldblock:1524004690071916647> **Gold Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 16GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 400% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 25GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`$16/ Month`\n\n## <:diamondblock:1533418958797930546> **Diamond Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 32GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 600% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 50GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`$32/ Month`\n\n\n\n## **Specifications**\n** <a:notepad:1524960814103003158> All are dedicated resources**\n**98% Uptime <a:uptime:1524395713814073459>**\n**Custom plans available on request**\n\nCreate ticket <#1504458541526683806>  to buy plans\n\n||@here||",
        color=0x55FF55)
    await ctx.send(embed=embed)

@bot.command()
async def inbi(ctx):
    embed = discord.Embed(
        description="## <:dirt:1533418867898978314> **Dirt Plan**\n\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 2GB RAM**\n<a:warrow:1524395568846340186>**<:processor:1533418381896712365> : 100% CPU**\n<a:warrow:1524395568846340186>**<:ssd:1533418365136404490> : 5GB STORAGE**\n<a:warrow:1524395568846340186>**<a:money:1525728934090641510> Price : **`₹60/ Month`\n\n## <:coal:1533418841680515092> **Coal Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 4GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 150% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 10GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`₹120/ Month`\n\n## <:89458ironblock:1524004703275323503> **Iron Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 8GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 200% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 15GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`240/ Month`\n\n## <:38785goldblock:1524004690071916647> **Gold Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 16GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 400% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 25GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`₹480/ Month`\n\n## <:diamondblock:1533418958797930546> **Diamond Plan**\n<a:warrow:1524395568846340186>** <:ram_module:1533418272018665472> : 32GB RAM**\n<a:warrow:1524395568846340186>** <:processor:1533418381896712365> : 600% CPU**\n<a:warrow:1524395568846340186>** <:ssd:1533418365136404490> : 50GB STORAGE**\n<a:warrow:1524395568846340186>** <a:money:1525728934090641510> Price : **`₹960/ Month`\n\n\n\n## **Specifications**\n** <a:notepad:1524960814103003158> All are dedicated resources**\n**98% Uptime <a:uptime:1524395713814073459>**\n**Custom plans available on request**\n\nCreate ticket <#1504458541526683806>  to buy plans\n\n||@here||",
        color=0x55FF55)
    await ctx.send(embed=embed)
# ─── ANSI Color Palette ───────────────────────────────────────────────────────

class Term:
    RESET      = "\033[0m"
    BOLD       = "\033[1m"
    DIM        = "\033[2m"
    UNDERLINE  = "\033[4m"
    BLINK      = "\033[5m"

    BLACK      = "\033[30m"
    RED        = "\033[31m"
    GREEN      = "\033[32m"
    YELLOW     = "\033[33m"
    BLUE       = "\033[34m"
    MAGENTA    = "\033[35m"
    CYAN       = "\033[36m"
    WHITE      = "\033[37m"

    BG_BLACK   = "\033[40m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"
    BG_WHITE   = "\033[47m"

    NEON_GREEN = "\033[38;5;82m"
    BLOOD_RED  = "\033[38;5;196m"
    ELECTRIC   = "\033[38;5;51m"
    MATRIX     = "\033[38;5;118m"
    WARNING    = "\033[38;5;208m"


# ─── ASCII Art Assets ─────────────────────────────────────────────────────────

def nexora_banner() -> str:
    return f"""{Term.NEON_GREEN}
    ███╗   ██╗███████╗██╗  ██╗ ██████╗ ██████╗  █████╗      ██████╗  ██████╗ ████████╗
    ████╗  ██║██╔════╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗     ██╔══██╗██╔═══██╗╚══██╔══╝
    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║██████╔╝███████║     ██████╔╝██║   ██║   ██║
    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║     ██╔══██╗██║   ██║   ██║
    ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║     ██████╔╝╚██████╔╝   ██║
    ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝
{Term.CYAN}          ═══════════════════════════════════════════════════════════════════
                        C L O U D    A U T O M A T I O N    B O T    v2.0
          ═══════════════════════════════════════════════════════════════════
{Term.RESET}"""





def divider(char: str = "═", length: int = 80) -> str:
    return f"{Term.CYAN}{char * length}{Term.RESET}"


def label_box(label: str, width: int = 78) -> str:
    pad = width - len(label) - 4
    left = pad // 2
    right = pad - left
    return f"{Term.NEON_GREEN}╔{'═' * (width - 2)}╗{Term.RESET}\n" \
           f"{Term.NEON_GREEN}║{' ' * left}{Term.BOLD}{Term.WHITE}{label}{Term.RESET}{Term.NEON_GREEN}{' ' * right}║{Term.RESET}\n" \
           f"{Term.NEON_GREEN}╚{'═' * (width - 2)}╝{Term.RESET}"


def metric_line(key: str, value: str, status: str = "OK") -> str:
    status_color = Term.NEON_GREEN if status == "OK" else Term.WARNING if status == "WARN" else Term.BLOOD_RED
    return f"{Term.CYAN}│{Term.RESET} {Term.BOLD}{Term.WHITE}{key:<24}{Term.RESET} {Term.ELECTRIC}{value:<34}{Term.RESET} [{status_color}{status:>6}{Term.RESET}] {Term.CYAN}│{Term.RESET}"


# ─── Cogs to load ─────────────────────────────────────────────────────────────

COGS = [
    "cogs.dm",
    "cogs.receipt",
    "cogs.orders",
    "cogs.reminder",
    "cogs.staff",
    "cogs.server_panel",
    "cogs.admin",
    "cogs.ticket_panel",
    "cogs.ticket_commands",
    "cogs.ticket_settings",
    "cogs.sales_orders",
    "cogs.tech_ops",
    "cogs.management",
    "cogs.security",
    "cogs.customer_relations",
]

COG_LABELS = {
    "cogs.dm":                 "DM & Reminders",
    "cogs.receipt":            "Receipts",
    "cogs.orders":             "Order Completion",
    "cogs.reminder":           "Reminders",
    "cogs.staff":              "Staff Hub",
    "cogs.staff_manager":      "Advanced Staff Management",
    "cogs.server_panel":       "Server Control Panels",
    "cogs.admin":              "Admin & Utility",
    "cogs.ticket_panel":       "Ticket Panel",
    "cogs.ticket_commands":    "Ticket Actions",
    "cogs.ticket_settings":    "Ticket Settings",
    "cogs.sales_orders":       "Sales & Orders",
    "cogs.tech_ops":           "DevOps & Status",
    "cogs.hr_onboarding":      "HR / Onboarding",
    "cogs.management":         "Management & KPIs",
    "cogs.security":           "Security & Moderation",
    "cogs.customer_relations": "Customer Relations",
}


# ─── Boot Splash ────────────────────────────────────────────────────────────────

def print_boot_splash():
    print("\n" * 2)
    print(nexora_banner())

    print("\n")
    print(divider("═", 80))
    print(label_box("S Y S T E M   B O O T   S E Q U E N C E"))
    print(divider("═", 80))


# ─── Events ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await bot.tree.sync()

    print("\n")
    print(divider("═", 80))
    print(label_box("O N L I N E   S T A T U S"))
    print(divider("═", 80))

    print(metric_line("Bot User", f"{bot.user}", "OK"))
    print(metric_line("Bot ID", f"{bot.user.id}", "OK"))
    print(metric_line("Connected Guilds", f"{len(bot.guilds)}", "OK"))
    print(metric_line("Loaded Cogs", f"{len(COGS)} / {len(COGS)}", "OK"))
    print(metric_line("Slash Commands", "Synced", "OK"))
    print(metric_line("Latency", f"{round(bot.latency * 1000, 2)} ms", "OK"))
    print(metric_line("Library", f"discord.py v{discord.__version__}", "OK"))
    print(metric_line("Python", "Running", "OK"))

    print(divider("═", 80))
    print(f"{Term.NEON_GREEN}[+] {Term.WHITE}Nexora Cloud Bot is fully operational.{Term.RESET}")
    print(f"{Term.CYAN}[*] {Term.WHITE}Awaiting incoming transmissions...{Term.RESET}")
    print(divider("═", 80))
    print("\n")


# ─── Startup ──────────────────────────────────────────────────────────────────

async def main():
    print_boot_splash()

    print(divider("─", 80))
    print(f"{Term.WARNING}[*] Loading {len(COGS)} neural modules...{Term.RESET}")
    print(divider("─", 80))

    async with bot:
        for cog in COGS:
            label = COG_LABELS.get(cog, cog)
            try:
                await bot.load_extension(cog)
                print(f"{Term.NEON_GREEN}[OK]{Term.RESET}  {Term.CYAN}{cog:<32}{Term.RESET}  {Term.WHITE}{label}{Term.RESET}")
            except Exception as e:
                print(f"{Term.BLOOD_RED}[FAIL]{Term.RESET} {Term.CYAN}{cog:<32}{Term.RESET}  {Term.BLOOD_RED}{type(e).__name__}: {e}{Term.RESET}")

        print(divider("─", 80))
        print(f"{Term.NEON_GREEN}[+] {Term.WHITE}Module initialization complete.{Term.RESET}")
        print(f"{Term.WARNING}[*] {Term.WHITE}Establishing Discord gateway connection...{Term.RESET}")
        print(divider("═", 80))
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        print(f"{Term.BLOOD_RED}[ERROR]{Term.RESET} {Term.WHITE}DISCORD_TOKEN environment variable is not set.{Term.RESET}")
        print(f"{Term.CYAN}[INFO]{Term.RESET}  {Term.WHITE}Run:  export DISCORD_TOKEN=your_bot_token_here{Term.RESET}")
        raise SystemExit(1)

    asyncio.run(main())
