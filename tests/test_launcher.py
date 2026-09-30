import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows PowerShell required')
class LauncherTests(unittest.TestCase):
    def run_doctor(self, tool_exit=0, registered=True):
        with tempfile.TemporaryDirectory(prefix='codex-launch-test-') as directory:
            home = Path(directory)
            harness = home / 'harness.ps1'
            launcher = str(ROOT / 'Start-Codex.ps1').replace("'", "''")
            python = str(ROOT / 'tests/fixtures/fake-python.cmd').replace("'", "''")
            package = ("[pscustomobject]@{PackageFamilyName='OpenAI.Codex_test';"
                       "PackageFullName='OpenAI.Codex_1.0_test';Version='1.0';"
                       "InstallLocation=$env:TEMP;Status='Ok'}") if registered else '$null'
            harness.write_text(
                f"function Get-AppxPackage {{ {package} }}\n"
                "function Get-StartApps { [pscustomobject]@{AppID='OpenAI.Codex_test!App'} }\n"
                "function Get-Process { $null }\n"
                "function Start-Process { throw 'Doctor must never activate the app' }\n"
                f"& '{launcher}' -Mode Doctor -Json -CodexHome '{str(home).replace(chr(39), chr(39)*2)}' -Python '{python}'\n"
                "exit $LASTEXITCODE\n",
                encoding='utf-8',
            )
            environment = dict(os.environ, RECOVERY_TEST_EXIT=str(tool_exit))
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness)],
                capture_output=True, text=True, env=environment, timeout=30,
            )
            self.assertFalse((home / 'windows-recovery').exists(), 'Doctor must be read-only')
            return result

    def test_start_skips_recovery_resources_by_default(self):
        with tempfile.TemporaryDirectory(prefix='codex-start-test-') as directory:
            home = Path(directory)
            harness = home / 'harness.ps1'
            launcher = str(ROOT / 'Start-Codex.ps1').replace("'", "''")
            package = ("[pscustomobject]@{PackageFamilyName='OpenAI.Codex_test';"
                       "PackageFullName='OpenAI.Codex_1.0_test';Version='1.0';"
                       "InstallLocation=$env:TEMP;Status='Ok'}")
            harness.write_text(
                f"function Get-AppxPackage {{ {package} }}\n"
                "function Get-StartApps { [pscustomobject]@{AppID='OpenAI.Codex_test!App'} }\n"
                "function Start-Process { throw 'Start -NoActivate must not activate the app' }\n"
                f"& '{launcher}' -Mode Start -NoActivate -CodexHome '{str(home).replace(chr(39), chr(39)*2)}'\n"
                "exit $LASTEXITCODE\n",
                encoding='utf-8',
            )
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Recovery checks were skipped', result.stdout)
            self.assertFalse((home / 'windows-recovery').exists())

    def test_healthy_exit_and_pure_json(self):
        result = self.run_doctor()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['resourceIntegrity'], 'verified')
        self.assertTrue(report['versionChanged'])
        self.assertEqual(report['visibleWindows'], 0)

    def test_failed_integrity_is_not_false_success(self):
        result = self.run_doctor(tool_exit=1)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['resourceIntegrity'], 'repair_required')

    def test_tool_error_stops_with_error_exit(self):
        result = self.run_doctor(tool_exit=2)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Resource tool failed', result.stderr)

    def test_unregistered_package_stops(self):
        result = self.run_doctor(registered=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('notregistered', ''.join(result.stderr.split()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
