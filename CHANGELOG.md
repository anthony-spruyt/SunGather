# Changelog

## [3.0.0](https://github.com/anthony-spruyt/SunGather/compare/v2.0.1...v3.0.0) (2026-10-06)


### ⚠ BREAKING CHANGES

* the code now lives in src/sungather and installs as the sungather package; run it with `uv run sungather` or the `sungather` console script instead of `python3 sungather.py`. SunGather/requirements.txt and setup.py are gone. Inside the image the app is no longer copied to /opt/sungather, so `-r` paths pointing there must change; the packaged registers file is the default.

### Features

* **devcontainer:** add claude state management script ([4ddfc28](https://github.com/anthony-spruyt/SunGather/commit/4ddfc2804c56363dd1a25d28e211e1f2b9b9f2a0))
* restructure as a uv package to join the python-image group ([#399](https://github.com/anthony-spruyt/SunGather/issues/399)) ([864696b](https://github.com/anthony-spruyt/SunGather/commit/864696ba9843f533630d5c124c191718de2eaec4))

## [2.0.1](https://github.com/anthony-spruyt/SunGather/compare/2.0.0...v2.0.1) (2026-09-19)


### Continuous Integration

* migrate releases to release-please ([#377](https://github.com/anthony-spruyt/SunGather/issues/377)) ([ea6731e](https://github.com/anthony-spruyt/SunGather/commit/ea6731e2a4c1983816e43a515f403d20648ec789))
