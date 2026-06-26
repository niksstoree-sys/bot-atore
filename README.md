# 🏪 Discord Store Bot

Bot Discord store premium production-ready untuk jual beli produk digital.  
Dibangun dengan Python 3.12, discord.py, SQLite, dan arsitektur modular yang bersih.

---

## ✨ Fitur Utama

| Fitur | Keterangan |
|-------|------------|
| 🏪 Store Dashboard | Embed profesional + Select Menu kategori |
| 📂 Kategori | CRUD lengkap dengan toggle aktif/nonaktif |
| 🛍️ Produk | CRUD lengkap dengan thumbnail, banner, emoji |
| 📦 Stok | Sistem FIFO, bulk input, notifikasi stok habis |
| 💳 Payment | Kelola metode pembayaran secara dinamis |
| 🎫 Ticket | Auto-create, transcript HTML, close/delete |
| 🛒 Order | Full lifecycle: pending → confirm → kirim stok via DM |
| 🎟️ Voucher | Percent & flat discount, max uses, expiry |
| 📊 Statistik | Revenue, top produk, top customer |
| 📋 Logging | Activity log ke DB + Discord channel + Webhook |
| 🔄 Auto Backup | Otomatis backup database setiap N jam |
| 🔍 Search | Cari produk berdasarkan nama/deskripsi |
| 🕐 Riwayat | Riwayat pembelian per user dengan pagination |
| 🧾 Invoice | Generate invoice otomatis setelah order sukses |
| 🔔 Notif Stok | Peringatan otomatis saat stok menipis |

---

## 📁 Struktur Project

```
store-bot/
├── bot.py                  ← Entry point utama
├── config.py               ← Konfigurasi dari .env
├── requirements.txt
├── .env.example
├── README.md
│
├── database/
│   ├── database.py         ← Async database manager (semua CRUD)
│   └── models.py           ← Schema SQL + seed data
│
├── cogs/
│   ├── store.py            ← /setup-store, /search, /my-orders
│   ├── category.py         ← /category add|edit|delete|list
│   ├── product.py          ← /product add|edit|delete|list|info
│   ├── stock.py            ← /stock add|view|remove|clear
│   ├── payment.py          ← /payment add|edit|delete|list
│   ├── order.py            ← /order info|list|invoice + purchase flow
│   ├── ticket.py           ← /ticket list|close|delete|info
│   └── admin.py            ← /voucher, /logs, /sales, /sync
│
├── utils/
│   ├── embeds.py           ← Semua embed builder
│   ├── views.py            ← Semua Discord UI (Button, Select, Modal)
│   ├── helpers.py          ← Utility functions
│   └── logger.py           ← Logging configuration
│
├── assets/                 ← Aset gambar (opsional)
└── logs/                   ← Log file + backup database
    └── backups/
```

---

## 🚀 Cara Install & Menjalankan

### Prerequisites

- Python 3.12+
- Git
- Discord Bot Token

### 1. Clone / Download Project

```bash
git clone https://github.com/username/store-bot.git
cd store-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Environment

```bash
cp .env.example .env
```

Edit file `.env` dengan text editor:

```env
TOKEN=your_bot_token_here
GUILD_ID=123456789012345678
ADMIN_ROLE_ID=123456789012345678
OWNER_ROLE_ID=123456789012345678
TICKET_CATEGORY_ID=123456789012345678
LOG_CHANNEL_ID=123456789012345678
STORE_CHANNEL_ID=123456789012345678
```

### 4. Setup Discord Bot

1. Buka [Discord Developer Portal](https://discord.com/developers/applications)
2. Buat application baru → Bot
3. Copy token → paste ke `.env`
4. Di bagian **Privileged Gateway Intents**, aktifkan:
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **MESSAGE CONTENT INTENT**
5. Di **OAuth2 → URL Generator**, pilih scope:
   - `bot`, `applications.commands`
6. Bot permissions:
   - `Manage Channels`, `Manage Messages`, `Manage Roles`
   - `Send Messages`, `Embed Links`, `Attach Files`
   - `Read Message History`, `Use Slash Commands`

### 5. Jalankan Bot

```bash
python bot.py
```

---

## ⚙️ Cara Setup Store

Setelah bot online:

### 1. Sync Commands
Jalankan `/sync` di Discord (hanya owner)

### 2. Tambah Kategori
```
/category add name:Hosting description:Web Hosting emoji:🖥️
/category add name:Premium Apps description:Akun Premium emoji:⭐
```

### 3. Tambah Produk
```
/product add category_id:1 name:Hosting Unlimited price:15000 description:Hosting unlimited SSD
```

### 4. Tambah Stok
```
/stock add product_id:1
```
(Modal akan muncul, masukkan stok satu per baris)

### 5. Setup Store Channel
```
/setup-store
```

---

## 🚂 Deploy ke Railway

### 1. Persiapan

Pastikan project sudah di GitHub:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/username/store-bot.git
git push -u origin main
```

### 2. Buat Project di Railway

1. Buka [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub repo**
3. Pilih repository store-bot kamu
4. Railway akan otomatis detect Python

### 3. Environment Variables di Railway

Di Railway dashboard → project → **Variables**, tambahkan semua variabel dari `.env`:

| Key | Value |
|-----|-------|
| `TOKEN` | Bot token kamu |
| `GUILD_ID` | ID server Discord |
| `ADMIN_ROLE_ID` | ID role admin |
| `OWNER_ROLE_ID` | ID role owner |
| `TICKET_CATEGORY_ID` | ID kategori ticket |
| `LOG_CHANNEL_ID` | ID channel log |
| `STORE_CHANNEL_ID` | ID channel store |
| `DATABASE_PATH` | `database/store.db` |

### 4. Buat File Procfile

Buat file `Procfile` di root project:

```
worker: python bot.py
```

### 5. Deploy

```bash
git add Procfile
git commit -m "Add Procfile for Railway"
git push
```

Railway akan otomatis build dan deploy.

> **⚠️ Penting:** Railway Free tier sleep setelah tidak ada traffic. Untuk Discord bot yang harus selalu online, gunakan Railway Starter ($5/bulan) atau **keep-alive** dengan UptimeRobot.

---

## 📋 Daftar Command

### 🌐 Public Commands

| Command | Keterangan |
|---------|------------|
| `/my-orders` | Lihat riwayat pembelian kamu |
| `/search` | Cari produk |
| `/order info` | Detail order berdasarkan invoice |
| `/order invoice` | Cetak ulang invoice |
| `/ticket my` | Lihat ticket milikmu |
| `/ticket info` | Info ticket di channel ini |
| `/ticket close` | Tutup ticket |
| `/ping` | Cek latensi bot |

### 🔒 Admin Commands

| Command | Keterangan |
|---------|------------|
| `/setup-store` | Setup store dashboard |
| `/store-stats` | Statistik store |
| `/store-config` | Ubah konfigurasi store |
| `/backup` | Backup database manual |
| `/category add/edit/delete/list/toggle` | Kelola kategori |
| `/product add/edit/delete/list/info/toggle` | Kelola produk |
| `/stock add/add-text/view/remove/clear` | Kelola stok |
| `/payment add/edit/delete/list/toggle` | Kelola payment |
| `/voucher create/list/delete/toggle/check` | Kelola voucher |
| `/order list` | Daftar order |
| `/ticket list/delete` | Kelola ticket |
| `/logs` | Log aktivitas |
| `/sales` | Statistik penjualan |
| `/user-info` | Info user |
| `/admin-help` | Referensi semua command |

### 👑 Owner Commands

| Command | Keterangan |
|---------|------------|
| `/sync` | Sync slash commands ke server |

---

## 🎟️ Cara Pakai Voucher

### Buat Voucher
```
/voucher create
```
Isi modal:
- **Kode:** `HEMAT20`
- **Deskripsi:** Diskon 20% untuk semua produk
- **Tipe:** `percent` (atau `flat`)
- **Nilai:** `20`
- **Max Uses:** `100` (0 = unlimited)

### User Pakai Voucher
User memasukkan kode voucher di modal saat klik **Buy Now**.

---

## 🗄️ Migrasi ke PostgreSQL

Database dirancang agar mudah migrate. Query sudah kompatibel standar SQL.

### 1. Install psycopg2

```bash
pip install psycopg2-binary
```

### 2. Modifikasi `database/database.py`

Ganti method `_get_connection()`:

```python
import psycopg2
import psycopg2.extras

def _get_connection(self):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn
```

### 3. Sesuaikan Placeholder

PostgreSQL menggunakan `%s` bukan `?`:

```python
# SQLite
cursor.execute("SELECT * FROM products WHERE id = ?", (id,))

# PostgreSQL
cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
```

### 4. Gunakan pg_migrate.py (opsional)

Export data SQLite ke PostgreSQL dengan tool seperti `pgloader` atau `sqlite3-to-postgres`.

---

## 📊 Schema Database

```
categories   → id, name, description, emoji, position, is_active
products     → id, category_id*, name, description, price, emoji, thumbnail_url, banner_url, role_id, status
stocks       → id, product_id*, content, is_sold, sold_at, order_id*
payments     → id, name, details, is_active, position
product_payments → product_id*, payment_id*  (many-to-many)
orders       → id, user_id, username, product_id*, total_price, payment_method, status, invoice_number, voucher_code ...
tickets      → id, channel_id, user_id, username, order_id*, status, transcript_url, closed_by
vouchers     → id, code, discount_type, discount_value, min_purchase, max_uses, used_count, expires_at
voucher_uses → voucher_id*, user_id, order_id*
settings     → key (PK), value
purchase_history → user_id, order_id*, product_id*, total_price, status
activity_logs → action, actor_id, actor_name, target, details
```

---

## 🔒 Security

- ✅ Semua query menggunakan **parameterized statements** (no SQL injection)
- ✅ Permission check di setiap admin command
- ✅ Input validation dan sanitization
- ✅ Ticket permission otomatis (hanya user & admin)
- ✅ Voucher: max uses, expiry, per-user use tracking
- ✅ Stock content tidak ditampilkan publik (admin only)
- ✅ DM delivery untuk stock (tidak exposed di channel publik)

---

## 🐛 Troubleshooting

**Bot tidak muncul di server?**
→ Pastikan scope `applications.commands` dicentang saat invite.

**Slash command tidak muncul?**
→ Jalankan `/sync` atau tunggu hingga 1 jam untuk propagasi global.

**Bot tidak bisa buat ticket channel?**
→ Pastikan bot punya permission `Manage Channels` dan posisi role bot lebih tinggi dari user.

**DM gagal terkirim?**
→ Normal jika user menutup DM. Stock akan dikirim di dalam ticket channel.

**Railway bot mati sendiri?**
→ Upgrade ke Starter plan atau set keep-alive dengan UptimeRobot.

---

## 📝 License

MIT License — bebas digunakan dan dimodifikasi.

---

> Made with ❤️ by Discord Store Bot
