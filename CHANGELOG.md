# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- Added for new features.
- Changed for changes in existing functionality.
- Deprecated for soon-to-be removed features.
- Removed for now removed features.
- Fixed for any bug fixes.
- Security in case of vulnerabilities.

## [0.2.0] - 2026-04-28

### Added

- Added an environment guard via `--no-environment` / `--no-env` and
  `block_environment=True` to block environment reads and mutations.
- Added a dynamic code execution guard via `--no-code-exec` and
  `block_code_exec=True` to block `eval`, `exec`, direct `compile(...)`
  calls, and `runpy` execution helpers while still allowing normal
  imports.
- Added a generic import policy guard via repeated `--deny-import` and
  `deny_imports=[...]` to block selected modules and package prefixes.
- Added an interpreter mutation guard via
  `--no-interpreter-mutation` and
  `block_interpreter_mutation=True` to block `os.chdir`,
  `site.addsitedir`, and mutation of import-resolution state such as
  `sys.path`.
- Added documentation and tests for the new guard surfaces, and updated
  bootstrap generation so the new guards are available in bootstrap
  mode too.

## [0.1.0] - 2025-10-01

### Added

- Initial set of guards for subprocess, native code, filesystem, network.