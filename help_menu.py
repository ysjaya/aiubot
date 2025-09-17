from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

"""
Struktur Menu Bantuan (Data-Driven)

MENU_DATA adalah "single source of truth" untuk semua halaman bantuan.
Setiap kunci utama (e.g., "main", "utility") mewakili satu halaman.

Struktur setiap halaman:
- "text": Teks konten yang akan ditampilkan (mendukung Markdown).
- "keyboard": Daftar tombol (InlineKeyboardButton) untuk halaman tersebut.

Callback data menggunakan format "help:<action>:<payload>"
- help:utility -> Menampilkan halaman 'utility'.
- help:back:main -> Kembali ke halaman 'main'.
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
            "Perintah untuk mengelola perilaku auto-reply dari AI.\n\n"
            "• `.start`\n"
            "  Mengaktifkan fitur auto-reply. AI akan mulai membalas pesan secara otomatis.\n\n"
            "• `.stop`\n"
            "  Menonaktifkan fitur auto-reply. Anda kembali memegang kendali penuh."
        ),
        "keyboard": [[InlineKeyboardButton("⬅️ Kembali", callback_data="help:back:main")]],
    },
    "developer": {
        "text": (
            "👨‍💻 **Perintah Khusus Developer**\n\n"
            "Fitur lanjutan yang ditujukan untuk developer. Gunakan dengan hati-hati.\n\n"
            "• `.add <session>`\n"
            "  Menambahkan userbot baru secara dinamis (bersifat sementara hingga bot di-restart).\n\n"
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
    
    Args:
        name (str): Kunci dari menu yang diinginkan (e.g., "main", "utility").
        
    Returns:
        Tuple[str, InlineKeyboardMarkup]: Teks menu dan objek keyboard.
    """
    # Jika nama menu tidak ditemukan, kembali ke menu "main" sebagai default
    data = MENU_DATA.get(name, MENU_DATA["main"])
    
    text = data["text"]
    keyboard = InlineKeyboardMarkup(data["keyboard"])
    
    return text, keyboard
