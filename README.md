# Codex Windows Recovery

A local, opt-in diagnostic and recovery tool for the Windows Codex desktop app.
It checks the current MSIX package's bundled plugin resources, repairs a damaged
user-owned mirror when needed, and launches Codex through Windows app activation.
It does not redistribute Codex, bundled plugins, or OpenAI runtimes.

This is an independent community project, not an official OpenAI product.

## What it addresses

- An app update changes packaged plugin resources while an old local mirror remains.
- A missing or damaged mirrored plugin file makes an installed plugin unavailable.
- Directly starting `app/ChatGPT.exe` fails with a Windows package-identity error.
- Packaged native runtimes need verified copies and a junction on some installations.

File integrity alone **does not** prove that every plugin is enabled, authorized,
or functional. Browser and Computer Use require separate end-to-end checks.
Slow first launch and off-screen windows also have several possible causes; this
project reports launch visibility but does not claim a universal window fix.

## Requirements

- Windows 11 with the `OpenAI.Codex` MSIX app registered for the current user.
- PowerShell 5.1 or newer and Python 3.12 or newer. The launch script can use
  Codex's cached Python runtime, or accept `-Python` explicitly.
- Enough free disk space for the mirrored plugin files and cached runtimes.
- A normal user session. Administrator elevation is not required.

Tested locally against Codex `26.924.2738.0` on 2026-09-29. Later package
layouts may differ. The tool stops with an error when required resources are
missing; do not force it through an incompatible update.

## Use

Run from this directory in PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-Codex.ps1 -Mode Doctor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-Codex.ps1 -Mode Start
```

`Start` launches the original Windows Codex app entry and does not run Python,
repair resources, set an environment override, or wait for a window. This is
the recommended daily path. `Doctor` is read-only and performs a full file-hash
check. `Repair` forces a verified repair when Codex is closed. Add
`-UseRecoveryResources` only when you intentionally want the legacy mirrored
resource flow. `-NoActivate` prepares resources without starting the app, and
`-Json` provides a machine-readable `Doctor` report.

The normal `Start` path does not set a user-level environment variable. The
legacy mirrored resource flow may configure
`CODEX_ELECTRON_BUNDLED_PLUGINS_RESOURCES_PATH`; remove that override only when
its value points to this tool's mirror. The script never kills Codex, resets
app data, changes `config.toml`, or edits model-provider settings.

## Update behavior

The package full name is recorded in `.codex/windows-recovery/state.json` after
successful verification. A new package version triggers a full hash check.
Missing files, size changes, and marketplace changes are checked on ordinary
launches. Same-size corruption outside the marketplace can escape a quick
check; run `Doctor` for a full audit. Repair uses verified stream copies,
reuses matching cached runtimes, and replaces only files in its dedicated
mirror. It does not keep a background process running.

If an update changes the package layout, stop and inspect the error. Do not
delete your Codex data or reinstall merely because this tool failed.

## Troubleshooting and rollback

1. Run `-Mode Doctor -Json` and keep the package version and status. Do not
   publish the report alongside account details or logs.
2. For plugin issues, confirm both the plugin's setting and its actual action
   in a fresh Codex chat. A file check cannot test permissions or account flags.
3. For slow launch, compare the time before app activation with the time until
   a visible window. First launch after update may populate runtime caches.
4. For a package-identity error, use the Windows app entry. Never start the
   executable inside `WindowsApps` directly.
5. For an off-screen window, try Windows window-management shortcuts or display
   settings first. This project does not modify registry window coordinates.

To stop using this project, launch Codex from its original Windows shortcut.
Then remove the user-level resource override only if its value points to this
tool's mirror; sign out and back in afterward. The mirror can be removed later
after verifying Codex works without it. Do not delete `.codex/config.toml`,
runtime caches, or package data as part of rollback. The override may have
existed before this tool was installed, so inspect it before changing it.

## Development

```powershell
python -B -m unittest discover -s tests -v
```

The tests use temporary fake package trees. They never copy or publish real
Codex resources. Contributions should include a failing regression test and
avoid adding personal paths, logs, config snapshots, or packaged binaries.

## Resume description

Built a Windows Codex diagnostic and recovery tool that detects MSIX updates,
verifies bundled plugin resources, incrementally repairs damaged local mirrors,
and activates the app with package identity. Added idempotence and corruption
tests, rollback instructions, and privacy-focused documentation. Validated on one Windows
installation; broader compatibility remains unverified.

## Disclaimer

Unofficial tool. No warranty. See [LICENSE](LICENSE). For official app guidance,
see [OpenAI's Codex app troubleshooting](https://developers.openai.com/codex/app/troubleshooting/).
