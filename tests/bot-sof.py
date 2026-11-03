# -*- coding: utf-8 -*-
"""tests/bot-sof.py — sof (tarmoqsiz) sinovlar: kanal postining kollaj belgisi («k», 3238 / 3242 / 3244).

Ishga tushirish:  python tests/bot-sof.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: requests.post / get almashtirilgan; send_rich / edit_rich / _sheets_update — yozib oluvchi soxtalar.
3242: to'plam postidagi «k» li e'lon boshqa postga ko'chsa («Yana keldi» / id tozalandi) qolganlar posti kollaj bo'lib qoladi;
«↩ Qaytarish» belgini hamma e'londan oladi. 3244: KOLLAJ_YOQIQ = False — belgi bo'lsa ham post slayd.
Chiqish: har sinov — «✓ nom» yoki «✗ nom — sabab»; oxirida «N ✓, M ✗», xato bo'lsa — chiqish kodi 1.
"""
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


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


RASM = '["https://ik.imagekit.io/x/a.jpg", "https://ik.imagekit.io/x/b.jpg"]'
MODELS = {'ch45': {'id': 'ch45', 'series': 'zaryad', 'nameUz': 'Nano 45W', 'brand': 'Anker', 'mos': 'phone'}}
LOG, SOROV = [], []


def muhit(idlar, yoqiq=True, asosiy=False):
    """To'plam posti: №303, №304, №305 (aksessuar). idlar — {num: channel_message_id}."""
    bot.KOLLAJ_YOQIQ = yoqiq
    bot.MAIN_KANALLAR = {'*': '@x'} if asosiy else {}
    bot._ELON_CACHE['series'] = [{'key': 'zaryad', 'type': 'accessory', 'labelUz': 'Zaryadlovchilar'}]
    bot._ELON_CACHE['models'] = dict(MODELS)
    bot._ELON_CACHE['by_num'] = {str(n): {'num': n, 'specId': 'ch45', 'price': 10 + n % 10, 'status': 'active',
                                          'images': RASM, 'channel_message_id': v} for n, v in idlar.items()}
    bot._ELON_CACHE['time'] = 1.0
    bot.GURUH = {'id': -1001234567890, 'post': 12, 'kollaj': 16}
    LOG.clear()
    SOROV.clear()
    bot.send_rich = lambda chat, html, disable_notification=False, **k: (LOG.append(('send', chat, html)) or (900, ''))
    bot.edit_rich = lambda chat, mid, html, **k: (LOG.append(('edit', mid, html)) or (True, ''))
    bot.delete_msg = lambda chat, mid: (LOG.append(('del', mid)) or (True, ''))
    bot._sheets_update = lambda payload: (LOG.append(('sheets', payload)) or True)
    bot.send_msg = lambda chat, text, keyboard=None: LOG.append(('msg', text))

    class _Req:
        @staticmethod
        def post(url, json=None, timeout=None):
            SOROV.append((url.rsplit('/', 1)[-1], json))
    bot.req = _Req


def idi(num):
    return str(bot._ELON_CACHE['by_num'][str(num)]['channel_message_id'])


def ed(mid):
    return [x for x in LOG if x[0] == 'edit' and x[1] == mid]


print('— kollaj belgisi postning hamma e\'lonida')
muhit({303: 77, 304: 77, 305: 77})
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:77')
sinov("«✅ Kanalda shunga o'tkazish» — uchala e'londa «77k»", [idi(n) for n in (303, 304, 305)] == ['77k'] * 3,
      [idi(n) for n in (303, 304, 305)])
sinov('post 77 — kollaj', bot.kollajmi(77) and ed(77) and '<tg-collage>' in ed(77)[-1][2])

print("— «k» li e'lon ko'chdi (yangi sxema): qolganlar posti kollaj")
bot.kanal_id_yoz(303, 99)
sinov('№303 — yangi post 99 (belgisiz)', idi(303) == '99' and not bot.kollajmi(99), idi(303))
sinov('kollajmi(77) — True bo\'lib qoldi', bot.kollajmi(77))
LOG.clear()
bot.toplam_tahrir(77)
sinov('keyingi tahrirda post 77 kollaj', ed(77) and '<tg-collage>' in ed(77)[-1][2] and '<tg-slideshow>' not in ed(77)[-1][2],
      repr(LOG)[:200])

print("— eski post: «k» faqat bitta e'londa (3242 gacha) — id 77 → 99")
muhit({303: '77k', 304: 77, 305: 77})
sinov('oldin: kollajmi(77) True', bot.kollajmi(77))
bot.kanal_id_yoz(303, 99)
sinov('keyin: kollajmi(77) True bo\'lib qoldi', bot.kollajmi(77), [idi(n) for n in (304, 305)])
sinov("belgi qolgan e'lonlarga o'tdi (№304, №305 — «77k»)", [idi(n) for n in (304, 305)] == ['77k', '77k'],
      [idi(n) for n in (304, 305)])
sinov("jadvalga yozildi", {'num': 304, 'channel_message_id': '77k'} in [x[1] for x in LOG if x[0] == 'sheets'])
sinov("ko'chgan №303 — post 99 slayd (belgi ergashmaydi)", idi(303) == '99' and not bot.kollajmi(99))

print("— eski post: «k» li e'lon id'si tozalandi")
muhit({303: '77k', 304: 77})
bot.kanal_id_yoz(303, None)
sinov('№303 — id bo\'sh, №304 — «77k», post kollaj', idi(303) == '' and idi(304) == '77k' and bot.kollajmi(77), idi(304))

print("— «Yana keldi» (kanal_yana_keldi): to'plamdan chiqdi")
muhit({303: '77k', 304: 77, 305: 77})
bot.kanal_post = lambda num, yon=None: (bot.kanal_id_yoz(num, 99), (99, ''))[1]
yangi, xato = bot.kanal_yana_keldi(303)
sinov('yangi post 99', yangi == 99 and idi(303) == '99', f'{yangi} {xato}')
sinov('to\'plam 77 qayta yasaldi — kollaj', ed(77) and '<tg-collage>' in ed(77)[-1][2], repr(LOG)[:300])

print("— «↩ Qaytarish» belgini hamma e'londan oladi")
muhit({303: '77k', 304: '77k', 305: 77})
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kgq:77')
sinov('uchala e\'londa belgi yo\'q', [idi(n) for n in (303, 304, 305)] == ['77'] * 3, [idi(n) for n in (303, 304, 305)])
sinov('post 77 — slayd', not bot.kollajmi(77) and ed(77) and '<tg-slideshow>' in ed(77)[-1][2])
bot.kanal_id_yoz(303, 99)
sinov("qaytarilgandan keyin e'lon ko'chsa — belgi qayta paydo bo'lmaydi", not bot.kollajmi(77) and idi(304) == '77')
muhit({303: '77k', 304: '77k'})
bot.kollaj_almashtir(bot.GURUH['id'], 5, 'slayd:77')
sinov("📢 Postlar «🎞 Slaydga qaytarish» ham — hammasidan", [idi(n) for n in (303, 304)] == ['77', '77'])

print('— chegaralar')
muhit({303: '77k', 304: 77})
bot.kollaj_belgila(77, False)
sinov("belgini olish («↩») — «k» li e'londa ham boshqasiga o'tmaydi", [idi(n) for n in (303, 304)] == ['77', '77'])
muhit({303: '77k', 304: 88})
bot.kanal_id_yoz(303, 99)
sinov('boshqa postga (88) tegilmaydi', idi(304) == '88' and not bot.kollajmi(88))
muhit({303: 'a77k', 304: 'a77'}, asosiy=True)
bot.kanal_id_yoz(303, 'a99')
sinov("asosiy kanal rejimi: «a77k» ko'chdi → №304 «a77k»", idi(304) == 'a77k' and bot.kollajmi(77), idi(304))
muhit({303: '77k a77', 304: '77 a77'})
bot.kanal_id_yoz(303, '99 a77')
sinov("ikki rejim: hozirgi rejim (77) belgisi o'tdi, «a» tokenlariga tegilmadi", idi(304) == '77k a77', idi(304))

print("— 3244: kollaj o'chiq (KOLLAJ_YOQIQ = False)")
muhit({303: '77k', 304: '77k'}, yoqiq=False)
sinov('belgi bor, lekin kollajmi(77) — False (slayd)', not bot.kollajmi(77))
bot.toplam_tahrir(77)
sinov('tahrirda post slayd', ed(77) and '<tg-slideshow>' in ed(77)[-1][2] and '<tg-collage>' not in ed(77)[-1][2])
n = len(LOG)
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:77')
sinov("eski «✅ Kanalda shunga o'tkazish» tugmasi — post tegilmaydi", len(LOG) == n and not SOROV)
sinov("kollaj nusxasi yo'q", bot.kollaj_nusxa(77)[0] is None)
muhit({303: '77k', 304: 77}, yoqiq=False)
bot.kanal_id_yoz(303, 99)
sinov("o'chiq bo'lsa ham belgi saqlanadi (yoqilganda kollaj qaytadi)", idi(304) == '77k')

print(f'\n  {NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
