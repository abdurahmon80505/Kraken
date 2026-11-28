"""4814: TashComp / Madina matni (_tc_tg_html) — xarakteristika va izoh kanal postidagidek yig'ilgan blokda
(<blockquote expandable>), sarlavha — blokning 1-qatori; 4810/4811 qatorlari blok ichida saqlanadi.
python tests/b4814_tc_yigilgan.py → «OK»"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

jadval = bot._rich_table('• Ekran: 6.8 dyum\n• Protsessor: Tensor G5', '• Экран: 6.8\n• Процессор: G5')
rich = ('<p><b>📱 Pixel</b><br/>#phone #223</p><details><summary>📋 Texnik xarakteristika / Характеристики</summary>'
        + jadval + '</details>' + bot.izoh_html({'izoh': 'Ekran singan'}) + '<p>Holati: <b>Yaxshi</b></p><p>Narx</p>')
m = bot._tc_tg_html(rich)
assert m.count('<blockquote expandable>') == m.count('</blockquote>') >= 1, m
b = m.split('<blockquote expandable>')[1].split('</blockquote>')[0]
assert b.startswith('<b>📋 Texnik xarakteristika / Характеристики</b>\n'), m
q = b.split('\n')
assert '<b>Ekran</b>: 6.8 dyum' in q and '<b>Protsessor</b>: Tensor G5' in q and '<b>Процессор</b>: G5' in q, m   # 4810
i = q.index('<b>Protsessor</b>: Tensor G5')
assert q[i + 1] == '' and q[i + 2] == '<b>Экран</b>: 6.8', m
assert 'Ekran</b>' not in m.split('<blockquote expandable>')[0], m        # ro'yxat blok tashqarisida emas
if bot.izoh_matni({'izoh': 'Ekran singan'}, 'uz'):
    assert '</blockquote>\n\n<blockquote expandable>📝 Izoh' in m, m      # izoh — o'z bloki
assert '</blockquote>\n\nHolati' in m and m.startswith('<b>📱 Pixel</b>'), m    # 4811: yopishmaydi
assert '\x01' not in m and '\x02' not in m and '<t' not in m and '<details' not in m, m
# sig'masa — oddiy matn, teg qolmaydi
d = bot._tc_tg_html(rich, chegara=60)
assert '<' not in d and '\x01' not in d, d
print('OK')
