# -*- coding: utf-8 -*-
"""tests/b3302_chek_holat.py — 3302: holat tugmasi bosilganda chek nusxasi (rasm, matni caption'da) ham yangilanadi;
bir buyurtmaning ikkala admin xabari (buyurtma + chek) bo'lsa — qaysi birida bosilsa ham ikkalasi.

Ishga tushirish:  python tests/b3302_chek_holat.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777002, №TC…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import html
import logging
import os
import re
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
_VAQT = tempfile.mkdtemp(prefix='b3302-')
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
MIJOZ, ADMIN = 777002, bot.ADMIN_ID
MID = [100]


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
    """Telegram o'rnida: yangi xabarga id beradi, tahrirda yuborilgan matnni qaytaradi (Telegram kabi)."""
    usul = url.rsplit('/', 1)[-1]
    d = kw.get('json') or kw.get('data') or {}
    SOROV.append((usul, d))
    if usul in ('sendMessage', 'copyMessage'):
        MID[0] += 1
        r = {'message_id': MID[0]}
        if usul == 'sendMessage':
            r.update(text=html.unescape(re.sub(r'<[^>]+>', '', d.get('text', ''))), entities=[])
        return Javob(200, {'ok': True, 'result': r})
    if usul == 'editMessageText':
        return Javob(200, {'ok': True, 'result': {'message_id': d['message_id'], 'text': d['text'], 'entities': d['entities']}})
    if usul == 'editMessageCaption':
        return Javob(200, {'ok': True, 'result': {'message_id': d['message_id'], 'caption': d['caption'],
                                                  'caption_entities': d['caption_entities']}})
    return Javob(200, {'ok': True, 'result': True})


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: True
bot._kk_sheet = lambda action, timeout=30, **p: {'ok': True}
bot.time.sleep = lambda s: None


def _fonsiz(self, ex, f, *a):
    fut = self.create_future()
    try:
        fut.set_result(f(*a))
    except Exception as e:
        fut.set_exception(e)
    return fut


asyncio.SelectorEventLoop.run_in_executor = _fonsiz
if hasattr(asyncio, 'ProactorEventLoop'):
    asyncio.ProactorEventLoop.run_in_executor = _fonsiz

BUYURTMA_HTML = ("🛒 <b>Yangi buyurtma</b> №{o}\n\n📱 <b>Tovar 21</b> · e'lon №21\n💵 500$ ≈ 6 000 000 so'm (kurs 12000)\n\n"
                 "👤 S\n📞 +998900000001\n📍 Emu\n\n⏳ <b>To'lov kutilmoqda</b> — chek hali kelmagan. Mijoz chekni o'zi yuboradi; "
                 "kelmasa — telefon qiling.\n🕒 31.10.2026 07:50")


def yangi(order):
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, {
            'order': order, 'ts': 1, 'holat': 'kutilmoqda', 'tovar': [{'num': '21', 'nom': 'T', 'narx': 500, 'soni': 1}],
            'jami': 500, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000001', 'til': 'uz', 'joy': {}})


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


def bos(data, xabar):
    """Admin tugma bosdi — callback'dagi xabar (Telegram yuborgan ko'rinishi)."""
    SOROV.clear()
    asyncio.run(bot.buyurtma_holat_tugma(ADMIN, xabar['message_id'], data, xabar))


def chek_xabari(mid, order, qator="⏳ To'lov kutilmoqda"):
    t, e = bot._html_b_ents(bot._chek_admin_matn({'order': order, 'ism': 'S', 'jami': 500}))
    t = t.replace("⏳ To'lov kutilmoqda", qator)
    return {'message_id': mid, 'chat': {'id': ADMIN}, 'photo': [{'file_id': 'x'}], 'caption': t, 'caption_entities': e}


def buyurtma_xabari(mid, order):
    t = html.unescape(re.sub(r'<[^>]+>', '', BUYURTMA_HTML.format(o=order)))
    return {'message_id': mid, 'chat': {'id': ADMIN}, 'text': t, 'entities': []}


VAQT = r"· \d\d:\d\d"

print('— chek matni → oddiy matn + bold')
t, e = bot._html_b_ents("🧾 <b>Chek keldi</b> — №AB12\n👤 A &amp; B\n\n⏳ To'lov kutilmoqda")
sinov('teglar olinadi, &amp; → &', t == "🧾 Chek keldi — №AB12\n👤 A & B\n\n⏳ To'lov kutilmoqda", repr(t))
sinov("bold — «Chek keldi» (UTF-16 offset)", e == [{'type': 'bold', 'offset': 3, 'length': 10}], repr(e))

print('— faqat chek xabari (caption): «✅ To\'landi» bosildi')
yangi('TC01')
bos(f'bh:tolandi:{MIJOZ}:TC01', chek_xabari(201, 'TC01'))
c = sorov('editMessageCaption')
sinov('editMessageCaption ketdi (editMessageText emas)', len(c) == 1 and not sorov('editMessageText'), repr(SOROV)[:300])
sinov("caption: «✅ To'landi · HH:MM», «kutilmoqda» yo'q",
      c and re.search("\n\n✅ To'landi " + VAQT, c[0]['caption']) and 'kutilmoqda' not in c[0]['caption'], repr(c)[:300])
sinov('caption boshi saqlangan (Chek keldi, №, ism)', c and c[0]['caption'].startswith('🧾 Chek keldi — №TC01'), repr(c)[:200])
sinov('🕒 vaqt qatori saqlangan', c and '\n🕒 Buyurtma: ' in c[0]['caption'], repr(c)[:300])
sinov('tugmalar ham shu so\'rovda (keyingi bosqich — Yo\'lda)', c and f'bh:yolda:{MIJOZ}:TC01' in str(c[0].get('reply_markup')))
sinov('yozuvda chek xabari eslab qolindi', [x['m'] for x in yozuv('TC01').get('admin_xb') or []] == [201])

print('— faqat buyurtma xabari (matn): «✅ To\'landi» bosildi')
yangi('TC02')
bos(f'bh:tolandi:{MIJOZ}:TC02', buyurtma_xabari(301, 'TC02'))
m = sorov('editMessageText')
sinov('editMessageText ketdi', len(m) == 1 and not sorov('editMessageCaption'), repr(SOROV)[:300])
sinov("matn: «✅ To'landi · HH:MM»", m and re.search("\n\n✅ To'landi " + VAQT, m[0]['text'])
      and 'kutilmoqda' not in m[0]['text'], repr(m)[:300])

print('— ikkalasi birga: buyurtma xabarida bosildi → chek ham yangilanadi')
yangi('TC03')
SOROV.clear()
bot._buyurtma_xabar_yubor(MIJOZ, 'TC03', {'matn': BUYURTMA_HTML.format(o='TC03'), 'holat': 'kutilmoqda', 'bron': ['21']}, kutish=(0,))
b_mid = MID[0]
bot._chek_adminga(MIJOZ, dict(yozuv('TC03')), 55)
c_mid = MID[0]
sinov('yozuvda ikkala xabar (buyurtma + chek)', [x['m'] for x in yozuv('TC03')['admin_xb']] == [b_mid, c_mid],
      repr(yozuv('TC03').get('admin_xb'))[:300])
sinov('chek: caption=1, matnda «⏳ To\'lov kutilmoqda»', yozuv('TC03')['admin_xb'][1]['c'] == 1
      and "⏳ To'lov kutilmoqda" in yozuv('TC03')['admin_xb'][1]['t'])
bos(f'bh:tolandi:{MIJOZ}:TC03', buyurtma_xabari(b_mid, 'TC03'))
m, c = sorov('editMessageText'), sorov('editMessageCaption')
sinov('buyurtma xabari — editMessageText', [x['message_id'] for x in m] == [b_mid], repr(m)[:200])
sinov('chek xabari — editMessageCaption (bosilmagan bo\'lsa ham)', [x['message_id'] for x in c] == [c_mid], repr(SOROV)[:300])
sinov("chek caption: «✅ To'landi», «kutilmoqda» yo'q", c and "\n\n✅ To'landi · " in c[0]['caption']
      and 'kutilmoqda' not in c[0]['caption'], repr(c)[:300])
sinov('chek tugmalari ham yangilandi (Yo\'lda)', c and f'bh:yolda:{MIJOZ}:TC03' in str(c[0].get('reply_markup')))
sinov('chek: bold «Chek keldi» saqlangan', c and {'type': 'bold', 'offset': 3, 'length': 10} in c[0]['caption_entities'])

print('— ikkalasi birga: keyingi bosqich chek xabarida bosildi → buyurtma xabari ham')
bos(f'bh:yolda:{MIJOZ}:TC03', chek_xabari(c_mid, 'TC03', yozuv('TC03')['admin_xb'][-1]['t'].split('\n\n')[-1].split('\n')[0]))
m, c = sorov('editMessageText'), sorov('editMessageCaption')
sinov('chek — caption, buyurtma — matn', [x['message_id'] for x in c] == [c_mid] and [x['message_id'] for x in m] == [b_mid],
      repr(SOROV)[:300])
zanjir = "✅ To'landi " + VAQT + " → 🚚 Yo'lda " + VAQT
sinov("ikkalasida zanjir «✅ To'landi · … → 🚚 Yo'lda · …»", c and m and re.search(zanjir, c[0]['caption'])
      and re.search(zanjir, m[0]['text']), repr(SOROV)[:400])
sinov('yozuvdagi matnlar ham yangi', all("🚚 Yo'lda" in x['t'] for x in yozuv('TC03')['admin_xb']))

print('— eski xabar (yozuvda yo\'q, holat boshqa joyda surilgan) — bosilganda o\'zi yangilanadi')
yangi('TC04')
bos(f'bh:tolandi:{MIJOZ}:TC04', buyurtma_xabari(401, 'TC04'))
yozuv('TC04').pop('admin_xb', None)   # bot qayta yongan — yozuv Sheets'dan, admin_xb yo'q
bos(f'bh:tolandi:{MIJOZ}:TC04', chek_xabari(402, 'TC04'))
c = sorov('editMessageCaption')
sinov("«eski» bosish: chek caption «✅ To'landi» ga o'tdi (ilgari faqat tugmalar)",
      len(c) == 1 and "\n\n✅ To'landi · " in c[0]['caption'] and 'kutilmoqda' not in c[0]['caption'], repr(SOROV)[:300])
sinov('buyurtma xabariga tegilmadi (yozuvda yo\'q edi)', not sorov('editMessageText'))

print('— takror bosish: matn allaqachon joriy — tahrir yo\'q, faqat tugmalar')
bos(f'bh:tolandi:{MIJOZ}:TC04', chek_xabari(402, 'TC04', "✅ To'landi · 08:00"))
sinov('editMessageCaption / Text yo\'q', not sorov('editMessageCaption') and not sorov('editMessageText'), repr(SOROV)[:300])
sinov('editMessageReplyMarkup ketdi', len(sorov('editMessageReplyMarkup')) == 1)
sinov("_buyurtma_holat_matn: zanjir oxiri shu holat → None",
      bot._buyurtma_holat_matn("A\n\n✅ To'landi · 07:00 → 🚚 Yo'lda · 08:00", [], 'yolda', 0) is None
      and bot._buyurtma_holat_matn("A\n\n✅ To'landi · 07:00 — 🎁 sovg'a, to'lov yo'q", [], 'tolandi', 0) is None)

print('— bekor qilingan buyurtma — matnga tegilmaydi')
yangi('TC05')
bos(f'bh:tolandi:{MIJOZ}:TC05', buyurtma_xabari(501, 'TC05'))
yozuv('TC05')['holat'] = 'bekor'
bos(f'bh:yolda:{MIJOZ}:TC05', chek_xabari(502, 'TC05'))
sinov('bekor: caption / matn tahriri yo\'q', not sorov('editMessageCaption') and not sorov('editMessageText'), repr(SOROV)[:300])

print('— davomi (albomning keyingi rasmi) yozuvga tushmaydi')
yangi('TC06')
bot._chek_adminga(MIJOZ, dict(yozuv('TC06')), 60, davomi=True)
sinov('davomi — admin_xb yo\'q', not yozuv('TC06').get('admin_xb'))

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
