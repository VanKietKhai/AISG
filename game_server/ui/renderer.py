# Modern UI Renderer - Fixed and Compact
import pygame
import math
import asyncio
import time
import logging
import random
from typing import Optional
from ..engine.game_state import BotState, GameState
logger = logging.getLogger(__name__)
class ModernColors:
    """Modern color palette with gradients and effects"""
    # Base colors
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    # Modern UI colors - Dark theme with neon accents
    BACKGROUND_PRIMARY = (10, 14, 39)      # Deep dark blue
    BACKGROUND_SECONDARY = (15, 20, 40)     # Slightly lighter
    BACKGROUND_TERTIARY = (25, 30, 50)     # Panel backgrounds
    # Neon accent colors
    NEON_CYAN = (0, 212, 255)              # Primary accent
    NEON_PINK = (255, 0, 128)              # Secondary accent  
    NEON_YELLOW = (255, 237, 78)           # Warning/special
    NEON_GREEN = (0, 255, 136)             # Success/health
    # UI element colors
    PANEL_BG = (15, 20, 40, 240)           # Semi-transparent panel
    BUTTON_NORMAL = (30, 35, 55)
    BUTTON_HOVER = (50, 55, 75) 
    BUTTON_ACTIVE = (0, 212, 255, 100)
    # Game element colors
    ARENA_BG = (10, 15, 30)
    WALL_PRIMARY = (100, 120, 150)
    WALL_SECONDARY = (80, 100, 130)
    WALL_BORDER = (150, 170, 200)
    # Bot colors with glow effects
    BOT_ALIVE = (0, 212, 255)
    BOT_ALIVE_GLOW = (0, 212, 255, 100)
    BOT_DEAD = (100, 100, 100)
    BOT_INVULNERABLE = (255, 237, 78)
    BOT_INVULNERABLE_GLOW = (255, 237, 78, 150)
    TEAM_A = (0, 212, 255)
    TEAM_A_DARK = (0, 110, 180)
    TEAM_A_GLOW = (0, 212, 255, 95)
    TEAM_B = (255, 92, 76)
    TEAM_B_DARK = (180, 52, 48)
    TEAM_B_GLOW = (255, 92, 76, 95)
    TEAM_OTHER = (200, 200, 200)
    # Bullet colors
    BULLET_CORE = (255, 237, 78)
    BULLET_GLOW = (255, 136, 0)
    # HP bar colors  
    HP_HIGH = (0, 255, 136)
    HP_MEDIUM = (255, 237, 78)
    HP_LOW = (255, 68, 68)
    HP_BG = (20, 20, 20, 180)
    # Text colors
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (200, 200, 200)
    TEXT_ACCENT = (0, 212, 255)
    TEXT_WARNING = (255, 237, 78)
class ModernButton:
    """Modern styled button with hover effects"""
    def __init__(self, x, y, width, height, text, font, active=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.active = active
        self.hover = False
        self.click_time = 0
    def handle_event(self, event):
        """Handle button events"""
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.click_time = time.time()
                return True
        return False
    def draw(self, surface):
        """Draw modern button with effects"""
        # Button background
        if self.active:
            color = ModernColors.NEON_CYAN
        elif self.hover:
            color = ModernColors.BUTTON_HOVER
        else:
            color = ModernColors.BUTTON_NORMAL
        # Draw main button
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        # Draw border
        border_color = ModernColors.NEON_CYAN if (self.active or self.hover) else ModernColors.TEXT_SECONDARY
        pygame.draw.rect(surface, border_color, self.rect, width=2, border_radius=8)
        # Draw button text
        text_color = ModernColors.TEXT_PRIMARY
        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
class GameRenderer:
    """Compact game renderer with fixed debug key"""
    def __init__(self, arena_width=800, arena_height=600):
        # Window/layout. The actual room map is 2000x1500, so the renderer
        # scales world coordinates into a visible viewport instead of cropping
        # the first 800x600 pixels.
        self.ui_panel_width = 360
        self.screen_width = 1366
        self.screen_height = 768
        self.arena_width = arena_width      # current visible viewport width, updated per frame
        self.arena_height = arena_height    # current visible viewport height, updated per frame
        self.world_width = arena_width      # current room/map width, updated per frame
        self.world_height = arena_height    # current room/map height, updated per frame
        self.scale = 1.0
        # Layout
        self.arena_offset_x = self.ui_panel_width + 24
        self.arena_offset_y = 66
        # Pygame objects
        self.screen = None
        self.clock = None
        self.fonts = {}
        # State
        self.running = False
        self.selected_bot = None
        self.show_debug = False  # Debug state tracking
        # UI elements
        self.speed_buttons = []
        # Animation timers
        self.title_glow_phase = 0
        logger.info(f"Compact renderer initialized: {self.screen_width}x{self.screen_height}")
        self._setup_ui_elements()
        self.current_viewing_room = None  # For spectator mode
        self.available_rooms = []  # List of all rooms
        self.viewing_mode = "room_001"
    def _setup_ui_elements(self):
        """Setup UI elements with compact layout"""
        # Speed control buttons - 2x2 grid
        button_width, button_height = 86, 40
        start_x, start_y = 28, 132
        speeds = [1.0, 2.0, 4.0, 10.0]
        labels = ["1x", "2x", "4x", "10x"]
        for i, (speed, label) in enumerate(zip(speeds, labels)):
            row = i // 2
            col = i % 2
            x = start_x + col * (button_width + 14)
            y = start_y + row * (button_height + 10)
            button = ModernButton(x, y, button_width, button_height, label, None, active=(speed == 1.0))
            button.speed = speed
            self.speed_buttons.append(button)
    def _initialize_fonts(self):
        """Initialize font system"""
        try:
            self.fonts = {
                'title': pygame.font.Font(None, 36),
                'subtitle': pygame.font.Font(None, 23),
                'normal': pygame.font.Font(None, 20),
                'small': pygame.font.Font(None, 18),
                'tiny': pygame.font.Font(None, 15),
            }
            # Update button fonts
            for button in self.speed_buttons:
                button.font = self.fonts['normal']
        except Exception as e:
            logger.error(f"Font initialization error: {e}")
            # Emergency fallback
            default_font = pygame.font.Font(None, 18)
            self.fonts = {key: default_font for key in ['title', 'subtitle', 'normal', 'small', 'tiny']}
    async def run(self, game_engine):
        """Main rendering loop"""
        if not self._initialize_pygame():
            return
        logger.info("Starting compact game renderer...")
        self.running = True
        try:
            while self.running:
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self._handle_key_press(event.key, game_engine)
                    elif event.type == pygame.VIDEORESIZE:
                        self.screen_width = max(1180, event.w)
                        self.screen_height = max(720, event.h)
                        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self._handle_mouse_click(event.pos, game_engine)
                    elif event.type == pygame.MOUSEMOTION:
                        self._handle_mouse_motion(event)
                # Update animations
                self.title_glow_phase += 0.08
                # Render frame
                self._render_frame(game_engine)
                # Control frame rate
                self.clock.tick(60)
                await asyncio.sleep(0.001)
        except Exception as e:
            logger.error(f"Renderer error: {e}")
        finally:
            self._cleanup()
    def _initialize_pygame(self) -> bool:
        """Initialize Pygame with compact window"""
        try:
            pygame.init()
            # Create compact window
            self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
            pygame.display.set_caption("Arena Battle - Team View")
            self.clock = pygame.time.Clock()
            # Initialize font system
            self._initialize_fonts()
            logger.info(f"Pygame initialized - Window: {self.screen_width}x{self.screen_height}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Pygame: {e}")
            return False
    def _render_frame(self, game_engine):
        """Render complete frame"""
        # Clear with gradient background
        self._render_background()
        # Render UI panel
        self._render_ui_panel(game_engine)
        # Render arena (perfectly fitted)
        self._render_arena(game_engine)
        # Update display
        pygame.display.flip()
    def _render_background(self):
        """Render background"""
        # Simple gradient
        for y in range(self.screen_height):
            ratio = y / self.screen_height
            r = int(ModernColors.BACKGROUND_PRIMARY[0] * (1-ratio) + ModernColors.BACKGROUND_SECONDARY[0] * ratio)
            g = int(ModernColors.BACKGROUND_PRIMARY[1] * (1-ratio) + ModernColors.BACKGROUND_SECONDARY[1] * ratio)  
            b = int(ModernColors.BACKGROUND_PRIMARY[2] * (1-ratio) + ModernColors.BACKGROUND_SECONDARY[2] * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.screen_width, y))
    def _render_ui_panel(self, game_engine):
        """Render readable left UI panel with team-separated information."""
        panel_rect = pygame.Rect(0, 0, self.ui_panel_width, self.screen_height)
        pygame.draw.rect(self.screen, ModernColors.BACKGROUND_TERTIARY, panel_rect)
        pygame.draw.line(self.screen, ModernColors.NEON_CYAN,
                        (self.ui_panel_width, 0), (self.ui_panel_width, self.screen_height), 2)

        y_offset = 18
        self._render_title(y_offset)
        y_offset += 58

        mode_surface = self.fonts['normal'].render("PvP Combat Mode", True, ModernColors.NEON_PINK)
        self.screen.blit(mode_surface, (28, y_offset))
        y_offset += 38

        speed_title = self.fonts['subtitle'].render("Speed Control", True, ModernColors.NEON_CYAN)
        self.screen.blit(speed_title, (28, y_offset - 16))
        y_offset += 28

        for button in self.speed_buttons:
            button.draw(self.screen)
        y_offset += 104

        y_offset = self._render_stats(game_engine, y_offset)
        y_offset += 16
        y_offset = self._render_bot_list(game_engine, y_offset)

        self._render_controls(self.screen_height - 104)
    def _render_title(self, y):
        """Render animated title"""
        title_text = "ARENA BATTLE"
        # Glow effect
        glow_intensity = int(100 + 50 * math.sin(self.title_glow_phase))
        glow_color = (*ModernColors.NEON_CYAN[:3], glow_intensity)
        # Main title
        title_surface = self.fonts['title'].render(title_text, True, ModernColors.TEXT_PRIMARY)
        title_rect = title_surface.get_rect(center=(self.ui_panel_width//2, y + 20))
        self.screen.blit(title_surface, title_rect)
    def _get_viewed_bots(self, game_engine):
        """Return bots from the currently selected room without truncating the team data."""
        game_state, _ = self._get_viewed_game_state(game_engine)
        return list(game_state.bots.values())

    def _team_label(self, bot):
        """Normalize team id into the labels used by the UI."""
        raw = (getattr(bot, "team_id", None) or getattr(bot, "player_id", None) or "").strip()
        name = (getattr(bot, "name", "") or "").strip()
        key = f"{raw} {name}".lower().replace("_", "").replace("-", "")
        if "teamb" in key or key.endswith(" b") or key == "b":
            return "Team B"
        if "teama" in key or key.endswith(" a") or key == "a":
            return "Team A"
        if raw:
            return raw[:1].upper() + raw[1:]
        return "No Team"

    def _team_color(self, label, fallback_index=0):
        label_lower = str(label).lower()
        if "team a" in label_lower or label_lower == "a":
            return ModernColors.TEAM_A
        if "team b" in label_lower or label_lower == "b":
            return ModernColors.TEAM_B
        return ModernColors.NEON_GREEN if fallback_index % 2 == 0 else ModernColors.NEON_YELLOW

    def _team_glow(self, label):
        label_lower = str(label).lower()
        if "team a" in label_lower or label_lower == "a":
            return ModernColors.TEAM_A_GLOW
        if "team b" in label_lower or label_lower == "b":
            return ModernColors.TEAM_B_GLOW
        return (*ModernColors.TEAM_OTHER[:3], 80)

    def _role_abbr(self, bot):
        role = (getattr(bot, "weapon_type", None) or getattr(bot, "role", None) or "AR").upper()
        if role == "SNIPER":
            return "SNI"
        if role == "SMG":
            return "SMG"
        return "AR"

    def _team_stats(self, bots):
        grouped = {}
        for bot in bots:
            label = self._team_label(bot)
            if label not in grouped:
                grouped[label] = {"bots": 0, "alive": 0, "kills": 0, "deaths": 0, "members": []}
            grouped[label]["bots"] += 1
            grouped[label]["kills"] += int(getattr(bot, "kills", 0) or 0)
            grouped[label]["deaths"] += int(getattr(bot, "deaths", 0) or 0)
            grouped[label]["members"].append(bot)
            if getattr(bot, "state", None) in [BotState.ALIVE, BotState.INVULNERABLE]:
                grouped[label]["alive"] += 1
        for label in ("Team A", "Team B"):
            grouped.setdefault(label, {"bots": 0, "alive": 0, "kills": 0, "deaths": 0, "members": []})
        return grouped

    def _render_stats(self, game_engine, y):
        """Render readable statistics split by Team A and Team B."""
        stats_title = self.fonts['subtitle'].render("Statistics", True, ModernColors.NEON_CYAN)
        self.screen.blit(stats_title, (28, y))
        y += 26

        game_state, _ = self._get_viewed_game_state(game_engine)
        stats = game_state.get_game_stats()
        bots = list(game_state.bots.values())
        team_stats = self._team_stats(bots)
        team_a = team_stats.get("Team A", {"bots": 0, "alive": 0, "kills": 0, "deaths": 0})
        team_b = team_stats.get("Team B", {"bots": 0, "alive": 0, "kills": 0, "deaths": 0})

        basic_lines = [
            f"Tick: {stats['tick']:,}",
            f"FPS: {stats['fps']:.1f}",
            f"Speed: {stats['speed_multiplier']}x",
            f"Uptime: {stats['uptime']:.0f}s",
            f"Team A: {team_a['bots']}     Team B: {team_b['bots']}",
        ]
        for line in basic_lines:
            line_surface = self.fonts['small'].render(line, True, ModernColors.TEXT_SECONDARY)
            self.screen.blit(line_surface, (28, y))
            y += 21

        table_x = 28
        table_y = y + 3
        table_w = self.ui_panel_width - 56
        table_h = 104
        mid_x = table_x + table_w // 2
        row_h = 25

        pygame.draw.rect(self.screen, ModernColors.BUTTON_NORMAL, (table_x, table_y, table_w, table_h), border_radius=6)
        pygame.draw.rect(self.screen, ModernColors.NEON_CYAN, (table_x, table_y, table_w, table_h), width=1, border_radius=6)
        pygame.draw.line(self.screen, ModernColors.TEXT_SECONDARY, (mid_x, table_y), (mid_x, table_y + table_h), 1)
        for r in range(1, 4):
            pygame.draw.line(self.screen, (70, 80, 105), (table_x, table_y + r * row_h), (table_x + table_w, table_y + r * row_h), 1)

        left_header = self.fonts['small'].render("TEAM A", True, ModernColors.TEAM_A)
        right_header = self.fonts['small'].render("TEAM B", True, ModernColors.TEAM_B)
        self.screen.blit(left_header, left_header.get_rect(center=(table_x + table_w * 0.25, table_y + 13)))
        self.screen.blit(right_header, right_header.get_rect(center=(table_x + table_w * 0.75, table_y + 13)))

        rows = [
            ("Alive", f"{team_a['alive']}/{team_a['bots']}", f"{team_b['alive']}/{team_b['bots']}"),
            ("Kills", str(team_a['kills']), str(team_b['kills'])),
            ("Deaths", str(team_a['deaths']), str(team_b['deaths'])),
        ]
        for idx, (label, left, right) in enumerate(rows, start=1):
            cy = table_y + idx * row_h + 13
            label_surface = self.fonts['tiny'].render(label, True, ModernColors.TEXT_SECONDARY)
            self.screen.blit(label_surface, (table_x + 8, cy - 7))
            left_surface = self.fonts['small'].render(left, True, ModernColors.TEXT_PRIMARY)
            right_surface = self.fonts['small'].render(right, True, ModernColors.TEXT_PRIMARY)
            self.screen.blit(left_surface, left_surface.get_rect(center=(table_x + table_w * 0.36, cy)))
            self.screen.blit(right_surface, right_surface.get_rect(center=(table_x + table_w * 0.86, cy)))

        return table_y + table_h

    def _render_bot_list(self, game_engine, y):
        """Render bot list separated by team."""
        bots_title = self.fonts['subtitle'].render("Active Bots", True, ModernColors.NEON_CYAN)
        self.screen.blit(bots_title, (28, y))
        y += 26

        bots = self._get_viewed_bots(game_engine)
        team_stats = self._team_stats(bots)
        ordered_labels = ["Team A", "Team B"]
        for label in sorted(team_stats.keys()):
            if label not in ordered_labels and team_stats[label]["bots"] > 0:
                ordered_labels.append(label)

        max_members_per_team = 4
        for team_index, label in enumerate(ordered_labels):
            members = sorted(team_stats[label]["members"], key=lambda b: (getattr(b, "weapon_type", ""), getattr(b, "name", "")))[:max_members_per_team]
            if not members and label not in ("Team A", "Team B"):
                continue

            color = self._team_color(label, team_index)
            header_rect = pygame.Rect(28, y, self.ui_panel_width - 56, 22)
            pygame.draw.rect(self.screen, (22, 28, 48), header_rect, border_radius=4)
            pygame.draw.line(self.screen, color, (header_rect.x + 4, header_rect.centery), (header_rect.right - 4, header_rect.centery), 2)
            header_text = self.fonts['tiny'].render(f" {label} ", True, color)
            pygame.draw.rect(self.screen, ModernColors.BACKGROUND_TERTIARY, header_text.get_rect(topleft=(header_rect.x + 8, header_rect.y + 3)).inflate(8, 0))
            self.screen.blit(header_text, (header_rect.x + 12, header_rect.y + 3))
            y += 26

            if not members:
                empty_surface = self.fonts['tiny'].render("Waiting for bots...", True, ModernColors.TEXT_SECONDARY)
                self.screen.blit(empty_surface, (42, y))
                y += 18
            else:
                for bot in members:
                    if bot.state == BotState.ALIVE:
                        status_color = color
                        status = "ALV"
                    elif bot.state == BotState.INVULNERABLE:
                        status_color = ModernColors.BOT_INVULNERABLE
                        status = "INV"
                    else:
                        status_color = ModernColors.BOT_DEAD
                        status = "DED"

                    selected_prefix = "> " if bot == self.selected_bot else "  "
                    role = self._role_abbr(bot)
                    short_name = bot.name if len(bot.name) <= 16 else bot.name[:13] + "..."
                    line = f"{selected_prefix}[{role}] {short_name}"
                    bot_surface = self.fonts['tiny'].render(line, True, status_color)
                    self.screen.blit(bot_surface, (38, y))

                    kd_text = f"{bot.kills}K/{bot.deaths}D"
                    kd_surface = self.fonts['tiny'].render(kd_text, True, ModernColors.TEXT_SECONDARY)
                    self.screen.blit(kd_surface, (self.ui_panel_width - 82, y))

                    status_surface = self.fonts['tiny'].render(status, True, status_color)
                    self.screen.blit(status_surface, (self.ui_panel_width - 132, y))
                    y += 19
            y += 6
        return y
    def _render_controls(self, y):
        """Render controls section"""
        controls_title = self.fonts['subtitle'].render("Controls", True, ModernColors.NEON_CYAN)
        self.screen.blit(controls_title, (28, y))
        y += 20
        controls = [
            "1,2,3,4 - Speed",
            "Click - Select Bot", 
            "F3 - Debug Mode",
            "R - Cycle Rooms",
            "S - Save Models",
            "ESC - Quit"
        ]
        for control in controls:
            control_surface = self.fonts['tiny'].render(control, True, ModernColors.TEXT_SECONDARY)
            self.screen.blit(control_surface, (28, y))
            y += 15
    def _get_viewed_game_state(self, game_engine):
        """Return the room state currently shown by the UI."""
        game_state = None
        room_info = ""

        if self.viewing_mode != "default":
            room_state = game_engine.get_room_state(self.viewing_mode)
            if room_state:
                game_state = room_state
                wall_count = len(room_state.walls)
                obstacle_count = max(0, wall_count - 4)
                room_info = f"Room: {self.viewing_mode} ({wall_count} walls, {obstacle_count} obstacles)"
            else:
                game_state = game_engine.game_state
                room_info = f"Default State (room '{self.viewing_mode}' not found)"
        else:
            available_rooms = list(game_engine.room_states.keys())
            if available_rooms:
                fallback_room = available_rooms[0]
                game_state = game_engine.room_states[fallback_room]
                wall_count = len(game_state.walls)
                obstacle_count = max(0, wall_count - 4)
                room_info = f"Viewing: {fallback_room} ({wall_count} walls, {obstacle_count} obstacles)"
            else:
                from game_server.engine.game_state import GameState
                game_state = GameState()
                room_info = "No rooms available"
        return game_state, room_info

    def _compute_arena_rect(self, game_state):
        """Fit the full world/map into the current pygame window."""
        self.world_width = max(1.0, float(getattr(game_state, "width", self.world_width) or self.world_width))
        self.world_height = max(1.0, float(getattr(game_state, "height", self.world_height) or self.world_height))

        max_display_width = max(320, self.screen_width - self.ui_panel_width - 40)
        max_display_height = max(240, self.screen_height - self.arena_offset_y - 40)
        self.scale = min(max_display_width / self.world_width, max_display_height / self.world_height)
        self.scale = max(0.05, min(self.scale, 1.0))

        self.arena_width = int(self.world_width * self.scale)
        self.arena_height = int(self.world_height * self.scale)

        return pygame.Rect(
            self.arena_offset_x,
            self.arena_offset_y,
            self.arena_width,
            self.arena_height,
        )

    def _world_to_screen(self, x, y, arena_rect):
        return arena_rect.x + float(x) * self.scale, arena_rect.y + float(y) * self.scale

    def _screen_to_world(self, x, y, arena_rect):
        return (float(x) - arena_rect.x) / self.scale, (float(y) - arena_rect.y) / self.scale

    def _render_arena(self, game_engine):
        """Render the selected room scaled to the visible window."""
        game_state, room_info = self._get_viewed_game_state(game_engine)
        arena_rect = self._compute_arena_rect(game_state)

        header_text = (
            f"🏟️ Combat Arena world {int(self.world_width)}x{int(self.world_height)} "
            f"→ view {self.arena_width}x{self.arena_height} ({self.scale:.2f}x)"
        )
        header_surface = self.fonts['normal'].render(header_text, True, ModernColors.TEXT_PRIMARY)
        self.screen.blit(header_surface, (self.arena_offset_x, self.arena_offset_y - 30))

        room_surface = self.fonts['small'].render(room_info, True, ModernColors.TEXT_SECONDARY)
        self.screen.blit(room_surface, (self.arena_offset_x, self.arena_offset_y - 10))

        pygame.draw.rect(self.screen, ModernColors.ARENA_BG, arena_rect)

        if self.viewing_mode == "room_001":
            border_color = ModernColors.NEON_CYAN
        elif self.viewing_mode == "room_002":
            border_color = ModernColors.NEON_PINK
        else:
            border_color = ModernColors.NEON_YELLOW
        pygame.draw.rect(self.screen, border_color, arena_rect, width=2)

        # Clip game objects to the arena viewport so bullets/bots never draw outside it.
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(arena_rect)
        try:
            self._render_walls(game_state, arena_rect)
            self._render_bullets(game_state, arena_rect)
            self._render_bots(game_state, arena_rect)
        finally:
            self.screen.set_clip(previous_clip)

        if self.show_debug:
            self._render_debug_overlay(game_state, arena_rect)

    def _render_walls(self, game_state, arena_rect):
        """Render walls với debug info"""
        for i, wall in enumerate(game_state.walls):
            wall_rect = pygame.Rect(
                int(arena_rect.x + wall.x * self.scale),
                int(arena_rect.y + wall.y * self.scale),
                max(1, int(wall.width * self.scale)),
                max(1, int(wall.height * self.scale))
            )
            
            # Render wall
            pygame.draw.rect(self.screen, ModernColors.WALL_PRIMARY, wall_rect)
            pygame.draw.rect(self.screen, ModernColors.WALL_BORDER, wall_rect, width=2)
            
            # Debug outline
            if self.show_debug:
                pygame.draw.rect(self.screen, ModernColors.NEON_YELLOW, wall_rect, width=1)
    
    def _render_bullets(self, game_state, arena_rect):
        """Render bullets with glow"""
        for bullet in game_state.bullets:
            bullet_x, bullet_y = self._world_to_screen(bullet.x, bullet.y, arena_rect)
            bullet_radius = max(2, bullet.radius * self.scale)
            
            # Glow effect
            for i in range(3, 0, -1):
                glow_radius = bullet_radius * (1 + i * 0.5)
                glow_alpha = 80 // i
                glow_color = (*ModernColors.BULLET_GLOW[:3], glow_alpha)
                
                glow_radius_i = max(1, int(glow_radius))
                glow_surf = pygame.Surface((glow_radius_i * 4, glow_radius_i * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, glow_color, (glow_radius_i * 2, glow_radius_i * 2), glow_radius_i)
                self.screen.blit(glow_surf, (bullet_x - glow_radius_i * 2, bullet_y - glow_radius_i * 2), 
                               special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Core bullet
            pygame.draw.circle(self.screen, ModernColors.BULLET_CORE,
                             (int(bullet_x), int(bullet_y)), int(bullet_radius))
            
            # Debug info
            if self.show_debug:
                # Velocity vector
                vel_scale = 0.1
                end_x = bullet_x + bullet.vel_x * vel_scale
                end_y = bullet_y + bullet.vel_y * vel_scale
                pygame.draw.line(self.screen, ModernColors.NEON_YELLOW,
                               (int(bullet_x), int(bullet_y)),
                               (int(end_x), int(end_y)), 2)
    
    def _render_bots(self, game_state, arena_rect):
        """Render bots"""
        for bot in game_state.bots.values():
            self._render_bot(bot, arena_rect)
    
    def _render_bot(self, bot, arena_rect):
        """Render individual bot with team color and weapon/role silhouette."""
        bot_x, bot_y = self._world_to_screen(bot.x, bot.y, arena_rect)
        bot_radius = max(10, int(bot.radius * self.scale * 1.25))

        team_label = self._team_label(bot)
        team_color = self._team_color(team_label)
        team_glow = self._team_glow(team_label)
        role = self._role_abbr(bot)

        if bot.state == BotState.DEAD:
            core_color = ModernColors.BOT_DEAD
            ring_color = (150, 150, 150)
            glow_color = (*ModernColors.BOT_DEAD[:3], 45)
        elif bot.state == BotState.INVULNERABLE:
            core_color = ModernColors.BOT_INVULNERABLE
            ring_color = team_color
            glow_color = ModernColors.BOT_INVULNERABLE_GLOW
        else:
            core_color = team_color
            ring_color = ModernColors.WHITE
            glow_color = team_glow

        # Selection highlight
        if bot == self.selected_bot:
            for i in range(4, 0, -1):
                highlight_radius = bot_radius + i * 5
                highlight_alpha = 70 // i
                highlight_color = (*ModernColors.NEON_YELLOW[:3], highlight_alpha)
                highlight_surf = pygame.Surface((highlight_radius * 4, highlight_radius * 4), pygame.SRCALPHA)
                pygame.draw.circle(highlight_surf, highlight_color,
                                 (highlight_radius * 2, highlight_radius * 2), highlight_radius)
                self.screen.blit(highlight_surf,
                               (bot_x - highlight_radius * 2, bot_y - highlight_radius * 2),
                               special_flags=pygame.BLEND_ALPHA_SDL2)

        # Team glow, bigger than old body so each team is visible at low scale.
        if bot.state != BotState.DEAD:
            for i in range(3, 0, -1):
                glow_radius = int(bot_radius * (1.3 + i * 0.3))
                glow_alpha = 70 // i
                current_glow = (*glow_color[:3], glow_alpha)
                glow_surf = pygame.Surface((glow_radius * 4, glow_radius * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, current_glow,
                                 (glow_radius * 2, glow_radius * 2), glow_radius)
                self.screen.blit(glow_surf,
                               (bot_x - glow_radius * 2, bot_y - glow_radius * 2),
                               special_flags=pygame.BLEND_ALPHA_SDL2)

        # Weapon barrel / direction indicator. Different gun roles get different silhouettes.
        if bot.state in [BotState.ALIVE, BotState.INVULNERABLE]:
            aim = float(getattr(bot, "aim_angle", 0.0) or 0.0)
            ux, uy = math.cos(aim), math.sin(aim)
            px, py = -uy, ux
            start = (int(bot_x + ux * (bot_radius * 0.25)), int(bot_y + uy * (bot_radius * 0.25)))

            if role == "SNI":
                length = bot_radius + 26
                width = 3
                end = (int(bot_x + ux * length), int(bot_y + uy * length))
                pygame.draw.line(self.screen, ModernColors.NEON_YELLOW, start, end, width)
                scope = (int(bot_x + ux * (bot_radius + 12)), int(bot_y + uy * (bot_radius + 12)))
                pygame.draw.circle(self.screen, ModernColors.WHITE, scope, 4, 1)
                pygame.draw.line(self.screen, ModernColors.WHITE,
                                 (int(end[0] + px * 4), int(end[1] + py * 4)),
                                 (int(end[0] - px * 4), int(end[1] - py * 4)), 1)
            elif role == "SMG":
                length = bot_radius + 14
                end = (int(bot_x + ux * length), int(bot_y + uy * length))
                pygame.draw.line(self.screen, ModernColors.NEON_YELLOW, start, end, 5)
                muzzle = pygame.Rect(0, 0, 6, 6)
                muzzle.center = end
                pygame.draw.rect(self.screen, ModernColors.WHITE, muzzle, border_radius=2)
            else:  # AR
                length = bot_radius + 20
                end = (int(bot_x + ux * length), int(bot_y + uy * length))
                pygame.draw.line(self.screen, ModernColors.NEON_YELLOW, start, end, 4)
                mag_center = (bot_x + ux * (bot_radius + 2), bot_y + uy * (bot_radius + 2))
                pygame.draw.line(self.screen, ModernColors.WHITE,
                                 (int(mag_center[0]), int(mag_center[1])),
                                 (int(mag_center[0] + px * 8), int(mag_center[1] + py * 8)), 3)

        # Role-specific bot body shape.
        cx, cy = int(bot_x), int(bot_y)
        aim = float(getattr(bot, "aim_angle", 0.0) or 0.0)
        if role == "SNI":
            points = []
            for ang, dist in [(aim, bot_radius * 1.35), (aim + 2.35, bot_radius), (aim - 2.35, bot_radius)]:
                points.append((int(bot_x + math.cos(ang) * dist), int(bot_y + math.sin(ang) * dist)))
            pygame.draw.polygon(self.screen, core_color, points)
            pygame.draw.polygon(self.screen, ring_color, points, width=2)
        elif role == "SMG":
            points = [(cx, cy - bot_radius), (cx + bot_radius, cy), (cx, cy + bot_radius), (cx - bot_radius, cy)]
            pygame.draw.polygon(self.screen, core_color, points)
            pygame.draw.polygon(self.screen, ring_color, points, width=2)
        else:
            pygame.draw.circle(self.screen, core_color, (cx, cy), bot_radius)
            pygame.draw.circle(self.screen, ring_color, (cx, cy), bot_radius, 2)

        # Clear role text inside the bot.
        role_surface = self.fonts['tiny'].render(role, True, ModernColors.BLACK if bot.state != BotState.DEAD else ModernColors.WHITE)
        role_rect = role_surface.get_rect(center=(cx, cy))
        self.screen.blit(role_surface, role_rect)

        if bot.state == BotState.DEAD:
            pygame.draw.line(self.screen, ModernColors.HP_LOW, (cx - bot_radius, cy - bot_radius), (cx + bot_radius, cy + bot_radius), 3)
            pygame.draw.line(self.screen, ModernColors.HP_LOW, (cx + bot_radius, cy - bot_radius), (cx - bot_radius, cy + bot_radius), 3)

        # HP bar
        if bot.state != BotState.DEAD:
            self._render_hp_bar(bot, bot_x, bot_y - bot_radius - 22)

        # Bot name + team label
        name_display = bot.name if len(bot.name) <= 12 else bot.name[:9] + "..."
        label_text = f"{team_label[-1]}-{name_display}"
        name_surface = self.fonts['tiny'].render(label_text, True, ModernColors.TEXT_PRIMARY)
        name_rect = name_surface.get_rect(center=(int(bot_x), int(bot_y + bot_radius + 21)))
        bg_rect = name_rect.inflate(8, 4)
        pygame.draw.rect(self.screen, (*ModernColors.BLACK[:3], 190), bg_rect, border_radius=3)
        pygame.draw.rect(self.screen, team_color, bg_rect, width=1, border_radius=3)
        self.screen.blit(name_surface, name_rect)

        if self.show_debug:
            debug_text = f"ID:{bot.id} HP:{bot.hp:.0f} K/D:{bot.kills}/{bot.deaths} {role}"
            debug_surface = self.fonts['tiny'].render(debug_text, True, ModernColors.NEON_CYAN)
            self.screen.blit(debug_surface, (int(bot_x - 48), int(bot_y + bot_radius + 38)))
    def _render_hp_bar(self, bot, x, y):
        """Render HP bar"""
        bar_width = max(30, int(50 * self.scale))
        bar_height = max(4, int(6 * self.scale))
        
        # Background
        bg_rect = pygame.Rect(x - bar_width//2, y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (*ModernColors.HP_BG[:3], 200), bg_rect)
        
        # HP fill
        hp_ratio = bot.hp / bot.max_hp
        fill_width = int(bar_width * hp_ratio)
        
        if fill_width > 0:
            if hp_ratio > 0.6:
                fill_color = ModernColors.HP_HIGH
            elif hp_ratio > 0.3:
                fill_color = ModernColors.HP_MEDIUM
            else:
                fill_color = ModernColors.HP_LOW
            
            fill_rect = pygame.Rect(x - bar_width//2, y, fill_width, bar_height)
            pygame.draw.rect(self.screen, fill_color, fill_rect)
        
        # Border
        pygame.draw.rect(self.screen, ModernColors.WHITE, bg_rect, width=1)
        
        # HP text
        hp_text = f"{bot.hp:.0f}"
        hp_surface = self.fonts['tiny'].render(hp_text, True, ModernColors.TEXT_PRIMARY)
        hp_rect = hp_surface.get_rect(center=(int(x), int(y - 8)))
        self.screen.blit(hp_surface, hp_rect)
    
    def _render_debug_overlay(self, game_state, arena_rect):
        """Render debug information overlay"""
        debug_y = arena_rect.bottom + 10
        
        debug_info = [
            f"Debug Mode: ON",
            f"World: {int(self.world_width)}x{int(self.world_height)}",
            f"View: {arena_rect.width}x{arena_rect.height}",
            f"Scale: {self.scale:.2f}x",
            f"Bots: {len(game_state.bots)}",
            f"Bullets: {len(game_state.bullets)}",
            f"Walls: {len(game_state.walls)}"
        ]
        
        for i, info in enumerate(debug_info):
            debug_surface = self.fonts['tiny'].render(info, True, ModernColors.NEON_YELLOW)
            self.screen.blit(debug_surface, (arena_rect.x, debug_y + i * 12))
    
    def _render_selected_bot_info(self):
        """Render selected bot info panel"""
        if not self.selected_bot:
            return
        
        # Compact info panel
        panel_width = 200
        panel_height = 160
        panel_x = self.screen_width - panel_width - 10
        panel_y = 80
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Panel background
        pygame.draw.rect(self.screen, (*ModernColors.BACKGROUND_TERTIARY[:3], 240), panel_rect)
        pygame.draw.rect(self.screen, ModernColors.NEON_CYAN, panel_rect, width=2)
        
        # Title
        title_surface = self.fonts['normal'].render("🎯 Selected Bot", True, ModernColors.NEON_CYAN)
        self.screen.blit(title_surface, (panel_x + 10, panel_y + 10))
        
        # Bot details
        details = [
            f"Name: {self.selected_bot.name[:15]}",
            f"ID: {self.selected_bot.id}",
            f"Player: {self.selected_bot.player_id[:12]}",
            f"State: {self.selected_bot.state.value.upper()}",
            f"HP: {self.selected_bot.hp:.1f}/{self.selected_bot.max_hp}",
            f"Position: ({self.selected_bot.x:.0f}, {self.selected_bot.y:.0f})",
            f"Kills: {self.selected_bot.kills}",
            f"Deaths: {self.selected_bot.deaths}",
            f"K/D: {self.selected_bot.kills/max(self.selected_bot.deaths,1):.2f}"
        ]
        
        detail_y = panel_y + 35
        for detail in details:
            detail_surface = self.fonts['small'].render(detail, True, ModernColors.TEXT_SECONDARY)
            self.screen.blit(detail_surface, (panel_x + 10, detail_y))
            detail_y += 14
    
    def _handle_key_press(self, key, game_engine):
        """Handle keyboard input - FIXED DEBUG KEY"""
        if key == pygame.K_ESCAPE:
            self.running = False
            logger.info("Exiting renderer...")
        elif key == pygame.K_1:
            self._set_speed(0, game_engine)
        elif key == pygame.K_2:
            self._set_speed(1, game_engine)
        elif key == pygame.K_3:
            self._set_speed(2, game_engine)
        elif key == pygame.K_4:
            self._set_speed(3, game_engine)
        elif key == pygame.K_F3:
            # FIXED: Debug toggle now works properly
            self.show_debug = not self.show_debug
            debug_status = "ON" if self.show_debug else "OFF"
            logger.info(f"Debug mode: {debug_status}")
        elif key == pygame.K_c:
            self.selected_bot = None
            logger.info("Bot selection cleared")
        elif key == pygame.K_s:
            logger.info("Manual model save triggered")
        elif key == pygame.K_r:
            self._cycle_viewing_room(game_engine)
    
    def _set_speed(self, button_index, game_engine):
        """Set game speed with visual feedback"""
        if 0 <= button_index < len(self.speed_buttons):
            # Update button states
            for i, button in enumerate(self.speed_buttons):
                button.active = (i == button_index)
            
            # Update game speed for default state and all room states
            new_speed = self.speed_buttons[button_index].speed
            game_engine.game_state.speed_multiplier = new_speed
            for room_state in getattr(game_engine, "room_states", {}).values():
                room_state.speed_multiplier = new_speed
            logger.info(f"Speed changed to {new_speed}x")
    
    def _handle_mouse_click(self, pos, game_engine):
        """Handle mouse clicks."""
        mouse_x, mouse_y = pos

        # Check speed buttons
        for i, button in enumerate(self.speed_buttons):
            if button.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos)):
                self._set_speed(i, game_engine)
                return

        game_state, _ = self._get_viewed_game_state(game_engine)
        arena_rect = self._compute_arena_rect(game_state)

        if arena_rect.collidepoint(mouse_x, mouse_y):
            arena_x, arena_y = self._screen_to_world(mouse_x, mouse_y, arena_rect)
            closest_bot = None
            closest_distance = float('inf')

            for bot in game_state.bots.values():
                dx = bot.x - arena_x
                dy = bot.y - arena_y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < bot.radius + 40 and distance < closest_distance:
                    closest_bot = bot
                    closest_distance = distance

            if closest_bot:
                self.selected_bot = closest_bot
                logger.info(f"Selected bot: {closest_bot.name} (ID: {closest_bot.id})")
            else:
                self.selected_bot = None

    def _handle_mouse_motion(self, event):
        """Handle mouse motion for hover effects"""
        for button in self.speed_buttons:
            button.handle_event(event)
    
    def stop(self):
        """Stop the renderer"""
        self.running = False
        logger.info("Renderer stopping...")
    
    def _cleanup(self):
        """Clean up Pygame resources"""
        if pygame.get_init():
            pygame.quit()
        logger.info("Renderer stopped")

    def _cycle_viewing_room(self, game_engine):
        """Cycle through available room states - FIXED TO WORK IMMEDIATELY"""
        room_states = game_engine.get_all_room_states()
        
        if not room_states:
            logger.info("🔄 No room states available")
            return
        
        # Danh sách rooms: default + room states
        room_ids = list(room_states.keys())
        
        if self.viewing_mode not in room_ids:
            # Chuyển tới room đầu tiên (không phải default)
            self.viewing_mode = room_ids[1] if len(room_ids) > 1 else room_ids[0]
        else:
            # Cycle tới room tiếp theo
            current_idx = room_ids.index(self.viewing_mode)
            next_idx = (current_idx + 1) % len(room_ids)
            self.viewing_mode = room_ids[next_idx]
        
        logger.info(f"🔄 Now viewing: {self.viewing_mode}")

# Keep the original class name for compatibility
ModernGameRenderer = GameRenderer