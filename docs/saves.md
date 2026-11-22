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
- `loadouts`: the stored equipment sets by id (`Loadout2`, `Loadout3`), each shaped like `equipment`;
  the worn set is the id missing from the numbering;
- `mastery`: per skill, its mastery guild tasks: `done` ids, `progress` (task id to progress for
  started tasks) and the `untouched` count;
- `slayer`: per Slayer master with a task, its `monster`, two `counters`, whether it is the
  `active` master, and the `blocked` monsters;
- `farming`: per plot with a crop chosen, its `crop`, whether an item slot holds `Fertiliser` (`fertilised`) and
  `growing`: the growing `crop`, its growth time in `seconds` and the seconds `remaining` at save time (0 when
  ready), or `null` when nothing grows;
- `ranching`: each ranching land in use with its `enclosure`, the enclosure's `condition` (0 to 1) and its `animals`
  (`species`, `variant`, `hunger`, `comfort` and `satisfaction` (also as the three `gauges` in save order), the
  `treats` slots with a flag whose meaning is not established, `adult_in_minutes` (negative once grown up) and
  `lifespan_minutes` left);
- `quests`: per quest, its `status` (`not_started`, `active`, `complete`, or the raw number for another value),
  `steps_done` out of `steps`, and for an active quest its current `step` and that step's `tasks` (`done`, and
  `goals`: goal id to progress). Step, task and goal ids are the game's own.

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
- loadouts, after the worn slots: an int32 count, then records of a loadout id, an int32 size and
  that set's slot records (checked 2026-11-22);
- mastery guild: a flag and the last opened category, then one record per task. A 2-byte payload
  is an untouched task; otherwise a flag, a goal key, an int32, a float64 progress and three flags,
  the first set when the task is complete (it matched progress reaching the game's target for
  every task of that save);
- Slayer: a has-task flag, the monster id, two int32 `counters` whose meaning is not established
  (they are reported as they are), then block slots naming skipped monsters;
- farming: see below.

A layout that does not match reads as an empty value; it never prevents the rest of the save from
loading.

### Game clock, farming timers and ranching animals

The Farming and Ranching `Passive` components count time in ticks of 1/60 s of total playtime: the int64 after the
Farming header's flag and category id equals the character's `TotalPlaytime` statistic (milliseconds) times 0.06.
A plot record is five flags, a presence flag and the chosen crop id, two item slots (a presence flag and an id
each), and an int32 state: 0 nothing chosen, 1 chosen but nothing growing, 2 growing. A growing plot then holds the
growing crop id, a flag, an int32, the growth time and the tick it is ready at. The growth time of every growing
plot of a real release save matched the game's crop interval (Potato 1.5 h, Penril 2 h, Wheat 4 h, Compost 24 h),
and between two saves 16 minutes apart the time left shrank by 16 minutes. The chosen crop and the growing crop can
differ (four allotments of that save chose Onion, Lettuce, Strawberry and Garlic while Potato grew).

The three animal gauges are the game's Hunger, Comfort and Satisfaction (its enclosure screen lists them in that
order and computes Happiness = Hunger x 0.3 + Comfort x 0.3 + Satisfaction x 0.4, Comfort counting as 1 from 75 %).
On a real save the second gauge equalled the enclosure condition for every animal, as the game says Comfort equals
the enclosure's maintenance; the first was 1 for every animal, Sheep and Cows included, which need no food. After
the treats come two float64 counts of minutes: until the animal's lifespan ends, and until it grows up. Their
difference is the animal's lifespan minus its growing time (Sheep 6912, Cow 10368, Chicken 5184 minutes, as in the
game data), a Cow calf gave the same age from both, and both shrank by 16 between saves 16 minutes apart. A third
float64 and an int32 after the gauges are not interpreted.

### Quests

`Quests` holds one record per quest: an int32 status (0, 1 or 3 seen: not started, active, complete), then step
records; a step is task records, a flag and an int32 status (2 done); a task is goal records (a float64 progress and
two flags), three flags and an int32 status (2 done). On a real save every goal of the completed quests held exactly
the game's `MaxProgress`, and the active quest's current step was its first step not done.

### Not decoded

- Pets: every skill's `Pets` component holds its pet id and a two-byte payload. Every payload of the save examined
  was zero, so which value means a found pet is not established.
- Slayer `counters`: on the save examined, the first was always at least the second, between about 2 and 4 times the
  master's base task length, and the second was 0 for three masters, the active one included. This suggests the
  task's kill count and the kills done, but no pair of saves with Slayer kills between them was available to
  confirm it, so the field keeps its neutral name.
