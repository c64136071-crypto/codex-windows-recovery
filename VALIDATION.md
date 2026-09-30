# Validation record

Date: 2026-09-29. Platform: one Windows desktop installation.
Codex package: `OpenAI.Codex`, version `26.924.2738.0`.

## Verified

- Eight project tests pass: mirror integrity, incremental copy, obsolete-file
  pruning, invalid manifest safety, source/mirror separation, read-only launcher
  diagnostics, child-process exit codes, and missing-package handling.
- Eleven existing private repair tests pass. These cover preference preservation,
  provider non-overwrite, plugin disable non-overwrite, backup rotation, stream
  copying, runtime linking, and plugin integrity. Private config snapshots and
  the private preference implementation are not included in this repository.
- Real `Doctor -Json` reports `resourceIntegrity=verified`, package status `Ok`,
  matching user resource override, and one visible Codex window.
- `Start -NoActivate` succeeds and records the verified package version without
  starting or stopping the app. The following doctor reports no version change.
- The user's config and existing preference snapshots retain their original
  hashes throughout the read-only validation.
- Source files contain no personal absolute paths, provider URLs, config
  snapshots, account credentials, or packaged application resources.

## Timing observations

The private quick inventory check took about 2.3 seconds. Full plugin and native
runtime marker hashing took about 20 seconds; the public doctor with the CUA tree
audit took about 16 seconds on later warm-cache runs. These are measurements on
one machine, not benchmarks or a claim of reduced app startup time.

## Not yet verified

- Closed-app startup through this release, after a real future app update.
- First-time installation without a pre-existing resource override.
- Cross-machine compatibility, redirected WindowsApps directories, and multi-drive
  junction/cache behavior.
- GitHub Actions execution. The workflow exists but no remote repository was
  created or pushed during this session.
- Every plugin's end-to-end operation. Computer Use initialization and window
  inspection were tested in the current conversation, not all plugins.
- Universal fixes for slow rendering or off-screen windows. These are diagnostic
  topics, not implemented recovery guarantees.

The launcher must never describe a visible window or a healthy file mirror as
proof that all plugin actions work.
