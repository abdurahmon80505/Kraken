"""3422: aksessuar posti — tur bo'yicha emoji / heshteg, izoh xarakteristika ostida (yig'ilgan blok).
python tests/b3422_aksessuar_post.py → «OK»"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

bot._ELON_CACHE['turkumlar'] = [
    {'key': 'keyboard', 'labelUz': 'Klaviaturalar', 'type': 'accessory'},
    {'key': 'headphones', 'labelUz': 'Naushniklar', 'type': 'accessory'},
    {'key': 'cable', 'labelUz': 'Kabellar', 'type': 'accessory'},
    {'key': 'phone', 'labelUz': 'Smartfonlar', 'type': 'phone'},
]
bot._ELON_CACHE['series'] = [
    {'key': 'kb', 'turkum': 'keyboard'}, {'key': 'hp', 'turkum': 'headphones'}, {'key': 'cb', 'turkum': 'cable'},
    {'key': 'px', 'turkum': 'phone'}, {'key': 'boshqa', 'type': 'aksessuar'},
]
models = {'1': {'series': 'kb', 'specUz': '• Turi: mexanik', 'specRu': '• Тип: механическая'},
          '2': {'series': 'hp'}, '3': {'series': 'cb'}, '4': {'series': 'px'}, '5': {'series': 'boshqa'}}


def e(num, spec, nom, izoh=''):
    return {'num': num, 'specId': spec, 'nameUz': nom, 'izoh': izoh, 'izohRu': 'Примечание' if izoh else '',
            'price': '10', 'status': 'active', 'condition': 'used', 'images': ''}


kutilgan = [
    (e(1, '1', 'Apex Pro'), ('accessory', '⌨️', 'keyboard')),
    (e(2, '2', 'Arctis'), ('accessory', '🎧', 'headset')),
    (e(3, '3', 'Razer USB kabel'), ('accessory', '🔌', 'cable')),
    (e(4, '4', 'Pixel 9'), ('phone', '📱', 'phone')),
    (e(5, '5', 'Arctis Nova Pro White'), ('accessory', '🎧', 'headset')),        # turkumsiz — nomdan
    (e(6, '5', 'QcK sichqoncha gilamchasi'), ('accessory', '🖱', 'mousepad')),   # sichqoncha emas
    (e(7, '5', '3D LED tungi chiroq — quloqchin'), ('accessory', '💡', 'lamp')),  # quloqchin emas
    (e(8, '5', 'Surface Book 2 128GB SSD'), ('accessory', '💻', 'laptop')),       # disk emas
    (e(9, '5', 'Nomaʼlum narsa'), ('accessory', '🧩', 'accessory')),
]
for el, k in kutilgan:
    assert bot.tur_belgisi(el, models) == k, (el['nameUz'], bot.tur_belgisi(el, models), k)

h = bot.build_rich_html(e(1, '1', 'Apex Pro', 'OLED, simli'), models, premium=False)
sarlavha = h.split('</p>', 1)[0]
assert '⌨️ Apex Pro' in sarlavha and '#keyboard #1' in sarlavha, sarlavha
assert 'OLED' not in sarlavha and '📝' not in sarlavha, 'izoh nom tagida qolmasin'
assert '#accessory' not in h
i_spec, i_izoh = h.index('Texnik xarakteristika'), h.index('<blockquote expandable>📝 Izoh')
assert i_spec < i_izoh < h.index('Holati'), 'izoh — xarakteristikadan keyin, holatdan oldin'
blok = h[i_izoh:h.index('</blockquote>', i_izoh)]
assert 'OLED, simli' in blok and 'Примечание' in blok and 'mexanik' not in blok, blok
assert '<blockquote' not in bot.build_rich_html(e(1, '1', 'Apex Pro'), models, premium=False), 'izohsiz — blok yo\'q'

_, matn, ent = bot.build_elon(e(1, '1', 'Apex Pro', 'OLED, simli'), models)
assert matn.startswith('⌨️ Apex Pro') and '#keyboard #1' in matn, matn[:60]
assert matn.index('Texnik') < matn.index('📝 Izoh') < matn.index('Holati'), matn
assert sum(1 for x in ent if x['type'] == 'expandable_blockquote') == 2
print('OK')
