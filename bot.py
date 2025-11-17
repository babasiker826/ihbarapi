import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from flask import Flask, request, jsonify
import os
import logging

# Log ayarı
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Environment variables'dan al (Render için)
API_ID = int(os.environ.get('API_ID', '17570480'))
API_HASH = os.environ.get('API_HASH', '18c5be05094b146ef29b0cb6f6601f1f')
SESSION_STR = os.environ.get('STRING_SESSION', '1ApWapzMBu8PXW4pbOyH0kArCYIGqcgPmIXo99Kn4k6DjNpnjY_byNsRMLdwKb_3F6TWI5TEv3OPPSneHv44IwrBRk0nM_zkXEmYghQosFSitbhqZD8tE7y0eFeFjrm0b6K2DpVllXkZZdSX7PklySrlCMjAx-J0IaCnDEProkKe2t1yRJ8PlRBhAdkDd9AxJr3bD1zH6mIqATPd01RJ2v2RgNb1adZ0ZCvFu9wwIcQVWRWSspSAQncPwZS9frSfWNz7uOPp7tZKO-GFKEi2uVsJQ29sjARXRL31XI3TqQWmEii6i94zfJtv2vukhApbrJVsr6-w6ZCwhGmPF8jGH3WA4XwzR8ng=')
BOT_USERNAME = "@KenevizihbarBot"

# Global client instance (Render için optimize)
_client = None

async def get_client():
    """Client'ı önbelleğe al"""
    global _client
    if _client is None:
        _client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
        await _client.start()
    return _client

# -----------------------------------------------------------
# TELEGRAM GÖNDERME FONKSİYONU
# -----------------------------------------------------------
async def send_to_bot(command, address, details):
    client = await get_client()
    
    try:
        # Komut
        await client.send_message(BOT_USERNAME, command)
        await asyncio.sleep(2)

        # Adres
        await client.send_message(BOT_USERNAME, address)
        await asyncio.sleep(2)

        # Detay
        await client.send_message(BOT_USERNAME, details)
        await asyncio.sleep(2)

        return True, "İhbar başarıyla gönderildi"

    except Exception as e:
        # Hata durumunda client'ı resetle
        global _client
        if _client:
            await _client.disconnect()
            _client = None
        return False, f"Hata: {str(e)}"

# -----------------------------------------------------------
# PARAMETRE BİRLEŞTİRİCİ
# -----------------------------------------------------------
def combine_params(key):
    values = request.args.getlist(key)
    if not values:
        return ""
    
    # URL decode işlemi
    decoded_values = []
    for value in values:
        try:
            # URL encoded karakterleri decode et
            import urllib.parse
            decoded = urllib.parse.unquote(value)
            decoded_values.append(decoded)
        except:
            decoded_values.append(value)
    
    return " ".join(decoded_values)

# -----------------------------------------------------------
# TÜM İHBARLARIN ORTAK KODU
# -----------------------------------------------------------
def handle_ihbar(command):
    adres = combine_params("adres")
    detay = combine_params("detay")

    if not adres or not detay:
        return jsonify({"status": "error", "message": "adres ve detay parametreleri gerekli"})

    try:
        # Asenkron işlem için event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, msg = loop.run_until_complete(send_to_bot(command, adres, detay))
        loop.close()

        if success:
            return jsonify({
                "status": "success", 
                "message": msg,
                "data": {
                    "komut": command,
                    "adres": adres,
                    "detay": detay
                }
            })
        else:
            return jsonify({
                "status": "error", 
                "message": msg
            }), 500

    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Sistem hatası: {str(e)}"
        }), 500

# -----------------------------------------------------------
# USOM / EGM / JANDARMA
# -----------------------------------------------------------
@app.route('/usomihbar')
def usom_ihbar():
    return handle_ihbar("/usomihbar")

@app.route('/egmihbar')
def egm_ihbar():
    return handle_ihbar("/egmihbar")

@app.route('/jandarmaihbar')
def jandarma_ihbar():
    return handle_ihbar("/jandarmaihbar")

# -----------------------------------------------------------
# SAĞLIK KONTROLÜ (Render için gerekli)
# -----------------------------------------------------------
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "message": "API çalışıyor"})

# -----------------------------------------------------------
# ANA SAYFA
# -----------------------------------------------------------
@app.route('/')
def ana():
    return jsonify({
        "message": "HASIM SYSTEM İHBAR API",
        "version": "1.0",
        "endpoints": {
            "usom": "/usomihbar?adres=...&detay=...",
            "egm": "/egmihbar?adres=...&detay=...", 
            "jandarma": "/jandarmaihbar?adres=...&detay=...",
            "health": "/health"
        },
        "örnek": "/jandarmaihbar?adres=Köy%20yolu%20mevkii&detay=Silah%20sesleri%20duyuluyor"
    })

# -----------------------------------------------------------
# UYGULAMA KAPATILIRKEN
# -----------------------------------------------------------
@app.teardown_appcontext
async def shutdown(exception=None):
    global _client
    if _client:
        await _client.disconnect()
        _client = None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚨 İHBAR API RENDER'DA ÇALIŞIYOR - Port: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
