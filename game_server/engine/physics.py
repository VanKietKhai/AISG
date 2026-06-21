# Physics logic
import numpy as np
import math
import time
import random
import logging
from typing import List, Tuple
from .game_state import Bot, Bullet, BotState, GameState

logger = logging.getLogger(__name__)

class PhysicsEngine:
    """Handles all physics simulation"""
    
    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.rng = random.Random(game_state.match_seed)
        
        # Physics constants
        self.bullet_speed = 400.0  # pixels per second
        self.max_bot_speed = 320.0
        self.bot_acceleration = 1200.0
        self.friction = 0.88
        self.shot_cooldown = 0.3  # seconds
        self.respawn_delay = 1.0  # seconds
        self.invulnerability_time = 1.0  # seconds
    
    def update(self, dt: float):
        """Update physics for one frame"""
        # Clamp dt to prevent instability
        dt = min(dt, 0.1)
        
        # Update bots
        self._update_weapon_states(dt)
        self._update_bots(dt)
        
        # Update bullets
        self._update_bullets(dt)
        
        # Check collisions
        self._check_bullet_collisions()
        self._expire_range_limited_bullets()
        self._check_bot_collisions()
        
        # Handle respawns
        self._handle_respawns()
        
        # Increment tick
        self.game_state.tick += 1

    def _update_weapon_states(self, dt: float):
        """Advance deterministic cooldown, reload and bloom timers."""
        for bot in self.game_state.bots.values():
            if bot.weapon_state is None:
                continue
            definition = self.game_state.weapon_config.get(bot.weapon_type)
            was_reloading = bot.weapon_state.is_reloading
            ammo_before = bot.weapon_state.ammo
            bot.weapon_state.update(dt, definition)
            if not was_reloading and bot.weapon_state.is_reloading:
                self.game_state.record_weapon_event(
                    'reload_started', bot_id=bot.id, weapon_type=definition.key,
                    ammo_before=ammo_before,
                    reload_time_seconds=definition.reload_seconds,
                )
            elif was_reloading and not bot.weapon_state.is_reloading:
                self.game_state.record_weapon_event(
                    'reload_finished', bot_id=bot.id, weapon_type=definition.key,
                    ammo_before=ammo_before, ammo_after=bot.weapon_state.ammo,
                )
    
    def _update_bots(self, dt: float):
        """Update bot physics"""
        for bot in self.game_state.bots.values():
            if bot.state not in [BotState.ALIVE, BotState.INVULNERABLE]:
                continue
            
            # Apply friction
            bot.vel_x *= self.friction
            bot.vel_y *= self.friction
            
            # Update position
            new_x = bot.x + bot.vel_x * dt
            new_y = bot.y + bot.vel_y * dt
            
            # Check bounds and walls
            if self.game_state._is_position_valid(new_x, bot.y, bot.radius):
                bot.x = new_x
            else:
                bot.vel_x = 0
            
            if self.game_state._is_position_valid(bot.x, new_y, bot.radius):
                bot.y = new_y
            else:
                bot.vel_y = 0
    
    def _update_bullets(self, dt: float):
        """Update bullet physics"""
        bullets_to_remove = []
        
        for bullet in self.game_state.bullets:
            # Update position
            bullet.previous_x = bullet.x
            bullet.previous_y = bullet.y
            delta_x = bullet.vel_x * dt
            delta_y = bullet.vel_y * dt
            requested_distance = math.hypot(delta_x, delta_y)
            remaining_range = max(0.0, bullet.max_range - bullet.distance_travelled)
            if requested_distance > remaining_range and requested_distance > 0.0:
                scale = remaining_range / requested_distance
                delta_x *= scale
                delta_y *= scale
            bullet.x += delta_x
            bullet.y += delta_y
            bullet.distance_travelled += math.hypot(delta_x, delta_y)

            if bullet.distance_travelled >= bullet.max_range:
                # Let collision resolution inspect the final in-range segment
                # before classifying a surviving projectile as a miss.
                bullet.range_exhausted = True
            
            # Check bounds
            if (bullet.x < 0 or bullet.x > self.game_state.width or
                bullet.y < 0 or bullet.y > self.game_state.height):
                self.game_state.record_weapon_event(
                    'shot_missed',
                    shooter_id=bullet.shooter_id,
                    weapon_type=bullet.weapon_type,
                    bullet_id=bullet.id,
                    distance=bullet.distance_travelled,
                    reason='arena_boundary',
                )
                bullets_to_remove.append(bullet)
                continue
            
            # Check wall collisions
            if self._bullet_wall_collision(bullet):
                self.game_state.record_weapon_event(
                    'shot_missed',
                    shooter_id=bullet.shooter_id,
                    weapon_type=bullet.weapon_type,
                    bullet_id=bullet.id,
                    distance=bullet.distance_travelled,
                    reason='wall',
                )
                bullets_to_remove.append(bullet)
                continue
        
        # Remove bullets
        for bullet in bullets_to_remove:
            self.game_state.remove_bullet(bullet)

    def _expire_range_limited_bullets(self):
        for bullet in list(self.game_state.bullets):
            if not bullet.range_exhausted:
                continue
            self.game_state.record_weapon_event(
                'shot_missed', shooter_id=bullet.shooter_id,
                weapon_type=bullet.weapon_type, bullet_id=bullet.id,
                distance=bullet.distance_travelled, reason='max_range',
            )
            self.game_state.remove_bullet(bullet)
    
    def _bullet_wall_collision(self, bullet: Bullet) -> bool:
        """Check if bullet collides with walls"""
        for wall in self.game_state.walls:
            if self.game_state._circle_rect_collision(
                bullet.x, bullet.y, bullet.radius, wall
            ) or self.game_state._line_rect_intersection(
                bullet.previous_x, bullet.previous_y, bullet.x, bullet.y, wall
            ):
                return True
        return False

    @staticmethod
    def _segment_circle_hit_fraction(bullet: Bullet, bot: Bot):
        """Return first hit fraction on the last bullet segment, or None."""
        sx, sy = bullet.previous_x, bullet.previous_y
        dx, dy = bullet.x - sx, bullet.y - sy
        fx, fy = sx - bot.x, sy - bot.y
        radius = bullet.radius + bot.radius
        a = dx * dx + dy * dy
        if a <= 1e-12:
            return 0.0 if fx * fx + fy * fy <= radius * radius else None
        c = fx * fx + fy * fy - radius * radius
        if c <= 0.0:
            return 0.0
        b = 2.0 * (fx * dx + fy * dy)
        discriminant = b * b - 4.0 * a * c
        if discriminant < 0.0:
            return None
        root = math.sqrt(discriminant)
        hits = [t for t in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)) if 0.0 <= t <= 1.0]
        return min(hits) if hits else None
    
    def _check_bullet_collisions(self):
        """Check bullet-bot collisions"""
        bullets_to_remove = []
        
        for bullet in self.game_state.bullets:
            for bot in self.game_state.bots.values():
                # Skip shooter and non-alive bots
                if (bot.id == bullet.shooter_id or 
                    bot.state != BotState.ALIVE):
                    continue
                
                # Check collision
                hit_fraction = self._segment_circle_hit_fraction(bullet, bot)

                if hit_fraction is not None:
                    # Hit!
                    definition = self.game_state.weapon_config.get(bullet.weapon_type)
                    segment_length = math.hypot(
                        bullet.x - bullet.previous_x, bullet.y - bullet.previous_y
                    )
                    hit_distance = max(
                        0.0,
                        bullet.distance_travelled - segment_length + segment_length * hit_fraction,
                    )
                    damage = definition.damage_at_distance(hit_distance)
                    if damage > 0:
                        self._damage_bot(bot, damage, bullet.shooter_id)
                    self.game_state.record_weapon_event(
                        'hit_registered',
                        shooter_id=bullet.shooter_id,
                        victim_id=bot.id,
                        target_id=bot.id,
                        weapon_type=bullet.weapon_type,
                        source_weapon=bullet.weapon_type,
                        bullet_id=bullet.id,
                        distance=hit_distance,
                        damage=damage,
                        damage_amount=damage,
                        victim_hp=max(0.0, bot.hp),
                        validation_flags={
                            'server_collision': True,
                            'inside_weapon_range': hit_distance < definition.max_range,
                            'positive_damage': damage > 0.0,
                        },
                    )
                    bullets_to_remove.append(bullet)
                    break
        
        # Remove hit bullets
        for bullet in bullets_to_remove:
            self.game_state.remove_bullet(bullet)
    
    def _check_bot_collisions(self):
        """Check bot-bot collisions"""
        alive_bots = self.game_state.get_alive_bots()
        
        for i in range(len(alive_bots)):
            for j in range(i + 1, len(alive_bots)):
                bot1, bot2 = alive_bots[i], alive_bots[j]
                
                dx = bot2.x - bot1.x
                dy = bot2.y - bot1.y
                distance = math.sqrt(dx*dx + dy*dy)
                min_distance = bot1.radius + bot2.radius
                
                if distance < min_distance and distance > 0:
                    # Collision! Separate bots
                    overlap = min_distance - distance
                    separation = overlap / 2
                    
                    # Normalize direction
                    nx = dx / distance
                    ny = dy / distance
                    
                    # Separate
                    bot1.x -= nx * separation
                    bot1.y -= ny * separation
                    bot2.x += nx * separation
                    bot2.y += ny * separation
                    
                    # Bounce velocities
                    v1n = bot1.vel_x * nx + bot1.vel_y * ny
                    v2n = bot2.vel_x * nx + bot2.vel_y * ny
                    
                    # Simple elastic collision
                    bot1.vel_x += (v2n - v1n) * nx * 0.5
                    bot1.vel_y += (v2n - v1n) * ny * 0.5
                    bot2.vel_x += (v1n - v2n) * nx * 0.5
                    bot2.vel_y += (v1n - v2n) * ny * 0.5
    
    def _damage_bot(self, bot: Bot, damage: float, attacker_id: int):
        """Apply damage to bot"""
        bot.hp -= damage
        
        if bot.hp <= 0:
            self._kill_bot(bot, attacker_id)
    
    def _kill_bot(self, bot: Bot, killer_id: int):
        """Handle bot death"""
        bot.state = BotState.DEAD
        bot.death_time = time.time()
        bot.hp = 0
        bot.deaths += 1
        
        # Award kill
        if killer_id in self.game_state.bots:
            self.game_state.bots[killer_id].kills += 1
            self.game_state.total_kills += 1
        
        self.game_state.total_deaths += 1
        
        logger.info(f"💀 Bot {bot.name} killed by Bot {killer_id}")
    
    def _handle_respawns(self):
        """Handle bot respawning"""
        current_time = time.time()
        
        for bot in self.game_state.bots.values():
            if bot.state == BotState.DEAD:
                if current_time - bot.death_time >= self.respawn_delay:
                    # Respawn at random location instead of death location
                    bot.x, bot.y = self.game_state._find_spawn_position()
                    
                    bot.state = BotState.INVULNERABLE
                    bot.hp = bot.max_hp
                    bot.vel_x = 0
                    bot.vel_y = 0
                    bot.invulnerable_until = current_time + self.invulnerability_time
                    if bot.weapon_state is not None:
                        definition = self.game_state.weapon_config.get(bot.weapon_type)
                        bot.weapon_state.reset(definition)
                    
                    logger.info(f"♻️  Bot {bot.name} respawned")
            
            elif bot.state == BotState.INVULNERABLE:
                if current_time >= bot.invulnerable_until:
                    bot.state = BotState.ALIVE
    
    def apply_bot_action(self, bot_id: int, action: dict):
        """Apply action to bot"""
        bot = self.game_state.bots.get(bot_id)
        if not bot or bot.state not in [BotState.ALIVE, BotState.INVULNERABLE]:
            return
        
        # Apply thrust
        thrust = action.get('thrust', {'x': 0, 'y': 0})
        thrust_x = max(-1, min(1, thrust.get('x', 0)))
        thrust_y = max(-1, min(1, thrust.get('y', 0)))
        
        definition = self.game_state.weapon_config.get(bot.weapon_type)

        # Add weapon-adjusted acceleration
        bot.vel_x += thrust_x * definition.acceleration * (1/60)  # Assume 60fps
        bot.vel_y += thrust_y * definition.acceleration * (1/60)
        
        # Limit speed
        speed = math.sqrt(bot.vel_x**2 + bot.vel_y**2)
        if speed > definition.max_speed:
            factor = definition.max_speed / speed
            bot.vel_x *= factor
            bot.vel_y *= factor
        
        # Update aim
        bot.aim_angle = action.get('aim_angle', bot.aim_angle)
        
        # Handle shooting
        if action.get('fire', False) and bot.state == BotState.ALIVE:
            self._try_shoot(bot)
    
    def _try_shoot(self, bot: Bot):
        """Try to make bot shoot"""
        if bot.weapon_state is None:
            return

        definition = self.game_state.weapon_config.get(bot.weapon_type)
        weapon_state = bot.weapon_state
        if not weapon_state.can_fire():
            if weapon_state.is_reloading:
                reason = 'reloading'
            elif weapon_state.ammo <= 0:
                reason = 'empty_magazine'
            else:
                reason = 'cooldown'
            self.game_state.record_weapon_event(
                'shot_rejected', shooter_id=bot.id, weapon_type=definition.key,
                reason=reason, ammo_before=weapon_state.ammo,
                ammo_after=weapon_state.ammo,
                cooldown_remaining=weapon_state.cooldown_remaining,
                reload_time_remaining=weapon_state.reload_remaining,
            )
            return

        diagnostic = self.game_state.get_observation(bot.id)

        spread_degrees = weapon_state.current_bloom_degrees
        spread_radians = math.radians(self.rng.uniform(-spread_degrees, spread_degrees))
        projectile_angle = bot.aim_angle + spread_radians

        bullet_offset = 25
        bullet_x = bot.x + math.cos(projectile_angle) * bullet_offset
        bullet_y = bot.y + math.sin(projectile_angle) * bullet_offset
        vel_x = math.cos(projectile_angle) * self.bullet_speed
        vel_y = math.sin(projectile_angle) * self.bullet_speed

        ammo_before = weapon_state.ammo
        bullet_id = self.game_state.add_bullet(
            bot.id,
            bullet_x,
            bullet_y,
            vel_x,
            vel_y,
            damage=definition.base_damage,
            weapon_type=definition.key,
            max_range=definition.max_range,
        )
        weapon_state.consume_shot(definition)
        self.game_state.record_weapon_event(
            'shot_fired',
            shooter_id=bot.id,
            weapon_type=definition.key,
            bullet_id=bullet_id,
            ammo_before=ammo_before,
            ammo_after=weapon_state.ammo,
            aim_angle=bot.aim_angle,
            projectile_angle=projectile_angle,
            bloom_degrees=spread_degrees,
            max_range=definition.max_range,
            base_damage=definition.base_damage,
            has_los=diagnostic['has_line_of_sight'],
            target_distance=diagnostic['target_distance'],
            in_effective_range=diagnostic['in_effective_range'],
            validation_flags={
                'weapon_state_valid': True,
                'has_los': diagnostic['has_line_of_sight'],
                'in_effective_range': diagnostic['in_effective_range'],
            },
        )
        bot.last_shot_time = time.time()
