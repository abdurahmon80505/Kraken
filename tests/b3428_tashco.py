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
assert t['kun'] == 5 and (t['bosh'], t['oxir']) == (9, 21) and t['b']['telefon'] == {'on': 0, 'n': 5, 'u': 'b'}
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

# Jasur modeli: bot TashkentComp'ga o'zi yozmaydi — Jasurga ish beradi; 1 ta sinovdan keyin Owner «Ko'rdim» demaguncha to'xtaydi
bot.tashco_saqla = lambda: True
bot.tashco_panel = lambda yangi=False: True
bot._TC_JOY['yuklandi'] = True
bot.tashco_yukla = lambda: True
bot.kanal_manbalari = lambda elon: ['https://x/1.jpg']
bot.build_rich_html = lambda *a, **k: ('<p><b>Apex</b> 10$<br>Holati a\'lo</p><tg-slideshow><img src="x"></tg-slideshow>'
                                       '<tg-button-row><tg-button url="https://t.me/b?startapp=e15">🛒 Saytda</tg-button>'
                                       '</tg-button-row><a href="tel:+998">+998</a>')
assert bot._tc_amal('yoq') == (False, '') and not bot._TC_JOY['h']['yoq'], 'sinovsiz yoqilmasin'
assert bot._tc_amal('kor') == (False, '') and not bot._TC_JOY['h']['korildi'], "sinovsiz «Ko'rdim» ishlamasin"
bot._ELON_CACHE['by_num'] = {'15': by['15']}
n = len(so_rov)
bot.tashco_bir()
ish = bot._TC_JOY['h']['ish']
assert ish['num'] == 15 and ish['holat'] == 'kut' and len(so_rov) == n, (ish, bot._TC_JOY['izoh'])
bot.tashco_bir()
assert 'navbatida' in bot._TC_JOY['izoh'], 'navbatda ish bor — ikkinchisi qo\'yilmasin'
v = bot.tashco_ish_ber()['ish']
assert v['num'] == 15 and v['nishon'] == '@TashkentComp' and v['thread'] == 917420 and v['usul'] == 'b', v
assert v['rasmlar'] == ['https://x/1.jpg'] and '<b>Apex</b>' in v['matn'] and 'tg-' not in v['matn'], v['matn']
assert 'tel:' not in v['matn'] and '🔗 <a href="https://t.me/b?startapp=e15">' in v['matn'], v['matn']
assert bot.tashco_ish_ber()['ish'] is None, 'bitta ish ikki marta berilmasin'
assert not bot.tashco_natija('99', 5, 'b')['ok'], 'boshqa raqam natijasi qabul qilinmasin'
bot.tashco_natija('15', 501, 'b')
h = bot._TC_JOY['h']
assert h['sinov']['mid'] == 501 and not h['ish'] and bot._tc_bugun(h)['s'] == 1 and h['log'].get('15')
assert so_rov[-1][0] == 'sendMessage' and 'TashkentComp/501' in so_rov[-1][1]['text'], 'Owner lichkasiga havola'
bot.tashco_bir()
assert 'allaqachon' in bot._TC_JOY['izoh'] and not h['ish'], 'Ko\'rdim\'siz ikkinchisi yo\'q'
bot.tashco_tick()
assert not h['ish'], "Ko'rdim'siz avtomat yo'q"
assert bot._tc_amal('kor')[0] and bot._tc_amal('yoq')[0] and h['korildi'] and h['yoq']
# avtomat: 30 daqiqa oraliq, keyin Jasurga ish
bot._ELON_CACHE['by_num'] = {'15': by['15'], '10': by['10']}
h['bosh'], h['oxir'] = 0, 24
bot._tc_soniya = lambda: 86000
bot.tashco_tick()
assert not h['ish'], '30 daqiqa ichida ikkinchisi yo\'q'
h['oxirgi'][-1][0] -= 3600
bot.tashco_tick()
assert h['ish']['num'] == 10 and h['ish']['k'] == 'telefon', h['ish']
# xato natija — bugun qayta urinilmaydi; eskirgan ish bekor
bot.tashco_ish_ber()
bot.tashco_natija('10', None, 'b', 'CHAT_WRITE_FORBIDDEN')
assert not h['ish'] and h['log']['10'] > time.time() - bot.TASHCO_HAFTA and 'yuborilmadi' in bot._TC_JOY['izoh']
bot._tc_ish_qoy(h, 10, 'telefon', 'avto')
h['ish']['ts'] -= bot.TASHCO_ISH_KUT + 1
assert bot._tc_ish_eskir(h) and not h['ish']
bot._tc_ish_qoy(h, 10, 'telefon', 'avto')
h['ish'].update(holat='berildi', bt=time.time() - bot.TASHCO_ISH_BERILDI - 1)
assert bot._tc_ish_eskir(h) and not h['ish']
# kunlik chegara — 5 dan oshmaydi
assert bot._tc_tozala({'kun': 9})['kun'] == 5
for _ in range(9):
    bot._tc_amal('kun+')
assert h['kun'] <= 5
kb = bot._tc_bugun(h)
kb['s'] = h['kun']
h['oxirgi'][-1][0] -= 7200
bot.tashco_bir()
assert 'chegara' in bot._TC_JOY['izoh'] and not h['ish']

# Jasur endpoint — kalitsiz 401
import json as _j  # noqa: E402


class Rq:
    def __init__(self, d):
        self.d = d

    async def json(self):
        return self.d


bot.BOT_TOKEN = bot.BOT_TOKEN or 'sinov-token'
r = asyncio.run(bot.tashco_jasur_endpoint(Rq({'kalit': 'xato', 'amal': 'ol'})))
assert r.status == 401
r = asyncio.run(bot.tashco_jasur_endpoint(Rq({'kalit': bot.tashco_jasur_kalit(), 'amal': 'ol'})))
assert r.status == 200 and _j.loads(r.body)['ok']
assert len(bot.tashco_jasur_kalit()) == 32

# vidjet: holat ≤1024 B, HTML ≤32768 B va zlib ≤4096 B; widget_query — ALLOWED_UPDATES da
import zlib  # noqa: E402
h['oxirgi'] = [[int(time.time()), 10000 + i, 'telefon', 1234567, 'f'] for i in range(10)]
bot._TC_JOY['izoh'] = 'x' * 900
d = bot._tc_holat_json(h)
assert len(d.encode()) <= 1024 and _j.loads(d)['n'] == h['kun'], len(d.encode())
assert len(bot.TASHCO_VIDJET.encode()) <= 32768 and len(zlib.compress(bot.TASHCO_VIDJET.encode(), 9)) <= 4096
assert 'widget_query' in bot.ALLOWED_UPDATES
# widget_query: admin emas — javob bo'sh, amal yo'q
so_rov.clear()
asyncio.run(bot.tashco_vidjet_sorov({'id': 'q1', 'from': {'id': 5}, 'chat': {'id': 5}, 'message_id': 9, 'data': 'yoq'}))
assert so_rov[-1][0] == 'answerWidgetQuery' and 'data' not in so_rov[-1][1]
print('OK', len(zlib.compress(bot.TASHCO_VIDJET.encode(), 9)), 'B')
