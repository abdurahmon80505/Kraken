import os
import logging
import asyncio
import base64
import json
import urllib.parse
from io import BytesIO
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
# CHANNEL'dan username va link (a'zolik tugmalari uchun — test kanalga ham mos)
CHANNEL_USERNAME = CHANNEL.lstrip('@')
CHANNEL_LINK = f'https://t.me/{CHANNEL_USERNAME}'
SAYT_URL = 'https://krakenmobileshop.netlify.app/'
SHEET_URL = os.environ.get('SHEET_URL', '')
ADMIN_USERNAME = 'Krakens_admin'

# ── ImageKit (saytdagi bilan bir xil — barqaror rasm hosting) ──
IK_PRIVATE_KEY = os.environ.get('IK_PRIVATE_KEY', 'private_uRjC2/psPBQPc5fAhmshbRw9K1o=')
IK_UPLOAD_URL = 'https://upload.imagekit.io/api/v1/files/upload'

_konkurs_cache = {'data': None, 'time': 0}
user_states = {}

# Admin rasm yuborganda albom (media group)ni yig'ish uchun bufer
# {media_group_id: {'file_ids': [...], 'task': asyncio_handle}}
_photo_groups = {}
_single_photo_lock = {'last': 0}

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

CONDITION_TXT = {
    'new':     ("Yangi (Karobka)", "Новый (Коробка)"),
    'openbox': ("Openbox (Ochilgan)", "Openbox (Вскрыт)"),
    'used':    ("Ishlatilgan", "Б.у"),
}


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
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        req.post(f'{TG_API}/sendMessage', json=payload, timeout=8)
    except Exception as e:
        logger.error(f'sendMessage: {e}')

def get_products():
    """Sheets'dan barcha elon va modellarni oladi (action'siz so'rov)."""
    if not SHEET_URL:
        return None, None
    try:
        r = req.get(f"{SHEET_URL}?callback=d", timeout=15)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        return data.get('listings', []), data.get('models', [])
    except Exception as e:
        logger.error(f'get_products: {e}')
        return None, None


def build_elon(item, models_by_id):
    """Bitta elon uchun (matn, entities) qaytaradi. entities premium emoji uchun."""
    num = int(float(item.get('num', 0) or 0))
    name_uz = item.get('nameUz', '') or item.get('name', '')
    name_ru = item.get('nameRu', '') or name_uz
    storage = item.get('storage', '')
    price = str(item.get('price', '')).replace('.0', '')
    old = str(item.get('oldPrice', '')).replace('.0', '')
    cond = item.get('condition', 'new')
    cycle = str(item.get('cycle', '') or '').replace('.0', '')
    color_uz = item.get('color', '')
    color_ru = item.get('colorRu', '') or color_uz
    spec_id = item.get('specId', '')

    model = models_by_id.get(spec_id, {})
    spec_uz = model.get('specUz', '') or ''
    spec_ru = model.get('specRu', '') or ''

    cond_uz, cond_ru, cond_emoji = holati_matni(cond, cycle)

    # Sarlavha: G logo + nom + xotira
    g_base = PREMIUM['google'][0]
    k_base = PREMIUM['k'][0]
    m_base = PREMIUM['money'][0]

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
    add(f"#phone #{num}\n\n")

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
    # Sotildi = price bo'sh/0 (oldPrice'da asl narx turadi)
    price_num = 0.0
    try:
        price_num = float(price) if price else 0.0
    except Exception:
        price_num = 0.0
    is_sold = (price_num == 0) and bool(old)

    add_prem('money'); add(" Цена/Narxi: ")
    if is_sold:
        # ~~400$~~ ❗️SOTILDI❗️
        add_fmt(f"{old}$", 'strikethrough')
        add(" ")
        add_fmt("❗️SOTILDI❗️", 'bold')
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


def html_escape(s):
    """HTML maxsus belgilarini himoyalaydi."""
    if not s:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def md_escape(s):
    """(eski nom — endi HTML escape ishlatamiz)"""
    return html_escape(s)


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


def strip_custom_emoji(entities):
    """Kanalga yuborishda custom_emoji entity'larni olib tashlaydi.

    Telegram cheklovi: bot custom emoji'ni faqat private/guruh/supergruhga
    yubora oladi (bot egasida Premium bo'lsa). KANALGA custom emoji umuman
    o'tmaydi — shu sabab lichkada premium chiqadi, kanalda oddiy emoji.
    Entity'ni qoldirib yuborsak, Telegram ba'zida g'alati bo'shliq qoldiradi.
    Shuning uchun kanal uchun custom_emoji'ni tashlaymiz — oddiy emoji (📱💰💡)
    baribir matnda turibdi, u toza ko'rinadi. Bold/strikethrough/quote qoladi."""
    if not entities:
        return entities
    return [e for e in entities if e.get('type') != 'custom_emoji']


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
    # ── Narx ──
    price_num = 0.0
    try:
        price_num = float(price) if price else 0.0
    except Exception:
        price_num = 0.0
    is_sold = (price_num == 0) and bool(old)
    if is_sold:
        lines.append(f"Цена/Narxi: {old}$ — SOTILDI ❗️")
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


def edit_channel_post(channel, message_id, text, entities, is_media_group=False, text_message_id=None):
    """Kanaldagi postni yangilaydi. Media group bo'lsa — caption yoki alohida matnni edit qiladi."""
    target_mid = text_message_id or message_id
    try:
        if is_media_group and text_message_id and text_message_id != message_id:
            # Alohida matn xabari bор — uni edit qilamiz
            payload = {'chat_id': channel, 'message_id': text_message_id, 'text': text}
            if entities:
                payload['entities'] = entities
            r = req.post(f'{TG_API}/editMessageText', json=payload, timeout=10).json()
            return r
        else:
            # Caption edit (rasm + caption)
            payload = {'chat_id': channel, 'message_id': target_mid, 'caption': text}
            if entities:
                payload['caption_entities'] = entities
            r = req.post(f'{TG_API}/editMessageCaption', json=payload, timeout=10).json()
            # Agar caption emas, oddiy matn bo'lsa — editMessageText sinaymiz
            if not r.get('ok'):
                payload2 = {'chat_id': channel, 'message_id': target_mid, 'text': text}
                if entities:
                    payload2['entities'] = entities
                r = req.post(f'{TG_API}/editMessageText', json=payload2, timeout=10).json()
            return r
    except Exception as e:
        logger.error(f'edit_channel_post: {e}')
        return None


async def send_new_elons(chat_id, text):
    parts = text.split()
    listings, models = get_products()
    if listings is None:
        send_msg(chat_id, "❌ Sheets'dan ma'lumot olib bo'lmadi. SHEET_URL'ni tekshiring.")
        return

    models_by_id = {m.get('id'): m for m in (models or [])}

    # /elon 199  yoki  /elon 199 200 205  -> aniq raqamlar
    nums = [int(p) for p in parts[1:] if p.isdigit()]

    def _is_sold(it):
        try:
            return float(it.get('price', '') or -1) == 0
        except (ValueError, TypeError):
            return False

    if nums:
        targets = [it for it in listings if int(float(it.get('num', 0) or 0)) in nums]
        targets.sort(key=lambda x: int(float(x.get('num', 0) or 0)))
        # Aniq raqamlar ichida sotilgani bo'lsa ogohlantiramiz (lekin yuboramiz — admin qarori)
        sold_nums = [int(float(it.get('num', 0) or 0)) for it in targets if _is_sold(it)]
        if sold_nums:
            send_msg(chat_id, "⚠️ Sotilgan: " + ", ".join('#' + str(n) for n in sold_nums))
    else:
        # /yubor  ->  oxirgi yuborilgandan keyingi yangilar (sotilganlarni chiqarib tashlaymiz)
        last = _last_sent['num']
        targets = [it for it in listings
                   if int(float(it.get('num', 0) or 0)) > last and not _is_sold(it)]
        targets.sort(key=lambda x: int(float(x.get('num', 0) or 0)))

    if not targets:
        send_msg(chat_id,
            f"ℹ️ Yangi elon yo'q. Oxirgi: #{_last_sent['num']}\n"
            f"Aniq raqam: `/elon 199`")
        return

    sent = 0
    max_num = _last_sent['num']
    for it in targets:
        num, etext, entities = build_elon(it, models_by_id)
        res = send_elon(chat_id, etext, entities)
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
        # Apps Script'da g'olibni aniqlaymiz
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, _end_konkurs_via_sheet, konkurs_id)
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
    end_ts = _parse_end_time(konkurs.get('end_time'))
    if not end_ts:
        return  # muddatsiz konkurs — qo'lda tugatiladi
    import time
    delay = end_ts - time.time()
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
    if not SHEET_URL:
        return []
    try:
        r = req.get(
            f"{SHEET_URL}?action=getParticipants&callback=d&id={urllib.parse.quote(str(konkurs_id))}",
            timeout=15)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        return data.get('participants', [])
    except Exception as e:
        logger.error(f'get_participants: {e}')
        return []



def not_member_msg(chat_id):
    send_msg(chat_id,
        "❗ *Konkursda qatnashish uchun kanalga a'zo bo'ling!*\n"
        "❗ *Для участия подпишитесь на канал!*",
        keyboard={"inline_keyboard": [
            [{"text": f"📢 {CHANNEL} ga a'zo bo'lish", "url": CHANNEL_LINK}],
            [{"text": "✅ A'zo bo'ldim — qatnashish", "callback_data": "check_member"}]
        ]})

async def start_konkurs_flow(chat_id, user):
    k = get_konkurs()
    if not k:
        send_msg(chat_id, f"😕 Hozirda aktiv konkurs yo'q.\n\nKanalimizni kuzating: {CHANNEL}")
        return

    if not is_member(chat_id):
        not_member_msg(chat_id)
        return

    user_states[chat_id] = {
        'step': 'phone',
        'konkurs_id': k['id'],
        'prize': k.get('prize', ''),
        'user_id': user.get('id', chat_id),
        'username': user.get('username', ''),
    }

    send_msg(chat_id,
        f"🎁 *{k.get('prize','Sovrin')}*\n\n"
        f"🇺🇿 Konkursda qatnashish uchun telefon raqamingizni ulashing 👇\n"
        f"🇷🇺 Чтобы участвовать в розыгрыше, поделитесь номером телефона 👇",
        keyboard={
            "keyboard": [[{"text": "📱 Raqamni ulashish / Поделиться номером", "request_contact": True}]],
            "resize_keyboard": True, "one_time_keyboard": True
        })

async def handle_phone(chat_id, phone, user):
    state = user_states.pop(chat_id, {})
    if not state:
        return

    if not is_member(chat_id):
        not_member_msg(chat_id)
        return

    username = state.get('username') or user.get('username', '')
    user_id = state.get('user_id', chat_id)
    konkurs_id = state.get('konkurs_id', '')
    prize = state.get('prize', '')
    # Ism (first_name + last_name) — g'olib username'siz bo'lsa ko'rsatish uchun
    ism = (user.get('first_name', '') or '').strip()
    _ln = (user.get('last_name', '') or '').strip()
    if _ln:
        ism = (ism + ' ' + _ln).strip()

    # ── DARROV javob: hech qanday Google so'rovini KUTMAYMIZ ──
    # Mijoz raqam berishi bilan tasdiqlash xabarini yuboramiz.
    req.post(f'{TG_API}/sendMessage', json={
        'chat_id': chat_id,
        'text': (
            "📲 *Deyarli tayyor! / Почти готово!*\n\n"
            "🇺🇿 Qatnashishni yakunlash uchun pastdagi tugmani bosing "
            "va saytda \"✅ Tasdiqlash\"ni bosing 👇\n"
            "🇷🇺 Чтобы завершить участие, нажмите кнопку ниже "
            "и нажмите \"✅ Подтвердить\" на сайте 👇"
        ),
        'parse_mode': 'Markdown',
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
            f"✅ Yangi elon yaratildi: *№{num}*\n"
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
        grp['timer'] = loop.call_later(
            2.0, finalize_konkurs_photos, key, chat_id)
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
            f"✅ *{len(urls)} ta sovrin rasmi qabul qilindi!*\n\n"
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
        grp['timer'] = loop.call_later(
            2.0, finalize_photo_group, media_group_id, chat_id)
    else:
        # Bitta rasm — darrov elon
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _single_photo_elon, chat_id, file_id)


def _single_photo_elon(chat_id, file_id):
    res = create_bot_elon([file_id])
    if res:
        num = res.get('num', '?')
        send_msg(chat_id,
            f"✅ Yangi elon yaratildi: *№{num}*\n"
            f"📸 1 ta rasm saqlandi.\n\n"
            f"Endi saytdagi admin panelda ma'lumotlarini to'ldiring 👇",
            keyboard={"inline_keyboard": [[{
                "text": "🛠 Admin panel / Saytga kirish",
                "web_app": {"url": SAYT_URL}
            }]]})
    else:
        send_msg(chat_id, "❌ Elon yaratishda xatolik. Qayta urining.")


async def webhook(request):
    try:
        data = await request.json()
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
            req.post(f'{TG_API}/answerCallbackQuery',
                json={'callback_query_id': cq_id}, timeout=5)
            if cq_data == 'check_member' and cq_chat:
                if is_member(cq_chat):
                    await start_konkurs_flow(cq_chat, cq_user)
                else:
                    send_msg(cq_chat,
                        "❌ Hali a'zo emassiz! Avval kanalga a'zo bo'ling.",
                        keyboard={"inline_keyboard": [
                            [{"text": "📢 Kanalga a'zo bo'lish", "url": CHANNEL_LINK}],
                            [{"text": "✅ A'zo bo'ldim", "callback_data": "check_member"}]
                        ]})
            elif cq_data.startswith('pub_') and cq_user.get('id') == ADMIN_ID:
                # (VAQTINCHA REJIMDA ishlatilmaydi — tugma yuborilmaydi.
                #  Avtomatik tizim qaytarilганда yana faollashadi.)
                num = cq_data[4:]
                cq_msg_id = cq.get('message', {}).get('message_id')
                await publish_elon_to_channel(num, cq_chat, cq_msg_id)
            elif cq_data.startswith('cancel_') and cq_user.get('id') == ADMIN_ID:
                # (VAQTINCHA REJIMDA ishlatilmaydi.)
                cq_msg_id = cq.get('message', {}).get('message_id')
                if cq_msg_id:
                    req.post(f'{TG_API}/editMessageReplyMarkup', json={
                        'chat_id': cq_chat, 'message_id': cq_msg_id,
                        'reply_markup': {'inline_keyboard': []}
                    }, timeout=5)
                send_msg(cq_chat, "❌ Bekor qilindi. Kanalga yuborilmadi.")
            return web.json_response({'ok': True})

        if not chat_id:
            return web.json_response({'ok': True})

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
                return web.json_response({'ok': True})
            # Aks holda — eski logika: chala elon yaratamiz
            await handle_admin_photo(chat_id, file_id, mgid)
            return web.json_response({'ok': True})

        if text.startswith('/yubor') or text.startswith('/elon'):
            if chat_id != ADMIN_ID:
                return web.json_response({'ok': True})
            await send_new_elons(chat_id, text)
            return web.json_response({'ok': True})

        if text.startswith('/start'):
            parts = text.split(' ', 1)
            deep = parts[1].strip() if len(parts) > 1 else ''
            if deep == 'konkurs':
                await start_konkurs_flow(chat_id, user)
            else:
                req.post(f'{TG_API}/sendAnimation', json={
                    'chat_id': chat_id,
                    'animation': 'CgACAgIAAxkBAAMvaf3qQRiu8Kk4qBQZdISLTSIIDJYAAsGZAAJG3OhLX3fB57eReYE7BA',
                    'caption': (
                        "🇺🇿 *Barcha aktual smartfonlarimiz saytimizga joylandi*\n"
                        "🇷🇺 *Все актуальные смартфоны уже на нашем сайте*\n\n"
                        "Kirish uchun bosing / Нажмите, чтобы перейти 👇"
                    ),
                    'parse_mode': 'Markdown',
                    'reply_markup': {"inline_keyboard": [[{
                        "text": "🛍 Saytga kirish / Перейти на сайт",
                        "web_app": {"url": SAYT_URL}
                    }]]}
                }, timeout=10)

        elif text == '/konkurs':
            # ADMIN: sovrin rasmi yig'ish rejimi (hech narsa demay rasm kutadi).
            # Oddiy mijoz: konkursda qatnashish flow'i.
            if chat_id == ADMIN_ID:
                user_states[chat_id] = {'step': 'konkurs_photo'}
                # Javob matni YO'Q — bot jimgina rasm kutadi (docx #9)
            else:
                await start_konkurs_flow(chat_id, user)

        elif text == '/konkurstimer' and chat_id == ADMIN_ID:
            # Admin zaxira: aktiv konkurs timerini qayta o'rnatadi + holatni ko'rsatadi
            loop = asyncio.get_event_loop()
            _konkurs_cache['time'] = 0
            k = await loop.run_in_executor(None, get_konkurs)
            if k and k.get('end_time'):
                schedule_konkurs_end(k)
                send_msg(chat_id,
                    f"✅ Aktiv konkurs topildi.\n"
                    f"🎁 {k.get('prize','')}\n"
                    f"⏰ Tugash: {k.get('end_time','')}\n"
                    f"⏳ Timer o'rnatildi — vaqti kelganda avtomatik tugaydi.")
            else:
                send_msg(chat_id, "ℹ️ Hozircha aktiv konkurs yo'q (yoki tugash vaqti belgilanmagan).")

        elif contact and chat_id in user_states:
            await handle_phone(chat_id, contact.get('phone_number', ''), user)

        elif text and chat_id in user_states and user_states[chat_id].get('step') != 'konkurs_photo':
            # Admin konkurs rasm rejimida matn yozsa — telefon deb qabul qilmaymiz
            await handle_phone(chat_id, text, user)

        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'Webhook: {e}')
        return web.json_response({'ok': False})

def fetch_elon_by_num(num):
    """Sheets'dan bitta elon + modellar ma'lumotini oladi."""
    try:
        r = req.get(f'{SHEET_URL}?action=getElon&num={num}', timeout=15).json()
        if r.get('ok'):
            return r.get('elon'), r.get('models_by_id', {})
    except Exception as e:
        logger.error(f'fetch_elon_by_num: {e}')
    return None, {}


async def preview_elon_to_admin(num, admin_chat):
    """VAQTINCHA REJIM: avtomatik kanal tizimi o'chirilgan.
    'Kanalga yuborish' bosilganda bot elonni FAQAT adminga (lichkaga) yuboradi:
      1) Kanal eloni — rasm(lar) + premium emoji bilan (copy qilib kanalga qo'yish uchun)
      2) OLX matni — alohida xabar (#5)
    Kanalga hech narsa yuborilmaydi, tasdiqlash tugmasi yo'q.
    (publish_elon_to_channel / update_channel_elon funksiyalari kodda qoladi —
     kelajakda avtomatik tizimni qaytarish uchun.)"""
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
    send_msg(admin_chat, "📋 *KANAL ELONI* — Kanalga joylashingiz mumkin 👇")
    res = send_elon_with_photos(admin_chat, text, entities, images)
    if not res:
        send_msg(admin_chat, "❌ Kanal elonini yuborishda xatolik.")


async def publish_elon_to_channel(num, admin_chat, preview_msg_id=None):
    """Elonни kanalга yuboради va channel_message_id'ни Sheets'ga saqlaydi."""
    elon, models = fetch_elon_by_num(num)
    if not elon:
        send_msg(admin_chat, f"❌ №{num} elon topilmadi.")
        return
    _, text, entities = build_elon(elon, models)
    # Kanalga custom emoji o'tmaydi (Telegram cheklovi) — tashlab yuboramiz,
    # oddiy emoji toza ko'rinadi. Bold/strikethrough/quote qoladi.
    entities = strip_custom_emoji(entities)
    images = elon.get('images', [])
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []

    res = send_elon_with_photos(CHANNEL, text, entities, images)
    if not res or not res.get('message_id'):
        send_msg(admin_chat, "❌ Kanalga yuborishda xatolik.")
        return

    # channel_message_id'ni Sheets'ga saqlaymiz
    save_channel_msg_id(num, res.get('message_id'), res.get('is_media_group', False), res.get('text_message_id'))

    # Preview tugmalarini o'chiramiz
    if preview_msg_id:
        req.post(f'{TG_API}/editMessageReplyMarkup', json={
            'chat_id': admin_chat, 'message_id': preview_msg_id,
            'reply_markup': {'inline_keyboard': []}
        }, timeout=5)
    send_msg(admin_chat, f"✅ №{num} kanalga yuborildi!")


def save_channel_msg_id(num, msg_id, is_media_group, text_msg_id):
    """channel_message_id va qo'shimcha ma'lumotni Sheets'ga yozadi."""
    try:
        payload = urllib.parse.quote(json.dumps({
            'num': num,
            'channel_message_id': msg_id,
            'is_media_group': is_media_group,
            'text_message_id': text_msg_id or msg_id
        }))
        req.get(f'{SHEET_URL}?action=saveChannelMsgId&data={payload}', timeout=15)
    except Exception as e:
        logger.error(f'save_channel_msg_id: {e}')


def update_channel_elon(num):
    """Tahrir/sotildi bo'lganda kanaldagi postni yangilaydi (avtomatik, tasdiqsiz)."""
    elon, models = fetch_elon_by_num(num)
    if not elon:
        return False
    ch_mid = elon.get('channel_message_id', '')
    if not ch_mid:
        return False  # kanalga hali yuborilmagan
    _, text, entities = build_elon(elon, models)
    entities = strip_custom_emoji(entities)   # kanalda custom emoji yo'q (#4)
    is_mg = str(elon.get('is_media_group', '')).lower() in ('true', '1', 'yes')
    text_mid = elon.get('text_message_id', '') or ch_mid
    edit_channel_post(CHANNEL, ch_mid, text, entities, is_media_group=is_mg, text_message_id=text_mid)
    return True


async def konkurs_started_endpoint(request):
    """Sayt konkursni 'active' qilganda — bot tugash timerini o'rnatadi.
    Kesh eskirmasin deb tozalab, yangi konkursga timer qo'yamiz."""
    try:
        data = await request.json()
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
    """Sayt 'Kanalga yuborish' bosganda — bot adminга preview + tasdiqlash yuboradi."""
    try:
        data = await request.json()
        num = str(data.get('num', ''))
        if not num:
            return web.json_response({'error': 'No num'}, status=400)
        await preview_elon_to_admin(num, ADMIN_ID)
        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'publish_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def update_channel_endpoint(request):
    """VAQTINCHA O'CHIRILGAN: sayt tahrir/sotildi qilganda kanalni AVTOMATIK
    tahrirlamaydi. Sabab: bot edit qilganda kanaldagi premium emoji yo'qoladi.
    Endi kanalni admin qo'lda boshqaradi. (update_channel_elon kodi qoladi —
    avtomatik tizim qaytarilганda shu endpoint ichini yana yoqamiz.)"""
    # Hech narsa qilmaymiz — 'ok' qaytaramiz (sayt xato bermasin).
    return web.json_response({'ok': True, 'skipped': 'auto-channel disabled'})


async def upload_image(request):
    try:
        data = await request.json()
        image_b64 = data.get('image', '')
        listing_num = data.get('num', 0)
        if not image_b64:
            return web.json_response({'error': 'No image'}, status=400)
        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]
        image_bytes = base64.b64decode(image_b64)
        r = req.post(
            f'{TG_API}/sendPhoto',
            data={'chat_id': CHANNEL, 'caption': f'📸 Elon №{listing_num}'},
            files={'photo': ('photo.jpg', BytesIO(image_bytes), 'image/jpeg')},
            timeout=30)
        result = r.json()
        if not result.get('ok'):
            return web.json_response({'error': result}, status=500)
        file_id = result['result']['photo'][-1]['file_id']
        fi = req.get(f'{TG_API}/getFile?file_id={file_id}').json()
        file_path = fi['result']['file_path']
        url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
        return web.json_response({'success': True, 'file_id': file_id, 'url': url})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def get_image_url(request):
    try:
        file_id = request.query.get('file_id', '')
        fi = req.get(f'{TG_API}/getFile?file_id={file_id}').json()
        file_path = fi['result']['file_path']
        return web.json_response({'url': f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def health(request):
    return web.json_response({'status': 'ok'})

async def keep_alive():
    render_url = os.environ.get('RENDER_URL', '')
    if not render_url:
        return
    while True:
        await asyncio.sleep(600)
        try:
            req.get(f'{render_url}/health', timeout=10)
        except:
            pass

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
    app.router.add_post('/update_channel', update_channel_endpoint)
    app.router.add_post('/upload', upload_image)
    app.router.add_get('/image', get_image_url)
    app.router.add_get('/health', health)
    app.router.add_route('OPTIONS', '/{path_info:.*}', lambda r: web.Response())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    render_url = os.environ.get('RENDER_URL', '')
    if render_url:
        r = req.post(f'{TG_API}/setWebhook', json={'url': f'{render_url}/webhook'})
        logger.info(f'Webhook: {r.json()}')
    asyncio.create_task(keep_alive())
    # Bot ishga tushganda aktiv konkurs timerini tiklaydi (restart himoyasi)
    asyncio.create_task(restore_konkurs_timer())
    # Bot ishga tushganda oxirgi elon raqamini eslab qoladi
    try:
        listings, _ = get_products()
        if listings:
            _last_sent['num'] = max(int(float(it.get('num', 0) or 0)) for it in listings)
            logger.info(f"Last elon num: {_last_sent['num']}")
    except Exception as e:
        logger.error(f'init last_sent: {e}')
    logger.info(f'Started on port {PORT}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
