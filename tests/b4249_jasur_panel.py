"""4249: Boss ilovasidagi Jasur paneli — /tashco/jasur amallari panel / boshqar / belgi; pauza Jasurga ish bermaydi.
python tests/b4249_jasur_panel.py → «OK»"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402


def e(num, nom, **k):
    return dict({'num': num, 'specId': '', 'nameUz': nom, 'price': '10', 'status': 'active'}, **k)


by = {'10': e(10, 'Pixel 9', tashco='telefon'), '11': e(11, 'Sony A7', tashco='foto'),
      '12': e(12, 'Sotilgan', tashco='telefon', status='sold'), '13': e(13, 'Belgisiz'),
      '14': e(14, 'Hech qachon', tashco='yoq')}
bot._ELON_CACHE['by_num'] = by
bot._ELON_CACHE['models'] = {'0': {}}
bot._ELON_CACHE['time'] = time.time()
saqlandi = []
bot.tashco_saqla = lambda: saqlandi.append(1)
bot._TC_JOY.update({'h': bot._tc_sukut(), 'yuklandi': True, 'izoh': ''})
h = bot._TC_JOY['h']
h['log']['11'] = time.time() - 86400          # kecha yuborilgan — navbatda emas

# holat: faqat faol va bo'limli belgilar, navbatdagisi oldin
p = bot.tashco_boss_holat()
assert p['ok'] and not p['pauza'] and p['bugun'] == 0 and p['kun'] == 5, p
assert [x['num'] for x in p['belgili']] == [10, 11], p['belgili']
assert p['belgili'][0]['n'] and not p['belgili'][1]['n']
assert p['navbatdagi'] == 10 and p['ish'] is None and p['keyingi'] == 0
assert p['belgili'][0]['nom'] == 'Pixel 9'

# pauza: «1 ta yuborish» ishlamaydi, mavjud ish Jasurga berilmaydi, kut ulanishi uyg'onmaydi
r = bot.tashco_boshqar('pauza')
assert r['ok'] and h['pauza'] and saqlandi, r
r = bot.tashco_boshqar('bir')
assert not r['ok'] and 'pauza' in r['izoh'] and not h['ish'], r
bot._tc_ish_qoy(h, 10, 'telefon', 'bir')
assert not bot._tc_ish_kutyapti()
assert bot.tashco_ish_ber() == {'ok': True, 'ish': None}
assert h['ish']['holat'] == 'kut'            # ish o'chmadi — davomda beriladi
r = bot.tashco_boshqar('davom')
assert r['ok'] and not h['pauza']
assert bot._tc_ish_kutyapti()
h['ish'] = {}

# bir: ish qo'yiladi (ok); ikkinchi marta — kutadi (ok emas)
r = bot.tashco_boshqar('bir')
assert r['ok'] and h['ish'].get('num') == 10, r
r = bot.tashco_boshqar('bir')
assert not r['ok'] and r['izoh'].startswith('⏳'), r
h['ish'] = {}

# kor: sinov e'loni yo'q — xato; bor — korildi
r = bot.tashco_boshqar('kor')
assert not r['ok'] and not h['korildi']
h['sinov'] = {'num': 10, 'mid': 555, 'ts': 1}
assert bot.tashco_boss_holat()['sinov'].endswith('/555')
r = bot.tashco_boshqar('kor')
assert r['ok'] and h['korildi'] and bot.tashco_boss_holat()['sinov'] == ''
assert not bot.tashco_boshqar('yoq')['ok']   # panel faqat 4 buyruq

# 30 daqiqa oralig'i: keyingi vaqt ko'rinadi
h['oxirgi'] = [[int(time.time()) - 600, 11, 'foto', 777, 'b']]
p = bot.tashco_boss_holat()
assert p['keyingi'] > time.time() and p['oxirgi'][0]['num'] == 11, p

# belgi: qo'yish, avto, olib tashlash; noto'g'ri qiymat — jadvalga yozilmaydi
yozildi = []
bot._sheets_update = lambda d: yozildi.append(d) or True
assert not bot.tashco_belgi('abc', 'telefon')['ok'] and not bot.tashco_belgi('13', 'yolgon')['ok'] and not yozildi
r = bot.tashco_belgi('13', 'monitor')
assert r['ok'] and yozildi[-1] == {'num': 13, 'tashco': 'monitor'} and by['13']['tashco'] == 'monitor', r
r = bot.tashco_belgi('13', '')
assert r['ok'] and by['13']['tashco'] == '' and 'olindi' in r['izoh']
r = bot.tashco_belgi('13', 'avto')
assert r['ok'] and r['b'] in bot.TASHCO_NOM, r
bot._sheets_update = lambda d: False
assert not bot.tashco_belgi('13', 'foto')['ok']

# saqlangan holatdan pauza qaytadi
assert bot._tc_tozala({'pauza': 1})['pauza'] is True and bot._tc_tozala({})['pauza'] is False
print('OK')
