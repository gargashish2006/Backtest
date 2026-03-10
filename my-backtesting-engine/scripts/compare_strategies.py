#!/usr/bin/env python3
import pandas as pd
import glob, os

out = 'strategies/outputs'
orig_files = sorted(glob.glob(os.path.join(out, 'industry_4q_10ind_3stocks_equity_*.csv')))
w52_files = sorted(glob.glob(os.path.join(out, 'industry_4q_10ind_3stocks_52w_equity_*.csv')))

if not orig_files:
    raise SystemExit('No original equity files found')
if not w52_files:
    raise SystemExit('No 52w equity files found')

orig = orig_files[-1]
w52 = w52_files[-1]


def metrics(file):
    df = pd.read_csv(file)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    else:
        df.rename(columns={df.columns[0]: 'date'}, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
    # equity column heuristics
    eq_col = None
    for c in ['equity', 'nav', 'portfolio_value', 'capital']:
        if c in df.columns:
            eq_col = c
            break
    if eq_col is None:
        eq_col = df.select_dtypes(include='number').columns[-1]
    df = df.sort_values('date')
    start = df[eq_col].iloc[0]
    end = df[eq_col].iloc[-1]
    total_return = end / start - 1
    days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    years = days / 365.25 if days > 0 else None
    cagr = (end / start) ** (1 / years) - 1 if years and years > 0 else None
    daily = df[eq_col].pct_change().dropna()
    ann_vol = daily.std() * (252 ** 0.5) if len(daily) > 1 else None
    run_max = df[eq_col].cummax()
    drawdown = df[eq_col] / run_max - 1
    mdd = drawdown.min()
    return {'file': os.path.basename(file), 'start': df['date'].iloc[0].strftime('%Y-%m-%d'), 'end': df['date'].iloc[-1].strftime('%Y-%m-%d'), 'total_return': total_return, 'cagr': cagr, 'ann_vol': ann_vol, 'max_drawdown': mdd}

m1 = metrics(orig)
m2 = metrics(w52)

print('Comparison: Original vs 52W')
print('')
print('Original:', m1['file'])
print('  period:', m1['start'], 'to', m1['end'])
print('  Total return: {:.1%}'.format(m1['total_return']))
print('  CAGR: {:.2%}'.format(m1['cagr']))
print('  Ann vol: {:.2%}'.format(m1['ann_vol']))
print('  Max drawdown: {:.1%}'.format(m1['max_drawdown']))
print('')
print('52W:', m2['file'])
print('  period:', m2['start'], 'to', m2['end'])
print('  Total return: {:.1%}'.format(m2['total_return']))
print('  CAGR: {:.2%}'.format(m2['cagr']))
print('  Ann vol: {:.2%}'.format(m2['ann_vol']))
print('  Max drawdown: {:.1%}'.format(m2['max_drawdown']))
