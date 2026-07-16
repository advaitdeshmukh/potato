"""
upload_to_hf.py

Pushes the generated huggingface_release/ folder to a HuggingFace *dataset* repo,
cleanly replacing the previous release (no stale leftover files). Because HF is
git-backed, the prior version stays recoverable from the repo's commit history.

This script contains NO data-shaping config — annotators, columns, and
anonymization all live in export_release.py and are already baked into the files.
Run export_release.py first, review the files, then run this.

    python upload_to_hf.py --yes
    python upload_to_hf.py --repo-id you/your-dataset --yes

Requires: `pip install huggingface_hub` and a token via `huggingface-cli login`
or the HF_TOKEN environment variable.
"""

import argparse
import os
import sys

# ── Configuration ──────────────────────────────────────────────────────────────

# Fill this in once (e.g. "your-username/your-dataset-name"), or pass --repo-id /
# set HF_DATASET_REPO_ID. The CLI arg / env var override this constant.
REPO_ID = "teagrjohnson/narrative-gold-annotations"

_HERE = os.path.dirname(os.path.abspath(__file__))
RELEASE_DIR = os.path.join(_HERE, 'huggingface_release')

# Only these paths are managed in the repo; anything matching that we don't
# re-upload is deleted, so retired files (old un-anonymized parquets, etc.) go
# away instead of lingering next to the new release.
DELETE_PATTERNS = ['*.parquet', 'README.md']


def resolve_repo_id(cli_repo_id):
    return cli_repo_id or os.environ.get('HF_DATASET_REPO_ID') or REPO_ID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-id', default=None,
                        help='HuggingFace dataset repo id (overrides REPO_ID / env).')
    parser.add_argument('--yes', action='store_true',
                        help='Confirm the upload (required — nothing is pushed without it).')
    parser.add_argument('--commit-message', default='Update release: anonymized, column-trimmed annotations')
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi
        from huggingface_hub.utils import HfHubHTTPError  # noqa: F401
    except ImportError:
        sys.exit('error: huggingface_hub not installed. Run: pip install huggingface_hub')

    repo_id = resolve_repo_id(args.repo_id)
    if not repo_id:
        sys.exit('error: no repo id. Set REPO_ID at the top of this file, pass '
                 '--repo-id, or set HF_DATASET_REPO_ID.')

    if not os.path.isdir(RELEASE_DIR):
        sys.exit(f'error: {RELEASE_DIR} not found. Run export_release.py first.')

    api = HfApi()
    token = api.token or os.environ.get('HF_TOKEN')
    if token is None:
        sys.exit('error: no HuggingFace token. Run `huggingface-cli login` or set HF_TOKEN.')

    files = sorted(os.listdir(RELEASE_DIR))
    print(f'Repo (dataset):  {repo_id}')
    print(f'Local folder:    {RELEASE_DIR}')
    print('Files to upload:')
    for f in files:
        size = os.path.getsize(os.path.join(RELEASE_DIR, f))
        print(f'  {f}  ({size/1e6:.2f} MB)')
    print(f'Delete patterns (retire stale files): {DELETE_PATTERNS}')

    if not args.yes:
        sys.exit('\nDry run — nothing uploaded. Re-run with --yes to push.')

    print('\nUploading ...')
    commit = api.upload_folder(
        repo_id=repo_id,
        repo_type='dataset',
        folder_path=RELEASE_DIR,
        delete_patterns=DELETE_PATTERNS,
        commit_message=args.commit_message,
    )
    print(f'Done. {commit.commit_url if hasattr(commit, "commit_url") else commit}')


if __name__ == '__main__':
    main()
