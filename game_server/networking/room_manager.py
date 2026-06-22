import json
import logging
import time
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Player:
    """Represents a connected player"""
    id: str
    bot_name: str
    connection_time: float = field(default_factory=time.time)
    bot_id: Optional[int] = None
    weapon_type: str = "AR"
    team_id: str = None
    role: str = None

@dataclass 
class Room:
    """Represents a game room"""
    id: str
    password: str
    max_players: int
    arena_config: dict
    weapon_loadout_cycle: List[str] = field(default_factory=lambda: ["AR", "SNIPER", "SMG"])
    players: List[Player] = field(default_factory=list)
    created_time: float = field(default_factory=time.time)

    def team_ids(self) -> set:
        return {player.team_id or player.id for player in self.players}

    def active_team_count(self) -> int:
        return len(self.team_ids())

    def is_active(self) -> bool:
        return self.active_team_count() >= 2

class RoomManager:
    """Room-based system replacing matchmaking"""
    _global_bot_id = 1

    def __init__(self, rooms_config_path: str = "rooms.json"):
        self.rooms_config_path = rooms_config_path
        self.rooms: Dict[str, Room] = {}
        self.player_to_room: Dict[str, str] = {}
        
        # Statistics
        self.total_players_served = 0
        
        # Load rooms from config - FIXED PATH RESOLUTION
        self._load_rooms_config()
    
    def _load_rooms_config(self):
        """Load rooms from JSON config file - FIXED PATH RESOLUTION"""
        try:
            project_root = Path(__file__).resolve().parents[2]
            requested_path = Path(self.rooms_config_path)
            config_path = requested_path if requested_path.is_absolute() else project_root / requested_path
            
            if not os.path.exists(config_path):
                logger.error(f"❌ rooms.json not found at {config_path}")
                self._create_default_rooms()
                return
                
            with open(config_path, 'r', encoding='utf-8') as f:
                rooms_data = json.load(f)
            
            for room_id, room_config in rooms_data.items():
                room = Room(
                    id=room_id,
                    password=room_config['password'],
                    max_players=room_config['max_players'],
                    arena_config=room_config['arena'],
                    weapon_loadout_cycle=self._validate_loadout_cycle(
                        room_config.get('weapon_loadout_cycle')
                    ),
                )
                self.rooms[room_id] = room
                
                # ✅ FIXED: Calculate obstacle_count
                obstacle_count = len(room_config['arena'].get('obstacles', []))
                logger.info(f"📋 Loaded room: {room_id} (max: {room.max_players} players, {obstacle_count} obstacles)")
                
        except Exception as e:
            logger.error(f"💥 Failed to load rooms config: {e}")
            import traceback
            traceback.print_exc()
            self._create_default_rooms()
    
    def _create_default_rooms(self):
        """Create default rooms if config loading fails"""
        default_rooms = {
            "room_default": {
                "password": "default123",
                "max_players": 8,
                "weapon_loadout_cycle": ["AR", "SNIPER", "SMG"],
                "arena": {
                    "width": 800,
                    "height": 600,
                    "obstacles": [
                        {"x": 300, "y": 200, "width": 6000, "height": 120},
                        {"x": 500, "y": 350, "width": 120, "height": 60}
                    ]
                }
            }
        }
        
        for room_id, room_config in default_rooms.items():
            room = Room(
                id=room_id,
                password=room_config['password'],
                max_players=room_config['max_players'],
                arena_config=room_config['arena'],
                weapon_loadout_cycle=self._validate_loadout_cycle(
                    room_config.get('weapon_loadout_cycle')
                ),
            )
            self.rooms[room_id] = room
            logger.info(f"📋 Created default room: {room_id}")
    
    @staticmethod
    def _validate_loadout_cycle(raw_cycle) -> List[str]:
        allowed = {"SNIPER", "AR", "SMG"}
        cycle = [str(value).upper() for value in (raw_cycle or ["AR", "SNIPER", "SMG"])]
        if not cycle or any(value not in allowed for value in cycle):
            raise ValueError("weapon_loadout_cycle must contain only SNIPER, AR or SMG")
        return cycle

    def join_room(
        self,
        player_id: str,
        bot_name: str,
        room_id: str,
        room_password: str,
        team_id: str = None,
        requested_weapon_type: str = None,
        role: str = None,
    ) -> Dict:
        """Join a specific room with password.

        A logical client can now create a team by opening multiple bot
        connections with different player_id values but the same team_id.
        The room becomes active only when at least two distinct teams exist.
        """

        if player_id in self.player_to_room:
            return {
                'success': False,
                'message': f'Player {player_id} already in room {self.player_to_room[player_id]}',
                'bot_id': 0
            }

        if room_id not in self.rooms:
            available_rooms = list(self.rooms.keys())
            return {
                'success': False,
                'message': f"❌ Room ID '{room_id}' does not exist. Available: {available_rooms}",
                'bot_id': 0
            }

        room = self.rooms[room_id]

        if room.password != room_password:
            return {
                'success': False,
                'message': f"❌ Wrong password for room '{room_id}'",
                'bot_id': 0
            }

        if len(room.players) >= room.max_players:
            return {
                'success': False,
                'message': f"❌ Room '{room_id}' is full ({len(room.players)}/{room.max_players} bot slots)",
                'bot_id': 0
            }

        team_id = (team_id or player_id).strip() or player_id
        allowed_weapons = set(self._validate_loadout_cycle(room.weapon_loadout_cycle))
        if requested_weapon_type:
            requested_weapon_type = requested_weapon_type.upper()
            if requested_weapon_type not in allowed_weapons:
                return {
                    'success': False,
                    'message': f"❌ Weapon '{requested_weapon_type}' is not allowed in room '{room_id}'. Allowed: {sorted(allowed_weapons)}",
                    'bot_id': 0,
                }
            weapon_type = requested_weapon_type
        else:
            weapon_type = room.weapon_loadout_cycle[len(room.players) % len(room.weapon_loadout_cycle)]

        player = Player(
            id=player_id,
            bot_name=bot_name,
            weapon_type=weapon_type,
            team_id=team_id,
            role=role or weapon_type.lower(),
        )
        room.players.append(player)
        self.player_to_room[player_id] = room_id
        self.total_players_served += 1

        bot_id = self._generate_bot_id(player, room)
        player.bot_id = bot_id

        players_count = len(room.players)
        team_count = room.active_team_count()
        status_msg = f"✅ Joined room {room_id} ({players_count}/{room.max_players} bot slots, {team_count} team(s))"

        if room.is_active():
            status_msg += " - ⚔️ Battle active!"
        else:
            status_msg += " - ⏳ Waiting for another team..."

        obstacle_count = len(room.arena_config.get('obstacles', []))
        logger.debug(
            f"Room {room_id} returns {obstacle_count} obstacles, team {team_id}, weapon {weapon_type}"
        )

        logger.info(
            f"👤 {player_id} ({bot_name}) → Room {room_id}, team {team_id}, "
            f"weapon {weapon_type} ({players_count}/{room.max_players} bot slots)"
        )

        return {
            'success': True,
            'room_id': room_id,
            'bot_id': bot_id,
            'message': status_msg,
            'players_in_room': players_count,
            'teams_in_room': team_count,
            'max_players': room.max_players,
            'arena_config': room.arena_config,
            'weapon_type': weapon_type,
            'team_id': team_id,
            'role': player.role,
        }

    def _generate_bot_id(self, player: Player, room: Room) -> int:
        bot_id = RoomManager._global_bot_id
        RoomManager._global_bot_id += 1
        return bot_id
    
    def leave_room(self, player_id: str) -> bool:
        """Remove player from room"""
        room_id = self.player_to_room.get(player_id)
        if not room_id or room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        
        # Remove player from room
        room.players = [p for p in room.players if p.id != player_id]
        del self.player_to_room[player_id]
        
        logger.info(f"👋 Player {player_id} left room {room_id} ({len(room.players)} remaining)")
        return True
    
    def get_room_info(self, room_id: str) -> Dict:
        """Get detailed room information"""
        if room_id not in self.rooms:
            return {'error': f'Room {room_id} not found'}
        room = self.rooms[room_id]
        player_count = len(room.players)
        team_count = room.active_team_count()
        return {
            'room_id': room.id,
            'players': [
                {
                    'id': p.id,
                    'team_id': p.team_id or p.id,
                    'name': p.bot_name,
                    'role': p.role or p.weapon_type.lower(),
                    'bot_id': p.bot_id,
                    'weapon_type': p.weapon_type,
                    'connected_time': time.time() - p.connection_time
                }
                for p in room.players
            ],
            'player_count': player_count,
            'team_count': team_count,
            'max_players': room.max_players,
            'arena_config': room.arena_config,
            'is_active': room.is_active(),
            'status': 'active' if room.is_active() else 'waiting'
        }

    def get_all_rooms(self) -> List[Dict]:
        """Get list of all rooms with player/team counts"""
        rooms_list = []
        for room in self.rooms.values():
            rooms_list.append({
                'id': room.id,
                'players': len(room.players),
                'teams': room.active_team_count(),
                'max_players': room.max_players,
                'is_active': room.is_active(),
                'weapon_loadout_cycle': list(room.weapon_loadout_cycle),
                'player_names': [p.bot_name for p in room.players],
                'team_ids': sorted(room.team_ids()),
            })
        return rooms_list

    def get_statistics(self) -> Dict:
        """Get room manager statistics"""
        total_active_players = sum(len(room.players) for room in self.rooms.values())
        active_rooms = len([r for r in self.rooms.values() if r.is_active()])
        
        return {
            'total_rooms': len(self.rooms),
            'active_rooms': active_rooms,
            'total_active_players': total_active_players,
            'total_players_served': self.total_players_served,
            'rooms_info': self.get_all_rooms()
        }
