# Release 1.0.42 — publication and backend installation

PR115 head `986b4b2df9b7eec74ef7e5b8a8749dce95f74ec9` passed both Python versions, UI/assets, image build and universal Mac DMG. It was merged as `302e91d5fdb5be7a570936ae241132c2d5eddc5f`. Release workflow `41536681376` completed all five jobs successfully, including the public release and download manifest.

The existing Mac installation was upgraded from 1.0.41 through the unchanged native updater from the reviewed PR115 snapshot. It retained the ordinary backup, capacity check, official manifest/image selection, health/version verification and rollback machine. No native bundle/signing identity was replaced during this backend update; the wrapper remains 1.0.38.

Readback:

- Authenticated backend version: **1.0.42**; the ordinary version-check action refreshed its previously cached 1.0.39 manifest to 1.0.42.
- Six database `quick_check` results are `ok`; all **3,451** original sources have the same combined immutable-field digest before and after installation.
- The two configured mail accounts and local `kingfisher-qwen3.5:9b-8k` remain. The global background/import pause is still enabled and automatic cloud classification remains disabled.
- Mistral's new allowance, spent amount and held amount are all zero; it is not ready for paid work. No Mistral inference was made.
- Data-volume free space after the update: **814,960,640 bytes**. No backup/volume/cache pruning was performed.

Protected local receipts are in `/private/tmp/kf-release42-20261102/`; they contain checksums/status rather than private source bodies. The actual native window remains a separate acceptance task pending Mac availability. Installation and automated checks do not establish the mixed real-mail quality gate or the user's everyday-use week. The bulk import is not released.
