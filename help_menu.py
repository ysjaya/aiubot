from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Teks untuk setiap bagian menu
main_menu_text = """
🤖 **Help Menu, what's good!** 🤙

Yo, *basically* ini semua command yang bisa lo pake. Tinggal pilih aja mau liat apaan, biar nggak *lost in translation*.
"""

utility_menu_text = """
🛠️ **Utility Stuffs**

`.id`
Ngecek ID. *Basically*, buat *stalking* digital. LOL.

`.ping`
Cuma 'pong' doang, ngetes koneksi. *Chill*.

`.help`
Kalo lo lupa, balik lagi ke sini. *No worries*.
"""

control_menu_text = """
⚙️ **Control Commands**

`.start`
Nyalain auto-reply. Biar gue yang balesin, lo tinggal *chill*.

`.stop`
Matiin auto-reply. *Okay, mic's back to you*.
"""

developer_menu_text = """
👨‍💻 **Developer's Playground**

`.add <session>`
Nambahin userbot baru *on the fly*. Tapi ini *temporary* ya, kalo mau permanen, *you know the drill*, tambahin di env.

`.gcast <pesan>`
Broadcast ke semua grup. *Please, use it wisely*, jangan nyepam. *Not cool*.

`.gucast <pesan>`
Broadcast ke semua DM. *Seriously*, jangan aneh-aneh, cuy.
"""

# Keyboard (Tombol) untuk setiap menu
main_menu_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🛠️ Utility", callback_data="help_utility"),
            InlineKeyboardButton("⚙️ Control", callback_data="help_control"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Developer", callback_data="help_developer"),
        ]
    ]
)

back_button_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("⬅️ Balik ke Menu Awal", callback_data="help_main"),
        ]
    ]
)
