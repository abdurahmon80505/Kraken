# -*- coding: utf-8 -*-
"""tests/b3248_nt_sotuvda.py — 3248: Nuqta tech kanali YANGI posti → adminga «🛒 Sotuvda» taklifi; ✅ — post tagiga URL tugma.

Ishga tushirish:  python tests/b3248_nt_sotuvda.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: bot.req.post / get — yozib oluvchi soxtalar. Kanal va post id'lari soxta; real kanalga tegilmaydi.
Holatlar: model bor (taklif), model yo'q (xabar yo'q), yangilik matni (avtomatik tugma YO'Q), ✅ / ✖, huquq yo'q, eski / boshqa post.
"""
import asyncio
import json
import logging
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL', 'ADMIN_GURUH', 'SHEET_URL', 'TECH_KANAL_ID'):
    os.environ.pop(k, None)

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
KANAL = -1009999000001          # soxta «Nuqta tech» kanali
JAVOB = {'edit': {'ok': True, 'result': True}, 'member': {'ok': True, 'result': {'status': 'administrator', 'can_edit_messages': True}}}


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


class Javob:
    def __init__(self, j):
        self._j = j

    def json(self):
        return self._j


def _post(url, json=None, timeout=None, **kw):
    usul = url.rsplit('/', 1)[-1]
    SOROV.append((usul, json or {}))
    if usul == 'editMessageReplyMarkup' and (json or {}).get('chat_id') == KANAL:
        return Javob(JAVOB['edit'])
    return Javob({'ok': True, 'result': {'message_id': 700}})


def _get(url, params=None, timeout=None, **kw):
    usul = url.rsplit('/', 1)[-1]
    SOROV.append((usul, params or {}))
    return Javob(JAVOB['member'] if usul == 'getChatMember' else {'ok': False})


bot.req.post = _post
bot.req.get = _get
bot.BOT_TOKEN = '123456:SINOV'
bot.TG_API = 'https://api.telegram.org/bot123456:SINOV'
bot.GURUH = {'id': -1001234567890, 'post': 12}
bot._update_yangimi = lambda u: True

bot._ELON_CACHE['series'] = [{'key': 'p10s', 'type': 'phone'}, {'key': 'zaryad', 'type': 'accessory'}]
bot._ELON_CACHE['models'] = {
    'p10p': {'id': 'p10p', 'series': 'p10s', 'nameUz': 'Google Pixel 10 Pro', 'nameRu': 'Google Pixel 10 Pro'},
    'p10x': {'id': 'p10x', 'series': 'p10s', 'nameUz': 'Google Pixel 10 Pro XL'},
    'p10': {'id': 'p10', 'series': 'p10s', 'nameUz': 'Google Pixel 10'},
    'p11': {'id': 'p11', 'series': 'p10s', 'nameUz': 'Google Pixel 11'},
    'nano': {'id': 'nano', 'series': 'zaryad', 'nameUz': 'Nano'},
}
bot._ELON_CACHE['by_num'] = {
    '1': {'num': 1, 'specId': 'p10p', 'status': 'active'},
    '2': {'num': 2, 'specId': 'p10p', 'status': 'active'},
    '3': {'num': 3, 'specId': 'p10p', 'status': 'sold'},
    '4': {'num': 4, 'specId': 'p10', 'status': 'active'},
    '5': {'num': 5, 'specId': 'nano', 'status': 'active'},
    '6': {'num': 6, 'specId': 'p11', 'status': 'deleted'},
}
bot._ELON_CACHE['time'] = 1.0
bot.elon_status = lambda e: e.get('status', 'active')


def post(matn, pid=501, chat=None, eski=False, caption=False, markup=None):
    p = {'message_id': pid, 'date': int(time.time()) - (3 * 86400 if eski else 10),
         'chat': chat or {'id': KANAL, 'type': 'channel', 'username': 'nuqta_tech', 'title': 'Nuqta tech'},
         ('caption' if caption else 'text'): matn}
    if markup:
        p['reply_markup'] = markup
    return p


def yangila(update):
    SOROV.clear()

    async def ish():
        await bot.handle_update(update)
        for t in [x for x in asyncio.all_tasks() if x is not asyncio.current_task()]:
            await t
    asyncio.run(ish())


def takliflar():
    return [d for u, d in SOROV if u == 'sendMessage' and 'Nuqta tech posti' in str(d.get('text'))]


def kanal_tahrir():
    return [d for u, d in SOROV if u == 'editMessageReplyMarkup' and d.get('chat_id') == KANAL]


def bos(data, kim=ADMIN):
    yangila({'update_id': 9, 'callback_query': {'id': 'q', 'from': {'id': kim}, 'data': data,
                                                'message': {'message_id': 77, 'chat': {'id': bot.GURUH['id']},
                                                            'message_thread_id': 12}}})


print('— model topish (taxminiy moslik)')
top = bot.nt_model_top
sinov('«Pixel 10 Pro» — p10p, 2 ta (sotilgani hisoblanmaydi)', top('Yangi Pixel 10 Pro keldi!') == ('p10p', 'Google Pixel 10 Pro', 2), top('Yangi Pixel 10 Pro keldi!'))
sinov('brend bilan, katta harf: «GOOGLE PIXEL 10 PRO»', (top('GOOGLE PIXEL 10 PRO sharhi') or ('',))[0] == 'p10p')
sinov('qator ko\'chishi orasida: «Pixel\\n10 Pro»', (top('Pixel\n10   Pro') or ('',))[0] == 'p10p')
sinov('«Pixel 10 Pro XL» — p10x (sotuvda yo\'q) → None, «Pixel 10 Pro» deb olinmaydi', top('Pixel 10 Pro XL — kamera testi') is None)
sinov('«Pixel 10» — p10 (1 ta)', top('Pixel 10 ning batareyasi') == ('p10', 'Google Pixel 10', 1))
sinov('so\'z ichida emas: «Pixel 100»', top('Pixel 100 haqida mish-mish') is None)
sinov('bir so\'zli nom («Nano») — hisoblanmaydi', top('Nano texnologiya haqida') is None)
sinov('o\'chirilgan e\'lon modeli («Pixel 11») — None', top('Google Pixel 11 taqdim etildi') is None)
sinov('bir nechta model — matnda birinchisi', (top('Pixel 10 va Pixel 10 Pro solishtiruvi') or ('',))[0] == 'p10')
sinov('bo\'sh matn — None', top('') is None and top(None) is None)

print('— URL va tugma')
u = bot.nt_sotuvda_url('p10p')
sinov('URL: Store Mini App, model filtri + src=nt', u == f'https://t.me/{bot.BOT_USERNAME}?startapp=m_p10p__src_nt', u)
sinov('startapp ≤ 64 belgi, faqat ruxsat etilgan belgilar', len(u.split('startapp=')[1]) <= 64)
sinov('xavfli id — None', bot.nt_sotuvda_url('a b') is None and bot.nt_sotuvda_url('x/y') is None and bot.nt_sotuvda_url('') is None)
t = bot.nt_tugma('p10p', 'Google Pixel 10 Pro', 2)
sinov('tugma matni: «🛒 Sotuvda — <model> (N ta)» + ruscha', t['text'] == '🛒 Sotuvda — Google Pixel 10 Pro (2 ta) / В продаже (2 шт.)', t)

print('— 1) model bor: adminga taklif, kanal posti tegilmaydi')
yangila({'update_id': 1, 'channel_post': post('🔥 Google Pixel 10 Pro — yangi partiya')})
tk = takliflar()
sinov('📢 Postlar mavzusiga bitta xabar', len(tk) == 1 and tk[0]['chat_id'] == bot.GURUH['id'], repr(SOROV)[:300])
sinov('matn: «Nuqta tech posti: <model> — tagiga "🛒 Sotuvda (N ta)" tugmasini qo\'shaymi?»',
      tk and 'Nuqta tech posti: <b>Google Pixel 10 Pro</b> — tagiga "🛒 Sotuvda (2 ta)" tugmasini qo\'shaymi?' in tk[0]['text'], tk and tk[0]['text'])
kb = tk[0]['reply_markup']['inline_keyboard'] if tk else []
sinov('tugmalar [✅ Qo\'sh] [✖ Kerak emas]', kb and [b['text'] for b in kb[0]] == ["✅ Qo'sh", '✖ Kerak emas'], kb)
sinov('callback ≤ 64 bayt', kb and all(len(b['callback_data'].encode()) <= 64 for b in kb[0]))
sinov('postga havola', tk and 'https://t.me/nuqta_tech/501' in tk[0]['text'])
sinov('kanal postiga avtomatik tugma QO\'YILMADI', not kanal_tahrir())

print('— 2) model yo\'q: xabar yo\'q')
yangila({'update_id': 2, 'channel_post': post('Bugun do\'kon soat 10:00 dan ochiq')})
sinov('taklif yo\'q, kanalga tegilmadi', not takliflar() and not kanal_tahrir(), repr(SOROV)[:200])
yangila({'update_id': 3, 'channel_post': post('Samsung Galaxy S30 chiqdi')})
sinov('Store\'da yo\'q model — taklif yo\'q', not takliflar())

print('— 3) yangilik matni')
yangila({'update_id': 4, 'channel_post': post('📰 Yangilik: Google Pixel 11 rasman taqdim etildi. Narxi 999$')})
sinov('sotuvda yo\'q yangi model haqidagi yangilik — xabar yo\'q', not takliflar() and not kanal_tahrir())
yangila({'update_id': 5, 'channel_post': post('📰 Pixel 10 Pro uchun Android 17 yangilanishi chiqdi', pid=502)})
sinov('sotuvdagi model haqida yangilik — faqat SO\'RALADI, post tegilmaydi', len(takliflar()) == 1 and not kanal_tahrir())
bos(f'nts:no:{KANAL}:502')
sinov('«✖ Kerak emas» — kanal posti tegilmaydi, admin xabari «✖ Qo\'shilmadi»', not kanal_tahrir()
      and any(u == 'editMessageReplyMarkup' and d.get('chat_id') == bot.GURUH['id'] and "Qo'shilmadi" in json.dumps(d, ensure_ascii=False)
              for u, d in SOROV), repr(SOROV)[:300])

print('— ✅ Qo\'sh')
bos(f'nts:ok:{KANAL}:501:p10p')
kt = kanal_tahrir()
sinov('kanal postiga (501) bitta tahrir — editMessageReplyMarkup (matn emas)', len(kt) == 1 and kt[0]['message_id'] == 501
      and not [u for u, d in SOROV if u in ('editMessageText', 'editMessageCaption')], repr(SOROV)[:300])
tg = kt[0]['reply_markup']['inline_keyboard'] if kt else []
sinov('URL tugma «🛒 Sotuvda — Google Pixel 10 Pro (2 ta) / В продаже (2 шт.)»', tg == [[{
    'text': '🛒 Sotuvda — Google Pixel 10 Pro (2 ta) / В продаже (2 шт.)',
    'url': f'https://t.me/{bot.BOT_USERNAME}?startapp=m_p10p__src_nt'}]], tg)
sinov('admin xabari — «✅ Qo\'shildi (2 ta)»', any(d.get('chat_id') == bot.GURUH['id'] and "Qo'shildi (2 ta)" in json.dumps(d, ensure_ascii=False)
                                                   for u, d in SOROV if u == 'editMessageReplyMarkup'))
sinov('begona bosgan tugma ishlamaydi', (bos(f'nts:ok:{KANAL}:501:p10p', kim=555) or True) and not kanal_tahrir())

print('— postning o\'z tugmalari saqlanadi; N — bosilgan paytdagi soni')
asl = {'inline_keyboard': [[{'text': 'Instagram', 'url': 'https://instagram.com/x'}]]}
yangila({'update_id': 6, 'channel_post': post('Pixel 10 Pro', pid=503, caption=True, markup=asl)})
sinov('rasm izohi (caption) dan ham topiladi', len(takliflar()) == 1)
bot._ELON_CACHE['by_num']['7'] = {'num': 7, 'specId': 'p10p', 'status': 'active'}
bos(f'nts:ok:{KANAL}:503:p10p')
tg = (kanal_tahrir() or [{}])[0].get('reply_markup', {}).get('inline_keyboard', [])
sinov('eski tugma joyida + «🛒 Sotuvda (3 ta)» oxirida', len(tg) == 2 and tg[0] == asl['inline_keyboard'][0] and '(3 ta)' in tg[1][0]['text'], tg)
del bot._ELON_CACHE['by_num']['7']

print('— sotuvdan chiqib ketgan model')
bot._ELON_CACHE['by_num']['4']['status'] = 'sold'
bos(f'nts:ok:{KANAL}:504:p10')
sinov('«endi sotuvda yo\'q» — kanalga tegilmaydi', not kanal_tahrir() and any("endi sotuvda yo'q" in str(d.get('text')) for u, d in SOROV), repr(SOROV)[:300])
bot._ELON_CACHE['by_num']['4']['status'] = 'active'

print('— huquq yo\'q')
JAVOB['edit'] = {'ok': False, 'error_code': 400, 'description': 'Bad Request: not enough rights to edit messages'}
bos(f'nts:ok:{KANAL}:505:p10p')
xm = ' '.join(str(d.get('text')) for u, d in SOROV if u == 'sendMessage')
sinov("adminga «❌ Tugma qo'shilmadi» + qaysi huquqni yoqish", "Tugma qo'shilmadi" in xm and 'can_edit_messages' in xm and 'Xabarlarni tahrirlash' in xm, xm)
JAVOB['edit'] = {'ok': True, 'result': True}
JAVOB['member'] = {'ok': True, 'result': {'status': 'administrator', 'can_edit_messages': False}}
sinov('nt_huquq: admin, can_edit_messages yo\'q → False', bot.nt_huquq(majbur=True) is False)
yangila({'update_id': 7, 'channel_post': post('Pixel 10 Pro', pid=506)})
sinov('taklifda ⚠️ huquq ogohlantirishi', takliflar() and "tahrirlash huquqi yo'q" in takliflar()[0]['text'], takliflar())
JAVOB['member'] = {'ok': True, 'result': {'status': 'administrator', 'can_edit_messages': True}}
sinov('nt_huquq: admin + can_edit_messages → True', bot.nt_huquq(majbur=True) is True)
JAVOB['member'] = {'ok': True, 'result': {'status': 'creator'}}
sinov('nt_huquq: creator → True', bot.nt_huquq(majbur=True) is True)
JAVOB['member'] = {'ok': True, 'result': {'status': 'left'}}
sinov('nt_huquq: admin emas → False', bot.nt_huquq(majbur=True) is False)
JAVOB['member'] = {'ok': False, 'description': 'Bad Request: chat not found'}
sinov('nt_huquq: tekshirib bo\'lmadi → None', bot.nt_huquq(majbur=True) is None)
yangila({'update_id': 8, 'message': {'message_id': 1, 'chat': {'id': ADMIN}, 'from': {'id': ADMIN}, 'text': '/nt_huquq'}})
xm = ' '.join(str(d.get('text')) for u, d in SOROV if u == 'sendMessage')
sinov('/nt_huquq — holat + ko\'rsatma', '@nuqta_tech' in xm and 'can_edit_messages' in xm, xm)
JAVOB['member'] = {'ok': True, 'result': {'status': 'administrator', 'can_edit_messages': True}}
bot.nt_huquq(majbur=True)

print('— eski postlarga va boshqa kanallarga tegilmaydi')
yangila({'update_id': 10, 'channel_post': post('Pixel 10 Pro', pid=10, eski=True)})
sinov('3 kunlik eski post — taklif yo\'q', not takliflar())
yangila({'update_id': 11, 'edited_channel_post': post('Pixel 10 Pro', pid=11)})
sinov('tahrirlangan post (edited_channel_post) — taklif yo\'q', not takliflar())
yangila({'update_id': 12, 'channel_post': post('Pixel 10 Pro', pid=12, chat={'id': -1005555, 'type': 'channel', 'username': 'nuqta_tech_mobile'})})
sinov('boshqa kanal (@nuqta_tech_mobile) — taklif yo\'q', not takliflar())
bot.TECH_KANAL = str(KANAL)
yangila({'update_id': 13, 'channel_post': post('Pixel 10 Pro', pid=13, chat={'id': KANAL, 'type': 'channel'})})
sinov('TECH_KANAL_ID raqamli id bo\'lsa ham ishlaydi', len(takliflar()) == 1)
bot.TECH_KANAL = ''
bos('nts:ok:abc:1:p10p')
sinov('buzuq callback — hech narsa', not kanal_tahrir())

print(f'{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
