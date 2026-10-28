# -*- coding: utf-8 -*-
"""tests/b3227_ikki_kanal.py — 3227: ikki kanal (test + asosiy) va webhook maxfiy kaliti.

Ishga tushirish:  python tests/b3227_ikki_kanal.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: requests.post / get almashtirilgan — chaqirilsa sinov yiqiladi.
Asosiy kanalga hech qanday so'rov ketmaydi (yuborish funksiyalari ham almashtirilgan, faqat chat yoziladi).
Chiqish: har sinov — «✓ nom» yoki «✗ nom — sabab»; oxirida «N ✓, M ✗», xato bo'lsa — chiqish kodi 1.
"""
import asyncio
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# import'dan OLDIN: haqiqiy token / kanal / kalit yo'q
for k in ('BOT_TOKEN', 'MAIN_CHANNEL_ID', 'WEBHOOK_SECRET', 'POST_CHANNEL_ID', 'POST_KANALLAR', 'TEST_CHANNEL_ID',
          'CHANNEL_ID', 'GURUH_KANAL_ID', 'ESKI_BOT_TOKEN', 'RENDER_URL'):
    os.environ.pop(k, None)

import requests


def _tarmoq_yoq(*a, **kw):
    raise AssertionError(f'tarmoq so\'rovi: {a[:1]}')


requests.post = requests.get = _tarmoq_yoq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

bot.req.post = bot.req.get = _tarmoq_yoq

TEST = '@Kraken_mobile_test'
ASOSIY = '@nuqta_tech_mobile'
NATIJA = [0, 0]


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


def rejim(main='', guruh='test'):
    bot.MAIN_KANALLAR = bot._main_kanallar(main)
    bot.GURUH_KANAL = guruh


# ── 1. Jadval: har post turi qaysi kanalga ──────────────────────────────────
KUTILGAN = {   # tur: (asosiy kanal yo'q, asosiy kanal ulangan)
    'elon': (TEST, ASOSIY),
    'toplam': (TEST, ASOSIY),
    'katalog': (TEST, ASOSIY),
    'guruh': (TEST, TEST),            # GURUH_KANAL_ID sukut — test
    'konkurs': (ASOSIY, ASOSIY),      # CHANNEL (sukut @nuqta_tech_mobile)
    'konkurs_sinov': (TEST, TEST),
    'richtest': (TEST, TEST),
    'rasm_yuklash': (TEST, TEST),
}
print('1. Post turi → kanal')
sinov('KANAL_YOLI — hamma tur sinovda bor', set(bot.KANAL_YOLI) == set(KUTILGAN),
      f'{sorted(set(bot.KANAL_YOLI) ^ set(KUTILGAN))}')
sinov('sukut: POST_CHANNEL = test kanal', bot.POST_CHANNEL == TEST, bot.POST_CHANNEL)
for tur, (bosh, ulangan) in KUTILGAN.items():
    rejim('')
    sinov(f'{tur}: MAIN_CHANNEL_ID yo\'q → {bosh}', bot.kanal_tanla(tur) == bosh, bot.kanal_tanla(tur))
    rejim(ASOSIY)
    sinov(f'{tur}: MAIN_CHANNEL_ID bor → {ulangan}', bot.kanal_tanla(tur) == ulangan, bot.kanal_tanla(tur))
rejim(ASOSIY, 'asl')
sinov('guruh «asl» → asosiy kanal', bot.kanal_tanla('guruh', 'mobile') == ASOSIY, bot.kanal_tanla('guruh', 'mobile'))
rejim(ASOSIY, '@boshqa')
sinov('guruh «@boshqa» → o\'sha chat', bot.kanal_tanla('guruh') == '@boshqa', bot.kanal_tanla('guruh'))
rejim('mobile=@m_kanal pc=@pc_kanal')
sinov('yo\'nalishli MAIN: pc → @pc_kanal', bot.kanal_tanla('elon', 'pc') == '@pc_kanal', bot.kanal_tanla('elon', 'pc'))
sinov('yo\'nalishli MAIN: noma\'lum → mobile', bot.kanal_tanla('elon', 'camera') == '@m_kanal',
      bot.kanal_tanla('elon', 'camera'))
sinov('yo\'nalishli MAIN: yo\'nalishsiz (to\'plam) → mobile', bot.kanal_tanla('toplam') == '@m_kanal',
      bot.kanal_tanla('toplam'))
rejim('')
sinov('_kk_kanal: sinov konkursi → test', bot._kk_kanal({'prize': 'TEST sovrin'}) == TEST)
sinov('_kk_kanal: oddiy konkurs → asosiy (CHANNEL)', bot._kk_kanal({'prize': 'iPhone'}) == ASOSIY)
sinov('RASM_YUKLASH_CHAT → test', bot.RASM_YUKLASH_CHAT == TEST, bot.RASM_YUKLASH_CHAT)

# ── 2. Post id'lari: «a» — asosiy kanal, «a»siz — test ──────────────────────
print('2. Post id\'lari')
E = lambda v: {'channel_message_id': v}   # noqa: E731
rejim('')
sinov('test rejim: «123» → test kanal', bot.kanal_postlar(E('123')) == [(None, TEST, 123)], bot.kanal_postlar(E('123')))
sinov('test rejim: «123.0» (Sheets soni) → 123', bot.kanal_postlar(E('123.0')) == [(None, TEST, 123)])
sinov('test rejim: «a123» e\'tiborsiz', bot.kanal_postlar(E('a123')) == [])
sinov('test rejim: «mobile:5 pc:6»', bot.kanal_postlar(E('mobile:5 pc:6')) == [('mobile', TEST, 5), ('pc', TEST, 6)])
sinov('test rejim: kanal_id_matn bitta → 7 (son, avvalgidek)', bot.kanal_id_matn([(None, 7)]) == 7)
rejim(ASOSIY)
sinov('asosiy rejim: eski «123» — post yo\'q (tegilmaydi)', bot.kanal_postlar(E('123')) == [])
sinov('asosiy rejim: eski «mobile:5» — post yo\'q', bot.kanal_postlar(E('mobile:5')) == [])
sinov('asosiy rejim: «a123» → asosiy kanal', bot.kanal_postlar(E('a123')) == [(None, ASOSIY, 123)])
sinov('asosiy rejim: «mobile:a5 pc:a6»', bot.kanal_postlar(E('mobile:a5 pc:a6')) == [('mobile', ASOSIY, 5), ('pc', ASOSIY, 6)])
sinov('asosiy rejim: hammasi=True — eskisi test kanalda',
      bot.kanal_postlar(E('123'), hammasi=True) == [(None, TEST, 123)])
sinov('asosiy rejim: kanal_msg_id eski → None', bot.kanal_msg_id(E('123')) is None)
sinov('asosiy rejim: kanal_id_matn bitta → «a7»', bot.kanal_id_matn([(None, 7)]) == 'a7', bot.kanal_id_matn([(None, 7)]))
sinov('asosiy rejim: _tok → «mobile:a7»', bot._tok('mobile', 7) == 'mobile:a7')

yozildi = []
_asl_sheets = bot._sheets_update
bot._sheets_update = lambda d: yozildi.append(d) or True
for main, mid, kut in (('', 7, 7), ('', '7', 7), (ASOSIY, 7, 'a7'), (ASOSIY, 'a7', 'a7'), (ASOSIY, 'mobile:a7', 'mobile:a7'),
                       (ASOSIY, None, '')):
    rejim(main)
    yozildi.clear()
    bot.kanal_id_yoz(999999, mid)
    q = yozildi[0]['channel_message_id'] if yozildi else '—'
    sinov(f'kanal_id_yoz({mid!r}) {"asosiy" if main else "test"} → {kut!r}', q == kut, repr(q))
bot._sheets_update = _asl_sheets

# ── 3. Haqiqiy yuborish yo'li: kanal_post / richtest qaysi chatga ──────────
print('3. Yuborish yo\'li (soxta yuborish)')
yuborilgan = []
_asl = {n: getattr(bot, n) for n in ('elon_cache_get', 'elon_status', 'post_yonalish', 'elon_yonalishlar', 'elon_turi',
                                     'kanal_rich_yubor', 'kanal_id_yoz', 'send_rich', 'send_msg', 'build_rich_html')}
bot.elon_cache_get = lambda num: ({'num': num}, {})
bot.elon_status = lambda e: 'active'
bot.post_yonalish = lambda e, m, tanlangan=None, **kw: 'mobile'
bot.elon_yonalishlar = lambda e, m: ['mobile']
bot.elon_turi = lambda e, m: 'phone'
bot.kanal_rich_yubor = lambda num, e, m, chat, *a, **kw: (yuborilgan.append(chat) or 41, '')
bot.kanal_id_yoz = lambda num, v: yozildi.append(v)
bot.send_rich = lambda chat, h, **kw: (yuborilgan.append(chat) or 42, '')
bot.send_msg = lambda *a, **kw: None
bot.build_rich_html = lambda *a, **kw: '<b>x</b>'
for main, kut in (('', TEST), (ASOSIY, ASOSIY)):
    rejim(main)
    yuborilgan.clear()
    yozildi.clear()
    bot.kanal_post(5, olx=False)
    sinov(f'kanal_post (oddiy oqim) {"asosiy" if main else "test"} rejim → {kut}', yuborilgan == [kut], yuborilgan)
    sinov(f'kanal_post id yozildi → {"a41" if main else "41"}', [str(v) for v in yozildi] == ['a41' if main else '41'],
          yozildi)
    yuborilgan.clear()
    bot.richtest(111, 5)
    sinov(f'/testpost (richtest) {"asosiy" if main else "test"} rejim → lichka + test, asosiyga yo\'q',
          yuborilgan == [111, TEST], yuborilgan)
for n, f in _asl.items():
    setattr(bot, n, f)

# ── 4. Webhook maxfiy kaliti ────────────────────────────────────────────────
print('4. Webhook maxfiy kaliti')


class Sorov:
    def __init__(self, kalit=None):
        self.headers = {} if kalit is None else {'X-Telegram-Bot-Api-Secret-Token': kalit}

    async def json(self):
        return []   # dict emas — ish boshlanmaydi, faqat javob kodi tekshiriladi


def holat(f, req_):
    return asyncio.run(f(req_)).status


SIR = 'sinov-kaliti-' + 'x' * 20
for nom, f in (('/webhook', bot.webhook), ('/webhook-eski', bot.eski_webhook)):
    bot.WEBHOOK_SECRET = ''
    sinov(f'{nom}: env yo\'q, sarlavha yo\'q → 200', holat(f, Sorov()) == 200)
    bot.WEBHOOK_SECRET = SIR
    sinov(f'{nom}: noto\'g\'ri kalit → 403', holat(f, Sorov('boshqa')) == 403)
    sinov(f'{nom}: kalitsiz so\'rov → 403', holat(f, Sorov()) == 403)
    sinov(f'{nom}: to\'g\'ri kalit → 200', holat(f, Sorov(SIR)) == 200)
bot.WEBHOOK_SECRET = ''
sinov('setWebhook: env yo\'q — secret_token yo\'q', 'secret_token' not in bot.webhook_sozlama('u', ['message']))
bot.WEBHOOK_SECRET = SIR
sinov('setWebhook: env bor — secret_token qo\'shiladi', bot.webhook_sozlama('u', ['message']).get('secret_token') == SIR)
bot.WEBHOOK_SECRET = ''

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
