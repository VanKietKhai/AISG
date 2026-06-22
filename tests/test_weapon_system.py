import math
import time
import unittest

from game_server.engine.game_state import BotState, GameState
from game_server.engine.physics import PhysicsEngine
from game_server.networking.room_manager import RoomManager
from game_server.networking.server import ArenaBattleServicer, BotConnection
from game_server.weapons import derive_match_seed, load_weapon_config
from proto import arena_pb2
from ai_bot.evaluation import summarize_entries
from ai_bot.client.bot_client import BotClient
from ai_bot.models.hmoe_model import HMoeModel


class WeaponConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_weapon_config()

    def test_required_weapon_baseline_and_version(self):
        self.assertEqual(self.config.version, "weapon-v3-three-role-teams")
        self.assertEqual(set(self.config.keys()), {"SNIPER", "AR", "SMG"})
        self.assertEqual(self.config.get("SNIPER").magazine, 5)
        self.assertEqual(self.config.get("AR").magazine, 30)
        self.assertEqual(self.config.get("SMG").magazine, 30)

    def test_runtime_conversion_matches_approved_draft(self):
        sniper = self.config.get("SNIPER")
        ar = self.config.get("AR")
        smg = self.config.get("SMG")

        self.assertEqual(sniper.base_damage, 50.0)
        self.assertEqual(ar.base_damage, 20.0)
        self.assertEqual(smg.base_damage, 15.0)
        self.assertEqual((sniper.max_range, ar.max_range, smg.max_range), (600.0, 420.0, 120.0))
        self.assertAlmostEqual(sniper.shot_cooldown, 0.8)
        self.assertAlmostEqual(ar.shot_cooldown, 1.0 / 5.75)
        self.assertAlmostEqual(smg.shot_cooldown, 0.125)
        self.assertAlmostEqual(smg.speed_multiplier, 1.24)

    def test_quadratic_damage_falloff(self):
        sniper = self.config.get("SNIPER")
        self.assertEqual(sniper.damage_at_distance(0), 50.0)
        self.assertAlmostEqual(sniper.damage_at_distance(300), 37.5)
        self.assertEqual(sniper.damage_at_distance(600), 0.0)
        self.assertEqual(sniper.damage_at_distance(601), 0.0)

    def test_config_snapshot_is_immutable(self):
        with self.assertRaises(TypeError):
            self.config.weapons["AR"] = self.config.get("SMG")

    def test_match_seed_is_stable_and_room_specific(self):
        first = derive_match_seed("room_001", self.config.version)
        self.assertEqual(first, derive_match_seed("room_001", self.config.version))
        self.assertNotEqual(first, derive_match_seed("room_002", self.config.version))


class RoomLoadoutTests(unittest.TestCase):
    def test_room_manager_loads_real_rooms_and_assigns_cycle(self):
        manager = RoomManager()
        self.assertIn("room_001", manager.rooms)

        first = manager.join_room("loadout-p1", "one", "room_001", "abc123")
        second = manager.join_room("loadout-p2", "two", "room_001", "abc123")
        third = manager.join_room("loadout-p3", "three", "room_001", "abc123")

        self.assertTrue(first["success"])
        self.assertEqual(first["weapon_type"], "AR")
        self.assertEqual(second["weapon_type"], "SNIPER")
        self.assertEqual(third["weapon_type"], "SMG")

    def test_team_room_waits_for_two_distinct_teams(self):
        manager = RoomManager()
        first = manager.join_room("team-a-1", "a1", "room_002", "abc456", team_id="team-a", requested_weapon_type="SMG")
        second = manager.join_room("team-a-2", "a2", "room_002", "abc456", team_id="team-a", requested_weapon_type="AR")
        room_info = manager.get_room_info("room_002")

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(first["team_id"], "team-a")
        self.assertEqual(second["weapon_type"], "AR")
        self.assertEqual(room_info["team_count"], 1)
        self.assertFalse(room_info["is_active"])

        third = manager.join_room("team-b-1", "b1", "room_002", "abc456", team_id="team-b", requested_weapon_type="AR")
        self.assertTrue(third["success"])
        self.assertTrue(manager.get_room_info("room_002")["is_active"])


class WeaponPhysicsTests(unittest.TestCase):
    def setUp(self):
        self.config = load_weapon_config()

    def make_state(self, seed=123, width=800, height=600):
        state = GameState(
            weapon_config=self.config,
            room_id="test-room",
            match_seed=seed,
        )
        state._create_arena_walls({"width": width, "height": height, "obstacles": []})
        return state

    def add_bot(self, state, weapon="AR", bot_id=1):
        state.add_bot("player", "bot", custom_bot_id=bot_id, weapon_type=weapon)
        bot = state.bots[bot_id]
        bot.x = 100.0
        bot.y = 100.0
        bot.aim_angle = 0.0
        return bot

    def test_arena_dimensions_are_applied(self):
        state = self.make_state(width=2000, height=1500)
        self.assertEqual((state.width, state.height), (2000, 1500))
        self.assertEqual(state.walls[1].y, 1480)

    def test_fire_consumes_ammo_and_enforces_cooldown(self):
        state = self.make_state()
        bot = self.add_bot(state, "SNIPER")
        physics = PhysicsEngine(state)

        physics.apply_bot_action(bot.id, {"aim_angle": 0.0, "fire": True})
        self.assertEqual(len(state.bullets), 1)
        self.assertEqual(bot.weapon_state.ammo, 4)
        self.assertGreater(bot.weapon_state.current_bloom_degrees, 0)

        physics.apply_bot_action(bot.id, {"aim_angle": 0.0, "fire": True})
        self.assertEqual(len(state.bullets), 1)
        self.assertEqual(bot.weapon_state.ammo, 4)

    def test_auto_reload_uses_simulation_time(self):
        state = self.make_state()
        bot = self.add_bot(state, "SNIPER")
        physics = PhysicsEngine(state)
        definition = self.config.get("SNIPER")
        bot.weapon_state.ammo = 1

        physics.apply_bot_action(bot.id, {"aim_angle": 0.0, "fire": True})
        physics.update(0.01)
        self.assertTrue(bot.weapon_state.is_reloading)
        self.assertEqual(bot.weapon_state.ammo, 0)

        for _ in range(math.ceil(definition.reload_seconds / 0.1) + 1):
            physics.update(0.1)
        self.assertFalse(bot.weapon_state.is_reloading)
        self.assertEqual(bot.weapon_state.ammo, definition.magazine)

    def test_bullet_is_removed_at_weapon_range(self):
        state = self.make_state()
        state.add_bullet(1, 100, 100, 400, 0, weapon_type="SMG", max_range=10)
        physics = PhysicsEngine(state)
        physics.update(0.1)
        self.assertEqual(state.bullets, [])
        self.assertEqual(state.weapon_events[-1]["event_type"], "shot_missed")
        self.assertEqual(state.weapon_events[-1]["reason"], "max_range")

    def test_projectile_applies_server_side_falloff_damage(self):
        state = self.make_state()
        shooter = self.add_bot(state, "AR", bot_id=1)
        state.add_bot("opponent", "target", custom_bot_id=2, weapon_type="SMG")
        target = state.bots[2]
        target.x = 180.0
        target.y = 100.0
        physics = PhysicsEngine(state)

        physics.apply_bot_action(shooter.id, {"aim_angle": 0.0, "fire": True})
        physics.update(0.15)

        expected_damage = self.config.get("AR").damage_at_distance(37.0)
        self.assertAlmostEqual(target.hp, 100.0 - expected_damage, places=5)
        self.assertEqual(state.bullets, [])
        event_types = [event["event_type"] for event in state.weapon_events]
        self.assertEqual(event_types, ["shot_fired", "hit_registered"])
        self.assertEqual(state.weapon_events[-1]["weapon_config_version"], "weapon-v3-three-role-teams")
        self.assertAlmostEqual(state.weapon_events[-1]["damage"], expected_damage)

    def test_same_team_bullets_do_not_damage_friendly_bots(self):
        state = self.make_state()
        state.add_bot("member-1", "ally-shooter", custom_bot_id=1, weapon_type="AR", team_id="team-a")
        state.add_bot("member-2", "ally-target", custom_bot_id=2, weapon_type="SMG", team_id="team-a")
        shooter = state.bots[1]
        target = state.bots[2]
        shooter.x, shooter.y, shooter.aim_angle = 100.0, 100.0, 0.0
        target.x, target.y = 180.0, 100.0

        physics = PhysicsEngine(state)
        physics.apply_bot_action(shooter.id, {"aim_angle": 0.0, "fire": True})
        physics.update(0.15)

        self.assertEqual(target.hp, 100.0)

    def test_mobility_changes_acceleration_and_speed_cap(self):
        sniper_state = self.make_state()
        sniper = self.add_bot(sniper_state, "SNIPER")
        smg_state = self.make_state()
        smg = self.add_bot(smg_state, "SMG")

        PhysicsEngine(sniper_state).apply_bot_action(sniper.id, {"thrust": {"x": 1, "y": 0}})
        PhysicsEngine(smg_state).apply_bot_action(smg.id, {"thrust": {"x": 1, "y": 0}})
        self.assertGreater(smg.vel_x, sniper.vel_x)
        self.assertEqual(self.config.get("SMG").max_speed, 320 * 1.24)

    def test_seeded_bloom_is_reproducible(self):
        velocity_sequences = []
        for _ in range(2):
            state = self.make_state(seed=999)
            bot = self.add_bot(state, "AR")
            physics = PhysicsEngine(state)
            definition = self.config.get("AR")

            physics.apply_bot_action(bot.id, {"aim_angle": 0.0, "fire": True})
            bot.weapon_state.cooldown_remaining = 0.0
            physics.apply_bot_action(bot.id, {"aim_angle": 0.0, "fire": True})
            velocity_sequences.append([(b.vel_x, b.vel_y) for b in state.bullets])

        self.assertEqual(velocity_sequences[0], velocity_sequences[1])
        self.assertEqual(velocity_sequences[0][0], (400.0, 0.0))
        self.assertNotEqual(velocity_sequences[0][1][1], 0.0)

    def test_respawn_resets_weapon_runtime(self):
        state = self.make_state()
        bot = self.add_bot(state, "AR")
        physics = PhysicsEngine(state)
        definition = self.config.get("AR")
        bot.weapon_state.ammo = 2
        bot.weapon_state.current_bloom_degrees = 4.0
        bot.weapon_state.reload_remaining = 1.0
        bot.state = BotState.DEAD
        bot.death_time = time.time() - physics.respawn_delay - 0.1

        physics._handle_respawns()
        self.assertEqual(bot.state, BotState.INVULNERABLE)
        self.assertEqual(bot.weapon_state.ammo, definition.magazine)
        self.assertEqual(bot.weapon_state.current_bloom_degrees, 0.0)
        self.assertFalse(bot.weapon_state.is_reloading)

    def test_observation_exposes_weapon_contract(self):
        state = self.make_state()
        bot = self.add_bot(state, "SMG")
        observation = state.get_observation(bot.id)

        self.assertEqual(observation["weapon_type"], "SMG")
        self.assertEqual(observation["ammo"], 30)
        self.assertEqual(observation["weapon_config_version"], "weapon-v3-three-role-teams")
        self.assertEqual(observation["weapon_max_range"], 120.0)

        proto = arena_pb2.Observation(
            weapon_type=observation["weapon_type"],
            ammo=observation["ammo"],
            weapon_config_version=observation["weapon_config_version"],
        )
        round_trip = arena_pb2.Observation.FromString(proto.SerializeToString())
        self.assertEqual(round_trip.weapon_type, "SMG")
        self.assertEqual(round_trip.ammo, 30)

        action = arena_pb2.Action(bot_id=bot.id, fire=True)
        action_round_trip = arena_pb2.Action.FromString(action.SerializeToString())
        self.assertEqual(action_round_trip.bot_id, bot.id)

    def test_reload_and_rejected_shot_emit_authoritative_events(self):
        state = self.make_state()
        bot = self.add_bot(state, "SNIPER")
        physics = PhysicsEngine(state)
        definition = self.config.get("SNIPER")
        bot.weapon_state.ammo = 1

        physics.apply_bot_action(bot.id, {"fire": True})
        physics.apply_bot_action(bot.id, {"fire": True})
        physics.update(0.01)
        for _ in range(math.ceil(definition.reload_seconds / 0.1) + 1):
            physics.update(0.1)

        events = state.weapon_events
        self.assertIn("shot_rejected", [e["event_type"] for e in events])
        self.assertEqual(
            [e["event_type"] for e in events if e["event_type"].startswith("reload_")],
            ["reload_started", "reload_finished"],
        )
        rejected = next(e for e in events if e["event_type"] == "shot_rejected")
        self.assertEqual(rejected["reason"], "empty_magazine")

    def test_swept_projectile_collision_prevents_tunnelling(self):
        state = self.make_state()
        self.add_bot(state, "AR", bot_id=1)
        state.add_bot("opponent", "target", custom_bot_id=2, weapon_type="SMG")
        target = state.bots[2]
        target.x, target.y = 135.0, 100.0
        state.add_bullet(1, 100.0, 100.0, 400.0, 0.0, weapon_type="AR", max_range=420.0)

        PhysicsEngine(state).update(0.1)

        self.assertLess(target.hp, 100.0)
        self.assertEqual(state.bullets, [])

    def test_final_range_segment_can_hit_before_expiring(self):
        state = self.make_state(width=1000)
        self.add_bot(state, "AR", bot_id=1)
        state.add_bot("opponent", "target", custom_bot_id=2, weapon_type="SMG")
        target = state.bots[2]
        target.x, target.y = 215.0, 100.0
        state.add_bullet(1, 100.0, 100.0, 400.0, 0.0, weapon_type="AR", max_range=100.0)

        physics = PhysicsEngine(state)
        for _ in range(3):
            physics.update(0.1)

        self.assertLess(target.hp, 100.0)
        self.assertEqual(state.weapon_events[-1]["event_type"], "hit_registered")

    def test_observation_exposes_g5_diagnostics(self):
        state = self.make_state()
        bot = self.add_bot(state, "AR", bot_id=1)
        state.add_bot("opponent", "target", custom_bot_id=2, weapon_type="SMG")
        state.bots[2].x, state.bots[2].y = 200.0, 100.0
        observation = state.get_observation(bot.id)

        self.assertEqual(observation["target_distance"], 100.0)
        self.assertTrue(observation["in_effective_range"])
        self.assertTrue(observation["can_shoot"])
        self.assertEqual(observation["run_mode"], "EVAL")


class GateG5AgentTests(unittest.TestCase):
    @staticmethod
    def observation(weapon, distance, **overrides):
        data = {
            "self_pos": {"x": 100.0, "y": 100.0},
            "self_hp": 100.0,
            "enemy_pos": {"x": 100.0 + distance, "y": 100.0},
            "enemy_hp": 100.0,
            "bullets": [],
            "weapon_type": weapon,
            "weapon_max_range": {"SNIPER": 600.0, "AR": 420.0, "SMG": 120.0}[weapon],
            "ammo": 10,
            "is_reloading": False,
            "shot_cooldown_remaining": 0.0,
            "current_bloom": 0.0,
            "has_line_of_sight": True,
            "in_effective_range": distance <= {"SNIPER": 600.0, "AR": 420.0, "SMG": 120.0}[weapon],
            "can_shoot": True,
        }
        data.update(overrides)
        return data

    def test_hmoe_routes_weapon_specific_spacing_and_fire_state(self):
        model = HMoeModel()
        sniper = model.act(self.observation("SNIPER", 200.0))
        smg = model.act(self.observation("SMG", 110.0))
        reloading = model.act(self.observation("AR", 200.0, is_reloading=True, can_shoot=False))

        self.assertLess(sniper["move_x"], 0.0)
        self.assertGreater(smg["move_x"], 0.0)
        self.assertEqual(sniper["weapon_tactic"], "SNIPER")
        self.assertFalse(reloading["fire"])
        self.assertEqual(model.run_mode, "EVAL")
        self.assertEqual(model.optimizer_step_count, 0)
        self.assertFalse(model.learn_from_experience({"event": "death"}))

    def test_eval_summary_uses_server_validated_events(self):
        entries = [
            {"type": "game_event", "event_type": "shot_fired", "data": {
                "tick": 1, "weapon_type": "AR", "target_distance": 200,
                "max_range": 420, "ammo_before": 30, "ammo_after": 29,
                "has_los": True, "in_effective_range": True,
            }},
            {"type": "game_event", "event_type": "hit_registered", "data": {
                "tick": 2, "weapon_type": "AR", "damage_amount": 18.0,
            }},
            {"type": "observation_sent", "data": {"self_kills": 1, "self_deaths": 1}},
        ]
        summary = summarize_entries(entries, expected_episodes=1)
        self.assertEqual(summary["run_mode"], "EVAL")
        self.assertEqual(summary["optimizer_step_count"], 0)
        self.assertEqual(summary["hit_rate"], 1.0)
        self.assertEqual(summary["damage_validated"], 18.0)
        self.assertEqual(summary["completion_rate"], 1.0)


