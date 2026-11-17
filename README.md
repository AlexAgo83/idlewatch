# Idlewatch

<p align="center"><img src="assets/idlewatch-mark.svg" width="120" alt="Idlewatch"></p>

<p align="center"><b>Your Melvor Idle 2 saves, read as plain JSON, never touched.</b></p>

<p align="center">

[![License](https://img.shields.io/badge/license-MIT-3f7d4a)](LICENSE) ![Version](https://img.shields.io/badge/version-v0.1.0-3f7d4a) ![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white) [![CI](https://github.com/AlexAgo83/idlewatch/actions/workflows/ci.yml/badge.svg)](https://github.com/AlexAgo83/idlewatch/actions/workflows/ci.yml)

</p>

Idlewatch decodes a Melvor Idle 2 save into its header (character, mode, save time, current
activity), skills, bank items and wallet. It only opens saves for reading, so it is safe to run
while the game is open. Use it from the command line or as a Python library.

Idlewatch is an unofficial fan tool. It is not affiliated with or endorsed by Games By Malcs.
Saves from the demo and from the release (save version 31) both decode; a game update can still change the format.

## Get started in a minute

```bash
pip install git+https://github.com/AlexAgo83/idlewatch
idlewatch list
idlewatch read "<path printed by list>"
```

`idlewatch list` searches the game's save folder on macOS and Windows; pass `--saves-dir` for any
other folder. In Python, `idlewatch.load(path)` returns the same dictionary `read` prints.

## What you can do

| Need | How | Detail |
| --- | --- | --- |
| Find every character's save | `idlewatch list [--saves-dir DIR]` | [Save locations](docs/saves.md#where-saves-live) |
| Read one save as JSON | `idlewatch read <save>` | [What a save holds](docs/saves.md#what-idlewatch-reads) |
| Use the decoder in your own tool | `idlewatch.load(path)`, `idlewatch.parse(data)` | [Save format](docs/saves.md#save-format) |

## Documentation

- [Saves](docs/saves.md): where the game keeps them, what Idlewatch reads, and the save format.
- [Contributing](CONTRIBUTING.md): checks to run and the rules for tests and fixtures.
- [Security](SECURITY.md): how to report a problem, and why never to attach a real save.

Contributions are welcome through pull requests. Idlewatch is [MIT licensed](LICENSE).
