import asyncio
import aiohttp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from flask import Flask, request, jsonify
import sys
import os
import base64
import tempfile
import json
import re
from datetime import datetime

# UTF-8
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)

# Telethon konfigürasyonu (YENİ SESSION)
API_ID = 17570480
API_HASH = "18c5be05094b146ef29b0cb6f6601f1f"
SESSION_STR = "1ApWapzMBu41F0unpfr3tr25gZZr-lnJLzLeMLxOtPQTcMD4lOR__E_yHYwVl46JDzyRIC6Q52BtZPxORAvvF4T6QOaC3T3CgSXlsQueOPelzja5lQ52V5875LzxLL-FShBrn5X2vQp-fX7gdtVNk7kn3osHIQ0HiRudVsI4hKsRuW1iwEd56zbjm2CzndtvOjUYUYBo5TTSIqt4JFF__uPplV8uCnllpvY61dMNtNIgomEj2jI7nfeDomm3WFT6-Od7iwMPt_NwduiBnWdzPIcpsYGXLO7z-GXKdTHsIEB_KAAHO_FM4ncF5TFXgAotL2rno7Vf0Ejfa4yRvM3YngwEXT9RDoTE="

# Botlar
BOT_USERNAME = "@KenevizihbarBot"
VESIKA_BOT = "@VesikaBot"

# API URL'leri
SULALE_API = "https://dosya.alwaysdata.net/api/sulale.php?tc="
ADRES_API = "https://dosya.alwaysdata.net/api/adres.php?tc="
TCGSM_API = "https://dosya.alwaysdata.net/api/tcgsm.php?tc="

# -----------------------------------------------------------
# API İSTEK FONKSİYONLARI
# -----------------------------------------------------------
async def fetch_api_data(session, url, tc):
    """API'den veri çeker"""
    try:
        async with session.get(f"{url}{tc}", timeout=30) as response:
            if response.status == 200:
                content = await response.text()
                try:
                    return json.loads(content)
                except:
                    return {"raw_data": content}
            else:
                return {"error": f"HTTP {response.status}"}
    except Exception as e:
        return {"error": str(e)}

def fix_turkish_chars(text):
    """Türkçe karakterleri düzelt"""
    if not isinstance(text, str):
        return text
    
    replacements = {
        'Ã§': 'ç', 'Ã‡': 'Ç',
        'ÄŸ': 'ğ', 'Äž': 'Ğ',
        'Ã¶': 'ö', 'Ã–': 'Ö',
        'ÅŸ': 'ş', 'Åž': 'Ş',
        'Ã¼': 'ü', 'Ãœ': 'Ü',
        'Ä±': 'ı', 'Ä°': 'İ',
        'â€': '-', 'â€™': "'",
        'â€œ': '"', 'â€': '"',
        'â€˜': "'", 'â€¦': '...'
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    
    return text

def clean_json_data(data):
    """JSON verisindeki Türkçe karakterleri temizle"""
    if isinstance(data, dict):
        return {key: clean_json_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data]
    elif isinstance(data, str):
        return fix_turkish_chars(data)
    else:
        return data

# -----------------------------------------------------------
# VESIKA BOT İŞLEMLERİ
# -----------------------------------------------------------
async def get_vesika(tc_kimlik_no):
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.start()
    
    query_id = str(os.urandom(8).hex())
    
    try:
        await client.send_message(VESIKA_BOT, '/start')
        await asyncio.sleep(1)
        
        await client.send_message(VESIKA_BOT, f'/vesika {tc_kimlik_no}')
        
        photo_received = asyncio.Event()
        photo_data = {"image": None, "error": None, "file_path": None}
        
        @client.on(events.NewMessage(from_users=VESIKA_BOT))
        async def handler(event):
            if event.message.photo:
                try:
                    temp_dir = tempfile.gettempdir()
                    file_path = os.path.join(temp_dir, f"vesika_{tc_kimlik_no}_{query_id}.jpg")
                    
                    await event.message.download_media(file=file_path)
                    photo_data["file_path"] = file_path
                    
                    with open(file_path, "rb") as f:
                        image_bytes = f.read()
                        photo_data["image"] = base64.b64encode(image_bytes).decode('utf-8')
                    
                    photo_received.set()
                    client.remove_event_handler(handler)
                    
                except Exception as e:
                    photo_data["error"] = str(e)
                    photo_received.set()
                    client.remove_event_handler(handler)
            
            elif event.message.text and ("bulunamadı" in event.message.text.lower() or 
                                        "geçersiz" in event.message.text.lower() or
                                        "hatalı" in event.message.text.lower()):
                photo_data["error"] = event.message.text
                photo_received.set()
                client.remove_event_handler(handler)
        
        try:
            await asyncio.wait_for(photo_received.wait(), timeout=30)
        except asyncio.TimeoutError:
            photo_data["error"] = "Zaman aşımı: Vesika fotoğrafı alınamadı"
        
        return photo_data
        
    except Exception as e:
        return {"image": None, "error": str(e), "file_path": None}
        
    finally:
        await client.disconnect()

# -----------------------------------------------------------
# SULALE PRO FONKSİYONU
# -----------------------------------------------------------
async def sulale_pro_query(tc):
    """Sülale Pro sorgusu yapar"""
    results = {
        "status": "processing",
        "ana_tc": tc,
        "sorgu_zamani": datetime.now().isoformat(),
        "toplam_kisi": 0,
        "veriler": [],
        "hata": None
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Sülale verisini al
            print(f"🔄 Sülale API sorgulanıyor: {tc}")
            sulale_data = await fetch_api_data(session, SULALE_API, tc)
            
            if "error" in sulale_data:
                results["hata"] = f"Sülale API hatası: {sulale_data['error']}"
                results["status"] = "error"
                return results
            
            # 2. TC'leri çıkar
            tc_list = extract_tc_numbers(sulale_data)
            tc_list = [t for t in tc_list if t.isdigit() and len(t) == 11]
            
            if not tc_list:
                tc_list = [tc]
            
            print(f"📋 Bulunan TC'ler: {tc_list}")
            results["toplam_kisi"] = len(tc_list)
            
            # 3. Her TC için detaylı sorgu
            all_data = []
            for i, person_tc in enumerate(tc_list, 1):
                print(f"🔍 Kişi {i}/{len(tc_list)} sorgulanıyor: {person_tc}")
                
                person_result = {
                    "tc": person_tc,
                    "sira": i,
                    "adres": None,
                    "tcgsm": None,
                    "hata": None
                }
                
                # Adres sorgusu
                adres_data = await fetch_api_data(session, ADRES_API, person_tc)
                if "error" not in adres_data:
                    person_result["adres"] = clean_json_data(adres_data)
                else:
                    person_result["hata"] = f"Adres: {adres_data.get('error')}"
                
                await asyncio.sleep(0.5)  # Rate limiting
                
                # TCGSM sorgusu
                tcgsm_data = await fetch_api_data(session, TCGSM_API, person_tc)
                if "error" not in tcgsm_data:
                    person_result["tcgsm"] = clean_json_data(tcgsm_data)
                elif not person_result["hata"]:
                    person_result["hata"] = f"TCGSM: {tcgsm_data.get('error')}"
                
                all_data.append(person_result)
                await asyncio.sleep(0.5)  # Rate limiting
            
            results["veriler"] = all_data
            results["status"] = "success"
            
            # Ham sülale verisini de ekle (temizlenmiş)
            results["ham_sulale_verisi"] = clean_json_data(sulale_data)
            
        except Exception as e:
            results["hata"] = f"Sistem hatası: {str(e)}"
            results["status"] = "error"
    
    return results

def extract_tc_numbers(data):
    """Veriden TC numaralarını çıkar"""
    tc_list = []
    
    try:
        # JSON'u string'e çevir
        if isinstance(data, dict):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)
        
        # 11 haneli rakamları bul
        tc_matches = re.findall(r'\b\d{11}\b', data_str)
        tc_list.extend(tc_matches)
        
        # TC: formatını kontrol et
        tc_colon_matches = re.findall(r'TC[:\s]+(\d{11})', data_str, re.IGNORECASE)
        tc_list.extend(tc_colon_matches)
        
        # Benzersiz TC'ler
        tc_list = list(set(tc_list))
        
    except Exception as e:
        print(f"TC çıkarma hatası: {e}")
    
    return tc_list

# -----------------------------------------------------------
# TC PRO FONKSİYONU
# -----------------------------------------------------------
async def tc_pro_query(tc):
    """TC Pro sorgusu yapar"""
    results = {
        "status": "processing",
        "tc": tc,
        "sorgu_zamani": datetime.now().isoformat(),
        "veriler": {},
        "hata": None
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"🔍 TC Pro sorgulanıyor: {tc}")
            
            # Adres sorgusu
            adres_data = await fetch_api_data(session, ADRES_API, tc)
            if "error" not in adres_data:
                results["veriler"]["adres"] = clean_json_data(adres_data)
            else:
                results["hata"] = f"Adres: {adres_data.get('error')}"
            
            await asyncio.sleep(0.5)
            
            # TCGSM sorgusu
            tcgsm_data = await fetch_api_data(session, TCGSM_API, tc)
            if "error" not in tcgsm_data:
                results["veriler"]["tcgsm"] = clean_json_data(tcgsm_data)
            elif not results["hata"]:
                results["hata"] = f"TCGSM: {tcgsm_data.get('error')}"
            
            results["status"] = "success"
            
        except Exception as e:
            results["hata"] = f"Sistem hatası: {str(e)}"
            results["status"] = "error"
    
    return results

# -----------------------------------------------------------
# TELEGRAM GÖNDERME FONKSİYONU
# -----------------------------------------------------------
async def send_to_bot(command, address, details):
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.start()

    try:
        await client.send_message(BOT_USERNAME, command)
        await asyncio.sleep(1.5)

        await client.send_message(BOT_USERNAME, address)
        await asyncio.sleep(1.5)

        await client.send_message(BOT_USERNAME, details)
        await asyncio.sleep(1.5)

        return True, "İhbar başarıyla gönderildi"

    except Exception as e:
        return False, str(e)

    finally:
        await client.disconnect()

# -----------------------------------------------------------
# PARAMETRE BİRLEŞTİRİCİ
# -----------------------------------------------------------
def combine_params(key):
    values = request.args.getlist(key)
    if not values:
        return ""
    combined = " ".join(values)

    try:
        return combined.encode('latin1').decode('utf-8')
    except:
        return combined

# -----------------------------------------------------------
# ENDPOINT'LER
# -----------------------------------------------------------

# VESIKA SORGULAMA
@app.route('/vesika')
def vesika_sorgu():
    tc_no = request.args.get('tc')
    
    if not tc_no or not tc_no.isdigit() or len(tc_no) != 11:
        return jsonify({
            "status": "error", 
            "message": "Geçerli bir 11 haneli TC kimlik numarası giriniz"
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_vesika(tc_no))
        loop.close()
        
        if result.get("file_path") and os.path.exists(result["file_path"]):
            os.remove(result["file_path"])
        
        if result.get("error"):
            return jsonify({
                "status": "error",
                "message": result["error"],
                "tc": tc_no
            })
        
        if result.get("image"):
            return jsonify({
                "status": "success",
                "message": "Vesika başarıyla alındı",
                "tc": tc_no,
                "image_base64": result["image"],
                "image_format": "jpg",
                "size_bytes": len(base64.b64decode(result["image"]))
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Vesika fotoğrafı alınamadı",
                "tc": tc_no
            })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Sistem hatası: {str(e)}",
            "tc": tc_no
        })

# VESIKA İNDİRME
@app.route('/vesika_download')
def vesika_download():
    tc_no = request.args.get('tc')
    
    if not tc_no or not tc_no.isdigit() or len(tc_no) != 11:
        return jsonify({
            "status": "error", 
            "message": "Geçerli bir 11 haneli TC kimlik numarası giriniz"
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_vesika(tc_no))
        loop.close()
        
        if result.get("error"):
            return jsonify({
                "status": "error",
                "message": result["error"],
                "tc": tc_no
            })
        
        if result.get("file_path") and os.path.exists(result["file_path"]):
            if request.args.get('format') == 'base64':
                with open(result["file_path"], "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
                
                os.remove(result["file_path"])
                
                return jsonify({
                    "status": "success",
                    "message": "Vesika başarıyla alındı",
                    "tc": tc_no,
                    "image_base64": image_base64,
                    "image_format": "jpg"
                })
            else:
                from flask import send_file
                response = send_file(
                    result["file_path"],
                    mimetype='image/jpeg',
                    as_attachment=True,
                    download_name=f"vesika_{tc_no}.jpg"
                )
                
                @response.call_on_close
                def cleanup():
                    if os.path.exists(result["file_path"]):
                        os.remove(result["file_path"])
                
                return response
        else:
            return jsonify({
                "status": "error",
                "message": "Vesika fotoğrafı alınamadı",
                "tc": tc_no
            })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Sistem hatası: {str(e)}",
            "tc": tc_no
        })

# SULALE PRO ENDPOINT
@app.route('/sulalepro')
def sulale_pro():
    tc = request.args.get('tc')
    
    if not tc or not tc.isdigit() or len(tc) != 11:
        return jsonify({
            "status": "error",
            "message": "Geçerli bir 11 haneli TC kimlik numarası giriniz",
            "örnek": "/sulalepro?tc=12345678901"
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(sulale_pro_query(tc))
        loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Sistem hatası: {str(e)}",
            "tc": tc
        })

# TC PRO ENDPOINT
@app.route('/tcpro')
def tc_pro():
    tc = request.args.get('tc')
    
    if not tc or not tc.isdigit() or len(tc) != 11:
        return jsonify({
            "status": "error",
            "message": "Geçerli bir 11 haneli TC kimlik numarası giriniz",
            "örnek": "/tcpro?tc=12345678901"
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(tc_pro_query(tc))
        loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Sistem hatası: {str(e)}",
            "tc": tc
        })

# İHBAR ENDPOINT'LERİ
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

@app.route('/usomihbar')
def usom_ihbar():
    return handle_ihbar("/usomihbar")

@app.route('/egmihbar')
def egm_ihbar():
    return handle_ihbar("/egmihbar")

@app.route('/jandarmaihbar')
def jandarma_ihbar():
    return handle_ihbar("/jandarmaihbar")

# ANA SAYFA
@app.route('/')
def ana():
    return jsonify({
        "message": "NABI SYSTEM İHBAR API",
        "versiyon": "3.0",
        "endpoints": {
            "ihbar": {
                "/jandarmaihbar": "Jandarma ihbarı",
                "/egmihbar": "EGM ihbarı", 
                "/usomihbar": "USOM ihbarı"
            },
            "vesika": {
                "/vesika": "TC kimlik vesikası sorgu",
                "/vesika_download": "Vesika indirme"
            },
            "sorgu": {
                "/sulalepro": "Sülale detaylı sorgu",
                "/tcpro": "TC detaylı sorgu"
            }
        },
        "parametreler": {
            "ihbar": "?adres=Köy&yolu&mevkii&detay=Silah&sesleri&duyuluyor",
            "vesika": "?tc=12345678901",
            "sorgu": "?tc=12345678901"
        },
        "örnekler": [
            "/jandarmaihbar?adres=Ankara&detay=Şüpheli araç",
            "/vesika?tc=12345678901",
            "/sulalepro?tc=12345678901",
            "/tcpro?tc=12345678901"
        ]
    })

# UYGULAMA BAŞLATMA
if __name__ == '__main__':
    print("🚨 NABI SYSTEM API ÇALIŞIYOR...")
    print("📌 Kullanılabilir Endpoints:")
    print("   - /jandarmaihbar, /egmihbar, /usomihbar")
    print("   - /vesika, /vesika_download")
    print("   - /sulalepro, /tcpro")
    print(f"🔑 String Session Güncellendi: {SESSION_STR[:30]}...")
    app.run(host="0.0.0.0", port=5000, debug=True)
