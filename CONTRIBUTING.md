# Contributing to Idlewatch

Run the checks before and after a change:

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

CI runs the same checks on Linux, macOS and Windows.

## Tests and fixtures

Tests build synthetic saves with `tests/synthetic.py`. Never commit a real save, a Steam account
number, or a path from your own machine: a real save identifies its player. `.gitignore` refuses
`*.sav` files for that reason. When a new game version changes the format, extend the synthetic
writer to match and add a test that fails without the decoder change.

Idlewatch stays read-only: no command writes to a save or to the save folder.

## README and documentation

The README keeps one short shape: title, logo and badges, the one-line promise, "Get started in a
minute", "What you can do" (a table), and "Documentation" (the docs index and the closing licence
line). Detail goes in `docs/`, never in the README.
`tests/test_readme_structure.py` enforces the shape.

## Workflow

Work is tracked with Logics in `logics/` (see `LOGICS.md`).
