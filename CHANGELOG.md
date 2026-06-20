# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-05-30

### Changed
- homogenized language on no vs block

### Added
- Pickle block

### Fixed

- Forwarded `sealed` into bootstrap-mode flag serialization so foreign interpreter launches no longer silently drop sealed mode.
- Restored bootstrap guard parity for the hardened network, subprocess, and filesystem surfaces, including the missing socket, process-spawn, `io.open`, and `shutil` protections.
- Sent in-process trace output to stderr so traced guard failures no longer pollute wrapped command stdout and now match bootstrap mode.
- Removed dead `_REFCOUNT` bookkeeping from `hermetic.blocker` and updated the related tests to rely on active policy state instead.

## [0.2.0] - 2026-04-29

### Added

- Environment guard via --no-environment / --no-env and block_environment=True to block environment reads and mutations.
- Dynamic code execution guard via --no-code-exec and block_code_exec=True to block eval, exec, compile() calls, and runpy execution helpers while still allowing normal imports.
- Generic import policy guard via repeated --deny-import and deny_imports=[...] to block selected modules and package prefixes.
- Interpreter mutation guard via --no-interpreter-mutation and block_interpreter_mutation=True to block os.chdir, site.addsitedir, and mutation of import-resolution state such as sys.path.
- Documentation and tests for the new guard surfaces, and updated bootstrap generation so the new guards are available in bootstrap mode too.

## [0.1.0] - 2025-10-21

### Added

- Initial set of guards for subprocess, native code, filesystem, and network.
- Envelope for running commands without network access.

[0.1.0]: https://github.com/matthewdeanmartin/hermetic/releases/tag/v0.1.0
[0.2.0]: https://github.com/matthewdeanmartin/hermetic/compare/v0.1.0...v0.2.0
[1.0.0]: https://github.com/matthewdeanmartin/hermetic/compare/v0.2.0...v1.0.0
[unreleased]: https://github.com/matthewdeanmartin/hermetic/compare/v1.0.0...HEAD
