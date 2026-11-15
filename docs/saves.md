# Saves

## Where saves live

Melvor Idle 2 keeps one file per character, `save_<uuid>.sav`, under the game's data folder:

| Platform | Folder |
| --- | --- |
| macOS | `~/Library/Application Support/Games By Malcs/Melvor Idle 2/steam/<steamid>/saves/` |
| Windows | `%APPDATA%\Games By Malcs\Melvor Idle 2\steam\<steamid>\saves\` |

`<steamid>` is your Steam account number. `idlewatch list` searches the data folder (the
`Melvor Idle 2` folder above) for every `save_*.sav` below it. On another platform, or for a copy
of your saves, pass the folder with `--saves-dir`.

A save path contains your Steam account number: keep that in mind before sharing the output of
`idlewatch list`.

## What Idlewatch reads

`idlewatch read <save>` prints one JSON object:

- `version`, `uuid`, `name`, `mode`, `saved_at` (UTC, ISO 8601), `demo`;
- `activity`: the current action `kind` and `target`, or `null`;
- `total_level`, `gp`, `slayer_coins`;
- `skills`: `name`, `level` and `xp` for each skill;
- `bank`: `stacks` (bank slots, placeholders included), `tabs`, and `items` (short item name to
  quantity, placeholders left out);
- `wallet`: currency short name to amount.

`idlewatch list` prints, for each save found, its `path`, `uuid`, `name`, `mode`, `saved_at` and
`total_level`, or `path` and `error` when the save cannot be decoded.

Idlewatch never writes to a save or to the save folder.

## Save format

A save is a Brotli stream around a .NET `BinaryWriter` layout: little-endian integers, and strings
as a 7-bit encoded byte length followed by UTF-8. The game leaves its Brotli stream unfinished, so a
one-shot decompress refuses it; Idlewatch streams it instead.

The decompressed data starts with a header: version (int32), character uuid (16 bytes, .NET byte
order), name, mode, save time (`DateTime.ToBinary`, int64), current activity kind, icon, target and
icon (strings), total level (int32), GP and slayer coins (int64), and a demo flag.

Then comes a table of entities, each a table of named components; a table is an int32 count, then
for each entry a name, an int32 size and that many bytes. A skill is an entity whose `Experience`
component is 12 bytes: xp (float64) and level (int32). The bank is the `MelvorBase:Bank` entity:

- `Inventory`: the default tab (int32), then for each tab three int32 stack limits and two flags,
  its stacks (quantity int32, two flags, item id), its label and its tags. A placeholder is a stack
  with quantity 0.
- `Wallet`: for each currency an amount (int64) and its id.

Ids look like `MelvorBase:Logs`; Idlewatch reports the part after the colon.
