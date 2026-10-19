import csv
import io
import json
import uuid
from config import OUTPUTS

FIELDS = ['pronunciation', 'biblical_names', 'naturalness', 'pacing', 'omissions_insertions']

def save_rating(a, b, preference, notes, *scores, output_root=None):
    if not a:
        raise ValueError('Generate an output before saving a rating.')
    if a.get('is_speech') is not True:
        raise ValueError('Test tones cannot be rated for speech quality. Install a real engine first.')
    if b and b.get('is_speech') is not True:
        raise ValueError('Output B is a test tone; retain a real speech output for comparison.')
    if preference in ('A', 'B', 'Tie') and not b:
        raise ValueError('Retain a speech output as B before choosing an A/B preference, or choose Single output.')
    if b and a['original_text'] != b['original_text']:
        raise ValueError('Comparison requires identical original text.')
    root = (output_root or OUTPUTS) / ('rating_' + uuid.uuid4().hex)
    root.mkdir(parents=True)
    row = {'output_a': a['id'], 'output_b': b['id'] if b else None,
           'preference': preference, 'notes': notes, **dict(zip(FIELDS, scores))}
    jp, cp = root / 'rating.json', root / 'rating.csv'
    jp.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    with cp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        # Treat spreadsheet formula prefixes as literal text in exported notes.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in row.items()})
    return str(jp), str(cp)
