# -*- coding: utf-8 -*-
"""tests/b4266_yolda_havola.py — 4266: admin chatiga raqam tugmasi chiqmaydi; «yo'lda» havolasi mijozga tovar rasmi bilan;
Owner'ga mijoz ko'rgan xabar nusxasi (yoki «bormadi»); rasm + havola birga; qayta yoqilganda takror yuborilmaydi.
Ishga tushirish:  python tests/b4266_yolda_havola.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get va bot._kk_sheet almashtirilgan, saqlash — o'chiq.
Buyurtmalar — soxta (uid 777001, №TB…); real mijozga tegilmaydi.
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
_VAQT = tempfile.mkdtemp(prefix='b4266-')
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
MIJOZ, ADMIN = 777001, bot.ADMIN_ID
JPEG = bytes((0xFF, 0xD8, 0xFF, 0xE0)) + b'0' * 200


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
        return Javob(200, {'ok': True, 'result': {'message_id': 5, 'photo': [{'file_id': 'kichik'}, {'file_id': 'FID_YANGI'}]}})
    if usul == 'getFile':
        return Javob(200, {'ok': True, 'result': {'file_path': 'photos/x.jpg'}})
    return Javob(200, {'ok': True, 'result': {'message_id': 900}})


def _get(url, **kw):
    if url.endswith('photos/x.jpg'):
        return Javob(200, content=JPEG)
    if 'getFile' in url:
        return Javob(200, {'ok': True, 'result': {'file_path': 'photos/x.jpg'}})
    return _post(url, **kw)


bot.req.post = _post
bot.req.get = _get
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: SOTUV.append((uid, b.get('order'))) or True
bot._init_data_user = lambda s: {'id': MIJOZ, 'username': 'sinov_mijoz'}
bot._kk_init_til = lambda s: 'uz'
bot.fetch_elon_by_num = lambda n: (None, None)
bot.time.sleep = lambda s: None
bot._update_yangimi = lambda u: True
bot.check_init_data = lambda s, max_age=86400: int(s) if str(s).isdigit() else None

ELON = {'21': {'num': '21', 'price': '500', 'status': 'active', 'specId': ''},    # telefon
        '22': {'num': '22', 'price': '10', 'status': 'active', 'specId': '', 'soni': 9},   # charger
        '23': {'num': '23', 'price': '20', 'status': 'active', 'specId': '', 'soni': 5},
        '24': {'num': '24', 'price': '30', 'status': 'active', 'specId': '', 'soni': 2}}
bot.elon_cache_get = lambda n: (ELON.get(str(n)), {})
bot.elon_status = lambda e: e.get('status', 'active')
bot._buyurtma_sarlavha = lambda e, m, r=None: 'Tovar ' + e['num']


def _havola(narxlar, qatorlar=(), nums=()):
    return {'ok': True, 'nums': list(nums), 'qatorlar': list(qatorlar), 'narxlar': {k: {'narx': v, 'asl': 100} for k, v in narxlar.items()}}


HAVOLA = {'bonuskod1': _havola({'21': 450, '22': 0}, [{'num': '21', 'rang': '', 'soni': 1}, {'num': '22', 'rang': '', 'soni': 1}]),
          'donakod01': _havola({'22': 0}, [{'num': '22', 'rang': '', 'soni': 1}]),
          'rangkod01': _havola({'23': 15}, [{'num': '23', 'rang': 'Oq', 'soni': 1}, {'num': '23', 'rang': 'Qora', 'soni': 2}]),
          'eskikod01': _havola({}, nums=['21', '22']),
          'kopkod001': _havola({'24': 25}, [{'num': '24', 'rang': '', 'soni': 7}])}
bot._kk_sheet = lambda action, timeout=30, **p: HAVOLA.get(p.get('kod'), {'ok': False, 'msg': 'eskirgan'}) if action == 'savatOl' else {'ok': True}


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


class So:
    def __init__(self, d):
        self.d = d

    async def json(self):
        return self.d


def yozuv(order):
    return next((b for b in bot._mijoz_ol(MIJOZ)['buyurtma'] if b.get('order') == order), None)


def yangi(order, holat='kutilmoqda'):
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(MIJOZ)['buyurtma'].insert(0, {'order': order, 'ts': 1, 'holat': holat, 'tovar': [{'num': '21', 'nom': 'T', 'narx': 500, 'soni': 1}],
                                                       'jami': 500, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000001', 'til': 'uz', 'joy': {}})


def buyurtma(order, nums, savat=None, **extra):
    bot._BUYURTMA_SONI.clear()
    SOROV.clear()
    d = {'initData': str(MIJOZ), 'num': nums[0], 'nums': list(nums), 'order': order, 'name': 'Sinov', 'phone': '+998 90 000 00 01',
         'tur': 'emu', 'manzil': 'Sinov shahri', 'kurs': 12000, **extra}
    if savat:
        d['savat'] = savat
    return asyncio.run(bot.buyurtma_endpoint(So(d))).status


def sorov(usul):
    return [d for u, d, _ in SOROV if u == usul]


def tugma(kl):
    return [t for q in (kl or {}).get('inline_keyboard', []) for t in q]


def holat_cb(kl):
    return [t.get('callback_data') for t in tugma(kl) if str(t.get('callback_data', '')).startswith('bh:')]


def yuborildi_mi(chat, soz):
    return any(str(d.get('chat_id')) == str(chat) and soz in str(d.get('text') or d.get('caption') or '') for d in sorov('sendMessage') + sorov('sendPhoto'))


def yangila(*a, **kw):
    SOROV.clear()
    return asyncio.run(bot.handle_update(*a, **kw))


def fon(update):
    """handle_update + u ochgan fon ishlari tugaguncha (webhook'dagi kabi)."""
    SOROV.clear()

    async def ish():
        await bot.handle_update(update)
        for t in [x for x in asyncio.all_tasks() if x is not asyncio.current_task()]:
            await t
    asyncio.run(ish())


def bosish(data, xabar_id=50, reply=None, matn='Buyurtma №TB01\n\n⏳ To\'lov kutilmoqda\n🕒 Buyurtma: 12:00', rid=1):
    m = {'message_id': xabar_id, 'chat': {'id': ADMIN}, 'text': matn, 'entities': []}
    if reply:
        m['reply_to_message'] = reply
    fon({'update_id': rid, 'callback_query': {'id': 'q', 'from': {'id': ADMIN}, 'data': data, 'message': m}})


def yozish(**m):
    fon({'update_id': 2, 'message': {'message_id': 70, 'chat': {'id': ADMIN}, 'from': {'id': ADMIN}, **m}})


b2 = ['21', '22']


# ── 4266: tovar rasmi (e'lon rasmi) — soxta; «yomon» manzilli rasm Telegram'da ochilmaydi
ELON['21']['rasm'] = ['https://rasm.uz/t21.jpg']
bot.images_of = lambda e: list((e or {}).get('rasm') or [])
bot.belgili = lambda u, *a, **kw: u + '?suv'
_eski_post = bot.req.post


def _post2(url, **kw):
    d = kw.get('json') or kw.get('data') or {}
    if url.endswith('/sendPhoto') and 'yomon' in str(d.get('photo') or ''):
        SOROV.append(('sendPhoto', d, False))
        return Javob(400, {'ok': False, 'description': 'Bad Request: wrong file identifier/HTTP URL specified'})
    j = _eski_post(url, **kw)
    if url.endswith('/sendPhoto') and j._j.get('ok'):   # Telegram javobi — yuborilgan izoh / tugma bilan (nusxa shundan olinadi)
        r = dict(j._j['result'], caption=d.get('caption', ''), reply_markup=d.get('reply_markup'))
        return Javob(200, {'ok': True, 'result': {k: v for k, v in r.items() if v is not None}})
    if url.endswith('/sendMessage') and j._j.get('ok'):
        r = dict(j._j['result'], text=d.get('text', ''), reply_markup=d.get('reply_markup'))
        return Javob(200, {'ok': True, 'result': {k: v for k, v in r.items() if v is not None}})
    return j


bot.req.post = _post2


def mijozga():
    return [d for u, d, _ in SOROV if str(d.get('chat_id')) == str(MIJOZ) and u in ('sendMessage', 'sendPhoto')]


def adminga():
    return [(u, d) for u, d, _ in SOROV if str(d.get('chat_id')) == str(ADMIN) and u in ('sendMessage', 'sendPhoto')]


print('— 1. admin chatiga «📱 Raqamni ulashish» chiqmaydi')
bot.get_konkurs = lambda: {'id': 'K1', 'prize': 'iPhone'}
bot._kk_aktivmi = lambda k: True
bot._kk_korsatsinmi = lambda k, u: True
bot.yetishmagan_kanallar = lambda c: []
bot.user_states.pop(ADMIN, None)
SOROV.clear()
h, _ = asyncio.run(bot.start_konkurs_flow(ADMIN, {'id': ADMIN}))
sm = sorov('sendMessage')
sinov('admin: tugma yo\'q, eski tugma olinadi, holat yo\'q', h == 'ok' and sm and 'request_contact' not in json.dumps(sm)
      and sm[-1].get('reply_markup') == {'remove_keyboard': True} and ADMIN not in bot.user_states, repr(sm)[:300])
sinov('admin: tiklash_holati — raqam so\'ralmaydi', asyncio.run(bot.tiklash_holati(ADMIN, {'id': ADMIN})) is False
      and ADMIN not in bot.user_states)
SOROV.clear()
asyncio.run(bot.start_konkurs_flow(555, {'id': 555}))
sinov('mijoz: tugma joyida (o\'zgarmagan)', 'request_contact' in json.dumps(sorov('sendMessage')) and bot.user_states.get(555, {}).get('step') == 'phone')
bot.user_states.pop(555, None)
SOROV.clear()
bot.eski_klaviatura_olib_tashla(ADMIN, True)
sm = sorov('sendMessage')
sinov('ishga tushganda: jim (bildirishnomasiz) olinadi + o\'chiriladi', sm and sm[0].get('disable_notification') is True
      and sorov('deleteMessage'), repr(SOROV)[:200])

print('— 2. havola → mijozga tovar rasmi bilan, Owner\'ga nusxa')
yangi('TC01', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TC01', matn='Buyurtma №TC01\n\n✅ To\'lov keldi')
yozish(text='https://3.redirect.appmetrica.yandex.com/route?id=S349XU', reply_to_message={'message_id': 900})
mj = mijozga()
sinov('mijozga 1 ta xabar — rasm (suv belgili) + izohda №, yo\'lda, havola + kuzatish tugmasi',
      len(mj) == 1 and mj[0].get('photo') == 'https://rasm.uz/t21.jpg?suv' and '№TC01' in mj[0]['caption']
      and "yo'lga chiqdi" in mj[0]['caption'] and 'appmetrica.yandex.com/route?id=S349XU' in mj[0]['caption']
      and 'Yetkazishni kuzatish' in json.dumps(mj[0].get('reply_markup'), ensure_ascii=False), repr(mj)[:400])
ad = adminga()
sinov('Owner: «✅ mijozga yetdi» + aynan o\'sha rasm, izoh, tugma',
      any(u == 'sendMessage' and 'mijozga yetdi' in d['text'] and d.get('reply_parameters', {}).get('message_id') == 70 for u, d in ad)
      and any(u == 'sendPhoto' and d['photo'] == 'FID_YANGI' and d['caption'] == mj[0]['caption']
              and d.get('reply_markup') == mj[0]['reply_markup'] for u, d in ad), repr(ad)[:500])
sinov('Owner: ⚠️ takror yo\'q', not any('mijozga xabar bormadi' in d.get('text', '') for u, d in ad))
sinov('holat yolda, isbot havola', yozuv('TC01')['holat'] == 'yolda' and yozuv('TC01')['yetkaz']['isbot']['tur'] == 'havola')

print('— 3. rasm ochilmasa — matn bilan (havola baribir yetadi)')
ELON['21']['rasm'] = ['https://rasm.uz/yomon.jpg']
yangi('TC02', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TC02', matn='Buyurtma №TC02')
yozish(text='https://taxi.yandex.uz/route/t2')
mj = [d for d in mijozga() if d.get('text')]
sinov('mijozga matn + havola', len(mj) == 1 and 'taxi.yandex.uz/route/t2' in mj[0]['text'], repr(mijozga())[:300])
sinov('Owner: matn nusxasi', any(u == 'sendMessage' and d.get('text') == mj[0]['text'] for u, d in adminga()), repr(adminga())[:300])
ELON['21']['rasm'] = ['https://rasm.uz/t21.jpg']

print('— 4. mijozga yetmasa — Owner\'ga ochiq «bormadi»')
MIJOZ_BLOK.add(MIJOZ)
yangi('TC03', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TC03', matn='Buyurtma №TC03')
yozish(text='https://taxi.yandex.uz/route/t3')
ad = adminga()
sinov('❌ bormadi + sabab, bitta xabar', len([1 for u, d in ad if 'xabar bormadi' in d.get('text', '')]) == 1
      and any("botni to'xtatgan" in d.get('text', '') for u, d in ad) and not any('mijozga yetdi' in d.get('text', '') for u, d in ad), repr(ad)[:400])
MIJOZ_BLOK.discard(MIJOZ)

print('— 5. chek rasmi + havola BIRGA (izohda)')
yangi('TC04', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TC04', matn='Buyurtma №TC04')
yozish(photo=[{'file_id': 'k'}, {'file_id': 'CHEK_TC04'}], caption='https://taxi.yandex.uz/route/t4')
mj = mijozga()
b = yozuv('TC04')
sinov('mijozga chek rasmi, izohda havola + kuzatish tugmasi', len(mj) == 1 and mj[0]['photo'] == 'CHEK_TC04'
      and 'route/t4' in mj[0]['caption'] and 'route/t4' in json.dumps(mj[0].get('reply_markup')), repr(mj)[:300])
sinov('isbot: rasm + havola', b['yetkaz']['isbot'].get('fid') == 'CHEK_TC04' and b['yetkaz']['isbot'].get('url', '').endswith('/t4'), repr(b.get('yetkaz')))
sinov('Owner: nusxa (rasm + o\'sha izoh)', any(u == 'sendPhoto' and d['caption'] == mj[0]['caption'] for u, d in adminga()), repr(adminga())[:300])

print('— 6. havoladan keyin chek (🧾 Chek) — havola yo\'qolmaydi')
bosish(f'bh:yolda:{MIJOZ}:TC01', matn='Buyurtma №TC01')
yozish(photo=[{'file_id': 'CHEK_TC01'}], reply_to_message={'message_id': 900})
mj = mijozga()
b = yozuv('TC01')
sinov('mijozga chek + oldingi havola', len(mj) == 1 and mj[0].get('photo') == 'CHEK_TC01' and 'S349XU' in mj[0]['caption'], repr(mj)[:300])
sinov('isbot: rasm + eski havola', b['yetkaz']['isbot'].get('fid') == 'CHEK_TC01' and 'S349XU' in b['yetkaz']['isbot'].get('url', ''), repr(b.get('yetkaz')))

print('— 7. qayta yoqilganda: Sheets yuklanmaguncha «♻️ Qayta yuborildi» yo\'q')
ISH = []
bot._buyurtma_xabar_ish = lambda: ISH.append(1) or 0
bot._mijoz_sync_yoqilgan = lambda: True
_sleep = asyncio.sleep


class To(Exception):
    pass


def sikl(n):
    q = [0]

    async def uxla(s):
        q[0] += 1
        if q[0] > n:
            raise To()
    asyncio.sleep = uxla
    try:
        asyncio.run(bot.buyurtma_xabar_loop())
    except To:
        pass
    finally:
        asyncio.sleep = _sleep


bot._MIJOZ_YUKLANDI.clear()
sikl(6)
sinov('Sheets yuklanmagan — yuborish ishi chaqirilmadi', not ISH, repr(ISH))
bot._kk_sheet = lambda action, timeout=30, **p: None
sinov('Sheets javob bermadi — belgi qo\'yilmaydi', bot.mijoz_sheet_yuklash(1) is False and not bot._MIJOZ_YUKLANDI.is_set())
bot._kk_sheet = lambda action, timeout=30, **p: {'ok': True, 'mijozlar': [], 'buyurtmalar': []}
bot._mijoz_sheet_birlash = lambda j: (0, 0)
sinov('Sheets yuklandi — belgi qo\'yildi', bot.mijoz_sheet_yuklash(1) is True and bot._MIJOZ_YUKLANDI.is_set())
sikl(3)
sinov('yuklangandan keyin — odatdagidek ishlaydi', len(ISH) >= 1, repr(ISH))

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
