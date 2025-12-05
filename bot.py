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
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# UTF-8
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)

# Telethon konfigürasyonu
API_ID = 17570480
API_HASH = "18c5be05094b146ef29b0cb6f6601f1f"
SESSION_STR = "1ApWapzMBu41F0unpfr3tr25gZZr-lnJLzLeMLxOtPQTcMD4lOR__E_yHYwVl46JDzyRIC6Q52BtZPxORAvvF4T6QOaC3T3CgSXlsQueOPelzja5lQ52V5875LzxLL-FShBrn5X2vQp-fX7gdtVNk7kn3osHIQ0HiRudVsI4hKsRuW1iwEd56zbjm2CzndtvOjUYUYBo5TTSIqt4JFF__uPplV8uCnllpvY61dMNtNIgomEj2jI7nfeDomm3WFT6-Od7iwMPt_NwduiBnWdzPIcpsYGXLO7z-GXKdTHsIEB_KAAHO_FM4ncF5TFXgAotL2rno7Vf0Ejfa4yRvM3YngwEXT9RDoTE="

# Botlar
BOT_USERNAME = "@KenevizihbarBot"
VESIKA_BOT = "@VesikaBot"

# API URL'LERİ
SULALE_API = "https://dosya.alwaysdata.net/api/sulale.php?tc="
ADRES_API = "https://dosya.alwaysdata.net/api/adres.php?tc="
TCGSM_API = "https://dosya.alwaysdata.net/api/tcgsm.php?tc="
AILE_API = "https://dosya.alwaysdata.net/api/aile.php?tc="

# IBAN API URL
IBAN_API_BASE = "https://hesapno.com/mod_iban_coz"

# -----------------------------------------------------------
# IBAN API SINIFI
# -----------------------------------------------------------
class IBANAPI:
    def __init__(self):
        self.base_url = IBAN_API_BASE
        
    def analyze_iban(self, iban_number):
        """IBAN numarasını analiz eder"""
        try:
            # IBAN doğrulama
            if not self.validate_iban(iban_number):
                return {"error": "Geçersiz IBAN formatı"}
            
            # Web sayfasına POST isteği gönder
            payload = {
                'iban': iban_number,
                'coz': 'Çözümle'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(self.base_url, data=payload, headers=headers)
            
            if response.status_code == 200:
                return self.parse_response(response.text, iban_number)
            else:
                return {"error": "API erişim hatası"}
                
        except Exception as e:
            return {"error": f"Sistem hatası: {str(e)}"}
    
    def validate_iban(self, iban):
        """IBAN formatını doğrular"""
        iban_clean = iban.replace(' ', '').upper()
        # TR ile başlamalı, 26 karakter olmalı
        if not re.match(r'^TR\d{24}$', iban_clean):
            return False
        return True
    
    def parse_response(self, html_content, iban):
        """HTML cevabını parse eder"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            "iban": iban,
            "banka_adi": "",
            "sube_kodu": "", 
            "hesap_no": "",
            "durum": "",
            "ulke": "Türkiye",
            "banka_kodu": ""
        }
        
        try:
            # Tablo içindeki verileri çek
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        key = cells[0].get_text().strip().lower()
                        value = cells[1].get_text().strip()
                        
                        if 'banka' in key:
                            result["banka_adi"] = value
                        elif 'şube' in key:
                            result["sube_kodu"] = value
                        elif 'hesap' in key:
                            result["hesap_no"] = value
                        elif 'durum' in key:
                            result["durum"] = value
            
            # Banka kodunu IBAN'dan çıkar
            if iban.startswith('TR'):
                result["banka_kodu"] = iban[4:6]
                
        except Exception as e:
            result["error"] = f"Parse hatası: {str(e)}"
        
        return result

# IBAN API nesnesi
iban_api = IBANAPI()

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
        "ana_tc": tc,
        "sorgu_zamani": datetime.now().isoformat(),
        "veriler": {}
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Sülale sorgusu
            print(f"🔄 Sülale API sorgulanıyor: {tc}")
            sulale_data = await fetch_api_data(session, SULALE_API, tc)
            results["veriler"]["sulale"] = clean_json_data(sulale_data)
            
            # 2. Adres sorgusu
            print(f"🏠 Adres API sorgulanıyor: {tc}")
            adres_data = await fetch_api_data(session, ADRES_API, tc)
            results["veriler"]["adres"] = clean_json_data(adres_data)
            
            # 3. TCGSM sorgusu
            print(f"📱 TCGSM API sorgulanıyor: {tc}")
            tcgsm_data = await fetch_api_data(session, TCGSM_API, tc)
            results["veriler"]["tcgsm"] = clean_json_data(tcgsm_data)
            
        except Exception as e:
            results["hata"] = f"Sistem hatası: {str(e)}"
    
    return results

# -----------------------------------------------------------
# AILE PRO FONKSİYONU
# -----------------------------------------------------------
async def aile_pro_query(tc):
    """Aile Pro sorgusu yapar"""
    results = {
        "ana_tc": tc,
        "sorgu_zamani": datetime.now().isoformat(),
        "veriler": {}
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. Aile sorgusu
            print(f"👨‍👩‍👧‍👦 Aile API sorgulanıyor: {tc}")
            aile_data = await fetch_api_data(session, AILE_API, tc)
            results["veriler"]["aile"] = clean_json_data(aile_data)
            
            # 2. Adres sorgusu
            print(f"🏠 Adres API sorgulanıyor: {tc}")
            adres_data = await fetch_api_data(session, ADRES_API, tc)
            results["veriler"]["adres"] = clean_json_data(adres_data)
            
            # 3. TCGSM sorgusu
            print(f"📱 TCGSM API sorgulanıyor: {tc}")
            tcgsm_data = await fetch_api_data(session, TCGSM_API, tc)
            results["veriler"]["tcgsm"] = clean_json_data(tcgsm_data)
            
        except Exception as e:
            results["hata"] = f"Sistem hatası: {str(e)}"
    
    return results

# -----------------------------------------------------------
# TC PRO FONKSİYONU
# -----------------------------------------------------------
async def tc_pro_query(tc):
    """TC Pro sorgusu yapar"""
    results = {
        "tc": tc,
        "sorgu_zamani": datetime.now().isoformat(),
        "veriler": {}
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"🔍 TC Pro sorgulanıyor: {tc}")
            
            # 1. Adres sorgusu
            print(f"🏠 Adres API sorgulanıyor: {tc}")
            adres_data = await fetch_api_data(session, ADRES_API, tc)
            results["veriler"]["adres"] = clean_json_data(adres_data)
            
            # 2. TCGSM sorgusu
            print(f"📱 TCGSM API sorgulanıyor: {tc}")
            tcgsm_data = await fetch_api_data(session, TCGSM_API, tc)
            results["veriler"]["tcgsm"] = clean_json_data(tcgsm_data)
            
        except Exception as e:
            results["hata"] = f"Sistem hatası: {str(e)}"
    
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
            "error": "Geçerli bir 11 haneli TC kimlik numarası giriniz"
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
                "error": result["error"],
                "tc": tc_no
            })
        
        if result.get("image"):
            return jsonify({
                "tc": tc_no,
                "image_base64": result["image"],
                "image_format": "jpg",
                "size_bytes": len(base64.b64decode(result["image"]))
            })
        else:
            return jsonify({
                "error": "Vesika fotoğrafı alınamadı",
                "tc": tc_no
            })
            
    except Exception as e:
        return jsonify({
            "error": f"Sistem hatası: {str(e)}",
            "tc": tc_no
        })

# VESIKA İNDİRME
@app.route('/vesika_download')
def vesika_download():
    tc_no = request.args.get('tc')
    
    if not tc_no or not tc_no.isdigit() or len(tc_no) != 11:
        return jsonify({
            "error": "Geçerli bir 11 haneli TC kimlik numarası giriniz"
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_vesika(tc_no))
        loop.close()
        
        if result.get("error"):
            return jsonify({
                "error": result["error"],
                "tc": tc_no
            })
        
        if result.get("file_path") and os.path.exists(result["file_path"]):
            if request.args.get('format') == 'base64':
                with open(result["file_path"], "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
                
                os.remove(result["file_path"])
                
                return jsonify({
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
                "error": "Vesika fotoğrafı alınamadı",
                "tc": tc_no
            })
            
    except Exception as e:
        return jsonify({
            "error": f"Sistem hatası: {str(e)}",
            "tc": tc_no
        })

# SULALE PRO ENDPOINT
@app.route('/sulalepro')
def sulale_pro():
    tc = request.args.get('tc')
    
    if not tc or not tc.isdigit() or len(tc) != 11:
        return jsonify({
            "error": "Geçerli bir 11 haneli TC kimlik numarası giriniz",
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
            "error": f"Sistem hatası: {str(e)}",
            "tc": tc
        })

# AILE PRO ENDPOINT
@app.route('/ailepro')
def aile_pro():
    tc = request.args.get('tc')
    
    if not tc or not tc.isdigit() or len(tc) != 11:
        return jsonify({
            "error": "Geçerli bir 11 haneli TC kimlik numarası giriniz",
            "örnek": "/ailepro?tc=12345678901"
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(aile_pro_query(tc))
        loop.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": f"Sistem hatası: {str(e)}",
            "tc": tc
        })

# TC PRO ENDPOINT
@app.route('/tcpro')
def tc_pro():
    tc = request.args.get('tc')
    
    if not tc or not tc.isdigit() or len(tc) != 11:
        return jsonify({
            "error": "Geçerli bir 11 haneli TC kimlik numarası giriniz",
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
            "error": f"Sistem hatası: {str(e)}",
            "tc": tc
        })

# -----------------------------------------------------------
# IBAN ENDPOINT'LERİ
# -----------------------------------------------------------
@app.route('/iban_sorgulama', methods=['GET', 'POST'])
def iban_sorgulama():
    """IBAN sorgulama endpoint'i"""
    if request.method == 'GET':
        iban = request.args.get('iban', '')
    else:
        iban = request.form.get('iban', '')
    
    if not iban:
        return jsonify({
            "error": "IBAN parametresi gerekli",
            "kullanim": "/iban_sorgulama?iban=TR330006100519786457841326"
        })
    
    result = iban_api.analyze_iban(iban)
    return jsonify(result)

@app.route('/iban_dogrulama', methods=['GET'])
def iban_dogrulama():
    """Sadece IBAN doğrulama"""
    iban = request.args.get('iban', '')
    
    if not iban:
        return jsonify({"error": "IBAN parametresi gerekli"})
    
    is_valid = iban_api.validate_iban(iban)
    return jsonify({
        "iban": iban,
        "gecerli": is_valid
    })

@app.route('/iban_banka_kodlari', methods=['GET'])
def banka_kodlari():
    """Banka kodları listesi"""
    banka_kodlari = {
        "10": "Türkiye Cumhuriyet Merkez Bankası",
        "12": "Türkiye Halk Bankası",
        "15": "Türkiye İş Bankası", 
        "30": "Türkiye Vakıflar Bankası",
        "32": "Türkiye Garanti Bankası",
        "46": "Akbank",
        "62": "Türkiye Halk Bankası",
        "67": "Yapı Kredi Bankası",
        "90": "Türkiye Emlak Bankası"
    }
    return jsonify(banka_kodlari)

# -----------------------------------------------------------
# İHBAR ENDPOINT'LERİ
# -----------------------------------------------------------
def handle_ihbar(command):
    adres = combine_params("adres")
    detay = combine_params("detay")

    if not adres or not detay:
        return jsonify({"error": "adres ve detay gerekli"})

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success, msg = loop.run_until_complete(send_to_bot(command, adres, detay))
    loop.close()

    if success:
        return jsonify({"message": "İhbar başarıyla gönderildi"})
    else:
        return jsonify({"error": msg})

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
                "/sulalepro": "Sülale + Adres + TCGSM sorgu",
                "/ailepro": "Aile + Adres + TCGSM sorgu",
                "/tcpro": "Adres + TCGSM sorgu"
            },
            "iban": {
                "/iban_sorgulama": "IBAN sorgulama",
                "/iban_dogrulama": "IBAN doğrulama",
                "/iban_banka_kodlari": "Banka kodları listesi"
            }
        },
        "parametreler": {
            "ihbar": "?adres=Ankara&detay=Şüpheli araç",
            "vesika": "?tc=12345678901",
            "sorgu": "?tc=12345678901",
            "iban": "?iban=TR330006100519786457841326"
        }
    })

# -----------------------------------------------------------
# UYGULAMA BAŞLATMA
# -----------------------------------------------------------
if __name__ == '__main__':
    print("🚨 NABI SYSTEM API ÇALIŞIYOR...")
    print("📌 Kullanılabilir Endpoints:")
    print("   - /jandarmaihbar, /egmihbar, /usomihbar")
    print("   - /vesika, /vesika_download")
    print("   - /sulalepro, /ailepro, /tcpro")
    print("   - /iban_sorgulama, /iban_dogrulama")
    print("📡 API URL'leri:")
    print(f"   - Sülale: {SULALE_API}")
    print(f"   - Aile: {AILE_API}")
    print(f"   - Adres: {ADRES_API}")
    print(f"   - TCGSM: {TCGSM_API}")
    app.run(host="0.0.0.0", port=5000, debug=True)
