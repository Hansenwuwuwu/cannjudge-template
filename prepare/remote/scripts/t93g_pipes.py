import csv
import glob
import os
import statistics
import sys

root = sys.argv[1]
dirs = []
for d in glob.glob(os.path.join(root, 'OPPROF_*', '*', '*')):
    b = os.path.basename(d)
    if b.isdigit():
        dirs.append((int(b), d))
dirs = sorted(dirs)

COLS = [
    ('dur', 'Task Duration(us)', 'OpBasicInfo'),
    ('aic', 'aic_time(us)', 'PipeUtilization'),
    ('cube', 'aic_cube_time(us)', 'PipeUtilization'),
    ('fix', 'aic_fixpipe_time(us)', 'PipeUtilization'),
    ('a_scl', 'aic_scalar_time(us)', 'PipeUtilization'),
    ('a_m1', 'aic_mte1_time(us)', 'PipeUtilization'),
    ('a_m2', 'aic_mte2_time(us)', 'PipeUtilization'),
    ('aiv', 'aiv_time(us)', 'PipeUtilization'),
    ('vec', 'aiv_vec_time(us)', 'PipeUtilization'),
    ('v_scl', 'aiv_scalar_time(us)', 'PipeUtilization'),
    ('v_m2', 'aiv_mte2_time(us)', 'PipeUtilization'),
    ('v_m3', 'aiv_mte3_time(us)', 'PipeUtilization'),
]

rows = []
for idx, d in dirs:
    vals = {'launch': idx}
    for key, col, kind in COLS:
        f = glob.glob(os.path.join(d, kind + '_*.csv'))
        if not f:
            vals[key] = None
            continue
        with open(f[0], newline='', encoding='utf-8-sig') as fh:
            data = list(csv.DictReader(fh))
        if kind == 'OpBasicInfo':
            try:
                vals[key] = float(data[0][col])
            except Exception:
                vals[key] = None
        else:
            vs = []
            for r in data:
                try:
                    vs.append(float(r[col]))
                except Exception:
                    pass
            vals[key] = max(vs) if vs else None
    rows.append(vals)

print('%7s' % 'launch' + ''.join('%8s' % k for k, _, _ in COLS))
for v in rows:
    print('%7d' % v['launch'] + ''.join('%8s' % ('%.2f' % v[k] if v[k] is not None else 'NA')
                                        for k, _, _ in COLS))
tail = rows[-4:]
med = []
for k, _, _ in COLS:
    vs = [v[k] for v in tail if v[k] is not None]
    med.append('%8.2f' % statistics.median(vs) if vs else '%8s' % 'NA')
print('%7s' % 'median' + ''.join(med))
