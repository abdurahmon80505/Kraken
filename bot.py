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
CHANNEL = '@Kraken_mobile'
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

    # ── Narx: eski (strikethrough) + yangi (bold) ──
    add_prem('money'); add(" Цена/Narxi: ")
    if old and old != price:
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

def save_participant(konkurs_id, user_id, username, phone):
    if not SHEET_URL:
        return None
    try:
        data = json.dumps({
            'konkurs_id': str(konkurs_id),
            'user_id': str(user_id),
            'username': username or '',
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
            [{"text": "📢 @Kraken_mobile ga a'zo bo'lish", "url": "https://t.me/Kraken_mobile"}],
            [{"text": "✅ A'zo bo'ldim — qatnashish", "callback_data": "check_member"}]
        ]})

async def start_konkurs_flow(chat_id, user):
    k = get_konkurs()
    if not k:
        send_msg(chat_id, "😕 Hozirda aktiv konkurs yo'q.\n\nKanalimizni kuzating: @Kraken_mobile")
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
                None, save_participant, konkurs_id, user_id, username, phone)
            _konkurs_cache['time'] = 0
        except Exception as e:
            logger.error(f'bg save_participant: {e}')
    asyncio.create_task(_save())

def notify_participants(konkurs_id, winner_user_id, winner_username, prize, winners=None):
    """Barcha qatnashuvchilarga xabar - g'oliblar va yutqazganlar.
    winners: [{user_id, username, prize}, ...] — ko'p g'olib ro'yxati."""
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

    # G'oliblar ro'yxatini matn uchun (yutqazganlarga ko'rsatamiz)
    medals = ['🥇', '🥈', '🥉']
    win_lines = []
    for idx, w in enumerate(winners):
        uname = w.get('username', '')
        disp = f"@{uname}" if uname else f"ID {w.get('user_id','')}"
        medal = medals[idx] if idx < 3 else f"{idx+1}."
        wp = w.get('prize', '')
        win_lines.append(f"{medal} {disp}" + (f" — {wp}" if wp else ""))
    win_text = "\n".join(win_lines) if win_lines else (f"@{winner_username}" if winner_username else "anonim")

    for p in participants:
        uid = str(p.get('user_id', ''))
        if not uid:
            continue
        try:
            if uid in win_map:
                # G'olibga maxsus xabar (o'z o'rni va sovg'asi bilan)
                info = win_map[uid]
                place = info['place']
                my_prize = info['prize']
                medal = medals[place-1] if place <= 3 else f"{place}."
                req.post(f'{TG_API}/sendMessage', json={
                    'chat_id': uid,
                    'text': (
                        f"🏆 *Tabriklaymiz! Siz g'olib bo'ldingiz!*\n\n"
                        f"{medal} *{place}-o'rin* — *{my_prize}*\n\n"
                        f"🇺🇿 Konkursda g'olib bo'ldingiz! 🎊\n"
                        f"🇷🇺 Вы выиграли *{place} место* — *{my_prize}*! 🎊\n\n"
                        f"🎁 Sovg'angizni olish uchun adminga yozing:\n"
                        f"🎁 Для получения приза напишите администратору:"
                    ),
                    'parse_mode': 'Markdown',
                    'reply_markup': {"inline_keyboard": [[{
                        "text": "📩 Adminga yozish / Написать админу",
                        "url": f"https://t.me/{ADMIN_USERNAME}"
                    }]]}
                }, timeout=5)
            else:
                # Yutqazganlarga xabar (barcha g'oliblar ro'yxati bilan)
                req.post(f'{TG_API}/sendMessage', json={
                    'chat_id': uid,
                    'text': (
                        f"🎁 *{prize}* konkursi yakunlandi!\n\n"
                        f"🏆 *G'oliblar / Победители:*\n{win_text}\n\n"
                        f"🇺🇿 Afsuski, bu safar siz yutmadingiz 😔\n"
                        f"💳 Lekin siz ham yutdingiz!\n"
                        f"Kanalimizning istalgan smartfoniga *5$lik vauchеr* oldingiz!\n\n"
                        f"🇷🇺 К сожалению, в этот раз вы не выиграли 😔\n"
                        f"💳 Но вы тоже в выигрыше — *ваучер на $5*!\n\n"
                        f"📅 Har oy yangi konkurslar — o'tkazib yubormang!\n"
                        f"📢 @Kraken_mobile"
                    ),
                    'parse_mode': 'Markdown',
                    'reply_markup': {"inline_keyboard": [[{
                        "text": "🛍 Smartfonlarni ko'rish / Смотреть смартфоны",
                        "web_app": {"url": SAYT_URL}
                    }]]}
                }, timeout=5)
        except Exception as e:
            logger.error(f'notify {uid}: {e}')


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
                            [{"text": "📢 Kanalga a'zo bo'lish", "url": "https://t.me/Kraken_mobile"}],
                            [{"text": "✅ A'zo bo'ldim", "callback_data": "check_member"}]
                        ]})
            return web.json_response({'ok': True})

        if not chat_id:
            return web.json_response({'ok': True})

        # ── ADMIN rasm yuborsa: chala elon yaratamiz (rasm + raqam) ──
        photo = message.get('photo')
        if photo and chat_id == ADMIN_ID:
            mgid = message.get('media_group_id')
            largest = photo[-1]  # eng katta o'lcham
            file_id = largest.get('file_id', '')
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
            await start_konkurs_flow(chat_id, user)

        elif contact and chat_id in user_states:
            await handle_phone(chat_id, contact.get('phone_number', ''), user)

        elif text and chat_id in user_states:
            await handle_phone(chat_id, text, user)

        return web.json_response({'ok': True})
    except Exception as e:
        logger.error(f'Webhook: {e}')
        return web.json_response({'ok': False})

async def notify_endpoint(request):
    try:
        data = await request.json()
        konkurs_id = data.get('konkurs_id', '')
        winner_user_id = data.get('winner_user_id', '')
        winner_username = data.get('winner_username', '')
        prize = data.get('prize', '')
        winners = data.get('winners', [])  # ko'p g'olib: [{user_id, username, prize}, ...]
        if konkurs_id and (winner_user_id or winners):
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None, notify_participants,
                konkurs_id, winner_user_id, winner_username, prize, winners)
        return web.json_response({'ok': True})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

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
