# AISG3 UI / Team View Update

## UI changes

- Default window size changed to `1366x768` and remains resizable.
- Left panel widened to `360px` so text is easier to read.
- Font sizes increased for title, section headers, normal text, bot names and K/D labels.
- Statistics panel no longer shows `Bullets` or `Shots`.
- Statistics now shows team count as `Team A: 4     Team B: 4` instead of one combined `Bots: 8` line.
- Kills and deaths are now separated into a two-column Team A / Team B table with a vertical divider.
- Active bot list is split into Team A and Team B sections with separator lines.

## Bot rendering changes

- Team A and Team B now use different colors.
- Bot body shape now represents weapon role:
  - `SNIPER`: triangle body, long rifle barrel and scope marker.
  - `AR`: circle body, medium rifle barrel and magazine marker.
  - `SMG`: diamond body, short compact gun marker.
- Weapon role abbreviation is drawn directly on the bot body: `SNI`, `AR`, or `SMG`.
- Bot label now includes team indicator and has a colored outline.

## Kept from previous update

- Room limit remains `8` bot slots.
- Only these roles/weapons are allowed: `SNIPER`, `AR`, `SMG`.
- `PISTOL` and `DAGGER` are still removed.
- Map/world dimensions are still scaled into the visible viewport instead of being cropped.
