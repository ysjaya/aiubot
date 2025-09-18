from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

"""
Struktur Menu Bantuan (Data-Driven)
"""

MENU_DATA = {
    "main": {
        "text": (
            "🤖 **Bantuan Userbot**\n\n"
            "Selamat datang! Ini adalah pusat kendali untuk semua fitur yang tersedia. "
            "Pilih salah satu kategori di bawah ini untuk melihat daftar perintah yang relevan."
        ),
        "keyboard": [
            [
                InlineKeyboardButton("🛠️ Utilitas", callback_data="help:utility"),
                InlineKeyboardButton("⚙️ Kontrol AI", callback_data="help:control"),
            ],
            [
                InlineKeyboardButton("👨‍💻 Developer", callback_data="help:developer"),
            ],
        ],
    },
    "utility": {
        "text": (
            "🛠️ **Perintah Utilitas**\n\n"
            "Kumpulan perintah untuk mendapatkan informasi dan melakukan tugas-tugas dasar.\n\n"
            "• `.id`\n"
            "  Mendapatkan ID pengguna dan ID obrolan saat ini.\n\n"
            "• `.ping`\n"
            "  Memeriksa apakah userbot aktif dan merespons.\n\n"
            "• `.help`\n"
            "  Menampilkan kembali menu bantuan utama ini."
        ),
        "keyboard": [[InlineKeyboardButton("⬅️ Kembali", callback_data="help:back:main")]],
    },
    "control": {
        "text": (
            "⚙️ **Kontrol Auto-Reply AI**\n\n"
            "Perintah untuk mengelola perilaku auto-reply secara terpisah untuk DM dan Grup.\n\n"
            "**Kontrol DM (Pesan Pribadi):**\n"
            "• `.startdm`\n"
            "  Mengaktifkan auto-reply di semua DM.\n\n"
            "• `.stopdm`\n"
            "  Menonaktifkan auto-reply di semua DM.\n\n"
            "**Kontrol Grup:**\n"
            "• `.startgc`\n"
            "  Mengaktifkan auto-reply di semua grup (saat di-mention/reply).\n\n"
            "• `.stopgc`\n"
            "  Menonaktifkan auto-reply di semua grup."
        ),
        "keyboard": [[InlineKeyboardButton("⬅️ Kembali", callback_data="help:back:main")]],
    },
    "developer": {
        "text": (
            "👨‍💻 **Perintah Khusus Developer**\n\n"
            "Fitur lanjutan yang ditujukan untuk developer. Gunakan dengan hati-hati.\n\n"
            "• `.add <session>`\n"
            "  Menambahkan userbot baru secara langsung dengan session string (temporer).\n\n"
            "• `.gcast <pesan>`\n"
            "  Mengirim pesan broadcast ke semua grup yang Anda ikuti.\n\n"
            "• `.gucast <pesan>`\n"
            "  Mengirim pesan broadcast ke semua obrolan pribadi (DM)."
        ),
        "keyboard": [[InlineKeyboardButton("⬅️ Kembali", callback_data="help:back:main")]],
    },
}

def get_menu(name: str):
    """
    Mengambil teks dan markup keyboard untuk nama menu yang diberikan.
    """
    data = MENU_DATA.get(name, MENU_DATA["main"])
    text = data["text"]
    keyboard = InlineKeyboardMarkup(data["keyboard"])
    return text, keyboard
