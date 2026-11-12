# -*- coding: utf-8 -*-
"""tests/b3304_bron_tugma.py — 3304: «🔓 Bronni bekor qilish» faqat «⏳ To'lov kutilmoqda» bosqichida; to'langan buyurtmaning broni eski tugmadan ham bekor qilinmaydi.

Ishga tushirish:  python tests/b3304_bron_tugma.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777004, №TR…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import json
import logging
import os
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL'):
    os.environ.pop(k, None)
_VAQT = tempfile.mkdtemp(prefix='b3304-')
atexit.register(shutil.rmtree, _VAQT, True)
os.environ['BRON_FAYL'] = os.path.join(_VAQT, 'bron.json')
os.environ['MIJOZ_FAYL'] = os.path.join(_VAQT, 'mijoz.json')

import requests


def _tarmoq_yoq(*a, **kw):
    raise AssertionError(f'tarmoq so\'rovi: {a[:1]}')


requests.post = requests.get = _tarmoq_yoq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

logging.disable(logging.CRITICAL)
NATIJA = [0, 0]
SOROV = []
SOTUV = []
MIJOZ_BLOK = set()
MIJOZ, ADMIN = 777004, bot.ADMIN_ID
JPEG = bytes((0xFF, 0xD8, 0xFF, 0xE0)) + b'0' * 200


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')



class Javob:
    def __init__(self, kod=200, j=None):
        self.status_code, self._j = kod, j or {}

    def json(self):
        return self._j


def _post(url, **kw):
    usul = url.rsplit('/', 1)[-1]
    d = kw.get('json') or kw.get('data') or {}
    SOROV.append((usul, d))
    if usul in ('editMessageText', 'editMessageCaption'):
        r = {'message_id': d.get('message_id')}
        r.update({'caption': d['caption'], 'caption_entities': d.get('caption_entities')} if 'caption' in d
                 else {'text': d.get('text'), 'entities': d.get('entities')})
        return Javob(200, {'ok': True, 'result': r})
    return Javob(200, {'ok': True, 'result': {'message_id': 900}})


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: SOTUV.append((uid, b.get('order'))) or True
bot._kk_sheet = lambda action, timeout=30, **p: {'ok': True}
bot.time.sleep = lambda s: None
bot._update_yangimi = lambda u: True

BUYURTMA_MATN = "🛒 Yangi buyurtma №{o}\n\n1. Tovar · №{n}\n💵 Jami 500$\n\n👤 S\n\n⏳ To'lov kutilmoqda\n🕒 Buyurtma: 03.11.2026 10:00"
CHEK_MATN = "🧾 Chek keldi — №{o}\n💵 500$\n\n⏳ To'lov kutilmoqda\n🕒 03.11.2026 10:05"


def yangi(order, num, holat='kutilmoqda'):
    """Soxta buyurtma: bron + ikki admin xabari (buyurtma id 50, chek nusxasi id 51)."""
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, {
            'order': order, 'ts': 1, 'holat': holat, 'tovar': [{'num': num, 'nom': 'T', 'narx': 500, 'soni': 1}],
            'jami': 500, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000004', 'til': 'uz', 'joy': {},
            'admin_xb': [{'m': 50, 'c': 0, 't': BUYURTMA_MATN.format(o=order, n=num), 'e': []},
                         {'m': 51, 'c': 1, 't': CHEK_MATN.format(o=order), 'e': []}]})
    bot._bron_qoy(num, MIJOZ, order)


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def tahrirlar():
    """(message_id, reply_markup) — admin xabarlari tahriri (matn / caption / faqat tugma)."""
    return [(d.get('message_id'), d.get('reply_markup')) for u, d in SOROV
            if u in ('editMessageText', 'editMessageCaption', 'editMessageReplyMarkup')]


def bron_tugmasi_bor(kl):
    return 'bron_och' in json.dumps(kl or {})


def admin_matn():
    return ' | '.join(str(d.get('text')) for u, d in SOROV if u == 'sendMessage' and str(d.get('chat_id')) == str(ADMIN)).lower()


def holat_bos(data, order, num):
    SOROV.clear()
    xabar = {'message_id': 50, 'chat': {'id': ADMIN}, 'text': BUYURTMA_MATN.format(o=order, n=num), 'entities': []}
    asyncio.run(bot.buyurtma_holat_tugma(ADMIN, 50, data, xabar))


def bron_bos(num, order):
    SOROV.clear()
    asyncio.run(bot.bron_bekor_tugma(ADMIN, f'bron_och:{num}:{order}'))


print('— _buyurtma_klava: bron tugmasi faqat «kutilmoqda» da')
for h in bot._HOLAT_TARTIB + ('bekor',):
    kl = bot._buyurtma_klava(MIJOZ, 'TR00', h, ['31', '32'])
    if h == 'kutilmoqda':
        sinov('kutilmoqda: ikkala bron tugmasi bor (№31, №32)',
              'bron_och:31:TR00' in json.dumps(kl) and 'bron_och:32:TR00' in json.dumps(kl), repr(kl))
    else:
        sinov(f'{h}: bron tugmasi yo\'q', not bron_tugmasi_bor(kl), repr(kl))
sinov('kutilmoqda, bitta e\'lon — «🔓 Bronni bekor qilish» (raqamsiz)',
      any(t['text'] == '🔓 Bronni bekor qilish' for q in bot._buyurtma_klava(MIJOZ, 'TR00', 'kutilmoqda', ['31'])['inline_keyboard'] for t in q))

print("— «✅ To'lov keldi» bosildi: buyurtma va chek xabarida bron tugmasi yo'qoladi")
yangi('TR01', '41')
holat_bos(f'bh:tolandi:{MIJOZ}:TR01', 'TR01', '41')
t = tahrirlar()
sinov("holat — to'landi", yozuv('TR01')['holat'] == 'tolandi')
sinov('buyurtma (50) va chek (51) xabarlari tahrirlandi', {m for m, _ in t} == {50, 51}, repr(t)[:300])
sinov("ikkala xabarda bron tugmasi yo'q", t and not any(bron_tugmasi_bor(k) for _, k in t), repr(t)[:400])
sinov("ikkala xabarda keyingi bosqich «🚚 Yo'lda» bor", all(f'bh:yolda:{MIJOZ}:TR01' in json.dumps(k) for _, k in t), repr(t)[:400])
sinov('bron o\'z joyida (to\'langan — e\'lon band)', (bot._BRON.get('41') or {}).get('order') == 'TR01')

print("— eski xabardagi eski tugma (to'langan buyurtma)")
bron_bos('41', 'TR01')
sinov('bron o\'chirilmadi', (bot._BRON.get('41') or {}).get('order') == 'TR01', repr(bot._BRON))
sinov("javob: «ℹ️ … to'langan buyurtma — bron bekor qilinmadi»",
      'ℹ️' in admin_matn() and "to'langan buyurtma" in admin_matn() and 'bron bekor qilinmadi' in admin_matn(), admin_matn())
sinov('«bron bekor qilindi» deyilmadi', 'hammaga ochiq' not in admin_matn(), admin_matn())

print("— «⏭ To'lovni kutmay — Yo'lda» (isbotsiz, bhy:skip → bh:yolda)")
yangi('TR02', '42')
holat_bos(f'bh:yolda:{MIJOZ}:TR02', 'TR02', '42')
t = tahrirlar()
sinov("holat — yo'lda", yozuv('TR02')['holat'] == 'yolda')
sinov("buyurtma va chek xabarida bron tugmasi yo'q", {m for m, _ in t} == {50, 51} and not any(bron_tugmasi_bor(k) for _, k in t),
      repr(t)[:400])
bron_bos('42', 'TR02')
sinov("eski tugma: bron turibdi, javob «to'langan buyurtma»", '42' in bot._BRON and "to'langan buyurtma" in admin_matn(), admin_matn())

print('— yetkazildi / yopildi buyurtma — eski tugma ham bronni bekor qilmaydi')
for o, n, h in (('TR03', '43', 'yetkazildi'), ('TR04', '44', 'yopildi')):
    yangi(o, n, h)
    bron_bos(n, o)
    sinov(f'{h}: bron turibdi', n in bot._BRON and 'bron bekor qilinmadi' in admin_matn(), admin_matn())

print("— «⏳ To'lov kutilmoqda» da tugma avvalgidek ishlaydi")
yangi('TR05', '45')
bron_bos('45', 'TR05')
sinov("bron bekor qilindi, javob «hammaga ochiq»", '45' not in bot._BRON and 'bron bekor qilindi' in admin_matn(), admin_matn())
bron_bos('45', 'TR05')
sinov("qayta bosish — «bron allaqachon yo'q»", "allaqachon yo'q" in admin_matn(), admin_matn())

print('— bron boshqa buyurtmada (kutilmoqda) — tegilmaydi')
yangi('TR06', '46')
bron_bos('46', 'TR99')
sinov('bron TR06 da qoldi', (bot._BRON.get('46') or {}).get('order') == 'TR06' and 'boshqa buyurtmada' in admin_matn(), admin_matn())

print('— callback: faqat admin')
yangi('TR07', '47')
SOROV.clear()


async def _ish(upd):
    await bot.handle_update(upd)
    for x in [x for x in asyncio.all_tasks() if x is not asyncio.current_task()]:
        await x
asyncio.run(_ish({'update_id': 7, 'callback_query': {'id': 'q', 'from': {'id': 555}, 'data': 'bron_och:47:TR07',
                                                     'message': {'message_id': 50, 'chat': {'id': 555}}}}))
sinov('admin emas — bron turibdi', '47' in bot._BRON)
asyncio.run(_ish({'update_id': 8, 'callback_query': {'id': 'q', 'from': {'id': ADMIN}, 'data': 'bron_och:47:TR07',
                                                     'message': {'message_id': 50, 'chat': {'id': ADMIN}}}}))
sinov('admin, kutilmoqda — bron bekor qilindi (handle_update orqali)', '47' not in bot._BRON)
with bot._MIJOZ_LOCK:
    yozuv('TR01')['holat'] = 'tolandi'
asyncio.run(_ish({'update_id': 9, 'callback_query': {'id': 'q', 'from': {'id': ADMIN}, 'data': 'bron_och:41:TR01',
                                                     'message': {'message_id': 50, 'chat': {'id': ADMIN}}}}))
sinov("admin, to'langan — bron turibdi (handle_update orqali)", '41' in bot._BRON)

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
