import os
import tempfile
import unittest
from pathlib import Path

from game import db
from game.engine import handle_player_text, start_or_get
from game.episode import load_episode


class ProjectIntegrityTests(unittest.TestCase):
    def test_episode_references_existing_locations_and_images(self) -> None:
        episode = load_episode()
        locations = episode["locations"]
        assets_dir = Path(__file__).resolve().parent.parent / "assets"

        self.assertIn(episode["hero_defaults"]["location"], locations)
        for key, location in locations.items():
            self.assertTrue((assets_dir / location["image"]).is_file(), key)
            for destination in location.get("directions", []):
                self.assertIn(destination, locations, f"{key} -> {destination}")


class EngineFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["GAME_DB_PATH"] = str(Path(self.temp_dir.name) / "test.sqlite3")
        os.environ["ENABLE_AI_SCENES"] = "false"
        db.init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_new_player_can_complete_setup_and_find_evidence(self) -> None:
        telegram_id = 1001
        initial = start_or_get(telegram_id)
        self.assertFalse(initial["hero"]["setup_complete"])

        await handle_player_text(telegram_id, "2")
        await handle_player_text(telegram_id, "1")
        answer, state, image = await handle_player_text(telegram_id, "Оглянь номер")

        self.assertTrue(state["hero"]["setup_complete"])
        self.assertEqual(state["hero"]["difficulty"], "normal")
        self.assertIn("Сірий пил біля ліжка", state["hero"]["evidence"])
        self.assertEqual(image, "hotel_room.png")
        self.assertIn("Нові докази", answer)

    async def test_player_can_move_only_to_open_direction(self) -> None:
        telegram_id = 1002
        await handle_player_text(telegram_id, "3")
        await handle_player_text(telegram_id, "2")
        _answer, state, image = await handle_player_text(
            telegram_id,
            "Йди до камери схову №46",
        )

        self.assertEqual(state["hero"]["location"], "station_locker")
        self.assertEqual(image, "station_locker.png")


if __name__ == "__main__":
    unittest.main()

