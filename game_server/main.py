import asyncio
import logging
import sys
import os
import time
from pathlib import Path

# Simple path handling
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(os.path.dirname(current_dir))
proto_dir = os.path.join(project_root, "proto")

# Add proto directory to Python path
sys.path.insert(0, proto_dir)

# Direct import from proto directory
try:
    from proto import arena_pb2, arena_pb2_grpc
except ImportError as e:
    sys.exit(1)

from game_server.engine.game_state import GameState, Wall
from game_server.engine.physics import PhysicsEngine
from game_server.networking.server import run_server
from game_server.ui.renderer import GameRenderer
from game_server.weapons import derive_match_seed, load_weapon_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GameEngine:
    def __init__(self, weapon_config_path=None):
        self.weapon_config = load_weapon_config(weapon_config_path)
        self.game_state = GameState(weapon_config=self.weapon_config)
        self.room_states = {}  
        self.physics_engines = {}  
        self.physics = PhysicsEngine(self.game_state)
        self.running = False
        self.last_time = time.time()
        
        self.match_active = False
        self.active_player_count = 0
        
        # Pre-create room states with proper error handling
        self._preload_room_states()

    def _preload_room_states(self):
        """Pre-create room states từ rooms.json với proper error handling"""
        try:
            import json
            
            # Find rooms.json với multiple paths
            possible_paths = [
                "rooms.json",  # Current working directory
                "../rooms.json",  # Parent directory
                os.path.join(os.getcwd(), "rooms.json"),  # Explicit current dir
                os.path.join(os.path.dirname(os.getcwd()), "rooms.json"),  # Parent of current
            ]
            
            # Also try relative to this file
            current_file = os.path.abspath(__file__)
            # From game_server/main.py -> project root
            project_root = os.path.dirname(os.path.dirname(current_file))
            possible_paths.append(os.path.join(project_root, "rooms.json"))
            
            print(f"🔧 GAME_ENGINE: Current file location: {current_file}")
            print(f"🔧 GAME_ENGINE: Project root: {project_root}")
            
            # Try each path
            rooms_json_path = None
            for i, path in enumerate(possible_paths):
                abs_path = os.path.abspath(path)
                exists = os.path.exists(abs_path)
                if exists:
                    rooms_json_path = abs_path
                    break
            
            if not rooms_json_path:
                print("❌ GAME_ENGINE: rooms.json not found in any location!")
                print("❌ GAME_ENGINE: Make sure rooms.json is in the project root directory")
                return
            
            # Load JSON file
            with open(rooms_json_path, 'r', encoding='utf-8') as f:
                rooms_data = json.load(f)
            
            print(f"📋 GAME_ENGINE: Successfully loaded JSON with {len(rooms_data)} rooms")
            
            # Create room states
            for room_id, room_config in rooms_data.items():
                
                # Create new GameState for this room
                room_state = GameState(
                    weapon_config=self.weapon_config,
                    room_id=room_id,
                    match_seed=derive_match_seed(room_id, self.weapon_config.version),
                )
                
                # Get arena config
                arena_config = room_config.get('arena', {})
                obstacles = arena_config.get('obstacles', [])
                
                for j, obs in enumerate(obstacles):
                    print(f"   Obstacle {j+1}: x={obs['x']}, y={obs['y']}, w={obs['width']}, h={obs['height']}")
                
                # Apply arena walls - THIS IS THE KEY PART
                room_state._create_arena_walls(arena_config)
                
                # Verify walls were created correctly
                wall_count = len(room_state.walls)
                print(f"🏗️ GAME_ENGINE: Room '{room_id}' now has {wall_count} walls")
                
                # Debug: Print first few walls to verify
                for k, wall in enumerate(room_state.walls[:6]):
                    print(f"   Wall {k}: ({wall.x}, {wall.y}) {wall.width}x{wall.height}")
                
                # Store room state
                self.room_states[room_id] = room_state
                self.physics_engines[room_id] = PhysicsEngine(room_state)
                
                print(f"✅ GAME_ENGINE: Room '{room_id}' state created and stored")
            
            print(f"🎯 GAME_ENGINE: Successfully created {len(self.room_states)} room states")
            print(f"🎯 GAME_ENGINE: Room IDs: {list(self.room_states.keys())}")
            
            # Verify room states are accessible
            for room_id in self.room_states:
                state = self.room_states[room_id]
                print(f"🔍 GAME_ENGINE: Verification - Room '{room_id}': {len(state.walls)} walls")
            
        except FileNotFoundError as e:
            print(f"❌ GAME_ENGINE: File not found error: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ GAME_ENGINE: JSON parsing error: {e}")
        except Exception as e:
            print(f"❌ GAME_ENGINE: Unexpected error: {e}")
            import traceback
            traceback.print_exc()

    def get_or_create_room_state(self, room_id, arena_config=None):
        """Get existing room state or create new one"""
        if room_id not in self.room_states:
            room_state = GameState(
                weapon_config=self.weapon_config,
                room_id=room_id,
                match_seed=derive_match_seed(room_id, self.weapon_config.version),
            )
            if arena_config:
                room_state._create_arena_walls(arena_config)
            self.room_states[room_id] = room_state
            self.physics_engines[room_id] = PhysicsEngine(room_state)
        return self.room_states[room_id]
    
    def get_all_room_states(self):
        """Get all room states with debug info"""
        print(f"🔍 GET_ALL: Returning {len(self.room_states)} room states")
        print(f"🔍 GET_ALL: Keys: {list(self.room_states.keys())}")
        return self.room_states
    
    def get_room_state(self, room_id):
        """Get specific room state with debug info"""
        exists = room_id in self.room_states
        
        if exists:
            state = self.room_states[room_id]
            wall_count = len(state.walls)
            return state
        else:
            return None
    
    async def run(self):
        """Main game loop with multi-room physics"""
        logger.info("🎮 Starting multi-room game engine...")
        self.running = True
        
        while self.running:
            current_time = time.time()
            dt = (current_time - self.last_time) * self.game_state.speed_multiplier
            self.last_time = current_time
            
            # Update physics for each room
            for room_id, room_state in self.room_states.items():
                total_bots = len(room_state.bots)
                alive_bots = len(room_state.get_alive_bots())
                
                if total_bots >= 2:
                    # Active room - full physics
                    self.physics_engines[room_id].update(min(dt, 0.1))
                elif total_bots > 0:
                    # Waiting room - slow physics
                    self.physics_engines[room_id].update(min(dt, 0.1) * 0.1)
            
            # Control game speed - MUST yield control to other tasks
            sleep_time = 1/60 / self.game_state.speed_multiplier  
            await asyncio.sleep(max(0.001, sleep_time))
    
    def stop(self):
        self.running = False

async def main():
    """Main entry point for PvP Arena Battle Server với JSON logging options"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Arena Battle Game Server - PvP Only with JSON Logging')
    parser.add_argument('--port', type=int, default=50051, help='Server port')
    parser.add_argument('--no-ui', action='store_true', help='Run without UI (headless)')
    parser.add_argument('--log-level', default='INFO', help='Log level')
    parser.add_argument('--min-players', type=int, default=2, help='Minimum players to start match')
    parser.add_argument('--max-players', type=int, default=8, help='Maximum players per match')
    
    # JSON Logging options
    parser.add_argument('--enable-json-logging', action='store_true', default=True, 
                       help='Enable JSON logging of gRPC data (default: True)')
    parser.add_argument('--disable-json-logging', action='store_true', 
                       help='Disable JSON logging completely')
    parser.add_argument('--log-rotation-minutes', type=int, default=5,
                       help='JSON log file rotation interval in minutes (default: 5)')
    parser.add_argument('--log-dir', default='logs/server_grpc_data',
                       help='Directory for JSON log files')
    parser.add_argument('--weapon-config', default=None,
                       help='Path to a versioned weapon config JSON file')
    
    args = parser.parse_args()
    
    # Determine logging settings
    enable_logging = args.enable_json_logging and not args.disable_json_logging
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create log directory if logging enabled
    if enable_logging:
        log_path = Path(args.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
    
    # Create game engine
    game_engine = GameEngine(args.weapon_config)
    
    # Create renderer if UI enabled
    renderer = None
    if not args.no_ui:
        try:
            renderer = GameRenderer()
            logger.info("✅ Renderer created successfully")
        except Exception as e:
            logger.error(f"❌ Renderer creation failed: {e}")
            renderer = None
    
    # Display startup banner
    logger.info("🤖 ==========================================")
    logger.info("🤖     ARENA BATTLE SERVER - ROOM MODE")
    logger.info("🤖 ==========================================")
    logger.info(f"🌐 Server port: {args.port}")
    logger.info(f"👥 Players required: {args.min_players}-{args.max_players}")
    logger.info(f"🎮 UI enabled: {'Yes' if not args.no_ui else 'No (headless)'}")
    logger.info("⚔️ Mode: PvP Only")
    logger.info(f"🔫 Weapon config: {game_engine.weapon_config.version}")
    logger.info("🎯 Waiting for AI bots to connect...")
    
    # JSON Logging info
    if enable_logging:
        logger.info("📝 ========== JSON LOGGING ENABLED ==========")
        logger.info(f"📁 Log directory: {args.log_dir}")
        logger.info(f"⏰ Rotation interval: {args.log_rotation_minutes} minutes")
        logger.info("📊 Logged data:")
        logger.info("   • Bot registrations & disconnections")
        logger.info("   • All observations sent to bots")
        logger.info("   • All actions received from bots")
        logger.info("   • Game events (kills, deaths, matches)")
        logger.info("   • Match events (start, end, player assignments)")
        logger.info("   • Error events & debugging info")
        logger.info("📝 =========================================")
    else:
        logger.info("📝 JSON Logging: DISABLED")
    
    if renderer:
        logger.info("🎨 UI Controls: 1,2,3,4 (speed), D (debug), ESC (quit)")
    
    logger.info("🤖 ==========================================")
    
    try:
        game_task = asyncio.create_task(game_engine.run())
        server_task = asyncio.create_task(run_server(
            game_engine, args.port, enable_logging=enable_logging
        ))

        # Wait a moment for server to be ready
        await asyncio.sleep(0.5)

        if renderer:
            renderer_task = asyncio.create_task(renderer.run(game_engine))
            await asyncio.gather(game_task, server_task, renderer_task)
        else:
            await asyncio.gather(game_task, server_task)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
        if enable_logging:
            logger.info("📁 JSON log files saved to: " + args.log_dir)
    finally:
        game_engine.stop()
        if renderer:
            renderer.stop()

if __name__ == "__main__":
    asyncio.run(main())
