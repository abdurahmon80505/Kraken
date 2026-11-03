# -*- coding: utf-8 -*-
"""tests/b3304_bron_tolov.py — 3304: «🔓 Bronni bekor qilish» faqat «⏳ To'lov kutilmoqda» da chiqadi.
«✅ To'lov keldi» yoki «⏭ To'lovni kutmay — Yo'lda» dan keyin — buyurtma xabarida ham, chek xabarida ham yo'q.
Eski xabardagi eski tugma bosilsa va buyurtma to'langan bo'lsa — bron o'chirilmaydi.

Ishga tushirish:  python tests/b3304_bron_tolov.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — vaqtinchalik papkada.
Buyurtmalar — soxta (uid 777004, №TR…); real mijozga tegilmaydi.
"""
import asyncio
import atexit
import html
import json
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
MIJOZ, ADMIN = 777004, bot.ADMIN_ID
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


def yangi(order, holat='kutilmoqda', nums=('21',)):
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, {
            'order': order, 'ts': 1, 'holat': holat, 'tovar': [{'num': n, 'nom': 'T', 'narx': 500, 'soni': 1} for n in nums],
            'jami': 500, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000001', 'til': 'uz', 'joy': {}})
    for n in nums:
        bot._bron_qoy(n, MIJOZ, order)


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


def bron_tugma_bor(klava):
    return 'bron_och:' in json.dumps(klava or {})


def admin_xabar(order):
    """Buyurtma xabari + chek nusxasi adminga (haqiqiy oqim kabi). Qaytaradi (buyurtma xabari, chek xabari) — callback ko'rinishida."""
    SOROV.clear()
    bot._buyurtma_xabar_yubor(MIJOZ, order, {'matn': BUYURTMA_HTML.format(o=order), 'holat': 'kutilmoqda',
                                             'bron': [str(x['num']) for x in yozuv(order)['tovar']]}, kutish=(0,))
    b_mid, b_kl = MID[0], sorov('sendMessage')[-1].get('reply_markup')
    bot._chek_adminga(MIJOZ, dict(yozuv(order)), 55)
    c_mid, c_kl = MID[0], sorov('copyMessage')[-1].get('reply_markup')
    xb = {x['m']: x for x in yozuv(order)['admin_xb']}
    bx = {'message_id': b_mid, 'chat': {'id': ADMIN}, 'text': xb[b_mid]['t'], 'entities': xb[b_mid]['e'], 'reply_markup': b_kl}
    cx = {'message_id': c_mid, 'chat': {'id': ADMIN}, 'photo': [{'file_id': 'x'}], 'caption': xb[c_mid]['t'],
          'caption_entities': xb[c_mid]['e'], 'reply_markup': c_kl}
    return bx, cx


def bos(data, xabar):
    SOROV.clear()
    asyncio.run(bot.buyurtma_holat_tugma(ADMIN, xabar['message_id'], data, xabar))


def bron_bos(data):
    SOROV.clear()
    asyncio.run(bot.bron_bekor_tugma(ADMIN, data))
    return ' '.join(d.get('text', '') for d in sorov('sendMessage'))


print('— _buyurtma_klava: bron tugmasi faqat «kutilmoqda» da')
for h in ('kutilmoqda', 'tolandi', 'yolda', 'yetkazildi', 'yopildi', 'bekor'):
    kl = bot._buyurtma_klava(MIJOZ, 'TR00', h, ['21', '22'])
    kutilgan = h == 'kutilmoqda'
    sinov(f"{h}: bron tugmasi " + ('bor' if kutilgan else "yo'q"), bron_tugma_bor(kl) == kutilgan, repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TR00', 'kutilmoqda', ['21', '22'])
sinov('kutilmoqda: har tovarga alohida (№21, №22)',
      [t['callback_data'] for q in kl['inline_keyboard'] for t in q if t.get('callback_data', '').startswith('bron_och:')]
      == ['bron_och:21:TR00', 'bron_och:22:TR00'], repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TR00', 'kutilmoqda', ['21'])
sinov("kutilmoqda: «✅ To'lov keldi», «⏭ To'lovni kutmay» joyida", f'bh:tolandi:{MIJOZ}:TR00' in json.dumps(kl)
      and f'bh:yolda:{MIJOZ}:TR00' in json.dumps(kl), repr(kl))

print("— «✅ To'lov keldi» bosildi: buyurtma xabarida ham, chek xabarida ham bron tugmasi yo'qoladi")
yangi('TR01')
bx, cx = admin_xabar('TR01')
sinov('boshida buyurtma xabarida bron tugmasi bor', bron_tugma_bor(bx['reply_markup']), repr(bx['reply_markup']))
bos(f'bh:tolandi:{MIJOZ}:TR01', bx)
m, c = sorov('editMessageText'), sorov('editMessageCaption')
sinov('buyurtma xabari tahrirlandi — bron tugmasi yo\'q', len(m) == 1 and not bron_tugma_bor(m[0].get('reply_markup')),
      repr(m)[:300])
sinov('chek xabari tahrirlandi — bron tugmasi yo\'q', len(c) == 1 and not bron_tugma_bor(c[0].get('reply_markup')), repr(c)[:300])
sinov("keyingi bosqich (🚚 Yo'lda) ikkalasida", all(f'bh:yolda:{MIJOZ}:TR01' in json.dumps(x.get('reply_markup')) for x in m + c))
sinov('bron o\'zi saqlanib qoldi (e\'lon sotuvga qaytmadi)', (bot._BRON.get('21') or {}).get('order') == 'TR01', repr(bot._BRON))

print("— «⏭ To'lovni kutmay — Yo'lda» (to'lovsiz jo'natildi): bron tugmasi yo'qoladi")
yangi('TR02', nums=('31',))
bx, cx = admin_xabar('TR02')
bos(f'bh:yolda:{MIJOZ}:TR02', bx)
m, c = sorov('editMessageText'), sorov('editMessageCaption')
sinov("holat «yolda»", yozuv('TR02')['holat'] == 'yolda', yozuv('TR02')['holat'])
sinov('buyurtma va chek xabarida bron tugmasi yo\'q', m and c and not any(bron_tugma_bor(x.get('reply_markup')) for x in m + c),
      repr(SOROV)[:400])

print('— chek xabarida «✅ To\'lov keldi» bosildi: buyurtma xabari ham bron tugmasisiz')
yangi('TR03', nums=('41',))
bx, cx = admin_xabar('TR03')
bos(f'bh:tolandi:{MIJOZ}:TR03', cx)
m, c = sorov('editMessageText'), sorov('editMessageCaption')
sinov('ikkalasi tahrirlandi, bron tugmasi yo\'q', len(m) == 1 and len(c) == 1
      and not any(bron_tugma_bor(x.get('reply_markup')) for x in m + c), repr(SOROV)[:400])

print('— takror bosish (eski) — tugmalar yangilanadi, bron tugmasi baribir yo\'q')
cx2 = dict(cx, caption=yozuv('TR03')['admin_xb'][-1]['t'])
bos(f'bh:tolandi:{MIJOZ}:TR03', cx2)
r = sorov('editMessageReplyMarkup')
sinov('editMessageReplyMarkup — bron tugmasisiz', len(r) == 1 and not bron_tugma_bor(r[0].get('reply_markup')), repr(SOROV)[:300])

print("— 🎁 sovg'a (darhol «to'landi»): admin xabari bron tugmasisiz chiqadi")
yangi('TR04', holat='tolandi', nums=('51',))
SOROV.clear()
bot._buyurtma_xabar_yubor(MIJOZ, 'TR04', {'matn': BUYURTMA_HTML.format(o='TR04'), 'holat': 'tolandi', 'bron': ['51']}, kutish=(0,))
s = sorov('sendMessage')
sinov('sendMessage — bron tugmasi yo\'q', len(s) == 1 and not bron_tugma_bor(s[0].get('reply_markup')), repr(s)[:300])

print('— eski xabardagi eski tugma: to\'langan buyurtma — bron o\'chirilmaydi')
yangi('TR05', nums=('61',))
bos(f'bh:tolandi:{MIJOZ}:TR05', admin_xabar('TR05')[0])
javob = bron_bos('bron_och:61:TR05')
sinov('bron joyida', (bot._BRON.get('61') or {}).get('order') == 'TR05', repr(bot._BRON))
sinov("javob: «ℹ️ To'langan buyurtma — bron bekor qilinmadi»", javob.startswith("ℹ️ To'langan buyurtma — bron bekor qilinmadi"), javob)
sinov('javobda e\'lon va buyurtma raqami', '№61' in javob and '№TR05' in javob, javob)
for h in ('yolda', 'yetkazildi', 'yopildi'):
    yozuv('TR05')['holat'] = h
    javob = bron_bos('bron_och:61:TR05')
    sinov(f'{h}: bron joyida, javob «bekor qilinmadi»', '61' in bot._BRON and 'bekor qilinmadi' in javob, javob)

print("— 2-mijoz ogohidagi tugma (buyurtma raqamisiz: bron_och:<num>:) ham to'langan bronni ochmaydi")
javob = bron_bos('bron_och:61:')
sinov('bron joyida', '61' in bot._BRON and 'bekor qilinmadi' in javob, javob)

print('— to\'lanmagan buyurtma — bron avvalgidek bekor qilinadi')
yangi('TR06', nums=('71',))
javob = bron_bos('bron_och:71:TR06')
sinov('bron o\'chdi', '71' not in bot._BRON, repr(bot._BRON))
sinov("javob: «🔓 №71 — bron bekor qilindi, e'lon hammaga ochiq.»", javob == "🔓 №71 — bron bekor qilindi, e'lon hammaga ochiq.", javob)
sinov('faylga ham yozildi', '71' not in json.load(open(os.environ['BRON_FAYL'], encoding='utf-8')))

print('— buyurtma yozuvi topilmadi (bot qayta yongan) — eskicha: bron bekor qilinadi')
bot._bron_qoy('81', MIJOZ, 'TRYOQ')
javob = bron_bos('bron_och:81:TRYOQ')
sinov('bron o\'chdi', '81' not in bot._BRON and 'bron bekor qilindi' in javob, javob)

print('— boshqa buyurtmadagi bron / bron yo\'q — avvalgidek')
yangi('TR07', nums=('91',))
javob = bron_bos('bron_och:91:BOSHQA')
sinov('boshqa buyurtma: tegilmadi', (bot._BRON.get('91') or {}).get('order') == 'TR07' and 'boshqa buyurtmada' in javob, javob)
javob = bron_bos('bron_och:99:TR07')
sinov("bron yo'q: «allaqachon yo'q»", 'allaqachon yo\'q' in javob, javob)

print("— «2-mijoz keldi» ogohlantirishi: to'langan buyurtma broni — tugma yo'q, to'lanmagan — bor")
ikkinchi = {'id': 888001, 'ism': 'Ikkinchi', 'username': ''}
SOROV.clear()
bot._bron_ogoh_yubor('61', ikkinchi, 'sinov')   # TR05 — to'langan
s = sorov('sendMessage')
sinov("to'langan: xabar ketdi, bron tugmasi yo'q, «2-mijozga yozish» bor", len(s) == 1 and not bron_tugma_bor(s[0].get('reply_markup'))
      and 'tg://user?id=888001' in json.dumps(s[0].get('reply_markup')), repr(s)[:300])
SOROV.clear()
bot._bron_ogoh_yubor('91', ikkinchi, 'sinov')   # TR07 — to'lanmagan
s = sorov('sendMessage')
sinov("to'lanmagan: bron tugmasi bor (bron_och:91:TR07)", len(s) == 1 and 'bron_och:91:TR07' in json.dumps(s[0].get('reply_markup')),
      repr(s)[:300])

print('— mijoz bekor qilgan buyurtma — bron tugmasi yo\'q (bron o\'zi ochilgan)')
kl = bot._buyurtma_klava(MIJOZ, 'TR07', 'bekor', ['91'])
sinov('bekor: bron tugmasi yo\'q', not bron_tugma_bor(kl), repr(kl))

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
