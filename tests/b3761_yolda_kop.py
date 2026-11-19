# -*- coding: utf-8 -*-
"""tests/b3761_yolda_kop.py — 3761: «🚚 Yo'lda» bir nechta buyurtmada birga, bot qayta yongandan keyin, yo'ldagi buyurtmaga chek,
buyurtma xabarining o'ziga reply, albom, takror bosish.

Ishga tushirish:  python tests/b3761_yolda_kop.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get almashtirilgan, saqlash — o'chiq. Buyurtmalar — soxta (uid 777101…, №TY…).
"""
import asyncio
import atexit
import itertools
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
_VAQT = tempfile.mkdtemp(prefix='b3761-')
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
ADMIN = bot.ADMIN_ID
M1, M2, M3 = 777101, 777102, 777103
MID = itertools.count(1000)
BOTCHA = {'id': 1, 'is_bot': True, 'username': bot.BOT_USERNAME}


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
    SOROV.append((usul, d))
    if usul == 'sendPhoto':
        return Javob(200, {'ok': True, 'result': {'message_id': next(MID), 'photo': [{'file_id': d.get('photo') or 'YANGI'}]}})
    return Javob(200, {'ok': True, 'result': {'message_id': next(MID)}})


bot.req.post = _post
bot.req.get = _post
bot.BOT_TOKEN = 'SINOV:TOKEN'
bot.TG_API = 'https://api.telegram.org/botSINOV:TOKEN'
bot._mijoz_saqlash = lambda: None
bot._mijoz_sync_belgila = lambda *a: None
bot._mijoz_sync_yoqilgan = lambda: False
bot._sotuv_sheet_yoz = lambda uid, b: True
bot.time.sleep = lambda s: None
bot._update_yangimi = lambda u: True


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


def yangi(uid, order, holat='tolandi'):
    with bot._MIJOZ_LOCK:
        bot._mijoz_ochiq(uid)['buyurtma'].insert(0, {
            'order': order, 'ts': 1, 'holat': holat, 'tovar': [{'num': '21', 'nom': 'T', 'narx': 500, 'soni': 1}], 'jami': 500,
            'tur': 'emu', 'ism': 'S', 'tel': '+998900000001', 'til': 'uz', 'joy': {},
            'admin_xb': [{'m': 50 + uid % 100, 't': f"Buyurtma №{order}\n\n⏳ To'lov kutilmoqda", 'e': []}]})


def yozuv(uid, order):
    return next((b for b in bot._mijoz_ol(uid)['buyurtma'] if b.get('order') == order), None)


def sorov(usul):
    return [d for u, d in SOROV if u == usul]


def mijozga(uid):
    return [d for d in sorov('sendMessage') + sorov('sendPhoto') if str(d.get('chat_id')) == str(uid)]


def fon(update, tozala=True):
    if tozala:
        SOROV.clear()

    async def ish():
        await bot.handle_update(update)
        for t in [x for x in asyncio.all_tasks() if x is not asyncio.current_task()]:
            await t
    asyncio.run(ish())


RID = itertools.count(1)


def bosish(uid, order, holat_matn="⏳ To'lov kutilmoqda", cb=None):
    xid = 50 + uid % 100
    m = {'message_id': xid, 'chat': {'id': ADMIN}, 'from': BOTCHA, 'text': f'Buyurtma №{order}\n\n{holat_matn}', 'entities': []}
    fon({'update_id': next(RID), 'callback_query': {'id': 'q', 'from': {'id': ADMIN}, 'data': cb or f'bh:yolda:{uid}:{order}',
                                                    'message': m}})
    s = [d for d in sorov('sendMessage') if d.get('chat_id') == ADMIN and 'reply_parameters' in d]
    return s[-1] if s else None


def soroq_xabar(s, uid, order):
    """Telegram reply_to_message ichida keladigan savol xabari (tugmalari bilan)."""
    return {'message_id': SAVOL_ID[order], 'from': BOTCHA, 'chat': {'id': ADMIN}, 'text': s['text'],
            'reply_markup': s['reply_markup']}


def yozish(tozala=True, **m):
    fon({'update_id': next(RID), 'message': {'message_id': next(MID), 'chat': {'id': ADMIN, 'type': 'private'},
                                             'from': {'id': ADMIN}, **m}}, tozala)


SAVOL_ID = {}


def savol_id_ol():
    # oxirgi sendMessage javobi id'si = MID dan oldingi qiymat; kutish yozuvidan olamiz (aniqroq)
    return {k['order']: s for (c, s), k in bot._YOLDA_KUT.items()}


print("— 3 buyurtma ketma-ket «Yo'lda», chek — har biri o'z savoliga reply")
for u, o in ((M1, 'TY01'), (M2, 'TY02'), (M3, 'TY03')):
    yangi(u, o)
S = {}
for u, o in ((M1, 'TY01'), (M2, 'TY02'), (M3, 'TY03')):
    S[o] = bosish(u, o)
SAVOL_ID.update(savol_id_ol())
sinov('3 savol, 3 kutish', all(S.values()) and set(SAVOL_ID) == {'TY01', 'TY02', 'TY03'}, repr(SAVOL_ID))
sinov('holatlar hali surilmagan', all(yozuv(u, o)['holat'] == 'tolandi' for u, o in ((M1, 'TY01'), (M2, 'TY02'), (M3, 'TY03'))))
yozish(photo=[{'file_id': 'CHEK1'}], reply_to_message=soroq_xabar(S['TY01'], M1, 'TY01'))
yozish(photo=[{'file_id': 'CHEK2'}], reply_to_message=soroq_xabar(S['TY02'], M2, 'TY02'))
yozish(text='https://taxi.yandex.uz/route/t3')   # reply'siz — eng oxirgi savol (TY03)
for u, o, f in ((M1, 'TY01', 'CHEK1'), (M2, 'TY02', 'CHEK2')):
    b = yozuv(u, o)
    sinov(f'№{o}: yolda, isbot = o\'z cheki', b['holat'] == 'yolda' and b['yetkaz']['isbot'].get('fid') == f, repr(b.get('yetkaz')))
b = yozuv(M3, 'TY03')
sinov('№TY03: reply\'siz havola — oxirgi savolga', b['holat'] == 'yolda' and b['yetkaz']['isbot'].get('url', '').endswith('/t3'), repr(b.get('yetkaz')))
sinov('kutishlar yopildi', not bot._YOLDA_KUT, repr(bot._YOLDA_KUT))

print('— har mijozga faqat o\'z cheki, bir martadan')
SOROV.clear()
yangi(M1, 'TY04')
s4 = bosish(M1, 'TY04')
SAVOL_ID.update(savol_id_ol())
yozish(photo=[{'file_id': 'CHEK4'}], reply_to_message=soroq_xabar(s4, M1, 'TY04'))
sinov('mijozga 1 ta rasm', len([d for d in mijozga(M1) if d.get('photo') == 'CHEK4']) == 1, repr(SOROV)[:300])
yozish(photo=[{'file_id': 'CHEK4B'}], reply_to_message=dict(soroq_xabar(s4, M1, 'TY04'), reply_markup={}))
sinov('yopilgan savolga yana rasm — mijozga bormaydi', not mijozga(M1), repr(SOROV)[:300])

print('— takror bosish: bitta kutish')
yangi(M2, 'TY05')
bosish(M2, 'TY05')
bosish(M2, 'TY05')
sinov('TY05 — bitta kutish', sum(1 for k in bot._YOLDA_KUT.values() if k['order'] == 'TY05') == 1, repr(bot._YOLDA_KUT))
SAVOL_ID.update(savol_id_ol())

print('— bot qayta yondi (xotira bo\'sh) — savolga reply baribir ishlaydi')
s5 = [d for d in sorov('sendMessage') if 'reply_parameters' in d][-1]
bot._YOLDA_KUT.clear()
yozish(photo=[{'file_id': 'CHEK5'}], reply_to_message=soroq_xabar(s5, M2, 'TY05'))
b = yozuv(M2, 'TY05')
sinov('TY05: yolda, chek', b['holat'] == 'yolda' and b['yetkaz']['isbot'].get('fid') == 'CHEK5', repr(b.get('yetkaz')))
sinov('mijozga chek bordi', any(d.get('photo') == 'CHEK5' for d in mijozga(M2)), repr(SOROV)[:300])
sinov('buyurtma xabari yozuvdan yangilandi', any(d.get('message_id') == 50 + M2 % 100 for d in sorov('editMessageText') + sorov('editMessageReplyMarkup')), repr(SOROV)[:400])
yozish(photo=[{'file_id': 'BEGONA'}], reply_to_message={'message_id': 1, 'from': {'id': 5, 'is_bot': False}, 'text': 'x'})
sinov('begona xabarga reply — isbot emas', not any(d.get('photo') == 'BEGONA' for d in mijozga(M2)), repr(SOROV)[:300])

print("— yo'ldagi buyurtmaga chek (Owner holati)")
kl = bot._buyurtma_klava(M3, 'TY03', 'yolda', ['21'], yozuv(M3, 'TY03'))
sinov('yolda tugmalari: 📦 + 🧾', [t.get('callback_data') for q in kl['inline_keyboard'] for t in q][:2] == [f'bh:yetkazildi:{M3}:TY03', f'bh:yolda:{M3}:TY03'], repr(kl))
s3 = bosish(M3, 'TY03', "🚚 Yo'lda")
sinov('savol chiqdi (chek so\'raladi)', s3 and '🧾' in s3['text'], repr(SOROV)[:300])
SAVOL_ID.update(savol_id_ol())
yozish(photo=[{'file_id': 'CHEK3'}], reply_to_message=soroq_xabar(s3, M3, 'TY03'))
b = yozuv(M3, 'TY03')
sinov('isbot almashdi, holat yolda', b['holat'] == 'yolda' and b['yetkaz']['isbot'].get('fid') == 'CHEK3', repr(b.get('yetkaz')))
sinov('mijozga chek 1 marta', len([d for d in mijozga(M3) if d.get('photo') == 'CHEK3']) == 1, repr(SOROV)[:300])

print('— eski buyurtma xabarining o\'ziga chek reply')
yangi(M1, 'TY06', 'yolda')
asl = {'message_id': 77, 'from': BOTCHA, 'chat': {'id': ADMIN}, 'text': "Buyurtma №TY06\n\n🚚 Yo'lda", 'entities': [],
       'reply_markup': {'inline_keyboard': [[{'text': '📦 Yetkazildi', 'callback_data': f'bh:yetkazildi:{M1}:TY06'}]]}}
yozish(photo=[{'file_id': 'CHEK6'}], reply_to_message=asl)
b = yozuv(M1, 'TY06')
sinov('reply — isbot yozildi, mijozga bordi', b['yetkaz']['isbot'].get('fid') == 'CHEK6' and any(d.get('photo') == 'CHEK6' for d in mijozga(M1)), repr(SOROV)[:300])
yozish(text='rahmat', reply_to_message=asl)
sinov('buyurtma xabariga oddiy matn — isbot emas', not mijozga(M1), repr(SOROV)[:300])
yangi(M1, 'TY07', 'yetkazildi')
asl7 = dict(asl, reply_markup={'inline_keyboard': [[{'text': 'x', 'callback_data': f'bh:yopildi:{M1}:TY07'}]]})
yozish(photo=[{'file_id': 'CHEK7'}], reply_to_message=asl7)
sinov('yetkazilganga chek — yozilmaydi, mijozga bormaydi', not (yozuv(M1, 'TY07').get('yetkaz') or {}).get('isbot') and not mijozga(M1), repr(SOROV)[:300])

print('— albom savolga reply: 1-rasm olinadi, qolgani yutiladi')
yangi(M2, 'TY08')
s8 = bosish(M2, 'TY08')
SAVOL_ID.update(savol_id_ol())
SOROV.clear()
for i, f in enumerate(('A1', 'A2', 'A3')):
    yozish(False, photo=[{'file_id': f}], media_group_id='G1', reply_to_message=soroq_xabar(s8, M2, 'TY08'))
sinov('mijozga faqat 1-rasm', [d.get('photo') for d in mijozga(M2)] == ['A1'], repr(SOROV)[:400])
sinov('albom qoldig\'i e\'lon bo\'lmadi (adminga e\'lon savoli yo\'q)', not [d for d in sorov('sendMessage') if d.get('chat_id') == ADMIN and "e'lon" in str(d.get('text', '')).lower()], repr(SOROV)[:400])
sinov('reply\'siz albom — isbot emas', bot._yolda_javobmi(ADMIN, {'photo': [{'file_id': 'x'}], 'media_group_id': 'G2'}, '') is None)

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
