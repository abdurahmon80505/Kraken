"""3428: TashkentComp tarqatish — avto bo'lim, navbat tartibi, haftalik chegara, sotilgan chiqmaydi, jadval vaqti,
TashkentComp'da bot jim, yuborish aniq mavzuga (mavzusiz qayta yuborish yo'q), 1 ta sinovdan keyin to'xtash.
python tests/b3428_tashco.py → «OK»"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

bot._ELON_CACHE['turkumlar'] = [
    {'key': 'keyboard', 'labelUz': 'Klaviaturalar', 'type': 'accessory'},
    {'key': 'phone', 'labelUz': 'Smartfonlar', 'type': 'phone'},
    {'key': 'cam', 'labelUz': 'Kameralar', 'type': 'camera'},
]
bot._ELON_CACHE['series'] = [
    {'key': 'kb', 'turkum': 'keyboard'}, {'key': 'px', 'turkum': 'phone'}, {'key': 'boshqa', 'type': 'aksessuar'},
    {'key': 'cm', 'turkum': 'cam'}, {'key': 'pcq', 'type': 'part', 'yonalish': 'pc'},
]
models = {'1': {'series': 'kb'}, '4': {'series': 'px'}, '5': {'series': 'boshqa'}, '6': {'series': 'cm'},
          '7': {'series': 'pcq'}}


def e(num, spec, nom, **k):
    return dict({'num': num, 'specId': spec, 'nameUz': nom, 'price': '10', 'status': 'active'}, **k)


avto = [
    (e(1, '1', 'Apex Pro'), 'periferiya'),
    (e(2, '4', 'Pixel 9'), 'telefon'),
    (e(3, '5', 'Surface Book 2'), 'noutbuk'),
    (e(4, '5', 'Arctis quloqchin'), 'periferiya'),
    (e(5, '5', 'Anker kabel'), 'aksessuar'),
    (e(6, '6', 'Sony A7'), 'foto'),
    (e(7, '7', 'RTX 3060'), 'jihoz'),
    (e(8, '5', 'Dell monitor 27"'), 'monitor'),
    (e(9, '5', 'Samsung SSD 1TB'), 'jihoz'),
]
for el, k in avto:
    assert bot.tashco_avto(el, models) == k, (el['nameUz'], bot.tashco_avto(el, models), k)

# navbat: faqat belgilangan + faol; sotilgan / kutilgan — yo'q; haftada bir marta
h = bot._tc_sukut()
by = {'10': e(10, '4', 'A', tashco='telefon'), '11': e(11, '4', 'B', tashco='telefon'),
      '12': e(12, '4', 'C', tashco='telefon', status='sold'), '13': e(13, '4', 'D'),
      '14': e(14, '4', 'E', tashco='yolgon'), '15': e(15, '5', 'F', tashco='aksessuar'),
      '16': e(16, '4', 'G', tashco='telefon', price='0', status='')}
h['log']['11'] = time.time() - 3 * 86400          # 3 kun oldin — hali mumkin emas
nv = bot.tashco_navbat(h, by)
assert [x[2] for x in nv['telefon']] == ['10'], nv['telefon']
assert [x[2] for x in nv['aksessuar']] == ['15']
h['log']['11'] = time.time() - 8 * 86400          # 8 kun — yana mumkin, lekin hech yuborilmagani oldin
assert [x[2] for x in bot.tashco_navbat(h, by)['telefon']] == ['10', '11']

# tanlash: bugun eng kam yuborilgan bo'lim; o'chirilgan / kunlik chegarasi to'lgani — o'tkaziladi
nv = bot.tashco_navbat(h, by)
bot._tc_bugun(h)['b'] = {'telefon': 1}
assert bot.tashco_tanla(h, nv) == ('15', 'aksessuar')
h['b']['aksessuar']['on'] = 0
assert bot.tashco_tanla(h, nv) == ('10', 'telefon')
h['b']['telefon']['n'] = 1
assert bot.tashco_tanla(h, nv) is None

# jadval vaqti: 5 ta, 09–21 → 10:12, 12:36, 15:00, 17:24, 19:48
h2 = bot._tc_sukut()
assert [bot._tc_soat(x) for x in bot._tc_slotlar(h2)] == ['10:12', '12:36', '15:00', '17:24', '19:48']

# tozalash: noto'g'ri holat — sukut / chegarada
t = bot._tc_tozala({'kun': 99, 'bosh': 22, 'oxir': 5, 'b': {'telefon': {'on': 0, 'n': 50, 'u': 'b'}, 'yoq_bolim': {}}})
assert t['kun'] == 20 and (t['bosh'], t['oxir']) == (9, 21) and t['b']['telefon'] == {'on': 0, 'n': 20, 'u': 'b'}
assert 'yoq_bolim' not in t['b']

# TashkentComp'dan kelgan xabar — bot jim (username katta-kichik harf farqsiz)
assert bot.tashco_guruhmi({'id': -100, 'username': 'tashkentcomp'})
assert not bot.tashco_guruhmi({'id': -100, 'username': 'boshqa'}) and not bot.tashco_guruhmi({})
so_rov = []


class R:
    status_code = 200
    text = '{}'

    def json(self):
        return {'ok': True, 'result': {'message_id': 77}}


bot.req._asl.post = lambda url, **kw: so_rov.append((url.rsplit('/', 1)[-1], kw.get('json'))) or R()
asyncio.run(bot.handle_update({'message': {'text': '/start', 'chat': {'id': -1001, 'type': 'supergroup',
                                                                      'username': 'TashkentComp'},
                                           'from': {'id': 5}}}))
asyncio.run(bot.handle_update({'callback_query': {'id': '1', 'data': 'yon:mobile', 'from': {'id': 5},
                                                  'message': {'chat': {'id': -1001, 'username': 'TashkentComp'}}}}))
assert not so_rov, so_rov

# yuborish: aniq mavzu, oddiy chat (Joy emas) — mavzu xatosida General'ga ketmaydi
bot._ELON_CACHE['by_num'] = {'15': by['15'], '12': by['12']}
bot._ELON_CACHE['models'] = models
bot._ELON_CACHE['time'] = time.time()
bot._TC_JOY['h'] = bot._tc_sukut()
bot.kanal_rich = lambda elon, models, kollaj=False, yonalish=None: ('<p>x</p>', None, [])
mid, usul, kalit, xato = bot.tashco_yubor('15')
assert (mid, usul, kalit) == (77, 'b', 'aksessuar'), (mid, usul, kalit, xato)
usl, j = so_rov[-1]
assert usl == 'sendRichMessage' and j['chat_id'] == '@TashkentComp' and j['message_thread_id'] == 917420, j
assert not isinstance(j['chat_id'], bot.Joy)
n = len(so_rov)
assert bot.tashco_yubor('12')[0] is None and len(so_rov) == n, 'sotilgan — yuborilmaydi'
assert bot.tashco_link(77) == 'https://t.me/TashkentComp/77'

# 1 ta sinovdan keyin — Owner «Ko'rdim» demaguncha ikkinchisi yo'q, avtomat yoqilmaydi
bot.tashco_saqla = lambda: True
bot.tashco_panel = lambda yangi=False: True
bot._TC_JOY['yuklandi'] = True
bot.tashco_tugma(0, 'tc:yoq')
assert not bot._TC_JOY['h']['yoq'], 'sinovsiz yoqilmasin'
bot.tashco_tugma(0, 'tc:kor')
assert not bot._TC_JOY['h']['korildi'], "sinov yuborilmasdan «Ko'rdim» ishlamasin"
bot._ELON_CACHE['by_num'] = {'15': by['15']}
bot.tashco_bir()
assert bot._TC_JOY['h']['sinov'].get('mid') == 77, bot._TC_JOY['izoh']
n = len(so_rov)
bot.tashco_bir()
assert len(so_rov) == n and 'allaqachon' in bot._TC_JOY['izoh'], 'ikkinchisi ketmasin'
bot.tashco_tick()
assert len(so_rov) == n, "Ko'rdim'siz avtomat ketmasin"
bot.tashco_tugma(0, 'tc:kor')
bot.tashco_tugma(0, 'tc:yoq')
assert bot._TC_JOY['h']['korildi'] and bot._TC_JOY['h']['yoq']
# avtomat: oxirgi yuborilgandan 30 daqiqa o'tmagan — kutadi
bot._ELON_CACHE['by_num'] = {'15': by['15'], '10': by['10']}
bot._TC_JOY['h']['bosh'], bot._TC_JOY['h']['oxir'] = 0, 24
bot._tc_soniya = lambda: 86000   # 23:53 — barcha slot o'tgan (sinov soatga bog'liq bo'lmasin)
bot.tashco_tick()
assert len(so_rov) == n, '30 daqiqa ichida ikkinchisi ketmasin'
bot._TC_JOY['h']['oxirgi'][-1][0] -= 3600
bot.tashco_tick()
assert len(so_rov) == n + 1 and so_rov[-1][1]['message_thread_id'] == 908147, so_rov[-1]
assert bot._TC_JOY['h']['log'].get('10')
print('OK')
