#!/usr/bin/env python3
"""
Extract automatic features for every sampled_text in the shared dataset.

Features produced (one row per safe_instance_id):
  past_tense_verb_rate   – VBD tokens / all tokens (spaCy)
  sentiment_pos          – VADER positive score
  sentiment_neg          – VADER negative score
  sentiment_neu          – VADER neutral score
  sentiment_compound     – VADER compound score
  pov_first_rate         – 1st-person pronoun tokens / all tokens
  pov_second_rate        – 2nd-person pronoun tokens / all tokens
  pov_third_rate         – 3rd-person pronoun tokens / all tokens
  pov_dominant           – dominant POV category (first / second / third / none)
  concreteness_mean      – mean Brysbaert concreteness score for matched lemmas
  concreteness_coverage  – fraction of content lemmas matched in the lexicon
  temporal_mention_rate  – DATE+TIME entity count / token count (spaCy NER)
  temporal_mention_count – raw count of DATE+TIME entities

Usage:
  python extract_features.py            # uses defaults below
  python extract_features.py --help
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd
import spacy
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# ── Paths (relative to this script's directory) ───────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_CSV   = SCRIPT_DIR.parent / 'event_relation_annotation_task' / 'data' / \
             'dolma_combined_final_sample_700_with_llm_summary_safeid_with_spans.csv'
CONCRETENESS_XLSX = SCRIPT_DIR / 'concreteness' / 'concreteness_lexicon.xlsx'
OUTPUT_CSV = SCRIPT_DIR / 'features.csv'

SPACY_MODEL = 'en_core_web_sm'

# ── POV pronoun sets ──────────────────────────────────────────────────────────
FIRST_PERSON  = {'i', 'me', 'my', 'mine', 'myself',
                 'we', 'us', 'our', 'ours', 'ourselves'}
SECOND_PERSON = {'you', 'your', 'yours', 'yourself', 'yourselves'}
THIRD_PERSON  = {'he', 'him', 'his', 'himself',
                 'she', 'her', 'hers', 'herself',
                 'it', 'its', 'itself',
                 'they', 'them', 'their', 'theirs', 'themselves'}


def load_concreteness(path: Path) -> dict:
    """Return {lowercase_word: conc_mean} from the Brysbaert lexicon."""
    df = pd.read_excel(path, usecols=['Word', 'Conc.M'])
    return {str(w).lower(): float(m) for w, m in zip(df['Word'], df['Conc.M'])}


def extract_features(text: str, nlp, vader, conc_lexicon: dict) -> dict:
    doc = nlp(text)
    tokens = [t for t in doc if not t.is_space]
    n_tokens = len(tokens)
    if n_tokens == 0:
        return _empty_row()

    # ── Past-tense verb rate ──────────────────────────────────────────────────
    n_past = sum(1 for t in tokens if t.tag_ == 'VBD')
    past_tense_verb_rate = n_past / n_tokens

    # ── VADER sentiment ───────────────────────────────────────────────────────
    scores = vader.polarity_scores(text)

    # ── POV (pronoun rate) ────────────────────────────────────────────────────
    n_first = n_second = n_third = 0
    for t in tokens:
        low = t.lower_
        if low in FIRST_PERSON:
            n_first += 1
        elif low in SECOND_PERSON:
            n_second += 1
        elif low in THIRD_PERSON:
            n_third += 1

    pov_first_rate  = n_first  / n_tokens
    pov_second_rate = n_second / n_tokens
    pov_third_rate  = n_third  / n_tokens

    rates = {'first': pov_first_rate, 'second': pov_second_rate, 'third': pov_third_rate}
    dominant_pov = max(rates, key=rates.get)
    pov_dominant = dominant_pov if rates[dominant_pov] > 0 else 'none'

    # ── Brysbaert concreteness ────────────────────────────────────────────────
    # Use lemmas of content words (nouns, verbs, adjectives, adverbs)
    content_pos = {'NOUN', 'VERB', 'ADJ', 'ADV'}
    content_lemmas = [t.lemma_.lower() for t in tokens if t.pos_ in content_pos]
    matched = [conc_lexicon[l] for l in content_lemmas if l in conc_lexicon]

    concreteness_mean     = sum(matched) / len(matched) if matched else None
    concreteness_coverage = len(matched) / len(content_lemmas) if content_lemmas else None

    # ── Temporal mentions (DATE + TIME NER entities) ──────────────────────────
    temporal_ents = [e for e in doc.ents if e.label_ in ('DATE', 'TIME')]
    temporal_mention_count = len(temporal_ents)
    temporal_mention_rate  = temporal_mention_count / n_tokens

    return {
        'past_tense_verb_rate':   round(past_tense_verb_rate, 6),
        'sentiment_pos':          round(scores['pos'], 4),
        'sentiment_neg':          round(scores['neg'], 4),
        'sentiment_neu':          round(scores['neu'], 4),
        'sentiment_compound':     round(scores['compound'], 4),
        'pov_first_rate':         round(pov_first_rate, 6),
        'pov_second_rate':        round(pov_second_rate, 6),
        'pov_third_rate':         round(pov_third_rate, 6),
        'pov_dominant':           pov_dominant,
        'concreteness_mean':      round(concreteness_mean, 4) if concreteness_mean is not None else None,
        'concreteness_coverage':  round(concreteness_coverage, 4) if concreteness_coverage is not None else None,
        'temporal_mention_rate':  round(temporal_mention_rate, 6),
        'temporal_mention_count': temporal_mention_count,
    }


def _empty_row() -> dict:
    return {
        'past_tense_verb_rate': None, 'sentiment_pos': None,
        'sentiment_neg': None, 'sentiment_neu': None, 'sentiment_compound': None,
        'pov_first_rate': None, 'pov_second_rate': None, 'pov_third_rate': None,
        'pov_dominant': None, 'concreteness_mean': None, 'concreteness_coverage': None,
        'temporal_mention_rate': None, 'temporal_mention_count': None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data',         default=str(DATA_CSV),          help='Input CSV path')
    parser.add_argument('--concreteness', default=str(CONCRETENESS_XLSX), help='Brysbaert lexicon path')
    parser.add_argument('--output',       default=str(OUTPUT_CSV),        help='Output CSV path')
    parser.add_argument('--spacy-model',  default=SPACY_MODEL,            help='spaCy model name')
    args = parser.parse_args()

    print('Loading spaCy model...')
    nlp = spacy.load(args.spacy_model)

    print('Loading VADER...')
    vader = SentimentIntensityAnalyzer()

    print('Loading Brysbaert concreteness lexicon...')
    conc_lexicon = load_concreteness(Path(args.concreteness))
    print(f'  {len(conc_lexicon):,} entries loaded')

    print('Reading dataset...')
    csv.field_size_limit(10**7)
    with open(args.data, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    print(f'  {len(rows):,} instances')

    results = []
    for i, row in enumerate(rows):
        if (i + 1) % 50 == 0 or i == 0:
            print(f'  Processing {i + 1}/{len(rows)}...', end='\r')
        feats = extract_features(row['sampled_text'], nlp, vader, conc_lexicon)
        feats['safe_instance_id'] = row['safe_instance_id']
        results.append(feats)

    print(f'\nDone. Writing {len(results):,} rows to {args.output}')

    out_df = pd.DataFrame(results)
    col_order = ['safe_instance_id',
                 'past_tense_verb_rate',
                 'sentiment_pos', 'sentiment_neg', 'sentiment_neu', 'sentiment_compound',
                 'pov_first_rate', 'pov_second_rate', 'pov_third_rate', 'pov_dominant',
                 'concreteness_mean', 'concreteness_coverage',
                 'temporal_mention_rate', 'temporal_mention_count']
    out_df[col_order].to_csv(args.output, index=False)
    print('Done.')


if __name__ == '__main__':
    main()
