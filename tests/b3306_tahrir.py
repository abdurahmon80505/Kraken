# -*- coding: utf-8 -*-
"""tests/b3306_tahrir.py — 3306: admin buyurtmani tahrirlaydi (tovar o'chirish / qo'shish, dona, narx). Yozuv, jami, chegirma,
bron, admin xabarlari (buyurtma matni + chek caption), Store chaqiruvi; mijozga xabar YO'Q.

Ishga tushirish:  python tests/b3306_tahrir.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get, bot._kk_sheet va bot._buyurtma_elon almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777003, №TT…); real mijozga tegilmaydi.
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
_VAQT = tempfile.mkdtemp(prefix='b3306-')
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
SHEET = []
MIJOZ, ADMIN = 777003, bot.ADMIN_ID
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


STORE_OK = [True]


def _sheet(action, timeout=30, **p):
    SHEET.append((action, p))
    return {'ok': True} if STORE_OK[0] else None


ELONLAR = {'55': {'num': '55', '_narx': 120}, '56': {'num': '56', '_narx': None}}


def _elon(n):
    e = ELONLAR.get(str(n))
    return (dict(e), {}, '') if e else ({'num': str(n)}, {}, 'topilmadi')


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: True
bot._kk_sheet = _sheet
bot._buyurtma_elon = _elon
bot._narx_son = lambda e: e.get('_narx')
bot._buyurtma_sarlavha = lambda e, m, r=None: f"Tovar {e['num']}"
bot.check_init_data = lambda s, max_age=86400: {'admin': ADMIN, 'mijoz': MIJOZ}.get(s)
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


class Sorov:
    def __init__(self, d):
        self._d = d

    async def json(self):
        return self._d


def tahrir(order, tovar, init='admin'):
    """Sayt «Saqlash» bosdi → (status, javob)."""
    SOROV.clear()
    SHEET.clear()
    r = asyncio.run(bot.admin_buyurtma_tahrir_endpoint(Sorov({'initData': init, 'uid': str(MIJOZ), 'order': order, 'tovar': tovar})))
    return r.status, json.loads(r.body)


ESKI = [{'num': '21', 'nom': 'Tovar 21', 'narx': 500, 'soni': 1}, {'num': '22', 'nom': 'Tovar 22', 'narx': 30, 'soni': 2, 'chegirma': 5}]
BUYURTMA_HTML = ("🛒 <b>Yangi buyurtma</b> №{o}\n\n📱 <b>Tovar 21</b> · e'lon №21\n📱 <b>Tovar 22</b> × 2\n💵 560$\n\n"
                 "👤 S\n📞 +998900000001\n📍 Emu\n\n✅ <b>To'landi</b> · 08:00\n🕒 Buyurtma: 31.10.2026 07:50")


def yangi(order, holat='tolandi', xb=True):
    b = {'order': order, 'ts': 1, 'holat': holat, 'tovar': [dict(x) for x in ESKI], 'jami': 560, 'tur': 'emu', 'ism': 'S',
         'tel': '+998900000001', 'til': 'uz', 'joy': {'kurs': 12000}}
    if xb:
        t, e = bot._html_b_ents(BUYURTMA_HTML.format(o=order))
        ct, ce = bot._html_b_ents(bot._chek_admin_matn(b))
        b['admin_xb'] = [{'m': 501, 'c': 0, 't': t, 'e': e}, {'m': 502, 'c': 1, 't': ct, 'e': ce}]
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, b)
    for x in ESKI:
        bot._bron_qoy(x['num'], MIJOZ, order)


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


def u16(t, o, ln):
    return t.encode('utf-16-le')[o * 2:(o + ln) * 2].decode('utf-16-le')


def bold(t, ents):
    return [u16(t, x['offset'], x['length']) for x in ents if x['type'] == 'bold']


print('— kirish tekshiruvi (_tahrir_kirish)')
k = bot._tahrir_kirish
sinov("to'g'ri ro'yxat", k([{'num': 21, 'soni': '2', 'narx': '35.5'}]) == [{'num': '21', 'soni': 2, 'narx': 35.5}])
sinov("bo'sh / ro'yxat emas — rad", k([]) is None and k(None) is None and k({'num': 1}) is None)
sinov('takror raqam — rad', k([{'num': 1, 'soni': 1, 'narx': 1}, {'num': '1', 'soni': 1, 'narx': 1}]) is None)
sinov('dona 0 / 100 — rad', k([{'num': 1, 'soni': 0, 'narx': 1}]) is None and k([{'num': 1, 'soni': 100, 'narx': 1}]) is None)
sinov('narx manfiy / matn — rad', k([{'num': 1, 'soni': 1, 'narx': -1}]) is None and k([{'num': 1, 'soni': 1, 'narx': 'x'}]) is None)
sinov("raqam harf — rad", k([{'num': 'abc', 'soni': 1, 'narx': 1}]) is None)
sinov('11 ta — rad (ko\'pi 10)', k([{'num': i, 'soni': 1, 'narx': 1} for i in range(1, 12)]) is None)
sinov("narx 0 (sovg'a) — qabul", k([{'num': 5, 'soni': 1, 'narx': 0}]) == [{'num': '5', 'soni': 1, 'narx': 0}])

print("— to'langan buyurtma: 21 o'chirildi, 22 → 3 dona × 28$, 55 qo'shildi (Store 120$ → 100$)")
yangi('TT01')
st, j = tahrir('TT01', [{'num': '22', 'soni': 3, 'narx': 28}, {'num': '55', 'soni': 1, 'narx': 100}])
sinov('200, ok, store, xabar=tahrir', st == 200 and j.get('ok') and j.get('store') is True and j.get('xabar') == 'tahrir', repr(j)[:300])
b = yozuv('TT01')
sinov('yozuv tarkibi: 22 (nom saqlangan), 55 (Store nomi)',
      [(x['num'], x['nom'], x['narx'], x['soni']) for x in b['tovar']] == [('22', 'Tovar 22', 28, 3), ('55', 'Tovar 55', 100, 1)],
      repr(b['tovar']))
sinov("chegirma: 22 → 30+5−28 = 7 · 55 → 120−100 = 20", [x.get('chegirma') for x in b['tovar']] == [7, 20], repr(b['tovar']))
sinov('jami = 28×3 + 100 = 184', b['jami'] == 184, repr(b['jami']))
sinov('tahrir_ts yozildi, holat o\'zgarmadi', b.get('tahrir_ts') and b['holat'] == 'tolandi')
sinov('javobdagi buyurtma — yangi tarkib + chegirma',
      [(x['num'], x['soni'], x['chegirma']) for x in j['buyurtma']['tovar']] == [('22', 3, 7), ('55', 1, 20)], repr(j['buyurtma'])[:300])
m, c = sorov('editMessageText'), sorov('editMessageCaption')
sinov('buyurtma xabari — editMessageText (501), chek — editMessageCaption (502)',
      [x['message_id'] for x in m] == [501] and [x['message_id'] for x in c] == [502], repr(SOROV)[:300])
t = m[0]['text'] if m else ''
sinov("matn: «✏️ O'zgartirildi», «2 ta tovar», eski 21 yo'q", "✏️ O'zgartirildi · " in t and '🧺 2 ta tovar:' in t
      and '№21' not in t and 'Tovar 21' not in t, t)
sinov("qatorlar: «1. Tovar 22 · №22 · 28$ × 3 = 84$ 🎟 (Store 35$)», «2. Tovar 55 · №55 · 100$ 🎟 (Store 120$)»",
      '1. Tovar 22 · №22 · 28$ × 3 = 84$ 🎟 (Store 35$)\n' in t and '2. Tovar 55 · №55 · 100$ 🎟 (Store 120$)\n' in t, t)
sinov("jami qatori: «💵 Jami 184$ ≈ 2 208 000 so'm (kurs 12 000)» + admin chegirmasi −41$",
      "💵 Jami 184$ ≈ 2 208 000 so'm (kurs 12 000)\n🎟 Admin chegirmasi: −41$\n\n👤 S" in t, t)
sinov('bosh va oxir saqlangan (sarlavha, mijoz, holat zanjiri, vaqt)', t.startswith('🛒 Yangi buyurtma №TT01\n\n✏️')
      and t.endswith("📍 Emu\n\n✅ To'landi · 08:00\n🕒 Buyurtma: 31.10.2026 07:50"), t)
e = m[0]['entities'] if m else []
bl = bold(t, e)
sinov("bold: «Yangi buyurtma» (oldin) va «To'landi» (surilgan) to'g'ri joyda; eski «Tovar 21» yo'q",
      'Yangi buyurtma' in bl and "To'landi" in bl and 'Tovar 21' not in bl, repr(bl))
sinov("bold: «O'zgartirildi», nomlar", "O'zgartirildi" in bl and 'Tovar 22' in bl and 'Tovar 55' in bl, repr(bl))
lk = [(u16(t, x['offset'], x['length']), x['url']) for x in e if x['type'] == 'text_link']
sinov('havola: nom → e\'lon (startapp=elon_55)', ('Tovar 55', f'https://t.me/{bot.BOT_USERNAME}?startapp=elon_55') in lk, repr(lk))
sinov('tugmalar: keyingi bosqich (Yo\'lda); to\'langan — bron tugmasi yo\'q (3304)',
      f'bh:yolda:{MIJOZ}:TT01' in str(m[0].get('reply_markup')) and 'bron_och' not in str(m[0].get('reply_markup')),
      repr(m[0].get('reply_markup'))[:300])
ct = c[0]['caption'] if c else ''
sinov("chek caption: «💵 184$ ≈ 2 208 000 so'm ✏️», qolgani saqlangan",
      "\n💵 184$ ≈ 2 208 000 so'm ✏️\n" in ct and ct.startswith('🧾 Chek keldi — №TT01') and '560' not in ct, ct)
sinov('chek: bold «Chek keldi» saqlangan', 'Chek keldi' in bold(ct, c[0]['caption_entities'] if c else []))
sinov('yozuvdagi admin_xb matnlari ham yangi', all('✏️' in x['t'] for x in b['admin_xb']) and len(b['admin_xb']) == 2)
sinov('bron: 21 ochildi, 55 — shu buyurtmaga', '21' not in bot._BRON and (bot._BRON.get('55') or {}).get('order') == 'TT01'
      and (bot._BRON.get('22') or {}).get('order') == 'TT01', repr(bot._BRON))
sinov("mijozga HECH NARSA ketmadi (sendMessage / copyMessage yo'q)",
      not sorov('sendMessage') and not sorov('copyMessage')
      and all(str(d.get('chat_id')) == str(ADMIN) for _, d in SOROV if 'chat_id' in d), repr(SOROV)[:300])
sh = [p for a, p in SHEET if a == 'buyurtmaTahrir']
d = json.loads(sh[0]['data']) if sh else {}
sinov('Store: buyurtmaTahrir bir marta', len(SHEET) == 1 and len(sh) == 1, repr(SHEET)[:300])
sinov('Store ma\'lumoti: order, user_id, holat, jami, kim',
      (d.get('order'), d.get('user_id'), d.get('holat'), d.get('jami'), d.get('kim')) == ('TT01', str(MIJOZ), 'tolandi', 184, 'admin'),
      repr(d)[:300])
sinov('Store: eski (nima edi) va yangi tarkib (chegirma bilan)',
      d.get('eski') == [{'num': '21', 'narx': 500, 'soni': 1}, {'num': '22', 'narx': 30, 'soni': 2}]
      and [(x['num'], x['narx'], x['soni'], x['chegirma']) for x in d.get('tovar') or []] == [('22', 28, 3, 7), ('55', 100, 1, 20)],
      repr(d)[:400])

print('— shu tarkib qayta saqlandi (oldingi Store javob bermagan bo\'lsa) — faqat Store')
st, j = tahrir('TT01', [{'num': '22', 'soni': 3, 'narx': 28}, {'num': '55', 'soni': 1, 'narx': 100}])
sinov("200, xabar='-', Telegram'ga hech narsa yo'q", st == 200 and j.get('xabar') == '-' and not SOROV, repr(j)[:200] + repr(SOROV)[:200])
sinov('Store yana chaqirildi', [a for a, _ in SHEET] == ['buyurtmaTahrir'])
sinov('tahrir_ts surilmadi, jami o\'sha', yozuv('TT01')['jami'] == 184)

print("— Store javob bermadi — yozuv baribir yangilanadi, store=false (sayt «qayta saqlang» deydi)")
STORE_OK[0] = False
st, j = tahrir('TT01', [{'num': '22', 'soni': 1, 'narx': 35}])
STORE_OK[0] = True
sinov('200, store=false', st == 200 and j.get('store') is False, repr(j)[:200])
sinov("yozuv: 22 × 1 = 35$, chegirma yo'q (Store narxi)", yozuv('TT01')['tovar'] == [{'num': '22', 'nom': 'Tovar 22', 'narx': 35, 'soni': 1}]
      and yozuv('TT01')['jami'] == 35, repr(yozuv('TT01')['tovar']))
t = sorov('editMessageText')[0]['text'] if sorov('editMessageText') else ''
sinov("matn: «1 ta tovar», chegirma qatori yo'q", '🧺 1 ta tovar:' in t and 'Admin chegirmasi' not in t and '1. Tovar 22 · №22 · 35$\n' in t, t)
sinov('ikkinchi tahrir ham bosh / oxirni buzmadi', t.startswith('🛒 Yangi buyurtma №TT01\n\n✏️') and t.endswith('07:50')
      and t.count("✏️ O'zgartirildi") == 1, t)
sinov('bron 55 ochildi', '55' not in bot._BRON, repr(bot._BRON))

print("— sovg'a (narx 0) va Store narxi yo'q tovar")
st, j = tahrir('TT01', [{'num': '22', 'soni': 2, 'narx': 0}, {'num': '56', 'soni': 1, 'narx': 10}])
b = yozuv('TT01')
sinov("22: narx 0, chegirma 35 (sovg'a)", b['tovar'][0]['narx'] == 0 and b['tovar'][0]['chegirma'] == 35, repr(b['tovar']))
sinov("56: Store narxi yo'q — chegirma yo'q", 'chegirma' not in b['tovar'][1] and b['tovar'][1]['narx'] == 10, repr(b['tovar']))
t = sorov('editMessageText')[0]['text'] if sorov('editMessageText') else ''
sinov("matn: «🎁 Sovg'a × 2 (Store 35$)», jami 10$", "Tovar 22 · №22 · 🎁 Sovg'a × 2 (Store 35$)\n" in t and '💵 Jami 10$' in t, t)

print('— rad etiladiganlar')
st, j = tahrir('TT01', [{'num': '99', 'soni': 1, 'narx': 5}])
sinov("Store'da yo'q raqam → 400 + nums, yozuv o'zgarmadi", st == 400 and j.get('nums') == ['99']
      and [x['num'] for x in yozuv('TT01')['tovar']] == ['22', '56'] and not SHEET and not SOROV, repr(j))
st, j = tahrir('TT01', [{'num': '22', 'soni': 1, 'narx': 5}], init='mijoz')
sinov('admin emas → 401', st == 401 and not SHEET, repr(j))
st, j = tahrir('TT01', [{'num': '22', 'soni': 0, 'narx': 5}])
sinov('buzuq parametr → 400', st == 400 and j.get('error') == 'parametr', repr(j))
st, j = tahrir('YOQ01', [{'num': '22', 'soni': 1, 'narx': 5}])
sinov("yo'q buyurtma → 404", st == 404, repr(j))
yangi('TT02', holat='bekor')
st, j = tahrir('TT02', [{'num': '22', 'soni': 1, 'narx': 5}])
sinov("bekor qilingan → 409, Store'ga ham, Telegram'ga ham hech narsa", st == 409 and j.get('error') == 'bekor' and not SHEET
      and not SOROV, repr(j))
yangi('TT03')
kod, _ = bot._tahrir_qoy(MIJOZ, 'TT03', [{'num': '21'}], [{'num': '21', 'nom': 'x', 'narx': 1, 'soni': 1}])
sinov("orada boshqa o'zgarish (nusxa eskirgan) → 'band', yozuv o'zgarmadi", kod == 'band' and yozuv('TT03')['jami'] == 560)

print("— yozuvda admin xabari yo'q (bot qayta yongan) — yangi xabar adminga")
yangi('TT04', holat='kutilmoqda', xb=False)
st, j = tahrir('TT04', [{'num': '21', 'soni': 1, 'narx': 450}])
s = sorov('sendMessage')
sinov("xabar='yangi', bitta sendMessage — ADMIN'ga", j.get('xabar') == 'yangi' and len(s) == 1 and s[0]['chat_id'] == ADMIN, repr(SOROV)[:300])
t = s[0]['text'] if s else ''
sinov("matn: «✏️ Buyurtma o'zgartirildi №TT04», tovar, mijoz, holat",
      "✏️ <b>Buyurtma o'zgartirildi</b> №TT04\n\n" in t and '450$ 🎟 (Store 500$)' in t and '👤 S\n📞 +998900000001' in t
      and "\n\n⏳ <b>To'lov kutilmoqda</b>\n🕒 Buyurtma: " in t, t)
sinov('holat qatori — zanjir taniydigan ko\'rinish (keyingi tugma davom ettiradi)',
      bot._HOLAT_QATOR_RE.search(html.unescape(re.sub(r'<[^>]+>', '', t))) is not None)
sinov('tugmalar: to\'lov kutilmoqda → «To\'landi» va «To\'lovni kutmay»', f'bh:tolandi:{MIJOZ}:TT04' in str(s[0].get('reply_markup'))
      and f'bh:yolda:{MIJOZ}:TT04' in str(s[0].get('reply_markup')) if s else False)
sinov('yangi xabar yozuvga eslab qolindi', [x['m'] for x in yozuv('TT04').get('admin_xb') or []] == [MID[0]])
sinov('bron: 22 ochildi (TT04 niki), 21 qoldi', (bot._BRON.get('21') or {}).get('order') == 'TT04'
      and (bot._BRON.get('22') or {}).get('order') != 'TT04', repr(bot._BRON))

print("— yetkazilgan buyurtmaga qo'shilgan tovar bron qilinmaydi; boshqa buyurtma broniga tegilmaydi")
yangi('TT05', holat='yetkazildi', xb=False)
bot._BRON.pop('55', None)
bot._bron_qoy('21', 123, 'BOSHQA')
st, j = tahrir('TT05', [{'num': '22', 'soni': 2, 'narx': 30}, {'num': '55', 'soni': 1, 'narx': 120}])
sinov("55 bron qilinmadi (yetkazilgan)", '55' not in bot._BRON, repr(bot._BRON))
sinov('21 — BOSHQA buyurtma broni joyida', (bot._BRON.get('21') or {}).get('order') == 'BOSHQA')
sinov('jami 180', yozuv('TT05')['jami'] == 180)

print('— Store yozuvi (buyurtmaYoz) va admin ro\'yxati chegirmani ham beradi')
sd = bot._buyurtma_sheet_dict(MIJOZ, yozuv('TT01'))
sinov('_buyurtma_sheet_dict: chegirma bor joyda bor, yo\'q joyda yo\'q',
      sd['tovar'][0].get('chegirma') == 35 and 'chegirma' not in sd['tovar'][1], repr(sd['tovar']))
ad = bot._admin_buyurtma_dict(MIJOZ, yozuv('TT01'))
sinov('_admin_buyurtma_dict: chegirma, tahrir_ts', ad['tovar'][0]['chegirma'] == 35 and ad['tovar'][1]['chegirma'] == 0
      and ad.get('tahrir_ts'), repr(ad)[:300])

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
