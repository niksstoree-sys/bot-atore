"""
cogs/order.py — Order processing system.
Handles purchase flow, voucher validation, stock delivery, and order status management.
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database.database import Database
from utils.embeds import (
    order_embed, order_success_embed, order_cancelled_embed,
    invoice_embed, error_embed, success_embed, info_embed, log_embed,
)
from utils.helpers import (
    is_admin, format_price, safe_send_dm, send_log, make_invoice_number
)
from utils.views import TicketActionView
from config import Config

logger = logging.getLogger("store.cog.order")


async def process_purchase(
    interaction: discord.Interaction,
    db: Database,
    product,
    payment,
    voucher_code: str = "",
    notes: str = "",
) -> None:
    """
    Called when a user completes the buy flow.
    Creates an order, validates voucher, creates a ticket channel.
    """
    await interaction.response.defer(ephemeral=True)

    # ─── Stock Check ──────────────────────────────────────────────────────────
    stock_count = await db.get_product_stock_count(product["id"])
    if stock_count == 0:
        return await interaction.followup.send(
            embed=error_embed("Stok Habis", "Maaf, produk ini sedang kehabisan stok."),
            ephemeral=True,
        )

    # ─── Voucher Validation ───────────────────────────────────────────────────
    discount_amount = 0.0
    voucher_row = None
    final_price = product["price"]

    if voucher_code:
        voucher_row = await db.get_voucher(voucher_code)
        if not voucher_row:
            return await interaction.followup.send(
                embed=error_embed("Voucher Tidak Valid", f"Kode `{voucher_code}` tidak ditemukan atau sudah expired."),
                ephemeral=True,
            )
        if voucher_row["max_uses"] > 0 and voucher_row["used_count"] >= voucher_row["max_uses"]:
            return await interaction.followup.send(
                embed=error_embed("Voucher Habis", "Voucher ini sudah mencapai batas pemakaian."),
                ephemeral=True,
            )
        if await db.user_used_voucher(voucher_row["id"], interaction.user.id):
            return await interaction.followup.send(
                embed=error_embed("Voucher Sudah Dipakai", "Kamu sudah pernah memakai voucher ini."),
                ephemeral=True,
            )
        if final_price < voucher_row["min_purchase"]:
            return await interaction.followup.send(
                embed=error_embed(
                    "Minimum Pembelian",
                    f"Voucher ini memerlukan pembelian minimum {format_price(voucher_row['min_purchase'])}.",
                ),
                ephemeral=True,
            )
        if voucher_row["discount_type"] == "percent":
            discount_amount = final_price * (voucher_row["discount_value"] / 100)
        else:
            discount_amount = min(voucher_row["discount_value"], final_price)
        final_price = max(0.0, final_price - discount_amount)

    # ─── Create Order ─────────────────────────────────────────────────────────
    order_id = await db.create_order(
        user_id=interaction.user.id,
        username=str(interaction.user),
        product_id=product["id"],
        product_name=product["name"],
        total_price=final_price,
        payment_method=payment["name"],
        voucher_code=voucher_code.upper() if voucher_code else "",
        discount_amount=discount_amount,
        notes=notes,
    )
    order = await db.get_order(order_id)

    # ─── Create Ticket Channel ────────────────────────────────────────────────
    guild = interaction.guild
    category_channel: Optional[discord.CategoryChannel] = None
    if Config.TICKET_CATEGORY_ID:
        category_channel = guild.get_channel(Config.TICKET_CATEGORY_ID)

    safe_username = "".join(
        c for c in interaction.user.display_name if c.isalnum() or c in "-_"
    )[:20] or "user"
    ticket_name = f"ticket-{safe_username}-{order_id}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True,
        ),
    }

    # Add admin role to ticket
    admin_role = guild.get_role(Config.ADMIN_ROLE_ID)
    if admin_role:
        overwrites[admin_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True,
        )

    try:
        ticket_channel: discord.TextChannel = await guild.create_text_channel(
            name=ticket_name,
            category=category_channel,
            overwrites=overwrites,
            topic=f"Order #{order_id} | {interaction.user} | {product['name']}",
            reason=f"Store ticket for order #{order_id}",
        )
    except discord.Forbidden:
        await db.update_order(order_id, status="cancelled")
        return await interaction.followup.send(
            embed=error_embed("Error", "Bot tidak punya permission membuat channel ticket."),
            ephemeral=True,
        )

    # ─── Save Ticket to DB ────────────────────────────────────────────────────
    await db.create_ticket(
        channel_id=ticket_channel.id,
        user_id=interaction.user.id,
        username=str(interaction.user),
        order_id=order_id,
    )
    await db.update_order(order_id, ticket_channel=ticket_channel.id)

    # Use voucher if valid
    if voucher_row:
        await db.use_voucher(voucher_row["id"], interaction.user.id, order_id)

    # ─── Send Ticket Welcome Embed ────────────────────────────────────────────
    from utils.embeds import ticket_welcome_embed
    ticket_embed_msg = ticket_welcome_embed(interaction.user, order, product)
    view = TicketActionView(db)

    payment_info_embed = discord.Embed(
        title="💳 Informasi Pembayaran",
        description=(
            f"**Metode:** {payment['name']}\n"
            f"**Detail:**\n```\n{payment['details'] or 'Hubungi admin untuk detail.'}\n```\n"
            f"**Total:** {format_price(final_price)}"
            + (f"\n\n🎟️ Voucher `{voucher_code.upper()}` diaplikasikan: -**{format_price(discount_amount)}**" if voucher_code else "")
        ),
        color=Config.COLOR_INFO,
    )

    await ticket_channel.send(
        content=f"🎫 {interaction.user.mention} | Ticket Pembelian",
        embeds=[ticket_embed_msg, payment_info_embed],
        view=view,
    )

    # ─── Notify User ──────────────────────────────────────────────────────────
    await interaction.followup.send(
        embed=success_embed(
            "Ticket Dibuat!",
            f"Ticket pembelianmu berhasil dibuat di {ticket_channel.mention}!\n\n"
            f"📦 **{product['name']}** — {format_price(final_price)}\n"
            f"💳 **{payment['name']}**\n\n"
            "Silakan lakukan pembayaran dan upload bukti di ticket.",
        ),
        ephemeral=True,
    )

    # ─── Log Activity ─────────────────────────────────────────────────────────
    await db.log_activity(
        action="Order Created",
        actor_id=interaction.user.id,
        actor_name=str(interaction.user),
        target=product["name"],
        details=f"Order #{order_id} | Total: {format_price(final_price)} | Payment: {payment['name']}",
        guild_id=interaction.guild_id or 0,
    )

    log = log_embed(
        action="🛒 Order Baru",
        actor=f"{interaction.user} ({interaction.user.id})",
        details=(
            f"Order **#{order_id}** | `{order['invoice_number']}`\n"
            f"Produk: **{product['name']}**\n"
            f"Total: **{format_price(final_price)}**\n"
            f"Payment: **{payment['name']}**\n"
            f"Ticket: {ticket_channel.mention}"
        ),
        color=Config.COLOR_WARNING,
    )
    await send_log(interaction.client, log, Config.LOG_WEBHOOK_URL or None)
    logger.info(f"Order #{order_id} created for {interaction.user} — {product['name']}")


async def confirm_order_in_ticket(
    interaction: discord.Interaction, db: Database
) -> None:
    """Admin confirms an order in a ticket channel. Delivers stock and closes loop."""
    await interaction.response.defer(ephemeral=True)

    ticket = await db.get_ticket_by_channel(interaction.channel_id)
    if not ticket:
        return await interaction.followup.send(
            embed=error_embed("Error", "Tidak menemukan data ticket untuk channel ini."),
            ephemeral=True,
        )
    if ticket["status"] != "open":
        return await interaction.followup.send(
            embed=error_embed("Error", "Ticket ini sudah ditutup."), ephemeral=True
        )

    order = await db.get_order(ticket["order_id"])
    if not order:
        return await interaction.followup.send(
            embed=error_embed("Error", "Data order tidak ditemukan."), ephemeral=True
        )
    if order["status"] != "pending":
        return await interaction.followup.send(
            embed=error_embed("Error", f"Order sudah berstatus `{order['status']}`."),
            ephemeral=True,
        )

    # ─── FIFO Stock Retrieval ─────────────────────────────────────────────────
    stock = await db.get_next_stock(order["product_id"])
    if not stock:
        return await interaction.followup.send(
            embed=error_embed("Stok Habis!", "Tidak ada stok tersedia untuk produk ini. Tambah stok dulu."),
            ephemeral=True,
        )

    await db.mark_stock_sold(stock["id"], order["id"])

    # ─── Update Order ─────────────────────────────────────────────────────────
    await db.update_order(
        order["id"],
        status="success",
        stock_content=stock["content"],
    )

    # ─── Add to Purchase History ──────────────────────────────────────────────
    await db.add_purchase_history(
        user_id=order["user_id"],
        username=order["username"],
        order_id=order["id"],
        product_id=order["product_id"],
        product_name=order["product_name"],
        total_price=order["total_price"],
        status="success",
    )

    # ─── Assign Role if Configured ────────────────────────────────────────────
    product = await db.get_product(order["product_id"])
    if product and product["role_id"]:
        guild = interaction.guild
        member = guild.get_member(order["user_id"])
        if member:
            role = guild.get_role(product["role_id"])
            if role:
                try:
                    await member.add_roles(role, reason=f"Purchase order #{order['id']}")
                except discord.Forbidden:
                    logger.warning(f"Could not assign role {role.id} to {member}")

    # ─── Deliver Stock via DM ─────────────────────────────────────────────────
    buyer = interaction.guild.get_member(order["user_id"])
    updated_order = await db.get_order(order["id"])
    success_embed_msg = order_success_embed(updated_order, stock["content"])
    inv_embed = invoice_embed(updated_order)

    dm_sent = False
    if buyer:
        dm_sent = await safe_send_dm(buyer, embeds=[success_embed_msg, inv_embed])

    # ─── Send in Ticket if DM Failed ─────────────────────────────────────────
    channel = interaction.channel
    if isinstance(channel, discord.TextChannel):
        mention = f"<@{order['user_id']}>"
        if not dm_sent:
            await channel.send(
                content=f"📬 {mention} DM kamu tertutup. Item kamu dikirim di sini:",
                embeds=[success_embed_msg, inv_embed],
            )
        else:
            await channel.send(
                content=f"✅ {mention} Pembelian berhasil! Cek DM kamu untuk item.",
                embed=discord.Embed(
                    title="✅ Order Dikonfirmasi",
                    description=f"Order `{updated_order['invoice_number']}` berhasil dikonfirmasi oleh {interaction.user.mention}.",
                    color=Config.COLOR_SUCCESS,
                ),
            )

    # ─── Log ──────────────────────────────────────────────────────────────────
    await db.log_activity(
        action="Order Success",
        actor_id=interaction.user.id,
        actor_name=str(interaction.user),
        target=order["product_name"],
        details=f"Order #{order['id']} | Invoice: {updated_order['invoice_number']} | Buyer: {order['username']}",
        guild_id=interaction.guild_id or 0,
    )

    log = log_embed(
        action="✅ Order Sukses",
        actor=f"{interaction.user} (Admin)",
        details=(
            f"Order **#{order['id']}** dikonfirmasi.\n"
            f"Buyer: <@{order['user_id']}>\n"
            f"Produk: **{order['product_name']}**\n"
            f"Total: **{format_price(order['total_price'])}**\n"
            f"DM: {'✅ Terkirim' if dm_sent else '❌ Gagal, dikirim di ticket'}"
        ),
        color=Config.COLOR_SUCCESS,
    )
    await send_log(interaction.client, log, Config.LOG_WEBHOOK_URL or None)

    await interaction.followup.send(
        embed=success_embed(
            "Order Dikonfirmasi",
            f"Order `{updated_order['invoice_number']}` berhasil dikonfirmasi dan stok terkirim.",
        ),
        ephemeral=True,
    )
    logger.info(f"Order #{order['id']} confirmed by {interaction.user}")


async def cancel_order_in_ticket(
    interaction: discord.Interaction, db: Database
) -> None:
    """Admin cancels an order in a ticket channel."""
    await interaction.response.defer(ephemeral=True)

    ticket = await db.get_ticket_by_channel(interaction.channel_id)
    if not ticket:
        return await interaction.followup.send(
            embed=error_embed("Error", "Data ticket tidak ditemukan."), ephemeral=True
        )

    order = await db.get_order(ticket["order_id"])
    if not order:
        return await interaction.followup.send(
            embed=error_embed("Error", "Data order tidak ditemukan."), ephemeral=True
        )
    if order["status"] != "pending":
        return await interaction.followup.send(
            embed=error_embed("Error", f"Order sudah berstatus `{order['status']}`."),
            ephemeral=True,
        )

    await db.update_order(order["id"], status="cancelled")
    await db.add_purchase_history(
        user_id=order["user_id"],
        username=order["username"],
        order_id=order["id"],
        product_id=order["product_id"],
        product_name=order["product_name"],
        total_price=order["total_price"],
        status="cancelled",
    )

    updated_order = await db.get_order(order["id"])
    buyer = interaction.guild.get_member(order["user_id"])
    cancel_embed = order_cancelled_embed(updated_order, reason=f"Dibatalkan oleh {interaction.user}")

    channel = interaction.channel
    if isinstance(channel, discord.TextChannel):
        mention = f"<@{order['user_id']}>"
        await channel.send(
            content=f"❌ {mention} Order kamu telah dibatalkan.",
            embed=cancel_embed,
        )

    if buyer:
        await safe_send_dm(buyer, embed=cancel_embed)

    await db.log_activity(
        action="Order Cancelled",
        actor_id=interaction.user.id,
        actor_name=str(interaction.user),
        target=order["product_name"],
        details=f"Order #{order['id']} cancelled by {interaction.user}",
        guild_id=interaction.guild_id or 0,
    )

    log = log_embed(
        action="❌ Order Dibatalkan",
        actor=f"{interaction.user} (Admin)",
        details=f"Order **#{order['id']}** | Buyer: <@{order['user_id']}> | Produk: **{order['product_name']}**",
        color=Config.COLOR_ERROR,
    )
    await send_log(interaction.client, log, Config.LOG_WEBHOOK_URL or None)

    await interaction.followup.send(
        embed=success_embed("Order Dibatalkan", f"Order `{updated_order['invoice_number']}` telah dibatalkan."),
        ephemeral=True,
    )
    logger.info(f"Order #{order['id']} cancelled by {interaction.user}")


class OrderCog(commands.Cog, name="Order"):
    """Order management slash commands."""

    def __init__(self, bot: commands.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    order_group = app_commands.Group(
        name="order", description="Kelola order di store."
    )

    @order_group.command(name="info", description="Lihat detail order berdasarkan invoice.")
    @app_commands.guild_only()
    @app_commands.describe(invoice="Nomor invoice (contoh: INV-20240101120000-001)")
    async def order_info(self, interaction: discord.Interaction, invoice: str) -> None:
        await interaction.response.defer(ephemeral=True)

        order = await self.db.get_order_by_invoice(invoice.upper())
        if not order:
            return await interaction.followup.send(
                embed=error_embed("Tidak Ditemukan", f"Invoice `{invoice}` tidak ditemukan."),
                ephemeral=True,
            )

        if not is_admin(interaction.user) and order["user_id"] != interaction.user.id:
            return await interaction.followup.send(
                embed=error_embed("Akses Ditolak", "Kamu tidak punya akses ke order ini."),
                ephemeral=True,
            )

        product = await self.db.get_product(order["product_id"])
        if not product:
            return await interaction.followup.send(
                embed=error_embed("Error", "Data produk tidak ditemukan."), ephemeral=True
            )

        embed = order_embed(order, product)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @order_group.command(name="list", description="[Admin] Lihat daftar order terbaru.")
    @app_commands.guild_only()
    @app_commands.describe(
        status="Filter status (pending/success/cancelled)",
        limit="Jumlah order ditampilkan (default: 10)",
    )
    async def order_list(
        self,
        interaction: discord.Interaction,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> None:
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Akses Ditolak", "Hanya admin."), ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        valid_statuses = {"pending", "success", "cancelled"}
        if status and status not in valid_statuses:
            return await interaction.followup.send(
                embed=error_embed("Error", f"Status tidak valid. Pilih: {', '.join(valid_statuses)}"),
                ephemeral=True,
            )

        limit = max(1, min(limit, 50))
        orders = await self.db.get_orders(status=status, limit=limit)

        if not orders:
            return await interaction.followup.send(
                embed=info_embed("Kosong", "Tidak ada order."), ephemeral=True
            )

        from utils.embeds import _base_embed
        embed = _base_embed(
            title=f"📋 Daftar Order{f' ({status.upper()})' if status else ''}",
            color=Config.COLOR_PRIMARY,
        )
        status_emoji = {"pending": "⏳", "success": "✅", "cancelled": "❌"}
        for o in orders[:20]:
            emoji = status_emoji.get(o["status"], "❓")
            embed.add_field(
                name=f"{emoji} `{o['invoice_number']}`",
                value=(
                    f"👤 {o['username']} | 📦 {o['product_name'][:30]}\n"
                    f"💰 {format_price(o['total_price'])} | 💳 {o['payment_method']} | "
                    f"📅 {o['created_at'][:16]}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @order_group.command(name="invoice", description="Cetak ulang invoice order.")
    @app_commands.guild_only()
    @app_commands.describe(invoice="Nomor invoice")
    async def order_invoice(self, interaction: discord.Interaction, invoice: str) -> None:
        await interaction.response.defer(ephemeral=True)

        order = await self.db.get_order_by_invoice(invoice.upper())
        if not order:
            return await interaction.followup.send(
                embed=error_embed("Tidak Ditemukan", f"Invoice `{invoice}` tidak ditemukan."),
                ephemeral=True,
            )

        if not is_admin(interaction.user) and order["user_id"] != interaction.user.id:
            return await interaction.followup.send(
                embed=error_embed("Akses Ditolak", "Kamu tidak punya akses."), ephemeral=True
            )

        if order["status"] != "success":
            return await interaction.followup.send(
                embed=error_embed("Error", "Invoice hanya tersedia untuk order yang sudah sukses."),
                ephemeral=True,
            )

        await interaction.followup.send(embed=invoice_embed(order), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OrderCog(bot, bot.db))
