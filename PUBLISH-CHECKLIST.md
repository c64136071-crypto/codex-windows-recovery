# Publish checklist

- [ ] Decide on project name, GitHub account, and repository visibility.
- [ ] Review every tracked file with `git status` and `git diff --cached`.
- [ ] Scan for usernames, email addresses, tokens, proxy addresses, logs, and
      absolute Windows paths before the first push.
- [ ] Confirm no OpenAI binaries, plugin files, runtime caches, or app assets
      are tracked. The tool must download nothing and redistribute nothing.
- [ ] Run unit tests and `Doctor` on the target Windows version.
- [ ] Test a closed-app start after an update; current live session was not
      terminated for this check.
- [ ] Confirm the README's tested version and known limitations remain accurate.
- [ ] Obtain explicit approval before creating or pushing a public repository.
