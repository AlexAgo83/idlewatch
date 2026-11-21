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
- `wallet`: currency short name to amount;
- `astrology`: constellation records and the active constellation (see below);
- `equipment`: slot to `item` and `quantity`, empty slots left out;
- `mastery`: per skill, its mastery guild tasks: `done` ids, `progress` (task id to progress for
  started tasks) and the `untouched` count;
- `slayer`: per Slayer master with a task, its `monster`, two `counters`, whether it is the
  `active` master, and the `blocked` monsters;
- `farming`: per plot with a crop, its `crop` and whether it is `fertilised`.

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

### Astrology

The `Action` component of `MelvorBase:Astrology` is decoded as an int32 constellation count,
then records containing an id, an int32 `value`, a float64 `xp`, an int32 minor-node count and
its node ids, followed by an int32 major-node count and its node ids. The final string is the
active constellation id, or an empty string for no active constellation (`None` in Python).
All output ids omit their namespace.

`value` deliberately has a neutral name: its meaning has not been established. `xp` is presumed
mastery XP. The small prefix before the constellation count is treated as an opaque header
(at most 16 bytes); its fields are not interpreted. Recognition requires valid namespaced ids,
unique constellation ids, finite nonnegative XP, an active id from the list (or empty), and exact
consumption of the component. Missing or unrecognized data yields
`{"constellations": [], "active": null}` in JSON, without preventing the rest of the save from loading.

These assumptions are covered by synthetic saves, including unknown and truncated layouts.
Release saves written since 2026-11 end differently: a presence flag, the active id when set,
then two zero bytes. Both tails are recognized, and checked against a real release save; any
other tail still reads as empty. Measured on that save, `xp` is the constellation's knowledge:
the minor nodes taken never exceed the game's knowledge thresholds it reaches.

### Equipment, mastery guild, Slayer and farming

These components share one shape: an int32 count, then records of an id, an int32 payload size
and the payload. Equipment and Slayer keep more data after the records (loadouts; a presence flag
and the active master id). Checked against a real release save (2026-11-21):

- equipment slot payload: int32 quantity (-1 when empty), a flag, a has-item flag, the item id;
- mastery guild: a flag and the last opened category, then one record per task. A 2-byte payload
  is an untouched task; otherwise a flag, a goal key, an int32, a float64 progress and three flags,
  the first set when the task is complete (it matched progress reaching the game's target for
  every task of that save);
- Slayer: a has-task flag, the monster id, two int32 `counters` whose meaning is not established
  (they are reported as they are), then block slots naming skipped monsters;
- farming: after the grain mill header, one record per plot; the first id inside is the crop.

A layout that does not match reads as an empty value; it never prevents the rest of the save from
loading.
