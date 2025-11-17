import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from flask import Flask, request, jsonify
import sys

# UTF-8
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)

API_ID = 17570480
API_HASH = "18c5be05094b146ef29b0cb6f6601f1f"
SESSION_STR = "1ApWapzMBu8PXW4pbOyH0kArCYIGqcgPmIXo99Kn4k6DjNpnjY_byNsRMLdwKb_3F6TWI5TEv3OPPSneHv44IwrBRk0nM_zkXEmYghQosFSitbhqZD8tE7y0eFeFjrm0b6K2DpVllXkZZdSX7PklySrlCMjAx-J0IaCnDEProkKe2t1yRJ8PlRBhAdkDd9AxJr3bD1zH6mIqATPd01RJ2v2RgNb1adZ0ZCvFu9wwIcQVWRWSspSAQncPwZS9frSfWNz7uOPp7tZKO-GFKEi2uVsJQ29sjARXRL31XI3TqQWmEii6i94zfJtv2vukhApbrJVsr6-w6ZCwhGmPF8jGH3WA4XwzR8ng="
BOT_USERNAME = "@KenevizihbarBot"


# -----------------------------------------------------------
# TELEGRAM GÖNDERME FONKSİYONU
# -----------------------------------------------------------
async def send_to_bot(command, address, details):
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.start()

    try:
        # Komut
        await client.send_message(BOT_USERNAME, command)
        await asyncio.sleep(1.5)

        # Adres
        await client.send_message(BOT_USERNAME, address)
        await asyncio.sleep(1.5)

        # Detay
        await client.send_message(BOT_USERNAME, details)
        await asyncio.sleep(1.5)

        return True, "İhbar başarıyla gönderildi"

    except Exception as e:
        return False, str(e)

    finally:
        await client.disconnect()



# -----------------------------------------------------------
# PARAMETRE BİRLEŞTİRİCİ (KÖY&YOLU&MEVKİİ → 'Köy yolu mevkii')
# -----------------------------------------------------------
def combine_params(key):
    values = request.args.getlist(key)
    if not values:
        return ""
    combined = " ".join(values)

    # Türkçe düzeltme
    try:
        return combined.encode('latin1').decode('utf-8')
    except:
        return combined



# -----------------------------------------------------------
# TÜM İHBARLARIN ORTAK KODU
# -----------------------------------------------------------
def handle_ihbar(command):
    adres = combine_params("adres")
    detay = combine_params("detay")

    if not adres or not detay:
        return jsonify({"status": "error", "message": "adres ve detay gerekli"})

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success, msg = loop.run_until_complete(send_to_bot(command, adres, detay))
    loop.close()

    return jsonify({"status": "success" if success else "error", "message": msg})



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
# ANA SAYFA
# -----------------------------------------------------------
@app.route('/')
def ana():
    return jsonify({
        "message": "HASIM SYSTEM İHBAR API",
        "örnek": "/jandarmaihbar?adres=Köy&yolu&mevkii&detay=Silah&sesleri&duyuluyor"
    })



if __name__ == '__main__':
    print("🚨 İHBAR API ÇALIŞIYOR...")
    app.run(host="0.0.0.0", port=5000)
