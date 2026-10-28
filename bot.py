import os
import re
import logging
import asyncio
import base64
import functools
import hashlib
import json
import html as _html
import urllib.parse
import time
import threading
import concurrent.futures
from aiohttp import web
import requests as req

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 8080))
TG_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
# Kanal ID — Render'dan CHANNEL_ID env orqali o'zgartiriladi.
# Test paytida:  CHANNEL_ID=@Kraken_mobile_test  (Render dashboard'ga qo'shasan)
# Testdan keyin: env'ni o'chirasan yoki @nuqta_tech_mobile qilasan → asosiy kanalga qaytadi.
# 2026-10-08 (BUGUN56): Mobile kanal manzili @Kraken_mobile → @nuqta_tech_mobile (foydalanuvchi o'zgartirdi; eskisi endi bo'sh).
CHANNEL = os.environ.get('CHANNEL_ID', '@nuqta_tech_mobile')
# G11.0: SINOV kanali — /richtest faqat shu yerga va admin lichkasiga yuboradi.
# ASOSIY KANALGA (CHANNEL) sinov xabari HECH QACHON KETMAYDI (foydalanuvchi:
# «hozir rasvo qiladi-ku… faqat lichkamga… test kanaliga yuborsin»).
TEST_CHANNEL = os.environ.get('TEST_CHANNEL_ID', '@Kraken_mobile_test')
# CHANNEL'dan username va link (a'zolik tugmalari uchun — test kanalga ham mos)
CHANNEL_USERNAME = CHANNEL.lstrip('@')
CHANNEL_LINK = f'https://t.me/{CHANNEL_USERNAME}'
SAYT_URL = 'https://nuqtatech-store.netlify.app/'
# Bot manzili (@username) — BITTA joy, kodda boshqa joyda yozilmaydi (2026-10-07, R1.4 b: yangi bot «Nuqta tech Store»
# @nuqta_tech_store_bot). Tartib: Render env BOT_USERNAME (qo'lda) → bo'lmasa — BOT_TOKEN egasi (Telegram getMe, ishga
# tushganda bir marta) → bo'lmasa — yangi bot nomi (BUGUN137: eski bot faqat yangisiga yo'naltiradi, zaxira nom ham yangisi).
# Ya'ni chiqarish kuni Render'da faqat BOT_TOKEN almashadi, manzil o'zi to'g'rilanadi.
def _bot_manzili():
    env = os.environ.get('BOT_USERNAME', '').strip().lstrip('@')
    if env:
        return env
    if BOT_TOKEN:
        try:
            j = req.get(f'{TG_API}/getMe', timeout=8).json()
            if j.get('ok') and (j.get('result') or {}).get('username'):
                return j['result']['username']
            logger.error(f'getMe: {j}')
        except Exception as e:
            logger.error(f'getMe: {e}')
    return 'nuqta_tech_store_bot'
BOT_USERNAME = _bot_manzili()
SHEET_URL = os.environ.get('SHEET_URL', '')
# ADMIN_USERNAME — pastda, «ALOQA» blokida (2026-10-07)

# Apps Script maxfiy kaliti. Mijoz telefon raqamlari (getParticipants) endi faqat
# shu kalit bilan beriladi — brauzerdan (saytdan) so'ralsa bo'sh qaytadi.
# Qiymat Render env'da va Apps Script Script Properties'da BIR XIL bo'lishi shart.
API_KEY = os.environ.get('API_KEY', '')

# ── ImageKit (saytdagi bilan bir xil — barqaror rasm hosting) ──
IK_PRIVATE_KEY = os.environ.get('IK_PRIVATE_KEY', '')
IK_UPLOAD_URL = 'https://upload.imagekit.io/api/v1/files/upload'

# ── REBRENDING (A5, 2026-10-06): brend nomi — mijozga ko'rinadigan bot matnlari shundan oladi ──
# Kanal / bot username'lari — yuqoridagi CHANNEL (env CHANNEL_ID), BOT_USERNAME; admin, raqam — pastdagi ALOQA.
BREND = 'Nuqta tech'

# ── ALOQA (2026-10-07, foydalanuvchi): kanal postidagi raqam, admin va yo'nalish kanallari — BITTA joy ──
# «Yangi raqam — yangi postlarning rich text'ida; admin — @nuqta_tech_admin; postdagi kanal havolasi — e'lon qaysi
# bo'limdan yuborilgan bo'lsa, o'sha kanal nomi va havolasi». Qiymatlar sayt `01-sozlama.js` KONTAKT bilan bir xil.
# Kod o'zgarmasdan env bilan almashadi: ADMIN_USERNAME, ALOQA_TEL, KANAL_MOBILE / KANAL_PC / KANAL_CAMERA (@ siz ham bo'ladi).
# ✅ 2026-10-08: @nuqta_tech_admin, @nuqta_tech_PC, @nuqta_tech_camera — Telegram'da bor (G2, G3; MS2 — «PC» katta harf bilan).
# Guruhlar (…_chat) bot matnlariga qo'yilmaydi — G1: hozir faqat izoh uchun, a'zo 100 dan oshgach.
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'nuqta_tech_admin').strip().lstrip('@')
ALOQA_TEL = os.environ.get('ALOQA_TEL', '+998 99 500 00 96').strip()
YON_KANAL = {   # yo'nalish kaliti (jadval «Yo'nalishlar») → (kanal nomi K5, username K10)
    'mobile': (f'{BREND} · Mobile', os.environ.get('KANAL_MOBILE', 'nuqta_tech_mobile').strip().lstrip('@')),
    'pc': (f'{BREND} · PC', os.environ.get('KANAL_PC', 'nuqta_tech_PC').strip().lstrip('@')),
    'camera': (f'{BREND} · Camera', os.environ.get('KANAL_CAMERA', 'nuqta_tech_camera').strip().lstrip('@')),
}

# ── A26 / B36: SUV BELGISI — kanal posti va OLX albomi rasmlariga logo (ImageKit overlay, rasm qayta ishlanmaydi) ──
# Logo ImageKit'da bir marta yuklangan: kraken/nuqta-tech_avatar-yashil.png (2026-10-06). Doira (r-max), 50% shaffof,
# o'lchami — rasm ENIning 13.8% (3184.6, Owner 2026-10-25: «logo biroz katta, 5–10% kichik» — 15% dan ~8% kam; sayt
# SUV_BELGI.olcham hali 0.15 — admin oynasidagi ko'rinish), sukut joyi — chap o'rta (markaz: eni 10.9%, bo'yi 50%).
# Joy har rasmga alohida — sayt admin tahrir oynasida tanlaydi va rasm manzili OXIRIGA yozadi: «…jpg#nb=X,Y» (markaz, %
# — eni va bo'yidan) yoki «#nb=0» (belgisiz). Belgisiz manzil — sukut joy. «#» — fragment: eski kod uni kesmasa ham brauzer
# rasmni baribir oladi. Bot manzilni ishlatishdan OLDIN belgi qismini kesadi (images_of, _ik_olcham — `belgi_ajrat`).
# SUV_BELGI=0 (env) — belgi o'chadi (rasmlar avvalgidek).
SUV_BELGI = os.environ.get('SUV_BELGI', '1') != '0'
SUV_BELGI_RASM = 'kraken/nuqta-tech_avatar-yashil.png'
SUV_BELGI_OLCHAM = 0.138
SUV_BELGI_CHET = 0.04
SUV_BELGI_SHAFFOF = 50
SUV_BELGI_TR = 'w-1600,q-85'   # kanal / OLX rasmi o'lchami (inline rasm yuklash bilan bir xil)
# BUGUN148 §2: 2+ rasmli e'londa 1-rasmda «o'ngga suring» belgisi (ImageKit matn layer'i, logo kabi usul — resize'dan keyin
# `:` bilan). Foydalanuvchi: «postda odamlar 1-rasmni ko'rib, qolganini ko'rmasligi mumkin». 3184.8 gacha — o'ng yuqorida «›››».
# 3184.8 (Owner 2026-10-25: «tepaga emas, pastga; qop-qora «›››» xunuk — logo rangida, 5–10% kattaroq, boshqacharoq»):
# PASTKI o'ngda, logo rangida (fon #134E4A — logo foni, 90%; belgi oq — logo yozuvi), Montserrat qalin. Joyi — markaz bo'yicha
# (lxc/lyc — belgi o'lchamiga bog'liq emas): bo'yi 88% — Telegram 4:5 ramkasi 3:4 rasmning pastidan ~3%, 0.70 nisbatlida ~6%
# kesadi, belgi to'liq ichkarida; o'ng chetda — o'rtadagi slayd nuqtalariga tegmaydi. O'lchami — eski belgidan ~8% katta
# (eski 118×80 px w-1600 da).
# 3184.9 (Owner 2026-10-25: «dumaloq yoqdi, strelka chaprog'ida + juda qirrali — rounded, o'rtaga, transparent, logodek»):
# faqat doira qoldi (kapsula «Suring ›» olib tashlandi). Shrift «›» emas — chizilgan: doira 112 px (ik_canvas, r-max), logo
# kabi o-50; strelka — ikkita oq kapsula (43×12, r-max — uchlari va burilishi yumaloq), ±45° burilgan, markazlari doira
# markazidan ±11 px — strelka qutisi doira markazida (chap / o'ng bo'sh joy 40 / 39 px). Strelka shaffof emas: ikki kapsula
# burilishda ustma-ust tushadi, shaffof bo'lsa o'sha joy dog' bo'lib ko'rinadi.
KEYINGI_BELGI = os.environ.get('KEYINGI_BELGI', '1') != '0'
KEYINGI_BELGI_LAYER = ('l-image,i-ik_canvas,bg-134E4A,w-112,h-112,r-max,o-50,lxc-bw_mul_0.89,lyc-bh_mul_0.88,l-end'
                       ':l-image,i-ik_canvas,bg-FFFFFF,w-43,h-12,r-max,rt-45,lxc-bw_mul_0.89,lyc-bh_mul_0.88_sub_11,l-end'
                       ':l-image,i-ik_canvas,bg-FFFFFF,w-43,h-12,r-max,rt-315,lxc-bw_mul_0.89,lyc-bh_mul_0.88_add_11,l-end')

_konkurs_cache = {'data': None, 'time': 0}
user_states = {}

# Admin rasm yuborganda albom (media group)ni yig'ish uchun bufer
# {media_group_id: {'file_ids': [...], 'task': asyncio_handle}}
_photo_groups = {}
# (_single_photo_lock olib tashlandi — E7: hech qayerda o'qilmasdi)
# BUGUN222 (2026-10-15: ketma-ket rasmlardan 37 e'lon — 6 tasiga takror raqam, 2 rasm yo'qoldi, №253 da aralash):
#  · admin rasmlaridan e'lon ochish — BITTA navbatda (1 ish ipi): albom = bitta e'lon, e'lonlar ketma-ket ochiladi.
#    Ilgari har albom / rasm o'z ipida bir vaqtda botCreateElon ni chaqirardi.
#  · _photo_qulf — _photo_groups ga (event loop ipi qo'shadi, navbat ipi oladi) bir vaqtda tegilmasin.
#  · getFile / yuklab olish / ImageKit — vaqt tugasa yoki server xatosi bo'lsa 3 marta qayta (1, 2, 4 s).
# BUGUN252 §1 (2026-10-18): albom kutish — har bo'lak kelganda qayta boshlanadi (ALBOM_KUTISH), lekin 1-bo'lakdan
#  ALBOM_MAKS dan oshmaydi: bitta albom ikki e'lon bo'lmasin. Navbatga 1-bo'lak kelgan payt qo'yiladi — albomlar va bitta
#  rasmlar kelgan tartibda, bittasi tugab keyingisi. §2: javob — bitta progress xabar («⏳ 12/20», JARAYON_ORALIQ da tahrir).
ALBOM_KUTISH = 3.0
ALBOM_MAKS = 10.0
JARAYON_ORALIQ = 5.0
RASM_QAYTA_KUTISH = (1, 2, 4)
_photo_qulf = threading.Lock()
_elon_navbat = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='elon-navbat')

# ── ELON YUBORISH ─────────────────────────────────────────
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1058186533'))

# ── B33 (BUGUN42): admin xabarlari — alohida yopiq guruhda, mavzular (Topics) bo'yicha ──
# Render env ADMIN_GURUH = "-1001234567890 post=12 olx=13 stat=14 mijoz=15 kollaj=16" — guruhda /guruh buyrug'i
# mavzularni o'zi ochadi va shu qatorni yozib beradi. Env bo'sh — hammasi eskicha admin lichkasiga (ADMIN_ID).
# Guruhdan faqat ADMIN_ID odamning xabari qabul qilinadi. Mijoz bilan yozishma o'zgarmaydi.
GURUH_MAVZULAR = [('post', '📢 Postlar'), ('olx', '🛒 OLX'), ('stat', '📊 Statistika'),
                  ('mijoz', '💬 Mijozlar'), ('kollaj', '🖼 Kollajlar'),
                  # MS3.2 (BUGUN56, 2026-10-08): rasm yuklash — har bo'limga o'z mavzusi. Shu mavzuga tashlangan rasm(lar)dan
                  # chala e'lon yaratiladi va javobdagi tugma saytni o'sha bo'limda ochadi. Lichkadan — avvalgidek (Mobile).
                  ('rasm_mobile', '📱 Rasm · Mobile'), ('rasm_pc', '💻 Rasm · PC'), ('rasm_camera', '📷 Rasm · Camera'),
                  # BUGUN244 (2026-10-17): saytdagi AI yordamchi — har 5 soatda hisobot (ai_hisobot_loop). Claude / qul ishlari — bu yerga EMAS.
                  ('ai', '🤖 AI yordamchi'),
                  # BUGUN252 §4 (2026-10-18): rasm ombori — e'lon OCHILMAYDI: rasm ImageKit /rasmlar ga, Store «Rasmlar»
                  # varag'iga; izohda e'lon raqami («213») — o'sha e'longa qo'shiladi. Saytda «🖼 Rasmlardan tanlash».
                  ('rasmlar', '🖼 Rasmlar')]


def rasm_yonalish(joy):
    """Admin rasmi qaysi bo'limga: guruhning «Rasm · …» mavzusidan — o'sha yo'nalish; boshqa joydan — None (avvalgidek)."""
    thread = getattr(joy, 'thread', None)
    if not thread or not GURUH.get('id') or int(joy) != GURUH['id']:
        return None
    return next((k[5:] for k, _ in GURUH_MAVZULAR if k.startswith('rasm_') and GURUH.get(k) == thread), None)


def guruh_oqi(qator):
    """"-100… post=12 …" → {'id': -100…, 'post': 12, …} yoki {} (buzuq / bo'sh)."""
    q = (qator or '').split()
    if not q or not re.fullmatch(r'-100\d{5,15}', q[0]):
        return {}
    g = {'id': int(q[0])}
    for bolak in q[1:]:
        k, _, v = bolak.partition('=')
        if k in dict(GURUH_MAVZULAR) and v.isdigit():
            g[k] = int(v)
    return g


def guruh_qator(g):
    return ' '.join([str(g['id'])] + [f'{k}={g[k]}' for k, _ in GURUH_MAVZULAR if g.get(k)])


GURUH = guruh_oqi(os.environ.get('ADMIN_GURUH', ''))


class Joy(int):
    """chat_id + mavzu (message_thread_id). int kabi ishlaydi (== , dict kaliti, JSON) — mavzu `req.post` da qo'shiladi."""
    def __new__(cls, chat, thread=None):
        o = super().__new__(cls, chat)
        o.thread = thread
        return o


def admin_joy(bolim):
    """Adminga xabar qayerga: guruh sozlangan bo'lsa — guruhning o'sha mavzusi, aks holda lichka (eskicha)."""
    if GURUH.get('id'):
        return Joy(GURUH['id'], GURUH.get(bolim))
    return ADMIN_ID


def admin_mi(chat_id):
    """Admin buyruq/tugma joyi: lichka yoki sozlangan guruh (guruhda odam ADMIN_ID ekani handle_update da tekshiriladi)."""
    return chat_id == ADMIN_ID or bool(GURUH.get('id')) and chat_id == GURUH['id']


class _TgReq:
    """`requests` o'rniga: send…/copy…/forward… so'rovida chat_id Joy (mavzuli) bo'lsa — message_thread_id qo'shiladi.
    Mavzu o'chirilgan bo'lsa (400 «thread») — mavzusiz qayta yuboriladi (xabar yo'qolmasin)."""
    def __init__(self, asl):
        self._asl = asl  # asl `requests` moduli (req = _TgReq(req) dan keyin global req — shu obyekt)

    def __getattr__(self, nom):
        return getattr(self._asl, nom)

    def post(self, url, **kw):
        j = kw.get('json')
        usul = url.rsplit('/', 1)[-1]
        if (isinstance(j, dict) and getattr(j.get('chat_id'), 'thread', None)
                and usul.startswith(('send', 'copy', 'forward')) and 'message_thread_id' not in j):
            r = self._asl.post(url, **dict(kw, json=dict(j, message_thread_id=j['chat_id'].thread)))
            if r.status_code == 400 and 'thread' in (r.text or '').lower():
                logger.warning(f'mavzu {j["chat_id"].thread} topilmadi — mavzusiz yuborildi')
                r = self._asl.post(url, **kw)
            return r
        return self._asl.post(url, **kw)


_TARMOQ_XATO = (req.Timeout, req.ConnectionError)   # BUGUN232: _sheet_oqi qayta urinadigan xatolar (asl modul)
req = _TgReq(req)


# 3110 (Owner, 2026-10-21): /guruh ochgan mavzular GURUH da faqat xotirada edi — bot qayta ishga tushganda yo'qolar, /guruh
# esa yangilarini ochar edi (25 ta mavzu to'plandi). Endi qator Apps Script «Script Properties» ga (ADMIN_GURUH, action
# guruhHolat) yoziladi va ishga tushganda o'qiladi. Jadvaldagi qator env ADMIN_GURUH dan USTUN; jadval bo'sh bo'lsa env
# (bo'lsa) jadvalga ko'chiriladi. Jadval o'qilmaguncha /guruh mavzu OCHMAYDI (takror bo'lmasin).
_guruh_holat = {'yuklandi': False, 'saqlanmagan': False}


def guruh_sheet_oqi():
    """Jadvaldagi ADMIN_GURUH qatori ('' — hali yo'q) yoki None (tarmoq / eski Apps Script)."""
    j = _kk_sheet('guruhHolat', timeout=20)
    return str(j.get('qator') or '') if j and j.get('ok') else None


def guruh_sheet_yoz(qator):
    j = _kk_sheet('guruhHolat', timeout=20, yoz=1, qator=qator)
    return bool(j and j.get('ok') and j.get('qator') == qator)


def guruh_yuklash():
    """Jadvaldagi GURUH ni xotiraga oladi. True — tayyor (yoki jadval umuman ulanmagan: eskicha, faqat env)."""
    global GURUH
    if _guruh_holat['yuklandi']:
        return True
    if not SHEET_URL or not API_KEY:
        _guruh_holat['yuklandi'] = True
        return True
    qator = None
    for urinish in range(3):
        qator = guruh_sheet_oqi()
        if qator is not None:
            break
        time.sleep(3)
    if qator is None:
        logger.error("guruh: jadvaldan o'qib bo'lmadi (tarmoq yoki Apps Script eski)")
        return False
    g = guruh_oqi(qator)
    if g:
        GURUH = g
        logger.info(f"guruh: jadvaldan yuklandi ({len(g) - 1} mavzu)")
    elif GURUH.get('id'):
        _guruh_holat['saqlanmagan'] = not guruh_sheet_yoz(guruh_qator(GURUH))   # env dagi qator — jadvalga ko'chadi
    _guruh_holat['yuklandi'] = True
    return True


async def guruh_tiklash():
    """Ishga tushganda (fonda): webhook kutmaydi."""
    try:
        await blok(guruh_yuklash)
    except Exception as e:
        logger.error(f'guruh_tiklash: {type(e).__name__}')


# 3213: ikki /guruh bir vaqtda (qayta bosish, ikki qurilma) ikkalasi ham «yo'q» mavzuni ko'rib, ikki martadan ochardi (rasmdagi
# «Rasm · Camera / Mobile / PC» takrori). Endi /guruh navbat bilan: ikkinchisi birinchisi saqlagan GURUH ni ko'radi.
_guruh_qulf = threading.Lock()


# 3213.1 (Owner 2026-10-27): guruhdagi mavzularning hammasi o'chirildi — /guruh «allaqachon bor» deb o'chgan mavzular havolasini
# berdi (saqlangan id'ni Telegram'da tekshirmasdi). Endi har saqlangan mavzu tekshiriladi: avval reopenForumTopic (xabarsiz;
# ochiq mavzu — «TOPIC_NOT_MODIFIED», yopig'i ochiladi), javob noaniq bo'lsa — ovozsiz sinov xabari (darhol o'chiriladi).
_MAVZU_YOQ = ('TOPIC_ID_INVALID', 'TOPIC_DELETED', 'THREAD NOT FOUND', 'THREAD_INVALID', 'TOPIC NOT FOUND')


def _tg_j(usul, j):
    try:
        return req.post(f'{TG_API}/{usul}', json=j, timeout=10).json()
    except Exception as e:
        return {'ok': False, 'description': f'tarmoq: {type(e).__name__}'}


def mavzu_bormi(chat, thread):
    """Mavzu Telegram'da bormi: True — bor, False — o'chirilgan, None — bilib bo'lmadi (tarmoq / huquq — eskisi qoladi)."""
    j = _tg_j('reopenForumTopic', {'chat_id': chat, 'message_thread_id': thread})
    d = str(j.get('description', '')).upper()
    if j.get('ok') or 'NOT_MODIFIED' in d:
        return True
    if any(s in d for s in _MAVZU_YOQ):
        return False
    # chat_id — oddiy int (Joy emas): _TgReq «thread» xatosida mavzusiz qayta yubormasin
    j = _tg_j('sendMessage', {'chat_id': int(chat), 'message_thread_id': thread, 'text': '🔎',
                              'disable_notification': True})
    if j.get('ok'):
        _tg_j('deleteMessage', {'chat_id': int(chat), 'message_id': j['result']['message_id']})
        return True
    d = str(j.get('description', '')).upper()
    return False if any(s in d for s in _MAVZU_YOQ) else None


def guruh_sozla(chat, forum, xabar_chat, yangi=False):
    with _guruh_qulf:
        _guruh_sozla(chat, forum, xabar_chat, yangi)


def _guruh_sozla(chat, forum, xabar_chat, noldan=False):
    """/guruh (guruhda, admin): YO'Q mavzularni ochadi (borlari takrorlanmaydi), GURUH ni xotirada yoqadi va jadvalga
    saqlaydi — bot qayta ishga tushsa ham shu to'plam. Oxirida ishlatilayotgan mavzular ro'yxati chiqadi.
    Saqlangan mavzu Telegram'da o'chirilgan bo'lsa — yangidan ochiladi. «/guruh yangi» — eskilarini unutib, hammasi noldan."""
    global GURUH
    if not forum:
        send_msg(xabar_chat, "⚠️ Bu guruhda «Topics» (Mavzular) yoqilmagan: guruh sozlamalari → Topics → yoqing, "
                             "keyin /guruh ni qayta yuboring.")
        return
    if not guruh_yuklash():
        send_msg(xabar_chat, "⚠️ Saqlangan mavzular jadvaldan o'qilmadi — takror mavzu ochilmasin deb to'xtadim. "
                             "1 daqiqadan keyin /guruh ni qayta yuboring.")
        return
    g = dict(GURUH) if GURUH.get('id') == chat and not noldan else {'id': chat}
    ochirilgan, nomalum = [], []
    for k, nom in GURUH_MAVZULAR:
        if g.get(k):
            bor = mavzu_bormi(chat, g[k])
            if bor is False:
                del g[k]
                ochirilgan.append(k)
            elif bor is None:
                nomalum.append(nom)
    yangi = [(k, nom) for k, nom in GURUH_MAVZULAR if not g.get(k)]
    ochildi, xato = [], None
    for k, nom in yangi:
        try:
            j = req.post(f'{TG_API}/createForumTopic', json={'chat_id': chat, 'name': nom}, timeout=10).json()
        except Exception as e:
            j = {'description': str(e)}
        if not j.get('ok'):
            xato = (nom, str(j.get('description', '')))
            break
        g[k] = j['result']['message_thread_id']
        ochildi.append((k, nom))
    if ochildi or ochirilgan:   # chala bo'lsa ham saqlanadi: ochilgan mavzu yo'qolmasin, o'chgan id qolmasin
        GURUH = g
        _guruh_holat['saqlanmagan'] = True
    if _guruh_holat['saqlanmagan']:
        _guruh_holat['saqlanmagan'] = not guruh_sheet_yoz(guruh_qator(GURUH))
    for k, nom in ochildi:
        send_msg(Joy(chat, g[k]), f"{nom} — shu mavzuga rasm tashlang: chala e'lon shu bo'limga yaratiladi."
                 if k.startswith('rasm_') else
                 f"{nom} — shu mavzuga rasm tashlang: e'lon ochilmaydi, rasm «Rasmlar» omboriga tushadi (saytda "
                 "«🖼 Rasmlardan tanlash»). Izohga e'lon raqamini (masalan 213) yozsangiz — rasm o'sha e'longa qo'shiladi."
                 if k == 'rasmlar' else
                 f"{nom} — saytdagi AI yordamchi hisoboti shu yerga keladi (Toshkent: 05, 10, 15, 20, 01)."
                 if k == 'ai' else f"{nom} — shu mavzuga shu turdagi xabarlar keladi.")
    if xato:
        send_msg(xabar_chat, f"⚠️ «{xato[0]}» mavzusi ochilmadi: <code>{html_escape(xato[1])}</code>\n"
                             "Botni guruhga admin qiling va «Mavzularni boshqarish» huquqini bering, keyin /guruh.")
        if not ochildi:
            return
    if GURUH.get('id') != chat:
        return
    royxat = '\n'.join(f'• <a href="https://t.me/c/{str(chat)[4:]}/{GURUH[k]}">{nom}</a>'
                       for k, nom in GURUH_MAVZULAR if GURUH.get(k))
    bosh = (f"✅ Guruh tayyor — {len(ochildi)} ta yangi mavzu ochildi" if ochildi else
            "ℹ️ Mavzular allaqachon bor (Telegram'da tekshirildi) — yangi mavzu ochilmadi")
    bosh += (" (/guruh yangi — hammasi noldan)." if noldan else
             f" ({len(ochirilgan)} tasi o'chirilgan edi — yangidan ochildi)." if ochirilgan else ".")
    if nomalum:
        bosh += f"\n⚠️ Tekshirib bo'lmadi, eskisi qoldi: {', '.join(nomalum)}. Hammasini noldan: /guruh yangi"
    oxir = ("Doimiy saqlandi: bot qayta ishga tushsa ham <b>shu mavzular</b> ishlaydi (oxirgi /guruh)."
            if not _guruh_holat['saqlanmagan'] else
            "⚠️ Doimiy saqlab bo'lmadi — bot qayta ishga tushsa yo'qoladi. Birozdan keyin /guruh ni qayta yuboring.")
    send_msg(xabar_chat, f"{bosh}\nBot hozir shu mavzularni ishlatyapti:\n{royxat}\n"
                         f"Guruhdagi boshqa mavzularning hammasi ortiqcha — o'chirsangiz bo'ladi.\n{oxir}")


# 3214.1 (Owner 2026-10-27): «/guruh namuna» — har saqlangan mavzuga bot o'sha yerga HAQIQATDA yuboradigan xabar turidan bittadan
# namuna (ovozsiz, «🧪 NAMUNA —» bilan). Ma'lumot — mavjud e'lon yoki soxta «Test Mijoz»; tugmalar ishlamaydi (callback «namuna»).
# Faqat shu buyruq bilan — kanal, mijoz, boshqa chatga hech narsa ketmaydi; mavzu ochilmaydi / o'chirilmaydi.
_NAMUNA_TUGMA = {"inline_keyboard": [[{"text": "🖼 Kollajga o'tkazish", "callback_data": "namuna"}],
                                     [{"text": "🗑 Postni o'chirish", "callback_data": "namuna"}]]}


def _namuna_elon():
    """(num, olx_matn) — eng katta raqamli faol e'lon; xotira bo'sh — (None, None)."""
    try:
        by_num, models = elon_cache_hammasi()
        faol = [n for n, e in by_num.items() if str(n).isdigit() and elon_status(e) == 'active']
        if not faol:
            return None, None
        num = max(faol, key=int)
        return num, build_olx_text(by_num[num], models)[1]
    except Exception as e:
        logger.error(f'namuna e\'lon: {type(e).__name__}')
        return None, None


def guruh_namunalar(hozir=None):
    """[(kalit, qachon, matn, tugma)] — har mavzu uchun: qaysi hodisada keladi va o'sha xabar matni (yoki None — bot yubormaydi)."""
    hozir = int(hozir or time.time())
    num, olx = _namuna_elon()
    n = num or '0'
    mijoz = _kirgan_nom({'id': ADMIN_ID, 'first_name': 'Test Mijoz'})
    ai = ai_hisobot_matn({'savol': 3, 'mijoz': 2, 'ai': 2, 'skript': 1, 'adminga': 0,
                          'top': [{'matn': 'iPhone 13 narxi'}, {'matn': 'yetkazib berish'}]}, hozir, hozir - 5 * 3600)
    rasm = {k: _elon_tayyor_matn({'ok': True, 'num': '0'}, 3, k[5:]) for k, _ in GURUH_MAVZULAR if k.startswith('rasm_')}
    return [
        ('post', "e'lon kanalga chiqqanda (saytdan / /post / 💧 tomchi); chiqmasa — ⚠️ xato",
         f"📣 №{n} kanalga chiqdi (id 0) — {POST_CHANNEL}", _NAMUNA_TUGMA),
        ('olx', "saytda «Menga yuborish» bosilganda: OLX matni, keyin kanal e'loni va rasmlar albomi",
         html_escape(olx) if olx else "ELON RAQAMI: #0\n(e'lonlar hali yuklanmagan — haqiqiysida OLX matni shu yerda)", None),
        ('stat', "bot o'zi yubormaydi — shu mavzuda /stat yozsangiz, javob shu yerga", None, None),
        ('mijoz', "kimdir tech kanalga kirganda; 1 daqiqadan keyin Mobile a'zoligi",
         f"✅ {mijoz} tech kanalga kirdi\n📱 {mijoz} Mobile'ga kirdi\n🔴 <b>{mijoz} Mobile'ga kirmadi</b>", None),
        ('kollaj', "bot o'zi yubormaydi («🖼 Kollajga o'tkazish» tugmasi — 📢 Postlar xabarida)", None, None),
        *[(k, "shu mavzuga rasm tashlanganda (chala e'lon ochiladi)", *rasm[k]) for k in rasm],
        ('ai', "har 5 soatda (Toshkent: 05, 10, 15, 20, 01)", ai, None),
        ('rasmlar', "shu mavzuga rasm tashlanganda (e'lon ochilmaydi, Rasmlar omboriga)",
         "📥 3 rasm Rasmlar omboriga saqlandi · izoh: test", None),
    ]


def _namuna_yubor(chat, thread, matn, tugma=None):
    """Mavzuga ovozsiz. (ok, izoh). chat_id — oddiy int: mavzu yo'q bo'lsa General'ga ketib qolmasin (_TgReq)."""
    j = {'chat_id': int(chat), 'message_thread_id': thread, 'text': matn[:4000], 'parse_mode': 'HTML',
         'disable_notification': True, 'link_preview_options': {'is_disabled': True}}
    r = _tg_j('sendMessage', dict(j, reply_markup=tugma) if tugma else j)
    if r.get('ok'):
        return True, ''
    xato = str(r.get('description', ''))[:120]
    if tugma and _tg_j('sendMessage', j).get('ok'):   # tugmani guruh qabul qilmadi — matn baribir ko'rinsin
        return True, f'tugmasiz yuborildi — tugma rad etildi: {xato}'
    return False, xato


def guruh_namuna(chat, xabar_chat, kut=0.3):
    if not guruh_yuklash():
        send_msg(xabar_chat, "⚠️ Saqlangan mavzular jadvaldan o'qilmadi — 1 daqiqadan keyin /guruh namuna ni qayta yuboring.")
        return
    if GURUH.get('id') != chat:
        send_msg(xabar_chat, "⚠️ Bu guruhda bot mavzulari saqlanmagan — avval /guruh yuboring.")
        return
    nomi = dict(GURUH_MAVZULAR)
    qator, yetdi = [], 0
    for k, qachon, matn, tugma in guruh_namunalar():
        if not GURUH.get(k):
            qator.append(f"• {nomi[k]} — mavzu yo'q (/guruh)")
            continue
        bosh = f"🧪 NAMUNA — {nomi[k]}\n<i>Qachon: {qachon}</i>"
        ok, izoh = _namuna_yubor(chat, GURUH[k], f"{bosh}\n\n{matn}" if matn else
                                 f"🧪 NAMUNA — bu mavzuga bot hozircha hech narsa yubormaydi\n<i>{qachon}</i>", tugma)
        yetdi += ok
        qator.append(f"• {nomi[k]} — {'✅' if ok else '❌'}" + (f" <code>{html_escape(izoh)}</code>" if izoh else ''))
        time.sleep(kut)
    send_msg(xabar_chat, f"🧪 Namuna: {yetdi}/{len(GURUH_MAVZULAR)} mavzuga yuborildi (ovozsiz)\n" + '\n'.join(qator))


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


# ═══ BUGUN260-7: rang va xususiyat lug'ati — sayt sayt/js/02-yordamchi.js (RANG_ROYXAT, XUSUSIYAT_LUGAT) bilan bir xil ═══
# NEGA: g'ilof «MagSafe / Stand» endi `xususiyat` ustunida (JSON ["magsafe","stand"]), `storage` — faqat xotira. Ilgari
# sarlavha `name (storage)` edi: migratsiyadan keyin g'ilof postidan «(MagSafe)» yo'qolardi, xotira bo'sh bo'lsa «()» chiqardi.
# Orqaga moslik: ustun bo'sh bo'lsa — eski `storage` dagi «MagSafe» o'qiladi (migratsiyagacha ham sarlavha o'zgarmaydi).
RANG_ROYXAT = [
    ('Qora', 'Чёрный'), ('Oq', 'Белый'), ("Ko'k", 'Синий'), ('Havorang', 'Голубой'), ('Qizil', 'Красный'),
    ('Yashil', 'Зелёный'), ('Sariq', 'Жёлтый'), ("To'q sariq", 'Оранжевый'), ('Kulrang', 'Серый'), ('Pushti', 'Розовый'),
    ('Binafsha', 'Фиолетовый'), ('Jigarrang', 'Коричневый'), ('Kumush', 'Серебристый'), ('Oltin', 'Золотой'),
    ("To'q ko'k", 'Тёмно-синий'), ('Shaffof', 'Прозрачный'), ('Qora shaffof', 'Чёрный прозрачный'),
    ('Obsidian Black (Qora)', 'Obsidian Black (Черный)'), ('Porcelain (Oq)', 'Porcelain (Белый)'),
    ('Snow White (Oq)', 'Snow White (Белый)'), ('Moonstone', 'Moonstone'), ('Hazel', 'Hazel'), ('Lemongrass', 'Lemongrass'),
    ('Jade', 'Jade'), ("Bay (Ko'k)", 'Bay (Синий)'), ('Rose Quartz', 'Rose Quartz'),
]
XUSUSIYAT_LUGAT = [
    ('magsafe', 'MagSafe', 'MagSafe', re.compile(r'mag\s*safe', re.I)),
    ('magfit', 'MagFit', 'MagFit', re.compile(r'mag\s*fit', re.I)),
    ('stand', 'Stand', 'Подставка', re.compile(r'stand|подставк|tayanch', re.I)),
    ('kamera', 'Kamera himoyasi', 'Защита камеры', re.compile(r'kamera\s*himoya|защит\w*\s*камер|camera\s*(guard|protect)', re.I)),
]


def rang_kalit(s):
    """AppScript.gs / sayt rangKalit bilan bir xil: katta-kichik harf, «ko'k / ko‘k / koʻk / kok» farqsiz."""
    return re.sub(r'\s+', ' ', re.sub(r"['‘’ʻʼ`´]", '', str(s or '').lower())).strip()


def rang_ru(item):
    """E'lon rangining ruschasi: `colorRu` → lug'at → admin qo'lda yozgani (getAll `rangLugat`) → o'zbekchasi."""
    ru = str((item or {}).get('colorRu') or '').strip()
    uz = str((item or {}).get('color') or '').strip()
    if ru or not uz:
        return ru
    k = rang_kalit(uz)
    for a, b in RANG_ROYXAT:
        if rang_kalit(a) == k:
            return b
    qolda = _ELON_CACHE.get('rangLugat') or {}
    yoz = qolda.get(k) if isinstance(qolda, dict) else None
    if isinstance(yoz, dict) and str(yoz.get('ru') or '').strip():
        return str(yoz['ru']).strip()
    return uz


def _xus_lugat():
    """Doimiy lug'at + admin ⚙️ Sozlama'da qo'shgani (getAll `xusLugat`: [{k, uz, ru}])."""
    out = list(XUSUSIYAT_LUGAT)
    bor = {x[0] for x in out}
    for x in (_ELON_CACHE.get('xusLugat') or []):
        if not isinstance(x, dict):
            continue
        k = str(x.get('k') or '').strip().lower()
        uz = str(x.get('uz') or '').strip()
        if k and uz and k not in bor:
            bor.add(k)
            out.append((k, uz, str(x.get('ru') or '').strip() or uz, re.compile(r'\s*'.join(map(re.escape, uz.split())), re.I)))
    return out


def _xus_matndan(s):
    v = str(s or '').strip()
    return [x[0] for x in _xus_lugat() if v and x[3].search(v)]


def storage_xususiyatmi(s):
    """storage qiymati xususiyatmi (xotira emas) — «MagSafe», «Magsafe, stand»; «128GB» — yo'q."""
    v = str(s or '').strip()
    return bool(v) and not re.search(r'\d\s*(gb|tb)', v, re.I) and bool(_xus_matndan(v))


def elon_xususiyat(item):
    """E'lon xususiyat kalitlari: `xususiyat` ustuni (JSON yoki vergul) — bo'sh bo'lsa eski `storage` («MagSafe»)."""
    item = item or {}
    v = item.get('xususiyat')
    if v not in (None, ''):
        a = v
        if isinstance(v, str):
            try:
                a = json.loads(v)
            except Exception:
                a = v.split(',')
        if not isinstance(a, list):
            a = [a]
        lug = _xus_lugat()
        out = []
        for x in a:
            k = str('' if x is None else x).strip().lower()
            kk = k if any(t[0] == k for t in lug) else (_xus_matndan(k) or [''])[0]
            if kk and kk not in out:
                out.append(kk)
        if out:
            return out
    st = item.get('storage')
    return _xus_matndan(st) if storage_xususiyatmi(st) else []


def xususiyat_matn(item, lang='uz'):
    """«MagSafe, Stand» (ru — «MagSafe, Подставка»)."""
    nom = {x[0]: (x[2] if lang == 'ru' else x[1]) for x in _xus_lugat()}
    return ', '.join(nom.get(k, k) for k in elon_xususiyat(item))


def elon_xotira(item):
    """Haqiqiy xotira: storage — faqat xususiyat bo'lmasa («MagSafe» → '')."""
    s = str((item or {}).get('storage') or '').strip()
    return '' if storage_xususiyatmi(s) else s


def elon_qavs(item, lang='uz'):
    """Nom yonidagi qavs ichi — xotira va xususiyat («256GB» · «MagSafe, Stand»); ikkalasi ham bo'sh — ''."""
    return ', '.join(x for x in (elon_xotira(item), xususiyat_matn(item, lang)) if x)


def holati_matni(cond, cycle):
    """condition + cycle bo'yicha (uz_qator, ru_qator, emoji) qaytaradi."""
    sikl_uz = f" ({cycle} tsikl)" if cycle else ""   # 3184.5: «98 tsikl» (ilgari «98tsikl»)
    sikl_ru = f" ({cycle} цикл)" if cycle else ""
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
        r = req.post(f'{TG_API}/sendMessage', json=payload, timeout=8)
    except Exception as e:
        logger.error(f'sendMessage: {e}')
        return False
    try:
        return bool(r.json().get('ok'))   # BUGUN233: /konkurs/boshla — xabar mijozga yetdimi (botni boshlamagan — 403)
    except Exception:
        return False


# /start javobi. E7: animatsiya file_id kodga qotirilgan — u o'chib ketsa
# (yoki boshqa botga ko'chirilsa) mijoz HECH NARSA olmasdi. Endi xato bo'lsa
# oddiy matn + tugma ketadi: mijoz baribir saytga kira oladi.
START_CAPTION = (
    "🇺🇿 <b>Barcha aktual smartfonlarimiz saytimizga joylandi</b>\n"
    "🇷🇺 <b>Все актуальные смартфоны уже на нашем сайте</b>\n\n"
    "Kirish uchun bosing / Нажмите, чтобы перейти 👇"
)
START_KB = {"inline_keyboard": [[{
    "text": "🛍 Saytga kirish / Перейти на сайт",
    "web_app": {"url": SAYT_URL}
}]]}


START_RASM = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kanal_xush_kelibsiz.png')
_start_rasm = {'file_id': ''}


def send_start(chat_id):
    """/start: rasm + caption (matn) + tugma. Caption 1024 belgidan oshsa — rasm alohida, keyin matn + tugma.
    Rasm yuborilmasa (fayl yo'q, Telegram xatosi) — oddiy matn + tugma: mijoz baribir saytga kira oladi."""
    sig = len(START_CAPTION) <= 1024
    maydon = {'chat_id': chat_id}
    if sig:
        maydon.update(caption=START_CAPTION, parse_mode='HTML', reply_markup=START_KB)
    try:
        if _start_rasm['file_id']:
            r = req.post(f'{TG_API}/sendPhoto', json=dict(maydon, photo=_start_rasm['file_id']), timeout=15)
        else:
            forma = {k: (v if isinstance(v, (str, int)) else json.dumps(v, ensure_ascii=False)) for k, v in maydon.items()}
            with open(START_RASM, 'rb') as f:
                r = req.post(f'{TG_API}/sendPhoto', data=forma, files={'photo': ('kanal_xush_kelibsiz.png', f, 'image/png')}, timeout=30)
        j = r.json() if r.status_code == 200 else {}
        if j.get('ok'):
            fotolar = (j.get('result') or {}).get('photo') or []
            if fotolar and fotolar[-1].get('file_id'):
                _start_rasm['file_id'] = fotolar[-1]['file_id']
            if not sig:
                send_msg(chat_id, START_CAPTION, START_KB)
            return
        _start_rasm['file_id'] = ''
        logger.error(f'/start sendPhoto: {r.text[:200]}')
    except Exception as e:
        logger.error(f'/start sendPhoto: {e}')
    send_msg(chat_id, START_CAPTION, START_KB)   # zaxira: rasmsiz


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
# Sayt xush kelibsizi ketadigan kanallar: env XUSH_KANALLAR («@nuqta_tech_mobile @…», bo'sh joy bilan) — qo'yilmasa TEST kanal.
XUSH_KANALLAR = tuple(os.environ.get('XUSH_KANALLAR', '').split()) or (TEST_CHANNEL,)
# ── B38 (K9 = ha, K10 = a, K12 = b — «Do'kon» tugmasi YO'Q): HUB — tech kanal ──
# Mijozga faqat «Nuqta tech» aytiladi → tech kanalga kiradi → bot FAQAT unga ko'rinadigan xabar: 3 yo'nalish tugmasi.
# env TECH_KANAL_ID (@nuqta_tech yoki -100…) — bo'sh bo'lsa hub o'chiq. Yo'nalish kanallari manzili — yuqoridagi YON_KANAL
# (env KANAL_MOBILE / KANAL_CAMERA / KANAL_PC); sukut — K10 manzillari. Sinov: TECH_KANAL_ID = TEST kanal.
TECH_KANAL = os.environ.get('TECH_KANAL_ID', '').strip()
TECH_SUKUT = '@nuqta_tech'   # 3110: env bo'sh bo'lsa ham tech kanalga kirish kuzatiladi (hub xush kelibsizi — faqat env bilan)
HUB_YONALISHLAR = (   # BUGUN213: tartib PC · Kamera · Smartfon (foydalanuvchi)
    ('💻 PC', YON_KANAL['pc'][1]),
    ('📷 Kamera', YON_KANAL['camera'][1]),
    ('📱 Smartfon', YON_KANAL['mobile'][1]),
)
HUB_MATN = (
    f"🇺🇿 <b>{BREND}'ga xush kelibsiz!</b> Qaysi yo'nalish kerak — tanlang 👇\n\n"
    f"🇷🇺 <b>Добро пожаловать в {BREND}!</b> Выберите направление 👇"
)
HUB_KB = {"inline_keyboard": [[{"text": t, "url": f"https://t.me/{u}"} for t, u in HUB_YONALISHLAR]]}
# BUGUN213: @nuqta_tech KANALIGA qo'shilganda (ephemeral) — foydalanuvchining o'z namunasi (aynan). Botdagi oddiy /start esa
# HUB_MATN + callback tugmalar (BOT_HUB_KB) — ikkala joy alohida.
KANAL_HUB_MATN = (
    '<tg-emoji emoji-id="5344058361363082545">⚡️</tg-emoji> <b>Nuqta tech kanaliga xush kelibsiz!</b>\n'
    "Yangiliklar, video obzorlar va yangi kelgan mahsulotlar — shu yerda.\n\n"
    "<b>Добро пожаловать в Nuqta tech!</b>\n"
    "Новости, видеообзоры и новинки — здесь.\n\n"
    "Sizni nima qiziqtiradi? / Что вам интересно? 👇"
)
# ── BUGUN213: ODDIY /start (payload yo'q, lichka) → HUB_MATN + 3 tugma (callback, sayt ochmaydi) → tanlangan yo'nalish posti ──
# Foydalanuvchi (2026-10-15): «botga linksiz to'g'ridan-to'g'ri start bosgan odamga kelsin va 3 tasidan bittasini tanlasa
# o'sha yo'nalishning postini yuborsin». Maxsus havolali /start (?start=<payload>) — eskicha (3 yo'nalish chiqmaydi, kasha bo'lmasin).
# Tartib: PC · Kamera · Smartfon. Post matni — tanlangan yo'nalish; tugma — saytni o'sha yo'nalishda ochadi (?p=y_<yo'nalish>).
BOT_HUB_TARTIB = (('pc', '💻 PC'), ('camera', '📷 Kamera'), ('mobile', '📱 Smartfon'))
# BUGUN224 (foydalanuvchi, 2026-10-16): «oradagi smartfonlarni shu yerga joyladik qismi shart emas, bo'limni bosganda darhol
# sayt ochilaversin» — tugma endi web_app (sayt o'sha yo'nalishda), oraliq post yo'q. Eski xabarlardagi `yon:` tugmasi
# (callback) — eskicha ishlayveradi (yonalish_post). «Smartfonlarni saytga joyladik» matni — faqat kanal welcome'ida (XUSH_MATN).
BOT_HUB_KB = {"inline_keyboard": [[{"text": t, "web_app": {"url": SAYT_URL + f'?p=y_{k}'}} for k, t in BOT_HUB_TARTIB]]}
# Yo'nalish havolasi (?start=mobile | y_mobile …) — hub emas, o'sha yo'nalishni ochadigan bitta tugma
YON_PAYLOAD = {p: k for k, _ in BOT_HUB_TARTIB for p in (k, f'y_{k}')}
YON_TUGMA = {'mobile': '📱 Smartfonlar / Смартфоны', 'camera': '📷 Kameralar / Камеры', 'pc': '💻 Kompyuterlar / Компьютеры'}


def send_yon_tugma(chat_id, yon):
    """?start=<yo'nalish> — o'sha yo'nalishda saytni ochadigan bitta web_app tugma (oraliq matnsiz)."""
    send_msg(chat_id, "👇", {"inline_keyboard": [[{
        "text": YON_TUGMA[yon], "web_app": {"url": SAYT_URL + f'?p=y_{yon}'}}]]})
YON_POST_MATN = {
    'mobile': (
        "🇺🇿 <b>Xush kelibsiz! Biz barcha smartfonlarimizni ushbu saytga joyladik. "
        "Kanaldan ko'ra qulayroq, albatta kirib ko'ring.</b>\n\n"
        "🇷🇺 <b>Добро пожаловать! Мы разместили все наши смартфоны на этом сайте. "
        "Это удобнее, чем канал — обязательно загляните.</b>"),
    'camera': (
        "🇺🇿 <b>Xush kelibsiz! Biz barcha kameralarimizni ushbu saytga joyladik. "
        "Kanaldan ko'ra qulayroq, albatta kirib ko'ring.</b>\n\n"
        "🇷🇺 <b>Добро пожаловать! Мы разместили все наши камеры на этом сайте. "
        "Это удобнее, чем канал — обязательно загляните.</b>"),
    'pc': (
        "🇺🇿 <b>Xush kelibsiz! Biz barcha kompyuterlarimizni ushbu saytga joyladik. "
        "Kanaldan ko'ra qulayroq, albatta kirib ko'ring.</b>\n\n"
        "🇷🇺 <b>Добро пожаловать! Мы разместили все наши компьютеры на этом сайте. "
        "Это удобнее, чем канал — обязательно загляните.</b>"),
}


# ── BUGUN213 §6b: BETA TESTER — env SINOVCHI_IDS («1367350290», bo'sh joy / vergul bilan) ──
# Faqat KONKURS: sinovchi yashirin konkursni ko'radi va qatnasha oladi (admin kabi). Kanal xush kelibsizi — HAMMA uchun
# (foydalanuvchi 17:35: «hamma uchun yoqaver unda welcome textlarni») — sinovchiga bog'liq emas.
SINOVCHI_IDS = frozenset(int(x) for x in os.environ.get('SINOVCHI_IDS', '').replace(',', ' ').split() if x.strip().isdigit())


def yon_kanal_kaliti(chat):
    """Update'dagi chat YON_KANAL dagi qaysi yo'nalish kanali ('mobile' | 'pc' | 'camera') yoki ''."""
    for kalit, (_, manzil) in YON_KANAL.items():
        if _kanal_mos(chat, '@' + manzil):
            return kalit
    return ''


# ── BUGUN226 (foydalanuvchi, 2026-10-16): /start ni qayta bosmagan ESKI mijozda eski reply-klaviatura (pastdagi matnli tugmalar)
# qolgan. Eski tugma bosilsa (u botga shu tugma matnini yuboradi) — eski klaviatura olib tashlanadi va yangi 3 tugmali /start
# xabari chiqadi. Nega: eski tugmalar yangi botda hech narsa qilmasdi («Tushunmadim»). Menyu tugmasi («Do'kon») — tegilmaydi.
_ESKI_TUGMA_SOZ = ('saytga kirish', 'saytga qaytish', 'saytni ochish', "do'kon", 'perejti na sayt', 'перейти на сайт',
                   'вернуться на сайт', 'открыть сайт', 'магазин', "kanalga a'zo bo'lish", 'kanal / канал', 'raqamni ulashish',
                   'поделиться номером', 'konkursda qatnashish', 'konkurs', 'розыгрыш')


def _eski_tugmami(text):
    """Matn — eski reply-klaviatura tugmasimi (emoji / bo'sh joy / registr hisobga olinmaydi)."""
    t = re.sub(r"[^\w\s'/]", '', str(text or '').lower().replace('’', "'"), flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t).strip()
    return bool(t) and not t.startswith('/') and len(t) <= 60 and any(t == x or t.startswith(x + ' ') for x in _ESKI_TUGMA_SOZ)


def eski_klaviatura_olib_tashla(chat_id):
    """Eski reply-klaviatura (pastdagi tugmalar) ni yopadi: remove_keyboard faqat xabar bilan ketadi — qisqa xabar yuborilib,
    darhol o'chiriladi (chatda iz qolmaydi). Xato bo'lsa jim — asosiy javobga xalaqit bermaydi."""
    try:
        r = req.post(f'{TG_API}/sendMessage', json={'chat_id': chat_id, 'text': '👇',
                                                    'reply_markup': {'remove_keyboard': True}}, timeout=8)
        mid = (r.json().get('result') or {}).get('message_id') if r.status_code == 200 else None
        if mid:
            req.post(f'{TG_API}/deleteMessage', json={'chat_id': chat_id, 'message_id': mid}, timeout=8)
    except Exception as e:
        logger.error(f'eski klaviatura: {type(e).__name__}')


def eski_mijoz_javob(chat_id):
    """Eski tugma / noma'lum matn (lichka): eski klaviatura olib tashlanadi + yangi 3 tugmali /start xabari."""
    eski_klaviatura_olib_tashla(chat_id)
    send_bot_hub(chat_id)


def send_bot_hub(chat_id):
    """Oddiy /start — «Nuqta tech'ga xush kelibsiz, qaysi yo'nalish» + 3 tugma. Qayta /start — yana chiqadi."""
    try:
        r = req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': HUB_MATN, 'parse_mode': 'HTML', 'reply_markup': BOT_HUB_KB,
        }, timeout=10)
        if r.status_code == 200 and r.json().get('ok'):
            return
        logger.error(f'bot hub: {r.text[:200]}')
    except Exception as e:
        logger.error(f'bot hub: {e}')
    send_start(chat_id)   # zaxira: eski /start — mijoz baribir saytga kira oladi


def yonalish_post(chat_id, yon):
    """3 yo'nalishdan biri bosildi — o'sha yo'nalishning xush kelibsiz posti + saytni shu yo'nalishda ochadigan tugma."""
    if yon not in YON_POST_MATN:
        return
    kb = {"inline_keyboard": [[{
        "text": START_KB["inline_keyboard"][0][0]["text"],
        "web_app": {"url": SAYT_URL + f'?p=y_{yon}'},
    }]]}
    send_msg(chat_id, YON_POST_MATN[yon], kb)


XUSH_RASM =os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kanal_xush_kelibsiz.png')
XUSH_MATN = (
    "🇺🇿 <b>Xush kelibsiz! Biz barcha smartfonlarimizni ushbu saytga joyladik. "
    "Kanaldan ko'ra qulayroq, albatta kirib ko'ring.</b>\n\n"
    "🇷🇺 <b>Добро пожаловать! Мы разместили все наши смартфоны на этом сайте. "
    "Это удобнее, чем канал — обязательно загляните.</b>"
)
XUSH_KB = {"inline_keyboard": [[{
    "text": START_KB["inline_keyboard"][0][0]["text"],   # /start dagi tugma bilan bir xil matn
    # kanal postlaridagi «Saytni ochish» bilan bir xil yo'l. B38: hozircha hamma kanalda — mobile (home); har kanal saytni o'z
    # yo'nalishida ochishi — A27 (yo'nalish g'ildiragi) bilan, sayt `startapp=<yo'nalish>` ni tushungach
    "url": f"https://t.me/{BOT_USERNAME}?startapp=home",
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
    if not isinstance(cm, dict):
        return None
    yangi = cm.get('new_chat_member') or {}
    user = yangi.get('user') or {}
    if not any(_kanal_mos(cm.get('chat'), k) for k in XUSH_KANALLAR + (TECH_KANAL or TECH_SUKUT,)) and not yon_kanal_kaliti(cm.get('chat')):
        return None   # BUGUN213: uchala yo'nalish kanali (YON_KANAL) — HAR KIMGA o'z xush kelibsizi
    if user.get('is_bot') or not user.get('id'):
        return None
    if _azo(cm.get('old_chat_member')) or yangi.get('status') not in ('member', 'restricted') or not _azo(yangi):
        return None
    return user['id']


def xush_yubor(chat_id, uid, hub=False, yon=''):
    """Kanal ichida faqat `uid` ga ko'rinadigan rasm + matn + tugma. (True, '') yoki (False, xato matni).
    hub=True (B38) — tech kanal: rasmsiz matn + 3 yo'nalish tugmasi (HUB_KB)."""
    maydon = {
        'chat_id': chat_id,
        'caption': XUSH_MATN,
        'parse_mode': 'HTML',
        'reply_markup': XUSH_KB,
        'ephemeral_message_parameters': {'receiver_user_id': uid},
    }
    if hub:
        maydon = dict(maydon, reply_markup=HUB_KB)
        maydon['text'] = KANAL_HUB_MATN
        del maydon['caption']
    elif yon:   # BUGUN213 §6b: sinovchi, haqiqiy yo'nalish kanali — o'sha yo'nalishning posti, rasmsiz
        maydon = dict(maydon, text=YON_POST_MATN[yon], reply_markup={"inline_keyboard": [[{
            "text": START_KB["inline_keyboard"][0][0]["text"],
            "url": f"https://t.me/{BOT_USERNAME}?startapp=y_{yon}"}]]})
        del maydon['caption']
    try:
        if hub or yon:
            j = req.post(f'{TG_API}/sendMessage', json=maydon, timeout=30).json()
        elif _xush['file_id']:
            j = req.post(f'{TG_API}/sendPhoto', json=dict(maydon, photo=_xush['file_id']), timeout=30).json()
        else:
            forma = {k: (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in maydon.items()}
            with open(XUSH_RASM, 'rb') as f:
                j = req.post(f'{TG_API}/sendPhoto', data=forma,
                             files={'photo': ('kanal_xush_kelibsiz.png', f, 'image/png')}, timeout=60).json()
    except Exception as ex:
        return False, f'tarmoq: {ex}'
    if not j.get('ok'):
        if not hub and not yon:
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


# 3110 (Owner, 2026-10-21): tech kanalga kirgan odam — adminga darhol «✅ … tech kanalga kirdi»; 1 daqiqadan keyin Mobile
# kanal a'zoligi tekshiriladi: a'zo — «📱 … Mobile'ga kirdi», a'zo emas — «🔴 … Mobile'ga kirmadi» (Owner mijozga Mobile
# havolasini o'zi yuboradi — ism bosilsa lichka ochiladi). Mijozga avtomatik xabar YO'Q. Taymer xotirada: 1 daqiqa ichida
# bot qayta ishga tushsa — shu odamning tekshiruvi tushib qoladi. Mobile kanalda bot admin bo'lishi shart (getChatMember).
MOBILE_KUTISH_S = 60


def _kirgan_nom(user):
    """Admin xabarida ism-havola: username bo'lsa t.me, bo'lmasa tg://user?id (lichka ochiladi)."""
    ism = ' '.join(x for x in (user.get('first_name'), user.get('last_name')) if x) or user.get('username') or str(user.get('id'))
    un = str(user.get('username') or '')
    havola = f'https://t.me/{un}' if re.fullmatch(r'\w{5,32}', un) else f"tg://user?id={user.get('id')}"
    return f'<a href="{havola}">{html_escape(ism)}</a>'


def _mobile_tekshir(user):
    azo = _kanal_azomi('@' + YON_KANAL['mobile'][1], user['id'], 'Mobile kanal')
    nom = _kirgan_nom(user)
    if azo is None:
        msg = f"⚠️ {nom} — Mobile a'zoligini tekshirib bo'lmadi (bot Mobile kanalda admin bo'lishi kerak)"
    else:
        msg = f"📱 {nom} Mobile'ga kirdi" if azo else f"🔴 <b>{nom} Mobile'ga kirmadi</b>"
    send_msg(admin_joy('mijoz'), msg)


def _mobile_rejalash(user):
    t = threading.Timer(MOBILE_KUTISH_S, _mobile_tekshir, args=(user,))
    t.daemon = True
    t.start()


def tech_kirdi(user):
    send_msg(admin_joy('mijoz'), f"✅ {_kirgan_nom(user)} tech kanalga kirdi")
    _mobile_rejalash(user)


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
    tech = _kanal_mos(chat, TECH_KANAL or TECH_SUKUT)
    if tech:
        tech_kirdi((cm.get('new_chat_member') or {}).get('user') or {'id': uid})   # 3110: «ishladi» xabari o'rniga
        if not TECH_KANAL:
            return ''   # hub o'chiq (env bo'sh) — xush kelibsiz yuborilmaydi, faqat kuzatuv
    yon = '' if _kanal_mos(chat, TECH_KANAL) else yon_kanal_kaliti(chat)   # BUGUN213: yo'nalish kanali — o'z yo'nalishi posti
    ok, xato = xush_yubor(chat.get('id'), uid, hub=_kanal_mos(chat, TECH_KANAL), yon=yon)   # B38: tech kanal — hub
    kanal = html_escape('@' + chat['username'] if chat.get('username') else str(chat.get('id', '')))
    if ok:
        logger.info(f'xush kelibsiz: {uid} -> {kanal}')
        if not _xush['ishladi'] and not tech:
            _xush['ishladi'] = True
            ism = html_escape(((cm.get('new_chat_member') or {}).get('user') or {}).get('first_name', '') or str(uid))
            send_msg(admin_joy('mijoz'), f"✅ Kanal xush kelibsiz ishladi: <b>{ism}</b> {kanal} ga qo'shildi — unga "
                               f"«faqat o'ziga ko'rinadigan» xabar ketdi.")
        return 'yuborildi'
    logger.error(f'xush kelibsiz: {xato}')
    if hozir - _xush['xato_vaqt'].get(xato, 0) >= 600:
        _xush['xato_vaqt'][xato] = hozir
        send_msg(admin_joy('mijoz'), f"⚠️ Kanal xush kelibsiz yuborilmadi ({kanal}):\n<code>{html_escape(xato)}</code>")
    return 'xato'


# BUGUN232 (2026-10-17): Apps Script odatda 4–6 s da javob beradi, lekin ba'zan 10–15 s dan oshadi — Render logida
# ReadTimeout: 10-15 19:20 (get_products 15 s, botStart 15 s), 10-16 22:05 (get_konkurs 10 s, ketma-ket 2 ta). O'qish —
# uzunroq kutish + bir marta qayta urinish (QOIDALAR_CHUQUR T8). Yozish (botStart) — navbatga, fonda qayta (pastda).
SHEET_OQISH_URINISH = 2
SHEET_OQISH_ORALIQ_S = 2


def _sheet_oqi(nom, url, timeout=25, urinish=SHEET_OQISH_URINISH):
    """Apps Script'dan O'QISH (GET). Tarmoq uzilsa / javob kechiksa — yana urinadi; oxirgisi ham o'xshamasa — xato
    yuqoriga. 🔴 Logda faqat xato turi (URL'da kalit bo'lishi mumkin)."""
    for n in range(urinish):
        try:
            return req.get(url, timeout=timeout)
        except _TARMOQ_XATO as e:
            logger.warning(f'{nom}: {type(e).__name__} ({n + 1}/{urinish})')
            if n + 1 >= urinish:
                raise
            time.sleep(SHEET_OQISH_ORALIQ_S)


def get_products(urinish=SHEET_OQISH_URINISH):
    """Sheets'dan barcha elon va modellarni oladi (action'siz so'rov)."""
    if not SHEET_URL:
        return None, None
    try:
        # BUGUN148: fid=1 — rasm_file_id ham (sayt olmaydi). BUGUN232: 15 → 30 s + qayta urinish (ro'yxat katta — 5 s+)
        r = _sheet_oqi('get_products', f"{SHEET_URL}?callback=d&fid=1", timeout=30, urinish=urinish)
        text = r.text.strip()
        data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        # G12: seriyalar ham keshda — `mos` kodlarini (p9s, phone) nomga aylantirish uchun
        if isinstance(data.get('series'), list):
            _ELON_CACHE['series'] = data['series']
        if isinstance(data.get('turkumlar'), list):      # G12 daraxt: turkum → bo'lim
            _ELON_CACHE['turkumlar'] = data['turkumlar']
        if isinstance(data.get('xusLugat'), list):       # BUGUN260-7: admin qo'shgan xususiyatlar (⚙️ Sozlama)
            _ELON_CACHE['xusLugat'] = data['xusLugat']
        if isinstance(data.get('rangLugat'), dict):      # BUGUN260-7: qo'lda yozilgan rang ruschalari
            _ELON_CACHE['rangLugat'] = data['rangLugat']
        if isinstance(data.get('guruhlar'), list):       # BUGUN251: ranglar guruhi (kanal posti) — {id: guruh}
            _ELON_CACHE['guruhlar'] = {str(g.get('id', '')).strip(): g for g in data['guruhlar']
                                       if isinstance(g, dict) and str(g.get('id', '')).strip()}
        return data.get('listings', []), data.get('models', [])
    except Exception as e:
        logger.error(f'get_products: {type(e).__name__}')
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
    """Sayt (admin) saqlagan e'lon — xotiradagi nusxa almashtiriladi.
    BUGUN148: sayt `rasm_file_id` ni olmaydi (Apps Script faqat botga beradi) — eskisi saqlanadi (bekorga qayta yozmaslik)."""
    with _elon_cache_lock:
        eski = _ELON_CACHE['by_num'].get(str(elon['num']))
        if eski and eski.get('rasm_file_id') and not elon.get('rasm_file_id'):
            elon['rasm_file_id'] = eski['rasm_file_id']
        if eski:                                          # BUGUN251: sayt xabarida guruh / sotilgan yo'q — eskisidan
            for k in ('guruh', 'sotilgan'):
                if k not in elon and eski.get(k) not in (None, ''):
                    elon[k] = eski[k]
        _ELON_CACHE['by_num'][str(elon['num'])] = elon


async def elon_cache_loop():
    """Kuniga bir marta ehtiyot uchun qayta yuklash (sayt xabari yetib kelmagan bo'lsa)."""
    while True:
        await asyncio.sleep(ELON_CACHE_MAX_AGE)
        try:
            await blok(elon_cache_load)
        except Exception as e:
            logger.error(f'elon_cache_loop: {e}')



# ── BUGUN244 (2026-10-17): «🤖 AI yordamchi» — saytdagi AI yordamchi hisoboti, guruhning o'z mavzusiga ──
# Toshkent vaqti bilan 05, 10, 15, 20, 01 da: «🤖 So'nggi 5 soat (10:00–15:00): 7 savol · 4 mijoz · AI 6 · skript 1 · adminga 1 · …».
# Sonlarni sayt hisoblaydi (netlify/functions/yordamchi.js, GET ?hisobot=) — botga faqat sonlar keladi (ism, username, tgId, telefon YO'Q).
# NEGA qat'iy soatlar («ishga tushgandan 5 soat» emas): bot qayta ishga tushganda hisob soati surilmaydi, odam qachon kelishini biladi.
# Takrorsiz: har oynaning belgisi (2026-10-17T15) saytda saqlanadi — bot qayta ishga tushsa ham shu oyna ikkinchi marta yuborilmaydi.
# Bot uxlab, bir necha oynani o'tkazib yuborsa — uyg'onganda faqat OXIRGI oyna bir marta yuboriladi.
# Env (Render): YORDAMCHI_JURNAL_KALIT — Netlify'dagi bilan bir xil · YORDAMCHI_URL (ixtiyoriy). Kalit yoki mavzu yo'q — jim (bitta log).
YORDAMCHI_URL = os.environ.get('YORDAMCHI_URL', '') or SAYT_URL.rstrip('/') + '/.netlify/functions/yordamchi'
YORDAMCHI_JURNAL_KALIT = os.environ.get('YORDAMCHI_JURNAL_KALIT', '')
AI_HISOBOT_SOATLAR = (1, 5, 10, 15, 20)   # Toshkent
AI_HISOBOT_QAYTA = 600                    # sayt / Telegram javob bermasa — 10 daqiqadan keyin yana
AI_HISOBOT_KUTISH_MAX = 1800              # uzoq uxlamaydi: soat surilsa ham 30 daqiqada o'zini tutadi
_AI_HISOBOT = {'oxirgi': None, 'matn': None, 'matn_belgi': None, 'urinish': 0, 'jim': None}


def ai_hisobot_oyna(hozir):
    """hozir (epoch s) → (oyna oxiri, oyna boshi, belgi, keyingi oyna oxiri) — epoch s; belgi Toshkent soati bilan: 2026-10-17T15."""
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=5))
    kun = datetime.fromtimestamp(hozir, tz).replace(hour=0, minute=0, second=0, microsecond=0)
    nuqtalar = [(kun + timedelta(days=d, hours=h)) for d in (-1, 0, 1) for h in AI_HISOBOT_SOATLAR]
    i = max(n for n, t in enumerate(nuqtalar) if t.timestamp() <= hozir)
    oxiri, boshi, keyingi = nuqtalar[i], nuqtalar[i - 1], nuqtalar[i + 1]
    return int(oxiri.timestamp()), int(boshi.timestamp()), oxiri.strftime('%Y-%m-%dT%H'), int(keyingi.timestamp())


def ai_hisobot_ol(oxiri, boshi, belgi):
    """Saytdan hisobot: dict · {'rad': True} (403 — kalit mos emas) · None (tarmoq / sayt xatosi — keyinroq yana).
    Logda kalit YO'Q (u faqat sarlavhada; xato matni o'rniga — xato turi)."""
    try:
        r = req.get(YORDAMCHI_URL, params={'hisobot': (oxiri - boshi) // 3600, 'gacha': oxiri * 1000, 'belgi': belgi},
                    headers={'x-jurnal-kalit': YORDAMCHI_JURNAL_KALIT}, timeout=20)
    except Exception as e:
        logger.error(f'ai_hisobot: sayt javob bermadi ({type(e).__name__})')
        return None
    if r.status_code == 403:
        logger.error("ai_hisobot: sayt 403 — Render va Netlify'dagi YORDAMCHI_JURNAL_KALIT bir xil emas")
        return {'rad': True}
    try:
        d = r.json() if r.status_code == 200 else None
    except Exception:
        d = None
    if not isinstance(d, dict) or not d.get('ok'):
        logger.error(f"ai_hisobot: sayt javobi noto'g'ri (HTTP {r.status_code})")
        return None
    return d


def ai_hisobot_matn(d, oxiri, boshi):
    """Sayt sonlaridan bitta qator. 0 savol — «0 savol» (hisobot baribir keladi: bot ishlayotgani ko'rinsin)."""
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=5))
    vaqt = f"{datetime.fromtimestamp(boshi, tz):%H:%M}–{datetime.fromtimestamp(oxiri, tz):%H:%M}"

    def son(k):
        try:
            return int(d.get(k) or 0)
        except (TypeError, ValueError):
            return 0
    qism = [f"{son('savol')} savol"]
    if son('savol'):
        qism += [f"{son('mijoz')} mijoz", f"AI {son('ai')}", f"skript {son('skript')}", f"adminga {son('adminga')}"]
        top = [html_escape(str(t.get('matn', ''))[:30]) for t in (d.get('top') or [])[:5] if isinstance(t, dict) and t.get('matn')]
        if top:
            qism.append("ko'p so'ralgan: " + ', '.join(top))
    matn = f"🤖 So'nggi {(oxiri - boshi) // 3600} soat ({vaqt}): " + ' · '.join(qism)
    sabab = d.get('xatoSabab')
    if son('xato') and isinstance(sabab, dict) and sabab:
        matn += f"\n⚠️ AI ishlamadi — {son('xato')} (" + ', '.join(
            f"{html_escape(str(k)[:20])} {int(v) if str(v).isdigit() else 0}" for k, v in list(sabab.items())[:5]) + ')'
    return matn


def ai_hisobot_qadam(hozir):
    """Bitta qadam (ai_hisobot_loop chaqiradi, sinov ham): kerak bo'lsa hisobotni oladi va mavzuga yuboradi.
    Qaytaradi — keyingi qadamgacha necha soniya kutish."""
    s = _AI_HISOBOT
    oxiri, boshi, belgi, keyingi = ai_hisobot_oyna(hozir)
    kut = max(1, min(keyingi - hozir, AI_HISOBOT_KUTISH_MAX))
    if s['oxirgi'] == belgi:
        return kut
    if not (GURUH.get('id') and GURUH.get('ai')) or not YORDAMCHI_JURNAL_KALIT:
        if s['jim'] != belgi:   # har oynada bitta qator; oyna «bajarildi» deb belgilanmaydi — /guruh dan keyin shu oyna ham keladi
            s['jim'] = belgi
            logger.info('ai_hisobot: jim — ' + ("«🤖 AI yordamchi» mavzusi yo'q (/guruh)" if not GURUH.get('ai')
                                                else "YORDAMCHI_JURNAL_KALIT yo'q"))
        return kut
    if s['matn_belgi'] != belgi:
        d = ai_hisobot_ol(oxiri, boshi, belgi)
        if d is None:
            return min(kut, AI_HISOBOT_QAYTA)
        if d.get('rad') or d.get('takror'):   # kalit mos emas (log yozildi) · shu oyna allaqachon yuborilgan
            s['oxirgi'] = belgi
            return kut
        s['matn'], s['matn_belgi'], s['urinish'] = ai_hisobot_matn(d, oxiri, boshi), belgi, 0
    if send_msg(Joy(GURUH['id'], GURUH['ai']), s['matn']):
        s['oxirgi'], s['matn'], s['matn_belgi'] = belgi, None, None
        return kut
    s['urinish'] += 1
    if s['urinish'] >= 3:
        logger.error(f'ai_hisobot: Telegram 3 marta qabul qilmadi — {belgi} oynasi tashlab ketildi')
        s['oxirgi'], s['matn'], s['matn_belgi'] = belgi, None, None
        return kut
    return min(kut, AI_HISOBOT_QAYTA)


async def ai_hisobot_loop():
    """Fonda: ai_hisobot_qadam — alohida ipda (sayt / Telegram so'rovi webhook'ni to'xtatmaydi). Xato — bot yiqilmaydi."""
    await asyncio.sleep(60)   # ishga tushish yuki (webhook, e'lon xotirasi) o'tsin
    while True:
        try:
            kut = await blok(ai_hisobot_qadam, time.time())
        except Exception as e:
            logger.error(f'ai_hisobot: {type(e).__name__}')
            kut = AI_HISOBOT_QAYTA
        await asyncio.sleep(kut)


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


def get_haftalik():
    """BUGUN139: haftalik hisobot matni — Apps Script quradi (AppScript.gs: getHaftalikMatn); trigger ham aynan shuni yuboradi."""
    if not SHEET_URL:
        return None
    if not API_KEY:
        return {'ok': False, 'msg': 'key_yoq'}
    try:
        r = req.get(f"{SHEET_URL}?action=haftalik&key={urllib.parse.quote(API_KEY)}", timeout=40)
        return r.json()
    except Exception as e:
        logger.error(f'get_haftalik: {e}')
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
    if len(parts) > 1 and parts[1].lower() in ('hafta', 'haftalik'):   # BUGUN139: /stat hafta — dushanbadagi hisobotning o'zi
        h = await blok(get_haftalik)
        if h and h.get('ok') and h.get('matn'):
            await blok(send_msg, chat_id, html_escape(h['matn']))
        else:
            await blok(send_msg, chat_id, "❌ Haftalik hisobotni olib bo'lmadi (Apps Script yangilanganmi? API_KEY bir xilmi?).")
        return
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
        'part': ('Barcha ehtiyot qismlar', 'Все запчасти'),   # S100: «Zapchastlar» → «Ehtiyot qismlar»
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
    """Model nomi — Sheets'da qanday yozilgan bo'lsa SHUNDAY (BUGUN17 §1, A24=c; sayt modelDisplayName).
    NEGA: brend o'zi qo'shilganda «Аккумулятор для Google Pixel 8a» kabi nomlar buzilardi —
    endi to'liq nom qo'lda yoziladi. Brend (model_brand) faqat filtr/qidiruv uchun."""
    if not model:
        return ''
    return str((model.get('nameUz') if lang == 'uz' else (model.get('nameRu') or model.get('nameUz'))) or model.get('name') or '').strip()


def elon_nomi(elon, model, lang='uz'):
    """G12 (2026-09-15): e'lonning O'Z nomi (Elonlar nameUz/nameRu) bo'lsa shu — admin
    «Pixel 8 (GrapheneOS)» deb o'zgartira oladi; bo'sh bo'lsa model nomi. Brend QO'SHILMAYDI
    (BUGUN17 §1) — nom qanday yozilsa shunday. Sayt: elonNomi."""
    e = elon or {}
    own = str((e.get('nameUz') if lang == 'uz' else (e.get('nameRu') or e.get('nameUz'))) or e.get('name') or '').strip()
    return own or model_display_name(model, lang)


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
    price = str(item.get('price', '')).replace('.0', '')
    old = str(item.get('oldPrice', '')).replace('.0', '')
    cond = item.get('condition', 'new')
    cycle = str(item.get('cycle', '') or '').replace('.0', '')
    color_uz = item.get('color', '')
    spec_id = item.get('specId', '')

    model = models_by_id.get(spec_id, {})
    spec_uz = model.get('specUz', '') or ''
    spec_ru = model.get('specRu', '') or ''
    # BUGUN17 §1: nom yozilganidek — brend oldiga QO'SHILMAYDI (e'lonning o'z nomi, bo'sh bo'lsa model nomi)
    name_uz = elon_nomi(item, model, 'uz')
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

    # ── Sarlavha: G logo + BOLD nom (xotira, xususiyat) + rang ──
    # BUGUN260-7: qavs ichi bo'sh bo'lsa — qavs yo'q (ilgari «Nom ()» chiqardi)
    add_prem('google'); add(" ")
    qavs = elon_qavs(item)
    title = name_uz + (f" ({qavs})" if qavs else '')
    add_fmt(title, 'bold')
    if color_clean:
        add(f" {color_clean}")
    add("\n")
    add(f"#{elon_turi(item, models_by_id)} #{num}\n")   # 3184.5: tur bo'yicha (ilgari hammasi #phone)
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

    # ── Kontaktlar (ALOQA, 2026-10-07: raqam, admin; kanal — e'lonning yo'nalishidan) ──
    add(f"📩 @{ADMIN_USERNAME}\n")
    add(f"📞 {ALOQA_TEL}\n\n")
    add_prem('k'); add(f" @{YON_KANAL[post_yonalish(item, models_by_id)][1]} (Kanal/Канал)\n")
    add_prem('k'); add(f" @{BOT_USERNAME}")

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

def _images_xom(elon):
    """E'lon rasmlari xom holda (belgi qismi bilan) — Sheets'da JSON matn, xotirada ro'yxat bo'lishi mumkin."""
    images = (elon or {}).get('images')
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []
    if not isinstance(images, list):
        images = []
    return [str(u).strip() for u in images if str(u or '').strip()]


_BELGI_RE = re.compile(r'#nb=([^#]*)$')


def belgi_ajrat(url):
    """«…jpg#nb=12.5,50» → ('…jpg', (0.125, 0.5)); «#nb=0» → ('…jpg', 'yoq'); belgisiz / buzuq → ('…jpg', None).
    Joy — logo MARKAZI, rasm eni / bo'yiga nisbatan 0–1 (sayt 09-admin.js belgiQosh bilan bir xil)."""
    url = str(url or '').strip()
    m = _BELGI_RE.search(url)
    if not m:
        return url, None
    toza, v = url[:m.start()], m.group(1).strip()
    if v == '0':
        return toza, 'yoq'
    try:
        x, y = (float(s) for s in v.split(','))
    except Exception:
        return toza, None
    if not (0 <= x <= 100 and 0 <= y <= 100):
        return toza, None
    return toza, (x / 100, y / 100)


def images_of(elon):
    """E'lon rasmlari — TOZA manzillar (suv belgisi joyi kesilgan). Hamma joy shuni ishlatadi."""
    return [belgi_ajrat(u)[0] for u in _images_xom(elon)]


def rasm_joylari(elon):
    """[(toza manzil, joy)] — joy: None (sukut, chap o'rta) / 'yoq' (belgisiz) / (x, y)."""
    return [belgi_ajrat(u) for u in _images_xom(elon)]


def belgili(url, joy=None, tr=SUV_BELGI_TR):
    """Rasm manzili + suv belgisi (ImageKit layer). ImageKit bo'lmagan, allaqachon `tr=` li yoki belgisiz rasm — faqat
    o'lcham (tr). Layer resize'dan KEYIN zanjir (`:`) bilan — vergul bilan qo'shilsa ImageKit 400 qaytaradi (sinaldi);
    `t-false` — logo chetlari kesilmasin (sukutda ImageKit bir xil rangli chetni kesib, doirani «zoom» qilib yuboradi)."""
    url = belgi_ajrat(url)[0]
    if not SUV_BELGI or joy == 'yoq' or 'ik.imagekit.io' not in url or 'tr=' in url:
        return _ik_olcham(url, tr) if tr else url
    x, y = joy if isinstance(joy, tuple) else (SUV_BELGI_CHET + SUV_BELGI_OLCHAM / 2, 0.5)
    layer = (f"l-image,i-{SUV_BELGI_RASM.replace('/', '@@')},t-false,w-bw_mul_{SUV_BELGI_OLCHAM:g},r-max,"
             f"o-{SUV_BELGI_SHAFFOF},lxc-bw_mul_{x:.3f},lyc-bh_mul_{y:.3f},l-end")
    return url + ('&' if '?' in url else '?') + 'tr=' + (f'{tr}:' if tr else '') + layer


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


def rich_media(rasmlar, kollaj=False, rasm_src=None):
    """Post tepasidagi rasm bloki. Sukut — slideshow (10 tagacha).
    kollaj=True (B28, BUGUN31) — admin «🖼 Kollajga o'tkazish» bosganda: birinchi 4 rasm kollaj,
    ko'p bo'lsa izoh «📷 N ta rasm — hammasi saytda» (v2 dagi kollaj ko'rinishi)."""
    src = lambda u: html_escape((rasm_src or {}).get(u, u))
    if not rasmlar:
        return ''
    if kollaj:
        imgs = ''.join(f'<img src="{src(u)}"/>' for u in rasmlar[:4])
        izoh = f'<figcaption>📷 {len(rasmlar)} ta rasm — hammasi saytda</figcaption>' if len(rasmlar) > 4 else ''
        return f'<tg-collage>{imgs}{izoh}</tg-collage>'
    imgs = ''.join(f'<img src="{src(u)}"/>' for u in rasmlar[:10])
    return f'<tg-slideshow>{imgs}</tg-slideshow>'


def keyingi_belgi(url):
    """Tayyor ImageKit manzilga (`…?tr=…`) «suring» belgisi layer'larini qo'shadi. ImageKit bo'lmagan / `tr=` siz — o'zgarmaydi."""
    if not KEYINGI_BELGI or 'ik.imagekit.io' not in url or '?tr=' not in url and '&tr=' not in url:
        return url
    return url + ':' + KEYINGI_BELGI_LAYER


def belgi_src(elon):
    """{toza rasm manzili: belgili manzil} — kanal postining rich rasmlari uchun (rich_media rasm_src).
    BUGUN148: 2+ rasm bo'lsa 1-rasmga «suring» belgisi ham (keyingi_belgi)."""
    joylar = rasm_joylari(elon)
    src = {t: belgili(t, j) for t, j in joylar}
    if len(joylar) >= 2:
        src[joylar[0][0]] = keyingi_belgi(src[joylar[0][0]])
    return src


# 3189 (A60, Owner 2026-10-25): post OXIRI — e'lon va rang guruhi postida bir xil. Matn oxirida 📞 admin (telefon + @),
#   kanallar; tugmalar — «🛒 Sotib olish» (shu e'lon Mini App'da) va «🛍 Boshqa e'lonlar» (sayt bosh sahifasi). «Admin» /
#   «Kanal» tugmalari olib tashlandi. Kanallar qayerda — POST_SHABLON: 1 — Yangiliklar tugmada, yo'nalish kanali matnda ·
#   2 — ikkalasi tugmada · 3 — ikkalasi matnda. 3191 (Owner 2026-10-26, xabar 1247 ni o'zi tahrirlab): 2 tanlandi.
POST_SHABLON = 2
# 3191: tugmalar joylashuvi — 1: «🛒 Sotib olish» / «🛍 Boshqa e'lonlar» / kanallar (har biri o'z qatorida, Owner namunasi) ·
#   2: 1-qatorda chapda «Boshqa e'lonlar», o'ngda «Sotib olish», 2-qatorda kanallar. Telegram bir qatordagi tugmalarni teng
#   kenglikda chizadi (RichMessageButton'da kenglik yo'q) — 2 da ikkalasi teng. Ranglar (style) Owner namunasidan: Sotib olish —
#   primary (ko'k), Boshqa e'lonlar — success (yashil), kanallar — danger (to'q sariq namunaga eng yaqini; Bot API'da boshqasi
#   yo'q: danger / success / primary, link — faqat callback).
POST_TUGMA = 1
# 3191.2 (Owner 2026-10-26): narx qatori — 1: butun qator qalin «💰 Narxi / Цена: 390$» (ilgari faqat raqam qalin edi) ·
#   2: <h4> sarlavha (3191.3, Owner 2026-10-26 01:38: «H3 emas h4» — biroz kattaroq; shrifti serifga o'xshab ketishi mumkin —
#   sinov uchun, Owner ko'rib tanlaydi).
#   3191.4 (Owner 2026-10-26 02:27, №311 ni o'zi tahrirlab): heading yo'q, oddiy matn, narx tepasida va pastida divider (<hr/>) —
#   3: narx bullet bilan («• 💰 Narxi / Цена: 390$») · 4: bullet'siz oddiy qator.
#   3191.5 (Owner 2026-10-26 03:16: «narxni bullet'ni olib tashlab center qil»): 5 (C) — narx <aside> ichida, divider'lar orasida.
#   Rich formatda markazlash faqat <aside> (pull quote — «centered text») va jadval katagida (align); <p> da align yo'q.
#   <hr/> (RichBlockDivider) maydonsiz — enini Telegram o'zi chizadi (o'rtada qisqa chiziq), uzaytirib bo'lmaydi.
#   3191.6 (Boss qarori, Owner 03:16 so'zi bo'yicha): sukut — 5 (C); 1 / 2 / 3 / 4 — muqobil sifatida qoladi.
#   3200 (Owner 2026-10-26 22:24: «pull quote va dividerlarsiz, faqat narxni bullet qilamiz»): 6 — narx bullet bilan
#   («• 💰 Narxi / Цена: 390$»), <hr/> ham, <aside> ham yo'q; qoldiq — tagida oddiy paragraf. Sukut — 6; 1–5 muqobil.
POST_NARX = 6
YON_EMOJI = {'mobile': '📱', 'pc': '💻', 'camera': '📷'}


def post_oxiri(sahifa, yonalish, shablon=None, tugma=None):
    """(aloqa <p>…</p>, tugma qatorlari) — sahifa: startapp qiymati («elon_307»), yonalish — YON_KANAL kaliti.
    3191: aloqa — 📞 raqam va 📩 admin YOPISHIQ (bitta paragraf, <br/>), alohida qatorda."""
    shablon = shablon or POST_SHABLON
    tugma = tugma or POST_TUGMA
    kanal_nomi, kanal = YON_KANAL[yonalish if yonalish in YON_KANAL else 'mobile']
    yon = (f"{YON_EMOJI.get(yonalish, '📱')} {kanal_nomi.replace(' · ', ' ')}", kanal)   # «📱 Nuqta tech Mobile»
    yangi = (f'💡 {BREND} • Yangiliklar', TECH_SUKUT.lstrip('@'))
    matnda, tugmada = {1: ([yon], [yangi]), 2: ([], [yon, yangi])}.get(shablon, ([yon, yangi], []))
    tel_href = re.sub(r'[^\d+]', '', ALOQA_TEL)
    aloqa = (f'<p>📞 <a href="tel:{tel_href}">{html_escape(ALOQA_TEL)}</a><br/>📩 @{ADMIN_USERNAME}'
             + ''.join(f'<br/><a href="https://t.me/{u}">{html_escape(n)}</a>' for n, u in matnda) + '</p>')
    sotib = f'<tg-button type="url" style="primary" url="https://t.me/{BOT_USERNAME}?startapp={sahifa}">🛒 Sotib olish</tg-button>'
    boshqa = f'<tg-button type="url" style="success" url="https://t.me/{BOT_USERNAME}?startapp=home">🛍 Boshqa e\'lonlar</tg-button>'
    qator = lambda *t: '<tg-button-row>' + ''.join(t) + '</tg-button-row>'
    tugmalar = (qator(boshqa, sotib) if tugma == 2 else qator(sotib) + qator(boshqa)) + (
        qator(*(f'<tg-button type="url" style="danger" url="https://t.me/{u}">{html_escape(n)}</tg-button>' for n, u in tugmada))
        if tugmada else '')
    return aloqa, tugmalar


def build_rich_html(elon, models_by_id, premium=True, rasm_src=None, kollaj=False, belgi=False, yonalish=None, shablon=None,
                    tugma=None, narx_k=None):
    """E'lon uchun Rich HTML (slideshow). premium=False — <tg-emoji>siz.
    v6 (2026-09-14): collage bekor (foydalanuvchi: «collage atmen»), faqat slideshow.
    v9 (BUGUN31, B28): kollaj=True — admin tugma bilan kollajga o'tkazgan post (sukut — slideshow).
    rasm_src — {rasm URL: src} (BUGUN16 inline: `tg://photo?id=…` — inline'da URL ishlamaydi); qolgani o'zgarmaydi.
    belgi=True (A26) — kanal posti: rasmlarda suv belgisi (rasm_src berilmagan bo'lsa).
    yonalish (2026-10-07, ALOQA) — postdagi kanal shu yo'nalishniki; None — e'lonning asosiy yo'nalishi (post_yonalish)."""
    if belgi and rasm_src is None:
        rasm_src = belgi_src(elon)
    num = int(float(elon.get('num', 0) or 0))
    model = models_by_id.get(str(elon.get('specId', '') or ''), {}) if isinstance(models_by_id, dict) else {}
    name = html_escape(elon_nomi(elon, model, 'uz'))   # G12: e'lonning o'z nomi (bo'lmasa model), yozilganidek (BUGUN17)
    mos_txt = html_escape(mos_line(model, models_by_id, 'uz'))
    izoh_txt = html_escape(izoh_matni(elon, 'uz'))   # G12 K2
    storage = html_escape(elon_qavs(elon))   # BUGUN260-7: xotira + xususiyat («MagSafe, Stand»)
    color = html_escape(clean_color(elon.get('color') or ''))
    price = str(elon.get('price', '') or '').replace('.0', '')
    old = str(elon.get('oldPrice', '') or '').replace('.0', '')
    cycle = str(elon.get('cycle', '') or '').replace('.0', '')
    cond_uz, cond_ru, cond_emoji = holati_matni(elon.get('condition', 'used') or 'used', cycle)
    e = (lambda k: _rich_emoji(k)) if premium else (lambda k: PREMIUM[k][0])
    # 3184.5: sarlavha emojisi va tegi — e'lon turidan (ilgari hammasi 📱 #phone: g'ilof ham, zaryadlovchi ham).
    #     Telefon (premium) — G logo, avvalgidek
    tur = elon_turi(elon, models_by_id)
    tur_emoji = e("google") if tur == 'phone' else TUR_NOMI.get(tur, TUR_NOMI['phone'])[0]

    # v6: slideshow — hammasi. v8 (2026-09-18, foydalanuvchi): «N ta rasm — suring» izohi OLIB TASHLANDI
    media = rich_media(images_of(elon), kollaj, rasm_src)

    title = name + (f' ({storage})' if storage else '') + (f' {color}' if color else '')
    if elon_status(elon) == 'sold':
        # B13 soni: ko'p donali tovar tugasa «QOLMADI» (e'lon o'chmaydi — yana kelsa post tahrirlanadi)
        narx = (f'<s>{html_escape(price or old)}$</s> ' if (price or old) else '') + ('❗️QOLMADI❗️' if kop_donali(elon) else '❗️SOTILDI❗️')
    elif old and old != price:
        narx = f'<s>{html_escape(old)}$</s> {html_escape(price)}$'
    else:
        narx = f'{html_escape(price)}$'
    # 3191.2: butun narx qatori qalin (POST_NARX 1) yoki <h4> (2); qoldiq («📦 N dona bor») — oddiy, alohida
    # 3191.4: 3 / 4 — oddiy matn, ikki <hr/> orasida; 3 — <ul> bullet, 4 — <p>. Qoldiq — narx tagida, chiziqlar ichida
    # 3191.5: 5 — markazda (<aside>), qoldiq o'sha blokda <br/> bilan
    # 3200: 6 — faqat bullet (<ul><li>), chiziq va markaz yo'q
    narx = f'{e("money")} Narxi / Цена: {narx}'
    soni = soni_qatori(elon)
    narx_k = narx_k or POST_NARX
    if narx_k == 6:
        narx_blok = f'<ul><li>{narx}</li></ul>' + (f'<p>{soni}</p>' if soni else '')   # 3200: chiziqsiz, quote'siz
    elif narx_k == 5:
        narx_blok = f'<hr/><aside>{narx}' + (f'<br/>{soni}' if soni else '') + '</aside><hr/>'
    elif narx_k in (3, 4):
        narx_blok = '<hr/>' + (f'<ul><li>{narx}</li></ul>' if narx_k == 3 else f'<p>{narx}</p>') + (
            f'<p>{soni}</p>' if soni else '') + '<hr/>'
    elif narx_k == 2:
        narx_blok = f'<h4>{narx}</h4>' + (f'<p>{soni}</p>' if soni else '')
    else:
        narx_blok = f'<p><b>{narx}</b>' + (f'<br/>{soni}' if soni else '') + '</p>'   # B13: qoldiq

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
    # ALOQA (2026-10-07): kanal — e'lon yuborilgan yo'nalishniki (Mobile → «Nuqta tech · Mobile» @nuqta_tech_mobile, …)
    aloqa, tugmalar = post_oxiri(f'elon_{num}', yonalish if yonalish in YON_KANAL else post_yonalish(elon, models_by_id), shablon, tugma)
    # v5: bloklar orasida BO'SH JOY (Telegram rich'da paragraflar orasiga margin qo'ymaydi —
    #     bo'sh paragraf \u00a0 bilan). Holati + narx BITTA blok. Foydalanuvchi ko'rsatdi:
    #     xarakteristika / bo'sh / holati·holati·narx / bo'sh / tugma
    # v6: spec TEPASIDA ham bo'sh joy (details'ga Telegram faqat pastdan chiziq chizadi —
    #     sarlavhaga yopishib ketardi); holati va narx ALOHIDA paragraflar (bo'sh qatorsiz,
    #     lekin <br/> bilan yopishgan emas)
    # v7: bo'sh joy rasm izohi («suring») bilan sarlavha ORASIDA (yopishib qolgan edi);
    #     spec tepasidagi bo'sh joy olib tashlandi («juda katta bo'lib ketdi»)
    # v9 (BUGUN31, B21): rasm TAGIDAGI bo'sh joy olib tashlandi \u2014 \u00absuring\u00bb izohi (v8) ketgach u ortiqcha qolgan edi;
    #     foydalanuvchi: \u00abrasm tagida biroz bo'shliq bor \u2014 yo'qotish kerak shuni\u00bb
    # 3191.1 (Owner, namuna 2026-10-26): bo'sh paragraf (BOSH) yo'q — bloklar orasida faqat Telegram'ning o'z paragraf
    #     oralig'i («yarim qatorcha»); BOSH u bilan qo'shilib 2 baravar katta bo'shliq berardi
    return (
        media
        + f'<p><b>{tur_emoji} {title}</b><br/>#{tur} #{num}' + (f'<br/>🔗 {mos_txt}' if mos_txt else '') + (f'<br/>📝 {izoh_txt}' if izoh_txt else '') + '</p>'
        + spec
        + f'<p>{html_escape(cond_emoji)} Holati: <b>{html_escape(cond_uz)}</b><br/>'
          f'{html_escape(cond_emoji)} Состояние: <b>{html_escape(cond_ru)}</b></p>'
        + narx_blok
        + aloqa   # ALOQA (2026-10-07): raqam (bosilsa qo'ng'iroq), admin, kanal(lar) — 3189: post_oxiri
        + tugmalar   # 3189 (A60): «🛒 Sotib olish» (shu e'lon) + «🛍 Boshqa e'lonlar»; v3 dagi «Saytni ochish» va Admin / Kanal tugmalari o'rnida
    )


def send_rich(chat_id, html, disable_notification=False, media=None, javob=None):
    """sendRichMessage. (message_id, '') yoki (None, xato matni).
    media — rich_message.media (BUGUN148: rasm file_id bilan, `tg://photo?id=rN`); javob (dict) — Telegram natijasi shunga."""
    rich = {'html': html}
    if media:
        rich['media'] = media
    try:
        r = req.post(f'{TG_API}/sendRichMessage', json={
            'chat_id': chat_id,
            'rich_message': rich,
            'disable_notification': disable_notification,
        }, timeout=30).json()
    except Exception as ex:
        return None, f'tarmoq: {ex}'
    if not r.get('ok'):
        return None, str(r.get('description') or r)
    if javob is not None and isinstance(r.get('result'), dict):
        javob.update(r['result'])
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
# MS3.1 (BUGUN56, 2026-10-08): yo'nalish → o'z kanali. «mobile, pc» e'lon IKKALA kanalga bir xil post bo'ladi.
# env POST_KANALLAR = "mobile=@nuqta_tech_mobile pc=@nuqta_tech_PC camera=@nuqta_tech_camera" (yoki -100… raqam).
# Env yo'q — hamma yo'nalish POST_CHANNEL'ga, bitta post (avvalgidek). Yozilmagan yo'nalish — POST_CHANNEL.
# channel_message_id: «123» — eski (POST_CHANNEL'dagi bitta post) yoki «mobile:123 pc:45» — har kanaldagi post.
# To'plam va katalog postlari — avvalgidek faqat POST_CHANNEL.
POST_KANALLAR = {k.strip().lower(): v.strip() for k, _, v in
                 (x.partition('=') for x in re.split(r'[\s,;]+', os.environ.get('POST_KANALLAR', '')) if '=' in x)
                 if k.strip() and v.strip()}


def post_kanal(yon):
    """Yo'nalish posti qaysi kanalga (POST_KANALLAR → POST_CHANNEL)."""
    return POST_KANALLAR.get(str(yon or '').strip().lower()) or POST_CHANNEL
AVTO_POST_TURLAR = ('phone', 'camera')
TOPLAM_TURLAR = ('accessory', 'case', 'part')
TUR_NOMI = {'phone': ('📱', 'Smartfonlar', 'Смартфоны'), 'camera': ('📷', 'Kameralar', 'Камеры'),
            'accessory': ('🔌', 'Aksessuarlar', 'Аксессуары'), 'case': ('🛡', "G'iloflar", 'Чехлы'),
            'part': ('🛠', 'Ehtiyot qismlar', 'Запчасти')}   # S100


def elon_turi(elon, models_by_id):
    """E'lon bo'limi (phone/camera/accessory/case/part) — model → lineyka → tur (sayt listingType bilan bir xil)."""
    model = models_by_id.get(str((elon or {}).get('specId', '') or ''), {}) if isinstance(models_by_id, dict) else {}
    sk = str((model or {}).get('series', '') or '')
    ser = next((s for s in (_ELON_CACHE.get('series') or []) if str(s.get('key', '')) == sk), None)
    return ser_type(ser) if ser else 'phone'


def elon_yonalishlar(elon, models_by_id):
    """E'lon yo'nalishlari (mobile / pc / camera) — e'lonning o'z `yonalish`i → model `yonalish` → seriya `yonalish` → mobile
    (sayt `modelYonalishlar` bilan bir xil; ustunlar jadvalga «🚀 Chiqarish kuni» 6-qadamda qo'shiladi, unga qadar — mobile)."""
    # BUGUN60 Q5: e'lonning O'Z yo'nalishi (jadvalda `yonalish` ustuni — guruh mavzusidan yaratilgan yoki tahrirda tanlangan) — birinchi
    e_yon = str((elon or {}).get('yonalish', '') or '').strip().lower()
    if e_yon in ('mobile', 'pc', 'camera'):
        return [e_yon]
    model = models_by_id.get(str((elon or {}).get('specId', '') or ''), {}) if isinstance(models_by_id, dict) else {}
    own = [y.lower() for y in parse_mos((model or {}).get('yonalish'))]
    if own:
        return own
    sk = str((model or {}).get('series', '') or '')
    ser = next((s for s in (_ELON_CACHE.get('series') or []) if str(s.get('key', '')) == sk), None)
    return [y.lower() for y in parse_mos((ser or {}).get('yonalish'))] or ['mobile']


# ALOQA (2026-10-07): kanal posti id → saytda e'lon yuborilgan yo'nalish (tahrirda ham o'sha kanal turishi uchun).
# Xotirada: bot qayta ishga tushsa — e'lonning asosiy (birinchi) yo'nalishi; farq faqat ko'p yo'nalishli tovarda (zaryad: mobile, pc).
_POST_YON = {}


def post_yonalish(elon, models_by_id, tanlangan=None, mid=None):
    """Postdagi kanal qaysi yo'nalishniki: saytda tanlangani (e'lon o'sha yo'nalishda bo'lsa) → shu post avval qaysi
    yo'nalishdan yuborilgan bo'lsa → e'lonning asosiy yo'nalishi → mobile."""
    bor = [y for y in elon_yonalishlar(elon, models_by_id) if y in YON_KANAL] or ['mobile']
    for y in (str(tanlangan or '').strip().lower(), _POST_YON.get(int(mid)) if mid else None):
        if y in bor:
            return y
    return bor[0]


def kanal_msg_id(elon):
    """channel_message_id (Sheets'da matn/son) → int yoki None. «mobile:123 pc:45» — birinchisi (asosiy post)."""
    p = kanal_postlar(elon)
    return p[0][2] if p else None


def kanal_postlar(elon):
    """channel_message_id → [(yo'nalish yoki None, kanal, mid)]. «123» → [(None, POST_CHANNEL, 123)];
    «mobile:123 pc:45» → [('mobile', kanal, 123), ('pc', kanal, 45)] (MS3.1)."""
    v = str((elon or {}).get('channel_message_id', '') or '').strip()
    if not v:
        return []
    if ':' not in v:
        try:
            return [(None, POST_CHANNEL, int(float(v)))]
        except Exception:
            return []
    out = []
    for qism in re.split(r'[\s,;]+', v):
        y, _, m = qism.partition(':')
        if y.strip() and re.fullmatch(r'\d{1,12}', m.strip()):
            out.append((y.strip().lower(), post_kanal(y), int(m)))
    return out


def kanal_id_matn(postlar):
    """[(yo'nalish, mid)] → Sheets qiymati: bitta post POST_CHANNEL'da — 123 (eski ko'rinish), aks holda «mobile:123 pc:45»."""
    if len(postlar) == 1 and post_kanal(postlar[0][0]) == POST_CHANNEL:
        return int(postlar[0][1])
    return ' '.join(f'{y}:{int(m)}' for y, m in postlar)


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
        r = req.get(f'{SHEET_URL}?action=update&key={urllib.parse.quote(API_KEY)}&data={urllib.parse.quote(json.dumps(payload))}', timeout=20)
        text = r.text.strip()
        d = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
        return bool(d.get('ok'))
    except Exception as e:
        logger.error(f'_sheets_update: {e}')
        return False


def kanal_id_yoz(num, mid):
    """Post id'sini Sheets'ga (channel_message_id) va xotiraga yozadi. mid=None — tozalash.
    mid — son yoki «mobile:123 pc:45» matni (MS3.1)."""
    qiymat = '' if not mid else (mid if isinstance(mid, str) and ':' in mid else int(mid))
    ok = _sheets_update({'num': int(num), 'channel_message_id': qiymat})
    with _elon_cache_lock:
        e = _ELON_CACHE['by_num'].get(str(num))
        if e is not None:
            e['channel_message_id'] = qiymat
    if not ok:
        logger.error(f'kanal_id_yoz: №{num} id {mid} Sheets ga yozilmadi')
    gid = guruh_idsi(e)
    if gid:
        guruh_yangila_keyin(gid)   # BUGUN251: rang posti paydo bo'ldi / o'chdi — guruh postidagi havola ham
    return ok


def edit_rich(chat_id, message_id, html, media=None, javob=None):
    """editMessageText + rich_message. (True, '') / (False, xato). «not modified» — ok. media / javob — send_rich kabi."""
    rich = {'html': html}
    if media:
        rich['media'] = media
    try:
        r = req.post(f'{TG_API}/editMessageText', json={
            'chat_id': chat_id, 'message_id': int(message_id), 'rich_message': rich,
        }, timeout=30).json()
    except Exception as ex:
        return False, f'tarmoq: {ex}'
    if r.get('ok'):
        if javob is not None and isinstance(r.get('result'), dict):
            javob.update(r['result'])
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
        return f'📩 <b>Ответ {BREND}</b>' + (f'\nНа ваш запрос: «{so}»' if so else '')
    return f'📩 <b>{BREND} javobi</b>' + (f"\nSiz so'ragan: «{so}»" if so else '')


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


def kanal_rich(elon, models, kollaj=False, yonalish=None):
    """Kanal posti (html, media, manbalar). BUGUN148: hamma rasmning file_id'si ma'lum — `tg://photo?id=rN` + media
    (Telegram rasmni qayta yuklamaydi); aks holda belgili manzillar (media=None)."""
    _fid_jadvaldan(elon)
    rasmlar = images_of(elon)[:10]
    manbalar = kanal_manbalari(elon)
    if kollaj:
        rasmlar, manbalar = rasmlar[:4], manbalar[:4]
    if rasmlar and len(set(rasmlar)) == len(rasmlar) and all(m in _URL_FID for m in manbalar):
        src = {u: f'tg://photo?id=r{i}' for i, u in enumerate(rasmlar)}
        media = [{'id': f'r{i}', 'media': {'type': 'photo', 'media': _URL_FID[m]}} for i, m in enumerate(manbalar)]
        return (build_rich_html(elon, models, premium=False, rasm_src=src, kollaj=kollaj, yonalish=yonalish),
                media, manbalar)
    return build_rich_html(elon, models, premium=False, kollaj=kollaj, belgi=True, yonalish=yonalish), None, manbalar


def rich_fidlar(natija):
    """Rich xabar natijasidagi rasmlar file_id'si (tartib bilan, eng katta o'lcham)."""
    fidlar = []

    def yur(x):
        if isinstance(x, dict):
            if x.get('type') == 'photo' and isinstance(x.get('photo'), list) and x['photo']:
                fidlar.append((x['photo'][-1] or {}).get('file_id'))
                return
            for v in x.values():
                yur(v)
        elif isinstance(x, list):
            for v in x:
                yur(v)
    yur((natija or {}).get('rich_message') or {})
    return fidlar


def kanal_rich_yubor(num, elon, models, chat, message_id=None, kollaj=False, yonalish=None):
    """Kanal posti — yangi (message_id=None: send_rich → (mid, xato)) yoki tahrir (edit_rich → (ok, xato)).
    file_id rad etilsa — manzillar bilan qayta. Manzillar bilan ketsa — natijadagi file_id'lar olinadi, jadvalga yoziladi."""
    html, media, manbalar = kanal_rich(elon, models, kollaj=kollaj, yonalish=yonalish)

    def yubor(h, md, jv):
        if message_id is None:
            return send_rich(chat, h, media=md, javob=jv)
        return edit_rich(chat, message_id, h, media=md, javob=jv)
    javob = {}
    natija = yubor(html, media, javob)
    if not natija[0] and media:
        logger.warning(f'kanal №{num} → {chat}: file_id rad etildi ({natija[1]}) — manzillar bilan')
        html = build_rich_html(elon, models, premium=False, kollaj=kollaj, belgi=True, yonalish=yonalish)
        media = None
        natija = yubor(html, None, javob)
    if natija[0] and not media and fid_olindi(num, manbalar, rich_fidlar(javob)):
        fid_saqla_fonda(num)
    return natija


def kanal_post(num, yonalish=None, olx=True):
    """E'lonni kanalga rich post qiladi, id yozadi. (mid, '') / (None, xato).
    yonalish — saytda e'lon yuborilgan bo'lim (postdagi kanal shuniki; ALOQA 2026-10-07).
    olx=False (3184.5, ommaviy / tomchi) — OLX albomi yuborilmaydi (90 ta albom OLX mavzusini to'ldirmasin)."""
    elon, models = elon_cache_get(num)
    if not elon:
        return None, "e'lon topilmadi"
    if elon_status(elon) in ('deleted', 'waited'):
        return None, "chala yoki o'chirilgan e'lon postlanmaydi"
    yon = post_yonalish(elon, models, tanlangan=yonalish)
    # MS3.1: e'lonning har yo'nalishi o'z kanaliga (saytda tanlangani birinchi — asosiy post). Kanal bir xil — bitta post
    yonlar = [yon] + [y for y in elon_yonalishlar(elon, models) if y in YON_KANAL and y != yon]
    postlar, xatolar, kanallar = [], [], set()
    for y in yonlar:
        chat = post_kanal(y)
        if chat in kanallar:
            continue
        kanallar.add(chat)
        m, x = kanal_rich_yubor(num, elon, models, chat, yonalish=y)
        if m:
            postlar.append((y, int(m)))
            _POST_YON[int(m)] = y
        else:
            xatolar.append(f'{chat}: {x}')
            logger.error(f'kanal_post №{num} → {chat}: {x}')
    if not postlar:
        return None, '; '.join(xatolar)
    mid = postlar[0][1]
    # 3184.5: aksessuar / g'ilof / qismning ALOHIDA posti — id doim «mobile:123» ko'rinishida (to'plam id'si — oddiy son):
    #     shunda toplam_postmi uni to'plam deb, tahrirda to'plam ko'rinishiga aylantirib yubormaydi
    alohida_tur = elon_turi(elon, models) in TOPLAM_TURLAR
    kanal_id_yoz(num, ' '.join(f'{y}:{int(m)}' for y, m in postlar) if alohida_tur else kanal_id_matn(postlar))
    if xatolar:
        send_msg(admin_joy('post'), f"⚠️ №{num} ba'zi kanalga chiqmadi: <code>{html_escape('; '.join(xatolar))}</code>")
    # A26: e'lon kanalga chiqdi — OLX bo'limiga matn + belgili albom (fonda: sayt / buyruq javobi kutib qolmasin)
    if olx:
        threading.Thread(target=olx_albom, args=(num,), daemon=True).start()
    return mid, ''


def kanal_tahrir(num):
    """Kanaldagi postni e'lonning hozirgi holatiga moslaydi. (True, '') / (False, sabab)."""
    elon, models = elon_cache_get(num)
    if not elon:
        return False, "e'lon topilmadi"
    mid = kanal_msg_id(elon)
    if not mid:
        return False, "post yo'q"
    if toplam_postmi(elon, models):
        return toplam_tahrir(mid)
    # A26: tahrirda ham suv belgisi (joyi o'zgargan bo'lsa — yangi joyda). editMessageText — bildirishnomasiz
    # MS3.1: har kanaldagi posti (yo'nalishi o'ziniki); kollaj — asosiy post bo'yicha
    natija = (True, '')
    for y, chat, m in kanal_postlar(elon):
        ok, xato = kanal_rich_yubor(num, elon, models, chat, m, kollaj=mid in _KOLLAJ,
                                    yonalish=y or post_yonalish(elon, models, mid=m))
        if not ok and natija[0]:
            natija = (False, xato)
    return natija


def olx_albom(num, jim=False):
    """A26: OLX bo'limiga (guruh «🛒 OLX» mavzusi; guruh yo'q — admin lichkasi) OLX matni + ODDIY albom (rich emas) —
    rasmlar suv belgisi bilan, OLX'ga bittalab saqlab joylash uchun. jim=True — bildirishnomasiz (tahrirdan keyin qayta).
    (True, '') / (False, xato)."""
    try:
        elon, models = elon_cache_get(num)
        if not elon:
            return False, "e'lon topilmadi"
        joy = admin_joy('olx')
        _, olx_text = build_olx_text(elon, models)
        r = req.post(f'{TG_API}/sendMessage', json={
            'chat_id': joy, 'text': olx_text, 'disable_notification': jim}, timeout=10).json()
        if not r.get('ok'):
            logger.error(f"olx_albom №{num} matn: {r.get('description')}")
        rasmlar = albom_manbalari(elon)
        if not rasmlar:
            return bool(r.get('ok')), '' if r.get('ok') else str(r.get('description'))
        # BUGUN148: file_id'i ma'lum rasm — file_id bilan (qayta yuklanmaydi); rad etilsa — manzillar bilan qayta
        _fid_jadvaldan(elon)
        fidli = [_URL_FID.get(u, u) for u in rasmlar]
        xabarlar = []
        for urinish in ([fidli, rasmlar] if fidli != rasmlar else [rasmlar]):
            if len(urinish) == 1:
                r = req.post(f'{TG_API}/sendPhoto', json={
                    'chat_id': joy, 'photo': urinish[0], 'disable_notification': jim}, timeout=30).json()
                xabarlar = [r.get('result')] if r.get('ok') else []
            else:
                r = req.post(f'{TG_API}/sendMediaGroup', json={
                    'chat_id': joy, 'media': [{'type': 'photo', 'media': u} for u in urinish],
                    'disable_notification': jim}, timeout=60).json()
                xabarlar = (r.get('result') or []) if r.get('ok') else []
            if r.get('ok'):
                break
            if urinish is fidli:
                logger.warning(f"olx_albom №{num}: file_id rad etildi ({r.get('description')}) — manzillar bilan")
        if r.get('ok') and len(xabarlar) == len(rasmlar):
            if fid_olindi(num, rasmlar, [_rasm_fid(x) for x in xabarlar]):
                fid_saqla_fonda(num)
        if not r.get('ok'):
            xato = str(r.get('description') or r)
            logger.error(f'olx_albom №{num} albom: {xato}')
            send_msg(joy, f"⚠️ №{num} OLX albomi yuborilmadi: <code>{html_escape(xato)}</code>")
            return False, xato
        return True, ''
    except Exception as e:
        logger.error(f'olx_albom №{num}: {e}')
        return False, str(e)


def kanal_ochir(num):
    """Postni o'chiradi, id'ni tozalaydi. To'plam ichidagi e'lon — to'plam qayta yasaladi."""
    elon, models = elon_cache_get(num)
    if not elon:
        return False, "e'lon topilmadi"
    mid = kanal_msg_id(elon)
    if not mid:
        return True, ''
    if toplam_postmi(elon, models):
        kanal_id_yoz(num, None)
        return toplam_tahrir(mid)
    qoldi, xato = [], ''   # MS3.1: hamma kanaldagi posti; o'chmagani id'da qoladi
    for y, chat, m in kanal_postlar(elon):
        ok, x = delete_msg(chat, m)
        if not ok:
            qoldi.append((y, m))
            xato = xato or x
    if not qoldi:
        kanal_id_yoz(num, None)
        return True, ''
    if qoldi[0][0] and len(qoldi) < len(kanal_postlar(elon)):
        kanal_id_yoz(num, ' '.join(f'{y}:{m}' for y, m in qoldi))
    return False, xato


def kanal_yana_keldi(num, yonalish=None):
    """«Yana keldi» / qayta yuborish: yangi post yuboriladi, yangi id yoziladi, KEYIN eskisi o'chadi (A14 qarori 2026-09-18).
    BUGUN251: avval yangisi — yangisi ketmasa eskisi kanalda qoladi. Eski post o'chmasa (48 soatdan eski / boshqa bot
    yuborgan) — bot uni tahrirlamaydi, adminga «eski postni qo'lda o'chiring» + havola (foydalanuvchi javobi 1B, 2026-10-17)."""
    elon, models = elon_cache_get(num)
    if not elon:
        return None, "e'lon topilmadi"
    mid = kanal_msg_id(elon)
    toplamda = bool(mid) and toplam_postmi(elon, models)
    eskilar = [] if toplamda or not mid else kanal_postlar(elon)   # MS3.1: hamma kanaldagisi
    yangi, xato = kanal_post(num, yonalish or (_POST_YON.get(int(mid)) if mid else None))
    if yangi and toplamda:
        toplam_tahrir(mid)   # BUGUN31: eski to'plamdan chiqdi (id endi yangi post'niki) — to'plam qayta yasaladi
    if yangi and eskilar:
        _eski_ochir(eskilar, f'№{num}')
    return yangi, xato


# ── To'plam (case / part / accessory; BUGUN31: saytda belgilangan har qanday e'lonlar) ──
TUR_TARTIB = ('phone', 'camera', 'accessory', 'case', 'part')
_KOLLAJ = set()   # B28: admin kollajga o'tkazgan postlar (mid). Xotirada — bot qayta ishga tushsa keyingi tahrirda slayd bo'ladi


def _tur_kalit(e, models):
    t = elon_turi(e, models)
    return (TUR_TARTIB.index(t) if t in TUR_TARTIB else len(TUR_TARTIB), -int(float(e.get('num', 0) or 0)))


def _toplam_items(shart):
    with _elon_cache_lock:
        items = list(_ELON_CACHE['by_num'].values())
        models = dict(_ELON_CACHE['models'])
    out = [e for e in items if elon_status(e) not in ('deleted', 'waited') and elon_turi(e, models) in TOPLAM_TURLAR and shart(e)]
    out.sort(key=lambda e: _tur_kalit(e, models))
    return out, models


def toplam_elonlar():
    """Hali kanalga chiqmagan (id yo'q) faol case/part/accessory e'lonlar."""
    return _toplam_items(lambda e: not kanal_msg_id(e))


def _mid_elonlar(mid, hammasi=False):
    """Shu postga (channel_message_id) yozilgan e'lonlar — har qanday tur. hammasi=False — faqat faollari."""
    with _elon_cache_lock:
        items = list(_ELON_CACHE['by_num'].values())
        models = dict(_ELON_CACHE['models'])
    out = [e for e in items if kanal_msg_id(e) == int(mid)
           and (hammasi or elon_status(e) not in ('deleted', 'waited'))]
    out.sort(key=lambda e: _tur_kalit(e, models))
    return out, models


def toplam_postmi(elon, models):
    """E'lonning posti to'plammi: case/part/accessory (/toplam) yoki bitta id'ga 2+ e'lon yozilgan (saytdan belgilab, B29)."""
    mid = kanal_msg_id(elon)
    if guruh_idsi(elon):
        # BUGUN251: rang guruhidagi e'lonning o'z posti (Ranglarni alohida) — oddiy post; to'plam faqat id umumiy bo'lsa
        return bool(mid) and len(_mid_elonlar(mid, hammasi=True)[0]) > 1
    if elon_turi(elon, models) in TOPLAM_TURLAR and ':' not in str(elon.get('channel_message_id', '') or ''):
        return True   # 3184.5: id «mobile:123» — o'z alohida posti (kanal_post), to'plam emas
    return bool(mid) and len(_mid_elonlar(mid, hammasi=True)[0]) > 1


def _narx_son(e):
    try:
        return float(str(e.get('price', '') or '').strip())
    except Exception:
        return None


def toplam_seriya(items, models_by_id):
    """B34 (BUGUN42): to'plamdagi HAMMA e'lon bitta telefon seriyasiga tegishli bo'lsa — o'sha seriya nomi (uz, ru), aks holda None.
    Tovar seriyasi: modelda `mos` bo'lsa — mos modellarning seriyalari (g'ilof «Pixel 10 / 10 Pro» → Pixel 10), yo'q bo'lsa —
    modelning o'z seriyasi (telefon). Umumiy seriya aniq bitta bo'lsa — sarlavhaga (foydalanuvchi: «Pixel 10 seriyasi,
    9 seriyasi, 8 seriyasi qilib ham jo'natish kerak»)."""
    series = _ELON_CACHE.get('series') or []
    umumiy = None
    for e in items:
        model = models_by_id.get(str(e.get('specId', '') or ''), {})
        mids = mos_expand(model.get('mos'), models_by_id, series) if parse_mos(model.get('mos')) else {str(e.get('specId', '') or '')}
        sers = {str((models_by_id.get(m) or {}).get('series', '') or '') for m in mids} - {''}
        umumiy = sers if umumiy is None else umumiy & sers
        if not umumiy:
            return None
    if not umumiy or len(umumiy) != 1:
        return None
    ser = next((s for s in series if str(s.get('key', '')) == next(iter(umumiy))), None)
    if not ser or ser_type(ser) not in ('phone', 'camera'):
        return None
    uz = str(ser.get('labelUz') or '').strip()
    return (uz, str(ser.get('labelRu') or uz).strip()) if uz else None


def build_toplam_html(items, models_by_id, kollaj=False):
    """To'plam posti — A17 (a) QISQA e'lon (BUGUN31; ilgari 50 ta e'lon nomma-nom — «chuvalchangdek po'ta»):
    rasm (slayd 10 tagacha / kollaj 4), «📦 Yangi keldi», «N ta tovar · min–max$»;
    5 tagacha — har biri bir qator (№, nom, narx), ko'p bo'lsa — tur bo'yicha soni; to'liq ro'yxat saytda.
    Tugmalar — postdagi turlar bo'limi (startapp=<tab>) + «Saytni ochish»."""
    rasmlar, src = [], {}
    for e in items:
        r = rasm_joylari(e)
        if r and r[0][0] not in rasmlar:
            rasmlar.append(r[0][0])
            src[r[0][0]] = belgili(*r[0])   # A26: to'plam posti ham kanal posti — suv belgisi bilan
    media = rich_media(rasmlar, kollaj, src)
    BOSH = '<p> </p>'
    guruh = {}
    for e in items:
        guruh.setdefault(elon_turi(e, models_by_id), []).append(e)
    turlar = [t for t in TUR_TARTIB if t in guruh]

    narxlar = [n for n in (_narx_son(e) for e in items if elon_status(e) != 'sold') if n]
    fmt = lambda n: ('%g' % n)
    oraliq = ''
    if narxlar:
        lo, hi = min(narxlar), max(narxlar)
        oraliq = f' · <b>{fmt(lo)}$</b>' if lo == hi else f' · <b>{fmt(lo)}–{fmt(hi)}$</b>'
    jami = f'<p>{len(items)} ta tovar / {len(items)} шт.{oraliq}</p>'

    if len(items) <= 5:
        qatorlar = []
        for e in items:
            num = int(float(e.get('num', 0) or 0))
            model = models_by_id.get(str(e.get('specId', '') or ''), {})
            nom = html_escape(elon_nomi(e, model, 'uz'))
            price = html_escape(str(e.get('price', '') or '').replace('.0', ''))
            if elon_status(e) == 'sold':
                narx = '<s>' + (price + '$' if price else '') + '</s> ' + ('Qolmadi' if kop_donali(e) else 'Sotildi')
            else:
                narx = f'<b>{price}$</b>' if price else ''
            qold = soni_qatori(e)
            emoji = TUR_NOMI.get(elon_turi(e, models_by_id), ('▫️',))[0]
            qatorlar.append(f'{emoji} №{num} {nom} — {narx}' + (f' · {qold.split(" / ")[0]}' if qold else ''))
        royxat = '<p>' + '<br/>'.join(qatorlar) + '</p>'
    else:
        royxat = '<p>' + '<br/>'.join(f'{TUR_NOMI[t][0]} {TUR_NOMI[t][1]} — {len(guruh[t])} ta' for t in turlar) \
                 + '<br/>Hammasi saytda / Все — на сайте</p>'

    tugma = lambda tur: f'<tg-button type="url" url="https://t.me/{BOT_USERNAME}?startapp={tur}">{TUR_NOMI[tur][0]} {TUR_NOMI[tur][1]}</tg-button>'
    qator_tugma = ''.join('<tg-button-row>' + ''.join(tugma(t) for t in turlar[i:i + 2]) + '</tg-button-row>'
                          for i in range(0, len(turlar), 2))
    # B34: bitta seriya — sarlavhada («Pixel 10 Seriyasi» / «Серия Pixel 10» — jadvaldagi labelUz / labelRu)
    seriya = toplam_seriya(items, models_by_id)
    if not seriya:
        sarlavha = '📦 Yangi keldi / Новое поступление'
    else:
        uz, ru = seriya[0].replace('Seriyasi', 'seriyasi'), seriya[1]
        if set(turlar) <= {'phone', 'camera'}:
            sarlavha = f'📱 {uz} / {ru}'
        else:
            ru = 'Для серии ' + ru[len('Серия '):] if ru.startswith('Серия ') else 'Для ' + ru
            sarlavha = f'📦 {uz} uchun / {ru}'
        sarlavha = html_escape(sarlavha)
    return (
        media
        + f'<p><b>{sarlavha}</b><br/>#toplam</p>'
        + jami
        + royxat
        + BOSH
        + qator_tugma
        + '<tg-button-row>'
          f'<tg-button type="url" style="primary" url="https://t.me/{BOT_USERNAME}?startapp=home">🛍 Saytni ochish / Открыть сайт</tg-button>'
          '</tg-button-row>'
    )


def toplam_tahrir(mid):
    """Shu to'plam postiga kirgan (id bir xil) e'lonlar bo'yicha post qayta yasalib tahrirlanadi; hech kim qolmasa — o'chadi."""
    items, models = _mid_elonlar(mid)
    if not items:
        _KOLLAJ.discard(int(mid))
        return delete_msg(POST_CHANNEL, mid)
    return edit_rich(POST_CHANNEL, mid, build_toplam_html(items, models, kollaj=int(mid) in _KOLLAJ))


def kollaj_tugma(mid, kollaj=False):
    """B28: admin lichkasidagi tugma (kanal postida emas — obunachilar ko'rmasin)."""
    ochir = [{"text": "🗑 Postni o'chirish", "callback_data": f"pochir:{int(mid)}"}]   # B34: sinov postini tozalash
    if kollaj:
        return {"inline_keyboard": [[{"text": "🎞 Slaydga qaytarish", "callback_data": f"slayd:{int(mid)}"}], ochir]}
    return {"inline_keyboard": [[{"text": "🖼 Kollajga o'tkazish", "callback_data": f"kollaj:{int(mid)}"}], ochir]}


def post_ochir(mid):
    """B34 (BUGUN42): kanal postini o'chiradi va unga yozilgan HAMMA e'lonning channel_message_id sini tozalaydi —
    TEST kanaldagi sinov postidan keyin e'lonlar «kanalda posti bor» bo'lib qolmasin (B27 — 93 e'lon asosiy kanalga,
    id bo'shlarini yuboradi). (True, 'N ta e'lon') / (False, sabab)."""
    mid = int(mid)
    items, _ = _mid_elonlar(mid, hammasi=True)
    postlar = kanal_postlar(items[0]) if len(items) == 1 else []
    if postlar and postlar[0][0]:
        for _, chat, m in postlar:   # MS3.1: yo'nalish kanallaridagi hamma posti
            ok, xato = delete_msg(chat, m)
            if not ok:
                return False, xato
    else:
        ok, xato = delete_msg(POST_CHANNEL, mid)
        if not ok:
            return False, xato
    _KOLLAJ.discard(mid)
    for e in items:
        kanal_id_yoz(int(float(e.get('num', 0) or 0)), None)
    return True, f"{len(items)} ta e'lon"


def post_ochir_tugma(admin_chat, xabar_id, data):
    """«🗑 Postni o'chirish» → «Ha / Yo'q» (tasodifan bosilmasin); «Ha» — post_ochir."""
    amal, _, mid = str(data).partition(':')
    if not re.fullmatch(r'\d{1,10}', mid):
        return
    tugma = lambda kb: req.post(f'{TG_API}/editMessageReplyMarkup', json={
        'chat_id': admin_chat, 'message_id': xabar_id, 'reply_markup': kb}, timeout=10)
    try:
        if amal == 'pochir':
            tugma({"inline_keyboard": [[{"text": "✅ Ha, o'chirilsin", "callback_data": f"pochir_ha:{mid}"},
                                        {"text": "↩️ Yo'q", "callback_data": f"pochir_yoq:{mid}"}]]})
        elif amal == 'pochir_yoq':
            tugma(kollaj_tugma(mid, int(mid) in _KOLLAJ))
        elif amal == 'pochir_ha':
            ok, izoh = post_ochir(mid)
            if ok:
                tugma({"inline_keyboard": []})
                send_msg(admin_chat, f"🗑 Post o'chirildi ({POST_CHANNEL}, id {mid}) — {izoh} yana «kanalga chiqmagan» bo'ldi.")
            else:
                send_msg(admin_chat, f"❌ Post o'chmadi: <code>{html_escape(izoh)}</code>")
    except Exception as e:
        logger.error(f'post_ochir_tugma: {e}')


def post_korinish(mid, kollaj):
    """B28: kanal postini kollaj ↔ slayd qilib tahrirlaydi (matn o'zgarmaydi). (True, '') / (False, sabab)."""
    mid = int(mid)
    items, models = _mid_elonlar(mid)
    if not items:
        return False, "bu postning e'loni topilmadi (o'chirilgan yoki post boshqa)"
    eski = mid in _KOLLAJ
    (_KOLLAJ.add if kollaj else _KOLLAJ.discard)(mid)
    if len(items) > 1 or elon_turi(items[0], models) in TOPLAM_TURLAR:
        ok, xato = edit_rich(POST_CHANNEL, mid, build_toplam_html(items, models, kollaj=kollaj))
    else:
        ok, xato = kanal_tahrir(int(float(items[0].get('num', 0) or 0)))   # MS3.1: hamma kanaldagi posti
    if not ok:
        (_KOLLAJ.add if eski else _KOLLAJ.discard)(mid)
    return ok, xato


def kollaj_almashtir(admin_chat, xabar_id, data):
    """«🖼 Kollajga o'tkazish» / «🎞 Slaydga qaytarish» bosildi: post tahrirlanadi, tugma teskarisiga almashadi."""
    amal, _, mid = str(data).partition(':')
    if not re.fullmatch(r'\d{1,10}', mid):
        return
    kollaj = amal == 'kollaj'
    ok, xato = post_korinish(mid, kollaj)
    if not ok:
        send_msg(admin_chat, f"❌ Post ko'rinishi o'zgarmadi: <code>{html_escape(xato)}</code>")
        return
    try:
        req.post(f'{TG_API}/editMessageReplyMarkup', json={'chat_id': admin_chat, 'message_id': xabar_id,
                                                            'reply_markup': kollaj_tugma(mid, kollaj)}, timeout=10)
    except Exception as e:
        logger.error(f'kollaj tugmasi: {e}')


def kanal_toplam(nums):
    """B29 (A18 a): saytda belgilangan e'lonlar → kanalga BITTA to'plam posti.
    Kanalda posti bor / chala / o'chirilgan e'lon o'tkazib yuboriladi (ikki marta chiqmasin).
    Bitta qolsa va u telefon/kamera bo'lsa — oddiy post (kanal_post).
    Natija: (mid, xato, yuborilgan nomerlar, [{'num', 'sabab'}])."""
    tanlangan, otkazildi, models = [], [], {}
    for n in dict.fromkeys(str(x) for x in nums):
        elon, md = elon_cache_get(n)
        models = md or models
        if not elon or elon_status(elon) in ('deleted', 'waited'):
            otkazildi.append({'num': int(n), 'sabab': "topilmadi yoki chala / o'chirilgan"})
        elif kanal_msg_id(elon):
            otkazildi.append({'num': int(n), 'sabab': 'kanalda posti bor'})
        elif guruh_idsi(elon):   # BUGUN251: rang guruhi o'z posti bilan chiqadi
            otkazildi.append({'num': int(n), 'sabab': "rang guruhida — guruh blokidan «Kanalga»"})
        else:
            tanlangan.append(elon)
    if not tanlangan:
        return None, "yuboriladigan e'lon yo'q", [], otkazildi
    tanlangan.sort(key=lambda e: _tur_kalit(e, models))
    yuborildi = [int(float(e.get('num', 0) or 0)) for e in tanlangan]
    if len(tanlangan) == 1 and elon_turi(tanlangan[0], models) not in TOPLAM_TURLAR:
        mid, xato = kanal_post(yuborildi[0])
        return mid, xato, (yuborildi if mid else []), otkazildi
    mid, xato = send_rich(POST_CHANNEL, build_toplam_html(tanlangan, models))
    if not mid:
        return None, xato, [], otkazildi
    for n in yuborildi:
        kanal_id_yoz(n, mid)
    return mid, '', yuborildi, otkazildi


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
            send_msg(admin_chat, "📭 Kanalga chiqmagan aksessuar / g'ilof / ehtiyot qism yo'q.")
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
        send_msg(admin_chat, f"✅ To'plam kanalga chiqdi (id {mid}), {len(p['nums'])} ta e'longa yozildi.", kollaj_tugma(mid))
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
        for g in {guruh_idsi(eski), guruh_idsi(yangi)} - {''}:
            guruh_yangila_keyin(g)   # BUGUN251: rang narxi / holati / nomi o'zgardi — guruh posti ham (kechiktirib, bir marta)
        if st == 'deleted':
            if mid:
                ok, xato = kanal_ochir(num)
                if not ok:
                    send_msg(admin_joy('post'), f"⚠️ №{num} kanal posti o'chmadi: <code>{html_escape(xato)}</code>")
            return 'ochir' if mid else ''
        if mid:
            ok, xato = kanal_tahrir(num)
            sabab = '' if ok else tahrir_sabab(xato)
            if sabab and not toplam_postmi(yangi, elon_cache_get(num)[1]):
                # BUGUN251: post qo'lda o'chirilgan / boshqa bot yuborgan — tahrir bo'lmaydi
                izoh = f"⚠️ №{num} kanal posti tahrirlanmadi — {TAHRIR_SABAB_MATN[sabab]}."
                if st == 'active':
                    yangi_mid, x2 = kanal_yana_keldi(num)
                    izoh += (f" Yangi post yuborildi (id {yangi_mid})." if yangi_mid
                             else f" Yangi post ham ketmadi: <code>{html_escape(x2)}</code>")
                else:
                    izoh += " E'lon faol emas — yangi post yuborilmadi."
                send_msg(admin_joy('post'), izoh)
                return 'yana' if st == 'active' else 'tahrir'
            if not ok:
                send_msg(admin_joy('post'), f"⚠️ №{num} kanal posti yangilanmadi: <code>{html_escape(xato)}</code>")
            elif eski is not None and _images_xom(eski) != _images_xom(yangi) and not toplam_postmi(yangi, elon_cache_get(num)[1]):
                # A26: rasmlar yoki suv belgisi joyi o'zgardi — OLX albomi ham yangisi bilan, JIM (narx o'zgarsa — yo'q)
                olx_albom(num, jim=True)
            return 'tahrir'
        if not _ELON_CACHE['time']:
            return ''   # xotira yuklanmagan — eskisi noma'lum, ehtiyot: avto-post yo'q
        _, models = elon_cache_get(num)
        yangi_elon = eski is None or elon_status(eski) == 'waited'
        if st == 'active' and yangi_elon and elon_turi(yangi, models) in AVTO_POST_TURLAR:
            mid, xato = kanal_post(num)
            if mid:
                send_msg(admin_joy('post'), f"📣 №{num} kanalga chiqdi (id {mid}) — {POST_CHANNEL}", kollaj_tugma(mid))
            else:
                send_msg(admin_joy('post'), f"⚠️ №{num} kanalga chiqmadi: <code>{html_escape(xato)}</code>")
            return 'post'
        return ''
    except Exception as e:
        logger.error(f'kanal_sinxron: {e}')
        return ''


# ══════════════════════════════════════════════════════════════════════════
#  BUGUN251 (2026-10-17): RANG GURUHI — KANAL POSTI («Ranglar» 4-bosqich)
#  Guruh (sayt «Guruh qilish», Guruhlar varag'i) → kanalga BITTA post: sarlavha, narx («12$ dan» — narxlar har xil),
#  «Ranglari:» (har rang — havola), «Mosligi:» (guruh tavsifi). Rasm — guruhning umumiy rasmlari, bo'lmasa har rangning
#  1-rasmi. Post har safar ma'lumotdan qayta yasaladi (rang qo'shilsa / narx o'zgarsa — tahrir).
#  · «Ranglarni alohida ham yuborilsinmi?» Ha — avval guruh posti (havolalar saytga), keyin har rang o'z posti
#    (orasi ≥3 s, 429 — kutib qayta), oxirida guruh posti tahrir: havolalar rang postlariga. Yo'q — faqat guruh posti.
#  · Qayta yuborish: yangisi yuboriladi, eskisi o'chadi. O'chmasa (48 soatdan eski / boshqa bot) — bot tahrirlamaydi,
#    adminga «eski postni qo'lda o'chiring» + havola (foydalanuvchi javobi 1B, 2026-10-17).
#  · Tahrir rad etilsa (post qo'lda o'chirilgan / boshqa bot yuborgan) — yangi post + adminga sababi.
#  · Kanal: env GURUH_KANAL_ID — bo'sh / «test» → TEST_CHANNEL (sukut: merge'dan keyin ham asl kanalga sinov posti
#    ketmasin); «asl» → e'lonning odatdagi kanali (post_kanal); boshqa qiymat — o'sha chat.
#    Test rejimida rang postlarining id'si Elonlar'ga YOZILMAYDI (asl kanal posti deb o'ylanmasin) — guruh id'si ichida («r»).
#  · Guruhlar.kanal_message_id — JSON {"k": kanal, "m": post id, "t": yuborilgan vaqt (epoch), "r": {num: rang posti id}}.
# ══════════════════════════════════════════════════════════════════════════
GURUH_KANAL = os.environ.get('GURUH_KANAL_ID', 'test').strip()
GURUH_ORALIQ_S = 3          # rang postlari orasi (Telegram kanalga ~20 xabar/daqiqa)
GURUH_429_URINISH = 3       # «Too Many Requests: retry after N» — necha marta kutib qayta
_GURUH_KECH_S = 8           # e'lon tahriridan keyin guruh postini yangilash — kechiktirib, bir marta (ketma-ket saqlashlar)
_GURUH_LOCK = threading.RLock()
_GURUH_FAOL = set()         # hozir yuborilayotgan / tahrirlanayotgan guruhlar
_GURUH_KUTDI = set()        # ish paytida yana o'zgargan — tugagach bir marta tahrir
_GURUH_TAYMER = {}
_uxla = time.sleep          # sinovda almashtiriladi
_taymer = threading.Timer
TAHRIR_SABAB_MATN = {
    'yoq': "post kanalda yo'q (qo'lda o'chirilgan)",
    'begona': "bu post boshqa bot yuborgan (yoki qo'lda yozilgan) — bot uni tahrirlay olmaydi",
}


def _fonda(fn, *a):
    threading.Thread(target=fn, args=a, daemon=True).start()


def guruh_idsi(elon):
    """E'lon qaysi rang guruhida (Elonlar.guruh) — '' yo'q."""
    return str((elon or {}).get('guruh', '') or '').strip()


def guruh_test_rejim():
    return GURUH_KANAL.lower() in ('', 'test')


def guruh_kanali(azolar, models):
    """Guruh posti qaysi kanalga (GURUH_KANAL_ID)."""
    if guruh_test_rejim():
        return TEST_CHANNEL
    if GURUH_KANAL.lower() == 'asl':
        return post_kanal(post_yonalish(azolar[0], models)) if azolar else POST_CHANNEL
    return GURUH_KANAL


def post_havola(chat, mid):
    """Kanal posti havolasi: @kanal → t.me/kanal/123; -100… (yopiq) → t.me/c/…/123; noma'lum — ''."""
    c = str(chat or '').strip()
    if not mid:
        return ''
    if c.startswith('@'):
        return f'https://t.me/{c[1:]}/{int(mid)}'
    if c.startswith('-100') and c[4:].isdigit():
        return f'https://t.me/c/{c[4:]}/{int(mid)}'
    return ''


def guruh_kanal_oqi(g):
    """Guruhlar.kanal_message_id → {'k', 'm', 't', 'r'}; post yo'q — {}. Oddiy son — POST_CHANNEL'dagi post."""
    v = (g or {}).get('kanal_message_id')
    if isinstance(v, str) and v.strip().startswith('{'):
        try:
            v = json.loads(v)
        except Exception:
            v = None
    if isinstance(v, dict):
        try:
            m = int(float(v.get('m')))
        except Exception:
            return {}
        r = {}
        for k, x in (v.get('r') or {}).items() if isinstance(v.get('r'), dict) else []:
            try:
                r[str(int(float(k)))] = int(float(x))
            except Exception:
                pass
        return {'k': str(v.get('k') or POST_CHANNEL), 'm': m, 't': int(float(v.get('t') or 0)), 'r': r}
    try:
        m = int(float(str(v).strip()))
    except Exception:
        return {}
    return {'k': POST_CHANNEL, 'm': m, 't': 0, 'r': {}} if m > 0 else {}


def tahrir_sabab(xato):
    """Tahrir xatosi: 'yoq' — post o'chirilgan, 'begona' — botniki emas (eski bot / qo'lda), '' — boshqa (tarmoq…)."""
    x = str(xato or '').lower()
    if 'message to edit not found' in x or 'message_id_invalid' in x or 'message not found' in x:
        return 'yoq'
    if "can't be edited" in x or 'message_author_required' in x:
        return 'begona'
    return ''


def _retry_after(xato):
    m = re.search(r'retry after (\d+)', str(xato or ''), re.I)
    return int(m.group(1)) if m else None


def _429_bilan(fn, *a):
    """Telegram «Too Many Requests: retry after N» — N soniya kutib qayta (GURUH_429_URINISH martagacha)."""
    for i in range(GURUH_429_URINISH):
        r = fn(*a)
        s = None if r[0] else _retry_after(r[1])
        if s is None or i == GURUH_429_URINISH - 1:
            return r
        _uxla(min(s, 60) + 1)
    return r


def _alohida(g):
    v = (g or {}).get('alohida')
    return v is True or str(v or '').strip().lower() in ('1', 'true', 'ha')


def _gnum(e):
    return int(float((e or {}).get('num', 0) or 0))


def guruh_ol(gid, yangila=False):
    """(guruh, a'zolar [faol / sotilgan e'lonlar, guruh tartibida], models). yangila — avval Sheets'dan qayta yuklash."""
    gid = str(gid or '').strip()
    if yangila or gid not in (_ELON_CACHE.get('guruhlar') or {}):
        elon_cache_load()
    with _elon_cache_lock:
        g = (_ELON_CACHE.get('guruhlar') or {}).get(gid)
        by_num = dict(_ELON_CACHE['by_num'])
        models = dict(_ELON_CACHE['models'])
    if not g:
        return None, [], models
    azolar = []
    for n in g.get('azolar') or []:
        try:
            e = by_num.get(str(int(float(n))))
        except Exception:
            continue
        if not e or elon_status(e) in ('deleted', 'waited') or ('guruh' in e and guruh_idsi(e) != gid):
            continue
        azolar.append(e)
    return g, azolar, models


def _guruh_nomi(g, azolar, models, lang='uz'):
    v = str((g or {}).get('nomUz' if lang == 'uz' else 'nomRu') or '').strip()
    if v or not azolar:
        return v
    return elon_nomi(azolar[0], models.get(str(azolar[0].get('specId', '') or ''), {}), lang)


def _guruh_rasmlar(g):
    v = (g or {}).get('rasmlar') or []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            v = [v]
    return [str(u).strip() for u in v if str(u or '').strip()] if isinstance(v, list) else []


def guruh_post_qur(g, azolar, models, havolalar=None, shablon=None):
    """Guruh posti HTML (rich). havolalar — {num: rang posti havolasi}; yo'q rang — saytga (startapp=elon_<num>)."""
    havolalar = havolalar or {}
    juft = [belgi_ajrat(u) for u in _guruh_rasmlar(g)] or [rasm_joylari(e)[0] for e in azolar if rasm_joylari(e)]
    rasmlar, src = [], {}
    for u, joy in juft:
        if u and u not in rasmlar:
            rasmlar.append(u)
            src[u] = belgili(u, joy)   # A26: kanal posti — suv belgisi bilan
    media = rich_media(rasmlar[:10], False, src)

    uz, ru = _guruh_nomi(g, azolar, models, 'uz'), _guruh_nomi(g, azolar, models, 'ru')
    sarlavha = html_escape(uz) + (f' / {html_escape(ru)}' if ru and ru != uz else '')
    fmt = lambda n: '%g' % n
    faol = [e for e in azolar if elon_status(e) != 'sold']
    narxlar = [n for n in (_narx_son(e) for e in faol) if n]
    farqli = len(set(narxlar)) > 1
    # 3189 (A55): juft guruh — telefon + g'ilof / aksessuar (rang emas): «…$ dan» yo'q, har qatorda o'z nomi va narxi
    aralash = len({elon_turi(e, models) == 'phone' for e in azolar}) > 1
    if not faol:
        narx = '<p>Qolmadi / Нет в наличии</p>'
    elif not narxlar or aralash:
        narx = ''
    elif farqli:
        narx = f'<p><b>{fmt(min(narxlar))}$ dan</b> / <b>от {fmt(min(narxlar))}$</b></p>'
    else:
        narx = f'<p><b>{fmt(narxlar[0])}$</b></p>'

    # 3189 (A62, Owner 2026-10-25): guruh posti ham TO'LIQ — narx, holati, aloqa. Holati hammasida bir xil — bitta qator,
    #     farqli — har rang qatorida
    hol = lambda e: holati_matni(e.get('condition', 'used') or 'used', str(e.get('cycle', '') or '').replace('.0', ''))
    hollar = {hol(e) for e in faol}
    holat = ''
    if len(hollar) == 1:
        cuz, cru, cem = next(iter(hollar))
        holat = (f'<p>{html_escape(cem)} Holati: <b>{html_escape(cuz)}</b><br/>'
                 f'{html_escape(cem)} Состояние: <b>{html_escape(cru)}</b></p>')

    qatorlar = []
    for e in azolar:
        num = _gnum(e)
        cuz = clean_color(e.get('color') or '').strip() or elon_nomi(e, models.get(str(e.get('specId', '') or ''), {}), 'uz')
        cru = clean_color(rang_ru(e)).strip()   # BUGUN260-7: colorRu bo'sh — rang lug'atidan
        nom = html_escape(cuz.upper()) + (f' / {html_escape(cru.upper())}' if cru and cru.upper() != cuz.upper() else '')
        if aralash:
            nom = html_escape(elon_nomi(e, models.get(str(e.get('specId', '') or ''), {}), 'uz'))
        if elon_status(e) == 'sold':
            qatorlar.append(f'• <s>{nom}</s> — qolmadi / нет')
            continue
        url = havolalar.get(num) or f'https://t.me/{BOT_USERNAME}?startapp=elon_{num}'
        p = _narx_son(e)
        qatorlar.append(f'• <a href="{html_escape(url)}">{nom}</a>' + (f' — {fmt(p)}$' if (farqli or aralash) and p else '')
                        + (f' · {html_escape(hol(e)[0])} / {html_escape(hol(e)[1])}' if len(hollar) > 1 else ''))
    ranglar = ('<p><b>Tanlang / Выберите:</b><br/>' if aralash else '<p><b>Ranglari / Цвета:</b><br/>') + '<br/>'.join(qatorlar) + '</p>' if qatorlar else ''

    izoh = html_escape(str(g.get('izoh') or '').strip()).replace('\n', '<br/>')
    izoh_ru = html_escape(str(g.get('izohRu') or '').strip()).replace('\n', '<br/>')
    mos = []
    if izoh:
        mos.append(f'<b>Mosligi:</b> {izoh}')
    if izoh_ru:
        mos.append(f'<b>Совместимость:</b> {izoh_ru}')
    mosligi = '<p>' + '<br/>'.join(mos) + '</p>' if mos else ''

    birinchi = _gnum(faol[0] if faol else (azolar[0] if azolar else {}))
    sahifa = f'elon_{birinchi}' if birinchi else 'home'
    aloqa, tugmalar = post_oxiri(sahifa, post_yonalish(azolar[0], models) if azolar else 'mobile', shablon)
    return (
        media
        + f'<p><b>{sarlavha}</b></p>'
        + holat
        + narx
        + ranglar
        + mosligi
        + '<p> </p>'
        + aloqa
        + tugmalar   # 3189: e'lon postidagi kabi — «Saytda ko'rish» o'rniga «🛒 Sotib olish» + «🛍 Boshqa e'lonlar»
    )


def _guruh_havolalar(g, azolar, models, kd):
    """«Ranglarni alohida» yoqilgan bo'lsa — {num: rang posti havolasi}. Test rejimida — kd['r'] dan (Elonlar'ga yozilmagan),
    asl rejimda — e'lonning o'z posti (to'plam posti emas; guruh kanalidagisi afzal)."""
    if not _alohida(g):
        return {}
    out = {}
    for e in azolar:
        num = _gnum(e)
        if guruh_test_rejim():
            m = (kd.get('r') or {}).get(str(num))
            h = post_havola(kd.get('k'), m) if m else ''
        else:
            postlar = [] if toplam_postmi(e, models) else kanal_postlar(e)
            p = next((x for x in postlar if x[1] == kd.get('k')), postlar[0] if postlar else None)
            h = post_havola(p[1], p[2]) if p else ''
        if h:
            out[num] = h
    return out


def guruh_kanal_yoz(gid, kd, alohida=None):
    """Guruh posti id'si (va «alohida») — Guruhlar varag'iga (Apps Script guruhKanal) va xotiraga. True — ok."""
    payload = {'id': str(gid), 'kanal_message_id': json.dumps(kd, separators=(',', ':')) if kd and kd.get('m') else ''}
    if alohida is not None:
        payload['alohida'] = bool(alohida)
    ok = False
    if SHEET_URL:
        try:
            # 🔴 faqat bot (API_KEY) — guruh posti id'sini begona yozmasin. Logda URL yo'q (kalit bor)
            r = req.get(f'{SHEET_URL}?action=guruhKanal&key={urllib.parse.quote(API_KEY)}'
                        f'&data={urllib.parse.quote(json.dumps(payload))}', timeout=20)
            text = r.text.strip()
            d = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
            ok = bool(d.get('ok'))
        except Exception as e:
            logger.error(f'guruh_kanal_yoz: {type(e).__name__}')
    with _elon_cache_lock:
        g = (_ELON_CACHE.get('guruhlar') or {}).get(str(gid))
        if g is not None:
            g['kanal_message_id'] = payload['kanal_message_id']
            if alohida is not None:
                g['alohida'] = bool(alohida)
    if not ok:
        logger.error(f'guruh_kanal_yoz: guruh {gid} id Sheets ga yozilmadi')
    return ok


def _eski_ochir(eskilar, nom, t=0):
    """Qayta yuborishdan keyin eski post(lar)ni o'chiradi [(yo'nalish, kanal, mid)]. O'chmagani — tahrirlanmaydi,
    adminga «eski postni qo'lda o'chiring» + havola (1B). True — hammasi o'chdi."""
    qoldi = []
    for _, chat, m in eskilar:
        ok, x = delete_msg(chat, m)
        if not ok:
            qoldi.append((chat, m, x))
    if not qoldi:
        return True
    sabab = '48 soatdan eski' if t and time.time() - t > 48 * 3600 else '48 soatdan eski yoki boshqa bot yuborgan'
    qatorlar = [f'• {post_havola(c, m)}' if post_havola(c, m) else f'• {html_escape(c)}, id {m}' for c, m, _ in qoldi]
    send_msg(admin_joy('post'),
             f"🧹 {html_escape(nom)}: yangi post yuborildi, eski post o'chmadi ({sabab}) — eski postni qo'lda o'chiring:\n"
             + '\n'.join(qatorlar) + f"\n<code>{html_escape(qoldi[0][2])}</code>")
    return False


def _guruh_ish(gid, fn, *a):
    """Bitta guruh ustida bir vaqtda bitta ish. Band bo'lsa — None (ish tugagach bir marta tahrir navbatga)."""
    with _GURUH_LOCK:
        if gid in _GURUH_FAOL:
            _GURUH_KUTDI.add(gid)
            return None
        _GURUH_FAOL.add(gid)
    try:
        return fn(gid, *a)
    finally:
        with _GURUH_LOCK:
            _GURUH_FAOL.discard(gid)
            qayta = gid in _GURUH_KUTDI
            _GURUH_KUTDI.discard(gid)
        if qayta:
            guruh_tahrir_fon(gid)


def _guruh_yubor(gid, alohida):
    g, azolar, models = guruh_ol(gid, yangila=True)
    if not g:
        return None, 'Guruh topilmadi', ''
    if not [e for e in azolar if elon_status(e) != 'sold']:
        return None, "Guruhda sotuvdagi rang yo'q", ''
    eski = guruh_kanal_oqi(g)
    chat = guruh_kanali(azolar, models)
    kd = {'k': chat, 'm': None, 't': int(time.time()), 'r': dict(eski.get('r') or {}) if eski.get('k') == chat else {}}
    html = guruh_post_qur(g, azolar, models, {})   # havolalar hozircha saytga (alohida — rang postlaridan keyin tahrir)
    mid, xato = _429_bilan(send_rich, chat, html)
    if not mid:
        return None, xato, ''
    kd['m'] = int(mid)
    guruh_kanal_yoz(gid, kd, alohida=None if alohida else False)
    if eski.get('m') and (eski['k'], eski['m']) != (chat, kd['m']):
        _eski_ochir([(None, eski['k'], eski['m'])], f"Guruh «{_guruh_nomi(g, azolar, models)}»", eski.get('t'))
    return kd['m'], '', post_havola(chat, kd['m'])


def guruh_yubor(gid, alohida=False):
    """Guruh posti kanalga (yangi yoki qayta). alohida — keyin fonda har rang o'z posti. (mid, xato, havola)."""
    gid = str(gid or '').strip()
    r = _guruh_ish(gid, _guruh_yubor, bool(alohida))
    if r is None:
        return None, 'Bu guruh posti hozir yuborilmoqda — biroz kuting', ''
    mid, xato, havola = r
    if mid:
        if alohida:
            _fonda(guruh_ranglar_fon, gid)
        else:
            g, azolar, models = guruh_ol(gid)
            send_msg(admin_joy('post'), f"📣 Guruh «{html_escape(_guruh_nomi(g, azolar, models))}» kanalga chiqdi"
                                        f"{' (TEST kanal)' if guruh_test_rejim() else ''}: {havola or mid}")
    return mid, xato, havola


def _guruh_ranglar(gid):
    """Har rang o'z posti (sotilgan / posti borlari o'tkaziladi), orasi ≥ GURUH_ORALIQ_S; oxirida guruh posti tahrir.
    {'yuborildi': [num], 'xatolar': [matn]}."""
    g, azolar, models = guruh_ol(gid, yangila=True)
    if not g:
        return {'yuborildi': [], 'xatolar': ['Guruh topilmadi']}
    kd = guruh_kanal_oqi(g)
    if not kd.get('m'):
        return {'yuborildi': [], 'xatolar': ["Guruh posti kanalda yo'q — avval «Kanalga»"]}
    guruh_kanal_yoz(gid, kd, alohida=True)
    g['alohida'] = True
    test = guruh_test_rejim()
    yuborildi, xatolar, birinchi = [], [], True
    for e in azolar:
        num = _gnum(e)
        if elon_status(e) == 'sold':
            continue
        if test and str(num) in kd['r']:
            continue
        if not test and kanal_msg_id(e) and not toplam_postmi(e, models):
            continue   # o'z posti bor
        if not birinchi:
            _uxla(GURUH_ORALIQ_S)
        birinchi = False
        if test:
            m, x = _429_bilan(kanal_rich_yubor, num, e, models, kd['k'])
            if m:
                kd['r'][str(num)] = int(m)
                guruh_kanal_yoz(gid, kd)
        else:
            m, x = _429_bilan(kanal_yana_keldi if kanal_msg_id(e) else kanal_post, num)   # to'plamda bo'lsa — undan chiqadi
        if m:
            yuborildi.append(num)
        else:
            xatolar.append(f'№{num}: {x}')
    with _GURUH_LOCK:
        _GURUH_KUTDI.discard(gid)   # rang postlari id'si yozilgani — quyidagi tahrir hammasini oladi
    ok, xato = guruh_tahrir(gid)
    if not ok:
        xatolar.append(f'guruh posti tahriri: {xato}')
    return {'yuborildi': yuborildi, 'xatolar': xatolar}


def guruh_ranglar_fon(gid):
    """«Ranglarni alohida yuborish» (fonda) — natija adminga."""
    try:
        r = _guruh_ish(gid, _guruh_ranglar)
        if r is None:
            send_msg(admin_joy('post'), f"⏳ Guruh {html_escape(gid)}: boshqa ish ketyapti — ranglarni keyinroq qayta yuboring.")
            return
        g, azolar, models = guruh_ol(gid)
        izoh = f"🎨 Guruh «{html_escape(_guruh_nomi(g, azolar, models))}»: {len(r['yuborildi'])} ta rang alohida yuborildi"
        izoh += (' (TEST kanal)' if guruh_test_rejim() else '') + (
            f" (№{', №'.join(str(n) for n in r['yuborildi'])})" if r['yuborildi'] else '')
        if r['xatolar']:
            izoh += '\n⚠️ ' + '\n⚠️ '.join(html_escape(x) for x in r['xatolar'])
        send_msg(admin_joy('post'), izoh)
    except Exception as e:
        logger.error(f'guruh_ranglar_fon {gid}: {e}')


# ── 3184.5 (2026-10-25): kanalga OMMAVIY yuborish (konkursdan oldin — eski e'lonlar) va 15 kunlik TOMCHI ──
# Owner: «test kanalga 4–5 ta; yaxshi bo'lsa kanalga eskilarni hammasini yuboramiz, so'ng konkurs — kirgan odam eski
# e'lonlarni ko'radi; keyin yangi e'lonlar birin-ketin, 15 kun ichida».
# Navbat — kanalda posti YO'Q faol e'lonlar (soni 0 — yo'q) + posti yo'q rang guruhlari (bitta guruh posti; a'zolari alohida emas).
# Chiqqani `channel_message_id` (guruh — Guruhlar.kanal_message_id) bilan belgilanadi — qayta yuborilmaydi; to'xtasa —
# «/ommaviy boshla» qaytadan: qolganidan davom etadi. OLX albomi yuborilmaydi (90 ta albom OLX mavzusini to'ldirmasin).
# 🔴 Navbatdagi biror post TEST kanalga tushadigan bo'lsa (env POST_CHANNEL_ID / POST_KANALLAR / GURUH_KANAL_ID yo'q) —
#    ikkalasi ham ishlamaydi: id test postga yozilib, e'lon asosiy kanalga hech qachon chiqmay qolardi.
OMMAVIY_ORALIQ_S = 4                      # postlar orasi (Telegram kanalga ~20 xabar/daqiqa; 429 — _429_bilan kutadi)
OMMAVIY_XATO_KETMA_KET = 5                # shuncha ketma-ket xato — to'xtaydi (bot kanalda admin emas va h.k.)
# 3189 (A61, Owner 2026-10-25): ommaviyda FAQAT smartfon — g'ilof / qism / aksessuar chiqmaydi (juft guruhdagi telefon —
# alohida posti bilan, g'ilofsiz). Ikki yarim: «/ommaviy boshla 1» — eskilari (raqami kichik), «… 2» — qolgani; eskisi birinchi.
# Yarim chegarasi — HAMMA faol telefonlar (kanalga chiqqani ham) raqam bo'yicha teng ikkiga: 1-yarim chiqqach 2-yarim siljimaydi.
# (3184.5 da hamma tur: qism → g'ilof → aksessuar → kamera → telefon tartibida edi.)
_OMMAVIY = {'ish': False, 'toxta': False}
KANAL_TOMCHI_BOSHI = os.environ.get('KANAL_TOMCHI_BOSHI', '').strip()   # «2026-11-01» (Toshkent) — bo'sh: tomchi O'CHIQ
KANAL_TOMCHI_KUN = 15
TOMCHI_SOAT = (10, 21)                    # Toshkent: kunlik postlar shu oraliqda teng taqsim
_TOMCHI = {'sana': None, 'vaqtlar': [], 'yuborildi': 0, 'xato': set(), 'jim': False}


def _ommaviy_chegara(items, models, faol):
    """1-yarimning oxirgi raqami: faol telefonlar (kanalga chiqqan-chiqmagan) raqam bo'yicha, toq bo'lsa 1-yarim bittaga ko'p."""
    nums = sorted(_gnum(e) for e in items if faol(e) and elon_turi(e, models) == 'phone')
    return nums[(len(nums) - 1) // 2] if nums else 0


def kanal_navbat(tartib='ommaviy', yarim=None):
    """Kanalga hali chiqmagan narsalar [{'num', 'tur', 'gid'?, 'soni'?}], raqam bo'yicha (eskisi birinchi).
    tartib='ommaviy' — faqat smartfon (3189); yarim 1 / 2 — shu yarmi (_ommaviy_chegara). 'tomchi' — hamma tur."""
    with _elon_cache_lock:
        items = list(_ELON_CACHE['by_num'].values())
        models = dict(_ELON_CACHE['models'])
        guruhlar = set((_ELON_CACHE.get('guruhlar') or {}).keys())
    faol = lambda e: elon_status(e) == 'active' and soni_val(e) != 0
    out, korildi = [], set()
    for e in items:
        if not faol(e):
            continue
        gid = guruh_idsi(e)
        if gid and gid in guruhlar:
            if gid in korildi:
                continue
            korildi.add(gid)
            g, azolar, _ = guruh_ol(gid)
            azolar = [a for a in azolar if faol(a)]
            turlar = {elon_turi(a, models) for a in azolar}
            if tartib == 'ommaviy' and 'phone' in turlar and len(turlar) > 1:
                # 3189: juft guruh (telefon + g'ilof) — ommaviyda telefon o'z posti bilan, g'ilof chiqmaydi
                out += [{'num': _gnum(a), 'tur': 'phone'} for a in azolar if elon_turi(a, models) == 'phone' and not kanal_msg_id(a)]
            elif g and azolar and not guruh_kanal_oqi(g).get('m'):
                out.append({'gid': gid, 'num': min(_gnum(a) for a in azolar),
                            'tur': 'phone' if turlar == {'phone'} else elon_turi(azolar[0], models), 'soni': len(azolar)})
            continue
        if not kanal_msg_id(e):
            out.append({'num': _gnum(e), 'tur': elon_turi(e, models)})
    if tartib == 'ommaviy':
        out = [x for x in out if x['tur'] == 'phone']
        if yarim in (1, 2):
            chegara = _ommaviy_chegara(items, models, faol)
            out = [x for x in out if (x['num'] <= chegara) == (yarim == 1)]
    out.sort(key=lambda x: x['num'])
    return out


def _navbat_nomi(x):
    return f"guruh {x['gid']} ({x['soni']} rang)" if x.get('gid') else f"№{x['num']}"


def _navbat_kanallari(x):
    """Shu narsa qaysi kanal(lar)ga tushadi."""
    if x.get('gid'):
        _, azolar, models = guruh_ol(x['gid'])
        return {guruh_kanali(azolar, models)}
    elon, models = elon_cache_get(x['num'])
    return {post_kanal(y) for y in elon_yonalishlar(elon, models) if y in YON_KANAL} or {POST_CHANNEL}


def navbat_test_xato(navbat):
    """'' — hammasi asosiy kanal(lar)ga; aks holda sabab (TEST kanalga tushadiganlar)."""
    test = [x for x in navbat if TEST_CHANNEL in _navbat_kanallari(x)]
    if not test:
        return ''
    guruh = any(x.get('gid') for x in test)
    return (f"⛔ {len(test)} tasi TEST kanalga ({TEST_CHANNEL}) tushadi: {', '.join(_navbat_nomi(x) for x in test[:5])}"
            + (' …' if len(test) > 5 else '') + ".\nAsosiy kanal sozlanmagan — Render → Environment: POST_CHANNEL_ID"
            + (" (yoki POST_KANALLAR)" if not POST_KANALLAR else '') + (", GURUH_KANAL_ID=asl" if guruh else '') + '.')


def _navbat_yubor(x):
    """Navbatdagi bittasi kanalga. (mid, xato)."""
    if x.get('gid'):
        r = _guruh_ish(x['gid'], _guruh_yubor, False)
        return (None, 'guruh posti hozir yuborilmoqda') if r is None else (r[0], r[1])
    elon, _ = elon_cache_get(x['num'])
    if elon and kanal_msg_id(elon):
        return kanal_msg_id(elon), ''   # orada chiqib bo'lgan (avto-post / tomchi) — qayta yo'q
    return kanal_post(x['num'], None, False)


def ommaviy_holat():
    """/ommaviy — nima, qayerga, qancha vaqt (yubormaydi)."""
    navbat = kanal_navbat()
    yarimlar = [kanal_navbat(yarim=1), kanal_navbat(yarim=2)]
    with _elon_cache_lock:
        bor = sorted(_gnum(e) for e in _ELON_CACHE['by_num'].values()
                     if elon_status(e) == 'active' and kanal_msg_id(e) and not guruh_idsi(e)
                     and elon_turi(e, _ELON_CACHE['models']) == 'phone')
    guruh = sum(1 for x in navbat if x.get('gid'))
    kanallar = sorted(set().union(*(_navbat_kanallari(x) for x in navbat))) if navbat else []
    q = [f"📣 <b>Kanalga ommaviy yuborish</b> — faqat smartfon, navbatda <b>{len(navbat)}</b> ta post"
         + (f" ({guruh} tasi rang guruhi — bitta post)" if guruh else '')]
    if navbat:
        q.append(f"Kanal: {html_escape(', '.join(kanallar))}")
        for i, y in enumerate(yarimlar, 1):
            q.append(f"{i}-yarim{' (eskilari)' if i == 1 else ''}: {len(y)} ta" + (f" — {html_escape(_navbat_nomi(y[0]))} … {html_escape(_navbat_nomi(y[-1]))}" if y else '')
                     + (f", ~{max(1, round(len(y) * (OMMAVIY_ORALIQ_S + 1.5) / 60))} daqiqa" if y else ''))
        q.append(f"Tartib: eskisi birinchi (har post orasi {OMMAVIY_ORALIQ_S} s); g'ilof / qism / aksessuar ommaviyda chiqmaydi")
    if bor:
        q.append(f"Kanalda posti bor (o'tkaziladi): №{', №'.join(str(n) for n in bor[:15])}" + (' …' if len(bor) > 15 else '')
                 + " — TEST kanaldagi post bo'lsa, avval /postochir")
    xato = navbat_test_xato(navbat)
    if xato:
        q.append(html_escape(xato))
    if _OMMAVIY['ish']:
        q.append("⏳ Hozir yuborilyapti — to'xtatish: /ommaviy toxtat")
    elif navbat and not xato:
        q.append("Boshlash: /ommaviy boshla 1 (keyin /ommaviy boshla 2) · to'xtatish: /ommaviy toxtat (keyin o'sha «boshla» — qolganidan davom)")
    q.append(tomchi_holat())
    return '\n'.join(q)


def ommaviy_ish(chat, yarim):
    """/ommaviy boshla 1|2 (fonda): shu yarim kanalga, orasi OMMAVIY_ORALIQ_S; har 20 tada va oxirida adminga hisob."""
    if _OMMAVIY['ish']:
        send_msg(chat, "⏳ Ommaviy yuborish allaqachon ketyapti — /ommaviy toxtat")
        return
    _OMMAVIY.update(ish=True, toxta=False)
    try:
        elon_cache_load()   # id'lar Sheets'dagidek (boshqa joydan chiqqani qayta ketmasin)
        navbat = kanal_navbat(yarim=yarim)
        xato = navbat_test_xato(navbat)
        if xato or not navbat:
            send_msg(chat, html_escape(xato) if xato else f"📭 {yarim}-yarimda kanalga chiqmagan smartfon yo'q.")
            return
        send_msg(chat, f"▶️ Ommaviy yuborish boshlandi ({yarim}-yarim): {len(navbat)} ta post, ~{max(1, round(len(navbat) * (OMMAVIY_ORALIQ_S + 1.5) / 60))} daqiqa. "
                       "To'xtatish: /ommaviy toxtat")
        chiqdi, xatolar, ketma = 0, [], 0
        for i, x in enumerate(navbat):
            if _OMMAVIY['toxta']:
                break
            if i:
                _uxla(OMMAVIY_ORALIQ_S)
            mid, x_ = _429_bilan(_navbat_yubor, x)
            if mid:
                chiqdi, ketma = chiqdi + 1, 0
            else:
                ketma += 1
                xatolar.append(f'{_navbat_nomi(x)}: {x_}')
                logger.error(f'ommaviy {_navbat_nomi(x)}: {x_}')
                if ketma >= OMMAVIY_XATO_KETMA_KET:
                    xatolar.append(f'{ketma} ta ketma-ket xato — to\'xtadi')
                    break
            if (i + 1) % 20 == 0 and i + 1 < len(navbat):
                send_msg(chat, f"📣 {i + 1}/{len(navbat)} — {chiqdi} ta chiqdi")
        qoldi = len(kanal_navbat(yarim=yarim))
        izoh = (f"{'⏸ To' + chr(39) + 'xtatildi' if _OMMAVIY['toxta'] else '✅ Tugadi'} ({yarim}-yarim): {chiqdi} ta post kanalga chiqdi"
                + (f", navbatda {qoldi} ta qoldi — davom: /ommaviy boshla {yarim}" if qoldi else '')
                + (" · keyingisi: /ommaviy boshla 2" if yarim == 1 and not qoldi and kanal_navbat(yarim=2) else ''))
        if xatolar:
            izoh += '\n⚠️ ' + '\n⚠️ '.join(html_escape(str(x)) for x in xatolar[:10]) + (' …' if len(xatolar) > 10 else '')
        send_msg(chat, izoh)
    except Exception as e:
        logger.error(f'ommaviy_ish: {type(e).__name__}: {e}')
        send_msg(chat, f"❌ Ommaviy yuborish to'xtadi: <code>{html_escape(type(e).__name__)}</code> — /ommaviy boshla {yarim} (qolganidan)")
    finally:
        _OMMAVIY['ish'] = False


def _tomchi_boshi():
    from datetime import date
    try:
        return date.fromisoformat(KANAL_TOMCHI_BOSHI[:10]) if KANAL_TOMCHI_BOSHI else None
    except ValueError:
        return None


def _tomchi_vaqtlar(kun, q):
    """Kunning q ta posti vaqti (unix): TOMCHI_SOAT oralig'i q bo'lakka, har bo'lak o'rtasida (10:00–21:00, 3 ta → 11:50, 15:30, 19:10)."""
    from datetime import datetime, timezone, timedelta
    bosh = datetime(kun.year, kun.month, kun.day, TOMCHI_SOAT[0], tzinfo=timezone(timedelta(hours=5))).timestamp()
    uzun = (TOMCHI_SOAT[1] - TOMCHI_SOAT[0]) * 3600
    return [bosh + uzun * (i + 0.5) / q for i in range(q)]


def tomchi_reja(hozir, jami):
    """Bugungi reja: {'holat': 'ochiq'|'kutadi'|'yoqilgan'|'tugadi', 'kun', 'bugun', 'chiqdi', 'keyingi', 'jami'}.
    Kunlik soni = navbatdagilar / qolgan kunlar (yuqoriga yaxlit) — kun boshida (yoki bot qayta ishga tushganda) hisoblanadi;
    yangi kelgani ertangi hisobga qo'shiladi. Qayta ishga tushganda o'tib ketgan vaqtlar yuborilmaydi (birdan 5 ta post
    tashlanmasin) — ular qolgan kunlarga taqsimlanadi."""
    from datetime import datetime, timezone, timedelta
    bugun = datetime.fromtimestamp(hozir, timezone(timedelta(hours=5))).date()
    boshi = _tomchi_boshi()
    if not boshi:
        return {'holat': 'ochiq', 'jami': jami, 'bugun': -(-jami // KANAL_TOMCHI_KUN)}
    kun = (bugun - boshi).days + 1
    if kun < 1:
        return {'holat': 'kutadi', 'jami': jami, 'kun': kun, 'boshi': boshi}
    if kun > KANAL_TOMCHI_KUN:
        return {'holat': 'tugadi', 'jami': jami, 'kun': kun}
    if _TOMCHI['sana'] != bugun:
        q = -(-jami // (KANAL_TOMCHI_KUN - kun + 1))
        vaqtlar = _tomchi_vaqtlar(bugun, q) if q else []
        _TOMCHI.update(sana=bugun, vaqtlar=vaqtlar, yuborildi=sum(1 for t in vaqtlar if t <= hozir))
    keyingi = next((t for t in _TOMCHI['vaqtlar'][_TOMCHI['yuborildi']:]), None)
    return {'holat': 'yoqilgan', 'jami': jami, 'kun': kun, 'bugun': len(_TOMCHI['vaqtlar']), 'chiqdi': _TOMCHI['yuborildi'],
            'keyingi': keyingi}


def tomchi_holat(hozir=None):
    """«💧 Kanal navbati: bugun 3, jami 41 …» — /tomchi va /ommaviy oxirida."""
    from datetime import datetime, timezone, timedelta
    hozir = time.time() if hozir is None else hozir
    navbat = [x for x in kanal_navbat('tomchi') if x['num'] not in _TOMCHI['xato']]
    r = tomchi_reja(hozir, len(navbat))
    if r['holat'] == 'ochiq':
        return (f"💧 Tomchi O'CHIQ. Yoqilsa — kanal navbati: bugun {r['bugun']}, jami {r['jami']} "
                f"({KANAL_TOMCHI_KUN} kunga, {TOMCHI_SOAT[0]}:00–{TOMCHI_SOAT[1]}:00). Yoqish — Render env KANAL_TOMCHI_BOSHI=YYYY-MM-DD")
    if r['holat'] == 'kutadi':
        return f"💧 Tomchi {r['boshi']:%d.%m} dan boshlanadi — kanal navbati: jami {r['jami']}"
    if r['holat'] == 'tugadi':
        return f"💧 Tomchi tugadi ({KANAL_TOMCHI_KUN} kun) — navbatda {r['jami']} ta qoldi"
    vaqt = f", keyingisi {datetime.fromtimestamp(r['keyingi'], timezone(timedelta(hours=5))):%H:%M}" if r['keyingi'] else ''
    return (f"💧 Kanal navbati: bugun {r['bugun']} ({r['chiqdi']} tasi o'tdi{vaqt}), jami {r['jami']} · "
            f"{r['kun']}/{KANAL_TOMCHI_KUN}-kun" + (" · ⏸ ommaviy yuborish ketyapti" if _OMMAVIY['ish'] else ''))


def tomchi_qadam(hozir):
    """Fonda har daqiqa: vaqti kelgan bo'lsa navbatdagi BITTA narsa kanalga (eskisi birinchi). True — post yuborildi."""
    if not _tomchi_boshi() or _OMMAVIY['ish']:
        return False
    navbat = [x for x in kanal_navbat('tomchi') if x['num'] not in _TOMCHI['xato']]
    r = tomchi_reja(hozir, len(navbat))
    if r['holat'] != 'yoqilgan' or not navbat or _TOMCHI['yuborildi'] >= sum(1 for t in _TOMCHI['vaqtlar'] if t <= hozir):
        return False
    xato = navbat_test_xato(navbat[:1])
    if xato:
        if not _TOMCHI['jim']:
            _TOMCHI['jim'] = True   # bir marta — har daqiqa emas
            send_msg(admin_joy('post'), '💧 Tomchi to\'xtab turibdi.\n' + html_escape(xato))
        return False
    x = navbat[0]
    _TOMCHI['yuborildi'] += 1
    mid, x_ = _429_bilan(_navbat_yubor, x)
    if mid:
        send_msg(admin_joy('post'), f"💧 {_navbat_nomi(x)} kanalga chiqdi (id {mid}).\n{tomchi_holat(hozir)}")
        return True
    _TOMCHI['xato'].add(x['num'])   # takror urinib navbatni to'sib qo'ymasin — admin qo'lda (/post)
    send_msg(admin_joy('post'), f"⚠️ 💧 {_navbat_nomi(x)} kanalga chiqmadi: <code>{html_escape(x_)}</code> — navbatdan chiqarildi, /post {x['num']}")
    return False


async def tomchi_loop():
    """KANAL_TOMCHI_BOSHI bo'lsa — har daqiqa tomchi_qadam (alohida ipda). Xato — bot yiqilmaydi."""
    await asyncio.sleep(90)   # ishga tushish yuki o'tsin, e'lon xotirasi yuklansin
    while True:
        try:
            await blok(tomchi_qadam, time.time())
        except Exception as e:
            logger.error(f'tomchi: {type(e).__name__}')
        await asyncio.sleep(60)


def kanal_navbat_buyruq(chat, text):
    """/ommaviy [boshla 1|2 | toxtat] · /tomchi (admin)."""
    qism = text.split()
    cmd, arg = qism[0].split('@')[0], (qism[1].lower() if len(qism) > 1 else '')
    if cmd == '/tomchi':
        send_msg(chat, tomchi_holat())
    elif arg in ('boshla', 'start'):
        if len(qism) > 2 and qism[2] in ('1', '2'):
            _fonda(ommaviy_ish, chat, int(qism[2]))
        else:
            send_msg(chat, "Qaysi yarim? /ommaviy boshla 1 (eskilari) yoki /ommaviy boshla 2 — holat: /ommaviy")
    elif arg in ('toxtat', "to'xtat", 'stop'):
        _OMMAVIY['toxta'] = True
        send_msg(chat, "⏸ To'xtatilmoqda (joriy post tugagach)." if _OMMAVIY['ish'] else "Ommaviy yuborish ketmayapti.")
    else:
        send_msg(chat, ommaviy_holat())


def guruh_tahrir(gid, yangila=False):
    """Guruh postini hozirgi ma'lumotdan qayta yasab tahrirlaydi. Post yo'q — hech narsa; a'zo qolmasa — post o'chadi.
    Tahrir rad etilsa (post o'chirilgan / boshqa bot) — yangi post + adminga sababi. Guruh tarqatilgan (Guruhlar'da
    endi yo'q) — posti o'chadi. (True, '') / (False, xato)."""
    with _elon_cache_lock:
        oldin = (_ELON_CACHE.get('guruhlar') or {}).get(str(gid))
    g, azolar, models = guruh_ol(gid, yangila)
    if not g:
        kd = guruh_kanal_oqi(oldin)
        if not (yangila and kd.get('m')):
            return False, 'Guruh topilmadi'
        ok, x = delete_msg(kd['k'], kd['m'])   # guruh tarqatildi (yangi yuklashda yo'q) — kanaldagi posti ham
        if not ok:
            send_msg(admin_joy('post'), f"🧹 Guruh {html_escape(gid)} tarqatildi, kanaldagi posti o'chmadi — qo'lda o'chiring: "
                                        f"{post_havola(kd['k'], kd['m']) or kd['m']}\n<code>{html_escape(x)}</code>")
        return True, ''
    kd = guruh_kanal_oqi(g)
    if not kd.get('m'):
        return True, ''
    if not azolar:
        ok, x = delete_msg(kd['k'], kd['m'])
        if ok:
            guruh_kanal_yoz(gid, {})
        return ok, x
    html = guruh_post_qur(g, azolar, models, _guruh_havolalar(g, azolar, models, kd))
    ok, xato = _429_bilan(edit_rich, kd['k'], kd['m'], html)
    if ok:
        return True, ''
    sabab = tahrir_sabab(xato)
    if not sabab:
        return False, xato
    nom = html_escape(_guruh_nomi(g, azolar, models))
    chat = guruh_kanali(azolar, models)
    yangi = {'k': chat, 'm': None, 't': int(time.time()), 'r': kd['r'] if kd['k'] == chat else {}}
    html = guruh_post_qur(g, azolar, models, _guruh_havolalar(g, azolar, models, yangi))
    mid, x2 = _429_bilan(send_rich, chat, html)
    if not mid:
        send_msg(admin_joy('post'), f"⚠️ Guruh «{nom}» posti tahrirlanmadi — {TAHRIR_SABAB_MATN[sabab]}. "
                                    f"Yangi post ham ketmadi: <code>{html_escape(x2)}</code>")
        return False, x2
    yangi['m'] = int(mid)
    guruh_kanal_yoz(gid, yangi)
    if sabab == 'begona':
        _eski_ochir([(None, kd['k'], kd['m'])], f'Guruh «{nom}»', kd.get('t'))
    send_msg(admin_joy('post'), f"⚠️ Guruh «{nom}» posti tahrirlanmadi — {TAHRIR_SABAB_MATN[sabab]}. "
                                f"Yangi post yuborildi: {post_havola(chat, mid) or mid}")
    return True, ''


def guruh_tahrir_fon(gid, yangila=True):
    """Fonda guruh posti tahriri (band bo'lsa — ish tugagach o'zi). Xato — adminga."""
    try:
        with _GURUH_LOCK:
            _GURUH_TAYMER.pop(gid, None)
        r = _guruh_ish(gid, guruh_tahrir, yangila)
        if r and not r[0]:
            send_msg(admin_joy('post'), f"⚠️ Guruh {html_escape(gid)} kanal posti yangilanmadi: <code>{html_escape(r[1])}</code>")
    except Exception as e:
        logger.error(f'guruh_tahrir_fon {gid}: {e}')


def guruh_yangila_keyin(gid):
    """E'lon o'zgardi — guruh posti (kanalda bo'lsa) _GURUH_KECH_S dan keyin bir marta yangilanadi."""
    gid = str(gid or '').strip()
    if not gid:
        return
    with _GURUH_LOCK:
        if gid in _GURUH_FAOL:
            _GURUH_KUTDI.add(gid)
            return
        g = (_ELON_CACHE.get('guruhlar') or {}).get(gid)
        if not g or not guruh_kanal_oqi(g).get('m'):
            return   # guruh kanalga chiqmagan
        eski = _GURUH_TAYMER.pop(gid, None)
        if eski:
            eski.cancel()
        t = _taymer(_GURUH_KECH_S, guruh_tahrir_fon, args=(gid,))
        t.daemon = True
        _GURUH_TAYMER[gid] = t
        t.start()


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
      <e'lon nomi (xotira)> — 3218: OLX sarlavhasiga nusxa (kanal posti / Store nomi bilan bir xil)
      ELON RAQAMI: #150
      <birxil shablon: telegramdan arzon, har oy konkurs, 20+ model>
      • Holati (uz/ru)
      <izoh uz / ru> — 3218: nuqson, to'plam (bo'sh bo'lsa — qator yo'q)
      Narxi: ~~eski~~ yangi
      ---
      Texnik xarakteristika (rang, xotira, ekran... uz+ru)
    """
    num = int(float(item.get('num', 0) or 0))
    storage = elon_xotira(item)   # BUGUN260-7: «MagSafe» xotira emas — alohida «Xususiyat» qatori
    xus_uz, xus_ru = xususiyat_matn(item, 'uz'), xususiyat_matn(item, 'ru')
    price = str(item.get('price', '')).replace('.0', '')
    old = str(item.get('oldPrice', '')).replace('.0', '')
    cond = item.get('condition', 'new')
    cycle = str(item.get('cycle', '') or '').replace('.0', '')
    color_uz = clean_color(item.get('color', ''))
    color_ru = clean_color(rang_ru(item))   # BUGUN260-7: colorRu bo'sh bo'lsa — rang lug'atidan

    model = models_by_id.get(item.get('specId', ''), {})
    spec_uz = model.get('specUz', '') or ''
    spec_ru = model.get('specRu', '') or ''

    cond_uz, cond_ru, _ = holati_matni(cond, cycle)
    # 3218: sarlavha — kanal posti bilan bir xil (e'lonning o'z nomi + qavsda xotira / xususiyat)
    qavs = elon_qavs(item)
    sarlavha = (elon_nomi(item, model, 'uz') + (f" ({qavs})" if qavs else '')).strip()
    izoh_uz, izoh_ru = izoh_matni(item, 'uz'), izoh_matni(item, 'ru')

    lines = []
    if sarlavha:
        lines.append(sarlavha)
        lines.append("")
    lines.append(f"ELON RAQAMI: #{num}")
    lines.append("")
    # ── Birxil shablon (har elon uchun bir xil) ──
    lines.append("Telegram kanal yoki saytimizdan zakaz qilganlarga narxi arzonroq "
                 "va kanalda har oy rozigrish (konkurs) bo'ladi!")
    lines.append("Bundan tashqari 20 ga yaqin modellar va boshqa aksessuarlar, "
                 "ehtiyot qismlar bor!")
    lines.append("Telegramdan yozing — linklarini tashlab beraman.")
    lines.append("")
    # ── Holati ──
    lines.append(f"• Holati: {cond_uz}")
    lines.append(f"• Состояние: {cond_ru}")
    lines.append("")
    # ── 3218: izoh (nuqson, to'plam) — narxdan oldin; xaridor ko'rmasa — janjal, qaytarish ──
    if izoh_uz:
        lines.append(izoh_uz)
        if izoh_ru != izoh_uz:
            lines.append(izoh_ru)
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
    if xus_uz:
        lines.append(f"• Xususiyat: {xus_uz}")
    if spec_uz:
        lines.append(spec_uz)
    lines.append("")
    if color_ru:
        lines.append(f"• Цвет: {color_ru}")
    if storage:
        lines.append(f"• Память: {storage}")
    if xus_ru:
        lines.append(f"• Особенности: {xus_ru}")
    if spec_ru:
        lines.append(spec_ru)

    return sarlavha, "\n".join(lines).strip()


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

def _kanal_azomi(kanal, user_id, nom='kanal'):
    """Kanal a'zoligi: True / False / None (tekshirib bo'lmadi — masalan bot u kanalda admin emas)."""
    try:
        r = req.get(f'{TG_API}/getChatMember', params={'chat_id': kanal, 'user_id': user_id}, timeout=6)
        j = r.json()
    except Exception as e:
        logger.error(f'getChatMember ({nom}): {type(e).__name__}')
        return None
    if isinstance(j, dict) and j.get('ok') and isinstance(j.get('result'), dict):
        return _azo(j['result'])
    logger.error(f"getChatMember ({nom} {kanal}): {str((j or {}).get('description', ''))[:80]} — bot u kanalda admin bo'lishi kerak")
    return None

def _tech_azomi(user_id):
    """BUGUN204: asosiy kanal (Nuqta tech) a'zoligi: True / False / None (tekshirib bo'lmadi — masalan bot u kanalda admin emas).
    Kanal: env TECH_KANAL_ID (@username yoki -100…), bo'sh bo'lsa @nuqta_tech."""
    return _kanal_azomi(TECH_KANAL or TECH_SUKUT, user_id, 'asosiy kanal')

def yetishmagan_kanallar(user_id):
    """BUGUN204: konkursga ikkala kanalga a'zolik shart. A'zo BO'LMAGAN kanallar ro'yxati, tartib: ['tech', 'mobile'];
    bo'sh — hammasiga a'zo. Mobile: tekshirib bo'lmasa — a'zo emas (avvalgidek). Asosiy kanal: tekshirib bo'lmasa
    (None — bot u kanalda admin emas / tarmoq) — to'sib QO'YILMAYDI, jurnalga yoziladi: aks holda hech kim qatnasha olmay qolardi."""
    yet = []
    if _tech_azomi(user_id) is False:
        yet.append('tech')
    if not is_member(user_id):
        yet.append('mobile')
    return yet

# BUGUN232: 2026-10-16 22:05 getKonkurs 10 s da javob bermadi → sayt /kirish_holat «kirmagan» oldi, /start «aktiv konkurs
# yo'q» deyishi mumkin edi. Endi: 20 s + qayta urinish; bir vaqtda bitta so'rov (parallel chaqiruvlar o'sha natijani oladi —
# 20 kishi /start bossa Apps Script'ga 20 ta so'rov ketmaydi); Apps Script baribir javob bermasa — oxirgi olingan
# konkurs (1 soatgacha). Eskirgan bo'lsa ham xavfsiz: _kk_aktivmi tugash vaqtini o'zi tekshiradi, yozish Apps Script'da.
_konkurs_qulf = threading.Lock()
_konkurs_oxirgi = {'avlod': 0, 'natija': None}   # nechanchi o'qish tugadi va nima qaytardi
_konkurs_zaxira = {'data': None, 'time': 0}      # oxirgi muvaffaqiyatli konkurs
KONKURS_ZAXIRA_S = 3600


def get_konkurs():
    now = time.time()
    if _konkurs_cache['data'] and now - _konkurs_cache['time'] < 120:
        return _konkurs_cache['data']
    if not SHEET_URL:
        return None
    avlod = _konkurs_oxirgi['avlod']
    if not _konkurs_qulf.acquire(timeout=90):
        return _konkurs_zaxira['data'] if time.time() - _konkurs_zaxira['time'] < KONKURS_ZAXIRA_S else None
    try:
        if _konkurs_oxirgi['avlod'] != avlod:      # biz kutganda boshqa oqim o'qib bo'ldi — o'sha natija
            return _konkurs_oxirgi['natija']
        natija = None
        try:
            r = _sheet_oqi('get_konkurs', f"{SHEET_URL}?action=getKonkurs&callback=d", timeout=20)
            text = r.text.strip()
            data = json.loads(text[2:-1]) if text.startswith('d(') else r.json()
            if data and data.get('id'):
                _konkurs_cache['data'] = data
                _konkurs_cache['time'] = time.time()
                _konkurs_zaxira.update(data=data, time=time.time())
                natija = data
            else:
                _konkurs_zaxira.update(data=None, time=0)   # jadval aniq aytdi: konkurs yo'q
        except Exception as e:
            logger.error(f'get_konkurs: {type(e).__name__}')
            if time.time() - _konkurs_zaxira['time'] < KONKURS_ZAXIRA_S:
                natija = _konkurs_zaxira['data']
                logger.warning("get_konkurs: Apps Script javob bermadi — oxirgi olingan konkurs ishlatildi")
        _konkurs_oxirgi.update(avlod=avlod + 1, natija=natija)
        return natija
    finally:
        _konkurs_qulf.release()


# ═══════════════════════════════════════════════════════════════
# KONKURS — tugatish va xabar yetkazish (BUGUN108, QOIDALAR_CHUQUR T2)
# 🔴 Nega qayta yozildi: 2026-09-04 bot qayta ishga tushib, ALLAQACHON TUGAGAN konkursga taymer qo'ydi — g'oliblar
# qayta tanlandi, ~90 kishiga 3 tadan xabar ketdi. Holat bot xotirasida edi, yetkazish jurnali yo'q edi.
# Endi:
#  • Holat — faqat JADVALDA (Konkurs: status, yetkazish, kanal_post; Qatnashchilar: xabar). Bot xotirasidagi taymer —
#    faqat «vaqt keldi» SIGNALI; restart, ikki nusxa bot, sayt tugmasi — ikkinchi tanlov ham, ikkinchi xabar ham bermaydi.
#  • endKonkurs IDEMPOTENT: tugagan konkursga — saqlangan g'oliblar qaytadi, qayta tanlanmaydi.
#  • Xabarlar — navbat + ijara: har odam qatori «olindi» → natija. Bot to'xtasa — qolganidan davom etadi.
#    «noaniq» (tarmoq uzildi — ketdimi, bilinmaydi) QAYTA YUBORILMAYDI — faqat admin /konkursdavom … noaniq desa.
#  • 429 — retry_after kutiladi; 403 (bloklagan) — yozib qo'yiladi, keyingisiga o'tiladi.
#  • Tugash vaqtidan 6 soatdan ko'p o'tgan (bot uzoq o'chiq edi) — o'zi tugatmaydi, adminga xabar.
# ═══════════════════════════════════════════════════════════════
KONKURS_KECHIKISH_S = 6 * 3600   # shundan ko'p kechikkan konkursni bot o'zi tugatmaydi
KONKURS_PARTIYA = 10             # navbatdan bir olishda nechta odam
KONKURS_ORALIQ_S = 0.1           # xabarlar orasida (Telegram chegarasi ~30/soniya — ancha past)


def _kk_worker_nomi():
    """Shu jarayon nomi (ijara egasi). Tasodifiy qo'shimcha — qayta ishga tushgan bot eski ijarani «o'ziniki» deb
    olmasin: eski nusxa olgan odamlar ikkinchi marta olinmaydi."""
    import socket
    asos = os.environ.get('RENDER_INSTANCE_ID') or socket.gethostname() or 'bot'
    return re.sub(r'[^A-Za-z0-9_.:-]', '', f'{asos}-{os.getpid()}-{os.urandom(2).hex()}')[-40:] or 'bot'


KONKURS_WORKER = _kk_worker_nomi()
# Tarqatma (konkurs e'loni Mijozlar'ga) — ESKI bot orqali: mijozlar yangi botga hali yozmagan, unga yozib bo'lmaydi.
ESKI_BOT_TOKEN = os.environ.get('ESKI_BOT_TOKEN', '').strip()
ESKI_BOT_USERNAME = 'kraken_mobile_shop_bot'


def _parse_end_time(end_str):
    """end_time matnini UTC timestamp (soniya)ga aylantiradi (Apps Script konkursTugashMs bilan BIR XIL qoida).
      1) zonali ISO satr: '...Z' (Apps Script Date->JSON, masalan '2026-07-08T16:10:00.000Z') yoki '+05:00' —
         zona hisobga olinadi, QAYTA -5 soat QILINMAYDI.
      2) 'YYYY-MM-DD HH:MM[:SS]' (zonasiz, naive) — Toshkent vaqti (UTC+5) deb qabul qilinadi, -5 soat qilinadi.
    Bo'sh / tushunarsiz — None.
    """
    if not end_str:
        return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?$',
                 str(end_str).strip(), re.I)
    if not m:
        return None
    from datetime import datetime
    import calendar
    try:
        dt = datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6] or 0))
    except ValueError:
        return None
    ts = calendar.timegm(dt.timetuple())
    zona = m[7]
    if not zona:
        return ts - 5 * 3600
    if zona.upper() == 'Z':
        return ts
    z = zona.replace(':', '')
    return ts - (1 if z[0] == '+' else -1) * (int(z[1:3]) * 3600 + int(z[3:5]) * 60)


def _kk_vaqt(ts):
    """UTC timestamp → 'dd.mm.yyyy HH:MM' Toshkent vaqtida."""
    from datetime import datetime, timezone, timedelta
    return (datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=5)).strftime('%d.%m.%Y %H:%M')


def _kk_aktivmi(k):
    """Konkursga hozir qatnashsa bo'ladimi: status 'active' va tugash vaqti o'tmagan.
    getKonkurs aktiv yo'q bo'lsa OXIRGI TUGAGAN konkursni qaytaradi — shu yerda ushlanadi."""
    if not k or str(k.get('status', '')).lower() != 'active':
        return False
    end = _parse_end_time(k.get('end_time'))
    return not end or end > time.time()


def _kk_sheet(action, timeout=30, **params):
    """Apps Script (API_KEY bilan). Javob {ok: …} bo'lsa — dict, aks holda None (tarmoq yoki ESKI versiya —
    eskisi noma'lum action'ga e'lonlar ro'yxatini qaytaradi, unda 'ok' yo'q).
    🔴 Xato matnida URL (key=…) bor — logga faqat xato turi yoziladi."""
    if not SHEET_URL or not API_KEY:
        logger.error(f'konkurs sheet {action}: SHEET_URL yoki API_KEY env bo\'sh')
        return None
    p = {'action': action, 'callback': 'd', 'key': API_KEY}
    p.update({k: str(v) for k, v in params.items() if v is not None})
    try:
        r = req.get(SHEET_URL, params=p, timeout=timeout)
        m = re.match(r'^d\((.*)\)\s*;?\s*$', (r.text or '').strip(), re.S)
        j = json.loads(m.group(1)) if m else None
        # BUGUN147: jim None / «ruxsat» — logga (kalit va URL'siz): admin buyrug'i nega ishlamagani ko'rinsin
        if not (isinstance(j, dict) and 'ok' in j):
            logger.error(f'konkurs sheet {action}: javob {r.status_code}, JSONP emas ({len(r.text or "")} belgi)')
        elif j.get('msg') == 'ruxsat':
            logger.error(f'konkurs sheet {action}: ruxsat — Render API_KEY Apps Script API_KEY ga mos emas')
        return j if isinstance(j, dict) and 'ok' in j else None
    except Exception as e:
        logger.error(f'konkurs sheet {action}: {type(e).__name__}')
        return None


# BUGUN173 (2026-10-14): /start → Mijozlar.yangi_bot (yangi bot) yoki eski_bot (eski botga yozgan) — Apps Script botStart.
# 3176 (2026-10-25): konkurs oqimi — /start va kanalga a'zo / chiqish voqealari NAVBATGA yoziladi, fonda har MIJOZ_KOP_S
# soniyada BITTA POST bilan (≤ MIJOZ_KOP_MAX ta) Apps Script botStartKop'ga. Ilgari har /start — alohida so'rov: yuzlab odam
# bir daqiqada kirsa Apps Script'ning bir vaqtdagi so'rov chegarasiga urilardi. Javob yo'q / qulf band — navbatda qoladi,
# keyingi safar qayta (Apps Script birinchi vaqtni qayta yozmaydi — qayta yuborish xavfsiz). Webhook kutmaydi.
_MIJOZ_BOT_YOZILGAN = set()   # (kanal, user_id, manba) — shu jarayonda navbatga tushganlar: har /start'da takror yubormaslik
_MIJOZ_KOP = []               # [{tur, user_id, …, vaqt}] — eng eskisi boshida
_MIJOZ_KOP_QULF = threading.Lock()
MIJOZ_KOP_S = 3
MIJOZ_KOP_MAX = 40            # Apps Script MJ_KOP_MAX = 50
MIJOZ_KOP_CHEGARA = 20000     # xotira himoyasi: Apps Script uzoq yotsa — eng eskisi tashlanadi (logda)
_mijoz_kop_xato = {'vaqt': 0.0}


def _tk_hozir():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() + 5 * 3600))   # Toshkent (UTC+5, yozgi vaqt yo'q)


def _mijoz_navbatga(d):
    with _MIJOZ_KOP_QULF:
        _MIJOZ_KOP.append(d)
        if len(_MIJOZ_KOP) > MIJOZ_KOP_CHEGARA:
            del _MIJOZ_KOP[:len(_MIJOZ_KOP) - MIJOZ_KOP_CHEGARA]
            logger.error(f'mijoz navbati {MIJOZ_KOP_CHEGARA} dan oshdi — eng eskilari tashlandi')


async def mijoz_bot_qayd(user, kanal, manba=''):
    """user — Telegram 'from' (id, username, first_name, language_code). kanal: 'yangi' | 'eski'.
    manba — /start parametri (konkurs posti havolasi va h.k.; Apps Script tozalaydi, bo'sh — 'bot')."""
    try:
        uid = str((user or {}).get('id') or '')
        manba = str(manba or '')[:64]
        if not uid or (kanal, uid, manba) in _MIJOZ_BOT_YOZILGAN:
            return
        if len(_MIJOZ_BOT_YOZILGAN) > 20000:
            _MIJOZ_BOT_YOZILGAN.clear()
        _MIJOZ_BOT_YOZILGAN.add((kanal, uid, manba))
        _mijoz_navbatga({'tur': 'start', 'user_id': uid, 'kanal': kanal, 'username': user.get('username') or '',
                         'ism': user.get('first_name') or '', 'til': user.get('language_code') or '', 'manba': manba,
                         'vaqt': _tk_hozir()})
    except Exception as e:
        logger.error(f'mijoz bot qayd ({kanal}): {type(e).__name__}')


def mijoz_kanal_qayd(cm):
    """`chat_member`: kanalga a'zo bo'ldi / chiqdi → Mijozlar.kanal_obuna (+ a'zo bo'lganda manba — taklif havolasi nomi,
    masalan konkurs posti uchun yaratilgan havola). Faqat navbatga — tarmoq yo'q (webhook ichida chaqirsa bo'ladi)."""
    try:
        if not isinstance(cm, dict):
            return ''
        eski, yangi = cm.get('old_chat_member') or {}, cm.get('new_chat_member') or {}
        user = yangi.get('user') or {}
        if user.get('is_bot') or not user.get('id') or _azo(eski) == _azo(yangi):
            return ''
        chat = cm.get('chat') or {}
        holat = 'a' if _azo(yangi) else 'c'
        _mijoz_navbatga({'tur': 'kanal', 'user_id': str(user['id']), 'username': user.get('username') or '',
                         'ism': user.get('first_name') or '', 'til': user.get('language_code') or '',
                         'kanal': chat.get('username') or str(chat.get('id') or ''), 'holat': holat,
                         'havola': ((cm.get('invite_link') or {}).get('name') or '')[:64] if holat == 'a' else '',
                         'vaqt': _tk_hozir()})
        return holat
    except Exception as e:
        logger.error(f'mijoz kanal qayd: {type(e).__name__}')
        return ''


def _kk_post(action, timeout=40, **body):
    """Apps Script doPost — kalit TANADA (katta to'plam GET URL'ga sig'maydi). {ok: …} → dict, aks holda None.
    🔴 Logga faqat xato turi (URL / kalit yo'q)."""
    if not SHEET_URL or not API_KEY:
        logger.error(f'sheet POST {action}: SHEET_URL yoki API_KEY env bo\'sh')
        return None
    try:
        r = req.post(SHEET_URL, data=json.dumps(dict(body, action=action, key=API_KEY), ensure_ascii=False).encode('utf-8'),
                     headers={'Content-Type': 'text/plain;charset=utf-8'}, timeout=timeout)
        j = json.loads(r.text) if (r.text or '').lstrip().startswith('{') else None
        if not (isinstance(j, dict) and 'ok' in j):
            logger.error(f'sheet POST {action}: javob {r.status_code}, JSON emas ({len(r.text or "")} belgi)')
            return None
        return j
    except Exception as e:
        logger.error(f'sheet POST {action}: {type(e).__name__}')
        return None


def _mijoz_kop_yubor():
    """Navbat boshidan ≤ MIJOZ_KOP_MAX tasini botStartKop bilan yozadi (bloklaydi — faqat fon oqimida).
    Yozildi — navbatdan olinadi; yo'q — joyida qoladi. Nechta yozilganini qaytaradi (0 — yozilmadi yoki bo'sh)."""
    with _MIJOZ_KOP_QULF:
        to_plam = _MIJOZ_KOP[:MIJOZ_KOP_MAX]
    if not to_plam:
        return 0
    j = _kk_post('botStartKop', royxat=to_plam)
    if not (j and j.get('ok')):
        hozir = time.time()
        if hozir - _mijoz_kop_xato['vaqt'] >= 600:
            _mijoz_kop_xato['vaqt'] = hozir
            logger.error(f'mijoz navbati: yozilmadi ({(j or {}).get("msg") or "javob yo`q"}), navbatda {len(_MIJOZ_KOP)}')
        return 0
    with _MIJOZ_KOP_QULF:
        # faqat shu oqim boshidan oladi, qolganlar oxiriga qo'shiladi — boshdagi len(to_plam) ta aynan yuborilganlar
        del _MIJOZ_KOP[:len(to_plam)]
    return len(to_plam)


async def mijoz_kop_loop():
    while True:
        await asyncio.sleep(MIJOZ_KOP_S)
        try:
            n = MIJOZ_KOP_MAX
            while n == MIJOZ_KOP_MAX:   # navbat to'la bo'lsa — kutmasdan ketma-ket
                n = await blok(_mijoz_kop_yubor) if _MIJOZ_KOP else 0
            if not _MIJOZ_KOP:
                continue
            if n == 0:
                await asyncio.sleep(12)   # Apps Script javob bermadi / qulf band — biroz kutib qayta
        except Exception as e:
            logger.error(f'mijoz navbat: {type(e).__name__}')


# ── 3184: SAVAT ESLATMASI va TAKROR QATORLAR — kimga (tanlov) va belgi Apps Script'da (savatEslatmaOl), bot faqat yuboradi.
# NEGA bot (Apps Script vaqt trigger'i emas): yangi trigger / tashqi so'rov egasidan qo'lda «Allow» so'raydi; bot esa Telegram'ga
# allaqachon yozadi — 429 ni kutadi, bloklaganni ajratadi (_kk_tg). SAVAT_ESLATMA (Render env): 'quruq' (sukut) — hech kimga
# yozilmaydi, logda faqat id oxirgi 3 raqami, til, № · 'ochiq' — yuboriladi · 'yoq' — o'chiq. Faqat 10:00–21:00 (Toshkent),
# 30 daqiqada bir, bir chaqiruvda ≤ 30 ta. Belgi YUBORISHDAN OLDIN qo'yiladi (qulf ichida) — tarmoq uzilsa ham ikki marta ketmaydi.
SAVAT_ESL_S = 1800
SAVAT_ESL_MAX = 30           # Apps Script SAVAT_ESL_MAX
SAVAT_ESL_SOAT = (10, 21)    # Apps Script SAVAT_ESL_SOAT
SAVAT_ESL_MATN = {'uz': ("Savatingizda tovar qoldi — u hali sotuvda 📱 Ko'rish 👇", 'Savat'),
                  'ru': ('В корзине остался товар — он ещё в продаже 📱 Посмотреть 👇', 'Корзина')}


def _savat_rejim():
    r = (os.environ.get('SAVAT_ESLATMA') or 'quruq').strip().lower()
    return r if r in ('quruq', 'ochiq', 'yoq') else 'quruq'


def _savat_oyna(t=None):
    soat = time.gmtime((time.time() if t is None else t) + 5 * 3600).tm_hour
    return SAVAT_ESL_SOAT[0] <= soat < SAVAT_ESL_SOAT[1]


def _savat_xabar(til):
    matn, tugma = SAVAT_ESL_MATN['ru' if til == 'ru' else 'uz']
    return matn, {'inline_keyboard': [[{'text': tugma, 'web_app': {'url': SAYT_URL + '?p=cart'}}]]}


def _savat_yubor(royxat, tg=None, uxla=0.1):
    """royxat — [{uid, til, nums}] → (yuborildi soni, [bloklagan uid]). Har xabar orasida uxla s (Telegram: ~30 xabar / s)."""
    tg = tg or _kk_tg
    n, bl = 0, []
    for x in (royxat or [])[:SAVAT_ESL_MAX]:
        uid = str(x.get('uid') or '')
        if not uid.isdigit():
            continue
        matn, markup = _savat_xabar(x.get('til'))
        h, _ = tg('sendMessage', {'chat_id': int(uid), 'text': matn, 'reply_markup': markup})
        if h == 'yuborildi':
            n += 1
        elif h == 'bloklagan':
            bl.append(uid)
        time.sleep(uxla)
    return n, bl


def _savat_eslatma_bir(t=None):
    """Bir aylanish. → (rejim, natija dict) yoki None (o'chiq / oyna tashqarisi / Apps Script javob bermadi)."""
    rejim = _savat_rejim()
    if rejim == 'yoq' or not _savat_oyna(t):
        return None
    j = _kk_post('savatEslatmaOl', rejim=rejim)
    if not (j and j.get('ok')):
        logger.error(f'savat eslatma: ro`yxat olinmadi ({(j or {}).get("msg") or "javob yo`q"})')
        return None
    if rejim == 'quruq':
        r = [f'{x.get("id")} {x.get("til")} ' + ' '.join('№' + str(n) for n in (x.get('nums') or [])) for x in (j.get('royxat') or [])]
        logger.info(f'savat eslatma (quruq): {j.get("jami", 0)} ta' + (' — ' + ', '.join(r) if r else ''))
        return 'quruq', {'jami': j.get('jami', 0), 'royxat': r}
    n, bl = _savat_yubor(j.get('royxat') or [])
    if bl:
        _kk_post('savatEslatmaNatija', blok=bl)
    logger.info(f'savat eslatma: {n} yuborildi, {len(bl)} bloklagan (jami {j.get("jami", 0)})')
    return 'ochiq', {'jami': j.get('jami', 0), 'yuborildi': n, 'blok': len(bl)}


async def savat_eslatma_loop():
    await asyncio.sleep(300)   # ishga tushganda boshqa yuklashlar avval
    while True:
        try:
            await blok(_savat_eslatma_bir)
        except Exception as e:
            logger.error(f'savat_eslatma_loop: {type(e).__name__}')
        await asyncio.sleep(SAVAT_ESL_S)


def _birlashtir_kutish(t=None):
    """Keyingi 04:00 (Toshkent) gacha necha soniya."""
    t = time.time() if t is None else t
    tk = (t + 5 * 3600) % 86400
    return (4 * 3600 - tk) % 86400 or 86400


async def mijoz_birlashtir_loop():
    """Kunda bir marta, 04:00: bir user_id — bitta Mijozlar qatori (ortiqchasi Mijozlar_birlashtirildi ga). Logda — faqat sonlar."""
    while True:
        await asyncio.sleep(_birlashtir_kutish())
        try:
            j = await blok(_kk_post, 'mijozBirlashtir', 120)
            if j and j.get('ok'):
                logger.info(f'mijoz birlashtirish: {j.get("guruh", 0)} odam, {j.get("olindi", 0)} qator olindi, qoldi {j.get("qator", 0)}')
            else:
                logger.error(f'mijoz birlashtirish: {(j or {}).get("msg") or "javob yo`q"}')
        except Exception as e:
            logger.error(f'mijoz_birlashtir_loop: {type(e).__name__}')
        await asyncio.sleep(60)


_KK_BLOK_BELGI = ('blocked', 'deactivated', 'chat not found', 'peer_id_invalid', 'user not found',
                  'bot was kicked', "bot can't initiate")


def _kk_tg(usul, payload, token=None, timeout=20, urinish=3, files=None):
    """Telegram so'rovi → (natija, javob). natija:
      'yuborildi' · 'bloklagan' (403 / foydalanuvchi yo'q) · 'xato' (Telegram aniq rad etdi — ketmadi) ·
      'noaniq' (tarmoq uzildi / 5xx — ketgan bo'lishi mumkin; QAYTA YUBORILMAYDI).
    429 — Telegram aytgan retry_after kutilib, qayta (ilgari xabar jimgina yo'qolardi).
    files — fayl yuklash (multipart; ichidagi fayl — bayt, qayta urinishda ham o'qiladi)."""
    url = f'https://api.telegram.org/bot{token}/{usul}' if token else f'{TG_API}/{usul}'
    for n in range(urinish):
        try:
            if files:
                r = req.post(url, data={k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                        for k, v in payload.items()}, files=files, timeout=timeout)
            else:
                r = req.post(url, json=payload, timeout=timeout)
        except Exception as e:
            logger.error(f'konkurs tg {usul}: {type(e).__name__}')
            return 'noaniq', None
        try:
            j = r.json()
        except Exception:
            j = None
        j = j if isinstance(j, dict) else {}
        if r.status_code == 200 and j.get('ok'):
            return 'yuborildi', j
        if r.status_code == 429:
            if n + 1 < urinish:
                kut = (j.get('parameters') or {}).get('retry_after') or 5
                time.sleep(min(float(kut), 60) + 0.5)
                continue
            return 'xato', j
        tavsif = str(j.get('description', '')).lower()
        if r.status_code == 403 or (r.status_code == 400 and any(b in tavsif for b in _KK_BLOK_BELGI)):
            return 'bloklagan', j
        if 400 <= r.status_code < 500:
            logger.warning(f'konkurs tg {usul}: {r.status_code} {tavsif[:120]}')
            return 'xato', j
        return 'noaniq', j
    return 'xato', None


def _kk_shaxsiy(chat_id, matn, markup, rasm=None, token=None):
    """Bir odamga BITTA xabar: rasm bilan (bo'lsa), bo'lmasa matn. Keyingi usulga faqat 'xato' (aniq ketmagan) da
    o'tiladi — 'noaniq' da ikkinchi xabar yuborilmaydi (ilgari rasm → matn zaxirasi ba'zan ikkalasini ham yuborardi)."""
    for r in ([rasm] if isinstance(rasm, str) else (rasm or [])):
        if not r or len(matn) > 1024:
            continue
        h, _ = _kk_tg('sendPhoto', {'chat_id': chat_id, 'photo': r, 'caption': matn, 'parse_mode': 'HTML',
                                    'reply_markup': markup}, token=token)
        if h != 'xato':
            return h
    h, _ = _kk_tg('sendMessage', {'chat_id': chat_id, 'text': matn, 'parse_mode': 'HTML', 'reply_markup': markup},
                  token=token)
    return h


def _kk_sinovmi(prize):
    """Sinov konkursi — sovrin nomi «TEST» yoki «🧪» bilan boshlanadi (chiqarish kuni 1–2 kishilik sinov, HOZIR.md).
    Nega: asosiy kanalga sinov xabari HECH QACHON ketmaydi (G11.0, foydalanuvchi) — kanal posti va anons TEST kanalga,
    «/tarqatma … hammaga» (~287 mijoz) — umuman yo'q."""
    p = str(prize or '').strip()
    return p.upper().startswith('TEST') or p.startswith('🧪')


def _kk_kanal_post(matn, toplamlar, markup, kanal=None):
    """Kanalga natija posti. toplamlar: [file_id'lar, url'lar] — birinchi ishlagani (token almashsa file_id o'tmaydi).
    1 rasm — sendPhoto (matn sig'sa — bitta post); ko'p rasm — albom + tugma alohida xabarda (albomga tugma qo'yilmaydi).
    kanal: sukut — CHANNEL; sinov konkursi — TEST_CHANNEL (_kk_sinovmi)."""
    kanal = kanal or CHANNEL
    sigadi = len(matn) <= 1000
    for rasmlar in toplamlar:
        rasmlar = [r for r in (rasmlar or []) if r][:10]
        if not rasmlar:
            continue
        if len(rasmlar) == 1:
            p = {'chat_id': kanal, 'photo': rasmlar[0]}
            if sigadi:
                p.update(caption=matn, parse_mode='HTML', reply_markup=markup)
            h, _ = _kk_tg('sendPhoto', p)
        else:
            media = [{'type': 'photo', 'media': r} for r in rasmlar]
            if sigadi:
                media[0].update(caption=matn, parse_mode='HTML')
            h, _ = _kk_tg('sendMediaGroup', {'chat_id': kanal, 'media': media}, timeout=40)
        if h == 'xato':
            continue
        if h != 'yuborildi' or (len(rasmlar) == 1 and sigadi):
            return h
        _kk_tg('sendMessage', {'chat_id': kanal, 'text': '🛍' if sigadi else matn, 'parse_mode': 'HTML',
                               'reply_markup': markup})
        return 'yuborildi'
    h, _ = _kk_tg('sendMessage', {'chat_id': kanal, 'text': matn, 'parse_mode': 'HTML', 'reply_markup': markup})
    return h


def _kk_rasmlar(k):
    """Sovrin rasmlari → (file_id'lar, url'lar). file_id — shu bot yuklagan; url — zaxira."""
    fids, urls, kor = [], [], set()
    for ustun in ('prizePicFileIds', 'prizePics'):
        for p in str((k or {}).get(ustun) or '').split(','):
            p = p.strip()
            if p and p not in kor:
                kor.add(p)
                (urls if p.startswith('http') else fids).append(p)
    return fids[:10], urls[:10]


_KK_MEDAL = ['🥇', '🥈', '🥉']


def _kk_medal(o):
    return _KK_MEDAL[o - 1] if 1 <= o <= 3 else f"{o}."


def _kk_orin(w, idx):
    try:
        return int(w.get('place') or idx + 1)
    except (TypeError, ValueError):
        return idx + 1


def _kk_goliblar_matni(winners):
    """G'oliblar qatori (mag'lubga, kanalga, adminga): 🥇 @user — sovg'a."""
    q = []
    for idx, w in enumerate(winners or []):
        wp = w.get('prize', '')
        q.append(f"{_kk_medal(_kk_orin(w, idx))} {winner_display(w)}" + (f" — {html_escape(wp)}" if wp else ""))
    return "\n".join(q) if q else "—"


def _kk_golib_xabari(place, prize):
    cap = (
        f"🏆 <b>Tabriklaymiz! Siz g'olib bo'ldingiz!</b> 🎊\n\n"
        f"{_kk_medal(place)} <b>{place}-o'rin</b> — <b>{html_escape(prize)}</b>\n\n"
        f"🎁 Sovg'angizni olish uchun adminga yozing.\n"
        f"🎁 Для получения приза напишите администратору."
    )
    return cap, {"inline_keyboard": [[{
        "text": "📩 Adminga yozish / Написать админу", "url": f"https://t.me/{ADMIN_USERNAME}"}]]}


def _kk_maglub_xabari(prize, win_text):
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
    return cap, {"inline_keyboard": [[{
        "text": "🛍 Smartfonlarni ko'rish / Смотреть смартфоны", "web_app": {"url": SAYT_URL}}]]}


def _kk_kanal_xabari(prize, win_text):
    matn = (
        f"🎊 <b>KONKURS YAKUNLANDI!</b> 🎊\n"
        f"🎁 <b>{html_escape(prize)}</b>\n\n"
        f"🏆 <b>G'oliblar / Победители:</b>\n{win_text}\n\n"
        f"🇺🇿 G'oliblarni tabriklaymiz! Sovg'ani olish uchun admin bilan bog'laning.\n"
        f"🇷🇺 Поздравляем победителей! Для получения приза свяжитесь с админом.\n\n"
        f"📅 Har oy yangi konkurslar — kuzatib boring!"
    )
    return matn, {"inline_keyboard": [[{
        "text": "🛍 Do'kon / Магазин", "url": f"https://t.me/{BOT_USERNAME}?startapp"}]]}


def _kk_sovrinlar(k):
    arr = k.get('prizesArr')
    if not isinstance(arr, list):
        arr = [x.strip() for x in str(k.get('prizes') or '').strip().strip('[]').split(',') if x.strip()]
    return [str(x) for x in arr if str(x).strip()]


def _kk_oz_matn(k, til, prize, end, sovrin):
    """BUGUN125: admin Konkurs varag'iga o'zi yozgan matn (tarqatma_matni / tarqatma_matni_ru). Bo'sh — None (eski matn).
    HTML sifatida emas, oddiy matn sifatida (escape) — <, & xato bermasin; o'rinbosarlar: {sovrin} {sovrinlar} {tugaydi} {bot}."""
    oz = str(k.get('tarqatma_matni_ru' if til == 'ru' else 'tarqatma_matni') or '').strip()
    if not oz:
        return None
    m = html_escape(oz).replace('\r\n', '\n')
    vaqt = f"{_kk_vaqt(end)} ({'по Ташкенту' if til == 'ru' else 'Toshkent vaqti'})" if end else ''
    for kalit, qiymat in (('{sovrin}', f"<b>{prize}</b>"), ('{sovrinlar}', "\n".join(sovrin)),
                          ('{tugaydi}', vaqt), ('{bot}', f"@{BOT_USERNAME}")):
        m = m.replace(kalit, qiymat)
    return m


def _kk_tarqatma_xabari(k, til):
    """Konkurs e'loni (rebranding bilan) — eski botdan Mijozlar'ga. Tugma yangi botda konkursga olib boradi.
    BUGUN125: Konkurs varag'ida o'z matni bo'lsa — o'sha (tugma baribir avtomatik qo'shiladi)."""
    prize = html_escape(str(k.get('prize') or ''))
    end = _parse_end_time(k.get('end_time'))
    sovrin = [f"{_kk_medal(i + 1)} {html_escape(p)}" for i, p in enumerate(_kk_sovrinlar(k))]
    oz = _kk_oz_matn(k, til, prize, end, sovrin)
    tugma = "🎁 Участвовать" if til == 'ru' else "🎁 Qatnashish"
    if oz:
        return oz, {"inline_keyboard": [[{"text": tugma, "url": f"https://t.me/{BOT_USERNAME}?start=konkurs"}]]}
    # BUGUN180 (foydalanuvchi, 2026-10-14, 4-band): eski botdan — yangi botga hali o'tmaganlarga; matn aynan shu
    if til == 'ru':
        q = ["🌚 Вы всё ещё не перешли в бот? Там уже стартовал конкурс",
             "🎁 Чтобы участвовать — нажмите кнопку ниже 👇"]
        tugma = "🎁 Участвовать"
    else:
        q = ["🌚 Siz hali ham botga o'tmadingizmi? U yerda allaqachon konkursga start berildi",
             "🎁 Qatnashish uchun pastdagi tugmani bosing 👇"]
        tugma = "🎁 Qatnashish"
    return "\n".join(q), {"inline_keyboard": [[{"text": tugma, "url": f"https://t.me/{BOT_USERNAME}?start=konkurs"}]]}


def _kk_yangibot_xabari(k, til):
    """BUGUN184 (v169/v170): yangi botga /start bosgan, lekin konkursda qatnashmaganlarga — YANGI bot orqali, bir marta.
    Tugma — callback (ular allaqachon botda): bosilsa start_konkurs_flow (telefon so'rovi) boshlanadi.
    BUGUN190 (foydalanuvchi, 2026-10-14, B): 👋 → 🌚; tugma ikkala tilda «🎯 Qatnashish / Участвовать» — emoji bitta."""
    prize = html_escape(str(k.get('prize') or ''))
    end = _parse_end_time(k.get('end_time'))
    if til == 'ru':
        q = ["🌚 В связи с ребрендингом Nuqta Tech объявляет конкурс!", f"🎁 Приз: <b>{prize}</b>"]
        if end:
            q.append(f"⏰ Завершится: {_kk_vaqt(end)} (по Ташкенту)")
        q += ["", "Чтобы участвовать — нажмите кнопку ниже 👇"]
        tugma = "🎯 Qatnashish / Участвовать"
    else:
        q = ["🌚 Nuqta tech rebranding munosabati bilan konkurs e'lon qildi!", f"🎁 Sovrin: <b>{prize}</b>"]
        if end:
            q.append(f"⏰ Tugaydi: {_kk_vaqt(end)} (Toshkent vaqti)")
        q += ["", "Qatnashish uchun pastdagi tugmani bosing 👇"]
        tugma = "🎯 Qatnashish / Участвовать"
    return "\n".join(q), {"inline_keyboard": [[{"text": tugma, "callback_data": "kk_qatnash"}]]}


async def _kk_admin(matn, joy=None):
    await blok(send_msg, joy or ADMIN_ID, matn)


# ═══ BUGUN147: g'oliblar obunasi, kanaldan chiqish ogohlantirishi, yashirin oyna, /start bloki ═══
def _kk_kanal(k):
    """Shu konkurs uchun obuna talab qilinadigan kanal: sinov (TEST…/🧪) — TEST_CHANNEL, aks holda — CHANNEL."""
    return TEST_CHANNEL if _kk_sinovmi((k or {}).get('prize')) else CHANNEL


def _kk_kanal_havola(kanal):
    k = str(kanal or '')
    return f'https://t.me/{k.lstrip("@")}' if k.startswith('@') else CHANNEL_LINK


def _kk_obunami(uid, kanal, urinish=3, oraliq=2):
    """G'olib kanalga obunami: True / False / None (bilib bo'lmadi). 🔴 is_member tarmoq xatosida False qaytaradi —
    bu yerda xato «obuna emas» EMAS (BUGUN147): faqat Telegram aniq holat (left / kicked) aytsa — False."""
    for n in range(urinish):
        try:
            r = req.get(f'{TG_API}/getChatMember', params={'chat_id': kanal, 'user_id': uid}, timeout=10)
            j = r.json()
        except Exception as e:
            logger.error(f'konkurs obuna: {type(e).__name__}')
            j = None
        if isinstance(j, dict) and j.get('ok') and isinstance(j.get('result'), dict):
            return _azo(j['result'])
        if n + 1 < urinish:
            time.sleep(oraliq * (n + 1))
    return None


def _kk_yashirinmi(k):
    """Konkurs oynasi yashirinmi (Script Property KONKURS_YASHIRIN). Maydon yo'q (eski Apps Script) — yashirin."""
    return (k or {}).get('yashirin') is not False


_kk_kalitli = set()   # yashirin konkursga «kalit» bilan (saytda logo 3 marta → ?start=konkurs_y) kelgan user_id'lar


def _kk_korsatsinmi(k, uid):
    """Begona yashirin konkursni ko'rmaydi; admin va kalit bilan kelgan — ko'radi."""
    return not _kk_yashirinmi(k) or uid == ADMIN_ID or uid in _kk_kalitli or uid in SINOVCHI_IDS   # BUGUN213 §6b


def _kk_obunasiz_xabari(prize):
    cap = (
        f"😔 <b>Siz g'olib chiqdingiz, lekin kanalga obuna emassiz — sovg'a berilmaydi, qayta tanlaymiz.</b>\n"
        f"🎁 {html_escape(prize)}\n\n"
        f"😔 <b>Вы стали победителем, но не подписаны на канал — приз не выдаётся, мы выберем победителя заново.</b>"
    )
    return cap, {"inline_keyboard": [[{"text": "📢 Kanal / Канал", "url": CHANNEL_LINK}]]}


async def _kk_obuna_tekshir(kid, e, joy):
    """endKonkurs dan keyin, xabarlar va kanal postidan OLDIN: har g'olib kanalga obunami. Obuna emas (aniq) —
    o'rniga boshqasi (konkursQaytaTanla — jadvalda, idempotent: restartda takrorlanmaydi, o'sha odam qayta tushmaydi).
    Tekshirib bo'lmasa — g'olib QOLADI, adminga «tekshirib bo'lmadi». Qaytaradi (yakuniy g'oliblar, izohlar) yoki
    None — tekshiruv yopilmadi (konkursObunaTugadi javob bermadi; xabarlar kutadi, admin /konkursdavom)."""
    kanal = _kk_kanal(e)
    izoh = []
    for w in list(e.get('winners') or []):
        try:
            place = int(w.get('place') or 0)
        except (TypeError, ValueError):
            continue
        md = _kk_medal(place)
        joriy = w
        for _ in range(30):
            uid = str(joriy.get('user_id') or '')
            ob = await blok(_kk_obunami, uid, kanal)
            if ob is True:
                break
            if ob is None:
                izoh.append(f"⚠️ {md} {winner_display(joriy)} — obunani tekshirib bo'lmadi (Telegram javob bermadi). "
                            f"G'olib o'zgarmadi — o'zingiz tekshiring.")
                break
            r = await _kk_sorov('konkursQaytaTanla', id=kid, place=place, user_id=uid)
            if r is None or not r.get('ok'):
                izoh.append(f"⚠️ {md} {winner_display(joriy)} — obuna emas, lekin qayta tanlab bo'lmadi "
                            f"({html_escape((r or {}).get('msg') or 'Apps Script javob bermadi')}). G'olib o'zgarmadi.")
                break
            if r.get('nomzod_yoq'):
                izoh.append(f"⚠️ {md} {winner_display(joriy)} — obuna emas, boshqa nomzod qolmadi. G'olib o'zgarmadi.")
                break
            yangi = r.get('winner') or {}
            if str(yangi.get('user_id') or '') == uid:
                break
            izoh.append(f"🔁 {md} {winner_display(r.get('old') or joriy)} — kanalga obuna emas → "
                        f"yangi g'olib: {winner_display(yangi)}")
            joriy = yangi
        else:
            izoh.append(f"⚠️ {md} — 30 marta qayta tanlandi, to'xtatildi. Hozirgi: {winner_display(joriy)}")
    t = await _kk_sorov('konkursObunaTugadi', id=kid)
    if t is None or not t.get('ok'):
        await _kk_admin(f"⚠️ Konkurs <b>{html_escape(kid)}</b>: obuna tekshiruvini yopib bo'lmadi "
                        f"({html_escape((t or {}).get('msg') or 'Apps Script javob bermadi')}) — xabarlar va kanal "
                        f"posti hali ketmadi.\nDavom: /konkursdavom {html_escape(kid)}", joy)
        return None
    return t.get('winners') or [], izoh


# Kanaldan chiqish: qatnashchilar ro'yxati — keshda (har chiqishda jadval so'ralmaydi), 5 daqiqada yangilanadi
KK_IDS_UMR_S = 300
_kk_ids = {'kid': None, 'ids': set(), 'vaqt': 0}
_kk_chiqqan = set()   # (kid, uid) — shu jarayonda ogohlantirilgan (jadval javob bermasa ham ikkinchisi ketmaydi)
_kk_ids_lock = threading.Lock()


def _kk_qatnashchimi(kid, uid):
    """True / False — keshdan; None — ro'yxat olinmadi (konkursChiqdi o'zi tekshiradi)."""
    hozir = time.time()
    with _kk_ids_lock:
        if _kk_ids['kid'] == kid and hozir - _kk_ids['vaqt'] < KK_IDS_UMR_S:
            return uid in _kk_ids['ids']
    r = _kk_sheet('konkursQatnashIds', id=kid)
    with _kk_ids_lock:
        if r and r.get('ok'):
            _kk_ids.update(kid=kid, ids={str(x) for x in (r.get('ids') or [])}, vaqt=hozir)
            return uid in _kk_ids['ids']
        if _kk_ids['kid'] == kid:
            return uid in _kk_ids['ids'] or None
    return None


def _kk_qatnashchi_qosh(kid, uid):
    with _kk_ids_lock:
        if _kk_ids['kid'] == str(kid):
            _kk_ids['ids'].add(str(uid))


def _kk_chiqish_matni(kanal):
    k = html_escape(kanal)
    return (
        f"⚠️ <b>Kanaldan chiqib ketdingiz</b> — konkursda g'olib chiqsangiz, sovg'a berilmaydi.\n"
        f"Qaytib obuna bo'ling: {k}\n\n"
        f"⚠️ <b>Вы вышли из канала</b> — если вы победите в конкурсе, приз не будет выдан.\n"
        f"Подпишитесь снова: {k}"
    ), {"inline_keyboard": [[{"text": "📢 Kanalga qaytish / Вернуться в канал", "url": _kk_kanal_havola(kanal)}]]}


def kanal_chiqdi(cm):
    """`chat_member`: konkurs qatnashchisi konkurs paytida kanaldan chiqdi → bot lichkasiga BIR MARTA ogohlantirish
    (konkurs + odam bo'yicha; qaytib kirsa — hech narsa). Natija: 'yuborildi' | 'bloklagan' | 'xato' | 'noaniq' | ''.
    Yuborilmasa — jim (faqat log)."""
    if not isinstance(cm, dict):
        return ''
    eski, yangi = cm.get('old_chat_member') or {}, cm.get('new_chat_member') or {}
    user = yangi.get('user') or {}
    if user.get('is_bot') or not user.get('id') or not _azo(eski) or _azo(yangi):
        return ''
    k = get_konkurs()
    if not _kk_aktivmi(k):
        return ''
    kanal = _kk_kanal(k)
    if not _kanal_mos(cm.get('chat'), kanal):
        return ''
    kid, uid = str(k.get('id') or ''), str(user['id'])
    if not kid or (kid, uid) in _kk_chiqqan or _kk_qatnashchimi(kid, uid) is False:
        return ''
    r = _kk_sheet('konkursChiqdi', id=kid, user_id=uid)
    if r is not None and (not r.get('ok') or not r.get('qatnashchi')):
        return ''
    _kk_chiqqan.add((kid, uid))
    if r is not None and not r.get('yangi'):
        return ''   # avval ogohlantirilgan (bot qayta ishga tushgan bo'lsa ham — jadvalda belgi bor)
    matn, mk = _kk_chiqish_matni(kanal)
    h = _kk_shaxsiy(uid, matn, mk)
    if h != 'yuborildi':
        logger.warning(f'konkurs chiqish ogohlantirishi {uid}: {h}')
    return h


def _kk_start_blok(k):
    """/start dan keyin (aktiv va ochiq konkurs bo'lsa): sovrin, tugash vaqti, «🎁 Qatnashish» tugmasi."""
    prize = html_escape(str(k.get('prize') or ''))
    end = _parse_end_time(k.get('end_time'))
    sovrin = [f"{_kk_medal(i + 1)} {html_escape(p)}" for i, p in enumerate(_kk_sovrinlar(k))]
    q = [f"🎁 <b>Konkurs! / Конкурс!</b>", f"Sovrin / Приз: <b>{prize}</b>"] + sovrin
    if end:
        q.append(f"⏰ Tugaydi / Завершится: {_kk_vaqt(end)} (Toshkent / по Ташкенту)")
    q += ["", "Qatnashish uchun pastdagi tugmani bosing 👇", "Чтобы участвовать — нажмите кнопку ниже 👇"]
    return "\n".join(q), {"inline_keyboard": [[{"text": "🎁 Qatnashish / Участвовать", "callback_data": "kk_qatnash"}]]}


def konkurs_start_xabari(chat_id):
    """Oddiy /start: aktiv va OCHIQ (yashirin emas) konkurs bo'lsa — konkurs bloki. Natija: 'yuborildi' | ''."""
    k = get_konkurs()
    if not _kk_aktivmi(k) or (_kk_yashirinmi(k) and chat_id not in SINOVCHI_IDS):   # BUGUN213 §6b: sinovchi yashirinni ham ko'radi
        return ''
    matn, mk = _kk_start_blok(k)
    return _kk_shaxsiy(chat_id, matn, mk, rasm=(_kk_rasmlar(k)[0][:1] + _kk_rasmlar(k)[1][:1]))


async def _kk_sorov(action, urinish=3, oraliq=5, **params):
    """_kk_sheet — bir necha urinish bilan. None — Apps Script javob bermadi."""
    for n in range(urinish):
        j = await blok(_kk_sheet, action, **params)
        if j is not None:
            return j
        if n + 1 < urinish:
            await asyncio.sleep(oraliq)
    return None


async def _kk_navbat(ol, yoz, yubor):
    """Umumiy navbat (konkurs xabari va tarqatma): ol() → partiya (Apps Script qatorlarni «olindi» qiladi);
    har odamga yubor(x) → natija; yoz(natija) — jadvalga. Holat — jadvalda, shuning uchun to'xtasa davom etadi.
    Qaytaradi (sanoq, sabab): sabab 'tugadi' | 'band' (boshqa nusxa yubormoqda) | 'javobsiz' | Apps Script xatosi."""
    sanoq = {'yuborildi': 0, 'bloklagan': 0, 'xato': 0, 'noaniq': 0}
    kutildi = 0
    while True:
        o = None
        for n in range(5):
            o = await blok(ol)
            if o is not None:
                break
            await asyncio.sleep(5 * (n + 1))
        if o is None:
            return sanoq, 'javobsiz'
        if not o.get('ok'):
            return sanoq, str(o.get('msg') or 'xato')
        if o.get('band'):
            if kutildi >= 1200:
                return sanoq, 'band'
            try:
                kut = min(max(int(o.get('kut_s') or 5), 5), 120)
            except (TypeError, ValueError):
                kut = 30
            kutildi += kut
            await asyncio.sleep(kut)
            continue
        royxat = o.get('royxat') or []
        if o.get('tugadi') or not royxat:
            return sanoq, 'tugadi'
        natija = []
        for x in royxat:
            try:
                h = await blok(yubor, x)
            except Exception as e:   # yuborishdan OLDIN (matn yasashda) — ketmagan
                logger.error(f'konkurs yubor: {type(e).__name__}')
                h = 'xato'
            h = h if h in sanoq else 'noaniq'
            sanoq[h] += 1
            natija.append({'u': str(x.get('user_id', '')), 'h': h})
            await asyncio.sleep(KONKURS_ORALIQ_S)
        for n in range(3):
            if await blok(yoz, natija) is not None:
                break
            await asyncio.sleep(3)


_kk_qulflar = set()   # shu jarayonda hozir ishlanayotgan konkurs id / 'T:'+kampaniya — ikkinchi chaqiruv 'band'


async def konkurs_tugat_va_yetkaz(kid, tugat=True, sabab='', manba='taymer', joy=None):
    """Konkursni tugatadi (tugat=True va hali aktiv bo'lsa) va navbatda qolgan xabarlarni yetkazadi.
    Istalgan joydan, istalgancha chaqirish XAVFSIZ: tanlov Apps Script'da bir marta (idempotent), xabar — navbat
    bo'yicha har odamga bir marta. manba: taymer | tiklash | sayt | buyruq."""
    kid = str(kid or '').strip()
    if not kid:
        return 'id'
    if kid in _kk_qulflar:
        return 'band'
    _kk_qulflar.add(kid)
    try:
        return await _kk_ish(kid, tugat, sabab, manba, joy)
    except Exception as e:
        logger.error(f'konkurs {kid}: {type(e).__name__}')
        await _kk_admin(f"⚠️ Konkurs <b>{html_escape(kid)}</b>: kutilmagan xato ({type(e).__name__}).\n"
                        f"Holat: /konkursholat {html_escape(kid)}", joy)
        return 'xato'
    finally:
        _kk_qulflar.discard(kid)


async def _kk_ish(kid, tugat, sabab, manba, joy):
    ek = html_escape(kid)
    # 1) Holat — jadvaldan. Apps Script javob bermasa yoki ESKI versiya bo'lsa — hech narsa qilinmaydi (yopiq holat).
    h = await _kk_sorov('konkursHolat', id=kid)
    if h is None:
        await _kk_admin(f"⚠️ Konkurs <b>{ek}</b>: Apps Script javob bermadi yoki eski versiya — hech narsa qilinmadi "
                        f"(g'olib tanlanmadi, xabar ketmadi).\nTekshirib, qayta: /konkurstugat {ek}", joy)
        return 'javobsiz'
    if not h.get('ok'):
        if manba != 'sayt':   # saytdan kelgan noma'lum id — jim (ochiq manzil, admin bezovta qilinmaydi)
            await _kk_admin(f"⚠️ Konkurs <b>{ek}</b>: {html_escape(h.get('msg', ''))} — hech narsa qilinmadi.", joy)
        return str(h.get('msg') or 'xato')
    st = str(h.get('status', ''))
    if st == 'active':
        if not tugat:
            return 'aktiv'   # /notify, tiklash — aktiv konkursni TUGATMAYDI
        end = _parse_end_time(h.get('end_time'))
        if manba == 'taymer' and end and end > time.time() + 5:   # vaqt surilgan — taymer qayta
            konkurs_taymer_qoy({'id': kid, 'status': 'active', 'end_time': h.get('end_time')})
            return 'erta'
    elif st == 'ended':
        y = str(h.get('yetkazish') or '').split('|')[0]
        if not tugat and manba != 'buyruq' and y in ('', 'tugadi', 'yoq') and h.get('kanal_post') != 'navbatda' \
                and str(h.get('obuna') or '').split('|')[0] != 'navbatda':
            return 'tugadi'   # yetkazadigan narsa yo'q
    else:
        if manba == 'buyruq':
            await _kk_admin(f"Konkurs <b>{ek}</b> holati: {html_escape(st or '—')} — hech narsa qilinmadi.", joy)
        return st or 'holat'

    # 2) Tugatish (idempotent: tugagan bo'lsa — saqlangan g'oliblar, qayta tanlanmaydi)
    # BUGUN147: obuna=1 — g'oliblar obunasi tekshirilguncha jadval xabar navbati va kanal postini YOPIQ tutadi
    e = await _kk_sorov('endKonkurs', timeout=60, id=kid, obuna='1')
    if e is None or not e.get('ok'):
        sabab_x = html_escape((e or {}).get('msg') or 'Apps Script javob bermadi')
        await _kk_admin(f"⚠️ Konkurs <b>{ek}</b>: tugatib bo'lmadi ({sabab_x}). Qayta: /konkurstugat {ek}", joy)
        return 'tugatilmadi'
    winners = e.get('winners') or []
    prize = str(e.get('prize') or '')
    # 2b) BUGUN147: g'oliblar kanalga obunami — obuna emas → qayta tanlash (kanal postidan OLDIN)
    obuna_izoh = []
    if str(e.get('obuna') or '').split('|')[0] == 'navbatda':
        t = await _kk_obuna_tekshir(kid, e, joy)
        if t is None:
            return 'obuna'
        winners, obuna_izoh = t
        if obuna_izoh:
            await _kk_admin(f"🔎 <b>Konkurs {ek} — g'oliblar obunasi</b> ({html_escape(_kk_kanal(e))})\n"
                            + "\n".join(obuna_izoh), joy)
    win_text = _kk_goliblar_matni(winners)
    if not e.get('already'):
        # BUGUN125: g'olib bir qurilmadan boshqa akkaunt bilan kirgan bo'lsa — faqat adminga ⚠️ (kanalga emas)
        ogoh = [f"⚠️ {_kk_medal(int(w.get('place') or 1))} {html_escape(str(w.get('ogohlantirish')))}"
                for w in winners if w.get('ogohlantirish')]
        ogoh_t = ("\n\n" + "\n".join(ogoh) + "\n(qayta tanlash — saytda «🎲 Qayta»)") if ogoh else ''
        await _kk_admin(f"🏁 <b>Konkurs tugadi</b> ({html_escape(sabab or manba)})\n🎁 {html_escape(prize)}\n"
                        f"👥 Qatnashchi: {e.get('total', 0)}\n🏆 G'oliblar:\n{win_text}{ogoh_t}\n\n📨 Xabarlar yuborilmoqda…",
                        joy)

    # 3) Shaxsiy xabarlar — navbatdan (har odamga bir marta)
    fids, urls = _kk_rasmlar(e)
    bir_rasm = fids[:1] + urls[:1]

    def yubor(x):
        try:
            place = int(x.get('place') or 0)
        except (TypeError, ValueError):
            place = 0
        if place > 0:
            cap, mk = _kk_golib_xabari(place, x.get('prize') or prize)
        elif x.get('obunasiz'):   # BUGUN147: g'olib edi, kanalga obuna emas — sovg'a berilmaydi
            cap, mk = _kk_obunasiz_xabari(prize)
        else:
            cap, mk = _kk_maglub_xabari(prize, win_text)
        return _kk_shaxsiy(x.get('user_id'), cap, mk, rasm=bir_rasm)

    sanoq, holat = await _kk_navbat(
        lambda: _kk_sheet('konkursXabarOl', id=kid, worker=KONKURS_WORKER, n=KONKURS_PARTIYA),
        lambda natija: _kk_sheet('konkursXabarNatija', id=kid, worker=KONKURS_WORKER, natija=json.dumps(natija)),
        yubor)

    # 4) Kanal posti — bir marta (kanal_post: navbatda → olindi → natija)
    kanal = None
    ko = await _kk_sorov('konkursKanalOl', id=kid, worker=KONKURS_WORKER)
    if ko and ko.get('ok') and ko.get('ol'):
        matn, mk = _kk_kanal_xabari(prize, win_text)
        kanal = await blok(_kk_kanal_post, matn, [fids, urls], mk, TEST_CHANNEL if _kk_sinovmi(prize) else None)
        for n in range(3):
            if await blok(_kk_sheet, 'konkursXabarNatija', id=kid, worker=KONKURS_WORKER, natija='[]',
                          kanal=kanal) is not None:
                break
            await asyncio.sleep(3)

    # 5) Hisobot — jadvaldagi sanoq bo'yicha
    if sum(sanoq.values()) or kanal or manba == 'buyruq' or holat != 'tugadi':
        hh = await _kk_sorov('konkursHolat', urinish=2, id=kid) or {}
        x = hh.get('xabar') or {}
        kp = kanal or str(hh.get('kanal_post') or '—').split('|')[0]
        q = [f"📨 <b>Konkurs {ek} — xabarlar</b>",
             f"✅ Yuborildi: {x.get('yuborildi', sanoq['yuborildi'])}",
             f"🚫 Bloklagan: {x.get('bloklagan', sanoq['bloklagan'])}",
             f"❌ Xato: {x.get('xato', sanoq['xato'])}",
             f"❔ Noaniq: {x.get('noaniq', sanoq['noaniq'])}",
             f"⏳ Kutmoqda: {x.get('kutmoqda', 0)} · olingan, javobsiz: {x.get('olindi', 0)}",
             f"📢 Kanal: {html_escape(kp)}"]
        if holat == 'obuna':
            q.append(f"⚠️ Xabarlar obuna tekshiruvini kutmoqda. Davom: /konkursdavom {ek}")
        elif holat != 'tugadi':
            q.append(f"⚠️ To'xtadi: {html_escape(holat)}. Davom: /konkursdavom {ek}")
        if x.get('xato'):
            q.append(f"Xatolarni qayta: /konkursdavom {ek}")
        if (x.get('noaniq') or 0) + (x.get('olindi') or 0):
            q.append(f"Noaniqlarni ham (ba'zilariga 2-marta borishi mumkin): /konkursdavom {ek} noaniq")
        await _kk_admin("\n".join(q), joy)
    return holat


# ── Taymer — faqat «vaqt keldi» signali. Tugatishda baribir jadvaldagi holat tekshiriladi.
_kk_taymer_holat = {'task': None, 'id': None, 'end': None}
_kk_ogohlantirilgan = set()   # kechikkan konkurs haqida admin bir marta ogohlantiriladi


def konkurs_taymer_qoy(k):
    """Aktiv konkursga taymer (event loop ichidan chaqiriladi). Qaytaradi:
    'qoyildi' | 'bor' | 'muddatsiz' | 'kechikdi' (6 soatdan ko'p o'tgan — adminga xabar) | 'aktiv_emas'."""
    if not k or str(k.get('status', '')).lower() != 'active':
        return 'aktiv_emas'
    kid = str(k.get('id') or k.get('konkurs_id') or '')
    if not kid:
        return 'aktiv_emas'
    end = _parse_end_time(k.get('end_time'))
    if not end:
        return 'muddatsiz'
    now = time.time()
    if end < now - KONKURS_KECHIKISH_S:
        if kid not in _kk_ogohlantirilgan:
            _kk_ogohlantirilgan.add(kid)
            ek = html_escape(kid)
            asyncio.create_task(_kk_admin(
                f"⚠️ Konkurs <b>{ek}</b> tugash vaqti ({_kk_vaqt(end)}) {int((now - end) // 3600)} soat oldin o'tgan — "
                f"bot o'chiq edi. O'zim tugatmadim: g'olib tanlanmadi, xabar ketmadi.\n"
                f"Tugatish (g'olib + xabarlar): /konkurstugat {ek}\nBekor qilish: /konkursbekor {ek}"))
        return 'kechikdi'
    t = _kk_taymer_holat
    if t['id'] == kid and t['end'] == end and t['task'] and not t['task'].done():
        return 'bor'
    if t['task'] and not t['task'].done():
        t['task'].cancel()
    t.update(task=asyncio.create_task(_kk_taymer(kid, max(0, end - now))), id=kid, end=end)
    logger.info(f'Konkurs {kid} taymeri: {int(end - now)}s')
    return 'qoyildi'


async def _kk_taymer(kid, kut):
    try:
        await asyncio.sleep(kut)
    except asyncio.CancelledError:
        return
    if _kk_taymer_holat['id'] == kid:
        _kk_taymer_holat.update(task=None, id=None, end=None)
    # alohida vazifa — keyin taymer bekor qilinsa ham yetkazish uzilmaydi
    asyncio.create_task(konkurs_tugat_va_yetkaz(kid, True, 'tugash vaqti keldi', 'taymer'))


async def konkurs_tiklash():
    """Bot ishga tushganda: aktiv konkursga taymer; tugagan, lekin xabari to'liq yetmagan konkurslar — davom
    (jadvaldagi navbatdan; allaqachon olinganlar qayta yuborilmaydi)."""
    try:
        _konkurs_cache['data'] = None
        _konkurs_cache['time'] = 0
        k = await blok(get_konkurs)
        if k:
            konkurs_taymer_qoy(k)
        r = await _kk_sorov('konkursYetkazishKerak')
        if r is None:
            logger.warning('konkurs tiklash: Apps Script javob bermadi (eski versiya yoki tarmoq)')
            return
        if not r.get('ok'):
            await _kk_admin("⚠️ Konkurs tiklash: Apps Script kalitni qabul qilmadi — Render API_KEY va "
                            "Script Properties API_KEY bir xilmi?")
            return
        for x in r.get('royxat') or []:
            if x.get('id'):
                asyncio.create_task(konkurs_tugat_va_yetkaz(x['id'], tugat=False, sabab='bot qayta ishga tushdi',
                                                            manba='tiklash'))
    except Exception as e:
        logger.error(f'konkurs tiklash: {type(e).__name__}')


_korilgan_update = {}


def _update_yangimi(update_id):
    """Telegram javobni kech olsa shu update'ni QAYTA yuboradi — ikkinchisi tashlanadi (QOIDALAR T1, T2)."""
    if update_id is None:
        return True
    if update_id in _korilgan_update:
        return False
    _korilgan_update[update_id] = 1
    if len(_korilgan_update) > 2000:
        for u in list(_korilgan_update)[:500]:
            del _korilgan_update[u]
    return True


def _kk_kampaniya(s):
    return re.sub(r'[^A-Za-z0-9_-]', '', str(s or ''))[:60]


async def konkurs_tarqat(k, kampaniya, ids, joy, yangibot=False):
    """Konkurs e'loni — ESKI bot orqali Mijozlar'ga (navbat bilan; qayta chaqirilsa — qolganidan davom, takror yo'q).
    yangibot (BUGUN184): yangi botga /start bosgan, konkursda qatnashmaganlarga — YANGI bot orqali (v169 matni)."""
    fids, urls = _kk_rasmlar(k)   # file_id — yangi botniki: eski bot yubora olmaydi (faqat url), yangi bot — ikkalasini
    if yangibot:
        matnlar = {'uz': _kk_yangibot_xabari(k, 'uz'), 'ru': _kk_yangibot_xabari(k, 'ru')}
        rasm = fids[:1] + urls[:1]
    else:
        matnlar = {'uz': _kk_tarqatma_xabari(k, 'uz'), 'ru': _kk_tarqatma_xabari(k, 'ru')}
        rasm = urls[:1]

    def yubor(x):
        matn, mk = matnlar.get(x.get('til'), matnlar['uz'])
        return _kk_shaxsiy(x.get('user_id'), matn, mk, rasm=rasm, token=None if yangibot else ESKI_BOT_TOKEN)

    # BUGUN173: 7:30 «hammaga» — yangi botga o'tganlar va shu konkursda qatnashganlar chetda (Apps Script tarqatmaTayyorla);
    # BUGUN184: «yangibot» — aksincha: faqat yangi botga o'tgan, lekin qatnashmaganlar
    return await _kk_tarqat(kampaniya, ids, joy, yubor, konkurs=None if ids else k.get('id'),
                            rejim='yangibot' if yangibot and not ids else None)


async def _kk_tarqat(kampaniya, ids, joy, yubor, konkurs=None, rejim=None):
    """Tarqatma navbati (konkurs e'loni, rebrending): Mijozlar → «tarqatma» varag'i (bir kishiga bir marta), partiya bilan
    yubor(x) → hisobot adminga. ids — faqat shu user_id'lar (sinov); None — botga yozgani ma'lum hamma (BUGUN185:
    Mijozlar + KonkursQatnashchilari, Istaklar, Korishlar, Qidiruvlar — takrorsiz).
    konkurs — faqat konkurs e'loni «hammaga» uchun (rebrending va sinov — None, filtr yo'q).
    rejim — 'yangibot' (BUGUN184): konkurs bilan birga; aks holda — oddiy «hammaga» filtri."""
    kampaniya = _kk_kampaniya(kampaniya)
    qulf = 'T:' + kampaniya
    if qulf in _kk_qulflar:
        await _kk_admin("⏳ Bu tarqatma hozir ketyapti.", joy)
        return 'band'
    _kk_qulflar.add(qulf)
    try:
        if konkurs:
            # BUGUN184: eski Apps Script «konkurs» / «rejim» parametrini bilmaydi — HAMMAGA, filtrsiz tayyorlab qo'yardi
            # (va «tarqatma» varag'ida shu nom bilan qolardi). Yozishdan oldin (faqat o'qiydi) versiyani tekshiramiz.
            h = await _kk_sorov('tarqatmaHolat', urinish=2, kampaniya=kampaniya)
            kerak = rejim or 'konkurs'
            if h is None or kerak not in (h.get('rejimlar') or []):
                sabab = 'Apps Script javob bermadi' if h is None else "Apps Script eski versiya (deploy.js kerak)"
                await _kk_admin(f"❌ Tarqatma boshlanmadi: {sabab}. Hech kimga yuborilmadi.", joy)
                return 'xato'
        t = await _kk_sorov('tarqatmaTayyorla', urinish=2, kampaniya=kampaniya,
                            ids=json.dumps([str(i) for i in ids]) if ids else None,
                            konkurs=str(konkurs) if konkurs else None, rejim=rejim)
        if t is None or not t.get('ok'):
            await _kk_admin(f"❌ Tarqatma tayyorlanmadi: {html_escape((t or {}).get('msg') or 'Apps Script javob bermadi')}",
                            joy)
            return 'xato'
        chetda = f" · chetda: {t['chetda']}" if t.get('chetda') else ''
        # BUGUN185: «hammaga» — Mijozlar + boshqa varaqlardagi user_id (takrorsiz); har varaqdan nechta — faqat son
        manba = ''
        if isinstance(t.get('manbalar'), dict):
            manba = "\nManbalar (bir odam bir nechtasida bo'lishi mumkin): " + " · ".join(
                f"{html_escape(str(k))} {html_escape(str(v))}" for k, v in t['manbalar'].items())
        elif not ids and not t.get('already'):
            manba = "\n⚠️ Apps Script eski versiya — faqat Mijozlar varag'idan (deploy.js kerak)."
        await _kk_admin(f"📣 Tarqatma <b>{kampaniya}</b>: {t.get('soni', 0)} kishi{chetda}"
                        f"{' (davomi)' if t.get('already') else ''} — yuborilmoqda…{manba}", joy)
        sanoq, holat = await _kk_navbat(
            lambda: _kk_sheet('tarqatmaOl', kampaniya=kampaniya, worker=KONKURS_WORKER, n=KONKURS_PARTIYA),
            lambda natija: _kk_sheet('tarqatmaNatija', kampaniya=kampaniya, worker=KONKURS_WORKER,
                                     natija=json.dumps(natija)),
            yubor)
        hh = await _kk_sorov('tarqatmaHolat', urinish=2, kampaniya=kampaniya) or {}
        x = hh.get('holat') or {}
        q = [f"📣 <b>Tarqatma {kampaniya}</b>",
             f"✅ Yuborildi: {x.get('yuborildi', sanoq['yuborildi'])}",
             f"🚫 Bloklagan: {x.get('bloklagan', sanoq['bloklagan'])}",
             f"❌ Xato: {x.get('xato', sanoq['xato'])} · ❔ Noaniq: {x.get('noaniq', sanoq['noaniq'])}",
             f"⏳ Kutmoqda: {x.get('kutmoqda', 0)} · olingan, javobsiz: {x.get('olindi', 0)}"]
        if holat != 'tugadi':
            q.append(f"⚠️ To'xtadi: {html_escape(holat)} — shu buyruqni qayta yuborsangiz, qolganidan davom etadi.")
        await _kk_admin("\n".join(q), joy)
        return holat
    finally:
        _kk_qulflar.discard(qulf)


async def konkurs_tarqat_test_kanal(k, joy):
    """BUGUN125: sinov tarqatma — uz va ru matn TEST kanalga (yangi bot), mijozlar o'rniga. Rasm — mijozga
    boradigani bilan bir xil (1-url), tugma — avtomatik. Admin — natijani ko'radi."""
    if not TEST_CHANNEL:
        await _kk_admin("⚠️ TEST kanal sozlanmagan (TEST_CHANNEL_ID) — faqat sizga keladi.", joy)
        return
    _, urls = _kk_rasmlar(k)
    holat = []
    for til in ('uz', 'ru'):
        matn, mk = _kk_tarqatma_xabari(k, til)
        h = await blok(_kk_kanal_post, matn, [[], urls[:1]], mk, TEST_CHANNEL)
        holat.append(f"{til}: {'✅' if h == 'yuborildi' else '❌ ' + html_escape(str(h))}")
    await _kk_admin(f"🧪 TEST kanal ({html_escape(TEST_CHANNEL)}) — {' · '.join(holat)}", joy)


_KK_BUYRUQLAR = ('/konkursholat', '/konkurstugat', '/konkursbekor', '/konkursdavom', '/tarqatma',
                 '/konkursochiq', '/konkursyashir')


async def konkurs_buyruq(chat_id, text):
    """Admin buyruqlari (fonda):
      /konkursholat [id] · /konkurstugat <id> [hozir] · /konkursbekor <id> · /konkursdavom <id> [noaniq]
      /tarqatma <id> sinov (TEST kanal + admin) · /tarqatma <id> hammaga (eski bot, yangi botga o'tmaganlarga)
      /tarqatma <id> yangibot (yangi bot: o'tgan, lekin qatnashmaganlarga) · /tarqatma <id> yangibotsinov (faqat adminga)
      /konkursochiq — konkurs oynasini hammaga ochadi · /konkursyashir — yana yashiradi"""
    q = text.split()
    b = q[0].split('@')[0]
    kid = q[1] if len(q) > 1 else ''
    ek = html_escape(kid)
    logger.info(f'konkurs buyruq: {b} {kid}')
    try:
        if b in ('/konkursochiq', '/konkursyashir'):
            # BUGUN147: yashirin oyna (Script Property KONKURS_YASHIRIN) — sayt banneri, Profil, /start bloki
            r = await _kk_sorov('konkursYashirin', urinish=2, holat='0' if b == '/konkursochiq' else '1')
            if r is None or not r.get('ok'):
                await _kk_admin(f"❌ {html_escape((r or {}).get('msg') or 'Apps Script javob bermadi')}", chat_id)
                return
            _konkurs_cache['data'] = None
            _konkurs_cache['time'] = 0
            if r.get('yashirin'):
                await _kk_admin("🙈 Konkurs oynasi <b>yashirin</b>: begona ko'rmaydi (saytda banner, Profil, "
                                "/start xabari yo'q). Siz — ko'rasiz; saytda logoni 3 marta bossa — ochiladi.\n"
                                "Hammaga ochish: /konkursochiq", chat_id)
            else:
                await _kk_admin("🔓 Konkurs oynasi <b>hammaga ochiq</b>: saytda banner va Profil'da 🎁, /start da "
                                "konkurs xabari.\nSaytda 2 daqiqagacha eski holat turishi mumkin.\n"
                                "Yana yashirish: /konkursyashir", chat_id)
            return

        if b == '/konkursholat':
            if not kid:
                _konkurs_cache['data'] = None
                _konkurs_cache['time'] = 0
                kid = str((await blok(get_konkurs) or {}).get('id') or '')
                ek = html_escape(kid)
            if not kid:
                # BUGUN137: xato emas — konkurs hali ochilmagan (ilgari «Konkurs topilmadi» xatoga o'xshardi)
                await _kk_admin("Hozir ochiq konkurs yo'q.\n"
                                "Yangi konkurs — /konkurs yozing va sovrin rasmini yuboring (keyin Admin panelda "
                                "to'ldirasiz).\nEski konkurs holati — /konkursholat &lt;id&gt;", chat_id)
                return
            h = await _kk_sorov('konkursHolat', urinish=2, id=kid)
            if h is None or not h.get('ok'):
                await _kk_admin(f"⚠️ {ek}: {html_escape((h or {}).get('msg') or 'Apps Script javob bermadi (eski versiyami?)')}",
                                chat_id)
                return
            x = h.get('xabar') or {}
            end = _parse_end_time(h.get('end_time'))
            t = _kk_taymer_holat
            taymer = (f"qo'yilgan — {_kk_vaqt(t['end'])}" if t['id'] == kid and t['task'] and not t['task'].done()
                      else "yo'q")
            await _kk_admin("\n".join([
                f"📊 <b>Konkurs {ek}</b>",
                f"Holat: <b>{html_escape(h.get('status') or '—')}</b>",
                f"🎁 {html_escape(h.get('prize') or '')}",
                f"⏰ Tugash: {_kk_vaqt(end) if end else '—'} (Toshkent)",
                f"👥 Qatnashchi: {h.get('count', 0)}",
                f"📨 Xabar: jami {x.get('jami', 0)} · ✅ {x.get('yuborildi', 0)} · 🚫 {x.get('bloklagan', 0)} · "
                f"❌ {x.get('xato', 0)} · ❔ {x.get('noaniq', 0)} · ⏳ {x.get('kutmoqda', 0)} · olingan {x.get('olindi', 0)}",
                f"📦 Yetkazish: {html_escape(str(h.get('yetkazish') or '—').split('|')[0])}",
                f"📢 Kanal: {html_escape(str(h.get('kanal_post') or '—').split('|')[0])}",
                f"🔎 G'oliblar obunasi: {html_escape(str(h.get('obuna') or '—').split('|')[0])} · "
                f"obunasiz: {h.get('obunasiz', 0)} · kanaldan chiqqan: {h.get('chiqdi', 0)}",
                f"🙈 Oyna: {'yashirin (/konkursochiq)' if h.get('yashirin', True) else 'hammaga ochiq (/konkursyashir)'}",
                f"⏱ Taymer: {taymer}"]), chat_id)
            return

        if not kid:
            await _kk_admin(html_escape(konkurs_buyruq.__doc__.split(':', 1)[1].strip()), chat_id)
            return

        if b == '/konkurstugat':
            h = await _kk_sorov('konkursHolat', urinish=2, id=kid)
            if h and h.get('ok') and h.get('status') == 'active':
                end = _parse_end_time(h.get('end_time'))
                if end and end > time.time() and (len(q) < 3 or q[2] != 'hozir'):
                    await _kk_admin(f"Konkurs {ek} hali tugamagan (tugash: {_kk_vaqt(end)}).\n"
                                    f"Hozir tugatish (g'olib tanlanadi, hammaga xabar ketadi): /konkurstugat {ek} hozir",
                                    chat_id)
                    return
            r = await konkurs_tugat_va_yetkaz(kid, True, "admin buyrug'i", 'buyruq', chat_id)
            if r == 'band':
                await _kk_admin(f"⏳ Konkurs {ek} hozir ishlanmoqda — tugagach hisobot keladi.", chat_id)
            return

        if b == '/konkursbekor':
            r = await _kk_sorov('bekorKonkurs', urinish=2, id=kid)
            if r is None or not r.get('ok'):
                await _kk_admin(f"❌ Bekor qilinmadi: {html_escape((r or {}).get('msg') or 'Apps Script javob bermadi')}"
                                f"{' (tugagan konkurs bekor qilinmaydi)' if (r or {}).get('status') == 'ended' else ''}",
                                chat_id)
                return
            t = _kk_taymer_holat
            if t['id'] == kid:
                if t['task'] and not t['task'].done():
                    t['task'].cancel()
                t.update(task=None, id=None, end=None)
            _konkurs_cache['data'] = None
            _konkurs_cache['time'] = 0
            await _kk_admin(f"🚫 Konkurs {ek} bekor qilindi — g'olib tanlanmaydi, hech kimga xabar ketmaydi.", chat_id)
            return

        if b == '/konkursdavom':
            noaniq = len(q) > 2 and q[2] == 'noaniq'
            r = await _kk_sorov('konkursNoaniqOch', urinish=2, id=kid, noaniq='1' if noaniq else None)
            if r is None or not r.get('ok'):
                if (r or {}).get('msg') == 'band':
                    await _kk_admin(f"⏳ Bot hozir yubormoqda — {r.get('kut_s', '?')} s dan keyin qayta urinib ko'ring.",
                                    chat_id)
                else:
                    await _kk_admin(f"❌ {html_escape((r or {}).get('msg') or 'Apps Script javob bermadi')}", chat_id)
                return
            await _kk_admin(f"🔁 Qayta navbatga: {r.get('ochildi', 0)} kishi{', kanal posti' if r.get('kanal') else ''}.",
                            chat_id)
            if await konkurs_tugat_va_yetkaz(kid, False, 'admin: davom', 'buyruq', chat_id) == 'band':
                await _kk_admin(f"⏳ Konkurs {ek} hozir ishlanmoqda — tugagach hisobot keladi.", chat_id)
            return

        if b == '/tarqatma':
            tur = q[2] if len(q) > 2 else ''
            if tur not in ('sinov', 'hammaga', 'yangibot', 'yangibotsinov'):
                await _kk_admin("/tarqatma &lt;id&gt; sinov — TEST kanalga va sizga (mijozlarga emas)\n"
                                "/tarqatma &lt;id&gt; hammaga — eski bot: yangi botga o'tmaganlarga (bir marta)\n"
                                "/tarqatma &lt;id&gt; yangibot — yangi bot: botga o'tgan, lekin qatnashmaganlarga (bir marta)\n"
                                "/tarqatma &lt;id&gt; yangibotsinov — yangi bot matni faqat sizga", chat_id)
                return
            if tur in ('sinov', 'hammaga') and not ESKI_BOT_TOKEN:
                await _kk_admin("❌ ESKI_BOT_TOKEN qo'yilmagan (Render env) — tarqatma eski bot orqali ketadi.", chat_id)
                return
            _konkurs_cache['data'] = None
            _konkurs_cache['time'] = 0
            k = await blok(get_konkurs)
            if not k or str(k.get('id')) != kid or not _kk_aktivmi(k):
                await _kk_admin(f"❌ Konkurs {ek} aktiv emas — tarqatma faqat ochiq konkursga.", chat_id)
                return
            if tur in ('hammaga', 'yangibot') and _kk_sinovmi(k.get('prize')):
                await _kk_admin(f"❌ {ek} — sinov konkursi (nomi TEST bilan): «{tur}» yuborilmaydi. "
                                f"Faqat: /tarqatma {ek} {'sinov' if tur == 'hammaga' else 'yangibotsinov'}", chat_id)
                return
            if tur in ('hammaga', 'yangibot') and _kk_yashirinmi(k):
                # BUGUN147: yashirin konkurs e'loni mijozlarga ketsa — tugma bosgan odam konkursni ko'rmaydi
                await _kk_admin(f"❌ Konkurs oynasi yashirin — «{tur}» yuborilmaydi.\n"
                                f"Avval oching: /konkursochiq, keyin: /tarqatma {ek} {tur}", chat_id)
                return
            yangibot = tur in ('yangibot', 'yangibotsinov')
            if tur == 'sinov':
                # BUGUN125 (v90-1): sinov — TEST kanal + admin; mijoz user_id'lari qabul qilinmaydi (adashib ketmasin)
                await konkurs_tarqat_test_kanal(k, chat_id)
                ids = [str(ADMIN_ID)]
                kampaniya = f'{kid}-sinov{int(time.time())}'
            elif tur == 'yangibotsinov':
                # BUGUN184: yangi bot matni — faqat adminga (yangi bot orqali; admin unga /start bosgan)
                ids = [str(ADMIN_ID)]
                kampaniya = f'{kid}-yangibotsinov{int(time.time())}'
            elif tur == 'yangibot':
                ids, kampaniya = None, f'{kid}-yangibot'
            else:
                ids, kampaniya = None, f'{kid}-hammaga'
            await konkurs_tarqat(k, kampaniya, ids, chat_id, yangibot=yangibot)
    except Exception as e:
        logger.error(f'konkurs buyruq {b}: {type(e).__name__}')
        await _kk_admin(f"⚠️ {html_escape(b)}: kutilmagan xato ({type(e).__name__})", chat_id)


# ── BUGUN137: rebrending xabari — ESKI bot nomidan (mijozlar yangi botga hali yozmagan, faqat eski bot yoza oladi) ──
# Matn — foydalanuvchiniki, HARFMA-HARF (BOSHQARUV/BER-2026-10-12-javoblar.md «Ilova»; testda solishtiriladi) — tuzatilmaydi.
# Qalin va premium 👀 — entities bilan (parse_mode yo'q). Premium emoji Bot API orqali o'tadi (sinov 2026-10-12, (a) usul).
REBREND_MATN = (
    "👀Kraken Mobile endi — Nuqta tech!\n\n"
    "📱Smartfonlarni ko’rish uchun yangi botimizga o’ting.\n"
    "🎁 Shuningdek, saytimizda konkurs boshlandi! Ishtirok eting va sovg’alarni yutib oling.\n\n"
    "🇷🇺 Kraken Mobile теперь — Nuqta Tech.\n\n"
    "📱 Чтобы посмотреть смартфоны, переходите в наш новый бот \n"
    "🎁 А ещё на нашем сайте стартовал конкурс! Участвуйте и выигрывайте призы."
)
REBREND_EMOJI_ID = '5210956306952758910'   # 👀 premium (foydalanuvchi bergan)
REBREND_RASM = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rebrending.png')


def _rebrend_entities():
    def ent(tur, qism, **q):
        i = REBREND_MATN.index(qism)
        return dict(type=tur, offset=_utf16len(REBREND_MATN[:i]), length=_utf16len(qism), **q)
    return [ent('custom_emoji', '👀', custom_emoji_id=REBREND_EMOJI_ID),
            ent('bold', 'Kraken Mobile endi — Nuqta tech!'),
            ent('bold', 'Kraken Mobile теперь — Nuqta Tech.')]


REBREND_ENT = _rebrend_entities()
REBREND_KB = {"inline_keyboard": [[{"text": "📱 Yangi botga o'tish", "url": f"https://t.me/{BOT_USERNAME}"}]]}
_rebrend = {'bayt': None, 'fid': {}}   # rasm baytlari (bir marta o'qiladi) · token → file_id (bir marta yuklanadi)


def _rebrend_yubor(chat_id, token):
    """Bir odamga rebrending xabari: rasm + matn + tugma. Natija — _kk_tg kabi. Rasm birinchi marta fayl bilan
    yuklanadi, keyin file_id bilan; rasm o'tmasa ('xato') — faqat matn ('noaniq' da ikkinchi xabar yo'q)."""
    asos = {'chat_id': chat_id, 'caption': REBREND_MATN, 'caption_entities': REBREND_ENT, 'reply_markup': REBREND_KB}
    fid = _rebrend['fid'].get(token)
    if fid:
        h, _ = _kk_tg('sendPhoto', dict(asos, photo=fid), token=token)
    else:
        if _rebrend['bayt'] is None:
            try:
                with open(REBREND_RASM, 'rb') as f:
                    _rebrend['bayt'] = f.read()
            except OSError:
                _rebrend['bayt'] = b''
        h = 'xato'
        if _rebrend['bayt']:
            h, j = _kk_tg('sendPhoto', asos, token=token, timeout=60,
                          files={'photo': ('rebrending.png', _rebrend['bayt'], 'image/png')})
            rasm = ((j or {}).get('result') or {}).get('photo') or []
            if h == 'yuborildi' and rasm:
                _rebrend['fid'][token] = rasm[-1].get('file_id')
    if h != 'xato':
        return h
    h, _ = _kk_tg('sendMessage', {'chat_id': chat_id, 'text': REBREND_MATN, 'entities': REBREND_ENT,
                                  'reply_markup': REBREND_KB}, token=token)
    return h


_REBREND_BUYRUQLAR = ('/forwardxabari', '/rebrending')


async def rebrend_buyruq(chat_id, text):
    """Admin buyruqlari (fonda) — rebrending xabari eski bot nomidan:
      /forwardxabari — faqat sizning lichkangizga (ko'rib chiqish uchun)
      /rebrending sinov — navbat orqali, faqat sizga (mijozlarga emas)
      /rebrending hammaga — botga yozgani ma'lum hammaga (Mijozlar + boshqa varaqlar), har kishiga bir marta"""
    q = text.split()
    b = q[0].split('@')[0]
    try:
        if not ESKI_BOT_TOKEN:
            await _kk_admin("❌ ESKI_BOT_TOKEN qo'yilmagan (Render env) — rebrending xabari eski bot orqali ketadi.",
                            chat_id)
            return
        if b == '/forwardxabari':
            h = await blok(_rebrend_yubor, ADMIN_ID, ESKI_BOT_TOKEN)
            if h == 'yuborildi':
                await _kk_admin(f"✅ Rebrending xabari @{ESKI_BOT_USERNAME} nomidan lichkangizga keldi — ko'ring.\n"
                                f"Mijozlarga (hammaga): /rebrending hammaga", chat_id)
            elif h == 'bloklagan':
                await _kk_admin(f"Avval @{ESKI_BOT_USERNAME} ga /start bosing", chat_id)
            else:
                await _kk_admin(f"❌ Yuborilmadi ({html_escape(h)}) — birozdan keyin qayta /forwardxabari", chat_id)
            return
        tur = q[1] if len(q) > 1 else ''
        if tur == 'sinov':
            # mijoz user_id'lari qabul qilinmaydi — sinov faqat adminga (adashib ketmasin)
            ids, kampaniya = [str(ADMIN_ID)], f'rebrending-sinov{int(time.time())}'
        elif tur == 'hammaga':
            ids, kampaniya = None, 'rebrending-hammaga'
        else:
            await _kk_admin(html_escape(rebrend_buyruq.__doc__.split(':', 1)[1].strip()), chat_id)
            return
        await _kk_tarqat(kampaniya, ids, chat_id, lambda x: _rebrend_yubor(x.get('user_id'), ESKI_BOT_TOKEN))
    except Exception as e:
        logger.error(f'rebrend buyruq {b}: {type(e).__name__}')
        await _kk_admin(f"⚠️ {html_escape(b)}: kutilmagan xato ({type(e).__name__})", chat_id)


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


def azo_kanal_tugmalari(yetishmagan=None):
    """BUGUN204: «a'zo emas» xabarlarida FAQAT a'zo bo'lmagan kanal(lar) — tartib: 1) asosiy (Nuqta tech), 2) Nuqta tech · Mobile.
    yetishmagan — ['tech', 'mobile'] dan (None — ikkalasi). Asosiy kanal manzili: env TECH_KANAL_ID @username bo'lsa — o'sha,
    aks holda (bo'sh yoki -100…) @nuqta_tech."""
    yetishmagan = ['tech', 'mobile'] if yetishmagan is None else yetishmagan
    tech = TECH_KANAL.lstrip('@') if TECH_KANAL.startswith('@') else 'nuqta_tech'
    q = []
    if 'tech' in yetishmagan:
        q.append([{"text": f"📢 {BREND}", "url": f"https://t.me/{tech}"}])
    if 'mobile' in yetishmagan:
        q.append([{"text": f"📢 {YON_KANAL['mobile'][0]}", "url": CHANNEL_LINK}])
    return q

def not_member_msg(chat_id, yetishmagan=None):
    yetishmagan = ['tech', 'mobile'] if yetishmagan is None else yetishmagan
    nomlar = [BREND if k == 'tech' else YON_KANAL['mobile'][0] for k in ('tech', 'mobile') if k in yetishmagan]
    ro = "\n".join(f"{i}) {n}" for i, n in enumerate(nomlar, 1))
    kop = len(nomlar) > 1
    return send_msg(chat_id,
        f"❗ <b>Konkursda qatnashish uchun {'kanallarga' if kop else 'kanalga'} a'zo bo'ling:</b>\n{ro}\n\n"
        f"❗ <b>Для участия подпишитесь на {'каналы' if kop else 'канал'}:</b>\n{ro}",
        keyboard={"inline_keyboard": azo_kanal_tugmalari(yetishmagan) + [
            [{"text": "✅ A'zo bo'ldim — qatnashish", "callback_data": "check_member"}]
        ]})

async def start_konkurs_flow(chat_id, user):
    """/start konkurs, «Qatnashish» tugmasi va saytdan (/konkurs/boshla, BUGUN233) — bitta yo'l.
    Natija: (holat, yetdi) — holat 'ok' | 'yopiq' | 'obuna'; yetdi — xabar mijozga bordimi (botni boshlamagan — yo'q)."""
    # E1: Sheets va Telegram so'rovlari alohida ipda — event loop to'xtamaydi
    k = await blok(get_konkurs)
    # getKonkurs aktiv yo'q bo'lsa oxirgi TUGAGANINI qaytaradi (BUGUN108). BUGUN147: yashirin — begonaga ham shu javob
    if not _kk_aktivmi(k) or not _kk_korsatsinmi(k, user.get('id', chat_id)):
        return 'yopiq', await blok(send_msg, chat_id, f"😕 Hozirda aktiv konkurs yo'q.\n\nKanalimizni kuzating: {CHANNEL}")

    yet = await blok(yetishmagan_kanallar, chat_id)
    if yet:
        return 'obuna', await blok(not_member_msg, chat_id, yet)

    user_states[chat_id] = {
        'step': 'phone',
        'konkurs_id': k['id'],
        'prize': k.get('prize', ''),
        'user_id': user.get('id', chat_id),
        'username': user.get('username', ''),
    }

    return 'ok', await blok(send_msg, chat_id,
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
    if user_states.get(chat_id, {}).get('step') == 'captcha':
        await _kk_captcha_tugma(chat_id)
        return
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
    _mijoz_tel_qosh(chat_id, phone, 'konkurs')   # BUGUN225: konkursda olingan raqam — profildagi akkaunt raqami
    if state.get('step') == 'captcha':        # BUGUN125: raqam allaqachon olingan — tekshiruv tugmasini qayta beramiz
        user_states[chat_id] = state
        await _kk_captcha_tugma(chat_id)
        return

    yet = await blok(yetishmagan_kanallar, chat_id)
    if yet:
        user_states[chat_id] = state          # a'zo bo'lgach qaytadan so'ramaymiz
        await blok(not_member_msg, chat_id, yet)
        return

    username = state.get('username') or user.get('username', '')
    user_id = state.get('user_id', chat_id)
    konkurs_id = state.get('konkurs_id', '')
    # Ism (first_name + last_name) — g'olib username'siz bo'lsa ko'rsatish uchun
    ism = (user.get('first_name', '') or '').strip()
    _ln = (user.get('last_name', '') or '').strip()
    if _ln:
        ism = (ism + ' ' + _ln).strip()

    # ── BUGUN125 (v97 a): raqam olindi, lekin HALI QATNASHMADI. Qatnashish — faqat Mini App'dagi oddiy tekshiruvdan
    # (captcha) o'tgach, /konkurs/qatnash yozganda. Ilgari bu yerda darrov yozilib, saytdagi «Tasdiqlash» — faqat
    # ko'rinish edi (hech narsani tekshirmasdi). Holat xotirada: bot qayta yonsa — mijoz raqamni qayta yuboradi.
    user_states[chat_id] = {'step': 'captcha', 'konkurs_id': konkurs_id, 'prize': state.get('prize', ''),
                            'user_id': user_id, 'username': username or '', 'ism': ism, 'phone': str(phone),
                            'vaqt': time.time()}
    await _kk_captcha_tugma(chat_id)


# ══ BUGUN125: Konkurs Mini App — captcha + qurilma belgisi ══
# Oqim: raqam → «✅ Tasdiqlash» (web_app, sayt/konkurs.html) → POST /konkurs/captcha (savol) → mijoz tanlaydi →
# POST /konkurs/qatnash (javob + qurilma belgisi) → Apps Script joinKonkurs (kalit bilan) → faqat ok bo'lsa «qatnashdingiz».
# Bir qurilmadan 2+ akkaunt — BLOKLANMAYDI (foydalanuvchi: «qisman ushlab qolamiz»): jadvalda ⚠️ + adminga ikkalasi.
KONKURS_MINI_URL = SAYT_URL + 'konkurs.html'
_KK_CAPTCHA_BELGI = (('🍎', 'olma', 'яблоко'), ('🚗', 'mashina', 'машина'), ('🐱', 'mushuk', 'кошка'),
                     ('⚽', "to'p", 'мяч'), ('🌙', 'oy', 'луна'), ('🔑', 'kalit', 'ключ'), ('🎈', 'shar', 'шарик'),
                     ('🐟', 'baliq', 'рыба'), ('📱', 'telefon', 'телефон'), ('⭐', 'yulduz', 'звезда'),
                     ('🍌', 'banan', 'банан'), ('🏠', 'uy', 'дом'))
KK_CAPTCHA_MIN_S = 1.5          # tezroq javob — odam emas
KK_CAPTCHA_UMR_S = 600          # savol 10 daqiqa yaroqli
KK_CAPTCHA_OTDI_S = 300         # o'tgan tekshiruv — 5 daqiqa (tarmoq xatosida «Qayta urinish» captcha'siz)
KK_CAPTCHA_SOAT_MAX = 20        # bir akkauntga soatiga ko'pi bilan shuncha savol
_kk_captcha = {}                # uid → {id, javob, vaqt, otdi}
_kk_captcha_soni = {}           # uid → [oyna_boshi, soni]


async def _kk_captcha_tugma(chat_id):
    await blok(send_msg, chat_id,
               # BUGUN180 (foydalanuvchi, 2026-10-14, 3-band): matn aynan shu; BUGUN190 (3-band): tugma emojisi 🧩 → ✅
               "⚡️ Oxirgi qadam — pastdagi tugmani bosing va saytda tasdiqlang.\n"
               "⚡️ Последний шаг — нажмите кнопку ниже и подтвердите участие на сайте.",
               {"inline_keyboard": [[{"text": "✅ Tasdiqlash / Подтвердить", "web_app": {"url": KONKURS_MINI_URL}}]]})


def _kk_xesh(qiymat):
    """Qurilma id / izi → qisqa HMAC (jadvalda xom qiymat turmaydi; tenglikni solishtirish uchun yetadi)."""
    import hmac
    import hashlib
    v = re.sub(r'[^A-Za-z0-9_-]', '', str(qiymat or ''))[:128]
    if len(v) < 8:
        return ''
    kalit = (API_KEY or BOT_TOKEN or 'kraken').encode()
    return hmac.new(kalit, b'konkurs-qurilma:' + v.encode(), hashlib.sha256).hexdigest()[:16]


def _kk_qatnash_yoz(st, qurilma, iz):
    """Apps Script joinKonkurs — kalit bilan (qurilma belgisi yoziladi). Javob dict yoki None (tarmoq / kalit yo'q)."""
    data = json.dumps({'konkurs_id': str(st.get('konkurs_id') or ''), 'user_id': str(st.get('user_id') or ''),
                       'username': st.get('username') or '', 'ism': st.get('ism') or '', 'phone': st.get('phone') or '',
                       'qurilma': qurilma, 'qurilma_izi': iz}, ensure_ascii=False)
    return _kk_sheet('joinKonkurs', timeout=25, data=data)   # BUGUN232: 15 → 25 s (sayt 30 s kutadi)


def _kk_kim(username, ism, uid):
    nom = html_escape(ism or '—')
    return f"{nom} · {'@' + html_escape(username) if username else 'username yo‘q'} · <code>{html_escape(str(uid))}</code>"


# BUGUN220 (foydalanuvchi, 2026-10-16): «qatnashyapsiz» xabari oxirida konkurs SHARTLARI — keyin «ogohlantirilmagandik»
# demasin. Matn — foydalanuvchi tasdiqlagan (saytdagi «Tasdiqlandi» oynasida ham aynan shu: sayt/js/11-konkurs.js).
# Til — Mini App initData'dagi language_code (imzolangan): ru / uz bo'lsa — faqat o'sha til, bilinmasa — ikkalasi.
_KK_QATNASH_MATN = {
    'uz': ("✅ <b>Siz konkursda qatnashyapsiz!</b>\nG'olib e'lon qilinganda xabar beramiz.\n\n"
           "📋 <b>Shartlar:</b>\n"
           "• 1 kishi — 1 akkaunt. Bir telefondan bir nechta akkaunt bilan qatnashganlar g'oliblikdan chiqariladi.\n"
           "• G'olib e'lon qilinguncha kanaldan chiqmang — chiqsangiz, sovg'a berilmaydi."),
    'ru': ("✅ <b>Вы участвуете в розыгрыше!</b>\nСообщим, когда объявим победителя.\n\n"
           "📋 <b>Условия:</b>\n"
           "• 1 человек — 1 аккаунт. Участники с нескольких аккаунтов на одном телефоне исключаются из числа победителей.\n"
           "• Не выходите из канала до объявления победителя — иначе приз не выдаётся."),
}


def _kk_init_til(init_data):
    """initData → 'uz' | 'ru' | None (bilinmaydi). Imzo oldin check_init_data'da tekshirilgan."""
    try:
        got = dict(urllib.parse.parse_qsl(init_data or '', keep_blank_values=True))
        kod = str(json.loads(got.get('user') or '{}').get('language_code') or '').lower()
    except Exception:
        return None
    return 'ru' if kod.startswith('ru') else 'uz' if kod.startswith('uz') else None


def _kk_qatnash_matn(til):
    if til in _KK_QATNASH_MATN:
        return _KK_QATNASH_MATN[til]
    return _KK_QATNASH_MATN['uz'] + '\n\n' + _KK_QATNASH_MATN['ru']


async def konkurs_captcha_endpoint(request):
    """Mini App: yangi savol. Faqat raqam bergan (step=captcha) akkauntga."""
    import secrets
    import random
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'ok': False, 'sabab': 'imzo'}, status=401)
        uid = int(uid)
        st = user_states.get(uid) or {}
        if st.get('step') != 'captcha':
            return web.json_response({'ok': False, 'sabab': 'holat'})
        now = time.time()
        c = _kk_captcha.get(uid)
        if c and c.get('otdi') and now - c['otdi'] <= KK_CAPTCHA_OTDI_S:
            return web.json_response({'ok': True, 'id': c['id'], 'otdi': True, 'konkurs_id': str(st.get('konkurs_id'))})
        oyna = _kk_captcha_soni.get(uid)
        if not oyna or now - oyna[0] > 3600:
            oyna = _kk_captcha_soni[uid] = [now, 0]
        if oyna[1] >= KK_CAPTCHA_SOAT_MAX:
            return web.json_response({'ok': False, 'sabab': 'kop'})
        oyna[1] += 1
        tanlov = random.sample(_KK_CAPTCHA_BELGI, 6)
        maqsad = random.choice(tanlov)
        variantlar = [{'t': secrets.token_hex(4), 'e': b[0]} for b in tanlov]
        javob = variantlar[tanlov.index(maqsad)]['t']
        cid = secrets.token_hex(6)
        _kk_captcha[uid] = {'id': cid, 'javob': javob, 'vaqt': now, 'otdi': 0}
        return web.json_response({'ok': True, 'id': cid, 'savol_uz': maqsad[1], 'savol_ru': maqsad[2],
                                  'variantlar': variantlar, 'konkurs_id': str(st.get('konkurs_id'))})
    except Exception as e:
        logger.error(f'konkurs_captcha: {type(e).__name__}')
        return web.json_response({'ok': False, 'sabab': 'xato'}, status=500)


async def konkurs_qatnash_endpoint(request):
    """Mini App: javob + qurilma belgisi → qatnashish. ok:true — FAQAT jadvalga yozilgach (yoki oldin yozilgan).
    Xato / uzilish — ok:false, holat va o'tgan tekshiruv saqlanadi: mijoz «Qayta urinish» bosadi."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'ok': False, 'sabab': 'imzo'}, status=401)
        uid = int(uid)
        now = time.time()
        c = _kk_captcha.get(uid)
        if not c or c['id'] != str(data.get('id') or ''):
            return web.json_response({'ok': False, 'sabab': 'captcha'})
        if not c.get('otdi'):
            if now - c['vaqt'] > KK_CAPTCHA_UMR_S or now - c['vaqt'] < KK_CAPTCHA_MIN_S \
                    or str(data.get('javob') or '') != c['javob']:
                _kk_captcha.pop(uid, None)            # har noto'g'ri javob — yangi savol
                return web.json_response({'ok': False, 'sabab': 'notogri'})
            c['otdi'] = now
        elif now - c['otdi'] > KK_CAPTCHA_OTDI_S:
            _kk_captcha.pop(uid, None)
            return web.json_response({'ok': False, 'sabab': 'captcha'})
        st = user_states.get(uid) or {}
        if st.get('step') != 'captcha':
            return web.json_response({'ok': False, 'sabab': 'holat'})
        r = await blok(_kk_qatnash_yoz, st, _kk_xesh(data.get('qurilma')), _kk_xesh(data.get('iz')))
        if not r:
            return web.json_response({'ok': False, 'sabab': 'xato'})     # holat qoladi — qayta urinish
        msg = r.get('msg')
        if r.get('ok') or msg in ('already', 'yopiq'):        # yakuniy javob — holat tozalanadi
            if user_states.get(uid, {}).get('step') == 'captcha':
                user_states.pop(uid, None)
            _kk_captcha.pop(uid, None)
        if r.get('ok') or (msg == 'already' and r.get('sabab') != 'telefon'):
            _konkurs_cache['time'] = 0
            _kk_qatnashchi_qosh(st.get('konkurs_id'), uid)   # BUGUN147: kanaldan chiqish keshiga darhol
            if r.get('ok'):
                await _kk_son_xabari(st.get('konkurs_id'), r.get('count'))   # BUGUN226: har 20 kishida adminga
            await blok(send_msg, uid, _kk_qatnash_matn(_kk_init_til(data.get('initData'))))
            if r.get('shubha'):
                q = [f"⚠️ <b>Konkurs {html_escape(str(st.get('konkurs_id')))}: bir qurilmadan bir nechta akkaunt</b>",
                     "(bloklanmadi — jadvalda «ogohlantirish» ustunida belgilandi)", "",
                     f"🆕 Hozir kirgan: {_kk_kim(st.get('username'), st.get('ism'), st.get('user_id'))}"]
                for x in r['shubha']:
                    sabab = 'shu qurilma' if x.get('sabab') == 'qurilma' else "o'xshash qurilma, 5 daq ichida"
                    q.append(f"👤 Avvalgi ({sabab}): {_kk_kim(x.get('username'), x.get('ism'), x.get('user_id'))}")
                await _kk_admin("\n".join(q))
            return web.json_response({'ok': True, 'already': not r.get('ok')})
        return web.json_response({'ok': False, 'sabab': r.get('sabab') if msg == 'already' else (msg or 'xato')})
    except Exception as e:
        logger.error(f'konkurs_qatnash: {type(e).__name__}')
        return web.json_response({'ok': False, 'sabab': 'xato'}, status=500)


# ── BUGUN233: «Konkursda qatnashish» — saytdan to'g'ridan-to'g'ri (eski Telegram ?start= ni yubormaydi) ──
_kk_boshla_vaqt = {}   # user_id → oxirgi so'rov vaqti (ikki marta bosilsa — xabar bir marta)
KK_BOSHLA_ORALIQ = 5


async def konkurs_boshla_endpoint(request):
    """POST /konkurs/boshla {initData, kalit?} → /start konkurs bilan bir xil yo'l (obuna tekshiruvi bilan).
    Javob: {ok, sabab: ''|'yopiq'|'obuna'|'yetmadi'|'imzo'|'xato', xabar: xabar mijozga yetdimi}.
    xabar=false bo'lsa sayt eski ?start=konkurs havolasiga o'tadi."""
    try:
        try:
            data = await request.json()
        except Exception:
            data = {}
        init_data = str(data.get('initData') or '')
        uid = check_init_data(init_data)
        if not uid:
            return web.json_response({'ok': False, 'sabab': 'imzo', 'xabar': False}, status=401)
        try:
            u = json.loads(dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True)).get('user') or '{}')
        except Exception:
            u = {}
        user = {'id': uid, 'username': u.get('username') or '', 'first_name': u.get('first_name') or '',
                'language_code': u.get('language_code') or ''}
        hozir = time.time()
        if hozir - _kk_boshla_vaqt.get(uid, 0) < KK_BOSHLA_ORALIQ:
            return web.json_response({'ok': True, 'sabab': '', 'xabar': True, 'takror': True})
        _kk_boshla_vaqt[uid] = hozir
        if data.get('kalit'):   # BUGUN147: yashirin konkurs — ?start=konkurs_y bilan bir xil kalit
            _kk_kalitli.add(uid)
        holat, yetdi = await start_konkurs_flow(uid, user)
        if yetdi:
            asyncio.create_task(mijoz_bot_qayd(user, 'yangi'))   # BUGUN173 — /start kabi (xabar yetdi = bot ochiq)
        else:
            _kk_boshla_vaqt.pop(uid, None)   # eski havola bilan qayta urinish to'silmasin
        sabab = holat if holat != 'ok' else ('' if yetdi else 'yetmadi')
        return web.json_response({'ok': holat == 'ok' and bool(yetdi), 'sabab': sabab, 'xabar': bool(yetdi)})
    except Exception as e:
        logger.error(f'konkurs_boshla: {type(e).__name__}')
        return web.json_response({'ok': False, 'sabab': 'xato', 'xabar': False}, status=500)


# ── BUGUN226 (foydalanuvchi, 2026-10-16): konkursda har 20 yangi ishtirokchida adminga «🎁 Konkursda 40 kishi».
# Son — Apps Script joinKonkurs javobidagi `count` (jadval qulfi ichida hisoblangan: har qo'shilishga o'z soni) — shu sabab bot
# qayta yonsa ham bir son ikki marta chiqmaydi (holat jadvalda — T2); `_kk_son_yuborilgan` — shu jarayondagi qo'shimcha himoya.
KK_SON_QADAM = 20
_kk_son_yuborilgan = set()


async def _kk_son_xabari(konkurs_id, soni):
    try:
        soni = int(soni)
    except (TypeError, ValueError):
        return
    kalit = (str(konkurs_id), soni)
    if soni < KK_SON_QADAM or soni % KK_SON_QADAM or kalit in _kk_son_yuborilgan:
        return
    _kk_son_yuborilgan.add(kalit)
    await _kk_admin(f"🎁 Konkursda {soni} kishi")


def _tg_mid(r):
    """Telegram javobidan birinchi xabar raqami (sendMediaGroup — ro'yxat). Xato / tushunarsiz — None."""
    try:
        j = r.json() if r is not None and r.status_code == 200 else None
        res = j.get('result') if isinstance(j, dict) and j.get('ok') else None
        if isinstance(res, list):
            res = res[0] if res else None
        mid = res.get('message_id') if isinstance(res, dict) else None
        return int(mid) if mid else None
    except Exception:
        return None


def send_konkurs_channel_post(chat_id, text, images, reply_markup):
    """Konkurs natijasini kanalga yuboradi (HTML parse_mode):
    1 rasm  -> sendPhoto (caption + tugma birga)
    ko'p rasm -> sendMediaGroup (caption 1-rasmga) + tugma alohida qisqa xabar.
    3185: postning (ko'p rasmda — 1-rasm, matni shunda) message_id sini qaytaradi; yuborilmadi — None."""
    imgs = [i for i in (images or []) if i][:10]
    if not imgs:
        return _tg_mid(req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': reply_markup
        }, timeout=10))
    caption_fits = len(text) <= 1000
    if len(imgs) == 1:
        r = req.post(f'{TG_API}/sendPhoto', json={
            'chat_id': chat_id, 'photo': imgs[0],
            'caption': text, 'parse_mode': 'HTML',
            'reply_markup': reply_markup
        }, timeout=15)
        if r.status_code == 200 and r.json().get('ok'):
            return _tg_mid(r)
        return _tg_mid(req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': reply_markup
        }, timeout=10))
    # Ko'p rasm — caption 1-rasmga biriktiriladi (matn+rasm birga)
    media = []
    for i, u in enumerate(imgs):
        item = {'type': 'photo', 'media': u}
        if i == 0 and caption_fits:
            item['caption'] = text
            item['parse_mode'] = 'HTML'
        media.append(item)
    mid = _tg_mid(req.post(f'{TG_API}/sendMediaGroup', json={'chat_id': chat_id, 'media': media}, timeout=20))
    if caption_fits:
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': '🛍', 'reply_markup': reply_markup
        }, timeout=10)
    else:
        # matn sig'madi — rasmlar matnsiz ketdi, post matni shu xabarda: havola shunga
        mid = _tg_mid(req.post(f'{TG_API}/sendMessage', json={
            'chat_id': chat_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': reply_markup
        }, timeout=10)) or mid
    return mid


def _maxfiy(e):
    """Xato matni — BOT_TOKEN siz (requests xatosida URL bo'ladi: /bot<token>/getFile, /file/bot<token>/…)."""
    t = str(e)
    return t.replace(BOT_TOKEN, '***') if BOT_TOKEN else t


def _qayta_urin(nom, fn, kutish=None):
    """BUGUN222: fn() — xato (vaqt tugadi, ulanish uzildi…) yoki None bo'lsa, RASM_QAYTA_KUTISH oraliqlari bilan qayta.
    Boshqa har qanday qiymat (bo'sh satr ham — «qayta urinish foyda bermaydi») darrov qaytadi. Oxiri ham bo'lmasa — None."""
    kutish = RASM_QAYTA_KUTISH if kutish is None else kutish
    for urinish in range(len(kutish) + 1):
        try:
            v = fn()
            if v is not None:
                return v
            sabab = "bo'sh javob"
        except Exception as e:
            sabab = _maxfiy(e)
        if urinish < len(kutish):
            logger.warning(f'{nom}: {sabab} — {urinish + 1}-urinish, {kutish[urinish]} s dan keyin qayta')
            time.sleep(kutish[urinish])
        else:
            logger.error(f"{nom}: {sabab} — {urinish + 1} urinishdan keyin ham bo'lmadi")
    return None


def tg_file_url(file_id):
    """Telegram file_id dan yuklab olinadigan URL qaytaradi. BUGUN222: vaqt tugasa / 5xx / 429 — qayta urinadi
    (2026-10-15: «getFile Read timed out» — 2 rasm yo'qolgan); Telegram «ok: false» desa — darrov ''."""
    def bir():
        r = req.get(f'{TG_API}/getFile?file_id={file_id}', timeout=10)
        if r.status_code == 429 or r.status_code >= 500:
            raise RuntimeError(f'HTTP {r.status_code}')
        fi = r.json()
        if fi.get('ok'):
            fp = fi['result']['file_path']
            return f'https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}'
        logger.error(f"getFile: {fi.get('description')}")
        return ''
    return _qayta_urin('getFile', bir) or ''


def upload_to_imagekit(file_id, papka='/kraken', kengaytma='jpg'):
    """Telegram file_id'ni yuklab olib, ImageKit'ga yuboradi. Barqaror URL qaytaradi, bo'lmasa — ''.
    BUGUN252: papka — «🖼 Rasmlar» mavzusidan '/rasmlar'; kengaytma — fayl (document) bo'lib kelgan rasmniki.
    BUGUN222: har qadam (getFile, yuklab olish, ImageKit) — 3 marta qayta urinish; 0 baytli fayl — xato (e'longa
    qo'shilmaydi, 2026-10-15 №253). Telegram URL'iga «fallback» OLIB TASHLANDI: unda BOT_TOKEN bor (jadvalga, saytga
    chiqardi) va havola ~1 soatda o'ladi — e'londa keyin buzuq rasm qolardi. Endi admin «N-rasm yuklanmadi» xabarini oladi."""
    tg_url = tg_file_url(file_id)
    if not tg_url:
        return ''

    # 1) Telegram'dan rasmni yuklab olamiz
    def yuklab_ol():
        img = req.get(tg_url, timeout=20)
        if img.status_code != 200 or not img.content:
            raise RuntimeError(f'yuklab olish: HTTP {img.status_code}, {len(img.content or b"")} bayt')
        return img.content
    content = _qayta_urin('rasm yuklab olish', yuklab_ol)
    if not content:
        return ''

    # 2) ImageKit'ga yuklaymiz (Basic Auth: private_key username, parol bo'sh)
    fname = f"{int(time.time()*1000)}_{file_id[:8]}.{kengaytma}"

    def ik():
        r = req.post(
            IK_UPLOAD_URL,
            auth=(IK_PRIVATE_KEY, ''),
            files={'file': (fname, content)},
            data={'fileName': fname, 'folder': papka},
            timeout=30
        )
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code == 200 and j.get('url'):
            return j['url']
        if r.status_code == 429 or r.status_code >= 500 or not j:
            raise RuntimeError(f'ImageKit HTTP {r.status_code}')
        logger.error(f'ImageKit upload: {r.status_code} {j}')
        return ''
    return _qayta_urin('ImageKit', ik) or ''


def rasmlar_yukla(file_ids, papka='/kraken', har_rasm=None, kengaytma='jpg'):
    """BUGUN252: 4 tadan parallel yuklash (tartib saqlanadi) → [url | '']. har_rasm() — har rasm tugaganda (progress)."""
    def bir(fid):
        try:
            return upload_to_imagekit(fid, papka, kengaytma)
        finally:
            if har_rasm:
                try:
                    har_rasm()
                except Exception as e:
                    logger.warning(f'progress: {_maxfiy(e)}')
    if not file_ids:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(file_ids))) as ex:
        return list(ex.map(bir, file_ids))


def create_bot_elon(file_ids, yonalish=None, har_rasm=None):
    """Rasm(lar)dan chala elon yaratadi. file_id -> ImageKit URL -> Sheets.
    yonalish (MS3.2) — Apps Script'ga ham boradi (hozir yozilmaydi — ustun yo'q; e'lon yo'nalishi modeldan).
    BUGUN222: rasmlar 4 tadan parallel yuklanadi (tartib saqlanadi); yuklanmaganlari — res['yuklanmadi'] (1 dan sanaladi).
    Hech biri yuklanmasa — {'ok': False, 'yuklanmadi': [...]}, e'lon ochilmaydi. botCreateElon — 45 s (Apps Script qulfda
    navbat kutishi mumkin), qayta yuborilmaydi: yetib borgan bo'lsa ikkinchi e'lon ochilardi."""
    if not file_ids:
        return None
    natija = rasmlar_yukla(file_ids, har_rasm=har_rasm)
    urls = [u for u in natija if u]
    yuklanmadi = [i + 1 for i, u in enumerate(natija) if not u]
    if not urls:
        return {'ok': False, 'yuklanmadi': yuklanmadi}
    try:
        payload = urllib.parse.quote(json.dumps(dict({'images': urls}, **({'yonalish': yonalish} if yonalish else {}))))
        r = req.get(f'{SHEET_URL}?action=botCreateElon&key={urllib.parse.quote(API_KEY)}&data={payload}', timeout=45)
        res = r.json()
    except Exception as e:
        logger.error(f'create_bot_elon: {_maxfiy(e)}')
        return None
    if not res.get('ok'):
        logger.error(f'create_bot_elon: {res}')
        return None
    if yuklanmadi:
        res['yuklanmadi'] = yuklanmadi
    return res


def _navbat_ishi(chat_id, fn, *args):
    """Navbat ipida: xato yashirinmasin (ilgari run_in_executor xatoni jim yutardi) — logga va hisobotga.
    BUGUN252: fn natijasi (dict | None) progress sessiyasiga boradi — oxirgi ish tugaganda bitta hisobot."""
    try:
        natija = fn(*args)
    except Exception as e:
        logger.error(f'elon navbati ({fn.__name__}): {_maxfiy(e)}')
        natija = {'tur': 'xato'}
    try:
        _jarayon_ish(chat_id, natija)
    except Exception as e:
        logger.error(f'rasm hisoboti: {_maxfiy(e)}')
        try:
            send_msg(chat_id, "❌ Hisobot yuborilmadi — saytda tekshiring.")
        except Exception:
            pass


# ── BUGUN252 §2: bitta progress xabar ──
# Sessiya — har joy (chat + mavzu) uchun: navbatga tushgan ishlar (albom / bitta rasm) va rasmlar soni. Rasm yuklangan sari
# «⏳ 12/20» xabari JARAYON_ORALIQ da bir marta tahrirlanadi (ilk xabar ham faqat shuncha vaqt o'tsa — tez tugagan 1 rasmga
# ortiqcha xabar yo'q). Oxirgi ish tugaganda — progress xabari o'chadi, BITTA hisobot keladi (qaysi albomdan nechta rasm
# yuklanmadi). Bitta e'lon bo'lsa — avvalgi «✅ Yangi elon yaratildi» xabari.
# Progress yozuvi va hisobot — ikkalasi ham e'lon navbati ipida (rasm yuklash havzasi ish ichida tugaydi) — bir vaqtda emas.
_jarayon = {}
_jarayon_qulf = threading.Lock()


def _jkalit(chat_id):
    return (int(chat_id), getattr(chat_id, 'thread', None))


def _jarayon_qosh(chat_id, rasm=0, ish=0, tur='elon'):
    """Event loop ipida: rasm keldi (rasm=1) / yangi ish navbatga tushdi (ish=1)."""
    with _jarayon_qulf:
        k = _jkalit(chat_id)
        j = _jarayon.get(k)
        if j is None:
            j = _jarayon[k] = {'chat': chat_id, 'tur': tur, 'jami': 0, 'tayyor': 0, 'ishlar': 0, 'tugadi': 0,
                               'mid': None, 'oxirgi': time.monotonic(), 'natija': []}
        j['jami'] += rasm
        j['ishlar'] += ish


def _jarayon_matn(j):
    elon = sum(1 for n in j['natija'] if n and n.get('tur') == 'elon' and (n.get('res') or {}).get('ok'))
    return (("⏳ Rasmlar omboriga: " if j['tur'] == 'rasmlar' else "⏳ Rasmlar yuklanmoqda: ")
            + f"<b>{j['tayyor']}/{j['jami']}</b>" + (f"\n✅ {elon} ta e'lon tayyor" if elon else ''))


def _jarayon_yoz(chat_id, mid, matn):
    """Progress xabari: yo'q bo'lsa — yuboriladi (ovozsiz), bor bo'lsa — tahrirlanadi. message_id qaytaradi."""
    try:
        if mid:
            req.post(f'{TG_API}/editMessageText', json={'chat_id': chat_id, 'message_id': mid, 'text': matn,
                                                         'parse_mode': 'HTML'}, timeout=8)
            return mid
        r = req.post(f'{TG_API}/sendMessage', json={'chat_id': chat_id, 'text': matn, 'parse_mode': 'HTML',
                                                     'disable_notification': True}, timeout=8).json()
        return (r.get('result') or {}).get('message_id')
    except Exception as e:
        logger.warning(f'progress xabari: {_maxfiy(e)}')
        return mid


def _jarayon_rasm(chat_id):
    """Rasm yuklandi (yoki yuklanmadi) — sanoq +1; oxirgi yozuvdan JARAYON_ORALIQ o'tgan bo'lsa — xabar yangilanadi."""
    with _jarayon_qulf:
        j = _jarayon.get(_jkalit(chat_id))
        if not j:
            return
        j['tayyor'] += 1
        hozir = time.monotonic()
        if hozir - j['oxirgi'] < JARAYON_ORALIQ or j['tayyor'] >= j['jami']:
            return
        j['oxirgi'] = hozir
        matn, mid = _jarayon_matn(j), j['mid']
    mid = _jarayon_yoz(chat_id, mid, matn)
    with _jarayon_qulf:
        j['mid'] = j['mid'] or mid


def _jarayon_ish(chat_id, natija):
    """Ish tugadi. Sessiyadagi oxirgi ish bo'lsa — hisobot (sessiya yopiladi)."""
    with _jarayon_qulf:
        k = _jkalit(chat_id)
        j = _jarayon.get(k)
        if j is None:     # sessiyasiz chaqiruv (eski yo'l / sinov) — shu natijaning o'zi
            j = {'chat': chat_id, 'tur': (natija or {}).get('tur', 'elon'), 'jami': 0, 'ishlar': 1, 'tugadi': 0,
                 'mid': None, 'natija': []}
        else:
            j['tugadi'] += 1
            if natija:
                j['natija'].append(natija)
            if j['tugadi'] < j['ishlar']:
                return
            _jarayon.pop(k, None)
            natija = None
    if natija:
        j['natija'].append(natija)
    _jarayon_yakun(j)


def _jarayon_yakun(j):
    chat_id, nat = j['chat'], [n for n in j['natija'] if n]
    if nat:
        if len(nat) == 1 and nat[0].get('tur') == 'elon':
            n = nat[0]
            _elon_tayyor_xabar(chat_id, n.get('res'), n.get('cnt', 0), n.get('yon'))
        elif len(nat) == 1 and nat[0].get('matn'):      # bitta Rasmlar / kech ishi — o'z qatori («📸 Jami» ortiqcha)
            send_msg(chat_id, nat[0]['matn'])
        else:
            matn, tugma = _hisobot(nat, j.get('jami') or sum(n.get('soni', 0) for n in nat))
            send_msg(chat_id, matn, tugma)
    if j.get('mid'):
        delete_msg(chat_id, j['mid'])


def _hisobot(nat, jami):
    """Bir nechta ish (albom / rasm) natijasi → (matn, tugma). Qaysi albomdan qaysi rasm yuklanmadi — alohida qator."""
    qator, ok_num, saqlandi, yonlar = [], [], 0, []
    for n in nat:
        tur = n.get('tur')
        if tur == 'elon':
            res, soni = n.get('res') or {}, n.get('soni', 0)
            yuk = res.get('yuklanmadi') or []
            if res.get('ok'):
                ok_num.append(f"№{res.get('num', '?')}")
                yonlar.append(n.get('yon'))
                saqlandi += soni - len(yuk)
                if yuk:
                    qator.append(f"⚠️ №{res.get('num', '?')}: {', '.join(f'{i}-rasm' for i in yuk)} yuklanmadi "
                                 f"({soni} tadan)")
            else:
                qator.append(f"❌ {'Albom' if soni > 1 else 'Rasm'} ({soni} rasm): "
                             + ("hech biri yuklanmadi" if yuk else "xatolik") + " — e'lon ochilmadi, qayta yuboring")
        elif tur == 'xato':
            qator.append("❌ Bir albomda xatolik — e'lon ochilmadi, qayta yuboring")
        else:                      # 'rasmlar' / 'kech' — tayyor qator
            saqlandi += n.get('saqlandi', 0)
            if n.get('matn'):
                qator.append(n['matn'])
    bosh = []
    if ok_num:
        yon = yonlar[0] if len(set(yonlar)) == 1 else None
        bolim = f" · {YON_KANAL[yon][0]}" if yon in YON_KANAL else ''
        bosh.append(f"✅ <b>{len(ok_num)} ta e'lon yaratildi</b>{bolim}: {', '.join(ok_num)}")
    matn = '\n'.join(bosh + qator + [f"📸 Jami: {saqlandi}/{jami} rasm saqlandi."])
    if not ok_num:
        return matn, None
    yon = yonlar[0] if len(set(yonlar)) == 1 else None
    return (matn + "\n\nEndi saytdagi admin panelda ma'lumotlarini to'ldiring 👇",
            {"inline_keyboard": [[{"text": "🛠 Admin panel / Saytga kirish",
                                   "web_app": {"url": SAYT_URL + (f'?p=y_{yon}' if yon in YON_KANAL else '')}}]]})


# ── BUGUN252 §1: albom bo'laklari ──
def _albom_bolak(key, chat_id, mid, file_id, tur, izoh='', kengaytma='jpg'):
    """Event loop ipida: albom bo'lagi keldi. 1-bo'lak — albom ochiladi va ishi DARROV navbatga qo'yiladi (kelgan tartib
    saqlansin); ish bo'laklar tugashini kutadi: har bo'lakda taymer qayta (ALBOM_KUTISH), 1-bo'lakdan ALBOM_MAKS dan oshmaydi.
    Ish boshlangandan keyin kelgan kech bo'lak — yangi e'lon EMAS: alohida ish o'sha e'longa qo'shadi."""
    loop = asyncio.get_event_loop()
    hozir = time.monotonic()
    yangi_ish = None
    with _photo_qulf:
        grp = _photo_groups.get(key)
        if grp is None:
            for k in [k for k, g in _photo_groups.items() if g.get('tugadi') and hozir - g.get('boshi', 0) > 600]:
                _photo_groups.pop(k, None)
            grp = _photo_groups[key] = {'bolaklar': [], 'izohlar': [], 'chat_id': chat_id, 'tur': tur,
                                        'kengaytma': kengaytma, 'yonalish': rasm_yonalish(chat_id), 'boshi': hozir,
                                        'tayyor': threading.Event()}
            yangi_ish = (_albom_ishi, key)
        if izoh:
            grp['izohlar'].append((mid, izoh))
        if grp.get('olindi'):
            grp.setdefault('kech', []).append((mid, file_id))
            if not grp.get('kech_navbatda'):
                grp['kech_navbatda'] = True
                yangi_ish = (_kech_ishi, key)
        else:
            grp['bolaklar'].append((mid, file_id))
            old = grp.get('timer')
            if old:
                old.cancel()
            qoldi = max(0.0, grp['boshi'] + ALBOM_MAKS - hozir)
            grp['timer'] = loop.call_later(min(ALBOM_KUTISH, qoldi), grp['tayyor'].set)
    _jarayon_qosh(chat_id, rasm=1, ish=1 if yangi_ish else 0, tur=tur)
    if yangi_ish:
        _elon_navbat.submit(_navbat_ishi, chat_id, *yangi_ish)


def _albom_izoh(grp):
    """Albom izohi — eng kichik message_id li izohli bo'lakdan (odatda 1-rasm): butun albomga."""
    return sorted(grp.get('izohlar') or [])[0][1] if grp.get('izohlar') else ''


def _albom_ishi(key):
    """Navbat ipida: albom bo'laklari tugashini kutadi, message_id bo'yicha tartiblaydi, e'lon / Rasmlar."""
    with _photo_qulf:
        grp = _photo_groups.get(key)
    if not grp:
        return None
    grp['tayyor'].wait(ALBOM_MAKS + 5)      # taymer (event loop) — bo'laklar tugadi; ehtiyot chegarasi bilan
    with _photo_qulf:
        grp['olindi'] = True
        t = grp.get('timer')
        if t:
            t.cancel()
        fids = [f for _, f in sorted(grp['bolaklar'])]
        izoh = _albom_izoh(grp)
    chat_id = grp['chat_id']
    try:
        if grp['tur'] == 'rasmlar':
            natija = _rasmlar_ishi(chat_id, fids, izoh, grp.get('kengaytma', 'jpg'))
        else:
            natija = _elon_ishi(chat_id, fids, grp.get('yonalish'))
    finally:
        with _photo_qulf:
            grp['tugadi'] = True
    grp['natija'] = natija
    return natija


def _kech_ishi(key):
    """Ish boshlangandan keyin kelgan bo'lak(lar) — o'sha e'longa (ochilmagan bo'lsa — yangi e'lon) / Rasmlar ga."""
    with _photo_qulf:
        grp = _photo_groups.get(key) or {}
        kech = sorted(grp.pop('kech', []))
        grp['kech_navbatda'] = False
    if not kech:
        return None
    chat_id, fids = grp['chat_id'], [f for _, f in kech]
    if grp.get('tur') == 'rasmlar':
        return _rasmlar_ishi(chat_id, fids, _albom_izoh(grp), grp.get('kengaytma', 'jpg'))
    num = ((grp.get('natija') or {}).get('res') or {}).get('num')
    if not num:
        return _elon_ishi(chat_id, fids, grp.get('yonalish'))
    natija = rasmlar_yukla(fids, har_rasm=lambda: _jarayon_rasm(chat_id))
    urls = [u for u in natija if u]
    j = _kk_sheet('rasmBiriktir', timeout=45, data=json.dumps({'num': num, 'urls': urls, 'majburiy': True})) if urls else None
    if j and j.get('ok'):
        return {'tur': 'kech', 'saqlandi': len(urls), 'soni': len(fids),
                'matn': f"➕ №{num} ga kech kelgan {len(urls)} rasm qo'shildi"
                        + (f" ({len(fids) - len(urls)} tasi yuklanmadi)" if len(urls) < len(fids) else '')}
    return {'tur': 'kech', 'saqlandi': 0, 'soni': len(fids),
            'matn': f"❌ №{num} ga kech kelgan {len(fids)} rasm qo'shilmadi — qayta yuboring"}


def _elon_ishi(chat_id, fids, yon):
    """Rasm(lar) → chala e'lon. Natija — hisobot uchun."""
    res = create_bot_elon(fids, yon, har_rasm=lambda: _jarayon_rasm(chat_id))
    return {'tur': 'elon', 'res': res, 'cnt': (res or {}).get('images', len(fids)), 'yon': yon, 'soni': len(fids)}


# ── BUGUN252 §4: «🖼 Rasmlar» mavzusi ──
# BUGUN246 §7 jadvali: raqam bor — «✅ №213 ga qo'shildi» · raqam yo'q — «№999 topilmadi — rasm Rasmlar omborida qoldi» ·
# sotilgan / o'chirilgan — «№213 sotilgan — baribir qo'shaymi?» (tugma) · izoh raqam emas — izoh bo'lib saqlanadi ·
# albomda faqat 1-rasmda izoh — butun albom o'sha raqamga · rasm emas — e'tiborsiz, bir marta yo'l-yo'riq.
_rasm_kutish = {}           # tugma tokeni → {'num', 'urls', 'vaqt'} («baribir qo'shaymi?» javobi kutilmoqda)
_rasmlar_yol = {'korsatildi': False}


def rasm_izoh(matn):
    """Izoh → (raqam | None, izoh). «213», «№213», «#213» — raqam; boshqasi — izoh (500 belgigacha)."""
    m = re.fullmatch(r'\s*[#№]?\s*(\d{1,6})\s*', matn or '')
    return (int(m.group(1)), '') if m else (None, (matn or '').strip()[:500])


def rasmlar_mavzusi(joy):
    t = getattr(joy, 'thread', None)
    return bool(t and GURUH.get('id') and GURUH.get('rasmlar') and int(joy) == GURUH['id'] and t == GURUH['rasmlar'])


def _rasmlar_ishi(chat_id, fids, izoh_matn='', kengaytma='jpg'):
    """Rasm(lar) → ImageKit /rasmlar → Store «Rasmlar» (botRasmlar); izohda raqam bo'lsa — o'sha e'longa ham."""
    natija = rasmlar_yukla(fids, '/rasmlar', lambda: _jarayon_rasm(chat_id), kengaytma)
    urls = [u for u in natija if u]
    yuk = [i + 1 for i, u in enumerate(natija) if not u]
    soni = len(fids)
    if not urls:
        return {'tur': 'rasmlar', 'saqlandi': 0, 'soni': soni, 'matn': f"❌ {soni} rasm yuklanmadi — qayta yuboring"}
    num, izoh = rasm_izoh(izoh_matn)
    j = _kk_sheet('botRasmlar', timeout=45, data=json.dumps({'urls': urls, 'izoh': izoh, 'num': num}))
    if not j or not j.get('ok'):
        logger.error(f'botRasmlar: {(j or {}).get("msg", "javob yoq")}')
        return {'tur': 'rasmlar', 'saqlandi': 0, 'soni': soni,
                'matn': f"❌ {len(urls)} rasm Rasmlar varag'iga yozilmadi — qayta yuboring"}
    qism = f" ({', '.join(f'{i}-rasm' for i in yuk)} yuklanmadi)" if yuk else ''
    holat = j.get('holat')
    if num and holat == 'qoshildi':
        matn = f"✅ №{num} ga qo'shildi — {len(urls)} rasm{qism}"
    elif num and holat in ('sotilgan', 'ochirilgan'):
        import secrets
        tok = secrets.token_hex(4)
        with _photo_qulf:
            for k in [k for k, v in _rasm_kutish.items() if time.time() - v['vaqt'] > 86400]:
                _rasm_kutish.pop(k, None)
            _rasm_kutish[tok] = {'num': num, 'urls': urls, 'vaqt': time.time()}
        nima = 'sotilgan' if holat == 'sotilgan' else "o'chirilgan"
        send_msg(chat_id, f"№{num} {nima} — baribir qo'shaymi? ({len(urls)} rasm Rasmlar omborida turibdi)",
                 {"inline_keyboard": [[{"text": "✅ Ha, qo'shilsin", "callback_data": f"rqo:{tok}"},
                                       {"text": "✖️ Yo'q", "callback_data": f"rqy:{tok}"}]]})
        matn = f"❓ №{num} {nima} — savol alohida xabarda{qism}"
    elif num:
        matn = f"№{num} topilmadi — rasm Rasmlar omborida qoldi ({len(urls)} rasm){qism}"
    else:
        matn = f"📥 {len(urls)} rasm Rasmlar omboriga saqlandi" + (f" · izoh: {html_escape(izoh)}" if izoh else '') + qism
    return {'tur': 'rasmlar', 'saqlandi': len(urls), 'soni': soni, 'matn': matn}


def rasm_baribir_tugma(chat_id, message_id, data):
    """«№213 sotilgan — baribir qo'shaymi?» tugmasi: rqo — qo'shiladi (rasmBiriktir, majburiy), rqy — omborda qoladi."""
    tok = data[4:]
    with _photo_qulf:
        k = _rasm_kutish.pop(tok, None)
    if not k:
        matn = "⌛ Bu savol eskirgan — rasm Rasmlar omborida, saytda «🖼 Rasmlardan tanlash» bilan qo'shing."
    elif data.startswith('rqy:'):
        matn = f"✖️ №{k['num']} ga qo'shilmadi — rasm Rasmlar omborida qoldi."
    else:
        j = _kk_sheet('rasmBiriktir', timeout=45, data=json.dumps({'num': k['num'], 'urls': k['urls'], 'majburiy': True}))
        matn = (f"✅ №{k['num']} ga qo'shildi — {len(k['urls'])} rasm" if j and j.get('ok') else
                f"❌ №{k['num']} ga qo'shilmadi — saytda «🖼 Rasmlardan tanlash» bilan qo'shing.")
    try:
        req.post(f'{TG_API}/editMessageText', json={'chat_id': chat_id, 'message_id': int(message_id or 0), 'text': matn},
                 timeout=8)
    except Exception as e:
        logger.warning(f'rasm tugmasi: {_maxfiy(e)}')
        send_msg(chat_id, matn)


async def handle_rasmlar_xabar(chat_id, message):
    """«🖼 Rasmlar» mavzusidagi admin xabari. Rasm / rasm-fayl — navbatga; boshqasi — e'tiborsiz, bir marta yo'l-yo'riq."""
    mid = message.get('message_id', 0)
    izoh = message.get('caption', '')
    mgid = message.get('media_group_id')
    photo = message.get('photo')
    doc = message.get('document') or {}
    kengaytma = 'jpg'
    if photo:
        fid = photo[-1].get('file_id', '')
    elif str(doc.get('mime_type', '')).startswith('image/'):
        if int(doc.get('file_size') or 0) > 20 * 1024 * 1024:
            await blok(send_msg, chat_id, "⚠️ Fayl katta (20 MB dan ortiq) — bot ololmaydi. Rasm sifatida yuboring.")
            return
        fid = doc.get('file_id', '')
        kengaytma = (re.findall(r'\.([A-Za-z0-9]{2,5})$', doc.get('file_name') or '') or ['jpg'])[0].lower()
    else:
        if not _rasmlar_yol['korsatildi']:
            _rasmlar_yol['korsatildi'] = True
            await blok(send_msg, chat_id, "🖼 Bu mavzuga rasm tashlang (izohga e'lon raqami — masalan 213 — yozsangiz, "
                                          "o'sha e'longa qo'shiladi). Matn, stiker, video — e'tiborsiz.")
        return
    if not fid:
        return
    if mgid:
        _albom_bolak(f'r:{mgid}', chat_id, mid, fid, 'rasmlar', izoh, kengaytma)
    else:
        _jarayon_qosh(chat_id, rasm=1, ish=1, tur='rasmlar')
        _elon_navbat.submit(_navbat_ishi, chat_id, _rasmlar_ishi, chat_id, [fid], izoh, kengaytma)


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
        r = req.get(f'{SHEET_URL}?action=createWaitedKonkurs&key={urllib.parse.quote(API_KEY)}&data={payload}', timeout=15)
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


async def handle_admin_photo(chat_id, file_id, media_group_id, mid=0):
    """Admin rasm yuborsa — chala elon yaratadi.
    Albom (media group) bo'lsa, barcha rasmlar to'planguncha kutadi (BUGUN252: _albom_bolak — qayta boshlanuvchi taymer,
    maks. ALBOM_MAKS; tartib — message_id). MS3.2: guruhning «Rasm · …» mavzusidan kelsa — e'lon o'sha bo'limniki."""
    if media_group_id:
        _albom_bolak(media_group_id, chat_id, mid, file_id, 'elon')
    else:
        # Bitta rasm — e'lon navbatiga (oldingi albom / rasm tugagach)
        _jarayon_qosh(chat_id, rasm=1, ish=1)
        _elon_navbat.submit(_navbat_ishi, chat_id, _elon_ishi, chat_id, [file_id], rasm_yonalish(chat_id))


def _elon_tayyor_xabar(chat_id, res, cnt, yon=None):
    """Chala e'lon yaratildi / xato — admin javobi. MS3.2: bo'lim mavzusidan — nomi va sayt o'sha bo'limda ochiladi (?p=y_pc)."""
    yuk = ', '.join(f'{n}-rasm' for n in ((res or {}).get('yuklanmadi') or []))
    if not res or not res.get('ok'):
        # BUGUN222: hech bir rasm yuklanmadi — e'lon ochilmadi (bo'sh e'lon qolmaydi)
        send_msg(chat_id, f"❌ {yuk} yuklanmadi — e'lon ochilmadi, qayta yuboring." if yuk
                 else "❌ Elon yaratishda xatolik. Qayta urining.")
        return
    send_msg(chat_id, *_elon_tayyor_matn(res, cnt, yon))


def _elon_tayyor_matn(res, cnt, yon=None):
    """«✅ Yangi elon yaratildi» matni va tugmasi (3214.1: /guruh namuna ham shuni ko'rsatadi)."""
    yuk = ', '.join(f'{n}-rasm' for n in ((res or {}).get('yuklanmadi') or []))
    num = res.get('num', '?')
    bolim = f" · {YON_KANAL[yon][0]}" if yon in YON_KANAL else ''
    return (f"✅ Yangi elon yaratildi: <b>№{num}</b>{bolim}\n"
            f"📸 {cnt} ta rasm saqlandi.\n"
            + (f"⚠️ {yuk} yuklanmadi, qayta yuboring.\n" if yuk else '') +
            f"\nEndi saytdagi admin panelda ma'lumotlarini to'ldiring 👇",
            {"inline_keyboard": [[{
                "text": "🛠 Admin panel / Saytga kirish",
                "web_app": {"url": SAYT_URL + (f'?p=y_{yon}' if yon in YON_KANAL else '')}
            }]]})


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
#  o'chiriladi. file_id Elonlar jadvalidagi `rasm_file_id` ustuniga ham yoziladi (BUGUN148) — restart / deploydan keyin
#  qayta yuklanmaydi (jadvaldan olinadi). Hali yuklanmagan
#  e'lon — oddiy rasm kartasi (_share_result) bilan chiqadi, keyingi so'rovda rich.
#  Yuklash faqat inline so'rov kelganda boshlanadi (BotFather'da yoqilmaguncha jim).
#  Ma'lumot — _ELON_CACHE (G10.3) + jadvaldagi file_id (rasm_file_id).
# ══════════════════════════════════════════════════════════════════════════

INLINE_SAHIFA = 50            # Telegram: bitta javobda ≤ 50 natija
INLINE_KUTISH = 5.0           # rasm yuklanishini kutish (s) — so'ng tayyori rich, qolgani karta
INLINE_EKRAN = 6              # 9000: telefonda birinchi ekranga sig'adigan natija — faqat shularning rasmi kutiladi
# BUGUN19 §1 (S130 = b + ovozsiz, 2026-09-26): rasm TEST kanalga yuklanadi (lichka toza qoladi).
# BUGUN148 (2026-10-13, foydalanuvchi: «deploydan keyin qayta jo'natmasin, yozib qo'ysin sheets'da»): file_id Elonlar'ning
# `rasm_file_id` ustuniga yoziladi — JSON {kalit: file_id}. Kalit: rasm URL'i (toza); 2+ rasmli e'londa 1-rasm «suring» belgili —
# kalit `URL#b`. Kalit rasm manzili bilan bog'liq: rasm almashsa eski file_id o'zi tushib qoladi (jadvalga qayta yozilganda).
# 🔴 Ombor botining file_id si bu botda ISHLAMAYDI — ko'chirilmaydi, Store boti o'zi yuklaydi.
RASM_YUKLASH_CHAT = TEST_CHANNEL
_RASM_ZAXIRA_CHAT = ADMIN_ID  # TEST kanal rad etsa (bot a'zo/admin emas, kanal yo'q) — lichka, ovozsiz (BUGUN16 yo'li)
_RASM_CHAT = {'id': RASM_YUKLASH_CHAT}
_RASM_XATO_KUTISH = 3600      # yuklanmagan rasm 1 soat qayta urinilmaydi
_RASM_FID = {}                # kalit (rasm URL / URL#b) → Telegram file_id
_RASM_EGA = {}                # kalit → e'lon raqami (file_id ni jadvalga yozish uchun)
_URL_FID = {}                 # kanal / albom rasmi (yuklangan manzil) → file_id (BUGUN148 2-urinish)
_fid_saqla_lock = threading.Lock()
_RASM_XATO = {}               # rasm URL → yuklanmagan vaqti
_rasm_navbat = []             # yuklash navbati (URL)
_rasm_kutilmoqda = set()      # navbatda yoki yuklanayotgan URL'lar
_rasm_ishchi = {'bor': False}
_rasm_lock = threading.Lock()


def _inline_norm(s):
    """Qidiruv uchun: kichik harf, bo'shliq/tinish belgisiz («Pixel 10 Pro XL» = «pixel10proxl»)."""
    return re.sub(r'[\W_]+', '', str(s or '').lower())


def inline_nomlari(elon, models):
    """E'lonning qidiriladigan nomlari — o'z nomi va model nomi, uz va ru.
    BUGUN17: nomga brend qo'shilmaydi, shuning uchun «anker nano» ham topilsin — brend + nom alohida."""
    model = (models or {}).get(str(elon.get('specId', '') or ''), {})
    nomlar = [elon_nomi(elon, model, 'uz'), elon_nomi(elon, model, 'ru'),
              model_display_name(model, 'uz'), model_display_name(model, 'ru')]
    brand = model_brand(model)
    if brand and not brendsizmi(brand):
        nomlar += [f'{brand} {n}' for n in nomlar if n and not n.lower().startswith(brand.lower())]
    return nomlar


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


# 9000 (2026-10-25, Owner: «@bot so'z → darrov natija»): «telefon», «zaryad» nomda yo'q — e'lonning TURKUMI nomi ham
# qidiriladi (Turkumlar varag'i: «Zaryadlovchilar», «Kabellar», «Наушники»; turkumsiz — bo'lim nomi TUR_NOMI). Turkum nomida
# yo'q so'zlar — bo'lim bo'yicha, so'z boshi mos kelsa («telefonlar», «чехол»). Nomda bo'lsa ham topiladi («phone» — iPhone).
INLINE_TUR_SOZ = {
    'phone': ('telefon', 'телефон', 'phone', 'smartfon', 'смартфон'),
    'camera': ('kamera', 'камера', 'camera'),
    'accessory': ('aksessuar', 'аксессуар'),
    'case': ('chexol', 'чехол', 'case'),
    'part': ('zapchast', 'запчаст', 'ehtiyot'),
}
# 9000: e'lon → (bo'lim, toza nomlar, toza turkum nomlari) — har harf bosilganda qayta hisoblanmaydi. Jadval qayta yuklansa
# (vaqt, seriyalar, turkumlar, modellar boshqa) — kesh yangidan.
_INLINE_IDX = {'v': None, 'd': {}}


def _inline_turkum(e, models, tur):
    """E'lon turkumining nomlari (uz, ru): model → lineyka → Turkumlar varag'i; topilmasa — bo'lim nomi."""
    model = (models or {}).get(str(e.get('specId', '') or ''), {})
    sk = str((model or {}).get('series', '') or '')
    ser = next((s for s in (_ELON_CACHE.get('series') or []) if str(s.get('key', '')) == sk), None) or {}
    tk = str(ser.get('turkum', '') or '').strip().lower()
    t = next((t for t in (_ELON_CACHE.get('turkumlar') or []) if tk and str(t.get('key', '')).strip().lower() == tk), None)
    nomlar = [t.get('labelUz'), t.get('labelRu')] if t else list(TUR_NOMI.get(tur, ('', '', ''))[1:])
    return [_inline_norm(n) for n in nomlar if n]


def _inline_tur_sozmi(w, tur):
    return any(w.startswith(p) for p in INLINE_TUR_SOZ.get(tur, ()))


def _inline_ind(e, models):
    c = _ELON_CACHE
    v = (c.get('time'), id(c.get('series')), id(c.get('turkumlar')), id(models))
    if _INLINE_IDX['v'] != v:
        _INLINE_IDX['v'], _INLINE_IDX['d'] = v, {}
    k = tuple(str(e.get(x, '') or '') for x in ('num', 'specId', 'nameUz', 'nameRu', 'name'))
    r = _INLINE_IDX['d'].get(k)
    if r is None:
        tur = elon_turi(e, models or {})
        r = (tur, [_inline_norm(n) for n in inline_nomlari(e, models) if n], _inline_turkum(e, models, tur))
        _INLINE_IDX['d'][k] = r
    return r


def inline_topish(query, by_num, models):
    """So'rov bo'yicha FAOL e'lonlar (yangisi birinchi). Sotilgan/o'chirilgan/kutilayotgan — yo'q.
    '' — hammasi; '248' / '#248' / '№248' — shu raqamli e'lon BIRINCHI, keyin nomida shu son borlari
    («15» — №15 va iPhone 15'lar); matn — nomida HAMMA so'zlar bor e'lonlar (harf katta-kichikligi,
    uz/ru, bo'shliq farqsiz). Turkum / bo'lim so'zi («telefon», «zaryad», «kabel», …) — nomda bo'lmasa ham mos (9000)."""
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
        tur, nomlar, turkum = _inline_ind(e, models)
        turdagi = {w for w in sozlar if _inline_tur_sozmi(w, tur) or (len(w) >= 3 and any(w in t for t in turkum))}
        if any(all(w in n or w in turdagi for w in sozlar) for n in nomlar):
            natija.append(e)
    return natija


def _ik_olcham(url, tr):
    """ImageKit rasmiga o'lcham (tr=…) qo'shadi; boshqa manzil o'zgarmaydi. Suv belgisi joyi («#nb=…») avval kesiladi —
    aks holda «?tr=» fragmentdan keyin qolib, Telegram o'lchamsiz asl rasmni olardi (B36)."""
    url = belgi_ajrat(url)[0]
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


def _chat_xatosi(r):
    """Javob rasm emas, CHAT sababli rad etilganmi (kanal yo'q, bot a'zo/admin emas)."""
    t = str((r or {}).get('description', '')).lower()
    return (r or {}).get('error_code') in (400, 403) and any(
        s in t for s in ('chat not found', 'not a member', 'not enough rights', 'forbidden',
                         'need administrator', 'have no rights', 'chat_write_forbidden'))


def _fid_manba(kalit):
    """Kalit → yuklanadigan manzil: `URL#b` — «suring» belgili 1-rasm, aks holda oddiy w-1600."""
    if kalit.endswith('#b'):
        return keyingi_belgi(_ik_olcham(kalit[:-2], 'w-1600,q-85'))
    return _ik_olcham(kalit, 'w-1600,q-85')


def inline_kalitlari(elon):
    """E'lonning inline rasm kalitlari (≤10, tartib bilan): 2+ rasmda 1-rasm — belgili (`URL#b`)."""
    rasmlar = images_of(elon)[:10]
    if len(rasmlar) >= 2 and KEYINGI_BELGI:
        rasmlar[0] += '#b'
    return rasmlar


def _fid_h(manba):
    """Jadvaldagi kalit — yuklangan manzilning qisqa izi (manzil uzun: logo + belgi layer'lari; GET so'rovi sig'sin).
    Manzil o'zgarsa (rasm almashdi, logo joyi, belgi) — iz ham o'zgaradi, eski file_id o'z-o'zidan tashlanadi."""
    return hashlib.sha1(manba.encode('utf-8')).hexdigest()[:12]


def kanal_manbalari(elon):
    """Kanal posti rasmlari — Telegram yuklaydigan manzillar (logo; 2+ rasmda 1-si «suring» belgili), ≤10."""
    src = belgi_src(elon)
    return [src.get(u, u) for u in images_of(elon)[:10]]


def albom_manbalari(elon):
    """OLX albomi rasmlari — logo bilan, belgisiz, ≤10."""
    return [belgili(t, j) for t, j in rasm_joylari(elon)][:10]


def _fid_xom(elon):
    """Jadvaldagi `rasm_file_id` — {iz: file_id}."""
    xom = elon.get('rasm_file_id')
    try:
        d = json.loads(xom) if isinstance(xom, str) and xom.strip() else (xom if isinstance(xom, dict) else {})
    except Exception:
        d = {}
    return {k: v for k, v in d.items() if isinstance(v, str) and v} if isinstance(d, dict) else {}


def _fid_jadvaldan(elon):
    """Jadvaldagi `rasm_file_id` dan HOZIRGI rasmlarga (inline, kanal, albom) to'g'ri kelganlarini xotiraga oladi —
    almashgan rasmniki tashlanadi. Qaytaradi: {iz: file_id} — jadvaldagi (tozalangan) holat."""
    d = _fid_xom(elon)
    num = _num_int(elon)
    qolgan = {}
    for k in inline_kalitlari(elon):
        _RASM_EGA[k] = num
        h = _fid_h(_fid_manba(k))
        if h in d:
            qolgan[h] = d[h]
            _RASM_FID.setdefault(k, d[h])
    for m in kanal_manbalari(elon) + albom_manbalari(elon):
        h = _fid_h(m)
        if h in d:
            qolgan[h] = d[h]
            _URL_FID.setdefault(m, d[h])
    return qolgan


def _fid_hozir(elon):
    """Xotiradagi hozirgi rasmlar file_id'si — {iz: file_id}."""
    hozir = {}
    for k in inline_kalitlari(elon):
        if k in _RASM_FID:
            hozir[_fid_h(_fid_manba(k))] = _RASM_FID[k]
    for m in kanal_manbalari(elon) + albom_manbalari(elon):
        if m in _URL_FID:
            hozir[_fid_h(m)] = _URL_FID[m]
    return hozir


def fid_olindi(num, manbalar, fidlar):
    """Kanal / albom yuborilgach Telegram bergan file_id'lar xotiraga. Soni mos kelmasa — olinmaydi. True — yangisi bor."""
    if not manbalar or len(manbalar) != len(fidlar) or not all(fidlar):
        return False
    yangi = False
    for m, f in zip(manbalar, fidlar):
        if _URL_FID.get(m) != f:
            _URL_FID[m] = f
            yangi = True
    return yangi


def _fid_num_saqla(num):
    """E'lon rasmlarining file_id'larini qatoriga (`rasm_file_id`) yozadi — faqat jadvaldagidan farq qilsa."""
    with _fid_saqla_lock:
        with _elon_cache_lock:
            elon = _ELON_CACHE['by_num'].get(str(num))
        if not elon:
            return
        _fid_jadvaldan(elon)
        hozir = _fid_hozir(elon)
        if not hozir or hozir == _fid_xom(elon):
            return
        qiymat = json.dumps(hozir, separators=(',', ':'))
        if _sheets_update({'num': int(num), 'rasm_file_id': qiymat}):
            with _elon_cache_lock:
                elon['rasm_file_id'] = qiymat
        else:
            logger.error(f'rasm_file_id: №{num} jadvalga yozilmadi')


def fid_saqla_fonda(num):
    threading.Thread(target=_fid_num_saqla, args=(num,), daemon=True).start()


def _fid_saqla(kalitlar):
    """Yangi yuklangan inline file_id larni e'lon qatoriga yozadi. Faqat o'zgargan bo'lsa."""
    for num in {_RASM_EGA.get(k) for k in kalitlar} - {None}:
        _fid_num_saqla(num)


def _rasm_yubor(guruh):
    """≤10 rasmni TEST kanalga (RASM_YUKLASH_CHAT) ovozsiz yuboradi, file_id'larni oladi, xabarlarni o'chiradi.
    Kanal chat sababli rad etsa — shu seans oxirigacha lichkaga (_RASM_ZAXIRA_CHAT), ovozsiz."""
    chat = _RASM_CHAT['id']
    if len(guruh) == 1:
        r = _rasm_tg('sendPhoto', {'chat_id': chat, 'photo': _fid_manba(guruh[0]),
                                   'disable_notification': True})
        xabarlar = [r.get('result')] if r.get('ok') else None
    else:
        r = _rasm_tg('sendMediaGroup', {'chat_id': chat, 'disable_notification': True,
                                        'media': [{'type': 'photo', 'media': _fid_manba(u)} for u in guruh]})
        xabarlar = r.get('result') if r.get('ok') else None
    if not xabarlar and chat != _RASM_ZAXIRA_CHAT and _chat_xatosi(r):
        logger.error(f"inline rasm: {chat} rad etdi ({r.get('description')}) — endi lichkaga, ovozsiz")
        _RASM_CHAT['id'] = _RASM_ZAXIRA_CHAT
        return _rasm_yubor(guruh)
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
        o = _rasm_tg('deleteMessages', {'chat_id': chat, 'message_ids': ids})
        if not o.get('ok'):             # kanalda «Delete messages» huquqi yo'q — rasm qolib ketadi
            logger.warning(f"inline rasm o'chirilmadi ({chat}): {o.get('description')}")


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
            _fid_saqla(guruh)
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
    xotira = elon_qavs(elon)   # BUGUN260-7: xotira + xususiyat
    rang = clean_color(elon.get('color') or '')
    sarlavha = nom + (f' ({xotira})' if xotira else '') + (f' {rang}' if rang else '')
    narx = str(elon.get('price', '') or '').replace('.0', '')
    cycle = str(elon.get('cycle', '') or '').replace('.0', '')
    cond_uz, _cond_ru, _emoji = holati_matni(elon.get('condition', 'used') or 'used', cycle)
    izoh = ' · '.join(x for x in ((f'{narx}$' if narx else ''), cond_uz, f'№{num}') if x)

    kalitlar = inline_kalitlari(elon)
    _fid_jadvaldan(elon)
    if rasmlar and all(k in _RASM_FID for k in kalitlar):
        src = {u: f'tg://photo?id=r{i}' for i, u in enumerate(rasmlar)}
        return {
            'type': 'article',
            'id': f'r{num}',
            'title': sarlavha,
            'description': izoh,
            'thumbnail_url': _ik_olcham(rasmlar[0], 'w-200,q-70'),
            'input_message_content': {'rich_message': {
                'html': build_rich_html(elon, models, premium=False, rasm_src=src),
                'media': [{'id': f'r{i}', 'media': {'type': 'photo', 'media': _RASM_FID[k]}}
                          for i, k in enumerate(kalitlar)],
            }},
        }
    return _inline_karta(num, elon, model, sarlavha, izoh)


def _inline_karta(num, elon, model, sarlavha=None, izoh=None):
    """Rasmi hali yuklanmagan e'lon — article (ro'yxatda sarlavha + «narx · holat · №»).

    BUGUN43 (2026-09-29): ilgari bu yerda _share_result (type=photo) qaytardi. Telegram ro'yxatida
    photo natijaning title/description'i ko'rinmaydi — «Photo» deb chiqadi (pixel 8 pro, 1-natija).
    Endi article: xabar matni — o'sha qisqa HTML, rasm — katta havola-ko'rinish, tugma — o'sha.
    Ulashish (savePreparedInlineMessage) _share_result'ni o'zgarishsiz ishlatadi.
    """
    karta = _share_result(num, elon, model)
    if not karta:
        return None
    if sarlavha is None:
        nom = elon_nomi(elon, model, 'uz')
        xotira = elon_qavs(elon)   # BUGUN260-7: xotira + xususiyat
        rang = clean_color(elon.get('color') or '')
        sarlavha = nom + (f' ({xotira})' if xotira else '') + (f' {rang}' if rang else '')
    if izoh is None:
        narx = str(elon.get('price', '') or '').replace('.0', '')
        cycle = str(elon.get('cycle', '') or '').replace('.0', '')
        cond_uz, _r, _e = holati_matni(elon.get('condition', 'used') or 'used', cycle)
        izoh = ' · '.join(x for x in ((f'{narx}$' if narx else ''), cond_uz, f'№{num}') if x)
    return {
        'type': 'article',
        'id': karta['id'],
        'title': sarlavha,
        'description': izoh,
        'thumbnail_url': _ik_olcham(images_of(elon)[0], 'w-200,q-70'),   # 9000: ro'yxatda kichik rasm (rich bilan bir xil)
        'input_message_content': {
            'message_text': karta['caption'],
            'parse_mode': 'HTML',
            'link_preview_options': {'url': karta['photo_url'], 'prefer_large_media': True,
                                     'show_above_text': True},
        },
        'reply_markup': karta['reply_markup'],
    }


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

        for e in sahifa:
            _fid_jadvaldan(e)       # jadvaldagi file_id — qayta yuklanmaydi (BUGUN148)
        urls = [k for e in sahifa for k in inline_kalitlari(e)]
        rasm_navbatga(urls)
        # 9000: faqat birinchi ekrandagilar kutiladi (navbatda ular oldinda) — «telefon» 50 ta natijada 500 rasm kutilmaydi
        kut = [k for e in sahifa[:INLINE_EKRAN] for k in inline_kalitlari(e)]
        oxiri = time.monotonic() + INLINE_KUTISH
        while any(u in _rasm_kutilmoqda for u in kut) and time.monotonic() < oxiri:
            await asyncio.sleep(0.25)

        natijalar = [n for n in (inline_natija(e, models) for e in sahifa) if n]
        hammasi_rich = all('rich_message' in n.get('input_message_content', {}) for n in natijalar)
        r = await blok(req.post, f'{TG_API}/answerInlineQuery', json={
            'inline_query_id': iq.get('id'),
            'results': natijalar,
            'next_offset': keyingi,
            'cache_time': 30 if hammasi_rich else 0,   # karta bo'lsa keyingi so'rovda rich chiqsin
            'is_personal': False,
        }, timeout=15)
        # Rich natija rad etilsa (hali jonli sinalmagan) — ro'yxat bo'sh qolmasin: shu so'rovga faqat kartalar
        javob = r.json() if hasattr(r, 'json') else {}
        if not javob.get('ok') and any('rich_message' in n.get('input_message_content', {}) for n in natijalar):
            logger.error(f"inline rich rad etildi: {javob.get('description')} — kartalar bilan qayta")
            # 9000: zaxira ham article karta (BUGUN43) — photo natija ro'yxatda nomsiz «Photo» bo'lib chiqardi
            kartalar = [k for k in (_inline_karta(_num_int(e), e, (models or {}).get(str(e.get('specId', '') or ''), {}))
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
    if not isinstance(data, dict) or not _update_yangimi(data.get('update_id')):
        return web.json_response({'ok': True})   # Telegram qayta yuborgan update — bir marta ishlanadi (T2)
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
            asyncio.create_task(blok(kanal_chiqdi, data['chat_member']))   # BUGUN147: qatnashchi kanaldan chiqdi
            mijoz_kanal_qayd(data['chat_member'])   # 3176: Mijozlar.kanal_obuna (faqat navbatga — tarmoqsiz)
            return

        message = data.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        contact = message.get('contact')

        # B33 (BUGUN42): guruhda /guruh (faqat admin) — mavzularni ochadi. Sozlangan guruhda faqat admin xabari qabul
        # qilinadi; chat_id — mavzuli (Joy), javob o'sha mavzuga ketadi. Boshqa guruhlar — eskicha.
        guruhdan = False
        if message.get('chat', {}).get('type') in ('group', 'supergroup'):
            buyruq = text.split(' ')[0].split('@')[0]
            if buyruq == '/guruh':
                if user.get('id') == ADMIN_ID and text.split()[1:2] == ['namuna']:   # 3214.1: fonda (T1 — 10 namuna + xulosa)
                    asyncio.create_task(blok(guruh_namuna, chat_id, Joy(chat_id, message.get('message_thread_id'))))
                elif user.get('id') == ADMIN_ID:
                    await blok(guruh_sozla, chat_id, bool(message['chat'].get('is_forum')),
                               Joy(chat_id, message.get('message_thread_id')),
                               text.split()[1:2] == ['yangi'])   # 3213.1: «/guruh yangi» — hammasi noldan
                return
            if GURUH.get('id') and chat_id == GURUH['id']:
                if user.get('id') != ADMIN_ID:
                    return
                guruhdan = True
                chat_id = Joy(chat_id, message.get('message_thread_id'))
                if text.startswith('/') and '@' in text.split(' ')[0]:
                    text = buyruq + text[len(text.split(' ')[0]):]
        adm = chat_id == ADMIN_ID or guruhdan

        cq = data.get('callback_query', {})
        if cq:
            cq_msg = cq.get('message', {})
            cq_chat = cq_msg.get('chat', {}).get('id')
            cq_user = cq.get('from', {})
            cq_adm = cq_user.get('id') == ADMIN_ID and admin_mi(cq_chat)
            if cq_adm and cq_chat != ADMIN_ID:
                cq_chat = Joy(cq_chat, cq_msg.get('message_thread_id'))
            cq_data = cq.get('data', '')
            cq_id = cq.get('id')
            await blok(req.post, f'{TG_API}/answerCallbackQuery',
                       json={'callback_query_id': cq_id, **({'text': "✔️ Bu bosqich bajarilgan — holat xabar matnida"}
                                                            if cq_data == 'bh:-' else {})}, timeout=5)
            if cq_data == 'kk_qatnash' and cq_chat:   # BUGUN147: /start dagi konkurs bloki tugmasi
                await start_konkurs_flow(cq_chat, cq_user)
            if cq_data.startswith('yon:') and cq_chat:   # BUGUN213: oddiy /start dagi 3 yo'nalish tugmasi
                await blok(yonalish_post, cq_chat, cq_data[4:])
            if cq_data == 'check_member' and cq_chat:
                yet = await blok(yetishmagan_kanallar, cq_chat)
                if not yet:
                    await start_konkurs_flow(cq_chat, cq_user)
                else:
                    await blok(send_msg, cq_chat,
                        "❌ Hali a'zo emassiz! Avval kanallarga a'zo bo'ling.\n"
                        "❌ Вы ещё не подписаны! Сначала подпишитесь на каналы.",
                        {"inline_keyboard": azo_kanal_tugmalari(yet) + [
                            [{"text": "✅ A'zo bo'ldim", "callback_data": "check_member"}]
                        ]})
            # G11.2: /toplam va /katalog tasdiqi (faqat admin lichkasi)
            if cq_data.startswith(('kanal_ok:', 'kanal_no:')) and cq_adm:
                asyncio.create_task(blok(kanal_tasdiq, cq_chat, cq_data.split(':', 1)[1], cq_data.startswith('kanal_ok:')))
            # B28: «🖼 Kollajga o'tkazish» / «🎞 Slaydga qaytarish» (faqat admin lichkasi)
            if cq_data.startswith(('kollaj:', 'slayd:')) and cq_adm:
                asyncio.create_task(blok(kollaj_almashtir, cq_chat, cq.get('message', {}).get('message_id'), cq_data))
            # BUGUN208: «🔓 Bronni bekor qilish» (faqat admin lichkasi)
            if cq_data.startswith('bron_och:') and cq_adm:
                asyncio.create_task(bron_bekor_tugma(cq_chat, cq_data))
            # BUGUN227: buyurtma holati — «✅ To'lov keldi» / «🚚 Yo'lda» / «📦 Yetkazildi» (faqat admin lichkasi)
            if cq_data.startswith('bh:') and cq_adm:
                asyncio.create_task(buyurtma_holat_tugma(cq_chat, cq.get('message', {}).get('message_id'), cq_data,
                                                         cq.get('message') or {}))
            # BUGUN252 §4: «№213 sotilgan — baribir qo'shaymi?» (🖼 Rasmlar mavzusi)
            if cq_data.startswith(('rqo:', 'rqy:')) and cq_adm:
                asyncio.create_task(blok(rasm_baribir_tugma, cq_chat, cq_msg.get('message_id'), cq_data))
            # B34: «🗑 Postni o'chirish» (faqat admin lichkasi)
            if cq_data.startswith('pochir') and cq_adm:
                asyncio.create_task(blok(post_ochir_tugma, cq_chat, cq.get('message', {}).get('message_id'), cq_data))
            # BUGUN296: mijoz — «🧾 To'landim — chek yuborish» (chk:) va «bu chek qaysi buyurtma?» (chm:); faqat o'z lichkasida
            if cq_data.startswith(('chk:', 'chm:')) and cq_user.get('id') and cq_chat == cq_user.get('id'):
                asyncio.create_task(chek_tugma(cq_user['id'], cq_data, cq_user))
            return

        if not chat_id:
            return

        # BUGUN10 §3b: admin «🔔 Yangi istak» xabariga reply qilsa — javob mijozga (rasm-e'lon yasashdan OLDIN
        # tekshiriladi: istakka rasm bilan javob chala e'lon bo'lib qolmasin). Buyruqlar (/…) — eski yo'lda. Fonda (T1).
        if adm and message.get('reply_to_message') and not text.startswith('/'):
            manzil = istak_javob_manzil(message.get('reply_to_message'))
            if manzil:
                asyncio.create_task(blok(istak_javob_yubor, chat_id, message, manzil))
                return

        # BUGUN252 §4: «🖼 Rasmlar» mavzusi — e'lon ochilmaydi (rasm omborga); buyruqlar (/…) — eski yo'lda
        if guruhdan and rasmlar_mavzusi(chat_id) and not text.startswith('/'):
            await handle_rasmlar_xabar(chat_id, message)
            return

        # BUGUN296: lichkada rasm / rasm-fayl / PDF — mijozning cheki (admin bo'lsa — faqat o'zi «chek kutilmoqda» qo'ygan bo'lsa,
        # ya'ni sinab ko'rayotgan bo'lsa; aks holda admin rasmi eskicha e'lon yaratadi)
        if (message.get('chat', {}).get('type') == 'private' and user.get('id') == chat_id
                and _chek_fayl(message) is not None and (not adm or await blok(_chek_kutyapti, chat_id))):
            asyncio.create_task(chek_qabul(chat_id, user, message))
            return

        # ── ADMIN rasm yuborsa ──
        photo = message.get('photo')
        if photo and adm:
            largest = photo[-1]  # eng katta o'lcham
            file_id = largest.get('file_id', '')
            mgid = message.get('media_group_id')
            # #6.5: Konkurs sovrin rasmi rejimida bo'lsa — elon emas, sovrin rasmi saqlaymiz
            st = user_states.get(chat_id, {})
            if st.get('step') == 'konkurs_photo':
                await handle_konkurs_photo(chat_id, file_id, mgid)
                return
            # Aks holda — eski logika: chala elon yaratamiz
            await handle_admin_photo(chat_id, file_id, mgid, message.get('message_id', 0))
            return

        if text.startswith('/yubor') or text.startswith('/elon'):
            if not adm:
                return
            await send_new_elons(chat_id, text)
            return

        # B34 (BUGUN42): demo saytni Telegram ICHIDA ochish tugmasi — «📣 Yuborish» (B29) initData bilan ishlaydi, oddiy
        # brauzerda initData yo'q. Manzil faqat Render env DEMO_URL da (repo ochiq — demo havolasi kodga yozilmaydi).
        if text.startswith('/demo') and adm:
            demo = os.environ.get('DEMO_URL', '').strip()
            if not demo.startswith('https://'):
                await blok(send_msg, chat_id, "DEMO_URL sozlanmagan (Render → Environment → DEMO_URL = demo sayt manzili, https://…).")
            else:
                await blok(send_msg, chat_id, "🧪 Demo sayt — Telegram ichida (admin):",
                           {"inline_keyboard": [[{"text": "🧪 Demo'ni ochish", "web_app": {"url": demo}}]]})
            return

        # G11.0: Rich Message sinovi — faqat admin, faqat lichka + TEST kanal. Fonda (T1).
        if text.startswith('/richtest') and adm:
            m_num = re.search(r'\d{1,6}', text)
            if not m_num:
                await blok(send_msg, chat_id, "Foydalanish: /richtest 248")
                return
            asyncio.create_task(blok(richtest, chat_id, m_num.group(0)))
            return

        # G11.2: kanal buyruqlari (admin). Fonda (T1).
        if adm and text.split(' ')[0] in ('/toplam', '/katalog', '/post', '/yana', '/postochir'):
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

        # 3184.5: kanalga ommaviy yuborish (eski e'lonlar) va 15 kunlik tomchi holati — fonda
        if adm and text.split() and text.split()[0].split('@')[0] in ('/ommaviy', '/tomchi'):
            asyncio.create_task(blok(kanal_navbat_buyruq, chat_id, text))
            return

        # F1: do'kon hisoboti. Fonda — Sheets hisobi sekin, webhook kutmasin (T1).
        if text.startswith('/stat') and adm:
            asyncio.create_task(handle_stat(chat_id, text))
            return

        if text.startswith('/tozala') and adm:
            # Fonda ishlaydi — Telegram javobni kutmasin (aks holda buyruqni qayta yuboradi)
            asyncio.create_task(handle_tozala(chat_id, text))
            return

        # BUGUN108: konkurs boshqaruvi (holat, tugatish, bekor, davom, tarqatma) — fonda
        if adm and text.split() and text.split()[0].split('@')[0] in _KK_BUYRUQLAR:
            asyncio.create_task(konkurs_buyruq(chat_id, text))
            return
        # BUGUN137: rebrending xabari (eski bot nomidan) — /forwardxabari, /rebrending sinov | hammaga — fonda
        if adm and text.split() and text.split()[0].split('@')[0] in _REBREND_BUYRUQLAR:
            asyncio.create_task(rebrend_buyruq(chat_id, text))
            return

        if text.startswith('/start'):
            parts = text.split(' ', 1)
            deep = parts[1].strip() if len(parts) > 1 else ''
            # BUGUN173: yangi botga /start → Mijozlar.yangi_bot (fonda; 7:30 konkurs e'lonidan chetda qoladi)
            # 3176: + manba — /start parametri (konkurs posti, e'lon…); chek_<raqam> — buyurtma raqami, manba emas
            if message.get('chat', {}).get('type') == 'private':
                asyncio.create_task(mijoz_bot_qayd(user, 'yangi', manba='' if deep.startswith('chek_') else deep))
            if deep.startswith('chek_') and message.get('chat', {}).get('type') == 'private' and user.get('id'):
                # BUGUN296: saytdagi «🧾 To'landim — chek yuborish» → ?start=chek_<buyurtma raqami> (konkurs / hub chiqmaydi)
                asyncio.create_task(chek_boshla(user['id'], user, deep[5:].upper()))
            elif deep in ('konkurs', 'konkurs_y'):
                if deep == 'konkurs_y' and user.get('id'):   # BUGUN147: saytda logo 3 marta — yashirin konkursga kalit
                    _kk_kalitli.add(user['id'])
                await start_konkurs_flow(chat_id, user)
            else:
                # BUGUN213: payload YO'Q + lichka → 3 yo'nalish; maxsus havolali (?start=<payload>) — eskicha, 3 yo'nalishsiz
                # BUGUN224: ?start=mobile | y_mobile (kanal havolasi) — o'sha yo'nalishni ochadigan bitta tugma
                if deep in YON_PAYLOAD and message.get('chat', {}).get('type') == 'private':
                    await blok(send_yon_tugma, chat_id, YON_PAYLOAD[deep])
                elif not deep and message.get('chat', {}).get('type') == 'private':
                    await blok(send_bot_hub, chat_id)
                else:
                    await blok(send_start, chat_id)
                # BUGUN147: aktiv va ochiq konkurs bo'lsa — konkurs xabari (fonda, /start kechikmasin)
                if message.get('chat', {}).get('type') == 'private':
                    asyncio.create_task(blok(konkurs_start_xabari, chat_id))

        elif text == '/konkurs':
            # ADMIN: sovrin rasmi yig'ish rejimi (hech narsa demay rasm kutadi).
            # Oddiy mijoz: konkursda qatnashish flow'i.
            if adm:
                user_states[chat_id] = {'step': 'konkurs_photo'}
                # Javob matni YO'Q — bot jimgina rasm kutadi (docx #9)
            else:
                await start_konkurs_flow(chat_id, user)

        elif text == '/konkursyuborish' and adm:
            # ADMIN: aktiv konkurs anonsini kanalga yuboradi.
            _konkurs_cache['time'] = 0
            k = await blok(get_konkurs)
            if not k or not k.get('id') or not _kk_aktivmi(k):
                await blok(send_msg, chat_id, "😕 Hozirda aktiv konkurs yo'q.")
            elif _kk_yashirinmi(k) and not _kk_sinovmi(k.get('prize')):
                # BUGUN147: yashirin konkurs anonsi kanalga ketsa — tugma bosgan obunachi konkursni ko'rmaydi
                await blok(send_msg, chat_id, "❌ Konkurs oynasi yashirin — anons kanalga yuborilmadi.\n"
                                              "Avval oching: /konkursochiq, keyin qayta /konkursyuborish")
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
                # Sana -> Toshkent, "25.07.2026 20:00". Zonasiz satr — Toshkent vaqti (ilgari UTC deb +5 qo'shilardi)
                def _fmt_end(s):
                    ts = _parse_end_time(s)
                    return _kk_vaqt(ts) if ts else str(s)
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
                kanal = TEST_CHANNEL if _kk_sinovmi(k.get('prize')) else CHANNEL   # sinov — asosiy kanalga emas
                mid = await blok(send_konkurs_channel_post, kanal, anons, pics, markup)
                await blok(send_msg, chat_id, f"✅ Konkurs anonsi kanalga yuborildi: {kanal}")
                # 3185: saytdagi «Do'stlarga ulashish» shu postni ulashadi — havola konkursga o'zi yoziladi
                havola = post_havola(kanal, mid)
                if havola and '/t.me/c/' not in havola:   # yopiq kanal posti — do'st ocholmaydi
                    r = await _kk_sorov('konkursPostHavola', urinish=2, id=k['id'], havola=havola)
                    if r and r.get('ok'):
                        _konkurs_cache['time'] = 0
                        await blok(send_msg, chat_id, f"🔗 Saytdagi «Do'stlarga ulashish» endi shu postni ulashadi:\n{havola}")
                    else:
                        await blok(send_msg, chat_id, f"⚠️ Post havolasi saytga yozilmadi — admin panelda qo'lda qo'ying:\n{havola}")

        elif text == '/konkurstimer' and adm:
            # Admin zaxira: aktiv konkurs taymerini qayta o'rnatadi + holatni ko'rsatadi
            # (taymer — faqat signal; tugatishda baribir jadvaldagi holat tekshiriladi — BUGUN108)
            _konkurs_cache['data'] = None
            _konkurs_cache['time'] = 0
            k = await blok(get_konkurs)
            r = konkurs_taymer_qoy(k)
            kid = html_escape(str((k or {}).get('id', '')))
            if r in ('qoyildi', 'bor'):
                end = _parse_end_time(k.get('end_time'))
                taymer = "o'rnatildi" if r == 'qoyildi' else "allaqachon bor"
                await blok(send_msg, chat_id,
                    f"✅ Aktiv konkurs: {kid}\n"
                    f"🎁 {html_escape(k.get('prize', ''))}\n"
                    f"⏰ Tugash: {_kk_vaqt(end)} (Toshkent)\n"
                    f"⏳ Taymer {taymer} — vaqti kelganda avtomatik tugaydi.\n"
                    f"Holat: /konkursholat")
            elif r == 'kechikdi':
                await blok(send_msg, chat_id,
                    f"⚠️ Konkurs {kid}: tugash vaqti 6 soatdan ko'p o'tgan — o'zim tugatmayman.\n"
                    f"Tugatish: /konkurstugat {kid}\nBekor qilish: /konkursbekor {kid}")
            elif r == 'muddatsiz':
                await blok(send_msg, chat_id, "ℹ️ Aktiv konkursning tugash vaqti belgilanmagan.")
            else:
                await blok(send_msg, chat_id, "ℹ️ Hozircha aktiv konkurs yo'q.")

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
            elif message.get('chat', {}).get('type') == 'private' and _eski_tugmami(text):
                # BUGUN226: eski reply-klaviatura tugmasi — yangi 3 tugmali /start xabari, eski klaviatura yopiladi
                await blok(eski_mijoz_javob, chat_id)
            elif not guruhdan:   # B33: guruhda (admin o'zi yozgan izoh) — jim
                # E4: noma'lum xabar — ilgari bot umuman javob bermasdi
                # BUGUN226: lichkada — eski klaviatura yopiladi, tugmalar — yangi 3 yo'nalish (web_app)
                lichka = message.get('chat', {}).get('type') == 'private'
                if lichka:
                    await blok(eski_klaviatura_olib_tashla, chat_id)
                await blok(send_msg, chat_id, NOMALUM_XABAR, BOT_HUB_KB if lichka else START_KB)
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
    if not k or not k.get('id') or not _kk_aktivmi(k) or not _kk_korsatsinmi(k, user.get('id', chat_id)):
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
      2) Kanal eloni — rich (kanal posti bilan bir xil, POST_NARX sukuti) + premium emoji (kanalga qo'lda joylash uchun; 3199)

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
    images = [belgili(t, j) for t, j in rasm_joylari(elon)]   # A26 (K2): OLX'ga ketadigan rasmlar — suv belgisi bilan

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
    # 3199 (Owner, 2026-10-26): kanal ko'rinishi — rich (kanal posti bilan bir xil; 3200 dan narx — bullet), premium emoji bilan: Telegram
    # custom emoji'ni lichka / guruhga ruxsat beradi (bot egasi Premium), kanalga — yo'q. 1-rasm: logo + «›››» belgisi.
    # Rich rad etilsa — eski caption + albom (quyida).
    send_msg(admin_chat, "📋 <b>KANAL ELONI</b> — Kanalga joylashingiz mumkin 👇")
    mid, xato = send_rich(admin_chat, build_rich_html(elon, models, premium=True, belgi=True))
    if mid:
        return
    logger.warning(f"preview №{num}: rich rad etildi ({xato}) — eski ko'rinish")
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
    xotira = html_escape(elon_qavs(elon))   # BUGUN260-7: xotira + xususiyat
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

    images = images_of(elon)   # B36: suv belgisi joyi kesilgan toza manzil
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


async def _json_tana(request):
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


async def konkurs_started_endpoint(request):
    """Sayt konkursni 'active' qilganda — bot tugash taymerini o'rnatadi. Tana kerak emas — signal yetarli:
    konkurs jadvaldan qayta o'qiladi (BUGUN108)."""
    try:
        _konkurs_cache['data'] = None
        _konkurs_cache['time'] = 0
        k = await blok(get_konkurs)
        return web.json_response({'ok': True, 'taymer': konkurs_taymer_qoy(k)})
    except Exception as e:
        logger.error(f'konkurs_started: {type(e).__name__}')
        return web.json_response({'error': 'xato'}, status=500)


async def notify_endpoint(request):
    """Sayt «konkurs tugadi» deydi. 🔴 BUGUN108: tanadagi g'oliblar / matnga ISHONILMAYDI (ilgari istalgan odam
    istalgan «g'olib» xabarini yubora olardi) — faqat konkurs id. Bot holatni jadvaldan oladi va navbatdagi
    xabarlarni yetkazadi; aktiv konkursni bu signal TUGATMAYDI, ikki marta kelsa — ikkinchi xabar ketmaydi."""
    data = await _json_tana(request)
    kid = str((data or {}).get('konkurs_id') or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', kid):
        return web.json_response({'error': 'konkurs_id'}, status=400)
    asyncio.create_task(konkurs_tugat_va_yetkaz(kid, tugat=False, sabab='sayt', manba='sayt'))
    return web.json_response({'ok': True})


_kk_reroll_korilgan = set()


async def reroll_notify_endpoint(request):
    """Reroll qilinganda: eski g'olib (A), yangi g'olib (B), kanal (C) xabarlari.
    🔴 BUGUN108: faqat admin (Telegram initData yoki API_KEY) — ilgari ochiq edi (istalgan odamga bot nomidan xabar);
    bir xil reroll ikkinchi marta kelsa — xabar qayta ketmaydi."""
    data = await _json_tana(request)
    if data is None:
        return web.json_response({'error': 'tana'}, status=400)
    import hmac
    kalit = str(data.get('key') or '')
    admin = check_init_data(data.get('initData') or '') == ADMIN_ID or (
        bool(API_KEY) and bool(kalit) and hmac.compare_digest(kalit.encode(), API_KEY.encode()))
    if not admin:
        return web.json_response({'error': 'Faqat admin'}, status=401)
    yangi = data.get('new') if isinstance(data.get('new'), dict) else {}
    kalit_r = (str(data.get('konkurs_id') or data.get('konkurs_nomi') or ''), str(data.get('orin') or ''),
               str(yangi.get('user_id') or ''))
    if kalit_r in _kk_reroll_korilgan:
        return web.json_response({'ok': True, 'already': True})
    _kk_reroll_korilgan.add(kalit_r)
    asyncio.create_task(blok(send_reroll_notify, data))
    return web.json_response({'ok': True})


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

    # BUGUN163: sinov belgisi — konkurs sovrini (konkurs_nomi) yoki g'olib sovrini «TEST…/🧪» (_kk_sinovmi).
    # Konkurs sovrini (konkurs_nomi) bo'sh/yo'q — haqiqiy ekani tasdiqlanmagan: xavfsiz tomon — sinov kabi (kanalga ketmaydi).
    nomi_xom = str(data.get('konkurs_nomi') or '').strip()
    sinov = _kk_sinovmi(nomi_xom) or _kk_sinovmi(data.get('sovga'))
    ishonchsiz = sinov or not nomi_xom
    admin_uid = str(ADMIN_ID)

    # ── (A) ESKI g'olibga — endi g'olib emas (kanal button) ──
    old_uid = str(old.get('user_id', '') or '')
    if old_uid and ishonchsiz and old_uid != admin_uid:
        logger.info(f'reroll old {old_uid}: sinov/ishonchsiz — mijozga yuborilmadi')
        old_uid = ''
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
    if new_uid and ishonchsiz and new_uid != admin_uid:
        logger.info(f'reroll new {new_uid}: sinov/ishonchsiz — mijozga yuborilmadi')
        new_uid = ''
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
        # sinov — TEST kanal; haqiqiy (tasdiqlangan) — asosiy kanal; tasdiqlanmagan — faqat admin lichkasi
        if sinov:
            c_chat = TEST_CHANNEL or ADMIN_ID     # TEST kanal sozlanmagan bo'lsa — jimgina yo'qolmasin, adminga
        elif nomi_xom:
            c_chat = CHANNEL
        else:
            c_chat = ADMIN_ID
        req.post(f'{TG_API}/sendMessage', json={
            'chat_id': c_chat, 'text': c_text, 'parse_mode': 'HTML',
            'reply_markup': {"inline_keyboard": [[{
                "text": "🛍 Do'kon / Магазин",
                "url": f"https://t.me/{BOT_USERNAME}?startapp"}]]}
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
            None, preview_elon_to_admin, num, admin_joy('olx'))
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
        # 3086: Mini App eski bot orqali ham ochiladi (eski kanal postlari, ulashilgan havolalar) - Telegram initData ni
        # o'sha botning tokeni bilan imzolaydi. Ikkalasi ham Owner'ning boti: yangi token, bo'lmasa ESKI_BOT_TOKEN.
        imzo_ok = False
        for tok in (BOT_TOKEN, ESKI_BOT_TOKEN):
            if not tok:
                continue
            secret = hmac.new(b'WebAppData', tok.encode(), hashlib.sha256).digest()
            calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(calc, h):
                imzo_ok = True
                break
        if not imzo_ok:
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
    images = images_of(elon)   # B36: suv belgisi joyi kesilgan toza manzil
    rasm = images[0] if images else ''
    if not rasm:
        return None       # type=photo uchun rasm SHART; rasmsiz e'lon ulashilmaydi

    # Telegram rasmni o'zi yuklab oladi — kichigi tezroq va ishonchliroq
    rasm = _ik_olcham(rasm, 'w-800,q-80')

    nom = elon_nomi(elon, model, 'uz')   # G12: e'lonning o'z nomi
    xotira = elon_qavs(elon)   # BUGUN260-7: xotira + xususiyat
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
        # BUGUN224: savatdan — nums (hamma raqam, birinchisi = num). Ko'pi bilan 10 ta, faqat raqam, takrorsiz
        nums_xom = data.get('nums') or []
        if not isinstance(nums_xom, list) or len(nums_xom) > 10:
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        qolgan_nums = []
        for n in nums_xom:
            n = str(n or '').strip()
            if not re.fullmatch(r'\d{1,6}', n):
                return web.json_response({'error': 'Nomer notogri'}, status=400)
            if n != num and n not in qolgan_nums:
                qolgan_nums.append(n)
        loop = asyncio.get_event_loop()
        mid, sabab = await loop.run_in_executor(None, save_prepared_share, uid, num)
        if not mid:
            return web.json_response({'error': sabab}, status=502)
        return web.json_response({'ok': True, 'id': mid})
    except Exception as e:
        logger.error(f'share_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


# BUGUN171: «Sotib olish» — mijoz manzilini kiritishi bilan adminga darhol xabar.
# Bot Sheets'ga YOZMAYDI (buyurtma ro'yxati yo'q — faqat xabar); takror yuborishdan
# himoya — xotirada (qayta ishga tushsa tozalanadi, zarari yo'q: eng ko'pi bitta takror xabar).
_BUYURTMA_KORILGAN = {}      # (uid, buyurtma_id) → vaqt
_BUYURTMA_SONI = {}           # uid → [vaqtlar]


# BUGUN208: yashirin bron. Mijoz to'liq to'ldirib «To'lovga o'tish» bosganda (shu /buyurtma) e'lon shu mijozga bron
# bo'ladi; boshqa mijoz «Sotib olish» ni bossa sayt /bron_tekshir dan so'raydi — javob FAQAT bron: true/false (kim ekani
# saytga qaytmaydi), admin esa xabar oladi. Saqlash: xotira + BRON_FAYL (Render qayta ishga tushsa / deploy bo'lsa diskdagi
# fayl ham o'chadi — bronlar yo'qoladi; doimiy saqlash Apps Script'ni talab qiladi, YAKUN'da yozilgan).
BRON_MUDDAT_S = int(os.environ.get('BRON_MUDDAT_S', '0') or 0)   # 0 = admin bekor qilmaguncha turadi
BRON_FAYL = os.environ.get('BRON_FAYL', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bron_holat.json'))
_BRON = {}              # e'lon raqami → {'uid', 'order', 'ts'}
_BRON_OGOH = {}         # (uid, num) → oxirgi ogohlantirish vaqti (takror xabar bo'lmasin)


def _bron_yuklash():
    try:
        with open(BRON_FAYL, encoding='utf-8') as f:
            d = json.load(f)
        for num, v in d.items():
            if isinstance(v, dict) and v.get('uid') and v.get('order'):
                _BRON[str(num)] = {'uid': int(v['uid']), 'order': str(v['order']), 'ts': float(v.get('ts', 0))}
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f'bron yuklash: {e}')


def _bron_saqlash():
    try:
        with open(BRON_FAYL, 'w', encoding='utf-8') as f:
            json.dump(_BRON, f)
    except Exception as e:
        logger.error(f'bron saqlash: {e}')


def _bron_olish(num):
    """E'lon bronini qaytaradi (muddati o'tgan bo'lsa o'chiradi); yo'q bo'lsa None."""
    b = _BRON.get(str(num))
    if b and BRON_MUDDAT_S and time.time() - b['ts'] > BRON_MUDDAT_S:
        _BRON.pop(str(num), None)
        _bron_saqlash()
        return None
    return b


def _bron_qoy(num, uid, order):
    _BRON[str(num)] = {'uid': uid, 'order': order, 'ts': time.time()}
    _bron_saqlash()


def _init_data_user(init_data):
    """Imzosi to'g'ri initData dan Telegram foydalanuvchi ma'lumoti (ism, username, id); aks holda None."""
    uid = check_init_data(init_data)
    if not uid:
        return None
    try:
        u = json.loads(dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True)).get('user', '{}'))
    except Exception:
        u = {}
    return {'id': uid, 'ism': ' '.join(x for x in (u.get('first_name'), u.get('last_name')) if x) or str(uid),
            'username': u.get('username') or ''}


def _bron_mijoz_matn(u):
    """Admin aloqaga chiqishi uchun: ism, @username yoki profil havolasi."""
    if u.get('username'):
        havola = '@' + html_escape(u['username'])
    else:
        havola = '<a href="tg://user?id=%s">profil</a>' % u['id']
    return f"{html_escape(u['ism'])} · {havola}"


def _bron_ogoh_yubor(num, ikkinchi, sabab):
    """Fon oqimida: adminga «e'lon bron, 2-mijoz keldi». ikkinchi — _init_data_user() natijasi.
    Bir mijoz bir e'lon uchun 10 daqiqada bir marta ogohlantiradi."""
    b = _BRON.get(str(num)) or {}
    hozir = time.time()
    if hozir - _BRON_OGOH.get((ikkinchi['id'], str(num)), 0) < 600:
        return
    _BRON_OGOH[(ikkinchi['id'], str(num))] = hozir
    matn = (f"⚠️ №{html_escape(num)} — 2-mijoz {sabab}, e'lon bron\n"
            f"1-buyurtma №{html_escape(b.get('order', '—'))}, soat {_kk_vaqt(b.get('ts', hozir))}\n\n"
            f"👤 2-mijoz: {_bron_mijoz_matn(ikkinchi)}\n"
            f"1-mijoz olmasa — shu odamga o'zingiz aloqaga chiqasiz.")
    klava = {'inline_keyboard': [
        [{'text': '2-mijozga yozish', 'url': f"tg://user?id={ikkinchi['id']}"}],
        [{'text': '🔓 Bronni bekor qilish', 'callback_data': f"bron_och:{num}:{b.get('order', '')}"}]]}
    try:
        r = req.post(f'{TG_API}/sendMessage', json={
            'chat_id': ADMIN_ID, 'text': matn, 'parse_mode': 'HTML', 'reply_markup': klava}, timeout=10).json()
        if not r.get('ok'):
            logger.error(f"bron ogoh: {r.get('description')}")
    except Exception as e:
        logger.error(f'bron ogoh: {e}')


async def bron_tekshir_endpoint(request):
    """Sayt «Sotib olish» bosilganda: e'lon boshqa mijoz tomonidan bron qilinganmi. Javob — FAQAT {'bron': bool}.
    Bron bo'lsa admin 2-mijoz ma'lumoti bilan xabar oladi. Imzosiz / xato — xato qaytadi (sayt oynani baribir ochadi)."""
    try:
        data = await request.json()
        u = _init_data_user(data.get('initData', ''))
        if not u:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        num = str(data.get('num', '') or '').strip()
        if not re.fullmatch(r'\d{1,6}', num):
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        # BUGUN224: savatdan — nums (hamma raqam, birinchisi = num). Ko'pi bilan 10 ta, faqat raqam, takrorsiz
        nums_xom = data.get('nums') or []
        if not isinstance(nums_xom, list) or len(nums_xom) > 10:
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        qolgan_nums = []
        for n in nums_xom:
            n = str(n or '').strip()
            if not re.fullmatch(r'\d{1,6}', n):
                return web.json_response({'error': 'Nomer notogri'}, status=400)
            if n != num and n not in qolgan_nums:
                qolgan_nums.append(n)
        b = _bron_olish(num)
        if not b or b['uid'] == u['id']:
            return web.json_response({'bron': False})
        asyncio.get_event_loop().run_in_executor(None, _bron_ogoh_yubor, num, u, "«Sotib olish» ni bosdi")
        return web.json_response({'bron': True})
    except Exception as e:
        logger.error(f'bron_tekshir_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def bron_bekor_tugma(chat_id, cq_data):
    """Admin «🔓 Bronni bekor qilish» tugmasi: bron_och:<num>:<order>. Bron boshqa buyurtmaga o'tgan bo'lsa tegmaydi."""
    try:
        _, num, order = (cq_data.split(':', 2) + ['', ''])[:3]
        b = _BRON.get(num)
        if b and (not order or b['order'] == order):
            _BRON.pop(num, None)
            _bron_saqlash()
            matn = f"🔓 №{num} — bron bekor qilindi, e'lon hammaga ochiq."
        elif b:
            matn = f"ℹ️ №{num} — bron boshqa buyurtmada (№{b['order']}); tegilmadi."
        else:
            matn = f"ℹ️ №{num} — bron allaqachon yo'q."
        await blok(send_msg, chat_id, matn)
    except Exception as e:
        logger.error(f'bron_bekor_tugma: {e}')


_BUYURTMA_TUR = {'yandex': ('🚕', 'Yandex Go'), 'emu': ('📮', 'EMU'), 'bts': ('📦', 'BTS')}


def _buyurtma_joy_matn(joy):
    """📍 qatori. Yandex Go — Yandex xarita havolasi (koordinatadan bot o'zi yasaydi); EMU / BTS — mijoz yozgan filial matni
    («📍 EMU: Samarqand, Qo'shko'pir filiali»; BUGUN207 — oldin Yandex havolasi edi).
    joy = {'tur', 'lat', 'lon', 'manzil'}; turi yo'q (eski sayt) — erkin matn manzil.
    Havola yo'q (Yandex Go'da sayt kalitsiz ishlagan) — «joy belgilanmagan»: mijozdan telefon orqali so'raladi."""
    tur = joy.get('tur')
    if tur not in _BUYURTMA_TUR:
        return html_escape(joy.get('manzil') or '—')
    e, nom = _BUYURTMA_TUR[tur]
    if tur == 'yandex':
        if joy.get('lat') is None:
            return f'{e} {nom} — joy belgilanmagan'
        havola = f"https://yandex.uz/maps/?pt={joy['lon']},{joy['lat']}&z=17&l=map"
        return f'{e} {nom} — <a href="{havola}">Yandex xaritada ochish</a>'
    return f"{nom}: {html_escape(joy.get('manzil') or '—')}"


def elon_ranglar(elon):
    """BUGUN236 §8: e'lonning ranglari — `ranglar` ustuni (JSON [{uz, ru, soni, rasm}], sayt elonRanglar bilan bir xil). Bo'sh/buzuq → []."""
    v = (elon or {}).get('ranglar')
    if isinstance(v, str):
        if not v.strip():
            return []
        try:
            v = json.loads(v)
        except Exception:
            return []
    if not isinstance(v, list):
        return []
    res = []
    for r in v:
        if isinstance(r, dict) and str(r.get('uz') or '').strip():
            try:
                n = max(0, int(float(str(r.get('soni', 0)).strip() or 0)))
            except Exception:
                n = 0
            res.append({'uz': str(r['uz']).strip(), 'ru': str(r.get('ru') or '').strip(), 'soni': n})
    return res


def _buyurtma_ranglar(elon, ranglar):
    """BUGUN236 §8: mijoz tanlagan ranglar [(nom, dona)] — har rang o'z sonigacha (e'londa yo'q / qolmagan rang tushib qoladi).
    E'lon ranglari bot keshida hali yo'q bo'lsa (eski kesh) — rang nomi saqlanadi, dona umumiy chegarada (_buyurtma_soni)."""
    tanlov = (ranglar or {}).get(str(elon.get('num', ''))) or []
    if not tanlov:
        return []
    bor = {}
    for r in elon_ranglar(elon):
        bor.setdefault(r['uz'].casefold(), r)
        if r['ru']:
            bor.setdefault(r['ru'].casefold(), r)
    res = []
    for nom, d in tanlov:
        r = bor.get(nom.casefold())
        if bor and not r:
            continue
        if r:
            d = min(d, r['soni'])
            nom = r['uz']
        if d >= 1:
            res.append((nom, d))
    return res


def _buyurtma_sarlavha(elon, model, ranglar=None):
    nom = elon_nomi(elon, model, 'uz') or f"E'lon №{elon.get('num', '')}"
    xotira = elon_qavs(elon)   # BUGUN260-7: xotira + xususiyat
    rr = _buyurtma_ranglar(elon, ranglar)
    if rr:   # BUGUN236 §8: «Powerbank — Oq × 1, Qora × 2» (e'lonning umumiy rangi o'rniga)
        rang = ', '.join(f'{r} × {d}' if (d > 1 or len(rr) > 1) else r for r, d in rr)
        return nom + (f' ({xotira})' if xotira else '') + f' — {rang}'
    rang = clean_color(elon.get('color') or '')
    return nom + (f' ({xotira})' if xotira else '') + (f' {rang}' if rang else '')


def _buyurtma_soni(elon, sonlar, ranglar=None):
    """BUGUN236: mijoz tanlagan dona soni — ko'p donali tovarda omborda borigacha, bitta tovarda — doim 1.
    §8: rang tanlangan bo'lsa — ranglar donasi yig'indisi (har rang o'z sonigacha)."""
    rr = _buyurtma_ranglar(elon, ranglar)
    try:
        n = sum(d for _, d in rr) if rr else int((sonlar or {}).get(str(elon.get('num', '')), 1))
    except Exception:
        n = 1
    if not kop_donali(elon):
        return 1
    return max(1, min(n, soni_val(elon) or 1, 99))


# ══ BUGUN287: kelishilgan narx — admin savatni ulashishdan oldin narxni tushirsa, narx FAQAT shu havolaga (Store'dagi
# SavatHavolalar.narxlar) yoziladi. Sayt botga faqat havola KODINI yuboradi (narx emas) — bot narxni Apps Script'dan o'zi oladi
# (API_KEY bilan). Haqiqiy narx = min(kelishilgan, Store'dagi hozirgi narx); chegirma = Store − haqiqiy (1 donaga).
def _savat_kel_narxlar(kodlar, nums):
    """kodlar — havola kodlari (≤3), nums — buyurtmadagi raqamlar. Qaytaradi ({num: kelishilgan $}, ogoh): ogoh — havola
    o'qilmadi / muddati o'tgan (narx Store'dagicha qoladi, admin xabarida ko'rinadi)."""
    kel, ogoh = {}, False
    for k in kodlar:
        r = _kk_sheet('savatOl', timeout=20, kod=k)
        if not (r and r.get('ok')):
            ogoh = True
            continue
        for n, v in (r.get('narxlar') or {}).items():
            try:
                x = float((v or {}).get('narx'))
            except Exception:
                continue
            if str(n) in nums and x > 0:
                kel[str(n)] = min(x, kel.get(str(n), x))
    return kel, ogoh


def _kel_narx(elon, kel):
    """(narx 1 dona, chegirma 1 dona) — kelishilgan narx bo'lsa va Store narxidan past bo'lsa — o'sha, aks holda Store narxi."""
    asl = _narx_son(elon)
    k = (kel or {}).get(str(elon.get('num', '')))
    if asl is None or k is None or not (0 < k < asl):
        return asl, 0
    return round(k, 2), round(asl - k, 2)


def _buyurtma_matn(uid, elon, model, order, ism, tel, joy, kurs, qolgan=(), sonlar=None, ranglar=None, kel=None, kel_ogoh=False,
                   ogoh=(), tel_ogoh=False):
    """Adminga boradigan xabar (HTML). Narx — SERVERDAGI e'londan (mijoz yuborganiga ishonilmaydi).
    BUGUN224: qolgan — savatdan sotib olishda qolgan tovarlar [(elon, model), …]; narx — hammasining jami.
    BUGUN236: sonlar — {num: dona}; narx × dona (dona ko'p donali tovarda omborda borigacha cheklanadi).
    §8: ranglar — {num: [(rang, dona)]}; sarlavhada «Oq × 1, Qora × 2», dona — ularning yig'indisi.
    BUGUN295: ogoh — [(num, 'yopiq' | 'topilmadi')] (buyurtma rad etilmaydi — admin ko'radi); tel_ogoh — saqlangan raqam topilmadi."""
    qatorlar = [(elon, model)] + list(qolgan)
    donalar = [_buyurtma_soni(e, sonlar, ranglar) for e, _ in qatorlar]
    kn = [_kel_narx(e, kel) for e, _ in qatorlar]   # BUGUN287: kelishilgan narx (havoladan, bot o'zi olgan)
    narxlar = [n for n, _ in kn]
    cheg = [c for _, c in kn]
    cheg_jami = round(sum(c * d for c, d in zip(cheg, donalar)), 2)
    usd = None if any(n is None for n in narxlar) else sum(n * d for n, d in zip(narxlar, donalar))
    narx = f'{usd:g}$' if usd is not None else '—'
    # so'm — 1 000 gacha yaxlit (to'lov sahifasidagi summa bilan bir xil bo'lsin: mijoz ko'rgan = admin ko'rgan)
    som = (f"{int(round(usd * kurs / 1000.0)) * 1000:,}".replace(',', ' ') + " so'm") if (usd is not None and kurs) else '—'
    kurs_s = f'{kurs:,}'.replace(',', ' ')
    def _dona(n, d, c=0):   # «35$ × 2 = 70$» · bitta bo'lsa «35$» · BUGUN287: kelishilgan bo'lsa « 🎟 (Store 50$)»
        if n is None:
            return '—'
        s = f'{n:g}$ × {d} = {round(n * d, 2):g}$' if d > 1 else f'{n:g}$'
        return s + (f' 🎟 (Store {round(n + c, 2):g}$)' if c > 0 else '')
    def _nom(e, m):   # 2011: tovar nomi — Store'dagi kartaga havola (Owner: «qaysi tovar ekanini bilishim uchun»)
        t = html_escape(_buyurtma_sarlavha(e, m, ranglar))
        n = str(e.get('num', '')).strip()
        return f'<a href="https://t.me/{BOT_USERNAME}?startapp=elon_{html_escape(n)}">{t}</a>' if n.isdigit() else t
    if len(qatorlar) == 1:
        tovar = (f"📱 <b>{_nom(elon, model)}</b> · e'lon №{html_escape(elon.get('num', ''))}\n"
                 + (f"🔢 <b>{donalar[0]} dona</b> · {html_escape(_dona(narxlar[0], donalar[0], cheg[0]))}\n" if donalar[0] > 1 else ''))
    else:
        tovar = f"🧺 <b>Savatdan — {len(qatorlar)} ta tovar:</b>\n" + ''.join(
            f"{i}. <b>{_nom(e, m)}</b> · №{html_escape(e.get('num', ''))}"
            f" · {html_escape(_dona(n, d, c))}\n"
            for i, ((e, m), n, d, c) in enumerate(zip(qatorlar, narxlar, donalar, cheg), 1))
    jami_s = 'Jami ' if (len(qatorlar) > 1 or donalar[0] > 1) else ''
    ogoh_s = ''.join(f"⚠️ №{html_escape(n)}: {_BUYURTMA_OGOH.get(o, o)}\n" for n, o in ogoh)
    tel_s = html_escape(tel) if tel else _BUYURTMA_TEL_YOQ
    return (f"🛒 <b>Yangi buyurtma</b> №{html_escape(order)}\n\n"
            + tovar +
            f"💵 {jami_s}{html_escape(narx)} ≈ {html_escape(som)} (kurs {kurs_s})\n"
            + (f"🎟 <b>Admin chegirmasi: −{cheg_jami:g}$</b> (kelishilgan narx, havoladan)\n" if cheg_jami > 0 else '')
            + ("⚠️ Mijoz ulashilgan havoladan keldi, lekin havola o'qilmadi / muddati o'tgan — narx Store'dagicha.\n"
               if kel_ogoh else '') + ogoh_s +
            "\n"
            f"👤 {html_escape(ism)}\n"
            f"📞 {tel_s}\n"
            f"📍 {_buyurtma_joy_matn(joy)}\n\n"
            f"⏳ <b>To'lov kutilmoqda</b> — chek hali kelmagan. Mijoz chekni o'zi yuboradi; "
            f"kelmasa — telefon qiling.\n"
            f"🕒 {_kk_vaqt(time.time())}")


# ══ BUGUN227: buyurtma holati — adminning tugmalari (✅ To'lov keldi · 🚚 Yo'lda · 📦 Yetkazildi) ══
# Holat faqat ALGA siljiydi: kutilmoqda → tolandi → yolda → yetkazildi (bosqichni o'tkazib yuborish mumkin: to'lov chekini ko'rmay
# «Yo'lda» desa ham bo'ladi). «bekor» (mijoz bekor qilgan) — oxirgi holat: undan keyin tugmalar ish bermaydi. Holat Sheets'ga yoziladi
# (Buyurtmalar varag'i), mijozga botda qisqa xabar (uz + ru), saytdagi «Buyurtmalarim» shu holatni ko'rsatadi.
_HOLAT_TARTIB = ('kutilmoqda', 'tolandi', 'yolda', 'yetkazildi')
_HOLAT_ADMIN = {'tolandi': ('✅', "To'lov keldi"), 'yolda': ('🚚', "Yo'lda"), 'yetkazildi': ('📦', 'Yetkazildi')}
_HOLAT_ADMIN_NOM = {'kutilmoqda': "⏳ To'lov kutilmoqda", 'tolandi': "✅ To'lov keldi", 'yolda': "🚚 Yo'lda",
                    'yetkazildi': '📦 Yetkazildi', 'bekor': '❌ Mijoz bekor qilgan'}
_HOLAT_MIJOZ = {   # mijozga xabar: (uz, ru) — {o} buyurtma raqami
    'tolandi': ("✅ <b>Buyurtma №{o}</b> — to'lovingiz qabul qilindi. Rahmat!",
                "✅ <b>Заказ №{o}</b> — оплата получена. Спасибо!"),
    'yolda': ("🚚 <b>Buyurtma №{o}</b> yo'lga chiqdi!",
              "🚚 <b>Заказ №{o}</b> уже в пути!"),
    'yetkazildi': ("📦 <b>Buyurtma №{o}</b> yetkazildi. Xaridingiz uchun rahmat!",
                   "📦 <b>Заказ №{o}</b> доставлен. Спасибо за покупку!"),
}


# BUGUN295: buyurtma xabaridagi holat qatori — admin tugma bosganda xabar MATNI ham o'zgaradi (ilgari faqat tugmalar o'zgarib,
# «⏳ To'lov kutilmoqda — chek hali kelmagan…» qolib ketardi). Bosqichlar ketma-ket: «✅ To'landi · 20:31 → 🚚 Yo'lda · 21:05».
_HOLAT_QATOR = {'tolandi': ('✅', "To'landi"), 'yolda': ('🚚', "Yo'lda"), 'yetkazildi': ('📦', 'Yetkazildi')}
_HOLAT_QATOR_RE = re.compile("\n\n(?:⏳ To'lov kutilmoqda|✅ To'landi|🚚 Yo'lda|📦 Yetkazildi)")
_BUYURTMA_VAQT_RE = re.compile(r'🕒 (?:Buyurtma: )?(\d\d\.\d\d\.\d{4} \d\d:\d\d)')


def _u16(s):
    """Telegram entity offset / length — UTF-16 birligida."""
    return len(s.encode('utf-16-le')) // 2


def _buyurtma_holat_matn(text, entities, holat, ts):
    """Admin xabari (text + entities, Telegram'dan qaytgan) → (yangi text, entities): holat qatoridan pasti almashadi.
    Holat qatori topilmasa (boshqa xabar) — None."""
    if holat not in _HOLAT_QATOR:
        return None
    m = None
    for m in _HOLAT_QATOR_RE.finditer(text or ''):
        pass
    if not m:
        return None
    bosh, dum = text[:m.start()], text[m.start() + 2:]
    v = _BUYURTMA_VAQT_RE.search(dum)
    eski = dum.split('\n', 1)[0]
    e, nom = _HOLAT_QATOR[holat]
    zanjir = '' if eski.startswith('⏳') else eski + ' → '
    qator = f"{zanjir}{e} {nom} · {_kk_vaqt(ts)[-5:]}"
    yangi = bosh + '\n\n' + qator + (f"\n🕒 Buyurtma: {v.group(1)}" if v else '')
    chek = _u16(bosh)
    ents = []
    for x in (entities or []):
        o, ln = int(x.get('offset', 0)), int(x.get('length', 0))
        if o >= chek:
            continue
        y = dict(x)
        y['length'] = min(ln, chek - o)
        ents.append(y)
    ents.append({'type': 'bold', 'offset': _u16(bosh + '\n\n' + zanjir + e + ' '), 'length': _u16(nom)})
    return yangi, ents


def _buyurtma_klava(uid, order, holat, bron_nums):
    """Adminga boradigan buyurtma xabarining tugmalari: Mijozga yozish · holat bosqichlari · bronni bekor qilish.
    2011: bosqichlar DOIM bir joyda — [✅ To'lov keldi | 🚚 Yo'lda] [📦 Yetkazildi]; bajarilgani «✔️ To'landi» bo'ladi (bosilsa
    holat o'zgarmaydi, faqat «bajarilgan» deydi). NEGA: Owner 2026-10-20 — bosgandan keyin «📍 ✅ To'lov keldi» yana tugmadek
    chiqdi, «Yo'lda» joyidan ko'chdi — nima o'zgargani tushunilmadi."""
    qator = [[{'text': 'Mijozga yozish', 'url': f'tg://user?id={uid}'}]]
    if holat in _HOLAT_TARTIB:
        i = _HOLAT_TARTIB.index(holat)
        t = [{'text': f'✔️ {_HOLAT_QATOR[h][1]}', 'callback_data': 'bh:-'} if _HOLAT_TARTIB.index(h) <= i else
             {'text': f'{_HOLAT_ADMIN[h][0]} {_HOLAT_ADMIN[h][1]}', 'callback_data': f'bh:{h}:{uid}:{order}'}
             for h in _HOLAT_TARTIB[1:]]
        qator += [t[:2], t[2:]]
    else:   # bekor — tugma emas, holat
        qator.append([{'text': '📍 ' + _HOLAT_ADMIN_NOM.get(holat, holat), 'callback_data': 'bh:-'}])
    qator += [[{'text': '🔓 Bronni bekor qilish' + (f' №{n}' if len(bron_nums) > 1 else ''),
                'callback_data': f'bron_och:{n}:{order}'}] for n in bron_nums]
    return {'inline_keyboard': qator}


def _buyurtma_holat_qoy(uid, order, yangi):
    """Holatni oldinga suradi. Qaytaradi (kod, buyurtma): 'ok' · 'eski' (shu yoki oldingi holat) · 'bekor' · 'topilmadi'."""
    with _MIJOZ_LOCK:
        b = next((x for x in _mijoz_ol(uid)['buyurtma'] if x.get('order') == order), None)
        if not b:
            return 'topilmadi', None
        if b.get('holat') == 'bekor':
            return 'bekor', dict(b)
        eski = b.get('holat') if b.get('holat') in _HOLAT_TARTIB else 'kutilmoqda'
        if _HOLAT_TARTIB.index(yangi) <= _HOLAT_TARTIB.index(eski):
            return 'eski', dict(b)
        b['holat'] = yangi
        b['holat_ts'] = time.time()
        _mijoz_saqlash()
        _mijoz_sync_belgila('b', uid, order)
        return 'ok', dict(b)


def _buyurtma_mijozga(uid, b, yangi):
    """Mijozga botda qisqa xabar. Til — buyurtma berilganda Telegram'dan olingan; bilinmasa ikkalasi. (natija) 'yuborildi' | boshqa."""
    uz, ru = _HOLAT_MIJOZ[yangi]
    o = html_escape(b.get('order', ''))
    til = b.get('til')
    matn = uz.format(o=o) if til == 'uz' else ru.format(o=o) if til == 'ru' else uz.format(o=o) + '\n\n' + ru.format(o=o)
    natija, _ = _kk_tg('sendMessage', {'chat_id': uid, 'text': matn, 'parse_mode': 'HTML'}, urinish=2)
    return natija


def _sotuv_sheet_yoz(uid, b):
    """BUGUN275: tasdiqlangan buyurtma → Store (Sotuvlar varag'i + e'lon «sotildi»). Store'da (order, num) bo'yicha bir marta
    yoziladi — qayta chaqirish xavfsiz (admin tugmani qayta bossa shu qayta urinish). nik — buyurtma paytidagi username,
    yo'q bo'lsa Telegram getChat. Raqam/nik logga YOZILMAYDI. True — Store qabul qildi."""
    try:
        tovar = [{'num': x.get('num'), 'soni': x.get('soni') or 1, 'narx': x.get('narx'), 'chegirma': x.get('chegirma') or 0}
                 for x in (b.get('tovar') or []) if x.get('num')]   # BUGUN287: narx — haqiqiy (kelishilgan), chegirma — 1 donaga
        if not tovar:
            return True
        nik = str(b.get('nik') or '').lstrip('@')
        if not nik:
            n, j = _kk_tg('getChat', {'chat_id': uid}, urinish=1)
            if n == 'yuborildi':
                nik = str(((j or {}).get('result') or {}).get('username') or '')
        d = {'order': b.get('order'), 'user_id': uid, 'nik': nik, 'tel': b.get('tel') or '', 'tovar': tovar}
        data = json.dumps(d, ensure_ascii=False)
        r = _kk_sheet('sotuvYoz', timeout=40, data=data)
        if not (r and r.get('ok')):   # BUGUN295: №SP34PV — Store yozgan, javob kechikkan; 2-urinish xavfsiz (takror yozilmaydi)
            time.sleep(3)
            r = _kk_sheet('sotuvYoz', timeout=60, data=data)
        return bool(r and r.get('ok'))
    except Exception as e:
        logger.error(f'sotuv_sheet_yoz: {type(e).__name__}')
        return False


async def buyurtma_holat_tugma(chat_id, message_id, cq_data, xabar=None):
    """Admin tugmasi: bh:<holat>:<uid>:<order>. Holat saqlanadi, tugmalar yangilanadi, mijozga xabar ketadi.
    BUGUN295: xabar — bosilgan xabarning o'zi (text + entities): holat o'zgarsa xabar matnidagi holat qatori ham almashadi."""
    try:
        p = cq_data.split(':')
        if len(p) != 4 or p[1] not in _HOLAT_ADMIN or not p[2].isdigit() or not re.fullmatch(r'[A-Z0-9]{4,12}', p[3]):
            return    # 'bh:-' (joriy holat belgisi) yoki buzuq — jim
        yangi, uid, order = p[1], int(p[2]), p[3]
        kod, b = await blok(_buyurtma_holat_qoy, uid, order, yangi)
        if kod == 'topilmadi':
            await blok(send_msg, chat_id, f"ℹ️ Buyurtma №{html_escape(order)} bot xotirasida topilmadi — holat o'zgarmadi.")
            return
        joriy = b.get('holat') if b else yangi
        bron_nums = [str(x.get('num')) for x in (b.get('tovar') or []) if x.get('num')]
        if message_id:
            klava = _buyurtma_klava(uid, order, joriy, bron_nums)
            xb = xabar or {}
            rasmli = not xb.get('text') and bool(xb.get('caption'))   # BUGUN296: chek nusxasi — rasm, matni caption'da
            yangi_m = _buyurtma_holat_matn(xb.get('caption') if rasmli else xb.get('text'),
                                           xb.get('caption_entities') if rasmli else xb.get('entities'), joriy,
                                           b.get('holat_ts') or time.time()) if (kod == 'ok' and b) else None
            natija = 'xato'
            if yangi_m and rasmli:
                natija, _ = await blok(_kk_tg, 'editMessageCaption', {
                    'chat_id': int(chat_id), 'message_id': message_id, 'caption': yangi_m[0],
                    'caption_entities': yangi_m[1], 'reply_markup': klava}, urinish=2)
            elif yangi_m:
                natija, _ = await blok(_kk_tg, 'editMessageText', {
                    'chat_id': int(chat_id), 'message_id': message_id, 'text': yangi_m[0], 'entities': yangi_m[1],
                    'reply_markup': klava, 'link_preview_options': {'is_disabled': True}}, urinish=2)
            if natija != 'yuborildi':
                await blok(req.post, f'{TG_API}/editMessageReplyMarkup', json={
                    'chat_id': int(chat_id), 'message_id': message_id, 'reply_markup': klava}, timeout=10)
        if kod == 'bekor':
            await blok(send_msg, chat_id, f"ℹ️ Buyurtma №{html_escape(order)} — mijoz bekor qilgan, holat o'zgarmadi.")
        elif kod == 'ok':
            natija = await blok(_buyurtma_mijozga, uid, b, yangi)
            if natija != 'yuborildi':
                await blok(send_msg, chat_id, f"⚠️ №{html_escape(order)}: holat saqlandi, lekin mijozga xabar bormadi "
                                              f"(botni to'xtatgan bo'lishi mumkin). «Mijozga yozish» orqali o'zingiz yozing.")
        # BUGUN275: tasdiqlangan (to'langan / yo'lda / yetkazilgan) buyurtma → Store'ga sotuv yozuvi, e'lonlar «sotildi».
        # 'eski' ham — bir xil tugma qayta bosilsa Store'ga yozish qayta uriniladi (Store takror yozmaydi).
        if kod in ('ok', 'eski') and b and b.get('holat') in ('tolandi', 'yolda', 'yetkazildi'):
            if not await blok(_sotuv_sheet_yoz, uid, b):
                await blok(send_msg, chat_id, f"⚠️ №{html_escape(order)}: Store'ga sotuv yozuvi tushmadi — "
                                              f"tugmani qayta bosing (takror yozilmaydi).")
    except Exception as e:
        logger.error(f'buyurtma_holat_tugma: {e}')


# ══ BUGUN296: chek botga ══
# Mijoz to'laydi va chekni SHU BOTGA yuboradi (ilgari — @admin ga yozardi, chek buyurtmaga bog'lanmasdi). Oqim:
#  1) buyurtma tushganda mijozga botda xabar: tarkibi, jami, «💳 To'lash» va «🧾 To'landim — chek yuborish» (to'langan bo'lsa — tugmasiz);
#  2) «To'landim» (yoki saytdagi tugma → ?start=chek_<raqam>) — bot «chek rasmini yuboring — №…» deydi; «chek kutilmoqda» holati
#     buyurtma yozuvida (chek = 'kut') — Sheets'dagi «chek» ustuniga ham yoziladi, bot qayta yonsa ham yo'qolmaydi;
#  3) rasm / rasm-fayl / PDF kelsa: holat bor — o'sha buyurtmaga; yo'q — oxirgi to'lanmagan buyurtmaga; bir nechta bo'lsa — tugma bilan so'raydi;
#  4) mijozga «✅ Chekingiz qabul qilindi…» + «✍️ Adminga yozish»; adminga chek nusxasi + «🧾 Chek keldi — №…» + «✅ To'lov keldi» (BUGUN295 oqimi).
# Bir xil rasm (file_unique_id) ikkinchi marta adminga bormaydi. Albom (bir nechta rasm) — bitta javob, hammasi adminga.
TOLOV_URL = os.environ.get('TOLOV_URL', 'https://nuqta-tech-tolov.netlify.app/').strip()   # sayt SOTIB_TOLOV_JONLI bilan bir xil
_CHEK_QULF = threading.Lock()
_CHEK_ALBOM = {}      # (uid, media_group_id) → {'t', 'order' | None (so'ralmoqda), 'mid': [xabar id'lari]}
_CHEK_TANLASH = {}    # (uid, message_id) → {'t', 'fid', 'mgid'} — «qaysi buyurtma?» deb so'ralgan chek


def _chek_matn(til, uz, ru):
    return uz if til == 'uz' else ru if til == 'ru' else uz + '\n\n' + ru


def _chek_tugma_nomi(til, uz, ru):
    return uz if til == 'uz' else ru if til == 'ru' else f'{uz} / {ru}'


def _chek_tel_til(user, b=None):
    """Buyurtmada bo'lsa — o'sha til; yo'q bo'lsa Telegram til kodi (ru → ru, uz → uz), bilinmasa ''."""
    t = (b or {}).get('til')
    if t in ('uz', 'ru'):
        return t
    k = str((user or {}).get('language_code') or '').lower()
    return 'ru' if k.startswith('ru') else 'uz' if k.startswith('uz') else ''


def _chek_summa(b):
    """(usd, so'm | None, kurs | None). Buyurtmadagi jami $ va (bor bo'lsa) buyurtma paytidagi kurs — sayt bilan bir xil yaxlitlash."""
    try:
        usd = float(b.get('jami'))
    except Exception:
        return None, None, None
    if not usd > 0:
        return None, None, None
    try:
        kurs = int(float((b.get('joy') or {}).get('kurs') or 0))
    except Exception:
        kurs = 0
    if not 1000 <= kurs <= 100000:
        return usd, None, None
    return usd, int(round(usd * kurs / 1000.0)) * 1000, kurs


def _chek_summa_s(b):
    usd, som, _ = _chek_summa(b)
    if usd is None:
        return '—'
    return f'{usd:g}$' + (f" ≈ {som:,}".replace(',', ' ') + " so'm" if som else '')


def _chek_tolov_url(b):
    usd, som, kurs = _chek_summa(b)
    if not som:
        return ''
    return TOLOV_URL.rstrip('/') + '/?' + urllib.parse.urlencode({'o': b.get('order'), 's': som, 'u': f'{usd:g}', 'k': kurs})


def _chek_admin_tugma():
    return {'text': "✍️ Adminga yozish", 'url': f'https://t.me/{ADMIN_USERNAME}'}


def _chek_buyurtma_matn(b):
    o = html_escape(b.get('order', ''))
    qat = ''
    for i, x in enumerate(b.get('tovar') or [], 1):
        soni = x.get('soni') or 1
        narx = '' if x.get('narx') is None else f" · {round(x['narx'] * soni, 2):g}$"
        qat += f"{i}. {html_escape(x.get('nom') or '—')}{f' × {soni}' if soni > 1 else ''}{narx}\n"
    jami = html_escape(_chek_summa_s(b))
    return _chek_matn(
        b.get('til'),
        f"🛒 <b>Buyurtma №{o}</b>\n\n{qat}\n💵 Jami: <b>{jami}</b>\n\n"
        f"To'lovni amalga oshiring, so'ng «🧾 To'landim» tugmasini bosib chekni yuboring.",
        f"🛒 <b>Заказ №{o}</b>\n\n{qat}\n💵 Итого: <b>{jami}</b>\n\n"
        f"Оплатите заказ, затем нажмите «🧾 Оплатил» и отправьте чек.")


def _chek_buyurtma_klava(b):
    """To'langan (yoki bekor) buyurtmada tugma yo'q; «To'lash» — summa va kurs ma'lum bo'lsa."""
    if b.get('holat') != 'kutilmoqda':
        return None
    til = b.get('til')
    qator = []
    url = _chek_tolov_url(b)
    if url:
        qator.append([{'text': _chek_tugma_nomi(til, "💳 To'lash", '💳 Оплатить'), 'url': url}])
    qator.append([{'text': _chek_tugma_nomi(til, "🧾 To'landim — chek yuborish", '🧾 Оплатил — отправить чек'),
                   'callback_data': f"chk:{b.get('order')}"}])
    return {'inline_keyboard': qator}


def _chek_yubor(uid, matn, klava=None):
    p = {'chat_id': uid, 'text': matn, 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True}}
    if klava:
        p['reply_markup'] = klava
    natija, _ = _kk_tg('sendMessage', p, urinish=2)
    return natija


def _chek_buyurtmalar(uid):
    return _mijoz_ol(uid)['buyurtma']


def _chek_mijozga_xabar(uid, order):
    """Buyurtma tushganda mijozga bitta xabar (har buyurtmaga bir marta: mijoz_xabar). /start bosmagan bo'lsa Telegram yubormaydi —
    qayta urinilmaydi (saytdagi «To'landim» tugmasi botni ochadi va o'sha paytda xabar o'zi chiqadi)."""
    with _MIJOZ_LOCK:
        b = next((x for x in _chek_buyurtmalar(uid) if x.get('order') == order), None)
        if not b or b.get('mijoz_xabar') or b.get('holat') != 'kutilmoqda':
            return None
        b['mijoz_xabar'] = 1
        _mijoz_saqlash()
        b = dict(b)
    try:
        return _chek_yubor(uid, _chek_buyurtma_matn(b), _chek_buyurtma_klava(b))
    except Exception as e:
        logger.error(f'chek mijozga xabar: {type(e).__name__}')
        return None


def _chek_belgi(uid, order, **maydon):
    """Yozuvga maydonlar (chek, chek_fid) → fayl + Sheets navbati."""
    with _MIJOZ_LOCK:
        b = next((x for x in _chek_buyurtmalar(uid) if x.get('order') == order), None)
        if not b:
            return None
        b.update(maydon)
        _mijoz_saqlash()
        _mijoz_sync_belgila('b', uid, order)
        return dict(b)


def _chek_boshla(uid, order, user=None):
    """«To'landim» bosildi / ?start=chek_<raqam>. Holatni qo'yadi, mijozga javob. Qaytaradi — natija kodi (sinov uchun)."""
    with _MIJOZ_LOCK:
        m = _mijoz_ol(uid)
        b = next((x for x in m['buyurtma'] if x.get('order') == order), None)
        til = _chek_tel_til(user, b)
        if b and b.get('holat') == 'kutilmoqda':
            for x in m['buyurtma']:   # bir vaqtda bitta «chek kutilmoqda»
                if x is not b and x.get('chek') == 'kut':
                    x['chek'] = ''
                    _mijoz_sync_belgila('b', uid, x.get('order'))
            if b.get('chek') != 'kut' or not b.get('chek_ts'):
                b['chek_ts'] = int(time.time())   # BUGUN305: 1 soatlik eslatma shu paytdan hisoblanadi (qayta bosish uni uzaytirmaydi)
            b['chek'] = 'kut'
            _mijoz_saqlash()
            _mijoz_sync_belgila('b', uid, order)
        b = dict(b) if b else None
    o = html_escape(order)
    if not b:
        _chek_yubor(uid, _chek_matn(til, f"ℹ️ Buyurtma №{o} topilmadi. Savolingiz bo'lsa — adminga yozing.",
                                    f"ℹ️ Заказ №{o} не найден. Если есть вопрос — напишите админу."),
                    {'inline_keyboard': [[_chek_admin_tugma()]]})
        return 'topilmadi'
    if b.get('holat') == 'bekor':
        _chek_yubor(uid, _chek_matn(til, f"ℹ️ Buyurtma №{o} bekor qilingan.", f"ℹ️ Заказ №{o} отменён."),
                    {'inline_keyboard': [[_chek_admin_tugma()]]})
        return 'bekor'
    if b.get('holat') != 'kutilmoqda':
        _chek_yubor(uid, _chek_matn(til, f"✅ Buyurtma №{o} — to'lov allaqachon qabul qilingan. Rahmat!",
                                    f"✅ Заказ №{o} — оплата уже принята. Спасибо!"))
        return 'tolangan'
    _chek_yubor(uid, _chek_matn(til, f"🧾 Chek rasmini (yoki faylini) shu yerga yuboring — buyurtma №{o}",
                                f"🧾 Отправьте сюда фото (или файл) чека — заказ №{o}"))
    return 'kutilmoqda'


def _chek_fayl(message):
    """Chek bo'la oladigan xabar: rasm · rasm / PDF fayl → file_unique_id ('' bo'lishi mumkin). Boshqasi — None."""
    ph = message.get('photo')
    if ph:
        return (ph[-1].get('file_unique_id') or ph[-1].get('file_id') or '')
    d = message.get('document') or {}
    mt = str(d.get('mime_type') or '')
    if d and (mt.startswith('image/') or mt == 'application/pdf'):
        return d.get('file_unique_id') or d.get('file_id') or ''
    return None


def _chek_kutyapti(uid):
    """Mijozda «chek kutilmoqda» holati bormi (admin o'z lichkasida sinasa — rasm e'lon yasamasin)."""
    with _MIJOZ_LOCK:
        return any(b.get('chek') == 'kut' and b.get('holat') == 'kutilmoqda' for b in _chek_buyurtmalar(uid))


def _chek_admin_matn(b, davomi=False):
    o = html_escape(b.get('order', ''))
    if davomi:
        return f"🧾 <b>Chek (davomi)</b> — №{o}"
    return (f"🧾 <b>Chek keldi</b> — №{o}\n💵 {html_escape(_chek_summa_s(b))}\n"
            f"👤 {html_escape(b.get('ism') or '—')}\n\n"
            f"⏳ To'lov kutilmoqda\n🕒 {_kk_vaqt(time.time())}")


def _chek_adminga(uid, b, mid, davomi=False):
    """Chek nusxasi (copyMessage) + izoh + «✅ To'lov keldi». Nusxa bo'lmasa — forward, u ham bo'lmasa — False."""
    order = b.get('order')
    yoz = [{'text': 'Mijozga yozish', 'url': f'tg://user?id={uid}'}]
    tolandi = _HOLAT_ADMIN['tolandi']
    klava = {'inline_keyboard': [yoz]} if davomi else {
        'inline_keyboard': [yoz, [{'text': f'{tolandi[0]} {tolandi[1]}', 'callback_data': f'bh:tolandi:{uid}:{order}'}]]}
    matn = _chek_admin_matn(b, davomi)
    natija, _ = _kk_tg('copyMessage', {'chat_id': ADMIN_ID, 'from_chat_id': uid, 'message_id': mid, 'caption': matn,
                                       'parse_mode': 'HTML', 'reply_markup': klava}, urinish=2)
    if natija in ('yuborildi', 'noaniq'):   # noaniq — ketgan bo'lishi mumkin: qayta yuborilmaydi (ikki nusxa bo'lmasin)
        return True
    f, _ = _kk_tg('forwardMessage', {'chat_id': ADMIN_ID, 'from_chat_id': uid, 'message_id': mid}, urinish=2)
    if f != 'yuborildi':
        return False
    return _kk_tg('sendMessage', {'chat_id': ADMIN_ID, 'text': matn, 'parse_mode': 'HTML', 'reply_markup': klava},
                  urinish=2)[0] in ('yuborildi', 'noaniq')


def _chek_topshir(uid, user, order, mids, fid):
    """Chek aniq buyurtmaga biriktirildi: holat belgilanadi, adminga nusxa, mijozga «qabul qilindi». mids[0] — asosiy xabar,
    qolgani (albom) — «davomi». Admin nusxasi yetmasa — holat qaytariladi va mijozga rost aytiladi (jimgina «qabul» demaydi)."""
    with _MIJOZ_LOCK:
        b = next((x for x in _chek_buyurtmalar(uid) if x.get('order') == order), None)
        if not b:
            return 'topilmadi'
        eski = {'chek': b.get('chek') or '', 'chek_fid': list(b.get('chek_fid') or [])}
    til = _chek_tel_til(user, b)
    yangi_fid = ([fid] if fid else []) + eski['chek_fid']
    b = _chek_belgi(uid, order, chek=_kk_vaqt(time.time())[-5:], chek_fid=yangi_fid[:10])
    o = html_escape(order)
    if _chek_adminga(uid, b, mids[0]):
        for m in mids[1:]:
            _chek_adminga(uid, b, m, davomi=True)
        _chek_yubor(uid, _chek_matn(
            til, f"✅ Chekingiz qabul qilindi. Buyurtmangiz №{o} qabul qilindi — admin siz bilan aloqaga chiqadi.",
            f"✅ Ваш чек принят. Заказ №{o} принят — админ свяжется с вами."), {'inline_keyboard': [[_chek_admin_tugma()]]})
        return 'qabul'
    _chek_belgi(uid, order, **eski)
    _chek_yubor(uid, _chek_matn(
        til, f"⚠️ Chekni adminga yetkaza olmadim (buyurtma №{o}). Iltimos, «Adminga yozish» orqali chekni to'g'ridan-to'g'ri yuboring.",
        f"⚠️ Не удалось передать чек админу (заказ №{o}). Пожалуйста, отправьте чек напрямую через «Написать админу»."),
        {'inline_keyboard': [[_chek_admin_tugma()]]})
    return 'adminga_yetmadi'


def _chek_qabul(uid, user, message):
    """Mijozdan rasm / fayl keldi (fon oqimida). Qaytaradi — natija kodi: qabul · dup · tanla · yoq · davomi · adminga_yetmadi."""
    mid, mgid, fid = message.get('message_id'), message.get('media_group_id'), _chek_fayl(message)
    hozir = time.time()
    nishon, ochiq, holat, order, davomi = None, [], '', None, False
    with _CHEK_QULF:
        for k in [k for k, v in _CHEK_ALBOM.items() if hozir - v['t'] > 600]:
            _CHEK_ALBOM.pop(k, None)
        for k in [k for k, v in _CHEK_TANLASH.items() if hozir - v['t'] > 3600]:
            _CHEK_TANLASH.pop(k, None)
        alb = _CHEK_ALBOM.get((uid, mgid)) if mgid else None
        if alb:   # albomning 2-, 3-… rasmi — qaror birinchisiniki
            alb['mid'].append(mid)
            order, davomi = alb['order'], True
        else:
            with _MIJOZ_LOCK:
                ochiq = [dict(b) for b in _chek_buyurtmalar(uid) if b.get('holat') == 'kutilmoqda']
            takror = next((b for b in ochiq if fid and fid in (b.get('chek_fid') or [])), None)
            kut = next((b for b in ochiq if b.get('chek') == 'kut'), None)
            nishon = takror or kut or (ochiq[0] if len(ochiq) == 1 else None)
            if takror:
                order, holat = takror.get('order'), 'dup'
            elif nishon:
                order, holat = nishon.get('order'), 'bor'
            else:
                holat = 'yoq' if not ochiq else 'tanla'
            if mgid and holat in ('bor', 'tanla'):
                _CHEK_ALBOM[(uid, mgid)] = {'t': hozir, 'order': order, 'mid': [mid]}
            if holat == 'tanla':
                _CHEK_TANLASH[(uid, mid)] = {'t': hozir, 'fid': fid, 'mgid': mgid}
    if davomi:
        if order:   # order yo'q — so'ralmoqda: tanlangach hammasi birga ketadi
            with _MIJOZ_LOCK:
                b = next((dict(x) for x in _chek_buyurtmalar(uid) if x.get('order') == order), None)
            if b:
                _chek_adminga(uid, b, mid, davomi=True)
                if fid:
                    _chek_belgi(uid, order, chek_fid=([fid] + list(b.get('chek_fid') or []))[:10])
        return 'davomi'
    til = _chek_tel_til(user, nishon)
    if holat == 'yoq':
        _chek_yubor(uid, _chek_matn(
            til, "ℹ️ Sizda to'lov kutayotgan buyurtma topilmadi. Savolingiz bo'lsa — adminga yozing.",
            "ℹ️ У вас нет заказа, ожидающего оплаты. Если есть вопрос — напишите админу."),
            {'inline_keyboard': [[_chek_admin_tugma()]]})
        return 'yoq'
    if holat == 'dup':
        o = html_escape(order)
        _chek_yubor(uid, _chek_matn(
            til, f"ℹ️ Bu chek allaqachon qabul qilingan — buyurtma №{o}. Admin siz bilan aloqaga chiqadi.",
            f"ℹ️ Этот чек уже принят — заказ №{o}. Админ свяжется с вами."), {'inline_keyboard': [[_chek_admin_tugma()]]})
        return 'dup'
    if holat == 'tanla':
        qator = [[{'text': f"№{b.get('order')} · {_chek_summa_s(b)}", 'callback_data': f"chm:{b.get('order')}:{mid}"}]
                 for b in ochiq[:6]]
        _chek_yubor(uid, _chek_matn(til, "🧾 Bu chek qaysi buyurtma uchun?", "🧾 Для какого заказа этот чек?"),
                    {'inline_keyboard': qator})
        return 'tanla'
    return _chek_topshir(uid, user, order, [mid], fid)


def _chek_tugma(uid, cq_data, user=None):
    """Mijoz tugmalari: chk:<order> — «To'landim» · chm:<order>:<message_id> — «shu buyurtma uchun» (chek allaqachon yuborilgan)."""
    p = cq_data.split(':')
    if len(p) < 2 or not re.fullmatch(r'[A-Z0-9]{4,12}', p[1]):
        return None
    order = p[1]
    if p[0] == 'chk' and len(p) == 2:
        return _chek_boshla(uid, order, user)
    if p[0] == 'chm' and len(p) == 3 and p[2].isdigit():
        mid = int(p[2])
        with _MIJOZ_LOCK:
            b = next((x for x in _chek_buyurtmalar(uid) if x.get('order') == order), None)
        if not b or b.get('holat') != 'kutilmoqda':
            return _chek_boshla(uid, order, user)   # holat bo'yicha tushuntiradi
        with _CHEK_QULF:
            t = _CHEK_TANLASH.pop((uid, mid), None)
            if t is None:   # bot qayta yongan yoki tugma ikki marta bosilgan — chek allaqachon ishlangan yoki xotira yo'q
                return _chek_boshla(uid, order, user)
            alb = _CHEK_ALBOM.get((uid, t.get('mgid'))) if t.get('mgid') else None
            mids = list(alb['mid']) if alb else [mid]
            if alb:
                alb['order'] = order
        return _chek_topshir(uid, user, order, mids, t.get('fid'))
    return None


async def chek_tugma(uid, cq_data, user=None):
    try:
        await blok(_chek_tugma, uid, cq_data, user)
    except Exception as e:
        logger.error(f'chek_tugma: {type(e).__name__}')


async def chek_qabul(uid, user, message):
    try:
        return await blok(_chek_qabul, uid, user, message)
    except Exception as e:
        logger.error(f'chek_qabul: {type(e).__name__}')


async def chek_boshla(uid, user, order):
    try:
        await blok(_chek_boshla, uid, order, user)
    except Exception as e:
        logger.error(f'chek_boshla: {type(e).__name__}')


# ══ BUGUN305: chek kelmasa — adminga eslatma ══
# Mijoz «To'landim» bosdi (chek = 'kut'), lekin 1 soat chek yubormadi → adminga BITTA eslatma (takror yo'q: chek_esl).
# Vaqt (chek_ts) va belgi (chek_esl) buyurtma yozuvida — Sheets'dagi «Buyurtmalar» varag'iga ham yoziladi, shuning uchun bot uxlab
# qolsa yoki Render qayta yonsa ham eslatma yo'qolmaydi: fon sikli har daqiqa tekshiradi, bot qayta yonsa Sheets'dan o'qigach davom etadi.
# 🌙 Tunda (Toshkent 23:00–08:00) yuborilmaydi — 08:00 dan keyin birinchi tekshiruvda ketadi. Chek kelsa (chek = 'HH:MM'),
# buyurtma to'langan / bekor bo'lsa — eslatma ketmaydi.
CHEK_ESLATMA_S = 3600
CHEK_ESLATMA_ORALIQ_S = 60


def _chek_tun(ts):
    """Toshkent vaqti bilan 23:00–08:00 (jim soatlar)."""
    soat = int(_kk_vaqt(ts)[11:13])
    return soat >= 23 or soat < 8


def _chek_eslatma_matn(b, hozir=None):
    o = html_escape(b.get('order', ''))
    bosilgan = _kk_vaqt(b.get('chek_ts') or time.time())[-5:]
    return (f"⏰ <b>Chek kelmadi</b> — №{o}\n💵 {html_escape(_chek_summa_s(b))}\n"
            f"🧾 «To'landim» bosilgan: {bosilgan}\n\n"
            f"⏳ To'lov kutilmoqda\n🕒 {_kk_vaqt(hozir or time.time())}")


def _chek_eslatma_yubor(uid, b, hozir=None):
    """Adminga: eslatma + «✅ To'lov keldi» + «✍️ Mijozga yozish». Natija — _kk_tg natijasi."""
    tolandi = _HOLAT_ADMIN['tolandi']
    klava = {'inline_keyboard': [
        [{'text': f'{tolandi[0]} {tolandi[1]}', 'callback_data': f"bh:tolandi:{uid}:{b.get('order')}"}],
        [{'text': '✍️ Mijozga yozish', 'url': f'tg://user?id={uid}'}]]}
    natija, _ = _kk_tg('sendMessage', {'chat_id': ADMIN_ID, 'text': _chek_eslatma_matn(b, hozir), 'parse_mode': 'HTML',
                                       'reply_markup': klava, 'link_preview_options': {'is_disabled': True}}, urinish=2)
    return natija


def _chek_eslatma_ish(hozir=None):
    """Bir tekshiruv. Qaytaradi — yuborilgan eslatmalar soni. «kut» holatda vaqti yozilmagan eski buyurtma — hisob hozirdan boshlanadi."""
    hozir = int(hozir if hozir is not None else time.time())
    if _chek_tun(hozir):
        return 0
    nomzod = []
    with _MIJOZ_LOCK:
        for uid, m in list(_MIJOZ.items()):
            for b in m['buyurtma']:
                if b.get('chek') != 'kut' or b.get('holat') != 'kutilmoqda' or b.get('chek_esl'):
                    continue
                if not b.get('chek_ts'):
                    b['chek_ts'] = hozir
                    _mijoz_saqlash()
                    _mijoz_sync_belgila('b', uid, b.get('order'))
                elif hozir - int(b['chek_ts']) >= CHEK_ESLATMA_S:
                    nomzod.append((uid, b.get('order')))
    yuborildi = 0
    for uid, order in nomzod:
        with _MIJOZ_LOCK:   # yuborishdan oldin qayta tekshiramiz va band qilamiz (chek kelgan bo'lishi mumkin; ikki marta ketmasin)
            b = next((x for x in _chek_buyurtmalar(uid) if x.get('order') == order), None)
            if not b or b.get('chek') != 'kut' or b.get('holat') != 'kutilmoqda' or b.get('chek_esl'):
                continue
            b['chek_esl'] = 'x'
            _mijoz_saqlash()
            b = dict(b)
        natija = _chek_eslatma_yubor(uid, b, hozir)
        # 'noaniq' — ketgan bo'lishi mumkin: qayta yuborilmaydi (ikki eslatma bo'lmasin); aniq rad etilsa — keyingi tekshiruvda qayta
        qiymat = _kk_vaqt(hozir)[-5:] if natija in ('yuborildi', 'noaniq') else ''
        _chek_belgi(uid, order, chek_esl=qiymat)
        if qiymat:
            yuborildi += 1
    return yuborildi


async def chek_eslatma_loop():
    """BUGUN305: har daqiqada — 1 soat chek kelmagan buyurtmalar uchun adminga eslatma."""
    await asyncio.sleep(120)   # ishga tushganda avval mijoz_sync_loop Sheets'dan yuklab olsin
    while True:
        try:
            n = await blok(_chek_eslatma_ish)
            if n:
                logger.info(f'chek: {n} ta eslatma adminga yuborildi')
        except Exception as e:
            logger.error(f'chek_eslatma_loop: {type(e).__name__}')
        await asyncio.sleep(CHEK_ESLATMA_ORALIQ_S)


# ══ BUGUN295: buyurtma yo'qolmasin ══
# 2026-10-19 20:2x: mijoz to'lab chek yubordi, adminga xabar kelmadi. Sabab: №261 19:21 da Store'da (skript bilan) «waited → active»
# qilingan, bot xotirasida esa «waited» qolgan — bot buyurtmani «yopiq» deb 502 bilan rad etgan va HECH QAYERGA yozmagan.
# Endi: (1) sayt buyurtmani AVVAL Store'ga yozadi (Apps Script buyurtmaZaxira), keyin botga; (2) bot yopiq / topilmagan tovarni
# Store'dan qayta o'qiydi va baribir rad etmaydi (⚠️ bilan); (3) bot avval yozuvni saqlaydi (admin_xabar = 'kutilmoqda'), keyin
# adminga 3 urinish bilan yuboradi; (4) fon sikli (buyurtma_xabar_loop) xabari chiqmaganlarni — bot qayta ishga tushgan bo'lsa
# ham (Sheets'dan) — qayta yuboradi.
_BUYURTMA_YOPIQ = ('deleted', 'waited', 'sold')
_BUYURTMA_OGOH = {'yopiq': "Store'da yopiq (sotilgan / chala / o'chirilgan) — mijoz to'lagan bo'lishi mumkin, tekshiring",
                  'topilmadi': "Store'da topilmadi — tekshiring"}
_BUYURTMA_TEL_YOQ = "— (saqlangan raqam botda topilmadi — «Mijozga yozish» orqali so'rang)"
_BUYURTMA_JARAYON = set()     # (uid, order) — xabari hozir yuborilayotgan (sayt qayta urinsa / fon sikli — ikki marta emas)
_BUYURTMA_QAYTA = "♻️ <b>Qayta yuborildi</b> — birinchi xabar adminga yetmagan edi (sayt zaxirasidan / bot qayta ishga tushgan).\n\n"


def _buyurtma_elon(n):
    """(elon, models, ogoh). Xotirada yo'q yoki yopiq bo'lsa — Store'dan YANGIDAN o'qiladi (xotira eskirgan bo'lishi mumkin).
    ogoh: '' · 'yopiq' (Store'da ham yopiq) · 'topilmadi' (elon — {'num': n} o'rinbosar, narx '—')."""
    elon, models = elon_cache_get(n)
    if not elon or elon_status(elon) in _BUYURTMA_YOPIQ:
        yangi, md = fetch_elon_by_num(n)
        if yangi:
            elon_cache_put(dict(yangi))
            elon, models = yangi, (models or md or {})
    if not elon:
        return {'num': str(n)}, models or {}, 'topilmadi'
    return elon, models or {}, ('yopiq' if elon_status(elon) in _BUYURTMA_YOPIQ else '')


def _buyurtma_tayyorla(uid, num, order, ism, tel, joy, kurs, qolgan_nums=(), sonlar=None, ranglar=None, kel=None, kel_ogoh=False,
                       tel_ogoh=False):
    """Fon oqimida. Adminga xabar: {'matn', 'bron'} (bron — tugmalar va bron uchun raqamlar). Hech qachon rad etmaydi."""
    elon, models, o = _buyurtma_elon(num)
    model = models.get(str(elon.get('specId', '') or ''), {})
    ogoh = [(str(num), o)] if o else []
    qolgan, bron = [], [str(num)]
    for n in qolgan_nums:
        e, ms, o = _buyurtma_elon(n)
        if o:
            ogoh.append((str(n), o))
        if o == 'topilmadi':   # Store'da umuman yo'q — ro'yxatga ham, bronga ham kirmaydi (faqat ⚠️ qatori)
            continue
        qolgan.append((e, ms.get(str(e.get('specId', '') or ''), {})))
        bron.append(str(n))
    matn = _buyurtma_matn(uid, elon, model, order, ism, tel, joy, kurs, qolgan, sonlar, ranglar, kel, kel_ogoh, ogoh, tel_ogoh)
    return {'matn': matn, 'bron': bron}


def _buyurtma_xabar_belgila(uid, order, qiymat):
    """Yozuvda admin_xabar = qiymat ('kutilmoqda' | 'HH:MM' yuborilgan vaqt) → fayl + Sheets navbati."""
    with _MIJOZ_LOCK:
        b = next((x for x in _mijoz_ol(uid)['buyurtma'] if x.get('order') == order), None)
        if not b:
            return
        b['admin_xabar'] = qiymat
        if qiymat != 'kutilmoqda':
            b.pop('_xabar', None)
        _mijoz_saqlash()
        _mijoz_sync_belgila('b', uid, order)


def _buyurtma_xabar_yubor(uid, order, tayyor, kutish=(0, 2, 5)):
    """Adminga buyurtma xabari — 3 urinish. HTML rad etilsa (400) — oddiy matn bilan. Yuborilsa — admin_xabar = vaqt. True/False."""
    klava = _buyurtma_klava(uid, order, 'kutilmoqda', tayyor.get('bron') or [])
    matn = tayyor['matn']
    for k in kutish:
        if k:
            time.sleep(k)
        natija, _ = _kk_tg('sendMessage', {'chat_id': ADMIN_ID, 'text': matn, 'parse_mode': 'HTML', 'reply_markup': klava,
                                           'link_preview_options': {'is_disabled': True}}, timeout=15, urinish=2)
        if natija == 'xato':   # HTML buzuq bo'lsa ham xabar yetsin
            oddiy = _html.unescape(re.sub(r'<[^>]+>', '', matn))
            natija, _ = _kk_tg('sendMessage', {'chat_id': ADMIN_ID, 'text': oddiy, 'reply_markup': klava}, timeout=15, urinish=2)
        if natija == 'yuborildi':
            _buyurtma_xabar_belgila(uid, order, _kk_vaqt(time.time())[-5:])
            return True
    logger.error(f'buyurtma xabari: №{order} adminga yetmadi — fon sikli qayta yuboradi')
    return False


def _buyurtma_tayyor_yozuvdan(uid, b):
    """Xabar matni saqlanmagan (bot qayta ishga tushgan / faqat sayt zaxirasi) — yozuvning o'zidan yasaladi."""
    joy = dict(b.get('joy') or {})
    joy['tur'] = b.get('tur') or joy.get('tur') or ''
    tovar = [x for x in (b.get('tovar') or []) if x.get('num')]
    nums = [str(x['num']) for x in tovar]
    if not nums:
        return None
    sonlar = {}
    for x in tovar:
        try:
            sonlar[str(x['num'])] = max(1, min(99, int(x.get('soni') or 1)))
        except Exception:
            pass
    ranglar = {}
    for k, v in (joy.get('ranglar') or {}).items():
        try:
            ranglar[str(k)] = [(str(r.get('r') or ''), int(r.get('n'))) for r in v if r.get('r')]
        except Exception:
            pass
    kel, kel_ogoh = ({}, False)
    if joy.get('savat'):
        kel, kel_ogoh = _savat_kel_narxlar([str(k) for k in joy['savat']][:3], nums)
    try:
        kurs = int(float(joy.get('kurs') or 0))
    except Exception:
        kurs = 0
    tel = b.get('tel') or ''
    if not tel and joy.get('tel_id') in _MIJOZ_TEL_TURLAR:
        tel = (_mijoz_ol(uid).get('tels') or {}).get(joy['tel_id'], '')
    t = _buyurtma_tayyorla(uid, nums[0], b.get('order'), b.get('ism') or '—', tel, joy, kurs if 1000 <= kurs <= 100000 else 0,
                           nums[1:], sonlar, ranglar, kel, kel_ogoh, tel_ogoh=not tel)
    return t


def _buyurtma_zaxira_birlash(j):
    """Apps Script zaxiraOl → xotirada yo'q buyurtmalar qo'shiladi (sayt yozgan, bot olmagan). Qaytaradi — qo'shilganlar soni."""
    yangi = 0
    with _MIJOZ_LOCK:
        for z in (j.get('buyurtma') or []):
            uid, order = str(z.get('user_id') or ''), str(z.get('order') or '').upper()
            if not uid.isdigit() or not re.fullmatch(r'[A-Z0-9]{4,12}', order):
                continue
            m = _mijoz_ochiq(uid)
            if any(x.get('order') == order for x in m['buyurtma']):
                continue
            joy = z.get('joy') if isinstance(z.get('joy'), dict) else {}
            tel = z.get('tel') or ''
            if not tel and joy.get('tel_id') in _MIJOZ_TEL_TURLAR:
                tel = m['tels'].get(joy['tel_id'], '')
            m['buyurtma'].insert(0, {
                'order': order, 'ts': float(z.get('ts') or time.time()), 'holat': z.get('holat') or 'kutilmoqda',
                'tovar': [x for x in (z.get('tovar') or []) if isinstance(x, dict)], 'jami': z.get('jami'), 'tur': z.get('tur') or '',
                'ism': z.get('ism') or '', 'tel': tel, 'til': z.get('til') if z.get('til') in ('uz', 'ru') else '',
                'nik': str(joy.get('nik') or ''), 'joy': joy, 'manba': 'sayt', 'admin_xabar': 'kutilmoqda'})
            m['buyurtma'].sort(key=lambda x: x.get('ts') or 0, reverse=True)
            del m['buyurtma'][MIJOZ_BUYURTMA_MAX:]
            _BUYURTMA_KORILGAN[(int(uid), order)] = time.time()
            for x in z.get('tovar') or []:   # bron — /buyurtma dagi kabi (faqat bo'sh e'lon)
                if isinstance(x, dict) and x.get('num') and not _bron_olish(x['num']):
                    _bron_qoy(str(x['num']), int(uid), order)
            yangi += 1
        if yangi:
            _mijoz_saqlash()
    return yangi


BUYURTMA_QAYTA_S = 150          # shuncha soniyadan keyin ham xabari chiqmagan buyurtma — fon sikli yuboradi
BUYURTMA_XABAR_ORALIQ_S = 120


def _buyurtma_xabar_ish():
    """Fon sikli bir qadami: sayt zaxirasi → xotira; xabari chiqmaganlar → adminga. Qaytaradi — yuborilganlar soni."""
    if _mijoz_sync_yoqilgan():
        j = _kk_sheet('zaxiraOl', timeout=40)
        if j and j.get('ok'):
            _buyurtma_zaxira_birlash(j)
    hozir = time.time()
    ish = []
    with _MIJOZ_LOCK:
        for uid, m in _MIJOZ.items():
            for b in m['buyurtma']:
                if (b.get('admin_xabar') == 'kutilmoqda' and hozir - (b.get('ts') or 0) > BUYURTMA_QAYTA_S
                        and (int(uid), b.get('order')) not in _BUYURTMA_JARAYON):
                    ish.append((int(uid), dict(b)))
    yuborildi = 0
    for uid, b in ish:
        k = (uid, b.get('order'))
        if b.get('holat') == 'bekor':   # mijoz o'zi bekor qilgan — xabar shart emas
            _buyurtma_xabar_belgila(uid, b.get('order'), 'bekor')
            continue
        _BUYURTMA_JARAYON.add(k)
        try:
            t = b.get('_xabar') or _buyurtma_tayyor_yozuvdan(uid, b)
            if not t:
                _buyurtma_xabar_belgila(uid, b.get('order'), '-')
                continue
            t = dict(t, matn=_BUYURTMA_QAYTA + t['matn'])
            if _buyurtma_xabar_yubor(uid, b.get('order'), t, kutish=(0, 3)):
                yuborildi += 1
                _chek_mijozga_xabar(uid, b.get('order'))   # BUGUN296: sayt zaxirasidan tiklangan buyurtma — mijozga ham (bir marta)
        except Exception as e:
            logger.error(f'buyurtma xabar ish: {type(e).__name__}')
        finally:
            _BUYURTMA_JARAYON.discard(k)
    return yuborildi


async def buyurtma_xabar_loop():
    """BUGUN295: har ~2 daqiqada — adminga yetmagan buyurtma xabarlari (sayt zaxirasi ham)."""
    await asyncio.sleep(90)   # ishga tushganda avval mijoz_sync_loop Sheets'dan yuklab olsin
    while True:
        try:
            n = await blok(_buyurtma_xabar_ish)
            if n:
                logger.info(f'buyurtma: {n} ta xabar adminga qayta yuborildi')
        except Exception as e:
            logger.error(f'buyurtma_xabar_loop: {type(e).__name__}')
        await asyncio.sleep(BUYURTMA_XABAR_ORALIQ_S)


def _buyurtma_yubor(uid, num, order, ism, tel, joy, kurs, qolgan_nums=(), sonlar=None, ranglar=None, kel=None, kel_ogoh=False,
                    tel_ogoh=False, tayyor=None):
    """Fon oqimida. (ok, sabab). BUGUN295: hech qachon rad etmaydi (yopiq / topilmagan — ⚠️ bilan); 3 urinish; yetmasa
    sabab 'telegram' — yozuv admin_xabar = 'kutilmoqda' bo'lib qoladi, fon sikli qayta yuboradi."""
    if tayyor is None:
        tayyor = _buyurtma_tayyorla(uid, num, order, ism, tel, joy, kurs, qolgan_nums, sonlar, ranglar, kel, kel_ogoh, tel_ogoh)
    ok = _buyurtma_xabar_yubor(uid, order, tayyor)
    return ok, ('' if ok else 'telegram')


async def buyurtma_endpoint(request):
    """Sayt «Sotib olish» → manzil kiritilgach shu yerga yuboradi → admin botda xabar oladi.

    Bu yo'l HAMMA mijoz uchun (ADMIN_ID tekshiruvi yo'q). Himoya:
      1) initData imzosi — so'rov Mini App ichidan kelganini isbotlaydi (imzosiz — 401)
      2) num faqat raqam; narx/nom e'londan olinadi — mijoz yuborgan narxga ishonilmaydi
      3) maydon uzunligi cheklangan; bitta mijozga 10 daqiqada 5 ta buyurtma
      4) bir xil buyurtma raqami ikkinchi marta xabar yubormaydi
    Xato bo'lsa sayt baribir to'lov sahifasiga o'tadi (mijoz to'xtab qolmaydi) —
    xabar bormagan bo'lsa chek paneli orqali admin baribir biladi.
    """
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        num = str(data.get('num', '') or '').strip()
        order = str(data.get('order', '') or '').strip().upper()
        ism = re.sub(r'\s+', ' ', str(data.get('name', '') or '')).strip()
        tel = re.sub(r'[^\d+ ()-]', '', str(data.get('phone', '') or '')).strip()
        # BUGUN225: mijoz profildagi saqlangan raqamni tanlasa sayt faqat 'tel_id' yuboradi (raqam saytda ochiq turmaydi)
        tel_id = str(data.get('tel_id', '') or '').strip()
        tel_ogoh = False
        if tel_id:
            tel = (_mijoz_ol(uid).get('tels') or {}).get(tel_id, '') if tel_id in _MIJOZ_TEL_TURLAR else ''
            tel_ogoh = not tel and tel_id in _MIJOZ_TEL_TURLAR   # BUGUN295: bot xotirasida yo'q (qayta ishga tushgan) — rad etilmaydi, adminga ⚠️
        tur = str(data.get('tur', '') or '').strip()
        joy = {'tur': tur if tur in _BUYURTMA_TUR else ''}
        if tur == 'yandex':
            # Koordinata (bo'lsa): faqat son, dunyo chegarasida — Yandex havolasini bot o'zi yasaydi (mijoz matni havolaga tushmaydi)
            if data.get('lat') is not None or data.get('lon') is not None:
                try:
                    lat, lon = float(data.get('lat')), float(data.get('lon'))
                except Exception:
                    return web.json_response({'error': 'Joy notogri'}, status=400)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    return web.json_response({'error': 'Joy notogri'}, status=400)
                joy.update(lat=round(lat, 6), lon=round(lon, 6))
        elif tur in ('emu', 'bts'):
            # BUGUN207: mijoz filialni oddiy matn bilan yozadi («Samarqand, Qo'shko'pir filiali») — faqat uzunligi tekshiriladi
            manzil = re.sub(r'[\x00-\x1f\x7f\s]+', ' ', str(data.get('manzil', '') or '')).strip()
            if not (1 <= len(manzil) <= 150):
                return web.json_response({'error': 'Filial notogri'}, status=400)
            joy['manzil'] = manzil
        else:
            # eski sayt (tur yo'q) — erkin matn manzil
            manzil = re.sub(r'[ \t]+', ' ', str(data.get('address', '') or '')).strip()
            if not (1 <= len(manzil) <= 300):
                return web.json_response({'error': 'Maydon notogri'}, status=400)
            joy['manzil'] = manzil
        try:
            kurs = int(float(data.get('kurs', 0) or 0))
        except Exception:
            kurs = 0
        if not re.fullmatch(r'\d{1,6}', num):
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        # BUGUN224: savatdan — nums (hamma raqam, birinchisi = num). Ko'pi bilan 10 ta, faqat raqam, takrorsiz
        nums_xom = data.get('nums') or []
        if not isinstance(nums_xom, list) or len(nums_xom) > 10:
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        qolgan_nums = []
        for n in nums_xom:
            n = str(n or '').strip()
            if not re.fullmatch(r'\d{1,6}', n):
                return web.json_response({'error': 'Nomer notogri'}, status=400)
            if n != num and n not in qolgan_nums:
                qolgan_nums.append(n)
        # BUGUN236: dona soni — {num: dona} (faqat shu buyurtmadagi raqamlar, 1..99; omborda borigacha — _buyurtma_soni)
        sonlar = {}
        sonlar_xom = data.get('sonlar') or {}
        if not isinstance(sonlar_xom, dict) or len(sonlar_xom) > 10:
            return web.json_response({'error': 'Soni notogri'}, status=400)
        for k, v in sonlar_xom.items():
            k = str(k or '').strip()
            try:
                v = int(v)
            except Exception:
                return web.json_response({'error': 'Soni notogri'}, status=400)
            if k not in [num] + qolgan_nums or not (1 <= v <= 99):
                return web.json_response({'error': 'Soni notogri'}, status=400)
            sonlar[k] = v
        # BUGUN236 §8: ranglar — {num: [{r: rang nomi, n: dona}]} (faqat shu buyurtmadagi raqamlar; rang e'londa bormi va
        # sonigacha — _buyurtma_ranglar). Ichki ko'rinishi {num: [(rang, dona)]}
        ranglar = {}
        ranglar_xom = data.get('ranglar') or {}
        if not isinstance(ranglar_xom, dict) or len(ranglar_xom) > 10:
            return web.json_response({'error': 'Rang notogri'}, status=400)
        for k, v in ranglar_xom.items():
            k = str(k or '').strip()
            if k not in [num] + qolgan_nums or not isinstance(v, list) or not (1 <= len(v) <= 10):
                return web.json_response({'error': 'Rang notogri'}, status=400)
            qator = []
            for x in v:
                try:
                    r = re.sub(r'[\x00-\x1f\x7f\s]+', ' ', str(x.get('r') or '')).strip()
                    n = int(x.get('n'))
                except Exception:
                    return web.json_response({'error': 'Rang notogri'}, status=400)
                if not (1 <= len(r) <= 40) or not (1 <= n <= 99):
                    return web.json_response({'error': 'Rang notogri'}, status=400)
                qator.append((r, n))
            ranglar[k] = qator
        # BUGUN287: ulashilgan savat havolasi kodlari (≤3) — kelishilgan narxni bot Apps Script'dan o'zi oladi (narx saytdan kelmaydi)
        savat_xom = data.get('savat') or []
        if not isinstance(savat_xom, list) or len(savat_xom) > 3:
            return web.json_response({'error': 'Savat notogri'}, status=400)
        savat_kodlar = []
        for k in savat_xom:
            k = str(k or '').strip().lower()
            if not re.fullmatch(r'[a-z0-9]{6,12}', k):
                return web.json_response({'error': 'Savat notogri'}, status=400)
            if k not in savat_kodlar:
                savat_kodlar.append(k)
        if not re.fullmatch(r'[A-Z0-9]{4,12}', order):
            return web.json_response({'error': 'Buyurtma raqami notogri'}, status=400)
        if not (1 <= len(ism) <= 60):
            return web.json_response({'error': 'Maydon notogri'}, status=400)
        if not tel_ogoh and (len(re.sub(r'\D', '', tel)) < 9 or len(tel) > 25):
            return web.json_response({'error': 'Telefon notogri'}, status=400)
        if not (1000 <= kurs <= 100000):
            return web.json_response({'error': 'Kurs notogri'}, status=400)
        joy['kurs'] = kurs   # BUGUN296: mijozga «💳 To'lash» havolasi (so'm = $ × shu kurs) — sayt bilan bir xil summa
        hozir = time.time()
        if (uid, order) in _BUYURTMA_KORILGAN or (uid, order) in _BUYURTMA_JARAYON:
            return web.json_response({'ok': True, 'takror': True})
        oxirgilar = [t for t in _BUYURTMA_SONI.get(uid, []) if hozir - t < 600]
        if len(oxirgilar) >= 5:
            return web.json_response({'error': 'Juda ko\'p'}, status=429)
        _BUYURTMA_SONI[uid] = oxirgilar + [hozir]
        loop = asyncio.get_event_loop()
        kel, kel_ogoh = ({}, False)
        if savat_kodlar:
            kel, kel_ogoh = await loop.run_in_executor(None, _savat_kel_narxlar, savat_kodlar, [num] + qolgan_nums)
        # BUGUN295: avval yozuv (admin_xabar = 'kutilmoqda'), keyin xabar — 3 urinish; yetmasa fon sikli qayta yuboradi.
        # Ilgari xabar ketmasa (yopiq tovar / tarmoq) — 502 va hech narsa saqlanmasdi (20:2x buyurtmasi shunday yo'qolgan).
        _BUYURTMA_JARAYON.add((uid, order))
        try:
            tayyor = await loop.run_in_executor(None, _buyurtma_tayyorla, uid, num, order, ism, tel, joy, kurs, qolgan_nums,
                                                sonlar, ranglar, kel, kel_ogoh, tel_ogoh)
            # BUGUN225: raqam profilga (akkaunt / yetkazish) + «Buyurtmalarim» yozuvi
            nik = ((_init_data_user(data.get('initData', '')) or {}).get('username') or '')   # BUGUN275: sotuv yozuvi uchun
            await loop.run_in_executor(None, _mijoz_buyurtma_yoz, uid, order, num, qolgan_nums, ism, tel, joy,
                                       _kk_init_til(data.get('initData', '')) or '', sonlar, ranglar, nik, kel, tayyor)
            _BUYURTMA_KORILGAN[(uid, order)] = hozir
            yetdi, _ = await loop.run_in_executor(
                None, functools.partial(_buyurtma_yubor, uid, num, order, ism, tel, joy, kurs, qolgan_nums, sonlar, ranglar, kel,
                                        kel_ogoh, tel_ogoh, tayyor=tayyor))
        finally:
            _BUYURTMA_JARAYON.discard((uid, order))
        # BUGUN296: mijozga botda buyurtma xabari (tarkib · jami · «💳 To'lash» · «🧾 To'landim») — fonda, javobni kutdirmaydi
        loop.run_in_executor(None, _chek_mijozga_xabar, uid, order)
        # BUGUN208: bron. Bo'sh e'lon — shu mijozga bron; allaqachon boshqa mijozda bo'lsa (poyga) — bron o'zgarmaydi,
        # adminga 2-buyurtma haqida ogohlantirish (1-mijoz olmasa 2-chisiga o'zi chiqadi).
        for bn in [num] + qolgan_nums:   # BUGUN224: savatdagi har tovarga
            b = _bron_olish(bn)
            if not b or b['uid'] == uid:
                _bron_qoy(bn, uid, order)
            else:
                ikkinchi = {'id': uid, 'ism': ism,
                            'username': (_init_data_user(data.get('initData', '')) or {}).get('username', '')}
                loop.run_in_executor(None, _bron_ogoh_yubor, bn, ikkinchi, f"buyurtma berdi (№{order})")
        for k in [k for k, v in _BUYURTMA_KORILGAN.items() if hozir - v > 86400]:
            _BUYURTMA_KORILGAN.pop(k, None)
        return web.json_response({'ok': True, 'xabar': yetdi})
    except Exception as e:
        logger.error(f'buyurtma_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)



# ══ BUGUN225: mijoz profili — 2 ta raqam (akkaunt · yetkazish) va «Buyurtmalarim» ══
# BUGUN271: /mijoz_holat imzosi tekshirilgan EGASIGA o'z raqamlarini to'liq qaytaradi (foydalanuvchi: «hech bir marketpleysda bunaqa
# yashirin turmaydi»); boshqa hech kimga — yo'q (imzo shart, uid imzodan). Sotib olishda sayt baribir 'tel_id' ('akkaunt' |
# 'dostavka') yuboradi, bot to'liq raqamni o'zi oladi. Yetkazish raqamini mijoz profildan o'zgartiradi — /mijoz_tel. Raqam qachon olinadi: konkursda (botda
# «Raqamni ulashish» — handle_phone) va «Sotib olish» bosilganda (/buyurtma). Saqlash: xotira + MIJOZ_FAYL (bron kabi: Render
# qayta ishga tushsa fayl o'chadi — doimiy saqlash Apps Script'ni talab qiladi; eng ko'pi bilan mijoz raqamini qayta yozadi).
MIJOZ_FAYL = os.environ.get('MIJOZ_FAYL', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mijoz_holat.json'))
_MIJOZ_TEL_TURLAR = ('akkaunt', 'dostavka')
_MIJOZ = {}             # str(uid) → {'tels': {'akkaunt': '+998…', 'dostavka': '…'}, 'buyurtma': [ {order, ts, holat, …} ]}
_MIJOZ_LOCK = threading.RLock()
MIJOZ_BUYURTMA_MAX = 30   # bitta mijozda saqlanadigan oxirgi buyurtmalar soni


def _mijoz_yuklash():
    try:
        with open(MIJOZ_FAYL, encoding='utf-8') as f:
            d = json.load(f)
        for k, v in d.items():
            if isinstance(v, dict):
                _MIJOZ[str(k)] = {'tels': dict(v.get('tels') or {}), 'buyurtma': list(v.get('buyurtma') or [])}
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f'mijoz yuklash: {e}')


def _mijoz_saqlash():
    try:
        with open(MIJOZ_FAYL, 'w', encoding='utf-8') as f:
            json.dump(_MIJOZ, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f'mijoz saqlash: {e}')


# ── BUGUN227: doimiy saqlash (Google Sheets, Apps Script mijozTelYoz / buyurtmaYoz / mijozHammasi) ──────────────────────────
# Render qayta ishga tushsa (har deploy) MIJOZ_FAYL o'chadi — shuning uchun har o'zgarish Sheets'ga ham yoziladi, bot ishga
# tushganda esa Sheets'dan o'qib olinadi. Yozish fonda va navbat bilan: tarmoq / Apps Script yiqilsa — navbatda qoladi, 5 soniyada
# qayta uriniladi (webhook kutmaydi — T1). Raqamlar jadvalda: faqat egasi ko'radi, saytga hech qachon chiqmaydi.
# SHEET_URL yoki API_KEY yo'q (sinov, mahalliy ishga tushirish) — sinxronlash umuman yurmaydi, faqat fayl.
_MIJOZ_SYNC = set()           # navbat: ('t', uid) · ('b', uid, order)
_MIJOZ_SYNC_QULF = threading.Lock()
MIJOZ_SYNC_ORALIQ_S = 5


def _mijoz_sync_yoqilgan():
    return bool(SHEET_URL and API_KEY)


def _mijoz_sync_belgila(*kalit):
    """O'zgargan yozuvni navbatga qo'yadi (fon sikli Sheets'ga yozadi)."""
    if _mijoz_sync_yoqilgan():
        with _MIJOZ_SYNC_QULF:
            _MIJOZ_SYNC.add(tuple(str(x) for x in kalit))


def _buyurtma_sheet_dict(uid, b):
    """Bitta buyurtma → Apps Script `buyurtmaYoz` ma'lumoti."""
    return {'order': b.get('order'), 'user_id': str(uid), 'ts': b.get('ts'), 'holat': b.get('holat'),
            'holat_ts': b.get('holat_ts'), 'bekor_ts': b.get('bekor_ts'), 'jami': b.get('jami'), 'tur': b.get('tur', ''),
            'til': b.get('til', ''), 'ism': b.get('ism', ''), 'tel': b.get('tel', ''), 'admin_xabar': b.get('admin_xabar') or None, 'chek': b.get('chek') or '',
            'chek_ts': b.get('chek_ts'), 'chek_esl': b.get('chek_esl') or '',   # BUGUN305
            'tovar': [{'num': x.get('num'), 'nom': x.get('nom'), 'narx': x.get('narx'), 'soni': x.get('soni') or 1} for x in (b.get('tovar') or [])]}


def _mijoz_sync_yubor():
    """Navbatdagilarni Sheets'ga yozadi (bloklaydi — faqat fon oqimida). Yozilmaganlar navbatda qoladi. Nechta yozilganini qaytaradi."""
    if not _mijoz_sync_yoqilgan():
        return 0
    with _MIJOZ_SYNC_QULF:
        ish = sorted(_MIJOZ_SYNC)
    yozildi = 0
    for k in ish:
        with _MIJOZ_LOCK:   # qiymatni qulf ostida nusxalaymiz (boshqa oqim o'zgartirayotgan bo'lishi mumkin)
            m = _MIJOZ.get(k[1])
            if k[0] == 't':
                par = {'user_id': k[1], 'akkaunt': (m or {}).get('tels', {}).get('akkaunt', ''),
                       'dostavka': (m or {}).get('tels', {}).get('dostavka', '')}
                data = None
            else:
                b = next((x for x in (m or {}).get('buyurtma', []) if x.get('order') == k[2]), None)
                data = json.dumps(_buyurtma_sheet_dict(k[1], b), ensure_ascii=False) if b else None
                par = None
        if k[0] == 't':
            j = _kk_sheet('mijozTelYoz', timeout=40, **par)
        elif data is None:
            j = {'ok': True}   # yozuv endi yo'q (30 tadan oshib tushgan) — yuboradigan narsa yo'q
        else:
            j = _kk_sheet('buyurtmaYoz', timeout=40, data=data)
        if j and j.get('ok'):
            with _MIJOZ_SYNC_QULF:
                _MIJOZ_SYNC.discard(k)
            yozildi += 1
        else:
            break   # Apps Script javob bermadi — qolganini keyingi urinishga (tartib buzilmasin)
    return yozildi


def _mijoz_sheet_birlash(j):
    """Sheets'dan kelgan {tels, buyurtma} ni xotiraga qo'shadi. Navbatdagi (hali yozilmagan) mahalliy yozuv ustun;
    Sheets'da yo'q mahalliy yozuv navbatga qo'yiladi. Qaytaradi — (mijoz soni, buyurtma soni)."""
    sheet_tel, sheet_buy = set(), set()
    with _MIJOZ_LOCK:
        for t in (j.get('tels') or []):
            uid = str(t.get('user_id') or '')
            if not uid:
                continue
            sheet_tel.add(uid)
            m = _mijoz_ochiq(uid)
            if ('t', uid) in _MIJOZ_SYNC:
                continue
            for tur in _MIJOZ_TEL_TURLAR:
                if t.get(tur):
                    m['tels'][tur] = t[tur]
                else:
                    m['tels'].pop(tur, None)
        for b in (j.get('buyurtma') or []):
            uid, order = str(b.get('user_id') or ''), str(b.get('order') or '')
            if not uid or not order:
                continue
            sheet_buy.add((uid, order))
            m = _mijoz_ochiq(uid)
            if ('b', uid, order) in _MIJOZ_SYNC:
                continue
            yozuv = {'order': order, 'ts': b.get('ts') or 0, 'holat': b.get('holat') or 'kutilmoqda', 'tovar': b.get('tovar') or [],
                     'jami': b.get('jami'), 'tur': b.get('tur') or '', 'ism': b.get('ism') or '', 'tel': b.get('tel') or '',
                     'til': b.get('til') or '', 'holat_ts': b.get('holat_ts'), 'bekor_ts': b.get('bekor_ts'),
                     'admin_xabar': b.get('admin_xabar') or ''}   # BUGUN295
            if 'chek' in b:   # BUGUN296: eski Apps Script ustunni bermaydi — shunda botdagi qiymat saqlanadi
                yozuv['chek'] = b.get('chek') or ''
            if 'chek_ts' in b:   # BUGUN305: «To'landim» vaqti va eslatma belgisi — bot qayta yonsa ham qoladi
                yozuv['chek_ts'] = b.get('chek_ts')
                yozuv['chek_esl'] = b.get('chek_esl') or ''
            i = next((n for n, x in enumerate(m['buyurtma']) if x.get('order') == order), -1)
            if i >= 0:
                m['buyurtma'][i] = dict(m['buyurtma'][i], **yozuv)   # BUGUN295: faqat botdagi (nik, joy, _xabar) saqlanadi
            else:
                m['buyurtma'].append(yozuv)
        for uid, m in _MIJOZ.items():
            m['buyurtma'].sort(key=lambda x: x.get('ts') or 0, reverse=True)
            del m['buyurtma'][MIJOZ_BUYURTMA_MAX:]
            if uid not in sheet_tel and m['tels']:
                _mijoz_sync_belgila('t', uid)
            for x in m['buyurtma']:
                if (uid, x.get('order')) not in sheet_buy:
                    _mijoz_sync_belgila('b', uid, x.get('order'))
        _mijoz_saqlash()
        return len(_MIJOZ), sum(len(m['buyurtma']) for m in _MIJOZ.values())


def mijoz_sheet_yuklash():
    """Bot ishga tushganda (fon oqimida): Sheets → xotira. Apps Script uxlab turgan / eski bo'lsa — 5 marta urinadi."""
    if not _mijoz_sync_yoqilgan():
        return False
    for n in range(5):
        j = _kk_sheet('mijozHammasi', timeout=60)
        if j and j.get('ok'):
            mj, by = _mijoz_sheet_birlash(j)
            logger.info(f'mijoz: Sheets dan {mj} mijoz, {by} buyurtma yuklandi')
            return True
        time.sleep(10 * (n + 1))
    logger.error("mijoz: Sheets dan yuklab bo'lmadi (Apps Script mijozHammasi javob bermadi) — bo'sh xotira bilan davom etadi")
    return False


async def mijoz_sync_loop():
    """Bot ishga tushganda yuklaydi, keyin navbatni bo'shatib turadi."""
    await blok(mijoz_sheet_yuklash)
    while True:
        await asyncio.sleep(MIJOZ_SYNC_ORALIQ_S)
        if _MIJOZ_SYNC:
            try:
                await blok(_mijoz_sync_yubor)
            except Exception as e:
                logger.error(f'mijoz sync: {type(e).__name__}')


def _mijoz_ol(uid):
    return _MIJOZ.get(str(uid)) or {'tels': {}, 'buyurtma': []}


def _mijoz_ochiq(uid):
    m = _MIJOZ.get(str(uid))
    if m is None:
        m = _MIJOZ[str(uid)] = {'tels': {}, 'buyurtma': []}
    return m


def _tel_norm(tel):
    """Taqqoslash uchun: faqat raqamlar, oxirgi 9 tasi (+998 / 998 / 8 farqi yo'qoladi)."""
    r = re.sub(r'\D', '', str(tel or ''))
    return r[-9:] if len(r) >= 9 else r


def _tel_niqob(tel):
    """'+998 90 123 45 67' → '+998 ** *** 45 67' (oxirgi 4 raqam ochiq). Boshqa shakl — oxirgi 4 raqamdan boshqasi '*'."""
    r = re.sub(r'\D', '', str(tel or ''))
    if len(r) < 5:
        return '***'
    if len(r) == 12 and r.startswith('998'):
        return f'+998 ** *** {r[-4:-2]} {r[-2:]}'
    return '*' * (len(r) - 4) + ' ' + r[-4:]


def _tel_uz(tel):
    """BUGUN271: O'zbekiston raqami → '+998 90 123 45 67'; boshqa shakl — ''. Qabul: '+998901234567', '998 90 123-45-67', '901234567'."""
    r = re.sub(r'\D', '', str(tel or ''))
    if len(r) == 9:
        r = '998' + r
    if len(r) != 12 or not r.startswith('998') or r[3] == '0':
        return ''
    return f'+998 {r[3:5]} {r[5:8]} {r[8:10]} {r[10:]}'


def _mijoz_tels_javob(m):
    """Profil uchun raqamlar ro'yxati — faqat egasining o'ziga (imzo tekshirilgandan keyin) beriladi."""
    return [{'id': k, 'tel': m['tels'][k], 'niqob': _tel_niqob(m['tels'][k])} for k in _MIJOZ_TEL_TURLAR if m['tels'].get(k)]


def _mijoz_tel_qosh(uid, tel, manba):
    """Raqamni profilga yozadi. manba 'konkurs' — akkaunt raqami (Telegram'dan olingan, almashtiriladi);
    manba 'sotib' — akkaunt yo'q bo'lsa akkaunt; bo'lsa va boshqa raqam bo'lsa — yetkazish raqami (yangisi eskisini almashtiradi)."""
    tel = str(tel or '').strip()
    if len(re.sub(r'\D', '', tel)) < 9:
        return
    with _MIJOZ_LOCK:
        t = _mijoz_ochiq(uid)['tels']
        if manba == 'konkurs':
            t['akkaunt'] = tel
            if _tel_norm(t.get('dostavka')) == _tel_norm(tel):
                t.pop('dostavka', None)
        elif not t.get('akkaunt'):
            t['akkaunt'] = tel
        elif _tel_norm(t['akkaunt']) != _tel_norm(tel):
            t['dostavka'] = tel
        _mijoz_saqlash()
        _mijoz_sync_belgila('t', uid)


def _mijoz_tovarlar(num, qolgan_nums, sonlar=None, ranglar=None, kel=None):
    """[{num, nom, narx, soni}] — e'lonlar serverdagi keshdan (mijoz yuborganiga ishonilmaydi). narx — 1 donasi (BUGUN236).
    BUGUN287: kelishilgan narx (havoladan) bo'lsa — narx o'sha, 'chegirma' — 1 donaga."""
    res = []
    for n in [num] + list(qolgan_nums):
        elon, models = elon_cache_get(n)
        if not elon:
            continue
        model = (models or {}).get(str(elon.get('specId', '') or ''), {})
        narx, cheg = _kel_narx(elon, kel)
        x = {'num': str(elon.get('num', n)), 'nom': _buyurtma_sarlavha(elon, model, ranglar), 'narx': narx,
             'soni': _buyurtma_soni(elon, sonlar, ranglar)}
        if cheg > 0:
            x['chegirma'] = cheg
        res.append(x)
    return res


def _mijoz_buyurtma_yoz(uid, order, num, qolgan_nums, ism, tel, joy, til='', sonlar=None, ranglar=None, nik='', kel=None, xabar=None):
    """/buyurtma (fon oqimida): raqam profilga + «Buyurtmalarim» yozuvi. BUGUN295: adminga xabar yuborilishidan OLDIN —
    admin_xabar 'kutilmoqda', _xabar — tayyor matn (yetmasa fon sikli shuni qayta yuboradi), joy — qayta yasash uchun.
    Sayt zaxirasidan (fon sikli) allaqachon qo'shilgan bo'lsa — matn qo'shiladi, xolos."""
    try:
        _mijoz_tel_qosh(uid, tel, 'sotib')
        tovar = _mijoz_tovarlar(num, qolgan_nums, sonlar, ranglar, kel)
        narxlar = [None if x['narx'] is None else x['narx'] * x['soni'] for x in tovar]
        with _MIJOZ_LOCK:
            m = _mijoz_ochiq(uid)
            bor = next((b for b in m['buyurtma'] if b.get('order') == order), None)
            if bor:
                if xabar and bor.get('admin_xabar') == 'kutilmoqda':
                    bor['_xabar'] = xabar
                    _mijoz_saqlash()
                return
            m['buyurtma'].insert(0, {
                'order': order, 'ts': time.time(), 'holat': 'kutilmoqda', 'tovar': tovar,
                'jami': None if (not narxlar or any(n is None for n in narxlar)) else round(sum(narxlar), 2),
                'tur': joy.get('tur') or '', 'ism': ism, 'tel': tel, 'til': til if til in ('uz', 'ru') else '',
                'nik': re.sub(r'[^\w.]', '', str(nik or ''))[:40], 'joy': dict(joy or {}), 'admin_xabar': 'kutilmoqda',
                '_xabar': xabar})
            del m['buyurtma'][MIJOZ_BUYURTMA_MAX:]
            _mijoz_saqlash()
            _mijoz_sync_belgila('b', uid, order)
    except Exception as e:
        logger.error(f'mijoz_buyurtma_yoz: {e}')


async def mijoz_holat_endpoint(request):
    """BUGUN225: profil — raqamlar (akkaunt / yetkazish) va «Buyurtmalarim» ro'yxati. initData imzosi shart (401).
    BUGUN271: raqam to'liq ('tel') + eski 'niqob' (moslik); uid faqat imzodan — boshqa odamning raqami kelmaydi. Ism, joy YO'Q."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        with _MIJOZ_LOCK:
            m = _mijoz_ol(uid)
            tels = _mijoz_tels_javob(m)
            buyurtma = [{'order': b.get('order'), 'ts': b.get('ts'), 'holat': b.get('holat'), 'jami': b.get('jami'),
                         'tur': b.get('tur', ''), 'tovar': [{'num': x.get('num'), 'nom': x.get('nom'), 'narx': x.get('narx'), 'soni': x.get('soni') or 1}
                                                            for x in (b.get('tovar') or [])]}
                        for b in m['buyurtma']]
        return web.json_response({'ok': True, 'tels': tels, 'buyurtma': buyurtma})
    except Exception as e:
        logger.error(f'mijoz_holat_endpoint: {e}')
        return web.json_response({'error': 'xato'}, status=500)


async def mijoz_tel_endpoint(request):
    """BUGUN271: profil — yetkazish raqamini o'zgartirish. {initData, tel}. Imzo shart (401), uid faqat imzodan; raqam
    +998 XX XXX XX XX bo'lmasa — 400. Akkaunt raqami bilan bir xil bo'lsa — alohida yetkazish raqami olib tashlanadi (akkaunt
    raqamining o'zi ishlatiladi). Akkaunt raqami (Telegram) bu yerda o'zgarmaydi. Javob — /mijoz_holat dagi 'tels'."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        tel = _tel_uz(data.get('tel', ''))
        if not tel:
            return web.json_response({'error': 'format'}, status=400)
        with _MIJOZ_LOCK:
            m = _mijoz_ochiq(uid)
            if m['tels'].get('akkaunt') and _tel_norm(m['tels']['akkaunt']) == _tel_norm(tel):
                m['tels'].pop('dostavka', None)
            else:
                m['tels']['dostavka'] = tel
            _mijoz_saqlash()
            _mijoz_sync_belgila('t', uid)
            tels = _mijoz_tels_javob(m)
        return web.json_response({'ok': True, 'tels': tels})
    except Exception as e:
        logger.error(f'mijoz_tel_endpoint: {type(e).__name__}')
        return web.json_response({'error': 'xato'}, status=500)


def _bekor_adminga(uid, b, bosh_nums):
    """Fon oqimida: adminga «❌ mijoz bekor qildi»."""
    try:
        tovar = ''.join(f"{i}. {html_escape(x.get('nom') or '—')} · №{html_escape(x.get('num') or '')}\n"
                        for i, x in enumerate(b.get('tovar') or [], 1))
        matn = (f"❌ <b>Mijoz buyurtmani bekor qildi</b> №{html_escape(b.get('order', ''))}\n\n{tovar}\n"
                f"👤 {html_escape(b.get('ism', '') or '—')}\n📞 {html_escape(b.get('tel', '') or '—')}\n"
                f"🔓 Bron bekor: {', '.join('№' + html_escape(n) for n in bosh_nums) or '—'}\n"
                f"🕒 {_kk_vaqt(time.time())}")
        r = req.post(f'{TG_API}/sendMessage', json={
            'chat_id': ADMIN_ID, 'text': matn, 'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': [[{'text': 'Mijozga yozish', 'url': f'tg://user?id={uid}'}]]},
        }, timeout=10).json()
        if not r.get('ok'):
            logger.error(f"bekor adminga: {r.get('description')}")
    except Exception as e:
        logger.error(f'bekor adminga: {e}')


async def buyurtma_bekor_endpoint(request):
    """BUGUN225: mijoz «Buyurtmalarim» da «Bekor qilish» bosdi. Faqat o'z buyurtmasi, faqat «kutilmoqda» holatida.
    Bron (shu buyurtmaniki) bekor bo'ladi, adminga «❌ mijoz bekor qildi». Takror bosish — zarari yo'q (ikkinchi xabar ketmaydi)."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        order = str(data.get('order', '') or '').strip().upper()
        if not re.fullmatch(r'[A-Z0-9]{4,12}', order):
            return web.json_response({'error': 'Buyurtma raqami notogri'}, status=400)
        with _MIJOZ_LOCK:
            b = next((x for x in _mijoz_ol(uid)['buyurtma'] if x.get('order') == order), None)
            if not b:
                return web.json_response({'error': 'Topilmadi'}, status=404)
            if b.get('holat') == 'bekor':
                return web.json_response({'ok': True, 'holat': 'bekor', 'takror': True})
            if b.get('holat') != 'kutilmoqda':
                return web.json_response({'error': 'Bekor qilib bolmaydi'}, status=409)
            b['holat'] = 'bekor'
            b['bekor_ts'] = b['holat_ts'] = time.time()
            _mijoz_saqlash()
            _mijoz_sync_belgila('b', uid, order)
        bosh = []
        for x in (b.get('tovar') or []):
            n = str(x.get('num') or '')
            br = _BRON.get(n)
            if br and br.get('order') == order and br.get('uid') == uid:
                _BRON.pop(n, None)
                bosh.append(n)
        if bosh:
            _bron_saqlash()
        asyncio.get_event_loop().run_in_executor(None, _bekor_adminga, uid, b, bosh)
        return web.json_response({'ok': True, 'holat': 'bekor'})
    except Exception as e:
        logger.error(f'buyurtma_bekor_endpoint: {e}')
        return web.json_response({'error': 'xato'}, status=500)


async def kirish_holat_endpoint(request):
    """BUGUN224: sayt (bot ichida ochilganda) — shu Telegram akkaunt aktiv konkursda raqam yuborib qatnashganmi.
    Ha bo'lsa sayt profilni «kirgan» qiladi (qayta «Kirish» so'ralmaydi). Javobda raqam YO'Q — faqat {kirgan: bool}.
    Himoya: initData imzosi (imzosiz — 401); qatnashchilar ro'yxati — 5 daqiqalik keshdan (_kk_qatnashchimi)."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid:
            return web.json_response({'error': 'Imzo notogri'}, status=401)
        k = await blok(get_konkurs)
        kid = str((k or {}).get('id') or '')
        if not kid:
            return web.json_response({'kirgan': False})
        r = await blok(_kk_qatnashchimi, kid, str(uid))
        return web.json_response({'kirgan': bool(r)})
    except Exception as e:
        logger.error(f'kirish_holat_endpoint: {e}')
        return web.json_response({'kirgan': False})


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
        # BUGUN224: savatdan — nums (hamma raqam, birinchisi = num). Ko'pi bilan 10 ta, faqat raqam, takrorsiz
        nums_xom = data.get('nums') or []
        if not isinstance(nums_xom, list) or len(nums_xom) > 10:
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        qolgan_nums = []
        for n in nums_xom:
            n = str(n or '').strip()
            if not re.fullmatch(r'\d{1,6}', n):
                return web.json_response({'error': 'Nomer notogri'}, status=400)
            if n != num and n not in qolgan_nums:
                qolgan_nums.append(n)
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
        await blok(send_msg, chat_id, f"✅ №{num} kanalga chiqdi (id {mid}) — {POST_CHANNEL}" if mid else f"❌ №{num}: <code>{html_escape(xato)}</code>",
                   kollaj_tugma(mid) if mid else None)
    elif cmd == '/yana':
        mid, xato = await blok(kanal_yana_keldi, num)
        await blok(send_msg, chat_id, f"🔄 №{num} qayta postlandi (yangi id {mid})" if mid else f"❌ №{num}: <code>{html_escape(xato)}</code>",
                   kollaj_tugma(mid) if mid else None)
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
        # BUGUN224: savatdan — nums (hamma raqam, birinchisi = num). Ko'pi bilan 10 ta, faqat raqam, takrorsiz
        nums_xom = data.get('nums') or []
        if not isinstance(nums_xom, list) or len(nums_xom) > 10:
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        qolgan_nums = []
        for n in nums_xom:
            n = str(n or '').strip()
            if not re.fullmatch(r'\d{1,6}', n):
                return web.json_response({'error': 'Nomer notogri'}, status=400)
            if n != num and n not in qolgan_nums:
                qolgan_nums.append(n)
        amal = str(data.get('amal', 'post'))
        yon = str(data.get('yonalish', '') or '')[:20]   # ALOQA: sayt yuborgan bo'lim (bo'lmasa — e'lonning yo'nalishi)
        if amal == 'yana':
            mid, xato = await blok(kanal_yana_keldi, num, yon)
        else:
            mid, xato = await blok(kanal_post, num, yon)
        if not mid:
            return web.json_response({'ok': False, 'error': xato})
        # B28: kollaj tugmasi admin lichkasiga (saytdan yuborilgan post uchun ham)
        await blok(send_msg, admin_joy('post'), f"📣 №{num} kanalga chiqdi (saytdan, id {mid}) — {POST_CHANNEL}", kollaj_tugma(mid))
        return web.json_response({'ok': True, 'mid': mid, 'kanal': POST_CHANNEL})
    except Exception as e:
        logger.error(f'kanal_post_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def kanal_toplam_endpoint(request):
    """B29 (BUGUN31): saytda uzoq bosib belgilangan e'lonlar → «📣 Yuborish» → bitta to'plam posti.
    Faqat admin (initData). {initData, nums: [248, 251, …]} → {ok, mid, kanal, nums, otkazildi}."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid or uid != ADMIN_ID:
            return web.json_response({'error': 'Faqat admin'}, status=401)
        nums = data.get('nums')
        if not isinstance(nums, list) or not 1 <= len(nums) <= 50:
            return web.json_response({'error': "1–50 ta e'lon tanlang"}, status=400)
        nums = [str(n).strip() for n in nums]
        if not all(re.fullmatch(r'\d{1,6}', n) for n in nums):
            return web.json_response({'error': 'Nomer notogri'}, status=400)
        mid, xato, yuborildi, otkazildi = await blok(kanal_toplam, nums)
        if not mid:
            return web.json_response({'ok': False, 'error': xato, 'otkazildi': otkazildi})
        izoh = f"📣 Saytdan to'plam: {len(yuborildi)} ta e'lon (№{', №'.join(str(n) for n in yuborildi)}) kanalga chiqdi (id {mid}) — {POST_CHANNEL}"
        if otkazildi:
            izoh += "\n⏭ O'tkazildi: " + ', '.join(f"№{o['num']} ({html_escape(o['sabab'])})" for o in otkazildi)
        await blok(send_msg, admin_joy('post'), izoh, kollaj_tugma(mid))
        return web.json_response({'ok': True, 'mid': mid, 'kanal': POST_CHANNEL, 'nums': yuborildi, 'otkazildi': otkazildi})
    except Exception as e:
        logger.error(f'kanal_toplam_endpoint: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def kanal_guruh_endpoint(request):
    """BUGUN251: saytdagi rang guruhi bloki — «📣 Kanalga» / «🔄 Qayta yuborish» / «🎨 Ranglarni alohida yuborish» va
    guruh o'zgargandan keyingi tahrir. Faqat admin (initData).
    {initData, id: 'g12', amal: 'yubor' | 'alohida' | 'tahrir', alohida: bool} →
    yubor: {ok, mid, havola, test} · alohida / tahrir: {ok, fonda: true} (natija adminga Telegram'da)."""
    try:
        data = await request.json()
        uid = check_init_data(data.get('initData', ''))
        if not uid or uid != ADMIN_ID:
            return web.json_response({'error': 'Faqat admin'}, status=401)
        gid = str(data.get('id', '') or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,20}', gid):
            return web.json_response({'error': 'Guruh id notogri'}, status=400)
        amal = str(data.get('amal', 'yubor'))
        if amal == 'yubor':
            mid, xato, havola = await blok(guruh_yubor, gid, bool(data.get('alohida')))
            if not mid:
                return web.json_response({'ok': False, 'error': xato})
            return web.json_response({'ok': True, 'mid': mid, 'havola': havola, 'test': guruh_test_rejim(),
                                      'alohida': bool(data.get('alohida'))})
        if amal == 'alohida':
            with _elon_cache_lock:
                g = (_ELON_CACHE.get('guruhlar') or {}).get(gid)
            if g is not None and not guruh_kanal_oqi(g).get('m'):
                return web.json_response({'ok': False, 'error': "Guruh posti kanalda yo'q — avval «Kanalga»"})
            _fonda(guruh_ranglar_fon, gid)
            return web.json_response({'ok': True, 'fonda': True})
        if amal == 'tahrir':
            _fonda(guruh_tahrir_fon, gid)
            return web.json_response({'ok': True, 'fonda': True})
        return web.json_response({'error': "Noma'lum amal"}, status=400)
    except Exception as e:
        logger.error(f'kanal_guruh_endpoint: {e}')
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

_ESKI_UPD = {}   # eski bot update_id → vaqt (Telegram qayta yuborsa — bir marta javob)


def _eski_bot_javob(upd):
    """BUGUN145: eski botga yozgan / tugma bosgan odamga ESKI bot tokeni bilan yangi bot havolasi.
    Nega: eski bot webhook'i ham /webhook ga kelardi — javob yangi token bilan ketib, yangi botga kirmaganlarga
    yetmasdi (403), mijoz javobsiz qolardi (foydalanuvchi, 2026-10-12)."""
    cq = upd.get('callback_query') or {}
    msg = upd.get('message') or cq.get('message') or {}
    chat = msg.get('chat') or {}
    if chat.get('type') != 'private':
        return
    if cq.get('id'):
        _kk_tg('answerCallbackQuery', {'callback_query_id': cq['id']}, token=ESKI_BOT_TOKEN, urinish=1)
    havola = f'https://t.me/{BOT_USERNAME}'
    m = re.match(r'^/start\s+([A-Za-z0-9_-]{1,64})$', (upd.get('message') or {}).get('text') or '')
    if m:   # e'lon / konkurs havolasi — yangi botda o'sha joyga ochilsin
        havola += f'?start={m.group(1)}'
    matn = ('Assalomu alaykum! 👋\n\n'
            f'Botimiz yangi manzilga ko\'chdi — <b>Nuqta tech</b>: @{BOT_USERNAME}\n\n'
            'Pastdagi tugmani bosing va «Start» ni bosing — e\'lonlar, narxlar va savollar endi o\'sha yerda.')
    mk = {'inline_keyboard': [[{'text': '👉 Yangi botga o\'tish', 'url': havola}]]}
    _kk_tg('sendMessage', {'chat_id': chat.get('id'), 'text': matn, 'parse_mode': 'HTML', 'reply_markup': mk},
           token=ESKI_BOT_TOKEN)


async def eski_webhook(request):
    """BUGUN145: eski bot webhook'i — darhol 200 (T1), javob fonda."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'ok': True})
    if isinstance(data, dict) and ESKI_BOT_TOKEN:
        uid = data.get('update_id')
        hozir = time.time()
        if uid not in _ESKI_UPD:
            _ESKI_UPD[uid] = hozir
            for k in [k for k, v in _ESKI_UPD.items() if hozir - v > 3600]:
                _ESKI_UPD.pop(k, None)
            asyncio.create_task(blok(_eski_bot_javob, data))
            # BUGUN173: eski botga yozgan — Mijozlar.eski_bot (fonda; javob bilan birga emas)
            kim = data.get('message') or data.get('callback_query') or {}
            chat = kim.get('chat') or (kim.get('message') or {}).get('chat') or {}
            if chat.get('type') == 'private':
                asyncio.create_task(mijoz_bot_qayd(kim.get('from'), 'eski'))
    return web.json_response({'ok': True})


async def main():
    _bron_yuklash()   # BUGUN208
    _mijoz_yuklash()  # BUGUN225
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post('/webhook', webhook)
    app.router.add_post('/webhook-eski', eski_webhook)   # BUGUN145: eski bot → yangi bot havolasi
    app.router.add_post('/notify', notify_endpoint)
    app.router.add_post('/konkurs_started', konkurs_started_endpoint)
    app.router.add_post('/reroll_notify', reroll_notify_endpoint)
    app.router.add_post('/publish', publish_endpoint)
    app.router.add_post('/label', label_endpoint)
    app.router.add_post('/share', share_endpoint)   # G9.1: ulashish uchun tayyor rasmli xabar
    app.router.add_post('/bron_tekshir', bron_tekshir_endpoint)   # BUGUN208: «Sotib olish» — e'lon bronmi (faqat true/false)
    app.router.add_post('/buyurtma', buyurtma_endpoint)
    app.router.add_post('/mijoz_holat', mijoz_holat_endpoint)   # BUGUN225: profil — raqamlar (BUGUN271: to'liq, faqat egasiga) + Buyurtmalarim
    app.router.add_post('/mijoz_tel', mijoz_tel_endpoint)       # BUGUN271: profil — yetkazish raqamini o'zgartirish
    app.router.add_post('/buyurtma_bekor', buyurtma_bekor_endpoint)   # BUGUN225: mijoz buyurtmani bekor qildi
    app.router.add_post('/kirish_holat', kirish_holat_endpoint)   # BUGUN224: konkurs qatnashchisi — saytda avto-kirish   # BUGUN171: «Sotib olish» — adminga darhol xabar
    app.router.add_post('/konkurs/captcha', konkurs_captcha_endpoint)   # BUGUN125: Mini App tekshiruvi
    app.router.add_post('/konkurs/qatnash', konkurs_qatnash_endpoint)
    app.router.add_post('/konkurs/boshla', konkurs_boshla_endpoint)     # BUGUN233: eski Telegram — ?start= siz
    app.router.add_post('/elon_changed', elon_changed_endpoint)   # G10.3: admin saqlaganda xotira yangilanadi + G11.2 kanal sinxron
    app.router.add_post('/kanal_post', kanal_post_endpoint)       # G11.2: saytdan «Kanalga» / «Yana keldi»
    app.router.add_post('/kanal_toplam', kanal_toplam_endpoint)   # B29: saytda belgilanganlar → bitta to'plam posti
    app.router.add_post('/kanal_guruh', kanal_guruh_endpoint)     # BUGUN251: rang guruhi posti
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
        if ESKI_BOT_TOKEN and ESKI_BOT_TOKEN != BOT_TOKEN:
            # BUGUN145: eski bot o'z yo'liga — javobni eski token bilan beradi (yangi bot havolasi)
            try:
                r2 = req.post(f'https://api.telegram.org/bot{ESKI_BOT_TOKEN}/setWebhook', timeout=20,
                              json={'url': f'{render_url}/webhook-eski', 'allowed_updates': ['message', 'callback_query']})
                logger.info(f'Eski bot webhook: {r2.json()}')
            except Exception as e:
                logger.error(f'eski bot webhook: {type(e).__name__}')
    # Servis uxlab qolmasin — har 10 daqiqada o'ziga so'rov
    asyncio.create_task(keep_alive())
    asyncio.create_task(mijoz_sync_loop())   # BUGUN227: Sheets dan yuklash + yozish navbati
    asyncio.create_task(buyurtma_xabar_loop())   # BUGUN295: adminga yetmagan buyurtma xabarlari (sayt zaxirasi ham)
    asyncio.create_task(chek_eslatma_loop())   # BUGUN305: 1 soat chek kelmasa — adminga bitta eslatma
    asyncio.create_task(mijoz_kop_loop())   # 3176: /start + kanal voqealari — to'plab, fonda (BUGUN232 navbati o'rniga)
    asyncio.create_task(savat_eslatma_loop())   # 3184: savatda qolgan tovar — eslatma (SAVAT_ESLATMA, sukut quruq)
    asyncio.create_task(mijoz_birlashtir_loop())   # 3184: takror Mijozlar qatorlari — kunda bir marta, 04:00
    # Bot ishga tushganda: aktiv konkursga taymer + yetkazilmay qolgan xabarlar davomi (holat jadvaldan — BUGUN108)
    asyncio.create_task(konkurs_tiklash())
    asyncio.create_task(guruh_tiklash())   # 3110: /guruh mavzulari jadvaldan (qayta ishga tushsa ham qoladi)
    # Bot ishga tushganda: e'lon xotirasi (G10.3) + oxirgi elon raqami — BITTA yuklashdan
    try:
        if await blok(elon_cache_load) and _ELON_CACHE['by_num']:   # BUGUN232: alohida ipda — Sheets kechiksa webhook to'xtamaydi
            _last_sent['num'] = max(int(k) for k in _ELON_CACHE['by_num'].keys())
            logger.info(f"Last elon num: {_last_sent['num']}")
    except Exception as e:
        logger.error(f'init elon_cache: {e}')
    asyncio.create_task(elon_cache_loop())   # kuniga bir marta ehtiyot yuklash
    asyncio.create_task(ai_hisobot_loop())   # BUGUN244: «🤖 AI yordamchi» mavzusiga har 5 soatda hisobot
    if KANAL_TOMCHI_BOSHI:
        asyncio.create_task(tomchi_loop())   # 3184.5: 15 kunlik tomchi (env yo'q — o'chiq)
    logger.info(f'Started on port {PORT} · bot @{BOT_USERNAME}')
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
