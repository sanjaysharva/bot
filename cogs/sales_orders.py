"""
cogs/sales_orders.py — Nexora Cloud
Sales & order management. Slash: quotes, order status. Prefix: invoices, refunds, discounts, upgrades, cancellations, reports.
"""

import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from ._shared import (
    guild_data, save_guild, log_audit, ACCENT, SUCCESS, WARNING, DANGER,
    PLAN_CHOICES, SPEC_CHOICES,
)


class SalesOrders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _oid(self) -> str:
        return f"ORD-{int(datetime.now(timezone.utc).timestamp()) % 100000}"

    # ── /quote ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="quote", description="Generate a price quote for a customer.")
    @app_commands.describe(customer="Customer name", plan="Plan", spec="Spec", months="Duration", discount="Discount %")
    @app_commands.choices(plan=PLAN_CHOICES, spec=SPEC_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def quote(self, interaction: discord.Interaction, customer: str, plan: app_commands.Choice[str], spec: app_commands.Choice[str], months: int = 1, discount: int = 0):
        base = {"Starter": 5, "Pro": 15, "Business": 40, "Enterprise": 99, "Custom": 0}[plan.value]
        total = base * months
        discount_amt = int(total * (discount / 100))
        final = max(0, total - discount_amt)
        embed = discord.Embed(title="Nexora Cloud Quote", color=SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Customer", value=customer, inline=True)
        embed.add_field(name="Plan", value=plan.value, inline=True)
        embed.add_field(name="Spec", value=spec.value, inline=True)
        embed.add_field(name="Duration", value=f"{months} month(s)", inline=True)
        embed.add_field(name="Subtotal", value=f"${total}", inline=True)
        if discount:
            embed.add_field(name="Discount", value=f"-${discount_amt} ({discount}%)", inline=True)
        embed.add_field(name="Total", value=f"**${final}**", inline=False)
        embed.set_footer(text=f"Prepared by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    # ── !invoice ─────────────────────────────────────────────────────────────────
    @commands.command(name="invoice", help="Create a pending invoice record. Usage: !invoice \"<customer>\" <amount> \"<description>\" [due_days]")
    @commands.has_permissions(manage_messages=True)
    async def invoice(self, ctx: commands.Context, customer: str, amount: float, description: str, due_days: int = 7):
        data = guild_data(ctx.guild.id)
        inv_id = f"INV-{int(datetime.now(timezone.utc).timestamp()) % 100000}"
        due = (datetime.now(timezone.utc) + timedelta(days=due_days)).strftime("%Y-%m-%d")
        data["orders"][inv_id] = {
            "id": inv_id, "customer": customer, "amount": amount, "description": description,
            "due": due, "status": "Pending", "created_by": ctx.author.display_name,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        save_guild(ctx.guild.id, data)
        embed = discord.Embed(title=f"Invoice Created — {inv_id}", color=WARNING, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Customer", value=customer, inline=True)
        embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
        embed.add_field(name="Due", value=due, inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text=f"Created by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ── !refund ──────────────────────────────────────────────────────────────────
    @commands.command(name="refund", help="Process a refund. Usage: !refund <order_id> <amount> [reason]")
    @commands.has_permissions(manage_messages=True)
    async def refund(self, ctx: commands.Context, order_id: str, amount: float, *, reason: str = "Customer request"):
        data = guild_data(ctx.guild.id)
        order = data["orders"].get(order_id)
        if not order:
            return await ctx.send(f"Order `{order_id}` not found.")
        order["status"] = "Refunded"
        data["kpi"]["refunds"] = data["kpi"].get("refunds", 0) + 1
        save_guild(ctx.guild.id, data)
        embed = discord.Embed(title="Refund Processed", color=DANGER, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Order", value=order_id, inline=True)
        embed.add_field(name="Customer", value=order["customer"], inline=True)
        embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)

    # ── !discount ─────────────────────────────────────────────────────────────────
    @commands.command(name="discount", help="Apply a discount to an order. Usage: !discount <order_id> <percent> [reason]")
    @commands.has_permissions(manage_messages=True)
    async def discount(self, ctx: commands.Context, order_id: str, percent: int, *, reason: str = "Promotional"):
        if not (0 <= percent <= 100):
            return await ctx.send("Error: Discount must be 0–100%.")
        data = guild_data(ctx.guild.id)
        order = data["orders"].get(order_id)
        if not order:
            return await ctx.send(f"Order `{order_id}` not found.")
        order["amount"] = round(order["amount"] * (1 - percent / 100), 2)
        order["discount"] = f"{percent}% — {reason}"
        save_guild(ctx.guild.id, data)
        await ctx.send(f"Discount of **{percent}%** applied to `{order_id}`. New amount: **${order['amount']:.2f}**.")

    # ── !upgrade_order ────────────────────────────────────────────────────────────
    @commands.command(name="upgrade_order", help="Upgrade an existing customer's plan. Usage: !upgrade_order <order_id> \"<new_plan>\" \"<new_spec>\"")
    @commands.has_permissions(manage_messages=True)
    async def upgrade_order(self, ctx: commands.Context, order_id: str, new_plan: str, new_spec: str):
        data = guild_data(ctx.guild.id)
        order = data["orders"].get(order_id)
        if not order:
            return await ctx.send(f"Order `{order_id}` not found.")
        order["plan"] = new_plan
        order["spec"] = new_spec
        order["status"] = "Upgraded"
        save_guild(ctx.guild.id, data)
        embed = discord.Embed(title="Order Upgraded", color=SUCCESS, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Order", value=order_id, inline=True)
        embed.add_field(name="New Plan", value=new_plan, inline=True)
        embed.add_field(name="New Spec", value=new_spec, inline=True)
        await ctx.send(embed=embed)

    # ── !cancel_order ──────────────────────────────────────────────────────────────
    @commands.command(name="cancel_order", help="Cancel an order. Usage: !cancel_order <order_id> [reason]")
    @commands.has_permissions(manage_messages=True)
    async def cancel_order(self, ctx: commands.Context, order_id: str, *, reason: str = "Customer request"):
        data = guild_data(ctx.guild.id)
        order = data["orders"].get(order_id)
        if not order:
            return await ctx.send(f"Order `{order_id}` not found.")
        order["status"] = "Cancelled"
        order["cancel_reason"] = reason
        save_guild(ctx.guild.id, data)
        embed = discord.Embed(title="Order Cancelled", color=DANGER, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Order", value=order_id, inline=True)
        embed.add_field(name="Customer", value=order["customer"], inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)

    # ── /order_status ────────────────────────────────────────────────────────────
    @app_commands.command(name="order_status", description="Look up the status of an order.")
    @app_commands.describe(order_id="Order/invoice ID")
    async def order_status(self, interaction: discord.Interaction, order_id: str):
        data = guild_data(interaction.guild.id)
        order = data["orders"].get(order_id)
        if not order:
            return await interaction.response.send_message(f"Order `{order_id}` not found.", ephemeral=True)
        color = SUCCESS if order["status"] == "Completed" else WARNING if order["status"] == "Pending" else DANGER
        embed = discord.Embed(title=f"Order Status — {order_id}", color=color, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Customer", value=order.get("customer", "N/A"), inline=True)
        embed.add_field(name="Plan", value=order.get("plan", "N/A"), inline=True)
        embed.add_field(name="Spec", value=order.get("spec", "N/A"), inline=True)
        embed.add_field(name="Amount", value=f"${order.get('amount', 0):.2f}", inline=True)
        embed.add_field(name="Status", value=order["status"], inline=True)
        embed.add_field(name="Due", value=order.get("due", "N/A"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── !sales_report ────────────────────────────────────────────────────────────
    @commands.command(name="sales_report", help="Show daily/weekly sales summary. Usage: !sales_report [today/week]")
    @commands.has_permissions(manage_messages=True)
    async def sales_report(self, ctx: commands.Context, period: str = "today"):
        data = guild_data(ctx.guild.id)
        orders = list(data.get("orders", {}).values())
        total = sum(o.get("amount", 0) for o in orders if o.get("status") in ("Pending", "Completed", "Upgraded"))
        count = len(orders)
        embed = discord.Embed(title=f"Sales Report — {period.title()}", color=ACCENT, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Total Orders", value=f"{count}", inline=True)
        embed.add_field(name="Total Revenue", value=f"${total:.2f}", inline=True)
        embed.add_field(name="Refunds", value=f"{data['kpi'].get('refunds', 0)}", inline=True)
        embed.set_footer(text="Tracks orders created via !invoice or /complete_order")
        await ctx.send(embed=embed)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Error: You need Manage Messages or higher.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Error: Missing required argument `{error.param.name}`. Check `!help {ctx.command.name}`.")
        else:
            await ctx.send(f"Error: `{error}`")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = ("Error: You need Manage Messages or higher." if isinstance(error, app_commands.MissingPermissions) else f"Error: `{error}`")
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SalesOrders(bot))
