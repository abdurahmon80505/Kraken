# -*- coding: utf-8 -*-
"""tests/b3403_kanal_yonalish.py — 3403 (Owner 2026-11-07): Camera e'loni Camera kanaliga, PC — PC kanaliga, Mobile — Mobile.

(a) bitta e'lon: yo'nalish → kanal; ikki yo'nalishli — ikkala kanalga;
(b) to'plam: har kanalga o'zinikilar, kanalga bittasi tushsa — oddiy post, OLX o'tkaziladi;
(c) message_id har kanalda o'zicha: bir xil raqamli post boshqa kanaldagisi bilan aralashmaydi (tahrir / o'chirish / qayta);
(d) eski «a1050» id'lar Mobile'da qoladi; env yo'q — hammasi avvalgidek bitta kanalga;
(e) javobda kanal nomi («Camera»).

Ishga tushirish:  python tests/b3403_kanal_yonalish.py   (repo ildizidan)
Tarmoqqa HECH NARSA ketmaydi.
"""
import asyncio
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

bot.req.post = bot.req.get = _tarmoq_yoq

MOBILE, PC, CAMERA = '@nuqta_tech_mobile', '@nuqta_tech_PC', '@nuqta_tech_camera'
XARITA = f'mobile={MOBILE} pc={PC} camera={CAMERA}'
NATIJA = [0, 0]


def sinov(nom, shart, sabab=''):
    if shart:
        NATIJA[0] += 1
        print(f'  ✓ {nom}')
    else:
        NATIJA[1] += 1
        print(f'  ✗ {nom} — {sabab}')


YUBORILDI, TAHRIR, OCHIRILDI, ADMIN = [], [], [], []
ISHLAMAYDI = set()     # shu kanalga yuborish xato qaytaradi
KEYINGI = {}           # kanal → keyingi message_id (hamma kanalda bir xil boshlanadi — to'qnashuvni tekshiradi)


def _send_rich(chat, html, **kw):
    if chat in ISHLAMAYDI:
        return None, 'kanal ishlamayapti'
    KEYINGI[chat] = KEYINGI.get(chat, 299) + 1
    YUBORILDI.append((chat, html))
    return KEYINGI[chat], ''


def _edit_rich(chat, mid, html, **kw):
    TAHRIR.append((chat, mid, html))
    return True, ''


def _delete_msg(chat, mid):
    OCHIRILDI.append((chat, mid))
    return True, ''


bot.send_rich, bot.edit_rich, bot.delete_msg = _send_rich, _edit_rich, _delete_msg
bot._sheets_update = lambda *a, **kw: True
bot.send_msg = lambda chat, matn, *a, **kw: ADMIN.append(matn)
bot.kanal_rich = lambda elon, models, kollaj=False, yonalish=None: (f"YAKKA:{elon['num']}:{yonalish}", None, [])
bot.build_toplam_html = lambda items, models, kollaj=False: 'TOPLAM:' + ','.join(sorted(str(e['num']) for e in items))
bot.fid_olindi = lambda *a, **kw: False
bot.olx_albom = lambda *a, **kw: (True, '')
bot.kollaj_nusxa_fonda = lambda *a, **kw: None

SERIES = [{'key': 'tel', 'type': 'phone'}, {'key': 'kam', 'type': 'camera'}, {'key': 'gil', 'type': 'case'}]
MODELS = {'1': {'id': '1', 'series': 'tel'}, '2': {'id': '2', 'series': 'kam'}, '3': {'id': '3', 'series': 'gil'},
          '4': {'id': '4', 'series': 'tel', 'yonalish': 'mobile, pc'}}


def elon(num, spec='1', yonalish='', cid=''):
    return {'num': num, 'specId': spec, 'yonalish': yonalish, 'status': 'active', 'price': 100,
            'channel_message_id': cid}


def sahna(xarita, *elonlar):
    bot.MAIN_KANALLAR = bot._main_kanallar(xarita)
    bot._POST_YON.clear()
    bot._ELON_CACHE.update({'by_num': {str(e['num']): e for e in elonlar}, 'models': MODELS, 'series': SERIES, 'time': 1})
    for r in (YUBORILDI, TAHRIR, OCHIRILDI, ADMIN):
        r.clear()
    ISHLAMAYDI.clear()
    KEYINGI.clear()


def cid(num):
    return bot._ELON_CACHE['by_num'][str(num)]['channel_message_id']


print('1. Bitta e\'lon — yo\'nalish kanaliga')
sahna(XARITA, elon(1, '2', 'camera'), elon(2, '1', 'pc'), elon(3, '1', 'mobile'), elon(4, '1'), elon(5, '4'))
for n in (1, 2, 3, 4):
    bot.kanal_post(n)
sinov('camera → Camera, pc → PC, mobile → Mobile, bo\'sh → Mobile', [c for c, _ in YUBORILDI] == [CAMERA, PC, MOBILE, MOBILE],
      str(YUBORILDI))
sinov('id: camera:a300', cid(1) == 'camera:a300', cid(1))
sinov('id: Mobile\'da eski ko\'rinish', cid(3) == 'a300', cid(3))
YUBORILDI.clear()
bot.kanal_post(5, 'pc')
sinov('«mobile, pc» — ikkala kanalga, bo\'limdagisi birinchi', [c for c, _ in YUBORILDI] == [PC, MOBILE], str(YUBORILDI))
sinov('id: ikkala post', cid(5) == 'pc:a301 mobile:a302', cid(5))
sinov('kanal_nomi', [bot.kanal_nomi(c) for c in (MOBILE, PC, CAMERA, '@boshqa')] == ['Mobile', 'PC', 'Camera', '@boshqa'])

print('2. To\'plam — har kanalga o\'zinikilar')
sahna(XARITA, elon(10, '2', 'camera'), elon(11, '2', 'camera'), elon(12, '1', 'pc'), elon(13, '3'), elon(14, '3'),
      elon(15, '1', 'olx'), elon(16, '2', 'camera', 'camera:a7'))
mid, xato, yub, otk = bot.kanal_toplam([10, 11, 12, 13, 14, 15, 16])
kanalga = dict(YUBORILDI)
sinov('Camera: bitta to\'plam (2 ta)', kanalga.get(CAMERA) == 'TOPLAM:10,11', str(kanalga))
sinov('PC: bittasi — oddiy post', kanalga.get(PC) == 'YAKKA:12:pc', str(kanalga))
sinov('Mobile: g\'iloflar to\'plami', kanalga.get(MOBILE) == 'TOPLAM:13,14', str(kanalga))
sinov('3 kanal, 3 post', len(YUBORILDI) == 3, str(YUBORILDI))
sinov('id\'lar kanali bilan', (cid(10), cid(11), cid(12), cid(13)) == ('camera:a300', 'camera:a300', 'pc:a300', 'mobile:a300'),
      str((cid(10), cid(12), cid(13))))
sinov('yuborildi', sorted(yub) == [10, 11, 12, 13, 14], str(yub))
sinov('OLX va posti borlar o\'tkazildi', sorted(o['num'] for o in otk) == [15, 16], str(otk))
sinov('javob — hamma kanal', sorted(bot.kanal_nomi(c) for c in bot.elon_kanallari(yub)) == ['Camera', 'Mobile', 'PC'])

sahna(XARITA, elon(20, '2', 'camera'), elon(21, '4'), elon(22, '1', 'pc'))
bot.kanal_toplam([20, 21, 22])
kanalga = dict(YUBORILDI)
sinov('ikki yo\'nalishli e\'lon — ikkala kanal to\'plamida', kanalga.get(PC) == 'TOPLAM:21,22' and kanalga.get(MOBILE) == 'YAKKA:21:mobile',
      str(kanalga))
sinov('ikki yo\'nalishli id', set(cid(21).split()) == {'mobile:a300', 'pc:a300'}, cid(21))

sahna(XARITA, elon(30, '3'), elon(31, '3'))
bot.kanal_toplam([30, 31])
sinov('hammasi Mobile — eski yo\'l, eski id', [c for c, _ in YUBORILDI] == [MOBILE] and cid(30) == 'a300' and cid(31) == 'a300',
      f'{YUBORILDI} {cid(30)}')

sahna(XARITA, elon(35, '2', 'camera'), elon(36, '1', 'pc'))
ISHLAMAYDI.add(CAMERA)
mid, xato, yub, otk = bot.kanal_toplam([35, 36])
sinov('bir kanal xato — ikkinchisi chiqadi', yub == [36] and cid(35) == '' and cid(36) == 'pc:a300', f'{yub} {cid(35)} {cid(36)}')
sinov('xato — o\'tkazildi va admin ogohlantiriladi', [o['num'] for o in otk] == [35] and any('chiqmadi' in a for a in ADMIN), f'{otk} {ADMIN}')
ISHLAMAYDI.add(PC)
for e in bot._ELON_CACHE['by_num'].values():
    e['channel_message_id'] = ''
mid, xato, yub, otk = bot.kanal_toplam([35, 36])
sinov('hamma kanal xato — mid yo\'q, xato bor', mid is None and xato and yub == [], f'{mid} {xato} {yub}')

print('3. Bir xil raqamli post boshqa kanalda — aralashmaydi')


def toqnash():
    sahna(XARITA, elon(40, '3', '', 'a300'), elon(41, '3', '', 'a300'), elon(42, '2', 'camera', 'camera:a300'),
          elon(43, '2', 'camera', 'camera:a300'), elon(44, '1', 'pc', 'pc:a300'))


toqnash()
bot.kanal_tahrir(42)
sinov('Camera to\'plami tahriri — faqat Camera, o\'z e\'lonlari', TAHRIR == [(CAMERA, 300, 'TOPLAM:42,43')], str(TAHRIR))
toqnash()
bot.kanal_tahrir(40)
sinov('Mobile to\'plami tahriri — faqat Mobile, o\'z e\'lonlari', TAHRIR == [(MOBILE, 300, 'TOPLAM:40,41')], str(TAHRIR))
toqnash()
bot.kanal_tahrir(44)
sinov('PC yakka post to\'plam deb olinmaydi', TAHRIR == [(PC, 300, 'YAKKA:44:pc')], str(TAHRIR))
toqnash()
bot.kanal_ochir(42)
sinov('to\'plamdan chiqish — post o\'chmaydi, qayta yasaladi', not OCHIRILDI and TAHRIR == [(CAMERA, 300, 'TOPLAM:43')],
      f'{OCHIRILDI} {TAHRIR}')
sinov('faqat o\'zining id\'si tozalandi', cid(42) == '' and cid(43) == 'camera:a300' and cid(40) == 'a300')
toqnash()
bot.kanal_ochir(44)
sinov('yakka post — faqat o\'z kanalidan o\'chadi', OCHIRILDI == [(PC, 300)] and cid(44) == '', str(OCHIRILDI))
sahna(XARITA, elon(45, '2', 'camera', 'camera:a300'))
bot.kanal_tahrir(45)
sinov('to\'plamda yolg\'iz qolgan — oddiy post', TAHRIR == [(CAMERA, 300, 'YAKKA:45:camera')], str(TAHRIR))
toqnash()
KEYINGI[CAMERA] = 400   # yangi post boshqa raqam oladi — Telegram ham shunday
bot.kanal_yana_keldi(42)
sinov('qayta yuborish: yangi post Camera\'ga', [c for c, _ in YUBORILDI] == [CAMERA], str(YUBORILDI))
sinov('qayta yuborish: eski to\'plam qayta yasaladi, o\'chmaydi', TAHRIR == [(CAMERA, 300, 'TOPLAM:43')] and not OCHIRILDI,
      f'{TAHRIR} {OCHIRILDI}')
sahna(XARITA, elon(46, '2', 'camera', 'camera:a300'))
bot.kanal_yana_keldi(46)
sinov('yakka post qayta: eskisi o\'z kanalidan o\'chadi', OCHIRILDI == [(CAMERA, 300)], str(OCHIRILDI))
sahna(XARITA, elon(47, '4', '', 'mobile:a300 pc:a300'), elon(48, '1', 'pc', 'pc:a300'))
bot.kanal_tahrir(47)
sinov('bir kanalda to\'plam, boshqasida yakka — har post o\'z ko\'rinishida',
      sorted(TAHRIR) == sorted([(MOBILE, 300, 'YAKKA:47:mobile'), (PC, 300, 'TOPLAM:47,48')]), str(TAHRIR))

print('4. Eski postlar va env yo\'q holat')
sahna(XARITA, elon(50, '1', 'mobile', 'a1050'), elon(51, '3', '', 'a1051'), elon(52, '3', '', 'mobile:a1052'))
sinov('eski «a1050» — Mobile\'da', bot.kanal_postlar(bot._ELON_CACHE['by_num']['50']) == [(None, MOBILE, 1050)])
sinov('eski g\'ilof «a1051» — to\'plam', bot.toplam_postmi(bot._ELON_CACHE['by_num']['51'], MODELS))
sinov('g\'ilof alohida posti «mobile:a1052» — to\'plam emas', not bot.toplam_postmi(bot._ELON_CACHE['by_num']['52'], MODELS))
bot.kanal_tahrir(51)
sinov('eski to\'plam tahriri — Mobile\'da', TAHRIR == [(MOBILE, 1051, 'TOPLAM:51')], str(TAHRIR))
sinov('faqat id biladigan eski tugma — Mobile\'dagi post', [e['num'] for e in bot._mid_elonlar(1050, hammasi=True)[0]] == [50])

sahna('', elon(60, '2', 'camera'), elon(61, '1', 'pc'))
bot.kanal_toplam([60, 61])
sinov('env yo\'q — bitta to\'plam, bitta kanal', [c for c, _ in YUBORILDI] == [bot.POST_CHANNEL] and cid(60) == 300 and cid(61) == 300,
      f'{YUBORILDI} {cid(60)}')
sahna(MOBILE, elon(62, '2', 'camera'), elon(63, '1', 'pc'))
bot.kanal_toplam([62, 63])
sinov('bitta kanal yozilgan — hammasi o\'sha kanalda', [c for c, _ in YUBORILDI] == [MOBILE] and cid(62) == 'a300', f'{YUBORILDI} {cid(62)}')
sahna(XARITA)
sinov('test kanal o\'zgarmadi', bot.kanal_tanla('richtest') == bot.TEST_CHANNEL)
sinov('katalog — umumiy kanalda', bot.kanal_tanla('katalog') == MOBILE)

print('5. Sayt javobi va /toplam')


class So:
    def __init__(self, d):
        self.d = d

    async def json(self):
        return self.d


bot.check_init_data = lambda x: bot.ADMIN_ID


def chaqir(f, d):
    return json.loads(asyncio.run(f(So(d))).text)


sahna(XARITA, elon(70, '2', 'camera'), elon(71, '4'), elon(72, '2', 'camera'), elon(73, '1', 'pc'))
j = chaqir(bot.kanal_post_endpoint, {'initData': 'x', 'num': 70, 'yonalish': 'camera'})
sinov('«📣 Kanalga» — Camera', j.get('kanallar') == ['Camera'] and j.get('kanal') == CAMERA, str(j))
sinov('adminga kanal nomi', any('Camera' in a for a in ADMIN), str(ADMIN))
j = chaqir(bot.kanal_post_endpoint, {'initData': 'x', 'num': 71, 'yonalish': ''})
sinov('ikki yo\'nalishli — ikki kanal nomi', j.get('kanallar') == ['Mobile', 'PC'], str(j))
j = chaqir(bot.kanal_toplam_endpoint, {'initData': 'x', 'nums': [72, 73]})
sinov('«📣 Yuborish» — ikki kanal nomi', sorted(j.get('kanallar') or []) == ['Camera', 'PC'], str(j))

sahna(XARITA, elon(80, '3', 'camera'), elon(81, '3', 'camera'))
bot._KANAL_KUTMOQDA['k'] = {'tur': 'toplam', 'html': 'x', 'nums': [80, 81]}
bot.kanal_tasdiq(1, 'k', True)
sinov('/toplam — yo\'nalish kanaliga', [c for c, _ in YUBORILDI] == [CAMERA] and cid(80) == 'camera:a300', f'{YUBORILDI} {cid(80)}')
sinov('/toplam javobida kanal', any('Camera' in a for a in ADMIN), str(ADMIN))

print(f'\n{NATIJA[0]} ✓, {NATIJA[1]} ✗')
sys.exit(1 if NATIJA[1] else 0)
