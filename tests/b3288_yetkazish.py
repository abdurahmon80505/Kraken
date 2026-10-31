# -*- coding: utf-8 -*-
"""tests/b3288_yetkazish.py — 3288: buyurtma bosqichlari 🚚 Yo'lga chiqdi (isbot) → 📦 Qabul qilindi → ⭐ Sharh → 🔒 Yopildi.

Ishga tushirish:  python tests/b3288_yetkazish.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get almashtirilgan (so'rovlar SOROV ga yoziladi), saqlash / Sheets — o'chiq.
Buyurtmalar — soxta (uid 777001, №TEST01…); real mijozga tegilmaydi.
"""
import asyncio
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL'):
    os.environ.pop(k, None)

import requests


def _tarmoq_yoq(*a, **kw):
    raise AssertionError(f'tarmoq so\'rovi: {a[:1]}')


requests.post = requests.get = _tarmoq_yoq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

NATIJA = [0, 0]
SOROV = []
SOTUV = []
MIJOZ_BLOK = set()   # shu chat_id larga Telegram 403 qaytaradi


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


class Javob:
    def __init__(self, kod=200, j=None, content=b''):
        self.status_code, self._j, self.content = kod, j or {}, content

    def json(self):
        return self._j


def _post(url, **kw):
    usul = url.rsplit('/', 1)[-1]
    d = kw.get('json') or kw.get('data') or {}
    SOROV.append((usul, d, bool(kw.get('files'))))
    if str(d.get('chat_id')) in {str(x) for x in MIJOZ_BLOK}:
        return Javob(403, {'ok': False, 'description': 'Forbidden: bot was blocked by the user'})
    if usul == 'sendPhoto':
        return Javob(200, {'ok': True, 'result': {'message_id': 5, 'photo': [{'file_id': 'kichik'}, {'file_id': 'FID_KATTA'}]}})
    if usul == 'getFile':
        return Javob(200, {'ok': True, 'result': {'file_path': 'photos/x.jpg'}})
    return Javob(200, {'ok': True, 'result': {'message_id': 1}})


def _get(url, **kw):
    SOROV.append(('GET', url.rsplit('/', 1)[-1], False))
    if url.endswith('photos/x.jpg'):
        return Javob(200, content=JPEG)
    if '/getFile?' in url:
        return Javob(200, {'ok': True, 'result': {'file_path': 'photos/x.jpg'}})
    return _post(url, **kw)


bot.req.post = _post
bot.req.get = _get
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._sotuv_sheet_yoz = lambda uid, b: SOTUV.append((uid, b.get('order'))) or True
bot.check_init_data = lambda s, max_age=86400: int(s) if str(s).isdigit() else None

JPEG = bytes((0xFF, 0xD8, 0xFF, 0xE0)) + b'0' * 200
MIJOZ, ADMIN = 777001, bot.ADMIN_ID


class Fayl:
    def __init__(self, b):
        self.file = io.BytesIO(b)


class So:
    """Soxta aiohttp so'rovi: json() yoki post() (multipart)."""
    def __init__(self, d):
        self.d = d

    async def json(self):
        return self.d

    async def post(self):
        return self.d


def chaqir(fn, d):
    r = asyncio.run(fn(So(d)))
    try:
        return r.status, json.loads(r.text)
    except Exception:
        return r.status, r.body


def yangi(order, holat='tolandi', til='uz'):
    with bot._MIJOZ_LOCK:
        m = bot._mijoz_ochiq(MIJOZ)
        m['buyurtma'] = [b for b in m['buyurtma'] if b.get('order') != order]
        m['buyurtma'].append({'order': order, 'ts': 1000 + len(m['buyurtma']), 'holat': holat, 'til': til, 'ism': 'Sinov',
                              'jami': 100, 'tovar': [{'num': 1, 'nom': 'Telefon', 'narx': 100, 'soni': 1}]})


def yozuv(order):
    return next(b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b['order'] == order)


def oxirgi(usul, chat=None):
    for s in reversed(SOROV):
        if s[0] == usul and (chat is None or str(s[1].get('chat_id')) == str(chat)):
            return s
    return None


async def _kut():
    await asyncio.sleep(0.2)


print('3288: yetkazish bosqichlari')

# ── 1. admin isbot — havola → «yolda», mijozga havola tugmasi bilan ──
yangi('TEST01')
SOROV.clear()
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'test01', 'amal': 'isbot',
                                            'havola': 'https://yandex.uz/route/abc'})
sinov('isbot havola — 200, holat yolda', k == 200 and j.get('holat') == 'yolda', (k, j))
sinov("isbot havola — javobda tur 'havola' + url", (j.get('yetkaz') or {}).get('isbot', {}).get('url') == 'https://yandex.uz/route/abc')
s = oxirgi('sendMessage', MIJOZ)
sinov("mijozga «yo'lga chiqdi» xabari", s and "yo'lga chiqdi" in s[1]['text'], repr(s))
kl = (s[1].get('reply_markup') or {}).get('inline_keyboard', []) if s else []
sinov('xabarda «🔗 Yetkazishni kuzatish» (havola) + «📦 Buyurtmalarim»',
      [q[0]['text'] for q in kl] == ['🔗 Yetkazishni kuzatish', '📦 Buyurtmalarim'] and kl[0][0]['url'] == 'https://yandex.uz/route/abc',
      repr(kl))
sinov('tasdiqlangan — sotuv yozuvi chaqirildi', ('TEST01' in [o for _, o in SOTUV]), repr(SOTUV))
sinov('isbot qayta yuklansa — almashadi (200)', chaqir(bot.admin_buyurtma_endpoint, {
    'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST01', 'amal': 'isbot', 'havola': 'https://yandex.uz/route/yangi'})[0] == 200
      and yozuv('TEST01')['yetkaz']['isbot']['url'] == 'https://yandex.uz/route/yangi')

# ── 2. noto'g'ri isbot ──
sinov("havola http:// — 400", chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST01',
                                                                   'amal': 'isbot', 'havola': 'http://x.uz/a'})[0] == 400)
sinov("rasm JPEG emas — 400", chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST01',
                                                                  'amal': 'isbot', 'rasm': Fayl(b'PNG....')})[0] == 400)
sinov("rasm > 900 KB — 400", chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST01',
      'amal': 'isbot', 'rasm': Fayl(JPEG + b'0' * bot._CHEK_ILOVA_MAX)})[0] == 400)
sinov("admin emas — 401", chaqir(bot.admin_buyurtma_endpoint, {'initData': str(MIJOZ), 'uid': str(MIJOZ), 'order': 'TEST01',
                                                              'amal': 'qabul'})[0] == 401)
sinov("noma'lum amal — 400", chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST01',
                                                                 'amal': 'tolandi'})[0] == 400)
sinov("yo'q buyurtma — 404", chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'YOQ999',
                                                                 'amal': 'yop'})[0] == 404)

# ── 3. isbot rasm → mijozga sendPhoto, file_id saqlanadi, /isbot_rasm qaytaradi ──
yangi('TEST02', til='ru')
SOROV.clear()
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST02', 'amal': 'isbot',
                                            'rasm': Fayl(JPEG)})
s = oxirgi('sendPhoto', MIJOZ)
sinov('isbot rasm — 200, yolda, mijozga yuborildi', k == 200 and j.get('holat') == 'yolda' and j.get('mijozga') is True, (k, j))
sinov('rasm mijozga sendPhoto (fayl bilan), caption ru', s and s[2] and 'уже в пути' in s[1]['caption'], repr(s))
sinov("yozuvda fid — eng katta o'lcham", yozuv('TEST02')['yetkaz']['isbot'] == {'tur': 'rasm', 'fid': 'FID_KATTA',
                                                                               'ts': yozuv('TEST02')['yetkaz']['isbot']['ts']})
sinov("javobda fid chiqmaydi", 'fid' not in json.dumps(j), repr(j))
k, body = chaqir(bot.isbot_rasm_endpoint, {'initData': str(MIJOZ), 'order': 'TEST02'})
sinov('/isbot_rasm (egasi) — JPEG baytlari', k == 200 and body == JPEG, (k, body[:10] if isinstance(body, bytes) else body))
k, body = chaqir(bot.isbot_rasm_endpoint, {'initData': str(ADMIN), 'order': 'TEST02', 'uid': str(MIJOZ)})
sinov('/isbot_rasm (admin, uid bilan) — 200', k == 200 and body == JPEG)
sinov("/isbot_rasm — begona mijoz 404", chaqir(bot.isbot_rasm_endpoint, {'initData': '555', 'order': 'TEST02'})[0] == 404)
sinov("/isbot_rasm — havola isbotida 404", chaqir(bot.isbot_rasm_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01'})[0] == 404)

# rasm mijozga bormasa (botni to'xtatgan) — adminga yuboriladi, fid baribir saqlanadi
yangi('TEST03')
MIJOZ_BLOK.add(MIJOZ)
SOROV.clear()
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST03', 'amal': 'isbot',
                                            'rasm': Fayl(JPEG)})
MIJOZ_BLOK.clear()
s = oxirgi('sendPhoto', ADMIN)
sinov('mijoz bloklagan — 200, mijozga false, adminga rasm', k == 200 and j.get('mijozga') is False and s
      and 'mijozga bormadi' in s[1]['caption'], (k, j, s))
sinov('mijoz bloklagan — fid saqlandi', yozuv('TEST03')['yetkaz']['isbot'].get('fid') == 'FID_KATTA')

# ── 4. mijoz «✅ Qabul qilib oldim» ──
SOROV.clear()
k, j = chaqir(bot.buyurtma_qabul_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01'})
sinov('mijoz qabul — 200, yetkazildi', k == 200 and j.get('holat') == 'yetkazildi' and not j.get('takror'), (k, j))
sinov("qabul_kim 'mijoz'", yozuv('TEST01')['yetkaz'].get('qabul_kim') == 'mijoz' and j['yetkaz'].get('qabul_kim') == 'mijoz')
asyncio.run(_kut())
s = oxirgi('sendMessage', ADMIN)
sinov('adminga «📦 Mijoz qabul qildi»', s and 'Mijoz qabul qildi' in s[1]['text'] and 'TEST01' in s[1]['text'], repr(s))
k, j = chaqir(bot.buyurtma_qabul_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01'})
sinov('qayta bosish — 200, takror', k == 200 and j.get('takror') is True, (k, j))
yangi('TEST04')   # tolandi — hali yo'lga chiqmagan
k, j = chaqir(bot.buyurtma_qabul_endpoint, {'initData': str(MIJOZ), 'order': 'TEST04'})
sinov("«tolandi» da mijoz qabul — 409 erta", k == 409 and j.get('error') == 'erta', (k, j))
yangi('TEST05', holat='bekor')
sinov("bekor buyurtma — 409", chaqir(bot.buyurtma_qabul_endpoint, {'initData': str(MIJOZ), 'order': 'TEST05'})[0] == 409)
sinov("imzosiz — 401", chaqir(bot.buyurtma_qabul_endpoint, {'initData': 'x', 'order': 'TEST01'})[0] == 401)
sinov("begona mijoz — 404", chaqir(bot.buyurtma_qabul_endpoint, {'initData': '555', 'order': 'TEST01'})[0] == 404)

# ── 5. admin «📦 Qabul qilindi» (mijoz unutsa) ──
SOROV.clear()
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST02', 'amal': 'qabul'})
sinov("admin qabul — 200, yetkazildi, qabul_kim 'admin'", k == 200 and j.get('holat') == 'yetkazildi'
      and j['yetkaz'].get('qabul_kim') == 'admin', (k, j))
s = oxirgi('sendMessage', MIJOZ)
sinov("mijozga «qabul qilindi» + «⭐ Оставить отзыв» (ru)", s and 'получен' in s[1]['text']
      and s[1]['reply_markup']['inline_keyboard'][0][0]['text'] == '⭐ Оставить отзыв', repr(s))
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST02', 'amal': 'isbot',
                                            'havola': 'https://yandex.uz/x'})
sinov("qabuldan keyin isbot — 409", k == 409, (k, j))

# ── 6. sharh → «yopildi» ──
yangi('TEST06')
sinov("sharh qabuldan oldin — 409 erta", chaqir(bot.buyurtma_sharh_endpoint, {'initData': str(MIJOZ), 'order': 'TEST06',
                                                                              'baho': 5})[0] == 409)
sinov("baho 0 — 400", chaqir(bot.buyurtma_sharh_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01', 'baho': 0})[0] == 400)
sinov("baho 6 — 400", chaqir(bot.buyurtma_sharh_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01', 'baho': '6'})[0] == 400)
SOROV.clear()
bot.SHARH_MATN = True   # 3262.1: matn odatda o'chiq — bu yerda yoqilgan holat (b32621_sharh_matn.py — o'chig'i)
SOROV.clear()
k, j = chaqir(bot.buyurtma_sharh_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01', 'baho': 4,
                                            'matn': '  Zo\'r,\n tez   keldi ' + 'x' * 600})
sinov('sharh — 200, yopildi', k == 200 and j.get('holat') == 'yopildi', (k, j))
sh = yozuv('TEST01')['yetkaz'].get('sharh') or {}
sinov('sharh matni — bo\'shliqlar siqildi, ≤ 500', sh.get('baho') == 4 and sh.get('matn', '').startswith("Zo'r, tez keldi x")
      and len(sh.get('matn', '')) == 500, repr(sh)[:120])
bot.SHARH_MATN = False
asyncio.run(_kut())
s = oxirgi('sendMessage', ADMIN)
sinov('adminga «⭐ Sharh» ★★★★☆ + «Buyurtma yopildi»', s and '★★★★☆' in s[1]['text'] and 'Buyurtma yopildi' in s[1]['text'], repr(s))
k, j = chaqir(bot.buyurtma_sharh_endpoint, {'initData': str(MIJOZ), 'order': 'TEST01', 'baho': 1})
sinov('ikkinchi sharh — takror, eskisi qoladi', k == 200 and j.get('takror') and yozuv('TEST01')['yetkaz']['sharh']['baho'] == 4,
      (k, j))

# ── 7. admin «🔒 Yopish», keyin mijoz sharhi baribir yoziladi ──
SOROV.clear()
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST02', 'amal': 'yop'})
sinov("admin yopish — 200, yopildi, yop_kim 'admin'", k == 200 and j.get('holat') == 'yopildi' and j['yetkaz'].get('yop_kim') == 'admin',
      (k, j))
s = oxirgi('sendMessage', MIJOZ)
sinov('mijozga «🔒 … закрыт»', s and 'закрыт' in s[1]['text'], repr(s))
k, j = chaqir(bot.buyurtma_sharh_endpoint, {'initData': str(MIJOZ), 'order': 'TEST02', 'baho': 5})
sinov('yopilgandan keyin sharh — 200 (holat yopildi qoladi)', k == 200 and j.get('holat') == 'yopildi'
      and yozuv('TEST02')['yetkaz']['sharh']['baho'] == 5, (k, j))
k, j = chaqir(bot.admin_buyurtma_endpoint, {'initData': str(ADMIN), 'uid': str(MIJOZ), 'order': 'TEST02', 'amal': 'yop'})
sinov("qayta yopish — takror", k == 200 and j.get('takror') is True, (k, j))

# ── 8. bot tugmasi (_buyurtma_holat_qoy) — admin bosgani yoziladi ──
yangi('TEST07', holat='yolda')
kod, b = bot._buyurtma_holat_qoy(MIJOZ, 'TEST07', 'yetkazildi')
sinov("bot tugmasi «Yetkazildi» — qabul_kim 'admin'", kod == 'ok' and b['yetkaz'].get('qabul_kim') == 'admin', repr(b))
kod, b = bot._buyurtma_holat_qoy(MIJOZ, 'TEST07', 'yopildi')
sinov("bot tugmasi «🔒 Yopish» — yopildi, yop_kim 'admin'", kod == 'ok' and b['holat'] == 'yopildi' and b['yetkaz'].get('yop_kim') == 'admin')
kl = bot._buyurtma_klava(MIJOZ, 'TEST07', 'yetkazildi', [])
sinov('admin klaviaturasida «🔒 Yopish» (3301: yetkazilgach)', '🔒' in json.dumps(kl, ensure_ascii=False), repr(kl))
sinov("_HOLAT_TASDIQ da 'yopildi' (sotuv yozuvi)", 'yopildi' in bot._HOLAT_TASDIQ)

# ── 9. admin ro'yxati ──
k, j = chaqir(bot.admin_buyurtmalar_endpoint, {'initData': str(ADMIN)})
r = j.get('buyurtma') or []
sinov('admin ro\'yxati — 200, yangisi tepada', k == 200 and len(r) >= 7 and r[0]['ts'] >= r[-1]['ts'], (k, len(r)))
t1 = next((x for x in r if x['order'] == 'TEST01'), {})
sinov('ro\'yxatda holat + yetkaz + tovar', t1.get('holat') == 'yopildi' and t1['yetkaz'].get('sharh', {}).get('baho') == 4
      and t1['tovar'][0]['nom'] == 'Telefon', repr(t1)[:200])
sinov("ro'yxatda fid chiqmaydi", 'FID_KATTA' not in json.dumps(j))
sinov("admin ro'yxati — mijozga 401", chaqir(bot.admin_buyurtmalar_endpoint, {'initData': str(MIJOZ)})[0] == 401)

# ── 10. Sheets: yetkaz — JSON ustun, qaytib o'qiladi ──
d = bot._buyurtma_sheet_dict(MIJOZ, yozuv('TEST01')) if bot._buyurtma_sheet_dict.__code__.co_argcount == 2 \
    else bot._buyurtma_sheet_dict(yozuv('TEST01'))
sinov("Sheets'ga 'yetkaz' — JSON matn", isinstance(d.get('yetkaz'), str) and json.loads(d['yetkaz'])['sharh']['baho'] == 4,
      repr(d.get('yetkaz'))[:120])

# ── 11. mijoz_holat javobida yetkaz (fid'siz) ──
sinov('_yetkaz_javob — rasm isbotida fid yo\'q', bot._yetkaz_javob(yozuv('TEST03')) == {
    'isbot': {'tur': 'rasm', 'ts': yozuv('TEST03')['yetkaz']['isbot']['ts']}}, repr(bot._yetkaz_javob(yozuv('TEST03'))))
sinov('_yetkaz_javob — bo\'sh yozuv → {}', bot._yetkaz_javob({}) == {})

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
