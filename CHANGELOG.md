# Changelog

## [3.0.5](https://github.com/anthony-spruyt/SunGather/compare/v3.0.4...v3.0.5) (2026-10-26)


### Bug Fixes

* **docker:** leave pip out of the runtime image ([#449](https://github.com/anthony-spruyt/SunGather/issues/449)) ([f62cb1e](https://github.com/anthony-spruyt/SunGather/commit/f62cb1e4c16f2ae22fdb4378f24a962fd3b9334c))

## [3.0.4](https://github.com/anthony-spruyt/SunGather/compare/v3.0.3...v3.0.4) (2026-10-24)


### Bug Fixes

* **deps:** replace container image ghcr.io/astral-sh/uv to 0.13.5 ([#442](https://github.com/anthony-spruyt/SunGather/issues/442)) ([429a3d8](https://github.com/anthony-spruyt/SunGather/commit/429a3d84db05ffe13491842bad72e911645ef6f9))
* **deps:** update certifi to 2026.10.23 ([#444](https://github.com/anthony-spruyt/SunGather/issues/444)) ([660e5f2](https://github.com/anthony-spruyt/SunGather/commit/660e5f231a94032c75740f99f675387acf952996))
* **deps:** update container image ghcr.io/astral-sh/uv to v0.13.5 ([#439](https://github.com/anthony-spruyt/SunGather/issues/439)) ([0d47ed6](https://github.com/anthony-spruyt/SunGather/commit/0d47ed6fbbad0244318207279068ba074ce85f57))
* **deps:** update container image python to v ([#434](https://github.com/anthony-spruyt/SunGather/issues/434)) ([a20c0e4](https://github.com/anthony-spruyt/SunGather/commit/a20c0e439437e98d1580b06789865eed703d8aa4))
* **deps:** update container image python to v ([#435](https://github.com/anthony-spruyt/SunGather/issues/435)) ([ae1ead0](https://github.com/anthony-spruyt/SunGather/commit/ae1ead0f8ca4dec976967de6c0e6c3fd72fa558b))

## [3.0.3](https://github.com/anthony-spruyt/SunGather/compare/v3.0.2...v3.0.3) (2026-10-21)


### Bug Fixes

* **deps:** lock file maintenance ([#426](https://github.com/anthony-spruyt/SunGather/issues/426)) ([a90b670](https://github.com/anthony-spruyt/SunGather/commit/a90b670c5dfcce24e7017dfe1a5352c5f2c2ac3f))
* **deps:** update container image python to v ([#429](https://github.com/anthony-spruyt/SunGather/issues/429)) ([563a269](https://github.com/anthony-spruyt/SunGather/commit/563a269c1c0de0c9de365757094ae68ee254d11f))
* **deps:** update container image python to v ([#430](https://github.com/anthony-spruyt/SunGather/issues/430)) ([24b1bd2](https://github.com/anthony-spruyt/SunGather/commit/24b1bd2f2a2974747540e2c0de9b829742021810))

## [3.0.2](https://github.com/anthony-spruyt/SunGather/compare/v3.0.1...v3.0.2) (2026-10-15)


### Bug Fixes

* **deps:** update container image ghcr.io/astral-sh/uv to v0.13.1 ([#419](https://github.com/anthony-spruyt/SunGather/issues/419)) ([7119088](https://github.com/anthony-spruyt/SunGather/commit/7119088ea61778019ed34618c5577689be316593))

## [3.0.1](https://github.com/anthony-spruyt/SunGather/compare/v3.0.0...v3.0.1) (2026-10-10)


### Bug Fixes

* **deps:** update container image python to 3.14 ([#409](https://github.com/anthony-spruyt/SunGather/issues/409)) ([b16d8f0](https://github.com/anthony-spruyt/SunGather/commit/b16d8f07ab19187ebd076fdf122f8d2627ea3f18))
* **deps:** update container image python to 3.14-slim ([#410](https://github.com/anthony-spruyt/SunGather/issues/410)) ([fbbcd9f](https://github.com/anthony-spruyt/SunGather/commit/fbbcd9fc48cbe001d31462dc12c1bf9c3069f918))


### Code Refactoring

* prepare for ruff PLR rules ([#406](https://github.com/anthony-spruyt/SunGather/issues/406)) ([e4038cb](https://github.com/anthony-spruyt/SunGather/commit/e4038cb5128719ccdcb05dbf623ac1f50f3cf6b1))

## [3.0.0](https://github.com/anthony-spruyt/SunGather/compare/v2.0.1...v3.0.0) (2026-10-06)


### ⚠ BREAKING CHANGES

* the code now lives in src/sungather and installs as the sungather package; run it with `uv run sungather` or the `sungather` console script instead of `python3 sungather.py`. SunGather/requirements.txt and setup.py are gone. Inside the image the app is no longer copied to /opt/sungather, so `-r` paths pointing there must change; the packaged registers file is the default.

### Features

* **devcontainer:** add claude state management script ([4ddfc28](https://github.com/anthony-spruyt/SunGather/commit/4ddfc2804c56363dd1a25d28e211e1f2b9b9f2a0))
* restructure as a uv package to join the python-image group ([#399](https://github.com/anthony-spruyt/SunGather/issues/399)) ([864696b](https://github.com/anthony-spruyt/SunGather/commit/864696ba9843f533630d5c124c191718de2eaec4))

## [2.0.1](https://github.com/anthony-spruyt/SunGather/compare/2.0.0...v2.0.1) (2026-09-19)


### Continuous Integration

* migrate releases to release-please ([#377](https://github.com/anthony-spruyt/SunGather/issues/377)) ([ea6731e](https://github.com/anthony-spruyt/SunGather/commit/ea6731e2a4c1983816e43a515f403d20648ec789))
