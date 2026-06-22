# AISG team update

## Current update

- Room capacity increased from 4 bot slots to 8 bot slots so two 4-agent teams can join the same room.
- The renderer now scales the full room/map into the game window instead of cropping the first 800x600 area. This fixes bots spawning outside the visible viewport when rooms use 2000x1500 maps.
- The pygame window is now 1280x720, resizable, and labeled `Arena Battle - Team View`.
- The left panel now reads statistics from the currently viewed room and can show up to 8 active bots.
- Weapon roles are limited to exactly 3 roles:
  - `SNIPER`
  - `AR`
  - `SMG`
- `PISTOL` and `DAGGER` were removed from room loadouts, weapon config, server validation, client loadout validation, and AI tactic branches.
- Map dimensions and obstacles are kept unchanged.
- Reward/bandit/bomb mechanics are still not implemented in this update.

## Example commands

Start server:

```bash
python -m game_server.main
```

Team A, 4 bots:

```bash
python -m ai_bot.main \
  --player-id teamA \
  --team-id teamA \
  --team-size 4 \
  --team-loadout AR,SNIPER,SMG,AR \
  --room-id room_001 \
  --room-password abc123
```

Team B, 4 bots:

```bash
python -m ai_bot.main \
  --player-id teamB \
  --team-id teamB \
  --team-size 4 \
  --team-loadout SMG,AR,SNIPER,SMG \
  --room-id room_001 \
  --room-password abc123
```
