# -*- coding: utf-8 -*-
"""tests/b3301_bosqich.py — 3301: bosqichma-bosqich tugmalar, «🚚 Yo'lda» + isbot, havola tarkibi (havoladagicha yoziladi).

Ishga tushirish:  python tests/b3301_bosqich.py   (repo ildizidan)

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
_VAQT = tempfile.mkdtemp(prefix='b3301-')
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


print('— tugmalar: faqat keyingi bosqich')
b2 = ['21', '22']
kl = bot._buyurtma_klava(MIJOZ, 'TB00', 'kutilmoqda', b2)
sinov("kutilmoqda: ✅ To'lov keldi + «to'lovni kutmay»", holat_cb(kl) == [f'bh:tolandi:{MIJOZ}:TB00', f'bh:yolda:{MIJOZ}:TB00'], repr(kl))
sinov('kutilmoqda: bron tugmalari bor', sum(t.get('callback_data', '').startswith('bron_och:') for t in tugma(kl)) == 2, repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TB00', 'tolandi', b2)
sinov("to'landi: faqat 🚚 Yo'lda, bron tugmasi yo'q (3304)", holat_cb(kl) == [f'bh:yolda:{MIJOZ}:TB00'] and 'bron_och' not in json.dumps(kl), repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TB00', 'yolda', b2)
sinov("yo'lda: faqat 📦 Yetkazildi, bron tugmasi yo'q (3304)", holat_cb(kl) == [f'bh:yetkazildi:{MIJOZ}:TB00'] and 'bron_och' not in json.dumps(kl), repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TB00', 'yetkazildi', b2)
sinov('yetkazildi: «🔒 Yopish (baho kutmasdan)», bron yo\'q', [t['text'] for t in tugma(kl) if 'callback_data' in t] == ['🔒 Yopish (baho kutmasdan)'], repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TB00', 'yopildi', b2)
sinov('yopildi: faqat «Mijozga yozish»', len(tugma(kl)) == 1 and 'url' in tugma(kl)[0], repr(kl))
kl = bot._buyurtma_klava(MIJOZ, 'TB00', 'bekor', b2)
sinov('bekor: holat 📍 (bosqich tugmasi yo\'q)', not holat_cb(kl) or holat_cb(kl) == ['bh:-'], repr(kl))
sinov('✔️ tugma yo\'q (bajarilgani — matnda)', not any('✔️' in t['text'] for h in bot._HOLAT_TARTIB for t in tugma(bot._buyurtma_klava(MIJOZ, 'TB00', h, b2))))
uzun = f'bhy:skip:{10**12}:ABCDEFGHIJKL'
sinov('callback_data ≤ 64 bayt', len(uzun.encode()) <= 64 and len(f'bh:yetkazildi:{10**12}:ABCDEFGHIJKL'.encode()) <= 64)
sinov('holat qatori: Yopildi nomi o\'zgarmagan', bot._HOLAT_QATOR['yopildi'][1] == 'Yopildi' if 'yopildi' in bot._HOLAT_QATOR else True)

print('— havola tarkibi: _savat_kel_narxlar')
k, o = bot._savat_kel_narxlar(['bonuskod1'])
sinov('tarkib va narx hamma tovarga', k['_tarkib'] == {'21': [('', 1)], '22': [('', 1)]} and k['21'] == 450 and k['22'] == 0 and o is False, repr(k))
k, o = bot._savat_kel_narxlar(['eskikod01'])
sinov('BUGUN275 havolasi (qatorsiz) — har tovar 1 ta', k['_tarkib'] == {'21': [('', 1)], '22': [('', 1)]}, repr(k))
k, o = bot._savat_kel_narxlar(['yoqkod001'])
sinov('o\'qilmadi — ogoh, tarkib yo\'q', o is True and '_tarkib' not in k, repr(k))

print('— havola tarkibi: _havola_tenglash')
k, _ = bot._savat_kel_narxlar(['donakod01'])
n, q, s, r = bot._havola_tenglash('22', [], {'22': 3}, {}, k)
sinov('dona 3 → 1', (n, q, s['22']) == ('22', [], 1) and any('3 → 1' in x for x in k['_farq']), repr((s, k)))
k, _ = bot._savat_kel_narxlar(['bonuskod1'])
n, q, s, r = bot._havola_tenglash('22', [], {}, {}, k)
sinov('telefon olib tashlangan — qaytariladi', [n] + q == ['22', '21'] and any('№21 qaytarildi' in x for x in k['_farq']), repr((n, q, k)))
k, _ = bot._savat_kel_narxlar(['bonuskod1'])
n, q, s, r = bot._havola_tenglash('21', ['22'], {}, {}, k)
sinov('havoladagicha — farq yo\'q', [n] + q == ['21', '22'] and '_farq' not in k, repr(k))
k, _ = bot._savat_kel_narxlar(['donakod01'])
n, q, s, r = bot._havola_tenglash('22', ['21'], {}, {}, k)
sinov('havolada yo\'q tovar — qoladi, ogohlantiriladi', [n] + q == ['22', '21'] and any('№21 havolada yo\'q' in x for x in k['_farq']), repr((q, k)))
k, _ = bot._savat_kel_narxlar(['rangkod01'])
n, q, s, r = bot._havola_tenglash('23', [], {'23': 1}, {'23': [('Oq', 1)]}, k)
sinov('rang va dona havoladagi', s['23'] == 3 and r['23'] == [('Oq', 1), ('Qora', 2)] and k.get('_farq'), repr((s, r, k)))
k, _ = bot._savat_kel_narxlar(['rangkod01'])
bot._havola_tenglash('23', [], {'23': 3}, {'23': [('Qora', 2), ('Oq', 1)]}, k)
sinov('rang tartibi boshqa — farq emas', '_farq' not in k, repr(k))
k, _ = bot._savat_kel_narxlar(['kopkod001'])
n, q, s, r = bot._havola_tenglash('24', [], {'24': 7}, {}, k)
sinov('ombor kamaygan (7 → 2) — yolg\'on farq yo\'q', '_farq' not in k and s['24'] == 7, repr(k))
k = {'21': 10}
sinov('tarkib yo\'q — o\'zgarmaydi', bot._havola_tenglash('21', ['22'], {'21': 2}, {}, k) == ('21', ['22'], {'21': 2}, {}) and '_farq' not in k)

print('— buyurtma: havoladagicha yoziladi')
st = buyurtma('TB10', ['22'], ['donakod01'], sonlar={'22': 3})
b = yozuv('TB10')
adm = next(d for d in sorov('sendMessage') if d.get('chat_id') == ADMIN)
sinov('sovg\'a: 3 so\'radi → 1 dona, jami 0, to\'landi', st == 200 and b['tovar'][0]['soni'] == 1 and b['jami'] == 0 and b['holat'] == 'tolandi', repr(b)[:300])
sinov('adminga ⚠️ «havoladagicha yozildi»', 'havoladagicha yozildi' in adm['text'] and '3 → 1' in adm['text'], adm['text'])
st = buyurtma('TB11', ['22'], ['bonuskod1'])
b = yozuv('TB11')
sinov('bonus: telefonsiz yubordi → telefon narxi bilan to\'plam', {x['num'] for x in b['tovar']} == {'21', '22'} and b['jami'] == 450 and b['holat'] == 'kutilmoqda', repr(b)[:300])
sinov('to\'plam tugamagan: «to\'lov kerak emas» yo\'q', not yuborildi_mi(MIJOZ, "to'lov kerak emas"), repr(SOROV)[:300])
st = buyurtma('TB12', ['21', '22'], ['soxtakod1'], sonlar={'22': 3})
b = yozuv('TB12')
sinov('havola o\'qilmadi — mijoz yuborgani, ogoh (zaxira)', next(x for x in b['tovar'] if x['num'] == '22')['soni'] == 3 and b['holat'] == 'kutilmoqda'
      and yuborildi_mi(ADMIN, "havola o'qilmadi"), repr(b)[:300])
st = buyurtma('TB13', ['22'], sonlar={'22': 3})
sinov('havolasiz buyurtma — eskicha', yozuv('TB13')['tovar'][0]['soni'] == 3 and not yuborildi_mi(ADMIN, 'havoladagicha'), repr(yozuv('TB13'))[:300])

print('— sayt zaxirasi ham havoladagicha')
bot._buyurtma_zaxira_birlash({'buyurtma': [{'user_id': MIJOZ, 'order': 'TB14', 'ts': 1, 'jami': 0, 'tur': 'emu', 'ism': 'S', 'tel': '+998900000001',
                                            'tovar': [{'num': '22', 'nom': 'T', 'narx': 0, 'soni': 3}], 'joy': {'manzil': 'x', 'savat': ['bonuskod1']}}]})
SOROV.clear()
bot._buyurtma_xabar_ish()
b = yozuv('TB14')
sinov('zaxira: telefon qaytdi, charger 1 ta, jami 450', {x['num']: x['soni'] for x in b['tovar']} == {'21': 1, '22': 1} and b['jami'] == 450 and b['holat'] == 'kutilmoqda', repr(b)[:300])

print("— «🚚 Yo'lda»: isbot so'raladi")
yangi('TB01', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TB01')
sorq = sorov('sendMessage')
sinov('holat surilmadi', yozuv('TB01')['holat'] == 'tolandi', repr(yozuv('TB01')))
sinov('savol: 🚕 / 🧾 + O\'tkazib yuborish + buyurtmaga reply', len(sorq) == 1 and '🚕 taksi havolasi' in sorq[0]['text'] and '🧾 BTS cheki' in sorq[0]['text']
      and sorq[0]['reply_parameters']['message_id'] == 50 and "O'tkazib yuborish" in json.dumps(sorq[0]['reply_markup'], ensure_ascii=False), repr(sorq))
sinov('mijozga hali hech narsa', not yuborildi_mi(MIJOZ, ''), repr(SOROV))
k = bot._yolda_kut_ol(ADMIN)
sinov('kutish yozildi', k and k['order'] == 'TB01' and k['soroq'] == 900, repr(k))
sinov('buyruq — isbot emas', bot._yolda_javobmi(ADMIN, {'text': '/stat'}, '/stat') is None)
sinov('albom — isbot emas', bot._yolda_javobmi(ADMIN, {'photo': [{'file_id': 'x'}], 'media_group_id': '9'}, '') is None)
sinov('boshqa xabarga reply — isbot emas', bot._yolda_javobmi(ADMIN, {'text': 'https://a.uz', 'reply_to_message': {'message_id': 1}}, 'https://a.uz') is None)
sinov('savolga reply — isbot', bot._yolda_javobmi(ADMIN, {'text': 'https://a.uz', 'reply_to_message': {'message_id': 900}}, 'https://a.uz') is k)
sinov('oddiy xabar — javob', bot._yolda_javobmi(ADMIN, {'text': 'https://a.uz'}, 'https://a.uz') is k)
k['t'] -= bot._YOLDA_KUT_S + 1
sinov('10 daqiqa o\'tdi — kutish tugadi', bot._yolda_kut_ol(ADMIN) is None and not bot._YOLDA_KUT)

print('— havola')
bosish(f'bh:yolda:{MIJOZ}:TB01')
yozish(text='Taksi: https://taxi.yandex.uz/route/abc123.')
b = yozuv('TB01')
sinov('holat yolda, isbot havola', b['holat'] == 'yolda' and b['yetkaz']['isbot']['tur'] == 'havola' and b['yetkaz']['isbot']['url'] == 'https://taxi.yandex.uz/route/abc123', repr(b.get('yetkaz')))
mj = [d for d in sorov('sendMessage') if d.get('chat_id') == MIJOZ]
sinov('mijozga «yo\'lga chiqdi» + taksi tugmasi', len(mj) == 1 and 'taxi.yandex.uz' in json.dumps(mj[0]), repr(mj))
ed = sorov('editMessageText')
sinov('buyurtma xabari: bosilgani matnda (BUGUN295), 📦 Yetkazildi', any(d['message_id'] == 50 and "Yo'lda" in d['text'] and 'bh:yetkazildi' in json.dumps(d.get('reply_markup')) for d in ed), repr(ed)[:400])
sinov('savol tugmalari yopildi', any(d['message_id'] == 900 and 'reply_markup' not in d for d in ed), repr(ed)[:400])
sinov('Store sotuv yozuvi', (MIJOZ, 'TB01') in SOTUV, repr(SOTUV))
sinov('kutish yopildi', bot._yolda_kut_ol(ADMIN) is None)

print('— rasm')
yangi('TB02', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TB02')
yozish(photo=[{'file_id': 'kichikF'}, {'file_id': 'CHEK_FID'}])
b = yozuv('TB02')
ph = [d for d in sorov('sendPhoto')]
sinov('file_id mijozga sendPhoto', len(ph) == 1 and ph[0]['chat_id'] == MIJOZ and ph[0]['photo'] == 'CHEK_FID', repr(ph))
sinov('isbot: rasm, fid', b['holat'] == 'yolda' and b['yetkaz']['isbot']['tur'] == 'rasm' and b['yetkaz']['isbot']['fid'] == 'CHEK_FID', repr(b.get('yetkaz')))
sinov('mijozga ⚠️ yo\'q', not yuborildi_mi(ADMIN, 'mijozga xabar bormadi'), repr(SOROV)[:300])

print('— rasm-fayl (document)')
yangi('TB03', 'kutilmoqda')
bosish(f'bh:yolda:{MIJOZ}:TB03')
yozish(document={'file_id': 'DOC_FID', 'mime_type': 'image/jpeg'})
b = yozuv('TB03')
sinov('baytlar yuklandi, yangi file_id', any(u == 'sendPhoto' and f for u, d, f in SOROV) and b['yetkaz']['isbot']['fid'] == 'FID_YANGI', repr(b.get('yetkaz')))
sinov("to'lovni kutmay — kutilmoqda dan yo'lda", b['holat'] == 'yolda', repr(b))

print("— isbot emas — qayta so'raladi")
yangi('TB04', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TB04')
yozish(text='keyinroq')
sinov('matn — qayta so\'raladi, kutish turadi', yuborildi_mi(ADMIN, 'taksi havolasi') and yozuv('TB04')['holat'] == 'tolandi' and bot._yolda_kut_ol(ADMIN), repr(SOROV)[:300])
yozish(document={'file_id': 'PDF', 'mime_type': 'application/pdf'})
sinov('PDF — qayta so\'raladi', yuborildi_mi(ADMIN, 'taksi havolasi') and yozuv('TB04')['holat'] == 'tolandi', repr(SOROV)[:300])

print("— O'tkazib yuborish / Bekor")
asl = {'message_id': 50, 'text': "№TB04\n\n⏳ To'lov kutilmoqda\n🕒 Buyurtma: 12:00", 'entities': []}
bosish(f'bhy:yoq:{MIJOZ}:TB04', 900)
sinov('Bekor — holat o\'zgarmadi, kutish yopildi', yozuv('TB04')['holat'] == 'tolandi' and bot._yolda_kut_ol(ADMIN) is None and not yuborildi_mi(MIJOZ, ''), repr(SOROV)[:300])
bosish(f'bh:yolda:{MIJOZ}:TB04')
bosish(f'bhy:skip:{MIJOZ}:TB04', 900, reply=asl)
b = yozuv('TB04')
sinov('skip — yolda, isbotsiz', b['holat'] == 'yolda' and not (b.get('yetkaz') or {}).get('isbot'), repr(b))
sinov('skip — mijozga oddiy xabar', yuborildi_mi(MIJOZ, 'chiqdi') or len([d for d in sorov('sendMessage') if d.get('chat_id') == MIJOZ]) == 1, repr(SOROV)[:300])
sinov('skip — asl xabar yangilandi', any(d.get('message_id') == 50 for d in sorov('editMessageText') + sorov('editMessageReplyMarkup')), repr(SOROV)[:300])
yangi('TB05', 'tolandi')
bot._YOLDA_KUT.clear()
bosish(f'bhy:skip:{MIJOZ}:TB05', 900, reply=asl)
sinov('bot qayta yongan (kutish yo\'q) — skip baribir ishlaydi', yozuv('TB05')['holat'] == 'yolda', repr(yozuv('TB05')))

print('— mijozga yetmasa')
MIJOZ_BLOK.add(MIJOZ)
yangi('TB06', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TB06')
yozish(text='https://taxi.yandex.uz/x')
sinov('havola: ⚠️ adminga, holat saqlandi', yozuv('TB06')['holat'] == 'yolda' and yuborildi_mi(ADMIN, 'mijozga xabar bormadi'), repr(SOROV)[:300])
yangi('TB07', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TB07')
yozish(photo=[{'file_id': 'CHEK2'}])
b = yozuv('TB07')
sinov('rasm: ⚠️ adminga, isbot yozildi', b['holat'] == 'yolda' and b['yetkaz']['isbot']['fid'] == 'CHEK2' and yuborildi_mi(ADMIN, 'mijozga xabar bormadi'), repr(b.get('yetkaz')))
MIJOZ_BLOK.clear()

print('— holat o\'zgargan')
yangi('TB08', 'tolandi')
bosish(f'bh:yolda:{MIJOZ}:TB08')
with bot._MIJOZ_LOCK:
    yozuv('TB08')['holat'] = 'bekor'
yozish(text='https://taxi.yandex.uz/y')
sinov('mijoz bekor qilgan — isbot yozilmaydi, xabar ketmaydi', yozuv('TB08')['holat'] == 'bekor' and not yuborildi_mi(MIJOZ, '') and not (yozuv('TB08').get('yetkaz') or {}).get('isbot'), repr(SOROV)[:300])
yangi('TB09', 'bekor')
bosish(f'bh:yolda:{MIJOZ}:TB09')
sinov('bekor buyurtma — savol chiqmaydi', not bot._YOLDA_KUT and yuborildi_mi(ADMIN, 'bekor qilgan'), repr(SOROV)[:300])
yangi('TB15', 'yetkazildi')
bosish(f'bh:yolda:{MIJOZ}:TB15')
sinov('allaqachon yetkazilgan — savol yo\'q, holat turadi', not bot._YOLDA_KUT and yozuv('TB15')['holat'] == 'yetkazildi', repr(SOROV)[:300])

print('— begona')
yangi('TB16', 'tolandi')
fon({'update_id': 3, 'callback_query': {'id': 'q', 'from': {'id': 555}, 'data': f'bhy:skip:{MIJOZ}:TB16',
                                        'message': {'message_id': 50, 'chat': {'id': 555}}}})
sinov('admin emas — bhy ishlamaydi', yozuv('TB16')['holat'] == 'tolandi')

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
