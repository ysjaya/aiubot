from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Teks untuk setiap bagian menu
main_menu_text = """
🤖 **Bantuan Perintah Bot** 🤖

Silakan pilih kategori di bawah ini untuk melihat daftar perintah yang tersedia.
"""

utility_menu_text = """
🛠️ **Perintah Utilitas**

`.id`
Menampilkan ID chat, ID pengguna yang dibalas, atau ID Anda sendiri.

`.ping`
Cek latensi dan memastikan bot aktif.

`.help`
Menampilkan menu bantuan interaktif ini.
"""

control_menu_text = """
⚙️ **Perintah Kontrol**

`.start`
Mengaktifkan fitur balas otomatis untuk akun ini.

`.stop`
Menonaktifkan fitur balas otomatis untuk akun ini.
"""

developer_menu_text = """
👨‍💻 **Perintah Khusus Developer**

`.add <session>`
Menambahkan userbot baru secara live tanpa restart.
**Penting**: Penambahan ini bersifat sementara (runtime). Untuk membuatnya permanen, Anda harus menambahkan session string ke environment variable di server.

`.gcast <pesan>`
Mengirim broadcast ke semua grup di mana bot menjadi anggota.
**Perhatian**: Gunakan dengan bijak untuk menghindari spam.

`.gucast <pesan>`
Mengirim broadcast ke semua obrolan pribadi (user) yang ada di daftar obrolan.
**Perhatian**: Gunakan dengan bijak untuk menghindari spam.
"""

# Keyboard (Tombol) untuk setiap menu
main_menu_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🛠️ Utilitas", callback_data="help_utility"),
            InlineKeyboardButton("⚙️ Kontrol", callback_data="help_control"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Developer", callback_data="help_developer"),
        ]
    ]
)

back_button_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("⬅️ Kembali ke Menu Utama", callback_data="help_main"),
        ]
    ]
)
