import os
import re
import logging
import asyncio
import base64
import functools
import json
import urllib.parse
import time
import threading
from aiohttp import web
import requests as req

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
# Kanal ID — Render'dan CHANNEL_ID env orqali o'zgartiriladi.
# Test paytida:  CHANNEL_ID=@Kraken_mobile_test  (Render dashboard'ga qo'shasan)
# Testdan keyin: env'ni o'chirasan yoki @Kraken_mobile qilasan → asosiy kanalga qaytadi.
CHANNEL = os.environ.get('CHANNEL_ID', '@Kraken_mobile')
# G11.0: SINOV kanali — /richtest faqat shu yerga va admin lichkasiga yuboradi.
# ASOSIY KANALGA (CHANNEL) sinov xabari HECH QACHON KETMAYDI (foydalanuvchi:
# «hozir rasvo qiladi-ku… faqat lichkamga… test kanaliga yuborsin»).
TEST_CHANNEL = os.environ.get('TEST_CHANNEL_ID', '@Kraken_mobile_test')
# CHANNEL'dan username va link (a'zolik tugmalari uchun — test kanalga ham mos)
CHANNEL_USERNAME = CHANNEL.lstrip('@')
CHANNEL_LINK = f'https://t.me/{CHANNEL_USERNAME}'
SAYT_URL = 'https://krakenmobileshop.netlify.app/'
BOT_USERNAME = 'kraken_mobile_shop_bot'
SHEET_URL = os.environ.get('SHEET_URL', '')
ADMIN_USERNAME = 'Krakens_admin'

# Apps Script maxfiy kaliti. Mijoz telefon raqamlari (getParticipants) endi faqat
# shu kalit bilan beriladi — brauzerdan (saytdan) so'ralsa bo'sh qaytadi.
# Qiymat Render env'da va Apps Script Script Properties'da BIR XIL bo'lishi shart.
API_KEY = os.environ.get('API_KEY', '')

# ── ImageKit (saytdagi bilan bir xil — barqaror rasm hosting) ──
IK_PRIVATE_KEY = os.environ.get('IK_PRIVATE_KEY', 'private_uRjC2/psPBQPc5fAhmshbRw9K1o=')
IK_UPLOAD_URL = 'https://upload.imagekit.io/api/v1/files/upload'

_konkurs_cache = {'data': None, 'time': 0}
user_states = {}

# Admin rasm yuborganda albom (media group)ni yig'ish uchun bufer
# {media_group_id: {'file_ids': [...], 'task': asyncio_handle}}
_photo_groups = {}
# (_single_photo_lock olib tashlandi — E7: hech qayerda o'qilmasdi)

# ── ELON YUBORISH ─────────────────────────────────────────
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1058186533'))

# Premium emoji ID'lari (base emoji -> custom_emoji_id)
PREMIUM = {
    'google': ('📱', '5330169502279690330'),   # G logo (sarlavha)
    'k':      ('💡', '5330189963503887513'),   # K logo (kanal/bot)
    'money':  ('💰', '5375296873982604963'),   # pul qopcha (narx)
}

# Bot oxirgi yuborgan elon raqami (RAM'da; restartda Sheets'dan tiklanadi)
_last_sent = {'num': 0}

# ── G10.3 (2026-09-14): E'LON XOTIRASI — ulashish tez bo'lsin ──
# Muammo: har «Ulashish»da bot Sheets'dan e'lonni so'rardi. Apps Script 3–5 s,
# ba'zan 30–90 s (o'lchandi) → mijoz kutar, bot 15 s da taslim bo'lib eski
# havolali usulga tushardi.
# Yechim: bot ishga tushganda butun ro'yxatni BIR MARTA oladi; sayt (admin)
# har saqlashda o'zgargan e'lonni /elon_changed ga yuboradi; kuniga bir marta
# ehtiyot uchun qayta yuklanadi. Xotirada yo'q e'lon (yangi, hali kelmagan) —
# eski yo'l bilan Sheets'dan olinib xotiraga qo'shiladi.
# Foydalanuvchi: «har 10 daqiqada yangilash kerak emas, saqlash bosganda botga
# so'rov boraqolsin» — shunday qilindi.
_ELON_CACHE = {'by_num': {}, 'models': {}, 'series': [], 'turkumlar': [], 'time': 0.0, 'last_try': 0.0}
ELON_CACHE_MAX_AGE = 24 * 3600
_elon_cache_lock = threading.Lock()

CONDITION_TXT = {
    'new':     ("Yangi (Karobka)", "Новый (Коробка)"),
    'openbox': ("Openbox (Ochilgan)", "Openbox (Вскрыт)"),
    'used':    ("Ishlatilgan", "Б.у"),
}


async def blok(fn, *args, **kwargs):
    """Bloklaydigan (sinxron `requests`) funksiyani ALOHIDA IPDA bajaradi (E1).

    🔴 Nega kerak: bu funksiyalar async `webhook` ichidan to'g'ridan-to'g'ri
    chaqirilardi. Har `requests` so'rovi (a'zolik tekshiruvi, Sheets, Telegram)
    butun event loop'ni to'xtatardi — bir vaqtda 20 mijoz raqam bersa navbat
    hosil bo'lardi, Telegram javobni kutmay xabarni QAYTA yuborardi va ish ikki
    marta bajarilardi (QOIDALAR T1).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))


def elon_status(item):
    """E'lon holati — sayt bilan AYNAN bir xil qoida (sayt: 02-yordamchi.js elonStatus).

    'status' ustuni: waited | active | sold | deleted.
    Ustun bo'sh bo'lsa (eski e'lonlar) — orqaga moslik:
      narx aniq 0  -> sold
      specId yo'q  -> waited (bot yaratgan chala e'lon)
      aks holda    -> active
    Ilgari bot faqat "narx=0" ni bilardi: sayt e'lonni 'sold' deb belgilasa ham
    kanalga narxi bilan chiqib ketardi (REJA B5).
    """
    if not item:
        return 'active'
    s = str(item.get('status', '') or '').strip().lower()
    if s:
        return s
    try:
        p = float(str(item.get('price', '')).strip())
    except (ValueError, TypeError):
        p = None
    if p == 0:
        return 'sold'
    if not str(item.get('specId', '') or '').strip():
        return 'waited'
    return 'active'


def is_sold(item):
    return elon_status(item) == 'sold'


def clean_color(color):
    """'Obsidian Black (Qora)' -> 'Obsidian Black' (qavsni olib tashlaydi)."""
    if not color:
        return ''
    import re
    return re.sub(r'\s*\([^)]*\)', '', str(color)).strip()


def holati_matni(cond, cycle):
    """condition + cycle bo'yicha (uz_qator, ru_qator, emoji) qaytaradi."""
    sikl_uz = f" ({cycle}tsikl)" if cycle else ""
    sikl_ru = f" ({cycle}цикл)" if cycle else ""
    if cond == 'new':
        return ("Yangi ochilmagan!", "Новое запечатанное!", "📦")
    if cond == 'openbox':
        return (f"Yengi Openbox!{sikl_uz}", f"Новое Опенбокс!{sikl_ru}", "📦")
    # used
    return (f"Ishlatilgan{sikl_uz}", f"Б.у{sikl_ru}", "🔸")

def send_msg(chat_id, text, keyboard=None):
    """Oddiy xabar. parse_mode = HTML (E5).

    Ilgari Markdown edi: sovg'a nomida yoki username'da `_` yoki `*` bo'lsa
    Telegram butun xabarni RAD ETARDI va mijozga hech narsa kelmasdi.
    HTML'da faqat `<`, `>`, `&` xavfli — ular html_escape bilan yopiladi.
    """
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        req.post(f'{TG_API}/sendMessage', json=payload, timeout=8)
    except Exception as e:
        logger.error(f'sendMessage: {e}')


# /start javobi. E7: animatsiya file_id kodga qotirilgan — u o'chib ketsa
# (yoki boshqa botga ko'chirilsa) mijoz HECH NARSA olmasdi. Endi xato bo'lsa
# oddiy matn + tugma ketadi: mijoz baribir saytga kira oladi.
START_CAPTION = (
    "🇺🇿 <b>Barcha aktual smartfonlarimiz saytimizga joylandi</b>\n"
    "🇷🇺 <b>Все актуальные смартфоны уже на нашем сайте</b>\n\n"
    "Kirish uchun bosing / Нажмите, чтобы перейти 👇"
)
START_ANIM = 'CgACAgIAAxkBAAMvaf3qQRiu8Kk4qBQZdISLTSIIDJYAAsGZAAJG3OhLX3fB57eReYE7BA'
START_KB = {"inline_keyboard": [[{
    "text": "🛍 Saytga kirish / Перейти на сайт",
    "web_app": {"url": SAYT_URL}
}]]}


def send_start(chat_id):
    try:
        r = req.post(f'{TG_API}/sendAnimation', json={
            'chat_id': chat_id,
            'animation': START_ANIM,
            'caption': START_CAPTION,
            'parse_mode': 'HTML',
            'reply_markup': START_KB,
        }, timeout=10)
        if r.status_code == 200 and r.json().get('ok'):
            return
        logger.error(f'sendAnimation: {r.text[:200]}')
    except Exception as e:
        logger.error(f'sendAnimation: {e}')
    send_msg(chat_id, START_CAPTION, START_KB)   # zaxira: animatsiyasiz


# ══════════════════════════════════════════════════════════════════════════
#  BUGUN6 §2 (2026-09-23): KANAL «XUSH KELIBSIZ» — ephemeral xabar (Bot API 10.2 / 10.3)
#  Odam kanalga qo'shilganda (`chat_member` yangilanishi) bot unga KANAL ICHIDA faqat o'ziga
#  ko'rinadigan xabar yuboradi («Only visible to you»): rasm tepada, ostida 2 tilda matn, «Saytga kirish».
#  Foydalanuvchi: «manabuni ishlatish kerak — kanalga kirishi bilan sayt chiqadi».
#  · Faqat XUSH_KANALLAR — hozir faqat TEST kanal. Asosiy kanalga — foydalanuvchi aytganda (ro'yxatga CHANNEL).
#  · Rasm — shu papkadagi `kanal_xush_kelibsiz.png` (foydalanuvchi skrinshoti, faqat TEST uchun). Almashtirish:
#    faylni SHU NOM bilan almashtirib GitHub'ga → Render «Manual Deploy». Birinchi yuborishda yuklanadi, keyin
#    Telegram'dagi file_id qayta ishlatiladi. Eski skeleton GIF — YO'Q (foydalanuvchi).
#  · Tugma — `url` (t.me/<bot>?startapp): `web_app` tugma FAQAT bot bilan shaxsiy chatda ishlaydi (Bot API).
#    «Kerakli telefon kelsa xabar bering» tugmasi — YO'Q (foydalanuvchi: «endi kirgan mijoz uchun g'alati»).
#  · 10.3: parametr `ephemeral_message_parameters.receiver_user_id` (10.2 dagi eski ko'rinish almashtirilgan).
#    Kanalda botga «welcome messages» ruxsati kerak bo'lishi mumkin (10.3 `can_send_welcome_messages`).
#  · Natija adminga: xato — Telegram javobi bilan (bir xil xato 10 daqiqada 1 marta); ishga tushgandan keyingi
#    birinchi muvaffaqiyat — bir marta. 🔴 Telegram ephemeral'ni qabul qilmay ODDIY post qilsa (hammaga
#    ko'rinsa) — post darhol o'chiriladi va xush kelibsiz to'xtaydi (keyingi deploy'gacha).
# ══════════════════════════════════════════════════════════════════════════
XUSH_KANALLAR = (TEST_CHANNEL,)
XUSH_RASM = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kanal_xush_kelibsiz.png')
XUSH_MATN = (
    "🇺🇿 <b>Xush kelibsiz! Biz barcha smartfonlarimizni ushbu saytga joyladik. "
    "Kanaldan ko'ra qulayroq, albatta kirib ko'ring.</b>\n\n"
    "🇷🇺 <b>Добро пожаловать! Мы разместили все наши смартфоны на этом сайте. "
    "Это удобнее, чем канал — обязательно загляните.</b>"
)
XUSH_KB = {"inline_keyboard": [[{
    "text": START_KB["inline_keyboard"][0][0]["text"],   # /start dagi tugma bilan bir xil matn
    "url": f"https://t.me/{BOT_USERNAME}?startapp=home",  # kanal postlaridagi «Saytni ochish» bilan bir xil yo'l
}]]}
# `chat_member` sukut bo'yicha KELMAYDI — setWebhook'da aniq aytilishi shart. Qolganlari — ilgari sukut bo'yicha
# kelayotgan asosiy turlar (bot hozir faqat message, callback_query va chat_member'ni o'qiydi).
ALLOWED_UPDATES = ['message', 'edited_message', 'channel_post', 'edited_channel_post', 'callback_query',
                   'inline_query', 'chosen_inline_result', 'my_chat_member', 'chat_member', 'chat_join_request']
_xush = {'file_id': '', 'yuborilgan': {}, 'xato_vaqt': {}, 'ishladi': False, 'toxtatildi': False}
_xush_lock = threading.Lock()


def _kanal_mos(chat, kanal):
    """Update'dagi chat shu kanalmi — '@username' (katta-kichik harf farqsiz) yoki raqamli id bo'yicha."""
    k = str(kanal or '').strip()
    if not k or not isinstance(chat, dict):
        return False
    if k.startswith('@'):
        return ('@' + str(chat.get('username') or '')).lower() == k.lower()
    return str(chat.get('id', '')) == k


def _azo(m):
    m = m or {}
    s = m.get('status')
    return s in ('member', 'administrator', 'creator') or (s == 'restricted' and bool(m.get('is_member')))


def xush_kimga(cm):
    """`chat_member` yangilanishi → xush kelibsiz kimga (user id) yoki None.

    Faqat XUSH_KANALLAR; faqat YANGI qo'shilgan (a'zo emas → oddiy a'zo); bot emas. Chiqib ketish, admin qilib
    tayinlash, huquq o'zgarishi — xush kelibsiz emas."""
    if not isinstance(cm, dict) or not any(_kanal_mos(cm.get('chat'), k) for k in XUSH_KANALLAR):
        return None
    yangi = cm.get('new_chat_member') or {}
    user = yangi.get('user') or {}
    if user.get('is_bot') or not user.get('id'):
        return None
    if _azo(cm.get('old_chat_member')) or yangi.get('status') not in ('member', 'restricted') or not _azo(yangi):
        return None
    return user['id']


def xush_yubor(chat_id, uid):
    """Kanal ichida faqat `uid` ga ko'rinadigan rasm + matn + tugma. (True, '') yoki (False, xato matni)."""
    maydon = {
        'chat_id': chat_id,
        'caption': XUSH_MATN,
        'parse_mode': 'HTML',
        'reply_markup': XUSH_KB,
        'ephemeral_message_parameters': {'receiver_user_id': uid},
    }
    try:
        if _xush['file_id']:
            j = req.post(f'{TG_API}/sendPhoto', json=dict(maydon, photo=_xush['file_id']), timeout=30).json()
        else:
            forma = {k: (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in maydon.items()}
            with open(XUSH_RASM, 'rb') as f:
                j = req.post(f'{TG_API}/sendPhoto', data=forma,
                             files={'photo': ('kanal_xush_kelibsiz.png', f, 'image/png')}, timeout=60).json()
    except Exception as ex:
        return False, f'tarmoq: {ex}'
    if not j.get('ok'):
        _xush['file_id'] = ''   # file_id eskirgan bo'lishi mumkin — keyingi safar rasm qayta yuklanadi
        return False, str(j.get('description') or j)
    res = j.get('result') or {}
    if res.get('message_id') and not res.get('receiver_user'):
        # 🔴 Ephemeral bo'lmay chiqdi — kanalda HAMMAGA ko'rinadi. Darhol o'chiriladi, keyingilari to'xtaydi.
        delete_msg(chat_id, res['message_id'])
        _xush['toxtatildi'] = True
        return False, ("Telegram xabarni «faqat o'ziga» emas, ODDIY post qilib yubordi — post darhol o'chirildi, "
                       "xush kelibsiz to'xtatildi (keyingi deploy'gacha)")
    rasmlar = res.get('photo') or []
    if rasmlar and rasmlar[-1].get('file_id'):
        _xush['file_id'] = rasmlar[-1]['file_id']
    return True, ''


def kanal_xush_kelibsiz(cm):
    """`chat_member` → yangi a'zoga xush kelibsiz (fonda, `blok` bilan). Natija: 'yuborildi' | 'xato' | ''."""
    uid = xush_kimga(cm)
    if not uid or _xush['toxtatildi']:
        return ''
    chat = cm.get('chat') or {}
    hozir = time.time()
    with _xush_lock:
        # bir odam chiqib-kirib tursa — soatiga bir marta
        if hozir - _xush['yuborilgan'].get((chat.get('id'), uid), 0) < 3600:
            return ''
        _xush['yuborilgan'][(chat.get('id'), uid)] = hozir
        if len(_xush['yuborilgan']) > 5000:
            _xush['yuborilgan'] = {k: t for k, t in _xush['yuborilgan'].items() if hozir - t < 3600}
    ok, xato = xush_yubor(chat.get('id'), uid)
    kanal = html_escape('@' + chat['username'] if chat.get('username') else str(chat.get('id', '')))
    if ok:
        logger.info(f'xush kelibsiz: {uid} -> {kanal}')
        if not _xush['ishladi']:
            _xush['ishladi'] = True
            ism = html_escape(((cm.get('new_chat_member') or {}).get('user') or {}).get('first_name', '') or str(uid))
            send_msg(ADMIN_ID, f"✅ Kanal xush kelibsiz ishladi: <b>{ism}</b> {kanal} ga qo'shildi — unga "
                               f"«faqat o'ziga ko'rinadigan» xabar ketdi.")
        return 'yuborildi'
    logger.error(f'xush kelibsiz: {xato}')
    if hozir - _xush['xato_vaqt'].get(xato, 0) >= 600:
        _xush['xato_vaqt'][xato] = hozir
        send_msg(ADMIN_ID, f"⚠️ Kanal xush kelibsiz yuborilmadi ({kanal}):\n<code>{html_escape(xato)}</code>")
    return 'xato'


def get_products():
    """Sheets'dan barcha elon va modellarni oladi (action'siz so'rov)."""
    if not SHEET_URL:
        return None, None
    try:
        r = req.get(f"{SHEET_URL}?callback=d", timeout=15)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        # G12: seriyalar ham keshda — `mos` kodlarini (p9s, phone) nomga aylantirish uchun
        if isinstance(data.get('series'), list):
            _ELON_CACHE['series'] = data['series']
        if isinstance(data.get('turkumlar'), list):      # G12 daraxt: turkum → bo'lim
            _ELON_CACHE['turkumlar'] = data['turkumlar']
        return data.get('listings', []), data.get('models', [])
    except Exception as e:
        logger.error(f'get_products: {e}')
        return None, None


def elon_cache_load():
    """Sheets'dan butun ro'yxatni olib xotiraga yozadi. True — muvaffaqiyat."""
    _ELON_CACHE['last_try'] = time.time()
    listings, models = get_products()
    if listings is None:
        return False
    by_num = {}
    for it in listings:
        try:
            by_num[str(int(float(it.get('num', 0) or 0)))] = it
        except Exception:
            pass
    md = {}
    for m in (models or []):
        if isinstance(m, dict) and m.get('id'):
            md[str(m['id'])] = m
    with _elon_cache_lock:
        _ELON_CACHE['by_num'] = by_num
        _ELON_CACHE['models'] = md
        _ELON_CACHE['time'] = time.time()
    logger.info(f'elon_cache: {len(by_num)} elon, {len(md)} model')
    return True


def elon_cache_get(num):
    """(elon, models_by_id) — avval xotiradan; yo'q bo'lsa Sheets'dan olib xotiraga qo'shadi."""
    c = _ELON_CACHE
    # Hali umuman yuklanmagan (ishga tushganda Sheets javob bermagan) — bir urinish,
    # lekin ketma-ket emas: 60 s da bir marta
    if not c['time'] and time.time() - c['last_try'] > 60:
        elon_cache_load()
    with _elon_cache_lock:
        e = c['by_num'].get(str(num))
        models = c['models']
    if e is not None and models:
        return e, models
    elon, md = fetch_elon_by_num(num)          # sekin yo'l — faqat xotirada yo'q bo'lsa
    if elon:
        with _elon_cache_lock:
            c['by_num'][str(num)] = elon
            if md and not c['models']:
                c['models'] = dict(md)
    return elon, (models or md or {})


def elon_cache_put(elon):
    """Sayt (admin) saqlagan e'lon — xotiradagi nusxa almashtiriladi."""
    with _elon_cache_lock:
        _ELON_CACHE['by_num'][str(elon['num'])] = elon


async def elon_cache_loop():
    """Kuniga bir marta ehtiyot uchun qayta yuklash (sayt xabari yetib kelmagan bo'lsa)."""
    while True:
        await asyncio.sleep(ELON_CACHE_MAX_AGE)
        try:
            await blok(elon_cache_load)
        except Exception as e:
            logger.error(f'elon_cache_loop: {e}')


def get_stat(days=1):
    """F1: Apps Script'dan do'kon hisobotini oladi.

    Hisob SHEETS TOMONIDA qilinadi (AppScript.gs: getStat) — Korishlar varag'ida
    minglab qator bo'lishi mumkin, ularni Render'ga tashish bekorga.
    Savdo ma'lumoti bo'lgani uchun so'rov API_KEY bilan yuboriladi.
    """
    if not SHEET_URL:
        return None
    if not API_KEY:
        return {'ok': False, 'msg': 'key_yoq'}
    try:
        url = f"{SHEET_URL}?action=stat&days={int(days)}&key={urllib.parse.quote(API_KEY)}"
        r = req.get(url, timeout=25)
        return r.json()
    except Exception as e:
        logger.error(f'get_stat: {e}')
        return None


def build_stat_text(s):
    """Hisobotni admin o'qiydigan xabarga aylantiradi (HTML)."""
    kun = s.get('days', 1)
    davr = 'Oxirgi 24 soat' if kun == 1 else f'Oxirgi {kun} kun'
    q = []
    q.append(f"📊 <b>{davr}</b>")
    q.append('')
    q.append(f"👥 Yangi mijoz: <b>{s.get('yangiMijoz', 0)}</b>")
    q.append(f"🚪 Saytga kirish: <b>{s.get('kirish', 0)}</b>  (turli odam: {s.get('unikalMijoz', 0)})")
    q.append(f"👁 E'lon ochilgan: <b>{s.get('korish', 0)}</b>")
    q.append(f"🛒 Savatga qo'shilgan: <b>{s.get('savat', 0)}</b>")
    q.append(f"💬 Aloqa bosilgan: <b>{s.get('aloqa', 0)}</b>")
    q.append(f"🔗 Ulashilgan: <b>{s.get('ulashish', 0)}</b>")

    top = s.get('topElon') or []
    if top:
        q.append('')
        q.append('🔥 <b>Eng ko\'p ochilgan</b>')
        for it in top:
            q.append(f"   {html_escape(it.get('nom', ''))} — {it.get('soni', 0)}")

    qid = s.get('topQidiruv') or []
    if qid:
        q.append('')
        q.append('🔍 <b>Eng ko\'p qidirilgan</b>')
        for it in qid:
            q.append(f"   {html_escape(it.get('nom', ''))} — {it.get('soni', 0)}")

    q.append('')
    q.append('📦 <b>Hozirgi holat</b>')
    q.append(f"   Sotuvda: <b>{s.get('faolElon', 0)}</b>   ·   Sotilgan: {s.get('sotilgan', 0)}")
    if s.get('chala', 0):
        q.append(f"   To'ldirilmagan (chala): <b>{s.get('chala', 0)}</b>")
    q.append(f"   Davrda qo'shilgan: {s.get('yangiElon', 0)}")
    q.append(f"   Jami mijoz: {s.get('jamiMijoz', 0)}")
    return '\n'.join(q)


async def handle_stat(chat_id, text):
    """/stat  yoki  /stat 7 — do'kon hisoboti (faqat admin).

    🔴 Fonda bajariladi (QOIDALAR T1): Sheets hisobi bir necha soniya olishi
    mumkin, webhook esa Telegram'ga DARROV 200 qaytarishi shart. Aks holda
    Telegram buyruqni qayta yuboradi va hisobot ikki marta keladi.
    """
    parts = text.split()
    try:
        days = int(parts[1]) if len(parts) > 1 else 1
    except ValueError:
        days = 1
    if days < 1:
        days = 1

    s = await blok(get_stat, days)
    if not s:
        await blok(send_msg, chat_id, "❌ Sheets'dan hisobot olib bo'lmadi. SHEET_URL'ni tekshiring.")
        return
    if not s.get('ok'):
        if s.get('msg') == 'key_yoq':
            await blok(send_msg, chat_id,
                       "❌ API_KEY qo'yilmagan. Render → Environment → API_KEY, "
                       "va Apps Script → Project Settings → Script Properties → API_KEY. "
                       "Ikkalasi BIR XIL bo'lishi kerak.")
        else:
            await blok(send_msg, chat_id,
                       "❌ Apps Script kalitni qabul qilmadi. Render'dagi API_KEY bilan "
                       "Script Properties'dagi API_KEY bir xilmi?")
        return
    await blok(send_msg, chat_id, build_stat_text(s))


# ══════════════════════════════════════════════════════════════════════
#  G12 — BREND va MOS QURILMA (sayt: 02-yordamchi.js bilan bir xil qoida)
#  Modellar varag'ida `brand` va `mos` ustunlari. `mos` — vergul bilan kodlar:
#  p10 (model) · p10s (seriya) · phone (bo'lim, kelajakdagilar ham). Sayt va bot
#  bir xil o'qishi shart — aks holda saytda «mos», postda «mos emas» chiqadi.
# ══════════════════════════════════════════════════════════════════════
MOS_TYPES = ('phone', 'accessory', 'case', 'part', 'camera')


def _type_norm(t):
    t = str(t or '').strip().lower()
    if t in ('smartfon', 'phone', 'telefon'):
        return 'phone'
    if t in ('camera', 'kamera'):
        return 'camera'
    if t in ('aksessuar', 'accessory', 'charger', 'anker', 'google'):
        return 'accessory'
    if t in ('gilof', "g'ilof", 'case', 'chexol', 'чехол'):
        return 'case'
    if t in ('zapchast', 'part', 'batareyka', 'battery', 'запчасть'):
        return 'part'
    return ''


def ser_type(ser):
    """Seriya turi — G12 daraxt: avval `turkum` (Turkumlar varag'i → type), bo'lmasa Sheets `type`
    ustuni (sayt serType ning qisqasi)."""
    tk = str((ser or {}).get('turkum', '') or '').strip().lower()
    if tk:
        for t in _ELON_CACHE.get('turkumlar') or []:
            if str(t.get('key', '')).strip().lower() == tk:
                tt = _type_norm(t.get('type'))
                if tt:
                    return tt
                break
    t = str((ser or {}).get('type', '') or '').strip().lower()
    if t in ('smartfon', 'phone', 'telefon'):
        return 'phone'
    if t in ('aksessuar', 'accessory', 'charger', 'anker', 'google'):
        return 'accessory'
    if t in ('gilof', "g'ilof", 'case', 'chexol', 'чехол'):
        return 'case'
    if t in ('zapchast', 'part', 'batareyka', 'battery', 'запчасть'):
        return 'part'
    if t in ('camera', 'kamera'):
        return 'camera'
    return 'phone'


def parse_mos(v):
    """`mos` katagi → kodlar ro'yxati (vergul/nuqtali vergul yoki JSON)."""
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v if v is not None else '').strip()
    if not s:
        return []
    if s.startswith('['):
        try:
            a = json.loads(s)
            if isinstance(a, list):
                return [str(x).strip() for x in a if str(x).strip()]
        except Exception:
            pass
    return [x.strip() for x in re.split(r'[,;]+', s) if x.strip()]


def _mos_kind(k, models_by_id, series):
    if k.lower() in MOS_TYPES:
        return 'type'
    if any(str(x.get('key')) == k for x in series):
        return 'series'
    if k in models_by_id:
        return 'model'
    return '?'


def mos_expand(keys, models_by_id, series=None):
    """Kodlar → mos model id'lari to'plami (sayt mosExpand bilan bir xil)."""
    series = _ELON_CACHE['series'] if series is None else series
    out = set()
    for k in parse_mos(keys):
        kind = _mos_kind(k, models_by_id, series)
        if kind == 'type':
            for mid, m in models_by_id.items():
                ser = next((x for x in series if str(x.get('key')) == str(m.get('series'))), None)
                if ser and ser_type(ser) == k.lower():
                    out.add(str(mid))
        elif kind == 'series':
            for mid, m in models_by_id.items():
                if str(m.get('series')) == k:
                    out.add(str(mid))
        elif kind == 'model':
            out.add(k)
    return out


def _mos_short_names(names):
    """«Google Pixel 10», «Google Pixel 10 Pro» → «Pixel 10 / 10 Pro» (sayt _mosShortNames)."""
    words = [str(n or '').split() for n in names]
    words = [w for w in words if w]
    if not words:
        return ''
    if len(words) == 1:
        w = words[0]
        return ' '.join(w[1:] if len(w) > 2 else w)
    common = 0
    while all(len(w) > common + 1 and w[common].lower() == words[0][common].lower() for w in words):
        common += 1
    first = ' '.join(words[0][1:] if common > 1 else words[0])
    rest = [' '.join(w[common:]) for w in words[1:]]
    return ' / '.join([first] + [r for r in rest if r])


def mos_label(keys, models_by_id, series=None, lang='uz'):
    """Odam o'qiydigan matn: «Barcha telefonlar», «Pixel 9 Seriyasi», «Pixel 10 / 10 Pro»."""
    series = _ELON_CACHE['series'] if series is None else series
    TYPE_LBL = {
        'phone': ('Barcha telefonlar', 'Все телефоны'),
        'camera': ('Barcha kameralar', 'Все камеры'),
        'accessory': ('Barcha aksessuarlar', 'Все аксессуары'),
        'case': ("Barcha g'iloflar", 'Все чехлы'),
        'part': ('Barcha zapchastlar', 'Все запчасти'),
    }
    parts, model_names, ser_labels = [], [], []
    for k in parse_mos(keys):
        kind = _mos_kind(k, models_by_id, series)
        if kind == 'type':
            parts.append(TYPE_LBL[k.lower()][0 if lang == 'uz' else 1])
        elif kind == 'series':
            ser = next(x for x in series if str(x.get('key')) == k)
            ser_labels.append(str((ser.get('labelUz') if lang == 'uz' else (ser.get('labelRu') or ser.get('labelUz'))) or k))
        elif kind == 'model':
            m = models_by_id[k]
            model_names.append(str((m.get('nameUz') if lang == 'uz' else (m.get('nameRu') or m.get('nameUz'))) or k))
    if ser_labels:
        parts.append(_mos_series_range(ser_labels, lang))
    if model_names:
        parts.append(_mos_short_names(model_names))
    return ', '.join(parts)


def _mos_series_range(labels, lang='uz'):
    """«Pixel 6 Seriyasi … Pixel 9 Seriyasi» → «Pixel 6–9 seriyalari» (ketma-ket), aks holda
    «Pixel 6, 7, 9 seriyalari». Raqam yoki umumiy nom topilmasa — oddiy ro'yxat. Sayt _mosSeriesRange bilan bir xil."""
    if len(labels) == 1:
        return labels[0]
    parsed = []
    for lbl in labels:
        m = re.match(r'^\s*(?:seriya|серия|series)?\s*(.*?)\s*(\d+)\s*(?:seriyasi|seriya|серия|series)?\s*$', str(lbl), re.I)
        parsed.append((m.group(1).strip(), int(m.group(2))) if m else None)
    if any(p is None for p in parsed) or len({p[0].lower() for p in parsed}) != 1:
        return ', '.join(labels)
    nums = sorted({p[1] for p in parsed})
    consecutive = all(i == 0 or n == nums[i - 1] + 1 for i, n in enumerate(nums))
    raqam = f'{nums[0]}–{nums[-1]}' if (consecutive and len(nums) > 2) else ', '.join(str(n) for n in nums)
    pre = parsed[0][0]
    return f'{pre} {raqam} seriyalari' if lang == 'uz' else f'{pre} {raqam} серии'


def brendsizmi(b):
    """«NoName» brendi nomga qo'shilmaydi (sayt brendsizmi)."""
    return str(b or '').strip().lower() in ('noname', 'no name', 'no-name', 'brendsiz', 'без бренда', '-')


def model_brand(model):
    """G12 daraxt: brend modelda bo'lmasa — lineykasidan (Seriyalar `brand`)."""
    b = str((model or {}).get('brand') or '').strip()
    if b or not model:
        return b
    for s in _ELON_CACHE.get('series') or []:
        if str(s.get('key', '')) == str(model.get('series', '')):
            return str(s.get('brand') or '').strip()
    return ''


def model_display_name(model, lang='uz'):
    """Model nomi brend bilan; nom brenddan boshlansa ikki marta chiqmaydi (sayt modelDisplayName)."""
    if not model:
        return ''
    name = str((model.get('nameUz') if lang == 'uz' else (model.get('nameRu') or model.get('nameUz'))) or model.get('name') or '').strip()
    brand = model_brand(model)
    if brand and not brendsizmi(brand) and not name.lower().startswith(brand.lower()):
        return f'{brand} {name}'
    return name


def elon_nomi(elon, model, lang='uz'):
    """G12 (2026-09-15): e'lonning O'Z nomi (Elonlar nameUz/nameRu) bo'lsa shu — admin
    «Pixel 8 (GrapheneOS)» deb o'zgartira oladi; bo'sh bo'lsa model nomi. Brend prefiksi
    model_display_name qoidasi bilan. Sayt: elonNomi."""
    e = elon or {}
    own = str((e.get('nameUz') if lang == 'uz' else (e.get('nameRu') or e.get('nameUz'))) or e.get('name') or '').strip()
    if not own:
        return model_display_name(model, lang)
    brand = model_brand(model)
    if brand and not brendsizmi(brand) and not own.lower().startswith(brand.lower()):
        return f'{brand} {own}'
    return own


def mos_line(model, models_by_id, lang='uz'):
    """«Mos: …» qatori — faqat modelda `mos` bo'lsa (aksessuar/g'ilof/zapchast)."""
    if not model or not parse_mos(model.get('mos')):
        return ''
    return ('Mos: ' if lang == 'uz' else 'Подходит: ') + mos_label(model.get('mos'), models_by_id, None, lang)


def izoh_matni(item, lang='uz'):
    """G12 K2: e'lon izohi («ekran singan», «MagSafe, stand») — ru bo'sh bo'lsa uz (sayt elonIzoh bilan bir xil)."""
    uz = str((item or {}).get('izoh') or '').strip()
    ru = str((item or {}).get('izohRu') or '').strip()
    return ru if (lang == 'ru' and ru) else uz


def build_elon(item, models_by_id):
    """Bitta elon uchun (matn, entities) qaytaradi. entities premium emoji uchun."""
    num = int(float(item.get('num', 0) or 0))
    name_uz = item.get('nameUz', '') or item.get('name', '')
    storage = item.get('storage', '')
    price = str(item.get('price', '')).replace('.0', '')
    old = str(item.get('oldPrice', '')).replace('.0', '')
    cond = item.get('condition', 'new')
    cycle = str(item.get('cycle', '') or '').replace('.0', '')
    color_uz = item.get('color', '')
    spec_id = item.get('specId', '')

    model = models_by_id.get(spec_id, {})
    spec_uz = model.get('specUz', '') or ''
    spec_ru = model.get('specRu', '') or ''
    # G12: nom brend bilan (modeldan); e'londagi nom bo'lsa — o'sha, brend oldiga
    brand = str(model.get('brand') or '').strip()
    if brand and not str(name_uz).lower().startswith(brand.lower()):
        name_uz = f'{brand} {name_uz}'.strip()
    mos_txt = mos_line(model, models_by_id, 'uz')
    izoh_txt = izoh_matni(item, 'uz')   # G12 K2

    cond_uz, cond_ru, cond_emoji = holati_matni(cond, cycle)

    # (g_base/k_base/m_base o'zgaruvchilari olib tashlandi — add_prem() emoji'ni
    #  PREMIUM dan o'zi oladi, ular hech qayerda ishlatilmasdi)

    # Matnni qism-qism yig'amiz, premium pozitsiyalarini belgilaymiz
    parts = []
    prem = []  # (custom_emoji_id, char_offset, base_emoji)
    quote = None  # (start_offset, length) - texnik xar. uchun blockquote
    fmt = []  # (type, start_offset, length) - bold/strikethrough

    def add(s):
        parts.append(s)

    def add_prem(key):
        base, eid = PREMIUM[key]
        prem.append((eid, _utf16len(''.join(parts)), base))
        parts.append(base)

    def add_fmt(s, ftype):
        start = _utf16len(''.join(parts))
        parts.append(s)
        fmt.append((ftype, start, _utf16len(s)))

    color_clean = clean_color(color_uz)

    # ── Sarlavha: G logo + BOLD nom (xotira) + rang ──
    add_prem('google'); add(" ")
    title = f"{name_uz} ({storage})"
    add_fmt(title, 'bold')
    if color_clean:
        add(f" {color_clean}")
    add("\n")
    add(f"#phone #{num}\n")
    if mos_txt:
        add(f"🔗 {mos_txt}\n")
    if izoh_txt:
        add(f"📝 {izoh_txt}\n")
    add("\n")

    # ── Texnik xarakteristika (collapsed blockquote) ──
    q_start = _utf16len(''.join(parts))
    add("Texnik xarakteristika/Технические характеристики:\n")
    if spec_uz:
        add(spec_uz + "\n\n")
    if spec_ru:
        add(spec_ru)
    q_end = _utf16len(''.join(parts))
    quote = (q_start, q_end - q_start)
    add("\n\n")

    # ── Holati ──
    add(f"{cond_emoji} • Holati: {cond_uz}\n")
    add(f"{cond_emoji} • Состояние: {cond_ru}\n\n")

    # ── Narx: eski (strikethrough) + yangi (bold), yoki SOTILDI ──
    # B5: sotilganini `status` ustuni aytadi. Sayt endi narxni 0 QILMAYDI —
    # sotilgan e'londa ham asl narx turadi, shuning uchun uni chizib ko'rsatamiz.
    sold = is_sold(item)

    add_prem('money'); add(" Цена/Narxi: ")
    if sold:
        # ~~400$~~ ❗️SOTILDI❗️
        narx = price if price and price != '0' else old
        if narx:
            add_fmt(f"{narx}$", 'strikethrough')
            add(" ")
        add_fmt("❗️QOLMADI❗️" if kop_donali(item) else "❗️SOTILDI❗️", 'bold')   # B13: ko'p donali tugasa
        add("\n\n")
    elif old and old != price:
        add_fmt(f"{old}$", 'strikethrough')
        add(" ")
        add_fmt(f"{price}$", 'bold')
        add("\n\n")
    else:
        add_fmt(f"{price}$", 'bold')
        add("\n\n")

    # ── Kontaktlar ──
    add("📩 @Krakens_admin\n")
    add("📞 +998997638595\n\n")
    add_prem('k'); add(" @Kraken_Mobile (Kanal/Канал)\n")
    add_prem('k'); add(" @Kraken_Mobile_shop_bot")

    text = ''.join(parts)
    entities = [{
        'type': 'custom_emoji',
        'offset': off,
        'length': _utf16len(base),
        'custom_emoji_id': eid,
    } for (eid, off, base) in prem]
    # Bold / strikethrough
    for ftype, off, length in fmt:
        entities.append({'type': ftype, 'offset': off, 'length': length})
    # Collapsed blockquote (yopilgan quote)
    if quote and quote[1] > 0:
        entities.append({
            'type': 'expandable_blockquote',
            'offset': quote[0],
            'length': quote[1],
        })
    return num, text, entities


def _utf16len(s):
    """Telegram entities UTF-16 birlikda hisoblaydi."""
    return len(s.encode('utf-16-le')) // 2


# ══════════════════════════════════════════════════════════════════════════
#  G11.0 — RICH MESSAGE SINOVI (/richtest <num>, faqat admin)
#
#  Bot API 10.1 (2026-iyun) — sendRichMessage: BITTA xabarda sarlavha, rasmlar
#  (<tg-collage> = to'r, hammasi ko'rinadi; <tg-slideshow> = varaqlanadigan),
#  yopiladigan <details> blok, <tg-emoji> (premium emoji), <tg-button> tugma.
#  Keyin editMessageText(rich_message=...) bilan TAHRIRLANADI — narx o'zgarsa
#  post o'zgaradi, sotilsa «Sotildi» bo'ladi (KANAL_REJA.md G11.2).
#
#  Asosiy savol: KANALDA premium emoji chiqadimi? Oddiy xabarda faqat Fragment
#  username bilan chiqadi (Bot API «Formatting options»). Rich bo'limida bu
#  cheklov YOZILMAGAN — faqat jonli sinov aytadi. Shu sabab bu buyruq e'lonni
#  2 ko'rinishda (collage, slideshow) admin lichkasiga VA test kanaliga yuboradi.
# ══════════════════════════════════════════════════════════════════════════

def images_of(elon):
    """E'lon rasmlari — Sheets'da JSON matn, xotirada ro'yxat bo'lishi mumkin."""
    images = elon.get('images')
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []
    if not isinstance(images, list):
        images = []
    return [str(u).strip() for u in images if str(u or '').strip()]


def _rich_emoji(key):
    base, eid = PREMIUM[key]
    return f'<tg-emoji emoji-id="{eid}">{base}</tg-emoji>'


def _rich_table(*spec_texts):
    """'• Ekran: 6.3 dyum…\n• Protsessor: …' matnlar(i) → BITTA <table bordered compact> (nom | qiymat).
    v7 (2026-09-14): uz va ru qatorlari bitta jadvalda — ustun kengligi bir marta hisoblanadi,
    ajratuvchi chiziq hamma qatorda bir xil joyda (ikki jadvalda ruscha nomlar uzunroq bo'lib
    chiziq o'ngroqqa surilardi). Oradagi <hr/> ham olib tashlandi (foydalanuvchi: «kerakmas»)."""
    rows = []
    for spec_text in spec_texts:
        guruh = []
        for line in str(spec_text or '').split('\n'):
            line = line.strip().lstrip('•').strip()
            if not line:
                continue
            k, sep, v = line.partition(':')
            if sep and v.strip():
                guruh.append(f'<tr><td><b>{html_escape(k.strip())}</b></td><td>{html_escape(v.strip())}</td></tr>')
            else:
                guruh.append(f'<tr><td colspan="2">{html_escape(line)}</td></tr>')
        if guruh and rows:
            # v8: uz va ru orasida BO'SH QATOR (chiziq emas) — bitta jadvalda ustunlar
            #     bir xil qoladi, lekin tillar aralashib ketmaydi (foydalanuvchi: «aralashib ketdi»)
            rows.append('<tr><td colspan="2">\u00a0</td></tr>')
        rows.extend(guruh)
    return f'<table bordered compact>{"".join(rows)}</table>' if rows else ''


def build_rich_html(elon, models_by_id, premium=True, rasm_src=None):
    """E'lon uchun Rich HTML (slideshow). premium=False — <tg-emoji>siz.
    v6 (2026-09-14): collage bekor (foydalanuvchi: «collage atmen»), faqat slideshow.
    rasm_src — {rasm URL: src} (BUGUN16 inline: `tg://photo?id=…` — inline'da URL ishlamaydi); qolgani o'zgarmaydi."""
    num = int(float(elon.get('num', 0) or 0))
    model = models_by_id.get(str(elon.get('specId', '') or ''), {}) if isinstance(models_by_id, dict) else {}
    name = html_escape(elon_nomi(elon, model, 'uz'))   # G12: e'lonning o'z nomi (bo'lmasa model), brend bilan
    mos_txt = html_escape(mos_line(model, models_by_id, 'uz'))
    izoh_txt = html_escape(izoh_matni(elon, 'uz'))   # G12 K2
    storage = html_escape(str(elon.get('storage') or '').strip())
    color = html_escape(clean_color(elon.get('color') or ''))
    price = str(elon.get('price', '') or '').replace('.0', '')
    old = str(elon.get('oldPrice', '') or '').replace('.0', '')
    cycle = str(elon.get('cycle', '') or '').replace('.0', '')
    cond_uz, cond_ru, cond_emoji = holati_matni(elon.get('condition', 'used') or 'used', cycle)
    e = (lambda k: _rich_emoji(k)) if premium else (lambda k: PREMIUM[k][0])

    # v6: slideshow — hammasi. v8 (2026-09-18, foydalanuvchi): «N ta rasm — suring» izohi OLIB TASHLANDI
    rasmlar = images_of(elon)[:10]
    imgs = ''.join(f'<img src="{html_escape((rasm_src or {}).get(u, u))}"/>' for u in rasmlar)
    media = f'<tg-slideshow>{imgs}</tg-slideshow>' if imgs else ''

    title = name + (f' ({storage})' if storage else '') + (f' {color}' if color else '')
    if elon_status(elon) == 'sold':
        # B13 soni: ko'p donali tovar tugasa «QOLMADI» (e'lon o'chmaydi — yana kelsa post tahrirlanadi)
        narx = (f'<s>{html_escape(price or old)}$</s> ' if (price or old) else '') + ('<b>❗️QOLMADI❗️</b>' if kop_donali(elon) else '<b>❗️SOTILDI❗️</b>')
    elif old and old != price:
        narx = f'<s>{html_escape(old)}$</s> <b>{html_escape(price)}$</b>'
    else:
        narx = f'<b>{html_escape(price)}$</b>'

    # v4: uz va ru jadvallari orasida chiziq (<hr/>) va sarlavha — foydalanuvchi:
    #     «o'zbekcha tugashi bilan ruscha boshlangan, 6-bo'limdek bo'lib ketgan»
    spec = ''
    jadval = _rich_table(model.get('specUz'), model.get('specRu'))   # v7: bitta jadval, chiziqsiz
    if jadval:
        spec = '<details><summary>📋 Texnik xarakteristika / Характеристики</summary>' + jadval + '</details>'

    # v2: <h3> emas — oddiy qalin qator (katta sarlavha «maqola»dek ko'rinardi);
    #     tugmalar align'siz — butun eniga (align="center" kichik qilib qo'ygan edi)
    # v4: RASM TEPADA, matn pastda — kanaldagi eski postga yaqin (foydalanuvchi so'radi);
    #     holati ikki tilda IKKI qator (bitta qatorga qo'shilgani «xunuk» edi)
    kanal = CHANNEL.lstrip('@')
    # v5: bloklar orasida BO'SH JOY (Telegram rich'da paragraflar orasiga margin qo'ymaydi —
    #     bo'sh paragraf \u00a0 bilan). Holati + narx BITTA blok. Foydalanuvchi ko'rsatdi:
    #     xarakteristika / bo'sh / holati·holati·narx / bo'sh / tugma
    # v6: spec TEPASIDA ham bo'sh joy (details'ga Telegram faqat pastdan chiziq chizadi —
    #     sarlavhaga yopishib ketardi); holati va narx ALOHIDA paragraflar (bo'sh qatorsiz,
    #     lekin <br/> bilan yopishgan emas)
    # v7: bo'sh joy rasm izohi («suring») bilan sarlavha ORASIDA (yopishib qolgan edi);
    #     spec tepasidagi bo'sh joy olib tashlandi («juda katta bo'lib ketdi»)
    BOSH = '<p>\u00a0</p>'
    return (
        media
        + (BOSH if media else '')
        + f'<p><b>{e("google")} {title}</b><br/>#phone #{num}' + (f'<br/>🔗 {mos_txt}' if mos_txt else '') + (f'<br/>📝 {izoh_txt}' if izoh_txt else '') + '</p>'
        + spec
        + BOSH
        + f'<p>{html_escape(cond_emoji)} Holati: <b>{html_escape(cond_uz)}</b><br/>'
          f'{html_escape(cond_emoji)} Состояние: <b>{html_escape(cond_ru)}</b></p>'
        + f'<p>{e("money")} Narxi / Цена: {narx}' + (f'<br/>{soni_qatori(elon)}' if soni_qatori(elon) else '') + '</p>'   # B13: qoldiq
        + BOSH
        + '<tg-button-row>'
          # v3: «Saytni ochish» — BUTUN sayt (startapp=home). Foydalanuvchi: «forwardda e'lonni
          #     to'liq ko'rib bo'lgan odamga shu e'lonni saytda ko'rishdan naf yo'q — boshqa
          #     e'lonlarni ko'rgani yaxshi»
          f'<tg-button type="url" style="primary" url="https://t.me/{BOT_USERNAME}?startapp=home">🛍 Saytni ochish / Открыть сайт</tg-button>'
          '</tg-button-row>'
        + '<tg-button-row>'
          '<tg-button type="url" url="https://t.me/Krakens_admin">✉️ Admin</tg-button>'
          f'<tg-button type="url" url="https://t.me/{kanal}">🪐 Kanal</tg-button>'   # v8: lampa (K logo) → 🪐 (foydalanuvchi)
          '</tg-button-row>'
    )


def send_rich(chat_id, html, disable_notification=False):
    """sendRichMessage. (message_id, '') yoki (None, xato matni)."""
    try:
        r = req.post(f'{TG_API}/sendRichMessage', json={
            'chat_id': chat_id,
            'rich_message': {'html': html},
            'disable_notification': disable_notification,
        }, timeout=30).json()
    except Exception as ex:
        return None, f'tarmoq: {ex}'
    if not r.get('ok'):
        return None, str(r.get('description') or r)
    return (r.get('result') or {}).get('message_id'), ''


def richtest(admin_chat, num):
    """/richtest <num>: 2 ko'rinish × 2 manzil (lichka, TEST kanal). Natijani adminga yozadi."""
    elon, models = elon_cache_get(num)
    if not elon:
        send_msg(admin_chat, f"❌ №{num} e'lon topilmadi.")
        return
    hisobot = [f"🧪 <b>Rich sinov №{num}</b> — test kanali: {TEST_CHANNEL}"]
    # v6: premium emoji kanalda chiqmasligi tasdiqlangan (2026-09-14 sinovi) — to'g'ridan-to'g'ri emoji'siz
    html = build_rich_html(elon, models, premium=False)
    for nom, chat in (('lichka', admin_chat), ('test kanal', TEST_CHANNEL)):
        mid, xato = send_rich(chat, html)
        if mid:
            hisobot.append(f"✅ {nom}: yuborildi (id {mid})")
        else:
            hisobot.append(f"❌ {nom}: <code>{html_escape(xato)}</code>")
    hisobot.append("\nSinov postlarini keyin o'chiramiz.")
    send_msg(admin_chat, '\n'.join(hisobot))


# ══════════════════════════════════════════════════════════════════════════
#  G11.2 / B15 (2026-09-18): KANAL MEXANIKASI — hozircha TEST kanalda sinaladi.
#  Rebrandingdan keyin FAQAT `POST_CHANNEL_ID` env almashadi (Render) — kod o'zgarmaydi.
#
#  · kanal_post(num)        rich post → kanal; `channel_message_id` Sheets'ga + xotiraga
#  · kanal_tahrir(num)      narx / sotildi / qolmadi / soni o'zgarsa POST TAHRIRLANADI
#                           (editMessageText + rich_message). Sukut shu (A14 qarori).
#  · kanal_ochir(num)       e'lon o'chirilsa post o'chadi (deleteMessage), id tozalanadi
#  · kanal_yana_keldi(num)  «Yana keldi»: eski post O'CHIB, YANGISI yuboriladi (yangi id) —
#                           keyingi tahrirlar shunga. Forward EMAS (nusxa tahrirni olmaydi).
#  · /toplam                case / part / accessory — alohida post EMAS: postlanmaganlarni
#                           BITTA to'plam postiga (tugmalar startapp=<tab>), adminga avval
#                           ko'rsatadi, tasdiqlasa kanalga. Ichidagi e'lon o'zgarsa —
#                           to'plam posti qayta yasalib tahrirlanadi.
#  · /katalog               qadaladigan «Katalog» posti (bo'lim tugmalari), tasdiq bilan
#  · AVTO-POST faqat phone/camera — sayt saqlaganda (yangi yoki waited→active).
#    Boshqa turlar faqat /toplam orqali (foydalanuvchi 2026-09-18: «10 ta batareyka,
#    20 ta chexol tashlasam g'alati bo'ladi»).
#  🔴 Eski 93 e'lon (id yo'q) hech qachon o'z-o'zidan postlanmaydi — faqat G11.4 (/hammasini_yubor).
# ══════════════════════════════════════════════════════════════════════════
POST_CHANNEL = os.environ.get('POST_CHANNEL_ID', TEST_CHANNEL)
AVTO_POST_TURLAR = ('phone', 'camera')
TOPLAM_TURLAR = ('accessory', 'case', 'part')
TUR_NOMI = {'phone': ('📱', 'Smartfonlar', 'Смартфоны'), 'camera': ('📷', 'Kameralar', 'Камеры'),
            'accessory': ('🔌', 'Aksessuarlar', 'Аксессуары'), 'case': ('🛡', "G'iloflar", 'Чехлы'),
            'part': ('🛠', 'Zapchastlar', 'Запчасти')}


def elon_turi(elon, models_by_id):
    """E'lon bo'limi (phone/camera/accessory/case/part) — model → lineyka → tur (sayt listingType bilan bir xil)."""
    model = models_by_id.get(str((elon or {}).get('specId', '') or ''), {}) if isinstance(models_by_id, dict) else {}
    sk = str((model or {}).get('series', '') or '')
    ser = next((s for s in (_ELON_CACHE.get('series') or []) if str(s.get('key', '')) == sk), None)
    return ser_type(ser) if ser else 'phone'


def kanal_msg_id(elon):
    """channel_message_id (Sheets'da matn/son) → int yoki None."""
    try:
        v = str((elon or {}).get('channel_message_id', '') or '').strip()
        return int(float(v)) if v else None
    except Exception:
        return None


def kop_donali(elon):
    """B13 soni: `soni` bo'sh emas — ko'p donali tovar (sayt koPDonali bilan bir xil)."""
    return str((elon or {}).get('soni', '') if (elon or {}).get('soni') is not None else '').strip() != ''


def soni_val(elon):
    if not kop_donali(elon):
        return None
    try:
        return max(0, int(float(str(elon.get('soni')).strip())))
    except Exception:
        return 0


def soni_qatori(elon):
    """Postdagi qoldiq qatori: «📦 5 dona bor» / «📦 Oxirgi 1 ta»; bitta tovar yoki 0 — bo'sh."""
    n = soni_val(elon)
    if n is None or n == 0:
        return ''
    return '📦 Oxirgi 1 ta / Последний' if n == 1 else f'📦 {n} dona bor / {n} шт.'


def _sheets_update(payload):
    """Elonlar qatorini yangilash (faqat kelgan maydonlar — Apps Script updateElon B9). True — ok."""
    if not SHEET_URL:
        return False
    try:
        r = req.get(f'{SHEET_URL}?action=update&data={urllib.parse.quote(json.dumps(payload))}', timeout=20)
        text = r.text.strip()
        d = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        return bool(d.get('ok'))
    except Exception as e:
        logger.error(f'_sheets_update: {e}')
        return False


def kanal_id_yoz(num, mid):
    """Post id'sini Sheets'ga (channel_message_id) va xotiraga yozadi. mid=None — tozalash."""
    ok = _sheets_update({'num': int(num), 'channel_message_id': int(mid) if mid else ''})
    with _elon_cache_lock:
        e = _ELON_CACHE['by_num'].get(str(num))
        if e is not None:
            e['channel_message_id'] = int(mid) if mid else ''
    if not ok:
        logger.error(f'kanal_id_yoz: №{num} id {mid} Sheets ga yozilmadi')
    return ok


def edit_rich(chat_id, message_id, html):
    """editMessageText + rich_message. (True, '') / (False, xato). «not modified» — ok."""
    try:
        r = req.post(f'{TG_API}/editMessageText', json={
            'chat_id': chat_id, 'message_id': int(message_id), 'rich_message': {'html': html},
        }, timeout=30).json()
    except Exception as ex:
        return False, f'tarmoq: {ex}'
    if r.get('ok'):
        return True, ''
    desc = str(r.get('description') or r)
    if 'not modified' in desc:
        return True, ''
    return False, desc


def delete_msg(chat_id, message_id):
    try:
        r = req.post(f'{TG_API}/deleteMessage', json={'chat_id': chat_id, 'message_id': int(message_id)}, timeout=15).json()
    except Exception as ex:
        return False, f'tarmoq: {ex}'
    if r.get('ok'):
        return True, ''
    desc = str(r.get('description') or r)
    if 'not found' in desc or 'MESSAGE_ID_INVALID' in desc:
        return True, ''   # allaqachon yo'q — maqsad bajarilgan
    return False, desc


# ══════════════════════════════════════════════════════════════════════════
#  BUGUN10 §3b (2026-09-24): ISTAKKA JAVOB MIJOZGA BOT ORQALI
#  Mijoz saytda istak yozadi («Topa olmadingizmi?» / Profil → Istaklar) → Kraken Apps Script adminga shu bot nomidan
#  «🔔 Yangi istak» xabarini yuboradi (apps-script/IstakXabar.gs). Admin o'sha xabarga Telegram'da «Reply» qilib yozsa —
#  bot javobni MIJOZGA yuboradi. Foydalanuvchi: «"Topa olmadingizmi"dan kelgan xabarga men javob bera olamanmi va mening
#  javobim mijozga botdan keladigan qilamizmi?»
#  · Faqat ADMIN_ID lichkasidan va faqat botning o'z «🔔 Yangi istak» xabariga javob bo'lsa (boshqa reply — eski yo'l).
#  · Mijoz — xabardagi «🆔 <id>» qatoridan. Apps Script bu qatorni FAQAT Telegram imzosi (initData) tasdiqlangan mijozga
#    yozadi; brauzerdan yozgan / imzosiz istakda qator yo'q → javob yo'q, adminga sababi aytiladi.
#  · Matn → bitta xabar (sarlavha + javob). Rasm / video / fayl → o'sha narsa nusxasi (copyMessage), sarlavha izohida.
#    Boshqasi (ovozli, stiker…) → avval sarlavha, keyin nusxa. Sarlavha mijoz tilida (xabardagi «🌐 uz/ru»).
#  · Natija adminga, javobiga reply bo'lib: «✅ Mijozga yuborildi» yoki sababi (bot bloklangan / mijoz botga yozmagan).
# ══════════════════════════════════════════════════════════════════════════
ISTAK_BELGI = '🔔 Yangi istak'   # 🔴 apps-script/IstakXabar.gs ISTAK_XABAR_BELGI bilan BIR XIL
ISTAK_IZOHLI = ('photo', 'video', 'animation', 'document', 'audio')   # copyMessage izoh (caption) oladigan turlar


def istak_javob_manzil(reply):
    """Admin reply qilgan xabar botning «🔔 Yangi istak» xabarimi. Bo'lsa {'id', 'til', 'matn'} — aks holda None.
    🆔 qatori yo'q bo'lsa (brauzer / imzosiz) — {'id': None} (adminga sababi aytiladi)."""
    r = reply or {}
    kim = r.get('from') or {}
    if not kim.get('is_bot') or str(kim.get('username') or '').lower() != BOT_USERNAME.lower():
        return None
    t = str(r.get('text') or '')
    if not t.startswith(ISTAK_BELGI):
        return None
    m = re.search(r'^🆔 (\d{3,15})\s*$', t, re.M)
    w = re.search(r'^💬 (.+)$', t, re.M)
    return {'id': int(m.group(1)) if m else None,
            'til': 'ru' if re.search(r'^🌐 ru\s*$', t, re.M) else 'uz',
            'matn': (w.group(1).strip() if w else '')[:120]}


def istak_javob_sarlavha(manzil):
    """Mijozga ketadigan sarlavha (HTML) — uning tilida, istagi eslatiladi."""
    so = html_escape(manzil.get('matn') or '')
    if manzil.get('til') == 'ru':
        return '📩 <b>Ответ Kraken Mobile</b>' + (f'\nНа ваш запрос: «{so}»' if so else '')
    return '📩 <b>Kraken Mobile javobi</b>' + (f"\nSiz so'ragan: «{so}»" if so else '')


def _istak_xato_sababi(desc):
    d = str(desc or '')
    if 'blocked' in d:
        return "mijoz botni bloklagan"
    if 'chat not found' in d or "can't initiate" in d or 'initiate conversation' in d:
        return "mijoz botga hali yozmagan (bot unga birinchi yoza olmaydi)"
    return d[:150] or "noma'lum xato"


def istak_javob_yubor(admin_chat, message, manzil):
    """Admin javobini mijozga yuboradi, natijani adminga (javobiga reply) aytadi. Natija: 'yuborildi' | 'id yoq' | 'xato'."""
    mid = message.get('message_id')

    def adminga(matn):
        try:
            req.post(f'{TG_API}/sendMessage', json={'chat_id': admin_chat, 'text': matn, 'parse_mode': 'HTML',
                                                    'reply_parameters': {'message_id': mid, 'allow_sending_without_reply': True}},
                     timeout=8)
        except Exception as e:
            logger.error(f'istak javobi (admin): {e}')

    if not manzil.get('id'):
        adminga("⚠️ Bu istak brauzerdan yoki Telegram imzosisiz yozilgan — mijozning Telegram'i yo'q, bot javob yubora olmaydi.")
        return 'id yoq'
    uid, sarl = manzil['id'], istak_javob_sarlavha(manzil)
    try:
        if message.get('text'):
            j = req.post(f'{TG_API}/sendMessage', json={'chat_id': uid, 'text': sarl + '\n\n' + html_escape(message['text']),
                                                        'parse_mode': 'HTML'}, timeout=10).json()
        elif any(message.get(k) for k in ISTAK_IZOHLI):
            cap = html_escape(message.get('caption') or '')
            j = req.post(f'{TG_API}/copyMessage', json={'chat_id': uid, 'from_chat_id': admin_chat, 'message_id': mid,
                                                        'caption': sarl + ('\n\n' + cap if cap else ''), 'parse_mode': 'HTML'},
                         timeout=15).json()
        else:
            j = req.post(f'{TG_API}/sendMessage', json={'chat_id': uid, 'text': sarl, 'parse_mode': 'HTML'}, timeout=10).json()
            if j.get('ok'):
                j = req.post(f'{TG_API}/copyMessage', json={'chat_id': uid, 'from_chat_id': admin_chat, 'message_id': mid},
                             timeout=15).json()
    except Exception as e:
        j = {'ok': False, 'description': f'tarmoq: {e}'}
    if j.get('ok'):
        adminga('✅ Mijozga yuborildi')
        return 'yuborildi'
    adminga('❌ Yuborilmadi: ' + html_escape(_istak_xato_sababi(j.get('description'))))
    return 'xato'


def kanal_post(num):
    """E'lonni kanalga rich post qiladi, id yozadi. (mid, '') / (None, xato)."""
    elon, models = elon_cache_get(num)
    if not elon:
        return None, "e'lon topilmadi"
    if elon_status(elon) in ('deleted', 'waited'):
        return None, "chala yoki o'chirilgan e'lon postlanmaydi"
    html = build_rich_html(elon, models, premium=False)
    mid, xato = send_rich(POST_CHANNEL, html)
    if not mid:
        return None, xato
    kanal_id_yoz(num, mid)
    return mid, ''


def kanal_tahrir(num):
    """Kanaldagi postni e'lonning hozirgi holatiga moslaydi. (True, '') / (False, sabab)."""
    elon, models = elon_cache_get(num)
    if not elon:
        return False, "e'lon topilmadi"
    mid = kanal_msg_id(elon)
    if not mid:
        return False, "post yo'q"
    if elon_turi(elon, models) in TOPLAM_TURLAR:
        return toplam_tahrir(mid)
    return edit_rich(POST_CHANNEL, mid, build_rich_html(elon, models, premium=False))


def kanal_ochir(num):
    """Postni o'chiradi, id'ni tozalaydi. To'plam ichidagi e'lon — to'plam qayta yasaladi."""
    elon, models = elon_cache_get(num)
    if not elon:
        return False, "e'lon topilmadi"
    mid = kanal_msg_id(elon)
    if not mid:
        return True, ''
    if elon_turi(elon, models) in TOPLAM_TURLAR:
        kanal_id_yoz(num, None)
        return toplam_tahrir(mid)
    ok, xato = delete_msg(POST_CHANNEL, mid)
    if ok:
        kanal_id_yoz(num, None)
    return ok, xato


def kanal_yana_keldi(num):
    """«Yana keldi»: eski post o'chadi, yangisi yuboriladi, yangi id yoziladi (A14 qarori 2026-09-18)."""
    elon, models = elon_cache_get(num)
    if not elon:
        return None, "e'lon topilmadi"
    mid = kanal_msg_id(elon)
    if mid and elon_turi(elon, models) not in TOPLAM_TURLAR:
        delete_msg(POST_CHANNEL, mid)   # o'chmasa ham yangisi ketadi
    return kanal_post(num)


# ── To'plam (case / part / accessory) ──
def _toplam_items(shart):
    with _elon_cache_lock:
        items = list(_ELON_CACHE['by_num'].values())
        models = dict(_ELON_CACHE['models'])
    out = [e for e in items if elon_status(e) not in ('deleted', 'waited') and elon_turi(e, models) in TOPLAM_TURLAR and shart(e)]
    out.sort(key=lambda e: (TOPLAM_TURLAR.index(elon_turi(e, models)), -int(float(e.get('num', 0) or 0))))
    return out, models


def toplam_elonlar():
    """Hali kanalga chiqmagan (id yo'q) faol case/part/accessory e'lonlar."""
    return _toplam_items(lambda e: not kanal_msg_id(e))


def build_toplam_html(items, models_by_id):
    """To'plam posti: birinchi rasmlar slideshow (10 tagacha), tur bo'yicha ro'yxat, bo'lim tugmalari (startapp=<tab>)."""
    rasmlar = []
    for e in items:
        r = images_of(e)
        if r and r[0] not in rasmlar:
            rasmlar.append(r[0])
    imgs = ''.join(f'<img src="{html_escape(u)}"/>' for u in rasmlar[:10])
    media = f'<tg-slideshow>{imgs}</tg-slideshow>' if imgs else ''
    BOSH = '<p>\u00a0</p>'
    guruh = {}
    for e in items:
        guruh.setdefault(elon_turi(e, models_by_id), []).append(e)
    bloklar = []
    for tur in TOPLAM_TURLAR:
        if tur not in guruh:
            continue
        emoji, uz, ru = TUR_NOMI[tur]
        qatorlar = [f'<b>{emoji} {uz} / {ru}</b>']
        for e in guruh[tur]:
            num = int(float(e.get('num', 0) or 0))
            model = models_by_id.get(str(e.get('specId', '') or ''), {})
            nom = html_escape(elon_nomi(e, model, 'uz'))
            price = html_escape(str(e.get('price', '') or '').replace('.0', ''))
            if elon_status(e) == 'sold':
                narx = '<s>' + (price + '$' if price else '') + '</s> ' + ('Qolmadi' if kop_donali(e) else 'Sotildi')
            else:
                narx = f'<b>{price}$</b>' if price else ''
            qold = soni_qatori(e)
            qatorlar.append(f'№{num} {nom} — {narx}' + (f' · {qold.split(" / ")[0]}' if qold else ''))
        bloklar.append('<p>' + '<br/>'.join(qatorlar) + '</p>')
    tugma = lambda tur: f'<tg-button type="url" url="https://t.me/{BOT_USERNAME}?startapp={tur}">{TUR_NOMI[tur][0]} {TUR_NOMI[tur][1]}</tg-button>'
    return (
        media + (BOSH if media else '')
        + '<p><b>🧩 Aksessuar · g\'ilof · zapchast — yangi to\'plam</b><br/>#toplam</p>'
        + ''.join(bloklar)
        + BOSH
        + '<tg-button-row>' + tugma('accessory') + '</tg-button-row>'
        + '<tg-button-row>' + tugma('case') + tugma('part') + '</tg-button-row>'
        + '<tg-button-row>'
          f'<tg-button type="url" style="primary" url="https://t.me/{BOT_USERNAME}?startapp=home">🛍 Saytni ochish / Открыть сайт</tg-button>'
          '</tg-button-row>'
    )


def toplam_tahrir(mid):
    """Shu to'plam postiga kirgan (id bir xil) e'lonlar bo'yicha post qayta yasalib tahrirlanadi; hech kim qolmasa — o'chadi."""
    items, models = _toplam_items(lambda e: kanal_msg_id(e) == int(mid))
    if not items:
        return delete_msg(POST_CHANNEL, mid)
    return edit_rich(POST_CHANNEL, mid, build_toplam_html(items, models))


def build_katalog_html():
    """Qadaladigan «Katalog» posti — bo'lim tugmalari (startapp=<tab>), sayt tugmasi."""
    tugma = lambda tur: f'<tg-button type="url" url="https://t.me/{BOT_USERNAME}?startapp={tur}">{TUR_NOMI[tur][0]} {TUR_NOMI[tur][1]}</tg-button>'
    return (
        '<p><b>🗂 KATALOG / КАТАЛОГ</b><br/>Bo\'limni tanlang — sayt shu bo\'limda ochiladi<br/>Выберите раздел — сайт откроется на нём</p>'
        + '<tg-button-row>' + tugma('phone') + tugma('camera') + '</tg-button-row>'
        + '<tg-button-row>' + tugma('accessory') + '</tg-button-row>'
        + '<tg-button-row>' + tugma('case') + tugma('part') + '</tg-button-row>'
        + '<tg-button-row>'
          f'<tg-button type="url" style="primary" url="https://t.me/{BOT_USERNAME}?startapp=home">🛍 Saytni ochish / Открыть сайт</tg-button>'
          '</tg-button-row>'
    )


# Admin lichkasidagi tasdiq: kalit → {'tur': 'toplam'|'katalog', 'html': ..., 'nums': [...]}
_KANAL_KUTMOQDA = {}


def kanal_taklif(admin_chat, tur):
    """/toplam yoki /katalog: postni AVVAL adminga ko'rsatadi, «Kanalga yuborish» tugmasi bilan."""
    if tur == 'toplam':
        items, models = toplam_elonlar()
        if not items:
            send_msg(admin_chat, "📭 Kanalga chiqmagan aksessuar / g'ilof / zapchast yo'q.")
            return
        html, nums = build_toplam_html(items, models), [int(float(e.get('num', 0) or 0)) for e in items]
        izoh = f"🧩 To'plam: {len(items)} ta e'lon (№{', №'.join(str(n) for n in nums)})"
    else:
        html, nums = build_katalog_html(), []
        izoh = "🗂 Katalog posti — kanalga yuborilib QADALADI"
    mid, xato = send_rich(admin_chat, html)
    if not mid:
        send_msg(admin_chat, f"❌ Ko'rsatib bo'lmadi: <code>{html_escape(xato)}</code>")
        return
    key = f'{tur}{int(time.time())}'
    _KANAL_KUTMOQDA[key] = {'tur': tur, 'html': html, 'nums': nums}
    send_msg(admin_chat, izoh + f"\nKanal: {POST_CHANNEL}", {"inline_keyboard": [[
        {"text": "✅ Kanalga yuborish", "callback_data": f"kanal_ok:{key}"},
        {"text": "❌ Bekor", "callback_data": f"kanal_no:{key}"}]]})


def kanal_tasdiq(admin_chat, key, ok):
    p = _KANAL_KUTMOQDA.pop(key, None)
    if not p:
        send_msg(admin_chat, "⌛ Bu taklif eskirgan — buyruqni qayta yuboring.")
        return
    if not ok:
        send_msg(admin_chat, "❌ Bekor qilindi.")
        return
    mid, xato = send_rich(POST_CHANNEL, p['html'])
    if not mid:
        send_msg(admin_chat, f"❌ Kanalga ketmadi: <code>{html_escape(xato)}</code>")
        return
    if p['tur'] == 'toplam':
        for n in p['nums']:
            kanal_id_yoz(n, mid)
        send_msg(admin_chat, f"✅ To'plam kanalga chiqdi (id {mid}), {len(p['nums'])} ta e'longa yozildi.")
    else:
        try:
            req.post(f'{TG_API}/pinChatMessage', json={'chat_id': POST_CHANNEL, 'message_id': mid, 'disable_notification': True}, timeout=15)
        except Exception as e:
            logger.error(f'pinChatMessage: {e}')
        send_msg(admin_chat, f"✅ Katalog posti kanalga chiqdi va qadaldi (id {mid}).")


def kanal_sinxron(eski, yangi):
    """Sayt (admin) e'lonni saqlaganda: o'chirilgan → post o'chadi; post bor → tahrir;
    yangi phone/camera (waited→active yoki yangi) → avto-post. Boshqa turlar — /toplam."""
    try:
        num = int(yangi['num'])
        st = elon_status(yangi)
        mid = kanal_msg_id(yangi)
        if st == 'deleted':
            if mid:
                ok, xato = kanal_ochir(num)
                if not ok:
                    send_msg(ADMIN_ID, f"⚠️ №{num} kanal posti o'chmadi: <code>{html_escape(xato)}</code>")
            return 'ochir' if mid else ''
        if mid:
            ok, xato = kanal_tahrir(num)
            if not ok:
                send_msg(ADMIN_ID, f"⚠️ №{num} kanal posti yangilanmadi: <code>{html_escape(xato)}</code>")
            return 'tahrir'
        if not _ELON_CACHE['time']:
            return ''   # xotira yuklanmagan — eskisi noma'lum, ehtiyot: avto-post yo'q
        _, models = elon_cache_get(num)
        yangi_elon = eski is None or elon_status(eski) == 'waited'
        if st == 'active' and yangi_elon and elon_turi(yangi, models) in AVTO_POST_TURLAR:
            mid, xato = kanal_post(num)
            if mid:
                send_msg(ADMIN_ID, f"📣 №{num} kanalga chiqdi (id {mid}) — {POST_CHANNEL}")
            else:
                send_msg(ADMIN_ID, f"⚠️ №{num} kanalga chiqmadi: <code>{html_escape(xato)}</code>")
            return 'post'
        return ''
    except Exception as e:
        logger.error(f'kanal_sinxron: {e}')
        return ''


def html_escape(s):
    """HTML maxsus belgilarini himoyalaydi."""
    if not s:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# (md_escape olib tashlandi — E7: html_escape ning eski nomi edi, hech qayerda
#  ishlatilmasdi)


def winner_display(w):
    """G'olibni ko'rsatish (HTML parse_mode):
       username bor  -> @username
       username yo'q -> <a href="tg://user?id=ID">Ism</a> (ism ko'rinadi, ID link)
                        agar ID bo'lmasa telefon link.
    HTML ishonchliroq: username'dagi _ buzilmaydi, tg link to'g'ri ishlaydi."""
    try:
        uname = str(w.get('username') or '').lstrip('@').strip()
    except Exception:
        uname = ''
    if uname:
        return '@' + html_escape(uname)
    ism = html_escape(str(w.get('ism') or '').strip() or 'Ishtirokchi')
    uid = str(w.get('user_id') or '').strip()
    phone = str(w.get('phone') or '').strip().lstrip('+')
    if uid:
        return f'<a href="tg://user?id={uid}">{ism}</a>'
    if phone:
        return f'<a href="tg://resolve?phone={phone}">{ism}</a>'
    return ism


# (strip_custom_emoji olib tashlandi — D2: kanalga avto-yuborish qaytarilmadi,
#  uni faqat o'sha yo'l ishlatardi)


def build_olx_text(item, models_by_id):
    """OLX uchun elon matni (premium emoji'siz, oddiy matn).

    Tuzilishi (prompt 5 bo'yicha):
      ELON RAQAMI: #150
      <birxil shablon: telegramdan arzon, har oy konkurs, 20+ model>
      • Holati (uz/ru)
      Narxi: ~~eski~~ yangi
      ---
      Texnik xarakteristika (rang, xotira, ekran... uz+ru)
    """
    num = int(float(item.get('num', 0) or 0))
    name_uz = item.get('nameUz', '') or item.get('name', '')
    storage = item.get('storage', '')
    price = str(item.get('price', '')).replace('.0', '')
    old = str(item.get('oldPrice', '')).replace('.0', '')
    cond = item.get('condition', 'new')
    cycle = str(item.get('cycle', '') or '').replace('.0', '')
    color_uz = clean_color(item.get('color', ''))
    color_ru = clean_color(item.get('colorRu', '') or item.get('color', ''))

    model = models_by_id.get(item.get('specId', ''), {})
    spec_uz = model.get('specUz', '') or ''
    spec_ru = model.get('specRu', '') or ''

    cond_uz, cond_ru, _ = holati_matni(cond, cycle)

    lines = []
    lines.append(f"ELON RAQAMI: #{num}")
    lines.append("")
    # ── Birxil shablon (har elon uchun bir xil) ──
    lines.append("Telegram kanal yoki saytimizdan zakaz qilganlarga narxi arzonroq "
                 "va kanalda har oy rozigrish (konkurs) bo'ladi!")
    lines.append("Bundan tashqari 20 ga yaqin modellar va boshqa aksessuarlar, "
                 "zapchastlar bor!")
    lines.append("Telegramdan yozing — linklarini tashlab beraman.")
    lines.append("")
    # ── Holati ──
    lines.append(f"• Holati: {cond_uz}")
    lines.append(f"• Состояние: {cond_ru}")
    lines.append("")
    # ── Narx (B5: sotilganini `status` ustuni aytadi) ──
    if is_sold(item):
        narx = price if price and price != '0' else old
        lines.append(f"Цена/Narxi: {narx}$ — SOTILDI ❗️" if narx else "Цена/Narxi: SOTILDI ❗️")
    elif old and old != price:
        lines.append(f"Цена/Narxi: ~~{old}$~~ {price}$")
    else:
        lines.append(f"Цена/Narxi: {price}$")
    lines.append("")
    lines.append("---")
    lines.append("")
    # ── Texnik xarakteristika ──
    lines.append("Texnik xarakteristika/Технические характеристики:")
    # Rang / Xotira (spec ichida ekran va h.k. bor)
    if color_uz:
        lines.append(f"• Rangi: {color_uz}")
    if storage:
        lines.append(f"• Xotira: {storage}")
    if spec_uz:
        lines.append(spec_uz)
    lines.append("")
    if color_ru:
        lines.append(f"• Цвет: {color_ru}")
    if storage:
        lines.append(f"• Память: {storage}")
    if spec_ru:
        lines.append(spec_ru)

    return f"{name_uz} ({storage})".strip(), "\n".join(lines).strip()


def send_elon(chat_id, text, entities):
    payload = {'chat_id': chat_id, 'text': text}
    if entities:
        payload['entities'] = entities
    try:
        r = req.post(f'{TG_API}/sendMessage', json=payload, timeout=10)
        return r.json()
    except Exception as e:
        logger.error(f'send_elon: {e}')
        return None


def send_elon_with_photos(chat_id, text, entities, images, reply_markup=None):
    """Rasm(lar) + caption yuboradi. 1 rasm -> sendPhoto, ko'p -> sendMediaGroup.
    Caption 1024 belgidan uzun bo'lsa -> rasm(lar) + alohida matn.
    Qaytaradi: {'message_id': ..., 'is_media_group': bool, 'text_message_id': ...}"""
    images = [u for u in (images or []) if u]
    CAP_LIMIT = 1024
    caption_fits = _utf16len(text) <= CAP_LIMIT

    # Rasm yo'q — oddiy matn
    if not images:
        payload = {'chat_id': chat_id, 'text': text}
        if entities:
            payload['entities'] = entities
        if reply_markup:
            payload['reply_markup'] = reply_markup
        try:
            r = req.post(f'{TG_API}/sendMessage', json=payload, timeout=10).json()
            mid = r.get('result', {}).get('message_id')
            return {'message_id': mid, 'is_media_group': False, 'text_message_id': mid}
        except Exception as e:
            logger.error(f'send_elon text: {e}')
            return None

    try:
        # Bitta rasm — sendPhoto (caption sig'sa) yoki rasm + alohida matn
        if len(images) == 1:
            if caption_fits:
                payload = {'chat_id': chat_id, 'photo': images[0], 'caption': text}
                if entities:
                    payload['caption_entities'] = entities
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                r = req.post(f'{TG_API}/sendPhoto', json=payload, timeout=15).json()
                mid = r.get('result', {}).get('message_id')
                return {'message_id': mid, 'is_media_group': False, 'text_message_id': mid}
            else:
                # Rasm alohida, matn alohida
                pr = req.post(f'{TG_API}/sendPhoto', json={'chat_id': chat_id, 'photo': images[0]}, timeout=15).json()
                tpayload = {'chat_id': chat_id, 'text': text}
                if entities:
                    tpayload['entities'] = entities
                if reply_markup:
                    tpayload['reply_markup'] = reply_markup
                tr = req.post(f'{TG_API}/sendMessage', json=tpayload, timeout=10).json()
                return {
                    'message_id': pr.get('result', {}).get('message_id'),
                    'is_media_group': False,
                    'text_message_id': tr.get('result', {}).get('message_id')
                }

        # Ko'p rasm — sendMediaGroup (grid). Caption 1-rasmga (agar sig'sa)
        # Media group tugma qo'ya olmaydi. Shuning uchun:
        #  - caption sig'sa VA tugma bo'lsa: rasmlarni caption bilan yuboramiz,
        #    keyin tugmani MATN xabariga emas — caption ostidagi oxirgi rasmga
        #    biriktirib bo'lmaydi, shuning uchun tugmani matn bilan birga yuboramiz.
        #  - Alohida bo'sh '👆' YUBORMAYMIZ (xunuk edi).
        media = []
        # Agar tugma bo'lsa, matnni media group caption'iga QO'YMAYMIZ — matn+tugmani
        # media group'dan keyin bitta xabar qilib yuboramiz (rasmlar tepada, matn+tugma pastda).
        put_caption_in_group = caption_fits and not reply_markup
        for i, url in enumerate(images[:10]):
            item = {'type': 'photo', 'media': url}
            if i == 0 and put_caption_in_group:
                item['caption'] = text
                if entities:
                    item['caption_entities'] = entities
            media.append(item)
        r = req.post(f'{TG_API}/sendMediaGroup', json={'chat_id': chat_id, 'media': media}, timeout=20).json()
        results = r.get('result', [])
        first_mid = results[0].get('message_id') if results else None

        text_mid = first_mid
        # Caption group'ga kirmagan bo'lsa (uzun YOKI tugma bor) — matn+tugmani alohida
        if not put_caption_in_group:
            tpayload = {'chat_id': chat_id, 'text': text}
            if entities:
                tpayload['entities'] = entities
            if reply_markup:
                tpayload['reply_markup'] = reply_markup
            tr = req.post(f'{TG_API}/sendMessage', json=tpayload, timeout=10).json()
            text_mid = tr.get('result', {}).get('message_id')

        return {'message_id': first_mid, 'is_media_group': True, 'text_message_id': text_mid}
    except Exception as e:
        logger.error(f'send_elon_with_photos: {e}')
        return None


# (edit_channel_post olib tashlandi — D2: kanal postini bot tahrirlamaydi,
#  admin qo'lda boshqaradi)


async def send_new_elons(chat_id, text):
    parts = text.split()
    listings, models = await blok(get_products)   # E1
    if listings is None:
        await blok(send_msg, chat_id, "❌ Sheets'dan ma'lumot olib bo'lmadi. SHEET_URL'ni tekshiring.")
        return

    models_by_id = {m.get('id'): m for m in (models or [])}

    # /elon 199  yoki  /elon 199 200 205  -> aniq raqamlar
    nums = [int(p) for p in parts[1:] if p.isdigit()]

    # B5/B6: o'chirilgan va chala e'lonlar HECH QACHON yuborilmaydi
    listings = [it for it in listings if elon_status(it) not in ('deleted', 'waited')]

    if nums:
        targets = [it for it in listings if int(float(it.get('num', 0) or 0)) in nums]
        targets.sort(key=lambda x: int(float(x.get('num', 0) or 0)))
        # Aniq raqamlar ichida sotilgani bo'lsa ogohlantiramiz (lekin yuboramiz — admin qarori)
        sold_nums = [int(float(it.get('num', 0) or 0)) for it in targets if is_sold(it)]
        if sold_nums:
            await blok(send_msg, chat_id, "⚠️ Sotilgan: " + ", ".join('#' + str(n) for n in sold_nums))
    else:
        # /yubor  ->  oxirgi yuborilgandan keyingi yangilar (sotilganlarni chiqarib tashlaymiz)
        last = _last_sent['num']
        targets = [it for it in listings
                   if int(float(it.get('num', 0) or 0)) > last and not is_sold(it)]
        targets.sort(key=lambda x: int(float(x.get('num', 0) or 0)))

    if not targets:
        await blok(send_msg, chat_id,
            f"ℹ️ Yangi elon yo'q. Oxirgi: #{_last_sent['num']}\n"
            f"Aniq raqam: <code>/elon 199</code>")
        return

    sent = 0
    max_num = _last_sent['num']
    for it in targets:
        num, etext, entities = build_elon(it, models_by_id)
        res = await blok(send_elon, chat_id, etext, entities)
        if res and res.get('ok'):
            sent += 1
            if num > max_num:
                max_num = num
        await asyncio.sleep(0.4)  # flood limit'dan saqlanish

    if not nums:
        _last_sent['num'] = max_num


def is_member(user_id):
    try:
        r = req.get(f'{TG_API}/getChatMember',
            params={'chat_id': CHANNEL, 'user_id': user_id}, timeout=6)
        status = r.json().get('result', {}).get('status', '')
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f'getChatMember: {e}')
        return False

def get_konkurs():
    import time
    now = time.time()
    if _konkurs_cache['data'] and now - _konkurs_cache['time'] < 120:
        return _konkurs_cache['data']
    if not SHEET_URL:
        return None
    try:
        r = req.get(f"{SHEET_URL}?action=getKonkurs&callback=d", timeout=10)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        if data and data.get('id'):
            _konkurs_cache['data'] = data
            _konkurs_cache['time'] = now
            return data
    except Exception as e:
        logger.error(f'get_konkurs: {e}')
    return None


# ═══════════════════════════════════════════════════════════════
# KONKURS AVTOMATIK TUGASH — aniq vaqtli timer (Apps Script polling O'RNIGA)
# Konkurs 'active' bo'lganda tugash vaqtiga aniq timer qo'yiladi. Vaqt kelganda
# bir marta g'olib aniqlanadi. Bot restart bo'lsa — startup'da qayta tiklanadi.
# Render doim yoqiq bo'lgani uchun ishonchli.
# ═══════════════════════════════════════════════════════════════
_konkurs_timer = {'task': None, 'id': None}   # joriy rejalashtirilgan timer
_ended_konkurslar = set()                     # shu ishga tushishda yakunlangan id'lar


def _parse_end_time(end_str):
    """end_time matnini UTC timestamp (soniya)ga aylantiradi.
    Ikki format bo'lishi mumkin:
      1) '...Z' bilan tugagan ISO satr (masalan '2026-07-08T16:10:00.000Z')
         — Apps Script Date->JSON konvertatsiyasi orqali keladi, bu ALLAQACHON
         to'g'ri UTC. QAYTA -5 soat QILINMAYDI.
      2) 'YYYY-MM-DD HH:MM[:SS]' (Z'siz, naive) — Toshkent vaqti (UTC+5) deb
         qabul qilinadi, -5 soat qilinadi.
    """
    if not end_str:
        return None
    s = str(end_str).strip()
    from datetime import datetime
    import calendar

    if s.endswith('Z'):
        s2 = s[:-1]
        for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
            try:
                dt = datetime.strptime(s2, fmt)
                return calendar.timegm(dt.timetuple())  # allaqachon UTC
            except Exception:
                continue
        return None

    s = s.replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            dt = datetime.strptime(s[:19] if len(s) >= 19 else s, fmt)
            return calendar.timegm(dt.timetuple()) - 5 * 3600
        except Exception:
            continue
    return None


async def _konkurs_end_worker(konkurs_id, delay):
    """delay soniyadan keyin konkursni tugatadi (Apps Script endKonkurs)."""
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        # Bitta konkurs FAQAT BIR MARTA yakunlanadi
        if konkurs_id in _ended_konkurslar:
            return
        _ended_konkurslar.add(konkurs_id)
        # Apps Script'da g'olibni aniqlaymiz
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, _end_konkurs_via_sheet, konkurs_id)
        if not (res and res.get('ok')):
            _ended_konkurslar.discard(konkurs_id)
        if res and res.get('ok'):
            # G'olib/maglub/kanal xabarlari (notify_participants)
            pics = res.get('_pics', [])
            await loop.run_in_executor(
                None, notify_participants,
                konkurs_id, '', '', res.get('_prize', ''), res.get('winners', []), pics)
            logger.info(f'Konkurs {konkurs_id} avtomatik tugadi')
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f'konkurs_end_worker: {e}')
    finally:
        if _konkurs_timer.get('id') == konkurs_id:
            _konkurs_timer['task'] = None
            _konkurs_timer['id'] = None


def _end_konkurs_via_sheet(konkurs_id):
    """Apps Script endKonkurs'ni chaqiradi, natijaga prize+pics qo'shadi."""
    try:
        r = req.get(f"{SHEET_URL}?action=endKonkurs&id={urllib.parse.quote(str(konkurs_id))}&callback=d", timeout=20)
        text = r.text.strip()
        res = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        if not (res and res.get('ok')):
            return None
        # Konkurs qatoridan prize + prizePicFileIds ni olamiz (kanal/g'olib rasmi uchun)
        k = get_konkurs_by_id(konkurs_id)
        if k:
            res['_prize'] = k.get('prize', '')
            fids = k.get('prizePicFileIds', '') or k.get('prizePics', '')
            res['_pics'] = [p.strip() for p in str(fids).split(',') if p.strip()]
        return res
    except Exception as e:
        logger.error(f'_end_konkurs_via_sheet: {e}')
        return None


def get_konkurs_by_id(konkurs_id):
    """Barcha konkurslardan id bo'yicha bittasini topadi."""
    try:
        r = req.get(f"{SHEET_URL}?action=getAllKonkurs&callback=d", timeout=10)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        arr = data if isinstance(data, list) else data.get('konkurslar', [])
        for k in arr:
            if str(k.get('id')) == str(konkurs_id):
                return k
    except Exception as e:
        logger.error(f'get_konkurs_by_id: {e}')
    return None


def schedule_konkurs_end(konkurs):
    """Aktiv konkursga tugash timerini qo'yadi (mavjudini almashtiradi)."""
    if not konkurs or not konkurs.get('id'):
        return
    kid = str(konkurs['id'])
    # Allaqachon yakunlangan konkursga timer qo'yilmaydi.
    # getKonkurs aktiv yo'q bo'lsa OXIRGI TUGAGAN konkursni qaytaradi — himoya shu yerda.
    if str(konkurs.get('status', '')).lower() == 'ended' or kid in _ended_konkurslar:
        return
    end_ts = _parse_end_time(konkurs.get('end_time'))
    if not end_ts:
        return  # muddatsiz konkurs — qo'lda tugatiladi
    import time
    delay = end_ts - time.time()
    # Tugash vaqti 1 soatdan ko'p oldin o'tgan (masalan Render o'chib qolgan) —
    # avtomatik yakunlamaymiz, aks holda eski konkurs qayta yakunlanadi
    if delay < -3600:
        logger.info(f'Konkurs {kid} muddati ancha oldin o\'tgan — avtomatik yakunlanmadi')
        return
    # Allaqachon shu konkurs rejalashtirilgan bo'lsa — qayta qo'ymaymiz
    if _konkurs_timer.get('id') == kid and _konkurs_timer.get('task'):
        return
    # Eski timerni bekor qilamiz
    old = _konkurs_timer.get('task')
    if old and not old.done():
        old.cancel()
    task = asyncio.create_task(_konkurs_end_worker(kid, max(0, delay)))
    _konkurs_timer['task'] = task
    _konkurs_timer['id'] = kid
    logger.info(f'Konkurs {kid} tugash timeri: {int(delay)}s keyin')


async def restore_konkurs_timer():
    """Bot ishga tushganda — aktiv konkurs bo'lsa timerni tiklaydi."""
    try:
        loop = asyncio.get_event_loop()
        k = await loop.run_in_executor(None, get_konkurs)
        if k and k.get('end_time'):
            schedule_konkurs_end(k)
    except Exception as e:
        logger.error(f'restore_konkurs_timer: {e}')


def save_participant(konkurs_id, user_id, username, phone, ism=''):
    if not SHEET_URL:
        return None
    try:
        data = json.dumps({
            'konkurs_id': str(konkurs_id),
            'user_id': str(user_id),
            'username': username or '',
            'ism': ism or '',
            'phone': str(phone),
        }, ensure_ascii=False)
        r = req.get(
            f"{SHEET_URL}?action=joinKonkurs&callback=d&data={urllib.parse.quote(data)}",
            timeout=12)
        text = r.text.strip()
        return json.loads(text[2:-1]) if text.startswith('d(') else r.json()
    except Exception as e:
        logger.error(f'save_participant: {e}')
        return None

def get_participants(konkurs_id):
    """Konkurs ishtirokchilari (telefon raqami bilan) — FAQAT API_KEY bilan.
    Kalit bo'lmasa Apps Script bo'sh ro'yxat qaytaradi (mijoz raqamlari yopiq)."""
    if not SHEET_URL:
        return []
    if not API_KEY:
        logger.error('get_participants: API_KEY yo\'q (Render env) — ro\'yxat olinmadi')
        return []
    try:
        r = req.get(
            f"{SHEET_URL}?action=getParticipants&callback=d"
            f"&id={urllib.parse.quote(str(konkurs_id))}"
            f"&key={urllib.parse.quote(API_KEY)}",
            timeout=15)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        if not data.get('ok'):
            logger.error(f"get_participants rad etildi: {data.get('msg')}")
        return data.get('participants', [])
    except Exception as e:
        logger.error(f'get_participants: {e}')
        return []


def purge_chat(user_id, count):
    """Chatga belgi xabar yuborib, undan OLDINGI `count` ta xabarni o'chiradi.
    Shaxsiy chatda message_id lar ketma-ket bo'lgani uchun ishlaydi.
    Belgi xabarning o'zi ham o'chiriladi. O'chirilgan eski xabarlar sonini qaytaradi."""
    try:
        r = req.post(f'{TG_API}/sendMessage',
                     json={'chat_id': user_id, 'text': '✨'}, timeout=10)
        mid = r.json().get('result', {}).get('message_id')
    except Exception as e:
        logger.error(f'purge send {user_id}: {e}')
        return 0
    if not mid:
        return 0
    n = 0
    for i in range(1, count + 1):
        try:
            d = req.post(f'{TG_API}/deleteMessage',
                         json={'chat_id': user_id, 'message_id': mid - i}, timeout=10)
            if d.json().get('ok'):
                n += 1
        except Exception:
            pass
    try:
        req.post(f'{TG_API}/deleteMessage',
                 json={'chat_id': user_id, 'message_id': mid}, timeout=10)
    except Exception:
        pass
    return n


async def handle_tozala(chat_id, text):
    """/tozala_test <user_id> <n> — bitta odamda sinash
       /tozala <n> [konkurs_id]   — barcha ishtirokchida (id'siz = hammasi)"""
    parts = text.split()
    try:
        if parts[0] == '/tozala_test':
            uid, cnt = parts[1], int(parts[2])
            n = await blok(purge_chat, uid, cnt)
            await blok(send_msg, chat_id, f"{uid}: {n} ta xabar o'chirildi.")
            return
        cnt = int(parts[1])
        kid = parts[2] if len(parts) > 2 else ''
    except (IndexError, ValueError):
        await blok(send_msg, chat_id, "Format: <code>/tozala_test 123456789 3</code> yoki <code>/tozala 3</code>")
        return

    ps = await blok(get_participants, kid)
    uids, seen = [], set()
    for p in ps:
        u = str(p.get('user_id', '')).strip()
        if u and u not in seen:
            seen.add(u)
            uids.append(u)
    await blok(send_msg, chat_id, f"{len(uids)} ta ishtirokchi — boshlandi...")
    total = 0
    for u in uids:
        total += await blok(purge_chat, u, cnt)
        await asyncio.sleep(0.4)
    await blok(send_msg, chat_id, f"Tugadi: {total} ta xabar o'chirildi.")


def not_member_msg(chat_id):
    send_msg(chat_id,
        "❗ <b>Konkursda qatnashish uchun kanalga a'zo bo'ling!</b>\n"
        "❗ <b>Для участия подпишитесь на канал!</b>",
        keyboard={"inline_keyboard": [
            [{"text": f"📢 {CHANNEL} ga a'zo bo'lish", "url": CHANNEL_LINK}],
            [{"text": "✅ A'zo bo'ldim — qatnashish", "callback_data": "check_member"}]
        ]})

async def start_konkurs_flow(chat_id, user):
    # E1: Sheets va Telegram so'rovlari alohida ipda — event loop to'xtamaydi
    k = await blok(get_konkurs)
    if not k:
        await blok(send_msg, chat_id, f"😕 Hozirda aktiv konkurs yo'q.\n\nKanalimizni kuzating: {CHANNEL}")
        return

    if not await blok(is_member, chat_id):
        await blok(not_member_msg, chat_id)
        return

    user_states[chat_id] = {
        'step': 'phone',
        'konkurs_id': k['id'],
        'prize': k.get('prize', ''),
        'user_id': user.get('id', chat_id),
        'username': user.get('username', ''),
    }

    await blok(send_msg, chat_id,
        f"🎁 <b>{html_escape(k.get('prize','Sovrin'))}</b>\n\n"
        f"🇺🇿 Konkursda qatnashish uchun telefon raqamingizni ulashing 👇\n"
        f"🇷🇺 Чтобы участвовать в розыгрыше, поделитесь номером телефона 👇",
        {
            "keyboard": [[{"text": "📱 Raqamni ulashish / Поделиться номером", "request_contact": True}]],
            "resize_keyboard": True, "one_time_keyboard": True
        })

async def handle_phone(chat_id, phone, user):
    # E2: matn telefon raqamiga o'xshamasa — QABUL QILMAYMIZ va holatni
    # saqlab qolamiz (mijoz qayta urinsin). Ilgari «salom» ham raqam bo'lib
    # Sheets'ga tushardi.
    if not _phone_ok(phone):
        await blok(send_msg, chat_id,
            "📱 Bu telefon raqamiga o'xshamadi.\n"
            "Pastdagi <b>«Raqamni ulashish»</b> tugmasini bosing yoki raqamni "
            "<code>+998901234567</code> ko'rinishida yozing.\n\n"
            "📱 Это не похоже на номер телефона.\n"
            "Нажмите кнопку <b>«Поделиться номером»</b> ниже или напишите номер "
            "в виде <code>+998901234567</code>.")
        return

    state = user_states.pop(chat_id, {})
    if not state:
        return

    if not await blok(is_member, chat_id):
        user_states[chat_id] = state          # a'zo bo'lgach qaytadan so'ramaymiz
        await blok(not_member_msg, chat_id)
        return

    username = state.get('username') or user.get('username', '')
    user_id = state.get('user_id', chat_id)
    konkurs_id = state.get('konkurs_id', '')
    # Ism (first_name + last_name) — g'olib username'siz bo'lsa ko'rsatish uchun
    ism = (user.get('first_name', '') or '').strip()
    _ln = (user.get('last_name', '') or '').strip()
    if _ln:
        ism = (ism + ' ' + _ln).strip()

    # ── DARROV javob: hech qanday Google so'rovini KUTMAYMIZ ──
    # Mijoz raqam berishi bilan tasdiqlash xabarini yuboramiz.
    await blok(req.post, f'{TG_API}/sendMessage', json={
        'chat_id': chat_id,
        'text': (
            "📲 <b>Deyarli tayyor! / Почти готово!</b>\n\n"
            "🇺🇿 Qatnashishni yakunlash uchun pastdagi tugmani bosing "
            "va saytda \"✅ Tasdiqlash\"ni bosing 👇\n"
            "🇷🇺 Чтобы завершить участие, нажмите кнопку ниже "
            "и нажмите \"✅ Подтвердить\" на сайте 👇"
        ),
        'parse_mode': 'HTML',
        'reply_markup': {
            "inline_keyboard": [[{
                "text": "✅ Saytda tasdiqlash / Подтвердить",
                "web_app": {"url": SAYT_URL + '?p=konkurs'}
            }]]
        }
    }, timeout=10)

    # ── FONDA: telefonni Sheets'ga yozamiz (g'olib aniqlash uchun ro'yxat). ──
    # Mijoz allaqachon javob oldi, bu yozish orqada ketadi — kechikish sezilmaydi.
    async def _save():
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, save_participant, konkurs_id, user_id, username, phone, ism)
            _konkurs_cache['time'] = 0
        except Exception as e:
            logger.error(f'bg save_participant: {e}')
    asyncio.create_task(_save())

def notify_participants(konkurs_id, winner_user_id, winner_username, prize, winners=None, pics=None):
    """Barcha qatnashuvchilarga xabar - g'oliblar va yutqazganlar.
    winners: [{user_id, username, prize}, ...] — ko'p g'olib ro'yxati.
    pics: konkurs sovrin rasmlari (file_id yoki url) — kanal postiga biriktiriladi."""
    participants = get_participants(konkurs_id)
    if not participants:
        logger.info('No participants to notify')
        return

    # G'oliblar xaritasi: user_id -> {o'rin, sovg'a}
    winners = winners or []
    win_map = {}
    for idx, w in enumerate(winners):
        wid = str(w.get('user_id', ''))
        if wid:
            win_map[wid] = {'place': idx + 1, 'prize': w.get('prize', '') or prize}
    # Agar winners bo'sh bo'lsa — eski (bitta g'olib) usul
    if not win_map and winner_user_id:
        win_map[str(winner_user_id)] = {'place': 1, 'prize': prize}

    # G'oliblar ro'yxati matni (yutqazgan va kanalga ko'rsatiladi) — username/ism link bilan
    medals = ['🥇', '🥈', '🥉']
    win_lines = []
    for idx, w in enumerate(winners):
        disp = winner_display(w)   # @username YOKI <a href="tg://user?id=">Ism</a>
        medal = medals[idx] if idx < 3 else f"{idx+1}."
        wp = w.get('prize', '')
        win_lines.append(f"{medal} {disp}" + (f" — {html_escape(wp)}" if wp else ""))
    win_text = "\n".join(win_lines) if win_lines else "—"

    # Rasm — g'olib/maglubga bitta (birinchi), kanalga hammasi
    pic_list = [p for p in (pics or []) if p]
    one_pic = pic_list[0] if pic_list else None

    def _send_photo_or_text(chat, caption, markup):
        """Rasm bo'lsa rasm+caption, bo'lmasa oddiy matn (HTML). Har biri xavfsiz."""
        try:
            if one_pic:
                r = req.post(f'{TG_API}/sendPhoto', json={
                    'chat_id': chat, 'photo': one_pic, 'caption': caption,
                    'parse_mode': 'HTML', 'reply_markup': markup
                }, timeout=15)
                if r.status_code == 200 and r.json().get('ok'):
                    return
            req.post(f'{TG_API}/sendMessage', json={
                'chat_id': chat, 'text': caption,
                'parse_mode': 'HTML', 'reply_markup': markup
            }, timeout=10)
        except Exception as e:
            logger.error(f'send to {chat}: {e}')

    def _notify_one(p):
        uid = str(p.get('user_id', ''))
        if not uid:
            return
        try:
            if uid in win_map:
                info = win_map[uid]
                place = info['place']
                my_prize = html_escape(info['prize'])
                medal = medals[place-1] if place <= 3 else f"{place}."
                cap = (
                    f"🏆 <b>Tabriklaymiz! Siz g'olib bo'ldingiz!</b> 🎊\n\n"
                    f"{medal} <b>{place}-o'rin</b> — <b>{my_prize}</b>\n\n"
                    f"🎁 Sovg'angizni olish uchun adminga yozing.\n"
                    f"🎁 Для получения приза напишите администратору."
                )
                _send_photo_or_text(uid, cap, {"inline_keyboard": [[{
                    "text": "📩 Adminga yozish / Написать админу",
                    "url": f"https://t.me/{ADMIN_USERNAME}"
                }]]})
            else:
                cap = (
                    f"🎁 <b>{html_escape(prize)}</b> konkursi yakunlandi!\n\n"
                    f"🏆 <b>G'oliblar / Победители:</b>\n{win_text}\n\n"
                    f"🎁 Ammo sizga <b>10$lik vaucher</b> sovg'a qilamiz!\n"
                    f"istalgan smartfonni tanlang va 10$ chegirma bilan xarid qiling. 🛒\n"
                    f"❗️Vaucher faqat 1 kun davomida amal qiladi.\n\n"
                    f"🎁 Но мы дарим вам <b>ваучер на 10$</b>!\n"
                    f"Выберите любой смартфон и получите скидку 10$ на покупку. 🛒\n"
                    f"❗️Ваучер действует только 1 день."
                )
                _send_photo_or_text(uid, cap, {"inline_keyboard": [[{
                    "text": "🛍 Smartfonlarni ko'rish / Смотреть смартфоны",
                    "web_app": {"url": SAYT_URL}
                }]]})
        except Exception as e:
            logger.error(f'notify {uid}: {e}')

    # PARALLEL: hammaga bir vaqtda (4-5 kishi 2-3 sekundda, ketma-ket emas)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(_notify_one, participants))

    # ── KANALGA (barcha rasmlar + g'oliblar matni + tugma) ──
    try:
        ch_text = (
            f"🎊 <b>KONKURS YAKUNLANDI!</b> 🎊\n"
            f"🎁 <b>{html_escape(prize)}</b>\n\n"
            f"🏆 <b>G'oliblar / Победители:</b>\n{win_text}\n\n"
            f"🇺🇿 G'oliblarni tabriklaymiz! Sovg'ani olish uchun admin bilan bog'laning.\n"
            f"🇷🇺 Поздравляем победителей! Для получения приза свяжитесь с админом.\n\n"
            f"📅 Har oy yangi konkurslar — kuzatib boring!"
        )
        markup = {"inline_keyboard": [[{
            "text": "🛍 Do'kon / Магазин",
            "url": "https://t.me/kraken_mobile_shop_bot?startapp"
        }]]}
        if pic_list:
            send_konkurs_channel_post(CHANNEL, ch_text, pic_list, markup)
        else:
            req.post(f'{TG_API}/sendMessage', json={
                'chat_id': CHANNEL, 'text': ch_text,
                'parse_mode': 'HTML', 'reply_markup': markup
            }, timeout=8)
    except Exception as e:
        logger.error(f'channel konkurs post: {e}')


def send_konkurs_channel_post(chat_id, text, images, reply_markup):
    """Konkurs natijasini kanalga yuboradi (HTML parse_mode):
    1 rasm  -> sendPhoto (caption + tugma birga)
    ko'p rasm -> sendMediaGroup (caption 1-rasmga) + tugma alohida qisqa xabar."""
    imgs = [i for i in (images or []) if i][:10]
    if not imgs:
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': reply_markup
        }, timeout=10)
        return
    caption_fits = len(text) <= 1000
    if len(imgs) == 1:
        r = req.post(f'{TG_API}/sendPhoto', json={
            'chat_id': chat_id, 'photo': imgs[0],
            'caption': text, 'parse_mode': 'HTML',
            'reply_markup': reply_markup
        }, timeout=15)
        if r.status_code == 200 and r.json().get('ok'):
            return
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': reply_markup
        }, timeout=10)
        return
    # Ko'p rasm — caption 1-rasmga biriktiriladi (matn+rasm birga)
    media = []
    for i, u in enumerate(imgs):
        item = {'type': 'photo', 'media': u}
        if i == 0 and caption_fits:
            item['caption'] = text
            item['parse_mode'] = 'HTML'
        media.append(item)
    req.post(f'{TG_API}/sendMediaGroup', json={'chat_id': chat_id, 'media': media}, timeout=20)
    if caption_fits:
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': '🛍', 'reply_markup': reply_markup
        }, timeout=10)
    else:
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': reply_markup
        }, timeout=10)


def tg_file_url(file_id):
    """Telegram file_id dan yuklab olinadigan URL qaytaradi."""
    try:
        fi = req.get(f'{TG_API}/getFile?file_id={file_id}', timeout=10).json()
        if fi.get('ok'):
            fp = fi['result']['file_path']
            return f'https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}'
    except Exception as e:
        logger.error(f'getFile: {e}')
    return ''


def upload_to_imagekit(file_id):
    """Telegram file_id'ni yuklab olib, ImageKit'ga yuboradi. Barqaror URL qaytaradi.
    Xato bo'lsa — Telegram URL'iga qaytadi (fallback)."""
    tg_url = tg_file_url(file_id)
    if not tg_url:
        return ''
    try:
        # 1) Telegram'dan rasmni yuklab olamiz
        img = req.get(tg_url, timeout=20)
        if img.status_code != 200:
            return tg_url
        # 2) ImageKit'ga yuklaymiz (Basic Auth: private_key username, parol bo'sh)
        import time as _t
        fname = f"{int(_t.time()*1000)}_{file_id[:8]}.jpg"
        r = req.post(
            IK_UPLOAD_URL,
            auth=(IK_PRIVATE_KEY, ''),
            files={'file': (fname, img.content)},
            data={'fileName': fname, 'folder': '/kraken'},
            timeout=30
        )
        j = r.json()
        if r.status_code == 200 and j.get('url'):
            return j['url']
        logger.error(f'ImageKit upload: {j}')
        return tg_url  # fallback
    except Exception as e:
        logger.error(f'upload_to_imagekit: {e}')
        return tg_url  # fallback


def create_bot_elon(file_ids):
    """Rasm(lar)dan chala elon yaratadi. file_id -> ImageKit URL -> Sheets."""
    urls = []
    for fid in file_ids:
        u = upload_to_imagekit(fid)
        if u:
            urls.append(u)
    if not urls:
        return None
    try:
        payload = urllib.parse.quote(json.dumps({'images': urls}))
        r = req.get(f'{SHEET_URL}?action=botCreateElon&data={payload}', timeout=20)
        res = r.json()
        return res if res.get('ok') else None
    except Exception as e:
        logger.error(f'create_bot_elon: {e}')
        return None


def finalize_photo_group(mgid, chat_id):
    """Albom to'planib bo'lgach chaqiriladi — chala elon yaratadi."""
    grp = _photo_groups.pop(mgid, None)
    if not grp:
        return
    file_ids = grp.get('file_ids', [])
    res = create_bot_elon(file_ids)
    if res:
        num = res.get('num', '?')
        cnt = res.get('images', len(file_ids))
        send_msg(chat_id,
            f"✅ Yangi elon yaratildi: <b>№{num}</b>\n"
            f"📸 {cnt} ta rasm saqlandi.\n\n"
            f"Endi saytdagi admin panelda ma'lumotlarini to'ldiring 👇",
            keyboard={"inline_keyboard": [[{
                "text": "🛠 Admin panel / Saytga kirish",
                "web_app": {"url": SAYT_URL}
            }]]})
    else:
        send_msg(chat_id, "❌ Elon yaratishda xatolik. Qayta urining.")


async def handle_konkurs_photo(chat_id, file_id, media_group_id=None):
    """#6.5: Admin konkurs rejimida rasm yuborsa — elon kabi GROUP qilib yig'adi,
    hammasi kelgach BITTADA javob beradi. Har rasm: file_id (kanalga yuborish uchun)
    + ImageKit URL (saytda ko'rsatish uchun) — ikkalasi Sheetsga saqlanadi."""
    if media_group_id:
        # Albom: rasmlarni yig'amiz, 2 sekund kutib, keyin bittada saqlaymiz
        key = f'konkurs_{media_group_id}'
        grp = _photo_groups.get(key)
        if not grp:
            grp = {'file_ids': [], 'chat_id': chat_id, 'is_konkurs': True}
            _photo_groups[key] = grp
        grp['file_ids'].append(file_id)
        old = grp.get('timer')
        if old:
            old.cancel()
        loop = asyncio.get_event_loop()
        # E1: call_later EVENT LOOP ipida ishlaydi. Ichida ImageKit va Sheets
        # so'rovlari bor — shuning uchun ish alohida ipga uzatiladi.
        grp['timer'] = loop.call_later(
            2.0, lambda: loop.run_in_executor(None, finalize_konkurs_photos, key, chat_id))
    else:
        # Bitta rasm — darrov
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _save_konkurs_photos, chat_id, [file_id])


def finalize_konkurs_photos(key, chat_id):
    """Albom to'planib bo'lgach — barcha konkurs rasmlarini bittada saqlaydi."""
    grp = _photo_groups.pop(key, None)
    if not grp:
        return
    file_ids = grp.get('file_ids', [])
    _save_konkurs_photos(chat_id, file_ids)


def _save_konkurs_photos(chat_id, file_ids):
    """Konkurs rasmlarini ImageKit'ga yuklaydi va BITTA 'waited' konkurs yaratadi
    (elon logikasi kabi): rasmlar bitta qatorga [,] bilan (prizePics), file_id'lar
    ham saqlanadi (25 kun kanalga yuborish uchun). Javobda 'admin panel' tugmasi."""
    if not file_ids:
        return
    urls = []
    fids = []
    for fid in file_ids:
        url = upload_to_imagekit(fid)
        if url:
            urls.append(url)
            fids.append(fid)
    if not urls:
        send_msg(chat_id, "❌ Rasm saqlashda xatolik. Qayta urining.")
        # rejimni yopamiz
        user_states.pop(chat_id, None)
        return
    # Bitta waited konkurs yaratamiz — rasmlar bitta qatorda vergul bilan
    try:
        payload = urllib.parse.quote(json.dumps({
            'prizePics': ','.join(urls),
            'prizePicFileIds': ','.join(fids)
        }))
        r = req.get(f'{SHEET_URL}?action=createWaitedKonkurs&data={payload}', timeout=15)
        ok = r.json().get('ok')
    except Exception as e:
        logger.error(f'createWaitedKonkurs: {e}')
        ok = False
    # Rejimni yopamiz (bir marta yig'ildi)
    user_states.pop(chat_id, None)
    if ok:
        send_msg(chat_id,
            f"✅ <b>{len(urls)} ta sovrin rasmi qabul qilindi!</b>\n\n"
            f"Admin panelda konkursni to'ldiring 👇",
            keyboard={"inline_keyboard": [[{
                "text": "⚙️ Admin panelni ochish",
                "web_app": {"url": SAYT_URL + "#admin"}
            }]]})
    else:
        send_msg(chat_id, "❌ Konkurs yaratishda xatolik. Qayta urining.")


async def handle_admin_photo(chat_id, file_id, media_group_id):
    """Admin rasm yuborsa — chala elon yaratadi.
    Albom (media group) bo'lsa, barcha rasmlar to'planguncha kutadi."""
    if media_group_id:
        # Albom: rasmlarni yig'amiz, 2 sekund kutib, keyin bitta elon qilamiz
        grp = _photo_groups.get(media_group_id)
        if not grp:
            grp = {'file_ids': [], 'chat_id': chat_id}
            _photo_groups[media_group_id] = grp
        grp['file_ids'].append(file_id)
        # Oldingi taymer bo'lsa bekor qilamiz, yangisini o'rnatamiz
        old = grp.get('timer')
        if old:
            old.cancel()
        loop = asyncio.get_event_loop()
        # E1: ish alohida ipda (ichida ImageKit + Sheets so'rovlari bor)
        grp['timer'] = loop.call_later(
            2.0, lambda: loop.run_in_executor(None, finalize_photo_group, media_group_id, chat_id))
    else:
        # Bitta rasm — darrov elon
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _single_photo_elon, chat_id, file_id)


def _single_photo_elon(chat_id, file_id):
    res = create_bot_elon([file_id])
    if res:
        num = res.get('num', '?')
        send_msg(chat_id,
            f"✅ Yangi elon yaratildi: <b>№{num}</b>\n"
            f"📸 1 ta rasm saqlandi.\n\n"
            f"Endi saytdagi admin panelda ma'lumotlarini to'ldiring 👇",
            keyboard={"inline_keyboard": [[{
                "text": "🛠 Admin panel / Saytga kirish",
                "web_app": {"url": SAYT_URL}
            }]]})
    else:
        send_msg(chat_id, "❌ Elon yaratishda xatolik. Qayta urining.")


# ══════════════════════════════════════════════════════════════════════════
#  BUGUN16 §1 (2026-09-25): INLINE REJIM — «@bot 248», «@bot pixel 10 pro xl»
#
#  Foydalanuvchi: «yuborishdan oldin rasmi chiqib tursin; kod yozmagan paytimda
#  esa barcha e'lonlar chiqib tursin va nomni yozsam ham nomi bilan chiqib
#  kelsin». Tanlanganda — KANALDAGI rich post (build_rich_html, premium=False —
#  kanal_post bilan bir xil matn, rasmlar tartibi bir xil).
#
#  🔴 TUZOQ: inline rich xabarda «Only previously uploaded files may be used» —
#  ImageKit URL ishlamaydi, Telegram file_id kerak. Shu sabab rasm bir marta
#  RASM_YUKLASH_CHAT ga ovozsiz yuboriladi, file_id olinadi, xabar DARROV
#  o'chiriladi. file_id xotirada (restartda qayta yuklanadi). Hali yuklanmagan
#  e'lon — oddiy rasm kartasi (_share_result) bilan chiqadi, keyingi so'rovda rich.
#  Yuklash faqat inline so'rov kelganda boshlanadi (BotFather'da yoqilmaguncha jim).
#  Ma'lumot — _ELON_CACHE (G10.3), jadvalga yozilmaydi.
# ══════════════════════════════════════════════════════════════════════════

INLINE_SAHIFA = 50            # Telegram: bitta javobda ≤ 50 natija
INLINE_KUTISH = 5.0           # rasm yuklanishini kutish (s) — so'ng tayyori rich, qolgani karta
RASM_YUKLASH_CHAT = ADMIN_ID  # SAVOL (BUGUN16 oxiri): admin lichkasi yoki TEST_CHANNEL
_RASM_XATO_KUTISH = 3600      # yuklanmagan rasm 1 soat qayta urinilmaydi
_RASM_FID = {}                # rasm URL → Telegram file_id
_RASM_XATO = {}               # rasm URL → yuklanmagan vaqti
_rasm_navbat = []             # yuklash navbati (URL)
_rasm_kutilmoqda = set()      # navbatda yoki yuklanayotgan URL'lar
_rasm_ishchi = {'bor': False}
_rasm_lock = threading.Lock()


def _inline_norm(s):
    """Qidiruv uchun: kichik harf, bo'shliq/tinish belgisiz («Pixel 10 Pro XL» = «pixel10proxl»)."""
    return re.sub(r'[\W_]+', '', str(s or '').lower())


def inline_nomlari(elon, models):
    """E'lonning qidiriladigan nomlari — o'z nomi va model nomi, uz va ru."""
    model = (models or {}).get(str(elon.get('specId', '') or ''), {})
    return [elon_nomi(elon, model, 'uz'), elon_nomi(elon, model, 'ru'),
            model_display_name(model, 'uz'), model_display_name(model, 'ru')]


def _elon_vaqti(elon):
    v = str(elon.get('created', '') or '').strip()
    if not v:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(v.replace('Z', '+00:00')).timestamp()
    except Exception:
        return 0.0


def _num_int(elon):
    try:
        return int(float(elon.get('num', 0) or 0))
    except (ValueError, TypeError):
        return 0


def inline_topish(query, by_num, models):
    """So'rov bo'yicha FAOL e'lonlar (yangisi birinchi). Sotilgan/o'chirilgan/kutilayotgan — yo'q.
    '' — hammasi; '248' / '#248' / '№248' — shu raqamli e'lon BIRINCHI, keyin nomida shu son borlari
    («15» — №15 va iPhone 15'lar); matn — nomida HAMMA so'zlar bor e'lonlar (harf katta-kichikligi,
    uz/ru, bo'shliq farqsiz)."""
    faol = [e for e in (by_num or {}).values() if isinstance(e, dict) and elon_status(e) == 'active']
    faol.sort(key=lambda e: (_elon_vaqti(e), _num_int(e)), reverse=True)
    q = str(query or '').strip()
    birinchi = []
    m = re.fullmatch(r'[#№]\s*(\d{1,6})|(\d{1,6})', q)
    if m:
        raqam = int(m.group(1) or m.group(2))
        birinchi = [e for e in faol if _num_int(e) == raqam]
        if m.group(1):                  # «#248» — faqat raqam
            return birinchi
    sozlar = [w for w in (_inline_norm(s) for s in q.split()) if w]
    if not sozlar:
        return faol
    natija = list(birinchi)
    for e in faol:
        if any(e is b for b in birinchi):
            continue
        nomlar = [_inline_norm(n) for n in inline_nomlari(e, models) if n]
        if any(all(w in n for w in sozlar) for n in nomlar):
            natija.append(e)
    return natija


def _ik_olcham(url, tr):
    """ImageKit rasmiga o'lcham (tr=…) qo'shadi; boshqa manzil o'zgarmaydi."""
    if 'ik.imagekit.io' in url and 'tr=' not in url:
        return url + ('&' if '?' in url else '?') + 'tr=' + tr
    return url


def _rasm_fid(xabar):
    """Xabardagi eng katta rasmning file_id si."""
    rasmlar = (xabar or {}).get('photo') or []
    return rasmlar[-1].get('file_id') if rasmlar else None


def _rasm_tg(metod, payload):
    """Telegram so'rovi; 429 da kutib BIR marta qayta uradi. Javob (dict)."""
    for urinish in range(2):
        try:
            r = req.post(f'{TG_API}/{metod}', json=payload, timeout=60).json()
        except Exception as ex:
            return {'ok': False, 'description': f'tarmoq: {ex}'}
        kut = ((r.get('parameters') or {}).get('retry_after')) if not r.get('ok') else None
        if kut and urinish == 0:
            time.sleep(min(float(kut), 30))
            continue
        return r
    return r


def _rasm_yubor(guruh):
    """≤10 rasmni RASM_YUKLASH_CHAT ga ovozsiz yuboradi, file_id'larni oladi, xabarlarni o'chiradi."""
    if len(guruh) == 1:
        r = _rasm_tg('sendPhoto', {'chat_id': RASM_YUKLASH_CHAT, 'photo': _ik_olcham(guruh[0], 'w-1600,q-85'),
                                   'disable_notification': True})
        xabarlar = [r.get('result')] if r.get('ok') else None
    else:
        r = _rasm_tg('sendMediaGroup', {'chat_id': RASM_YUKLASH_CHAT, 'disable_notification': True,
                                        'media': [{'type': 'photo', 'media': _ik_olcham(u, 'w-1600,q-85')} for u in guruh]})
        xabarlar = r.get('result') if r.get('ok') else None
    if not xabarlar:
        if len(guruh) > 1:
            for u in guruh:             # bitta buzuq rasm butun albomni yiqitadi — bittalab
                _rasm_yubor([u])
            return
        logger.warning(f"inline rasm yuklanmadi: {guruh[0]} — {r.get('description')}")
        _RASM_XATO[guruh[0]] = time.time()
        return
    for u, x in zip(guruh, xabarlar):
        fid = _rasm_fid(x)
        if fid:
            _RASM_FID[u] = fid
            _RASM_XATO.pop(u, None)
        else:
            _RASM_XATO[u] = time.time()
    ids = [x.get('message_id') for x in xabarlar if isinstance(x, dict) and x.get('message_id')]
    if ids:
        _rasm_tg('deleteMessages', {'chat_id': RASM_YUKLASH_CHAT, 'message_ids': ids})


def _rasm_ishchi_ish():
    """Fon ipi: navbatdagi rasmlarni 10 tadan yuklaydi (webhook'ni to'xtatmaydi — T1)."""
    while True:
        with _rasm_lock:
            guruh = _rasm_navbat[:10]
            del _rasm_navbat[:10]
            if not guruh:
                _rasm_ishchi['bor'] = False
                return
        try:
            _rasm_yubor(guruh)
        except Exception as ex:
            logger.error(f'inline rasm ishchisi: {ex}')
            for u in guruh:
                if u not in _RASM_FID:
                    _RASM_XATO[u] = time.time()
        finally:
            with _rasm_lock:
                _rasm_kutilmoqda.difference_update(guruh)
        time.sleep(1.0)                 # Telegram cheklovi — bir chatga tez-tez yubormaslik


def rasm_navbatga(urls, ishga=True):
    """file_id'i yo'q rasmlarni navbatning BOSHIGA qo'yadi (hozir so'ralgani birinchi)."""
    hozir = time.time()
    yangi = []
    for u in urls:
        if u in _RASM_FID or u in _rasm_kutilmoqda or u in yangi:
            continue
        if hozir - _RASM_XATO.get(u, 0) < _RASM_XATO_KUTISH:
            continue
        yangi.append(u)
    if not yangi:
        return
    with _rasm_lock:
        yangi = [u for u in yangi if u not in _rasm_kutilmoqda]
        _rasm_kutilmoqda.update(yangi)
        _rasm_navbat[:0] = yangi
        boshlash = ishga and not _rasm_ishchi['bor']
        if boshlash:
            _rasm_ishchi['bor'] = True
    if boshlash:
        threading.Thread(target=_rasm_ishchi_ish, daemon=True).start()


def inline_natija(elon, models):
    """Bitta e'lon — inline natija. Hamma rasmi yuklangan bo'lsa KANAL rich posti, aks holda rasm kartasi."""
    num = _num_int(elon)
    model = (models or {}).get(str(elon.get('specId', '') or ''), {})
    rasmlar = images_of(elon)[:10]
    nom = elon_nomi(elon, model, 'uz')
    xotira = str(elon.get('storage') or '').strip()
    rang = clean_color(elon.get('color') or '')
    sarlavha = nom + (f' ({xotira})' if xotira else '') + (f' {rang}' if rang else '')
    narx = str(elon.get('price', '') or '').replace('.0', '')
    cycle = str(elon.get('cycle', '') or '').replace('.0', '')
    cond_uz, _cond_ru, _emoji = holati_matni(elon.get('condition', 'used') or 'used', cycle)
    izoh = ' · '.join(x for x in ((f'{narx}$' if narx else ''), cond_uz, f'№{num}') if x)

    if rasmlar and all(u in _RASM_FID for u in rasmlar):
        src = {u: f'tg://photo?id=r{i}' for i, u in enumerate(rasmlar)}
        return {
            'type': 'article',
            'id': f'r{num}',
            'title': sarlavha,
            'description': izoh,
            'thumbnail_url': _ik_olcham(rasmlar[0], 'w-200,q-70'),
            'input_message_content': {'rich_message': {
                'html': build_rich_html(elon, models, premium=False, rasm_src=src),
                'media': [{'id': f'r{i}', 'media': {'type': 'photo', 'media': _RASM_FID[u]}}
                          for i, u in enumerate(rasmlar)],
            }},
        }
    karta = _share_result(num, elon, model)
    if karta:
        karta['title'] = sarlavha
        karta['description'] = izoh
    return karta


def elon_cache_hammasi():
    """(by_num nusxasi, models) — xotira hech yuklanmagan bo'lsa bir urinish (60 s da bir)."""
    c = _ELON_CACHE
    if not c['time'] and time.time() - c['last_try'] > 60:
        elon_cache_load()
    with _elon_cache_lock:
        return dict(c['by_num']), c['models']


async def inline_javob(iq):
    """inline_query → answerInlineQuery (sahifa 50 tadan, next_offset bilan)."""
    try:
        by_num, models = await blok(elon_cache_hammasi)
        topildi = inline_topish(iq.get('query', ''), by_num, models)
        try:
            boshi = max(0, int(iq.get('offset') or 0))
        except ValueError:
            boshi = 0
        sahifa = topildi[boshi:boshi + INLINE_SAHIFA]
        keyingi = str(boshi + INLINE_SAHIFA) if boshi + INLINE_SAHIFA < len(topildi) else ''

        urls = [u for e in sahifa for u in images_of(e)[:10]]
        rasm_navbatga(urls)
        oxiri = time.monotonic() + INLINE_KUTISH
        while any(u in _rasm_kutilmoqda for u in urls) and time.monotonic() < oxiri:
            await asyncio.sleep(0.25)

        natijalar = [n for n in (inline_natija(e, models) for e in sahifa) if n]
        hammasi_rich = all(n.get('type') == 'article' for n in natijalar)
        r = await blok(req.post, f'{TG_API}/answerInlineQuery', json={
            'inline_query_id': iq.get('id'),
            'results': natijalar,
            'next_offset': keyingi,
            'cache_time': 30 if hammasi_rich else 0,   # karta bo'lsa keyingi so'rovda rich chiqsin
            'is_personal': False,
        }, timeout=15)
        # Rich natija rad etilsa (hali jonli sinalmagan) — ro'yxat bo'sh qolmasin: shu so'rovga faqat kartalar
        javob = r.json() if hasattr(r, 'json') else {}
        if not javob.get('ok') and any(n.get('type') == 'article' for n in natijalar):
            logger.error(f"inline rich rad etildi: {javob.get('description')} — kartalar bilan qayta")
            kartalar = [k for k in (_share_result(_num_int(e), e, (models or {}).get(str(e.get('specId', '') or ''), {}))
                                    for e in sahifa) if k]
            await blok(req.post, f'{TG_API}/answerInlineQuery', json={
                'inline_query_id': iq.get('id'), 'results': kartalar, 'next_offset': keyingi,
                'cache_time': 0, 'is_personal': False,
            }, timeout=15)
    except Exception as ex:
        logger.error(f'inline_javob: {ex}')


async def webhook(request):
    """🔴 QOIDALAR T1: Telegram'ga DARROV 200 qaytariladi.

    Butun ish fonda (`asyncio.create_task`) bajariladi. Ilgari ish tugamaguncha
    javob berilmasdi: Sheets sekin bo'lsa Telegram javobni kutmay xabarni qayta
    yuborardi va ish ikki marta bajarilardi.
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f'webhook json: {e}')
        return web.json_response({'ok': True})
    asyncio.create_task(handle_update(data))
    return web.json_response({'ok': True})


async def handle_update(data):
    try:
        # BUGUN16 §1: «@bot …» — inline rejim
        if data.get('inline_query'):
            await inline_javob(data['inline_query'])
            return

        # BUGUN6 §2: kanalga yangi a'zo → faqat o'ziga ko'rinadigan xush kelibsiz (fonda — T1)
        if data.get('chat_member'):
            asyncio.create_task(blok(kanal_xush_kelibsiz, data['chat_member']))
            return

        message = data.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        contact = message.get('contact')

        cq = data.get('callback_query', {})
        if cq:
            cq_chat = cq.get('message', {}).get('chat', {}).get('id')
            cq_user = cq.get('from', {})
            cq_data = cq.get('data', '')
            cq_id = cq.get('id')
            await blok(req.post, f'{TG_API}/answerCallbackQuery',
                       json={'callback_query_id': cq_id}, timeout=5)
            if cq_data == 'check_member' and cq_chat:
                if await blok(is_member, cq_chat):
                    await start_konkurs_flow(cq_chat, cq_user)
                else:
                    await blok(send_msg, cq_chat,
                        "❌ Hali a'zo emassiz! Avval kanalga a'zo bo'ling.",
                        {"inline_keyboard": [
                            [{"text": "📢 Kanalga a'zo bo'lish", "url": CHANNEL_LINK}],
                            [{"text": "✅ A'zo bo'ldim", "callback_data": "check_member"}]
                        ]})
            # G11.2: /toplam va /katalog tasdiqi (faqat admin lichkasi)
            if cq_data.startswith(('kanal_ok:', 'kanal_no:')) and cq_chat == ADMIN_ID:
                asyncio.create_task(blok(kanal_tasdiq, cq_chat, cq_data.split(':', 1)[1], cq_data.startswith('kanal_ok:')))
            return

        if not chat_id:
            return

        # BUGUN10 §3b: admin «🔔 Yangi istak» xabariga reply qilsa — javob mijozga (rasm-e'lon yasashdan OLDIN
        # tekshiriladi: istakka rasm bilan javob chala e'lon bo'lib qolmasin). Buyruqlar (/…) — eski yo'lda. Fonda (T1).
        if chat_id == ADMIN_ID and message.get('reply_to_message') and not text.startswith('/'):
            manzil = istak_javob_manzil(message.get('reply_to_message'))
            if manzil:
                asyncio.create_task(blok(istak_javob_yubor, chat_id, message, manzil))
                return

        # ── ADMIN rasm yuborsa ──
        photo = message.get('photo')
        if photo and chat_id == ADMIN_ID:
            largest = photo[-1]  # eng katta o'lcham
            file_id = largest.get('file_id', '')
            mgid = message.get('media_group_id')
            # #6.5: Konkurs sovrin rasmi rejimida bo'lsa — elon emas, sovrin rasmi saqlaymiz
            st = user_states.get(chat_id, {})
            if st.get('step') == 'konkurs_photo':
                await handle_konkurs_photo(chat_id, file_id, mgid)
                return
            # Aks holda — eski logika: chala elon yaratamiz
            await handle_admin_photo(chat_id, file_id, mgid)
            return

        if text.startswith('/yubor') or text.startswith('/elon'):
            if chat_id != ADMIN_ID:
                return
            await send_new_elons(chat_id, text)
            return

        # G11.0: Rich Message sinovi — faqat admin, faqat lichka + TEST kanal. Fonda (T1).
        if text.startswith('/richtest') and chat_id == ADMIN_ID:
            m_num = re.search(r'\d{1,6}', text)
            if not m_num:
                await blok(send_msg, chat_id, "Foydalanish: /richtest 248")
                return
            asyncio.create_task(blok(richtest, chat_id, m_num.group(0)))
            return

        # G11.2: kanal buyruqlari (admin). Fonda (T1).
        if chat_id == ADMIN_ID and text.split(' ')[0] in ('/toplam', '/katalog', '/post', '/yana', '/postochir'):
            cmd = text.split(' ')[0]
            m_num = re.search(r'\d{1,6}', text[len(cmd):])
            if cmd == '/toplam':
                asyncio.create_task(blok(kanal_taklif, chat_id, 'toplam'))
            elif cmd == '/katalog':
                asyncio.create_task(blok(kanal_taklif, chat_id, 'katalog'))
            elif not m_num:
                await blok(send_msg, chat_id, f"Foydalanish: {cmd} 248")
            else:
                asyncio.create_task(kanal_buyruq(chat_id, cmd, m_num.group(0)))
            return

        # F1: do'kon hisoboti. Fonda — Sheets hisobi sekin, webhook kutmasin (T1).
        if text.startswith('/stat') and chat_id == ADMIN_ID:
            asyncio.create_task(handle_stat(chat_id, text))
            return

        if text.startswith('/tozala') and chat_id == ADMIN_ID:
            # Fonda ishlaydi — Telegram javobni kutmasin (aks holda buyruqni qayta yuboradi)
            asyncio.create_task(handle_tozala(chat_id, text))
            return

        if text.startswith('/start'):
            parts = text.split(' ', 1)
            deep = parts[1].strip() if len(parts) > 1 else ''
            if deep == 'konkurs':
                await start_konkurs_flow(chat_id, user)
            else:
                await blok(send_start, chat_id)

        elif text == '/konkurs':
            # ADMIN: sovrin rasmi yig'ish rejimi (hech narsa demay rasm kutadi).
            # Oddiy mijoz: konkursda qatnashish flow'i.
            if chat_id == ADMIN_ID:
                user_states[chat_id] = {'step': 'konkurs_photo'}
                # Javob matni YO'Q — bot jimgina rasm kutadi (docx #9)
            else:
                await start_konkurs_flow(chat_id, user)

        elif text == '/konkursyuborish' and chat_id == ADMIN_ID:
            # ADMIN: aktiv konkurs anonsini kanalga yuboradi.
            _konkurs_cache['time'] = 0
            k = await blok(get_konkurs)
            if not k or not k.get('id'):
                await blok(send_msg, chat_id, "😕 Hozirda aktiv konkurs yo'q.")
            else:
                prize = html_escape(k.get('prize', 'Konkurs'))
                # prizes: JSON array (["...","..."]) yoki vergulli matn
                raw = k.get('prizes', '') or ''
                items = []
                if raw:
                    try:
                        parsed = json.loads(raw) if isinstance(raw, str) else raw
                        if isinstance(parsed, list):
                            items = [str(x).strip() for x in parsed if str(x).strip()]
                    except Exception:
                        # [ va ] qavslarni olib tashlab, vergul bo'yicha bo'lamiz
                        cleaned = str(raw).strip().lstrip('[').rstrip(']')
                        items = [s.strip().strip('"').strip("'") for s in cleaned.split(',') if s.strip()]
                # 1-3 medal, 4-5 raqam
                marks = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']
                # Sana: ISO (UTC) -> Toshkent (UTC+5), "25.07.2026 20:00"
                def _fmt_end(s):
                    try:
                        from datetime import datetime, timedelta
                        d = datetime.strptime(str(s)[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=5)
                        return d.strftime('%d.%m.%Y %H:%M')
                    except Exception:
                        return str(s)
                lines = [f"🎊 <b>{prize}</b> konkursga start berdik! 🎊", ""]
                if items:
                    lines.append("🎁 Sovg'alar:")
                    for i, it in enumerate(items[:5]):
                        lines.append(f"{marks[i]} {html_escape(it)}")
                    lines.append("")
                lines.append(f"⏰ Konkurs tugashi: {_fmt_end(k.get('end_time', ''))}")
                lines.append("")
                lines.append("Hoziroq qatnashing 👇")
                anons = "\n".join(lines)
                # Rasmlar: yig'ilgan sovrin rasmlari
                pics = []
                praw = k.get('prizePics', '') or ''
                if praw:
                    pics = [p.strip() for p in str(praw).split(',') if p.strip()]
                markup = {"inline_keyboard": [[{
                    "text": "🎁 Konkursda qatnashish",
                    "url": f"https://t.me/{BOT_USERNAME}?startapp=konkurs"
                }]]}
                await blok(send_konkurs_channel_post, CHANNEL, anons, pics, markup)
                await blok(send_msg, chat_id, "✅ Konkurs anonsi kanalga yuborildi!")

        elif text == '/konkurstimer' and chat_id == ADMIN_ID:
            # Admin zaxira: aktiv konkurs timerini qayta o'rnatadi + holatni ko'rsatadi
            _konkurs_cache['time'] = 0
            k = await blok(get_konkurs)
            if k and k.get('end_time'):
                schedule_konkurs_end(k)
                await blok(send_msg, chat_id,
                    f"✅ Aktiv konkurs topildi.\n"
                    f"🎁 {k.get('prize','')}\n"
                    f"⏰ Tugash: {k.get('end_time','')}\n"
                    f"⏳ Timer o'rnatildi — vaqti kelganda avtomatik tugaydi.")
            else:
                await blok(send_msg, chat_id, "ℹ️ Hozircha aktiv konkurs yo'q (yoki tugash vaqti belgilanmagan).")

        elif contact:
            # E3: bot qayta yonganda `user_states` yo'qoladi. Ilgari mijoz raqam
            # ulashsa bot JIM qolardi. Endi holat aktiv konkursdan tiklanadi.
            if chat_id not in user_states and not await tiklash_holati(chat_id, user):
                await blok(send_msg, chat_id,
                    "😕 Hozirda aktiv konkurs yo'q.\n"
                    "😕 Сейчас нет активного розыгрыша.")
                return
            await handle_phone(chat_id, contact.get('phone_number', ''), user)

        elif text and chat_id in user_states and user_states[chat_id].get('step') != 'konkurs_photo':
            # Admin konkurs rasm rejimida matn yozsa — telefon deb qabul qilmaymiz
            await handle_phone(chat_id, text, user)

        elif text and not text.startswith('/'):
            # F5: «№199» / «199» — e'lon kartasi
            elon_num = _elon_num_from_text(text)
            if elon_num:
                await blok(send_elon_card, chat_id, elon_num)
            elif _phone_ok(text) and await tiklash_holati(chat_id, user):
                # E3: mijoz raqamni QO'LDA yozgan (tugmasiz) va aktiv konkurs bor
                await handle_phone(chat_id, text, user)
            else:
                # E4: noma'lum xabar — ilgari bot umuman javob bermasdi
                await blok(send_msg, chat_id, NOMALUM_XABAR, START_KB)
    except Exception as e:
        logger.error(f'handle_update: {e}')


# E4: noma'lum xabarga javob. Mijoz botga yozsa hech narsa kelmasligi — eng
# yomon taassurot: «bot ishlamayapti» degani.
NOMALUM_XABAR = (
    "🇺🇿 Tushunmadim 🙂 Smartfonlarni ko'rish uchun pastdagi tugmani bosing.\n"
    "E'lon raqamini yozsangiz (masalan <b>199</b>) — o'sha e'lonni ko'rsataman.\n"
    "Konkurs uchun: /konkurs\n\n"
    "🇷🇺 Не понял 🙂 Нажмите кнопку ниже, чтобы посмотреть смартфоны.\n"
    "Напишите номер объявления (например <b>199</b>) — покажу его.\n"
    "Розыгрыш: /konkurs"
)


def _phone_ok(s):
    """Matn telefon raqamiga o'xshaydimi (E2).

    Ilgari `handle_phone` ISTALGAN matnni raqam deb qabul qilardi: «salom» ham
    Sheets'ga ishtirokchi telefoni bo'lib tushardi va g'olib aniqlashda o'sha
    qator chiqardi.
    """
    t = str(s or '').strip()
    if not t or len(t) > 25:
        return False
    if not re.fullmatch(r'\+?[\d\s\-()]{9,25}', t):
        return False
    return len(re.sub(r'\D', '', t)) >= 9


def _elon_num_from_text(s):
    """«199», «№199», «#199» → 199. Aks holda None (F5)."""
    m = re.fullmatch(r'\s*[№#]?\s*(\d{1,6})\s*', str(s or ''))
    return m.group(1) if m else None


async def tiklash_holati(chat_id, user):
    """E3: aktiv konkursdan `user_states` ni tiklaydi. Konkurs yo'q — False."""
    if chat_id in user_states:
        return True
    k = await blok(get_konkurs)
    if not k or not k.get('id'):
        return False
    user_states[chat_id] = {
        'step': 'phone',
        'konkurs_id': k['id'],
        'prize': k.get('prize', ''),
        'user_id': user.get('id', chat_id),
        'username': user.get('username', ''),
    }
    return True

def fetch_elon_by_num(num):
    """Sheets'dan bitta elon + modellar ma'lumotini oladi."""
    try:
        r = req.get(f'{SHEET_URL}?action=getElon&num={num}', timeout=15).json()
        if r.get('ok'):
            return r.get('elon'), r.get('models_by_id', {})
    except Exception as e:
        logger.error(f'fetch_elon_by_num: {e}')
    return None, {}


def preview_elon_to_admin(num, admin_chat):
    """«Menga yuborish»: bot e'lonni FAQAT adminga (lichkaga) yuboradi:
      1) OLX matni — nusxalab OLX'ga joylash uchun
      2) Kanal eloni — rasm(lar) + premium emoji bilan (kanalga qo'lda joylash uchun)

    Kanalga hech narsa yuborilmaydi. D2 qarori (2026-09-04): avtomatik kanal
    tizimi QAYTARILMADI — kanalni admin qo'lda boshqaradi, chunki bot edit
    qilganda kanaldagi premium emoji yo'qoladi. Shu sabab
    publish_elon_to_channel / update_channel_elon / save_channel_msg_id
    funksiyalari butunlay olib tashlandi (o'lik kod qoldirilmaydi).

    Funksiya SINXRON — `blok()` orqali alohida ipda chaqiriladi (E1).
    """
    elon, models = fetch_elon_by_num(num)
    if not elon:
        send_msg(admin_chat, f"❌ №{num} elon topilmadi.")
        return
    _, text, entities = build_elon(elon, models)   # premium emoji lichkaga chiqadi
    images = elon.get('images', [])
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []

    # ── 1) OLX MATNI (avval — #5) ──
    _, olx_text = build_olx_text(elon, models)
    try:
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': admin_chat,
            'text': "🟢 OLX UCHUN MATN — nusxalab OLX'ga joylang 👇",
        }, timeout=8)
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': admin_chat,
            'text': olx_text,
        }, timeout=10)
    except Exception as e:
        logger.error(f'OLX send: {e}')

    # ── 2) KANAL ELONI (keyin — premium emoji bilan, forward/joylash uchun) ──
    send_msg(admin_chat, "📋 <b>KANAL ELONI</b> — Kanalga joylashingiz mumkin 👇")
    res = send_elon_with_photos(admin_chat, text, entities, images)
    if not res:
        send_msg(admin_chat, "❌ Kanal elonini yuborishda xatolik.")


# F5: mijoz «199» yoki «№199» deb yozsa — o'sha e'lonning kartasi + tugma.
# Kanaldan kelgan mijoz uchun eng qisqa yo'l: raqamni ko'rdi → botga yozdi →
# rasm, narx va «Saytda ochish» tugmasi keldi.
def send_elon_card(chat_id, num):
    elon, models = fetch_elon_by_num(num)
    holat = elon_status(elon) if elon else 'deleted'
    if not elon or holat in ('deleted', 'waited'):
        send_msg(chat_id,
            f"🔍 №{num} e'lon topilmadi.\n"
            f"🔍 Объявление №{num} не найдено.",
            START_KB)
        return
    model = models.get(str(elon.get('specId', '')), {}) if isinstance(models, dict) else {}
    nom = html_escape(elon_nomi(elon, model, 'uz'))   # G12: e'lonning o'z nomi
    xotira = html_escape(str(elon.get('storage', '') or ''))
    rang = html_escape(clean_color(elon.get('color', '')))
    narx = str(elon.get('price', '') or '').replace('.0', '')
    cond_uz, cond_ru, cond_emoji = holati_matni(elon.get('condition', 'used'),
                                                str(elon.get('cycle', '') or '').replace('.0', ''))
    qatorlar = [f"📱 <b>{nom}</b>" + (f" ({xotira})" if xotira else '') + (f" {rang}" if rang else ''),
                f"№{num}",
                '']
    qatorlar.append(f"{cond_emoji} {cond_uz} / {cond_ru}")
    if holat == 'sold':
        qatorlar.append("❗️ <b>QOLMADI / НЕТ В НАЛИЧИИ</b>" if kop_donali(elon) else "❗️ <b>SOTILDI / ПРОДАНО</b>")
    else:
        qatorlar.append(f"💰 <b>{narx}$</b>")
        if soni_qatori(elon):
            qatorlar.append(soni_qatori(elon))   # B13: «📦 5 dona bor / 5 шт.»
    matn = "\n".join(qatorlar)

    images = elon.get('images', [])
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []
    kb = {"inline_keyboard": [[{
        "text": "🛍 Saytda ochish / Открыть на сайте",
        "url": f"https://t.me/{BOT_USERNAME}?startapp=elon_{num}"
    }]]}
    rasm = images[0] if images else ''
    if rasm:
        try:
            r = req.post(f'{TG_API}/sendPhoto', json={
                'chat_id': chat_id, 'photo': rasm, 'caption': matn,
                'parse_mode': 'HTML', 'reply_markup': kb
            }, timeout=15)
            if r.status_code == 200 and r.json().get('ok'):
                return
        except Exception as e:
            logger.error(f'send_elon_card photo: {e}')
    send_msg(chat_id, matn, kb)


async def konkurs_started_endpoint(request):
    """Sayt konkursni 'active' qilganda — bot tugash timerini o'rnatadi.
    Kesh eskirmasin deb tozalab, yangi konkursga timer qo'yamiz."""
    try:
        await request.json()          # tanasi kerak emas — signal yetarli
        _konkurs_cache['data'] = None  # keshni yangilaymiz
        _konkurs_cache['time'] = 0
        loop = asyncio.get_event_loop()
        k = await loop.run_in_executor(None, get_konkurs)
        if k and k.get('end_time'):
            schedule_konkurs_end(k)
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'konkurs_started: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def notify_endpoint(request):
    try:
        data = await request.json()
        konkurs_id = data.get('konkurs_id', '')
        winner_user_id = data.get('winner_user_id', '')
        winner_username = data.get('winner_username', '')
        prize = data.get('prize', '')
        winners = data.get('winners', [])  # ko'p g'olib: [{user_id, username, prize}, ...]
        pics = data.get('pics', [])        # konkurs sovrin rasmlari (file_id yoki url)
        if konkurs_id and (winner_user_id or winners):
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None, notify_participants,
                konkurs_id, winner_user_id, winner_username, prize, winners, pics)
        return web.json_response({'ok': True})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def reroll_notify_endpoint(request):
    """Reroll qilinganda: eski g'olib (A), yangi g'olib (B), kanal (C) xabarlari."""
    try:
        data = await request.json()
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, send_reroll_notify, data)
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'reroll_notify: {e}')
        return web.json_response({'error': str(e)}, status=500)


def send_reroll_notify(data):
    """Reroll xabarlari (rasmsiz, HTML):
       old = {user_id, ism, username}, new = {user_id, ism, username},
       konkurs_nomi, orin, sovga, sabab_uz, sabab_ru, kanal_username."""
    old = data.get('old', {}) or {}
    new = data.get('new', {}) or {}
    kname = html_escape(data.get('konkurs_nomi', ''))
    orin = data.get('orin', '')
    sovga = html_escape(data.get('sovga', ''))
    sabab_uz = html_escape(data.get('sabab_uz', ''))
    sabab_ru = html_escape(data.get('sabab_ru', ''))
    old_ism = html_escape(old.get('ism', '') or 'mijoz')

    # ── (A) ESKI g'olibga — endi g'olib emas (kanal button) ──
    old_uid = str(old.get('user_id', '') or '')
    if old_uid:
        try:
            a_text = (
                f"🔄 Hurmatli {old_ism}!\n"
                f"Siz «{kname}» konkursida g'olib bo'lgan edingiz, ammo "
                f"{sabab_uz} sababli sovrin boshqa ishtirokchiga o'tkazildi.\n"
                f"Kelasi konkurslarda omad tilaymiz! 🍀\n"
                f"Kanalimizga obuna bo'lib qo'ying 👇\n\n"
                f"🔄 Уважаемый {old_ism}!\n"
                f"Вы были победителем конкурса, но приз передан другому "
                f"участнику по причине: {sabab_ru}.\n"
                f"Удачи в следующих конкурсах! 🍀\n"
                f"Подпишитесь на наш канал 👇"
            )
            req.post(f'{TG_API}/sendMessage', json={
                'chat_id': old_uid, 'text': a_text, 'parse_mode': 'HTML',
                'reply_markup': {"inline_keyboard": [[{
                    "text": "📢 Kanal / Канал", "url": CHANNEL_LINK}]]}
            }, timeout=8)
        except Exception as e:
            logger.error(f'reroll old {old_uid}: {e}')

    # ── (B) YANGI g'olibga — tabrik (admin button) ──
    new_uid = str(new.get('user_id', '') or '')
    if new_uid:
        try:
            b_text = (
                f"🎉 Tabriklaymiz! Siz «{kname}» konkursida qayta "
                f"aniqlash natijasida g'olib bo'ldingiz!\n"
                f"🏆 {orin}-o'rin — <b>{sovga}</b>\n"
                f"Sovg'ani olish uchun adminga yozing 👇\n\n"
                f"🎉 Поздравляем! Вы стали победителем по итогам "
                f"переопределения!\n"
                f"🏆 {orin}-место — <b>{sovga}</b>\n"
                f"Для получения приза напишите админу 👇"
            )
            req.post(f'{TG_API}/sendMessage', json={
                'chat_id': new_uid, 'text': b_text, 'parse_mode': 'HTML',
                'reply_markup': {"inline_keyboard": [[{
                    "text": "📩 Admin", "url": f"https://t.me/{ADMIN_USERNAME}"}]]}
            }, timeout=8)
        except Exception as e:
            logger.error(f'reroll new {new_uid}: {e}')

    # ── (C) KANALGA — natija o'zgardi (sayt button, rasmsiz) ──
    try:
        new_disp = winner_display(new)
        c_text = (
            f"🔄 Konkurs natijasi o'zgardi!\n"
            f"{orin}-o'rin sovrini (<b>{sovga}</b>) egasi {sabab_uz} sababli "
            f"g'olib qayta tanlandi.\n"
            f"🏆 Yangi g'olib: {new_disp}\n\n"
            f"🔄 Результат конкурса изменён!\n"
            f"Приз за {orin}-место (<b>{sovga}</b>) переразыгран "
            f"по причине: {sabab_ru}.\n"
            f"🏆 Новый победитель: {new_disp}"
        )
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': CHANNEL, 'text': c_text, 'parse_mode': 'HTML',
            'reply_markup': {"inline_keyboard": [[{
                "text": "🛍 Do'kon / Магазин",
                "url": "https://t.me/kraken_mobile_shop_bot?startapp"}]]}
        }, timeout=8)
    except Exception as e:
        logger.error(f'reroll channel: {e}')


async def publish_endpoint(request):
    """Sayt «Menga yuborish» bosganda — bot adminga OLX matni + kanal elonini yuboradi.
    E1: ish fonda ketadi, sayt javobni kutib turmaydi."""
    try:
        data = await request.json()
        num = str(data.get('num', ''))
        if not num:
            return web.json_response({'error': 'No num'}, status=400)
        asyncio.get_event_loop().run_in_executor(
            None, preview_elon_to_admin, num, ADMIN_ID)
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'publish_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)

# (update_channel_endpoint olib tashlandi — D2 qarori: kanalga avto-yuborish
#  qaytarilmadi. Endpoint faqat 'skipped' qaytarardi, sayt esa uni endi
#  umuman chaqirmaydi.)


def check_init_data(init_data, max_age=86400):
    """Telegram Mini App initData imzosini tekshiradi (HMAC-SHA256).
    To'g'ri bo'lsa foydalanuvchi id'sini, aks holda None qaytaradi."""
    import hmac, hashlib, time as _t
    try:
        got = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        h = got.pop('hash', '')
        if not h:
            return None
        check = '\n'.join(f'{k}={v}' for k, v in sorted(got.items()))
        secret = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, h):
            return None
        if _t.time() - int(got.get('auth_date', 0) or 0) > max_age:
            return None   # eskirgan
        return int(json.loads(got.get('user', '{}')).get('id', 0)) or None
    except Exception as e:
        logger.error(f'check_init_data: {e}')
        return None


def send_label_doc(chat_id, raw, name):
    """Yorliqni HUJJAT qilib yuboradi. sendPhoto EMAS — Telegram rasmni siqadi,
    qora-oq nozik grafika siqilsa chop etishda iflos chiqadi."""
    try:
        r = req.post(f'{TG_API}/sendDocument',
                     data={'chat_id': str(chat_id)},
                     files={'document': (name, raw, 'image/png')}, timeout=30)
        return bool(r.json().get('ok'))
    except Exception as e:
        logger.error(f'sendDocument: {e}')
        return False


async def label_endpoint(request):
    """Mini App yorliq PNG'ini yuboradi -> admin botda hujjat bo'lib oladi."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        if uid != ADMIN_ID:
            return web.json_response({'error': 'Ruxsat yoq'}, status=403)
        b64 = data.get('png_base64', '')
        if not b64:
            return web.json_response({'error': 'Rasm yoq'}, status=400)
        raw = base64.b64decode(b64)
        name = str(data.get('file_name') or 'yorliq.png')
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, send_label_doc, uid, raw, name)
        if not ok:
            return web.json_response({'error': 'Telegram yubormadi'}, status=502)
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'label: {e}')
        return web.json_response({'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════════════════════════
#  G9.1 — ULASHISH: Mini App'dan tayyor RASMLI xabar
#
#  Muammo: sayt «Ulashish» bosilganda oddiy HAVOLA yuborardi. Do'stga quruq
#  havola (yoki butun ekranni egallagan katta preview) borardi va e'lonni
#  ochish UCH qadam edi: havola → sayt sahifasi → t.me sahifasi → ilova.
#
#  Yechim: Telegram'ning o'z yo'li — savePreparedInlineMessage. Bot xabarni
#  OLDINDAN tayyorlab qo'yadi, sayt esa Telegram.WebApp.shareMessage(id) bilan
#  «Kimga yuborish» oynasini ochadi. Do'stga ODDIY RASM keladi, ostida nom va
#  narx, tagida tugma — tugma e'lonni BIR qadamda Mini App'da ochadi.
# ══════════════════════════════════════════════════════════════════════════

def _share_result(num, elon, model):
    """Ulashish uchun tayyor inline natija (rasm + qisqa matn + tugma).

    build_elon ATAYLAB ishlatilmaydi: u kanal uchun uzun matn va PREMIUM emoji
    yasaydi. Premium emoji oddiy mijozning chatida ko'rinmaydi — do'stga
    buzilgan belgilar borardi. Shu sabab bu yerda qisqa, sof HTML matn.
    """
    images = elon.get('images')
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []
    if not isinstance(images, list):
        images = []
    rasm = str(images[0]).strip() if images else ''
    if not rasm:
        return None       # type=photo uchun rasm SHART; rasmsiz e'lon ulashilmaydi

    # Telegram rasmni o'zi yuklab oladi — kichigi tezroq va ishonchliroq
    if 'ik.imagekit.io' in rasm and 'tr=' not in rasm:
        rasm += ('&' if '?' in rasm else '?') + 'tr=w-800,q-80'

    nom = elon_nomi(elon, model, 'uz')   # G12: e'lonning o'z nomi
    xotira = str(elon.get('storage') or '').strip()
    rang = clean_color(elon.get('color') or '')
    narx = str(elon.get('price', '')).replace('.0', '')
    cycle = str(elon.get('cycle', '') or '').replace('.0', '')
    cond_uz, _cond_ru, _emoji = holati_matni(elon.get('condition', 'used') or 'used', cycle)

    sarlavha = nom + (f' ({xotira})' if xotira else '') + (f' {rang}' if rang else '')
    narx_qatori = 'Sotildi' if elon_status(elon) == 'sold' else f'{narx}$'

    caption = (f'<b>{html_escape(sarlavha)}</b>\n'
               f'{html_escape(narx_qatori)} · {html_escape(cond_uz)}\n'
               f"E'lon №{num} · @{BOT_USERNAME}")

    return {
        'type': 'photo',
        'id': f'elon{num}',
        'photo_url': rasm,
        'thumbnail_url': rasm,
        'caption': caption,
        'parse_mode': 'HTML',
        'reply_markup': {'inline_keyboard': [[{
            'text': "Ko'rish / Открыть",
            'url': f'https://t.me/{BOT_USERNAME}?startapp=elon_{num}',
        }]]},
    }


def save_prepared_share(uid, num):
    """Telegram'da tayyor xabarni saqlaydi. (id, '') yoki (None, sabab) qaytaradi."""
    elon, models = elon_cache_get(num)         # G10.3: xotiradan (tez), yo'q bo'lsa Sheets
    if not elon:
        return None, 'topilmadi'
    if elon_status(elon) in ('deleted', 'waited'):
        return None, 'yopiq'
    natija = _share_result(num, elon, models.get(str(elon.get('specId', '') or ''), {}))
    if not natija:
        return None, 'rasmsiz'
    try:
        r = req.post(f'{TG_API}/savePreparedInlineMessage', json={
            'user_id': uid,
            'result': natija,
            'allow_user_chats': True,
            'allow_group_chats': True,
            'allow_channel_chats': True,
        }, timeout=20).json()
    except Exception as e:
        logger.error(f'savePreparedInlineMessage tarmoq: {e}')
        return None, 'tarmoq'
    if not r.get('ok'):
        # Eng ehtimolli sabab: BotFather'da inline rejim yoqilmagan
        logger.error(f"savePreparedInlineMessage: {r.get('description')}")
        return None, str(r.get('description') or 'telegram')
    return (r.get('result') or {}).get('id'), ''


async def share_endpoint(request):
    """Mini App «Ulashish» tugmasi shu yerga so'rov yuboradi.

    Bu yo'l ADMIN uchun emas, HAMMA mijoz uchun — shuning uchun label_endpoint
    dagi ADMIN_ID tekshiruvi bu yerda YO'Q. Himoya ikkita:
      1) initData imzosi — so'rov haqiqatan Mini App ichidan kelganini isbotlaydi
      2) num faqat raqam — begona qiymat Sheets so'roviga tushmaydi
    Xato bo'lsa sayt eski usulga (havola ulashish) o'zi tushadi.
    """
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        num = str(data.get('num', '') or '').strip()
        if not re.fullmatch(r'\d{1,6}', num):
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        loop = asyncio.get_event_loop()
        mid, sabab = await loop.run_in_executor(None, save_prepared_share, uid, num)
        if not mid:
            return web.json_response({'error': sabab}, status=502)
        return web.json_response({'ok': True, 'id': mid})
    except Exception as e:
        logger.error(f'share_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def elon_changed_endpoint(request):
    """G10.3: sayt (admin) e'lonni saqlaganda shu yerga yuboradi — bot xotirasi yangilanadi.

    Himoya: initData imzosi + FAQAT ADMIN_ID. Oddiy mijoz bu yo'lga kira olmaydi
    (aks holda begona odam xotiradagi narxni buzib, ulashish xabarini o'zgartirardi).
    Kelgan e'lon Sheets'ga yozilgan payload'ning o'zi (sayt elonPayload) —
    images JSON matn, price/cycle matn; _share_result ikkalasini ham tushunadi.
    """
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid or uid != ADMIN_ID:
            return web.json_response({'error': 'Faqat admin'}, status=401)
        elon = data.get('elon')
        if not isinstance(elon, dict):
            return web.json_response({'error': 'Elon yoq'}, status=400)
        num = str(elon.get('num', '') or '').strip()
        if not re.fullmatch(r'\d{1,6}', num):
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        elon['num'] = int(num)
        with _elon_cache_lock:
            eski = _ELON_CACHE['by_num'].get(num)
        # Sayt payload'ida channel_message_id YO'Q — xotiradagisi saqlanib qolsin (aks holda post «yo'qolardi»)
        if eski and not elon.get('channel_message_id'):
            elon['channel_message_id'] = eski.get('channel_message_id', '')
        elon_cache_put(elon)
        # G11.2: kanal posti — tahrir / o'chirish / avto-post (fonda)
        asyncio.get_event_loop().run_in_executor(None, kanal_sinxron, eski, elon)
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'elon_changed: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def kanal_buyruq(chat_id, cmd, num):
    """/post N · /yana N · /postochir N — natija adminga."""
    if cmd == '/post':
        mid, xato = await blok(kanal_post, num)
        await blok(send_msg, chat_id, f"✅ №{num} kanalga chiqdi (id {mid}) — {POST_CHANNEL}" if mid else f"❌ №{num}: <code>{html_escape(xato)}</code>")
    elif cmd == '/yana':
        mid, xato = await blok(kanal_yana_keldi, num)
        await blok(send_msg, chat_id, f"🔄 №{num} qayta postlandi (yangi id {mid})" if mid else f"❌ №{num}: <code>{html_escape(xato)}</code>")
    else:
        ok, xato = await blok(kanal_ochir, num)
        await blok(send_msg, chat_id, f"🗑 №{num} posti o'chirildi" if ok else f"❌ №{num}: <code>{html_escape(xato)}</code>")


async def kanal_post_endpoint(request):
    """G11.2: saytdagi «📣 Kanalga» / «🔄 Yana keldi» tugmalari. Faqat admin (initData). Javob: {ok, mid}."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid or uid != ADMIN_ID:
            return web.json_response({'error': 'Faqat admin'}, status=401)
        num = str(data.get('num', '') or '').strip()
        if not re.fullmatch(r'\d{1,6}', num):
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        amal = str(data.get('amal', 'post'))
        if amal == 'yana':
            mid, xato = await blok(kanal_yana_keldi, num)
        else:
            mid, xato = await blok(kanal_post, num)
        if not mid:
            return web.json_response({'ok': False, 'error': xato})
        return web.json_response({'ok': True, 'mid': mid, 'kanal': POST_CHANNEL})
    except Exception as e:
        logger.error(f'kanal_post_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def health(request):
    return web.json_response({'status': 'ok'})

async def keep_alive():
    """Har 10 daqiqada botning O'ZIGA `/health` so'rovi — servis uxlab qolmasin.

    🔴 2026-09-04: bu funksiya bir marta O'CHIRILGAN edi — «Render pullik
    tarifda doim yoniq» degan taxminga tayanib. Taxmin NOTO'G'RI edi va
    foydalanuvchidan so'ralmagan ham. Qaytarildi.
    🔴 BOSHQA HECH QACHON O'CHIRILMAYDI — avval foydalanuvchidan so'raladi.

    `RENDER_URL` env qo'yilmagan bo'lsa funksiya hech narsa qilmaydi.
    """
    render_url = os.environ.get('RENDER_URL', '')
    if not render_url:
        logger.warning('keep_alive: RENDER_URL yoq — bot uxlab qolishi mumkin')
        return
    while True:
        await asyncio.sleep(600)
        try:
            # blok() bilan: so'rov alohida ipda ketadi va event loop'ni to'xtatmaydi (T1)
            await blok(req.get, f'{render_url}/health', timeout=10)
        except Exception as e:
            logger.error(f'keep_alive: {e}')

@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

async def main():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post('/webhook', webhook)
    app.router.add_post('/notify', notify_endpoint)
    app.router.add_post('/konkurs_started', konkurs_started_endpoint)
    app.router.add_post('/reroll_notify', reroll_notify_endpoint)
    app.router.add_post('/publish', publish_endpoint)
    app.router.add_post('/label', label_endpoint)
    app.router.add_post('/share', share_endpoint)   # G9.1: ulashish uchun tayyor rasmli xabar
    app.router.add_post('/elon_changed', elon_changed_endpoint)   # G10.3: admin saqlaganda xotira yangilanadi + G11.2 kanal sinxron
    app.router.add_post('/kanal_post', kanal_post_endpoint)       # G11.2: saytdan «Kanalga» / «Yana keldi»
    app.router.add_get('/health', health)
    app.router.add_route('OPTIONS', '/{path_info:.*}', lambda r: web.Response())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    render_url = os.environ.get('RENDER_URL', '')
    if render_url:
        # BUGUN6 §2: allowed_updates — `chat_member` (kanal xush kelibsiz) sukut bo'yicha kelmaydi
        r = req.post(f'{TG_API}/setWebhook', json={'url': f'{render_url}/webhook', 'allowed_updates': ALLOWED_UPDATES})
        logger.info(f'Webhook: {r.json()}')
    # Servis uxlab qolmasin — har 10 daqiqada o'ziga so'rov
    asyncio.create_task(keep_alive())
    # Bot ishga tushganda aktiv konkurs timerini tiklaydi (restart himoyasi)
    asyncio.create_task(restore_konkurs_timer())
    # Bot ishga tushganda: e'lon xotirasi (G10.3) + oxirgi elon raqami — BITTA yuklashdan
    try:
        if elon_cache_load() and _ELON_CACHE['by_num']:
            _last_sent['num'] = max(int(k) for k in _ELON_CACHE['by_num'].keys())
            logger.info(f"Last elon num: {_last_sent['num']}")
    except Exception as e:
        logger.error(f'init elon_cache: {e}')
    asyncio.create_task(elon_cache_loop())   # kuniga bir marta ehtiyot yuklash
    logger.info(f'Started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
