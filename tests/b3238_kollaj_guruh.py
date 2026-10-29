# -*- coding: utf-8 -*-
"""tests/b3238_kollaj_guruh.py — 3238: kanalda oddiy post, guruhning 🖼 Kollajlar mavzusiga kollaj nusxasi + tugma.

Ishga tushirish:  python tests/b3238_kollaj_guruh.py   (repo ildizidan)

Tarmoqqa HECH NARSA ketmaydi: requests.post / get almashtirilgan; send_rich / edit_rich / _sheets_update — yozib oluvchi
soxtalar. Tekshiriladi: nusxa Kollajlar mavzusiga kollaj bilan va «✅ Kanalda shunga o'tkazish» tugmasi bilan ketadi;
tugma bosilsa kanal posti kollajga tahrirlanadi, holat jadvalga (id oxirida «k») yoziladi — bot qayta yonsa ham saqlanadi;
«↩ Qaytarish» — slayd; kanal id'sini o'qish «k» dan buzilmaydi.
Chiqish: har sinov — «✓ nom» yoki «✗ nom — sabab»; oxirida «N ✓, M ✗», xato bo'lsa — chiqish kodi 1.
"""
import asyncio
import inspect
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

bot.KOLLAJ_YOQIQ = True   # 3244: kollaj hozircha o'chiq; bu sinov yoqilgan holatni tekshiradi (o'chig'i — tests/bot-sof.py)

NATIJA = [0, 0]


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


RASM = '["https://ik.imagekit.io/x/a.jpg", "https://ik.imagekit.io/x/b.jpg", "https://ik.imagekit.io/x/c.jpg"]'
MODELS = {
    'p10p': {'id': 'p10p', 'series': 'p10s', 'nameUz': 'Google Pixel 10 Pro', 'brand': 'Google'},
    'ch45': {'id': 'ch45', 'series': 'zaryad', 'nameUz': 'Nano 45W', 'brand': 'Anker', 'mos': 'phone'},
}
LOG, SOROV = [], []


def muhit(sheets_ok=True):
    """Xotira: №301 telefon (post 55), №303 + №304 aksessuar — bitta to'plam posti (77). Guruh: Kollajlar mavzusi 16."""
    bot._ELON_CACHE['series'] = [{'key': 'p10s', 'type': 'phone', 'labelUz': 'Pixel 10 Seriyasi'},
                                 {'key': 'zaryad', 'type': 'accessory', 'labelUz': 'Zaryadlovchilar'}]
    bot._ELON_CACHE['models'] = dict(MODELS)
    bot._ELON_CACHE['by_num'] = {
        '301': {'num': 301, 'specId': 'p10p', 'price': 900, 'status': 'active', 'images': RASM, 'channel_message_id': 55},
        '303': {'num': 303, 'specId': 'ch45', 'price': 14, 'status': 'active', 'images': RASM, 'channel_message_id': 77},
        '304': {'num': 304, 'specId': 'ch45', 'price': 15, 'status': 'active', 'images': RASM, 'channel_message_id': 77},
    }
    bot._ELON_CACHE['time'] = 1.0
    bot.GURUH = {'id': -1001234567890, 'post': 12, 'kollaj': 16}
    LOG.clear()
    SOROV.clear()
    bot.send_rich = lambda chat, html, disable_notification=False, **k: (
        LOG.append(('send', chat, html, k.get('tugma'), disable_notification)) or (900 + len(LOG), ''))
    bot.edit_rich = lambda chat, mid, html, **k: (LOG.append(('edit', mid, html)) or (True, ''))
    bot._sheets_update = lambda payload: (LOG.append(('sheets', payload)) or sheets_ok)
    bot.send_msg = lambda chat, text, keyboard=None: LOG.append(('msg', text))

    class _Req:
        @staticmethod
        def post(url, json=None, timeout=None):
            SOROV.append((url.rsplit('/', 1)[-1], json))
    bot.req = _Req


def cb(kb):
    return [t['callback_data'] for q in kb['inline_keyboard'] for t in q]


# ── 1. Id formati: «k» belgisi ──
bot.MAIN_KANALLAR = {}
sinov("«55k» o'qiladi — post id 55", bot.kanal_msg_id({'channel_message_id': '55k'}) == 55)
sinov("«mobile:123k pc:45» — ikkala post", [m for _, _, m in bot.kanal_postlar({'channel_message_id': 'mobile:123k pc:45'})] == [123, 45])
sinov("belgi qo'yiladi: 55 → 55k", bot._id_kollaj('55', 55, True) == (False, '55k'))
sinov("belgi olinadi: 55k → 55", bot._id_kollaj('55k', 55, False) == (True, '55'))
sinov("faqat o'sha post: mobile:123 pc:45 → mobile:123k pc:45", bot._id_kollaj('mobile:123 pc:45', 123, True)[1] == 'mobile:123k pc:45')
sinov("boshqa rejim («a») tokeniga tegilmaydi", bot._id_kollaj('a55 55', 55, True)[1] == 'a55 55k')
bot.MAIN_KANALLAR = {'*': '@x'}
sinov("asosiy kanal rejimida — «a» tokeni", bot._id_kollaj('a55 55', 55, True)[1] == 'a55k 55')
sinov("asosiy rejimda «a55k» o'qiladi", bot.kanal_msg_id({'channel_message_id': 'a55k'}) == 55)
bot.MAIN_KANALLAR = {}

# ── 2. Kollaj nusxasi Kollajlar mavzusiga ──
muhit()
mid, xato = bot.kollaj_nusxa(55)
s = LOG[-1] if LOG else None
sinov("yakka post: nusxa yuborildi", bool(mid) and s and s[0] == 'send', f'{mid} {xato} {LOG}')
sinov("guruhning Kollajlar mavzusiga (16)", s and int(s[1]) == -1001234567890 and getattr(s[1], 'thread', None) == 16, repr(s and s[1]))
sinov("kollaj ko'rinishida (slayd emas)", s and '<tg-collage>' in s[2] and '<tg-slideshow>' not in s[2])
sinov("tagida «✅ Kanalda shunga o'tkazish» (kg:55)", s and cb(s[3]) == ['kg:55']
      and s[3]['inline_keyboard'][0][0]['text'] == "✅ Kanalda shunga o'tkazish", repr(s and s[3]))
sinov("ovozsiz", s and s[4] is True)
sinov("kanal postiga tegilmadi", not [x for x in LOG if x[0] == 'edit'])
bot.kollaj_nusxa(77)
s = LOG[-1]
sinov("to'plam posti: kollaj nusxa, kg:77", s[0] == 'send' and '<tg-collage>' in s[2] and cb(s[3]) == ['kg:77'])
bot.GURUH = {'id': -1001234567890, 'post': 12}
n = len(LOG)
sinov("Kollajlar mavzusi yo'q — hech narsa", bot.kollaj_nusxa(55)[0] is None and len(LOG) == n)

# ── 3. Tugma bosildi → kanal posti kollaj; holat jadvalda ──
muhit()
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:55')
ed = [x for x in LOG if x[0] == 'edit']
sinov("kanal posti 55 kollajga tahrirlandi", ed and ed[-1][1] == 55 and '<tg-collage>' in ed[-1][2], repr(ed[-1:]))
sinov("jadvalga «55k» yozildi", ('sheets', {'num': 301, 'channel_message_id': '55k'}) in LOG)
sinov("guruh tugmasi «✅ O'tkazildi · ↩ Qaytarish» (kgq:55)", SOROV and SOROV[-1][0] == 'editMessageReplyMarkup'
      and SOROV[-1][1]['message_id'] == 9 and cb(SOROV[-1][1]['reply_markup']) == ['kgq:55']
      and SOROV[-1][1]['reply_markup']['inline_keyboard'][0][0]['text'] == "✅ O'tkazildi · ↩ Qaytarish", repr(SOROV[-1:]))
# «bot qayta yondi» — xotirada faqat jadvaldan kelgan qiymat qoladi
saqlangan = bot._ELON_CACHE['by_num']['301']['channel_message_id']
muhit()
bot._ELON_CACHE['by_num']['301']['channel_message_id'] = saqlangan
sinov("qayta yongandan keyin ham kollaj (jadvaldan)", bot.kollajmi(55), saqlangan)
bot.kanal_tahrir(301)
sinov("keyingi tahrirda (narx) kollaj qoladi", '<tg-collage>' in LOG[-1][2])
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kgq:55')
ed = [x for x in LOG if x[0] == 'edit']
sinov("«↩ Qaytarish» — kanal posti slaydga", '<tg-slideshow>' in ed[-1][2] and not bot.kollajmi(55))
sinov("jadvalda 55 (belgisiz, eski ko'rinish)", ('sheets', {'num': 301, 'channel_message_id': 55}) in LOG)
sinov("tugma yana «✅ Kanalda shunga o'tkazish»", cb(SOROV[-1][1]['reply_markup']) == ['kg:55'])

# to'plam posti: belgi birinchi e'londa, hammasi kollaj deb biladi
muhit()
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:77')
sinov("to'plam: post 77 kollaj, belgi bitta e'londa", LOG[-1][0] == 'edit' and '<tg-collage>' in LOG[-1][2]
      and [x[1]['channel_message_id'] for x in LOG if x[0] == 'sheets'] == ['77k'], repr(LOG))
bot.toplam_tahrir(77)
sinov("to'plam keyingi tahrirda ham kollaj", '<tg-collage>' in LOG[-1][2])

# 📢 Postlar tugmasi (eski) — o'zgarmadi, o'sha belgi
muhit()
bot.kollaj_almashtir(bot.GURUH['id'], 5, 'kollaj:55')
sinov("eski «🖼 Kollajga o'tkazish» — o'z tugmasi (slayd:55, 3273: o'chirishsiz)", cb(SOROV[-1][1]['reply_markup']) == ['slayd:55']
      and bot.kollajmi(55))

# jadval yozilmasa — post o'zgaradi, adminga ⚠️
muhit(sheets_ok=False)
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:55')
sinov("jadvalga yozilmadi — ⚠️ ogohlantirish, post baribir kollaj",
      any(x[0] == 'msg' and '⚠️' in x[1] for x in LOG) and any(x[0] == 'edit' and '<tg-collage>' in x[2] for x in LOG))

# post topilmadi — sabab, tugma o'zgarmaydi
muhit()
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:12345')
sinov("e'loni yo'q post — sabab, tugma tegilmaydi", LOG and LOG[-1][0] == 'msg' and "o'zgarmadi" in LOG[-1][1] and not SOROV)
n = len(LOG)
bot.kollaj_almashtir(bot.GURUH['id'], 9, 'kg:abc')
sinov("noto'g'ri id — hech narsa", len(LOG) == n and not SOROV)

# ── 4. Ulanish: callback va post chiqqan joylar ──
manba = inspect.getsource(bot)
sinov("callback: kg: / kgq: kollaj_almashtir ga", "cq_data.startswith(('kollaj:', 'slayd:', 'kg:', 'kgq:')) and cq_adm" in manba)
sinov("7 joyda post chiqqach nusxa (/post, /yana, /toplam, avto, sayt, sayt to'plami)",
      manba.count('kollaj_nusxa_fonda(mid)') == 7, manba.count('kollaj_nusxa_fonda(mid)'))

muhit()
fonda = []
bot.kollaj_nusxa_fonda = fonda.append
bot.kanal_post = lambda num: (55, '')
bot.kanal_yana_keldi = lambda num: (0, 'xato')
asyncio.run(bot.kanal_buyruq(bot.ADMIN_ID, '/post', 301))
sinov("/post — kanalga oddiy, keyin nusxa (55)", fonda == [55], fonda)
asyncio.run(bot.kanal_buyruq(bot.ADMIN_ID, '/yana', 301))
sinov("/yana xato — nusxa yo'q (mid bo'sh)", fonda[-1] == 0)   # kollaj_nusxa_fonda(0) — o'zi hech narsa qilmaydi

# guruh namunasi — Kollajlar mavzusiga endi xabar boradi
nam = {k: (q, m, t) for k, q, m, t in bot.guruh_namunalar()}
sinov("/guruh namuna: Kollajlar — tugmali namuna", nam['kollaj'][1] and cb(nam['kollaj'][2]) == ['namuna'])

print(f'\n  {NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
