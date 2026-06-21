import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ServerJSONLogger:
    """
    Server-side JSON logger với time-based rotation (5 phút/file)
    Log tất cả gRPC data từ server mà không cần sửa AI bot
    """
    
    def __init__(self, log_dir: str = "logs/server_grpc", rotation_minutes: int = 5):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.rotation_interval = rotation_minutes * 60  # Convert to seconds
        self.current_file = None
        self.current_file_handle = None
        self.file_start_time = None
        self.lock = threading.Lock()
        self.entry_count = 0
        
        # Initialize first log file
        self._rotate_file()
        
        logger.info(f"📝 Server JSON Logger initialized - Dir: {self.log_dir}, Rotation: {rotation_minutes}min")
    
    def _get_timestamp_filename(self) -> str:
        """Generate filename with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"server_grpc_{timestamp}.json"
    
    def _rotate_file(self):
        """Create new log file with timestamp"""
        with self.lock:
            # Close current file if exists
            if self.current_file_handle:
                # Write closing bracket for JSON array
                self.current_file_handle.write("\n]")
                self.current_file_handle.close()
                logger.info(f"📁 Closed log file: {self.current_file} ({self.entry_count} entries)")
            
            # Create new file
            filename = self._get_timestamp_filename()
            self.current_file = self.log_dir / filename
            self.current_file_handle = open(self.current_file, 'w', encoding='utf-8')
            self.file_start_time = time.time()
            self.entry_count = 0
            
            # Write opening bracket for JSON array
            self.current_file_handle.write("[\n")
            self.current_file_handle.flush()
            
            logger.info(f"📝 Created new log file: {filename}")
    
    def _should_rotate(self) -> bool:
        """Check if file should be rotated based on time"""
        if self.file_start_time is None:
            return True
        
        return (time.time() - self.file_start_time) >= self.rotation_interval
    
    def _write_entry(self, entry: Dict[str, Any]):
        """Internal method to write JSON entry"""
        try:
            # Check if rotation needed
            if self._should_rotate():
                self._rotate_file()
            
            with self.lock:
                # Write comma if not first entry
                if self.entry_count > 0:
                    self.current_file_handle.write(",\n")
                
                # Write JSON entry
                json.dump(entry, self.current_file_handle, indent=2, ensure_ascii=False)
                self.current_file_handle.flush()
                self.entry_count += 1
        
        except Exception as e:
            logger.error(f"💥 JSON logging error: {e}")
    
    def log_bot_registration(self, player_id: str, bot_name: str, bot_id: int, success: bool, message: str):
        """Log bot registration event"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "type": "bot_registration",
            "player_id": player_id,
            "data": {
                "bot_name": bot_name,
                "bot_id": bot_id,
                "success": success,
                "message": message
            }
        }
        self._write_entry(entry)
    
    def log_observation_sent(self, bot_id: int, player_id: str, observation_data: Dict[str, Any]):
        """Log observation sent to bot"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "type": "observation_sent",
            "bot_id": bot_id,
            "player_id": player_id,
            "data": observation_data
        }
        self._write_entry(entry)
    
    def log_action_received(self, bot_id: int, player_id: str, action_data: Dict[str, Any]):
        """Log action received from bot"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "type": "action_received",
            "bot_id": bot_id,
            "player_id": player_id,
            "data": action_data
        }
        self._write_entry(entry)
    
    def log_game_event(self, event_type: str, event_data: Dict[str, Any], related_bots: list = None):
        """Log game events (deaths, kills, matches, etc.)"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "type": "game_event",
            "event_type": event_type,
            "data": event_data,
            "related_bots": related_bots or []
        }
        self._write_entry(entry)
    
    def log_match_event(self, match_id: str, event_type: str, event_data: Dict[str, Any]):
        """Log match-specific events"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "type": "match_event",
            "match_id": match_id,
            "event_type": event_type,
            "data": event_data
        }
        self._write_entry(entry)
    
    def log_bot_disconnect(self, bot_id: int, player_id: str, connection_duration: float):
        """Log bot disconnection"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "timestamp_ms": int(time.time() * 1000),
            "type": "bot_disconnect",
            "bot_id": bot_id,
            "player_id": player_id,
            "data": {
                "connection_duration": connection_duration
            }
        }
        self._write_entry(entry)
    
    def close(self):
        """Close logger and current file"""
        with self.lock:
            if self.current_file_handle:
                self.current_file_handle.write("\n]")
                self.current_file_handle.close()
                logger.info(f"📁 Server JSON Logger closed: {self.current_file} ({self.entry_count} entries)")

# Utility functions để convert protobuf messages
def observation_to_dict(observation) -> Dict[str, Any]:
    """Convert protobuf observation to dictionary"""
    return {
        "tick": observation.tick,
        "self_pos": {
            "x": observation.self_pos.x,
            "y": observation.self_pos.y
        },
        "self_hp": observation.self_hp,
        "enemy_pos": {
            "x": observation.enemy_pos.x,
            "y": observation.enemy_pos.y
        },
        "enemy_hp": observation.enemy_hp,
        "bullets": [
            {"x": bullet.x, "y": bullet.y} 
            for bullet in observation.bullets
        ],
        "walls": list(observation.walls),
        "has_line_of_sight": observation.has_line_of_sight,
        "arena_width": observation.arena_width,
        "arena_height": observation.arena_height,
        "weapon_type": observation.weapon_type,
        "ammo": observation.ammo,
        "magazine_size": observation.magazine_size,
        "is_reloading": observation.is_reloading,
        "reload_progress": observation.reload_progress,
        "shot_cooldown_remaining": observation.shot_cooldown_remaining,
        "current_bloom": observation.current_bloom,
        "weapon_config_version": observation.weapon_config_version,
        "weapon_base_damage": observation.weapon_base_damage,
        "weapon_max_range": observation.weapon_max_range,
        "weapon_shots_per_second": observation.weapon_shots_per_second,
        "weapon_mobility_multiplier": observation.weapon_mobility_multiplier,
        "self_kills": observation.self_kills,
        "self_deaths": observation.self_deaths,
        "reload_time_remaining": observation.reload_time_remaining,
        "target_distance": observation.target_distance,
        "in_effective_range": observation.in_effective_range,
        "can_shoot": observation.can_shoot,
        "last_shot_elapsed": observation.last_shot_elapsed,
        "run_mode": observation.run_mode,
    }

def action_to_dict(action) -> Dict[str, Any]:
    """Convert protobuf action to dictionary"""
    return {
        "thrust": {
            "x": action.thrust.x,
            "y": action.thrust.y
        },
        "aim_angle": action.aim_angle,
        "fire": action.fire,
        "bot_id": action.bot_id,
    }
