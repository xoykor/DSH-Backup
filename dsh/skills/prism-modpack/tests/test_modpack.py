import json
from pathlib import Path
import sys
import subprocess
import time
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from modpack import Workbench, digest, initialize, read, write


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.instance = self.base / "prism" / "instances" / "Pack com espaços"
        self.game = self.instance / ".minecraft"
        self.game.mkdir(parents=True)
        (self.instance / "instance.cfg").write_text("[General]\n")
        self.root = self.base / "work"
        initialize(self.root, self.instance, [sys.executable])
        self.work = Workbench(self.root)

    def jar(self, path, payload="test"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("fabric.mod.json", json.dumps({"id": payload}))
        return path

    def test_build_complete_pack_and_rollback_preserves_worlds(self):
        self.jar(self.game / "mods" / "old.jar")
        world = self.game / "saves" / "world" / "level.dat"
        world.parent.mkdir(parents=True)
        world.write_bytes(b"world-data")
        source = self.jar(self.base / "downloads" / "new.jar")
        plan = self.base / "plan.json"
        write(plan, {"mods": [{"file": str(source), "sha256": digest(source)}]})
        result = self.work.build(plan)
        self.assertFalse((self.game / "mods" / "old.jar").exists())
        self.assertTrue((self.game / "mods" / "new.jar").exists())
        self.work.rollback(result["snapshot"])
        self.assertTrue((self.game / "mods" / "old.jar").exists())
        self.assertFalse((self.game / "mods" / "new.jar").exists())
        self.assertEqual(world.read_bytes(), b"world-data")
        self.assertFalse((self.root / "modpack.lock.json").exists())

    def test_invalid_checksum_does_not_change_pack(self):
        self.jar(self.game / "mods" / "old.jar")
        before = self.work.inventory()
        source = self.jar(self.base / "new.jar")
        write(self.base / "plan.json", {"mods": [{"file": str(source), "sha256": "wrong"}]})
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.work.build(self.base / "plan.json")
        self.assertEqual(self.work.inventory(), before)

    def test_corrupted_snapshot_never_deletes_live_pack(self):
        self.jar(self.game / "mods" / "old.jar")
        sid = self.work.snapshot("baseline")
        (self.root / "snapshots" / sid / "mods" / "old.jar").write_bytes(b"bad")
        before = self.work.inventory()
        with self.assertRaisesRegex(ValueError, "corrompido"):
            self.work.rollback(sid)
        self.assertEqual(self.work.inventory(), before)

    def test_symlink_outside_instance_is_rejected(self):
        external = self.base / "external"
        external.mkdir()
        (self.game / "mods").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "link simbólico"):
            self.work.snapshot("unsafe")

    def test_only_changed_logs_are_collected(self):
        crash = self.game / "crash-reports" / "old.txt"
        crash.parent.mkdir()
        crash.write_text("Old OutOfMemoryError")
        latest = self.game / "logs" / "latest.log"
        latest.parent.mkdir()
        latest.write_text("previous boot")
        write(self.root / "runs" / "run1" / "run.json",
              {"baseline": self.work.baseline(), "status": "observing"})
        latest.write_text("New boot\nCaused by: java.lang.NoSuchMethodError: test\ncontext\n")
        self.work.collect("run1")
        report = self.work.diagnose("run1")
        self.assertEqual(report["findings"][0]["category"], "linkage")
        self.assertFalse((self.root / "runs/run1/logs/crash-reports/old.txt").exists())

    def test_clean_logs_are_inconclusive(self):
        write(self.root / "runs" / "run1" / "run.json", {"baseline": {}, "status": "observing"})
        self.assertEqual(self.work.diagnose("run1")["result"], "inconclusive")

    def test_launcher_exit_does_not_unlock_instance(self):
        # A fake launcher exits immediately, simulating forwarding to existing Prism.
        fake = self.base / "fake.py"
        fake.write_text("print('request forwarded')\n")
        self.work.settings["launcher"] = [sys.executable, str(fake)]
        result = self.work.launch(0.1)
        self.assertEqual(result["status"], "awaiting_game_stop")
        with self.assertRaisesRegex(ValueError, "pendente"):
            self.work.snapshot("must fail")
        self.work.finish()
        self.work.snapshot("now allowed")

    def test_repeated_fix_is_rejected(self):
        write(self.root / "state.json", {"latest": "run1"})
        self.work.record("dependency mismatch", "replace A with B")
        with self.assertRaisesRegex(ValueError, "já foi proposta"):
            self.work.record("another description", "replace A with B")

    def test_nested_workspace_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "separados"):
            initialize(self.instance / "state", self.instance, ["prismlauncher"])

    def test_missing_launcher_does_not_mark_active(self):
        self.work.settings["launcher"] = [str(self.base / "missing-executable")]
        with self.assertRaises(FileNotFoundError):
            self.work.launch(0.1)
        self.assertFalse(self.work.state().get("active"))

    def test_configure_wrapper_is_idempotent_and_preserves_other_sections(self):
        config = self.instance / "instance.cfg"
        config.write_text("[General]\nOverrideCommands=false\nWrapperCommand=old\n\n[UI]\nname=keep\n")
        first = self.work.configure_wrapper()
        self.assertTrue(first["changed"])
        self.assertTrue(Path(first["backup"]).is_file())
        value = config.read_text()
        self.assertIn("OverrideCommands=true", value)
        self.assertIn(str(ROOT / "scripts" / "game_wrapper.py"), value)
        self.assertIn("[UI]\nname=keep", value)
        second = self.work.configure_wrapper()
        self.assertFalse(second["changed"])
        self.assertIsNone(second["backup"])

    def test_configure_wrapper_rejects_missing_general_section(self):
        config = self.instance / "instance.cfg"
        config.write_text("[UI]\nname=keep\n")
        with self.assertRaisesRegex(ValueError, "Seção"):
            self.work.configure_wrapper()
        self.assertEqual(config.read_text(), "[UI]\nname=keep\n")

    def start_wrapper(self, script):
        write(self.root / 'runs' / 'wrapped' / 'run.json',
              {'baseline': self.work.baseline(), 'status': 'observing'})
        write(self.root / 'state.json', {'active': 'wrapped', 'latest': 'wrapped'})
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts' / 'game_wrapper.py'),
                                    '--workspace', str(self.root), '--', sys.executable, '-c', script], cwd=self.game)
        self.addCleanup(lambda: process.poll() is None and process.terminate())
        for _ in range(100):
            if (self.root / 'runs/wrapped/lifecycle.json').exists():
                if read(self.root / 'runs/wrapped/lifecycle.json')['status'] != 'starting':
                    break
            time.sleep(0.02)
        return process

    def test_wrapper_exit_auto_releases_state_and_records_exit_code(self):
        process = self.start_wrapper('raise SystemExit(7)')
        process.wait(timeout=5)
        status = self.work.refresh()
        self.assertEqual(status['returncode'], 7)
        self.assertFalse(status['alive'])
        self.assertNotIn('active', self.work.state())
        self.assertEqual(read(self.root / 'runs/wrapped/run.json')['game_returncode'], 7)

    def test_wrapper_blocks_finish_and_stop_targets_owned_process(self):
        process = self.start_wrapper('import time; time.sleep(120)')
        with self.assertRaisesRegex(ValueError, 'rodando'):
            self.work.finish()
        result = self.work.stop()
        process.wait(timeout=5)
        self.assertFalse(result['alive'])
        self.assertNotIn('active', self.work.state())
        self.assertIn('stop_requested_at', read(self.root / 'runs/wrapped/run.json'))

    def test_dead_pid_without_starttime_is_not_alive(self):
        write(self.root / 'runs/wrapped/run.json', {'baseline': {}, 'status': 'observing'})
        write(self.root / 'state.json', {'active': 'wrapped', 'latest': 'wrapped'})
        write(self.root / 'runs/wrapped/lifecycle.json',
              {'status': 'exited', 'pid': 99999999, 'starttime': None, 'returncode': 0, 'finished': time.time()})
        self.assertFalse(self.work.refresh()['alive'])


if __name__ == "__main__":
    unittest.main()
