"""
Save a single 3×4 combined figure of annotation label distributions.

Follows the same data loading as save_distribution_pdfs.py (reads from
the three parquet files). Gold columns are the only annotation columns
currently present in those parquets.

Output: ./distribution_pdfs/combined_label_distributions.pdf
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

OUT_DIR = os.path.join(os.path.dirname(__file__), 'distribution_pdfs')
os.makedirs(OUT_DIR, exist_ok=True)

COLOR_AGENCY  = '#A8B78B'
COLOR_SETTING = '#D4B896'
COLOR_EVENT   = '#7BA8A8'

base = os.path.dirname(__file__)
setting_df = pd.read_parquet(os.path.join(base, 'setting_annotations.parquet'))
agency_df  = pd.read_parquet(os.path.join(base, 'agency_annotations.parquet'))
event_df   = pd.read_parquet(os.path.join(base, 'event_relation_annotations.parquet'))

SCALE_15 = [1, 2, 3, 4, 5]

# 11 panels in reference-figure order; 12th cell will be hidden
PANELS = [
    (agency_df,  'agency_focalization_gold',       COLOR_AGENCY,  SCALE_15, 'Rating (1–5)'),
    (agency_df,  'agency_emotion_gold',            COLOR_AGENCY,  SCALE_15, 'Rating (1–5)'),
    (agency_df,  'agency_cognition_gold',          COLOR_AGENCY,  SCALE_15, 'Rating (1–5)'),
    (agency_df,  'agency_change_of_state_gold',    COLOR_AGENCY,  SCALE_15, 'Rating (1–5)'),
    (agency_df,  'agency_conflict_gold',           COLOR_AGENCY,  SCALE_15, 'Rating (1–5)'),
    (setting_df, 'setting_concreteness_gold',      COLOR_SETTING, SCALE_15, 'Rating (1–5)'),
    (setting_df, 'setting_temporal_grounding_gold',COLOR_SETTING, SCALE_15, 'Rating (1–5)'),
    (setting_df, 'setting_spatial_grounding_gold', COLOR_SETTING, SCALE_15, 'Rating (1–5)'),
    (setting_df, 'setting_sensory_gold',           COLOR_SETTING, SCALE_15, 'Rating (1–5)'),
    (event_df,   'temporal_order_gold',            COLOR_EVENT,   None,     'Label'),
    (event_df,   'causality_rating_gold',          COLOR_EVENT,   None,     'Label'),
]

LABEL_ABBREV = {
    'same_event':       'same\nevent',
    'simultaneous':     'simult.',
    'span1_first':      'span1\nfirst',
    'span2_first':      'span2\nfirst',
    'too_hard_to_tell': 'too\nhard',
    'direct_cause':     'direct\ncause',
    'enables':          'enables',
    'not_related':      'not\nrelated',
}


def short_title(col):
    return (col
            .replace('_gold', '')
            .replace('agency_', '')
            .replace('setting_', '')
            .replace('_', ' ')
            .title())


sns.set_theme(style='whitegrid', font_scale=1.05)
plt.rcParams['figure.dpi'] = 120

fig, axes = plt.subplots(3, 4, figsize=(14, 9))

for i, (df, col, color, scale, xlabel) in enumerate(PANELS):
    ax = axes.flat[i]
    series = pd.to_numeric(df[col], errors='coerce') if scale else df[col]
    n = int(series.notna().sum())

    if scale:
        counts = series.value_counts().reindex(scale, fill_value=0)
        ax.bar(counts.index, counts.values, color=color, edgecolor='white', width=0.6)
        ax.set_xticks(scale)
    else:
        counts = series.value_counts().sort_index()
        tick_labels = [LABEL_ABBREV.get(str(v), str(v)) for v in counts.index]
        ax.bar(range(len(counts)), counts.values, color=color, edgecolor='white', width=0.6)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(tick_labels, fontsize=8)

    ax.set_title(short_title(col), fontsize=10)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel('Count', fontsize=8)
    ax.annotate(f'n={n}', xy=(0.97, 0.95), xycoords='axes fraction',
                ha='right', va='top', fontsize=8, color='#555555')

axes.flat[11].set_visible(False)

plt.suptitle('Annotation label distributions (gold)', fontsize=13)
plt.tight_layout()

out_path = os.path.join(OUT_DIR, 'combined_label_distributions.pdf')
fig.savefig(out_path, bbox_inches='tight')
plt.close(fig)
print(f'Saved {out_path}')
