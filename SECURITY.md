# Security

Idlewatch only reads files, never writes them, and makes no network call.

To report a vulnerability, open a private report through the repository's **Security** tab
(Report a vulnerability) rather than a public issue. You can expect a first answer within a week.

Never attach a real save to an issue, a pull request or a report: a save and its path identify
the player (character names and the Steam account number). Describe the problem, or build a
synthetic save with `tests/synthetic.py` that reproduces it.
