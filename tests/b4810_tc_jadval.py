"""4810: TashComp matni (_tc_tg_html) — xarakteristika jadvali har qatori alohida qatorda («nom: qiymat»), yopishmaydi.
python tests/b4810_tc_jadval.py → «OK»"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bot  # noqa: E402

jadval = bot._rich_table('• Ekran: 6.8 dyum\n• Protsessor: Tensor G5', '• Экран: 6.8\n• Процессор: G5')
m = bot._tc_tg_html('<p><strong>Pixel</strong></p>' + jadval + '<p>Narx</p>')
q = m.split('\n')
assert '<b>Ekran</b>: 6.8 dyum' in q and '<b>Protsessor</b>: Tensor G5' in q, m
assert '<b>Экран</b>: 6.8' in q and '<b>Процессор</b>: G5' in q, m
i = q.index('<b>Protsessor</b>: Tensor G5')
assert q[i + 1] == '' and q[i + 2] == '<b>Экран</b>: 6.8', m          # uz / ru orasida bo'sh qator
assert '<t' not in m and ' ' not in m, m
assert m.startswith('<b>Pixel</b>') and m.endswith('Narx'), m
print('OK')
