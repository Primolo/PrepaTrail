#!/usr/bin/env python3
"""
generate.py — Lit Activities.csv, calcule l'historique complet,
génère index.html avec les données embarquées.
Lancé par GitHub Action à chaque push du CSV.
"""

import csv
import json
import sys
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

# ── Constantes plan ───────────────────────────────────────────────────────────
PLAN_START  = datetime(2026, 3, 23)   # Lundi S1
RACE_DATE   = datetime(2026, 7, 12)   # UTOPIC
RACE_UTMJ   = datetime(2026, 10, 11)  # UTMJ (premier dimanche d'octobre)

WEEK_TARGETS = {
    1:  dict(km=(35,45),  dp=(500,800),   fc_long=148, nb=4),
    2:  dict(km=(40,50),  dp=(650,950),   fc_long=148, nb=4),
    3:  dict(km=(43,53),  dp=(780,1100),  fc_long=148, nb=4),
    4:  dict(km=(28,40),  dp=(400,640),   fc_long=150, nb=4, recup=True),
    5:  dict(km=(43,55),  dp=(850,1150),  fc_long=152, nb=4),
    6:  dict(km=(47,58),  dp=(950,1300),  fc_long=152, nb=4),
    7:  dict(km=(52,64),  dp=(1100,1500), fc_long=152, nb=4),
    8:  dict(km=(34,44),  dp=(500,750),   fc_long=152, nb=4, recup=True),
    9:  dict(km=(80,105), dp=(1700,2300), fc_long=158, nb=5, choc=True),
    10: dict(km=(48,62),  dp=(1000,1400), fc_long=155, nb=4),
    11: dict(km=(56,70),  dp=(1200,1600), fc_long=155, nb=4),
    12: dict(km=(85,110), dp=(2400,3100), fc_long=160, nb=5, choc=True),
    13: dict(km=(52,66),  dp=(1300,1700), fc_long=155, nb=4),
    14: dict(km=(38,50),  dp=(550,800),   fc_long=152, nb=4, recup=True),
    15: dict(km=(22,32),  dp=(250,450),   fc_long=150, nb=4),
    16: dict(km=(8,16),   dp=(80,160),    fc_long=150, nb=4),
}

MOIS_FR = ['jan','fév','mar','avr','mai','juin','juil','août','sep','oct','nov','déc']

# ── Helpers ───────────────────────────────────────────────────────────────────
def week_bounds(n):
    start = PLAN_START + timedelta(weeks=n-1)
    end   = start + timedelta(days=6, hours=23, minutes=59)
    return start, end

def week_of(date):
    delta = (date - PLAN_START).days
    if delta < 0:
        return None
    w = delta // 7 + 1
    return w if 1 <= w <= 16 else None

def parse_num(v):
    if not v or v in ('--', '', 'N/A'):
        return 0.0
    try:
        return float(str(v).replace(',', '.'))
    except:
        return 0.0

# ── CSV parsing ───────────────────────────────────────────────────────────────
def detect_cols(headers):
    """Auto-detect column names regardless of Strava language."""
    h = [x.lower() for x in headers]
    def find(*patterns):
        for i, col in enumerate(h):
            for p in patterns:
                if p.lower() in col:
                    return headers[i]
        return None
    return {
        'date':  find('data', 'date'),
        'type':  find('tipo', 'activity type', 'type'),
        'title': find('titolo', 'activity name', 'title', 'nom'),
        'dist':  find('distanza', 'distance'),
        'elev':  find('ascesa', 'elevation gain', 'dénivelé', 'denivelé'),
        'fc':    find('fc media', 'avg hr', 'fc moy', 'fréquence cardiaque moy'),
        'fcmax': find('fc max', 'max hr', 'fréquence cardiaque max'),
        'time':  find('tempo', 'moving time', 'durée', 'temps'),
        'pace':  find('passo medio', 'avg pace', 'allure moy'),
    }

def load_activities(csv_path):
    activities = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        cols = detect_cols(headers)
        if not cols.get('date'):
            print(f"ERROR: Cannot detect date column in {csv_path}")
            return []
        for row in reader:
            t = row.get(cols['type'], '').lower()
            if not any(x in t for x in ['trail', 'run', 'cour']):
                continue
            try:
                date_str = row.get(cols['date'], '')
                date = datetime.fromisoformat(date_str[:19])
            except:
                continue
            activities.append({
                'date':  date.isoformat(),
                'type':  row.get(cols['type'], ''),
                'title': row.get(cols['title'], ''),
                'km':    parse_num(row.get(cols['dist'], 0)),
                'dp':    parse_num(row.get(cols['elev'], 0)),
                'fc':    parse_num(row.get(cols['fc'], 0)),
                'fcmax': parse_num(row.get(cols['fcmax'], 0)),
                'time':  row.get(cols['time'], ''),
                'pace':  row.get(cols['pace'], ''),
            })
    return activities

# ── Per-week stats ────────────────────────────────────────────────────────────
def compute_week_stats(activities):
    """Returns dict week_num -> {km, dp, nb, fc_long, fc_avg, acts, score, score_details}"""
    by_week = {}
    for act in activities:
        date = datetime.fromisoformat(act['date'])
        w = week_of(date)
        if w is None:
            continue
        if w not in by_week:
            by_week[w] = {'km':0, 'dp':0, 'nb':0, 'fc_sum':0, 'fc_count':0,
                          'fc_long':0, 'acts':[], 'long_km':0}
        s = by_week[w]
        s['km']  += act['km']
        s['dp']  += act['dp']
        s['nb']  += 1
        if act['fc'] > 0:
            s['fc_sum']   += act['fc']
            s['fc_count'] += 1
        if act['km'] > s['long_km']:
            s['long_km'] = act['km']
            s['fc_long'] = act['fc']
        s['acts'].append(act)

    # Add score per week
    for w, s in by_week.items():
        t = WEEK_TARGETS.get(w, WEEK_TARGETS[1])
        score = 0
        # km 0-25
        if s['km'] >= t['km'][0]:
            score += min(25, round(25 * (s['km'] - t['km'][0]) / max(1, t['km'][1] - t['km'][0])) + 15)
        # dp 0-25
        if s['dp'] >= t['dp'][0]:
            score += min(25, round(25 * (s['dp'] - t['dp'][0]) / max(1, t['dp'][1] - t['dp'][0])) + 15)
        # nb séances 0-25
        score += min(25, round(25 * s['nb'] / t['nb']))
        # FC 0-25
        if s['fc_long'] > 0:
            score += max(0, 25 - round(max(0, s['fc_long'] - t['fc_long']) * 1.5))
        else:
            score += 15
        s['score'] = min(100, score)
        s['fc_avg'] = round(s['fc_sum'] / s['fc_count']) if s['fc_count'] else 0

    return by_week

# ── Adaptive targets ──────────────────────────────────────────────────────────
def compute_adaptive_targets(by_week, current_week):
    """
    Analyse les 4 dernières semaines et adapte les cibles si besoin.
    Retourne un dict d'ajustements + alertes.
    """
    alerts = []
    adjustments = {}

    recent_weeks = [w for w in range(max(1, current_week-4), current_week) if w in by_week]
    if not recent_weeks:
        return adjustments, alerts

    # FC trend
    fc_vals = [by_week[w]['fc_long'] for w in recent_weeks if by_week[w]['fc_long'] > 0]
    if len(fc_vals) >= 2:
        fc_target = WEEK_TARGETS.get(current_week, {}).get('fc_long', 152)
        avg_fc = sum(fc_vals) / len(fc_vals)
        if avg_fc > fc_target + 8:
            adjustments['fc_adjust'] = round(avg_fc - fc_target)
            alerts.append({
                'type': 'fc_high',
                'level': 'ambre',
                'msg': f'FC systématiquement élevée ces {len(fc_vals)} dernières semaines (moy. {avg_fc:.0f} bpm vs cible &lt;{fc_target}). Les cibles de cette semaine ont été ajustées — priorité à ralentir sur les sorties longues.',
                'icon': '💓'
            })

    # D+ cumul retard
    planned_dp_cumul = sum(
        (WEEK_TARGETS.get(w, {}).get('dp', (0,0))[0] + WEEK_TARGETS.get(w, {}).get('dp', (0,0))[1]) / 2
        for w in range(1, current_week)
    )
    actual_dp_cumul = sum(by_week[w]['dp'] for w in by_week if w < current_week)
    retard_dp = planned_dp_cumul - actual_dp_cumul
    if retard_dp > 500:
        pct_retard = round(retard_dp / max(1, planned_dp_cumul) * 100)
        alerts.append({
            'type': 'dp_retard',
            'level': 'ambre' if pct_retard < 25 else 'rouge',
            'msg': f'D+ cumulé en retard de {int(retard_dp)} m ({pct_retard}% sous le plan). Chercher des sorties dominicales avec plus de dénivelé. Ne pas rattraper brutalement — +20% max par semaine.',
            'icon': '⛰'
        })
    elif retard_dp < -300:
        alerts.append({
            'type': 'dp_avance',
            'level': 'vert',
            'msg': f'D+ cumulé en avance de {abs(int(retard_dp))} m sur le plan. Excellente progression dénivelé !',
            'icon': '📈'
        })

    # Semaines consécutives incomplètes
    incomplete = [w for w in recent_weeks if by_week[w]['nb'] < WEEK_TARGETS.get(w, {}).get('nb', 4) - 1]
    if len(incomplete) >= 3:
        alerts.append({
            'type': 'incomplete_streak',
            'level': 'rouge',
            'msg': f'{len(incomplete)} semaines incomplètes sur les {len(recent_weeks)} dernières. Risque de sous-charge. Vérifier la récupération, le sommeil et la gestion du stress.',
            'icon': '⚠️'
        })

    # Score de forme 4 dernières semaines
    scores = [by_week[w]['score'] for w in recent_weeks]
    if scores:
        form_score = round(sum(scores) / len(scores))
        adjustments['form_score'] = form_score
        adjustments['form_trend'] = 'up' if len(scores) >= 2 and scores[-1] > scores[0] else 'down' if len(scores) >= 2 and scores[-1] < scores[0] else 'stable'

    return adjustments, alerts

# ── Main generation ───────────────────────────────────────────────────────────
def main():
    # Paths
    root = Path(__file__).parent.parent
    csv_path  = root / 'Activities.csv'
    tmpl_path = root / 'index_template.html'
    out_path  = root / 'index.html'

    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)
    if not tmpl_path.exists():
        print(f"ERROR: {tmpl_path} not found")
        sys.exit(1)

    print(f"Reading {csv_path}...")
    activities = load_activities(csv_path)
    print(f"  Found {len(activities)} trail activities")

    # Compute stats
    by_week = compute_week_stats(activities)
    print(f"  Weeks with data: {sorted(by_week.keys())}")

    # Current week
    today = datetime.now()
    current_week = week_of(today) or 1

    # Adaptive analysis
    adjustments, alerts = compute_adaptive_targets(by_week, current_week)
    print(f"  Alerts: {len(alerts)}, Adjustments: {adjustments}")

    # Build JSON payload to embed
    payload = {
        'generated_at': today.isoformat(),
        'csv_file': 'Activities.csv',
        'activities': activities,
        'by_week': {str(k): v for k, v in by_week.items()},
        'current_week': current_week,
        'alerts': alerts,
        'adjustments': adjustments,
        'cumul': {
            'km':  sum(a['km'] for a in activities),
            'dp':  sum(a['dp'] for a in activities),
            'nb':  len(activities),
        }
    }

    # Inject into template
    with open(tmpl_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Replace the renderRapport init — inject server-side data
    inject_script = f"""
<script id="server-data">
// Auto-generated by generate.py on {today.strftime('%d/%m/%Y %H:%M')}
window.TRAIL_DATA = {json.dumps(payload, ensure_ascii=False, default=str)};
</script>
"""
    # Insert before </head>
    html = html.replace('</head>', inject_script + '</head>', 1)

    # Also patch the renderRapport call to use server data if available
    old_render_call = 'function renderRapport() {\n  // Check if we have stored activities\n  const stored = localStorage.getItem(\'trailActivities\');'
    new_render_call = '''function renderRapport() {
  // Use server-injected data first (GitHub Action), then localStorage
  if (window.TRAIL_DATA && window.TRAIL_DATA.activities && window.TRAIL_DATA.activities.length > 0) {
    const td = window.TRAIL_DATA;
    const activities = td.activities.map(a => ({...a, date: new Date(a.date)}));
    // Update localStorage with fresh server data
    localStorage.setItem('trailActivities', JSON.stringify(td.activities));
    localStorage.setItem('trailLastImport', td.generated_at);
    localStorage.setItem('trailFileName', td.csv_file);
    showImportSuccess(td.csv_file + ' (mis à jour automatiquement)', activities.length);
    // Inject alerts + adjustments
    window.TRAIL_ALERTS = td.alerts || [];
    window.TRAIL_ADJ    = td.adjustments || {};
    generateRapport(activities);
    return;
  }
  // Check if we have stored activities
  const stored = localStorage.getItem('trailActivities');'''

    if old_render_call in html:
        html = html.replace(old_render_call, new_render_call, 1)
        print("  Patched renderRapport for server data")
    else:
        print("  WARNING: Could not patch renderRapport — using fallback")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated {out_path} ({out_path.stat().st_size // 1024} KB)")
    print(f"Done. {len(activities)} activities, weeks {sorted(by_week.keys())}")

if __name__ == '__main__':
    main()
