from pyrogram import Client
from pyrogram.types import Message

# Fungsi ini akan dipanggil dari main.py untuk membuat handler
def get_stats_handler(auto_reply_states: dict):
    """
    Membuat dan mengembalikan fungsi handler untuk perintah .stat.
    Ini memungkinkan handler untuk mengakses 'auto_reply_states' dari main.py.
    """
    async def stat_command_handler(client: Client, message: Message):
        """Menampilkan status auto-reply saat ini."""
        try:
            client_id = client.me.id
            states = auto_reply_states.get(client_id, {})
            
            # Dapatkan status, default ke False jika tidak ditemukan
            dm_status = states.get('dm', False)
            gc_status = states.get('gc', False)
            
            # Ubah boolean menjadi teks yang lebih mudah dibaca dengan emoji
            dm_text = "🟢 **ON**" if dm_status else "🔴 **OFF**"
            gc_text = "🟢 **ON**" if gc_status else "🔴 **OFF**"

            status_message = (
                "🤖 **Status Auto-Reply Bot**\n\n"
                f"Status untuk akun: **{client.me.first_name}**\n\n"
                f"• Pesan Pribadi (DM): {dm_text}\n"
                f"• Grup (GC): {gc_text}"
            )
            
            await message.edit_text(status_message)
        except Exception as e:
            await message.edit_text(f"❌ Terjadi kesalahan saat mengambil status: `{e}`")

    return stat_command_handler
