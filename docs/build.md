# Building and signing

Requirements: Python 3.10+, git and the HarmonyOS command-line tools (SDK 5.1.0 was used).

```bash
python3 tools/prepare_sources.py
mkdir -p toolchain && ln -s /path/to/command-line-tools toolchain/command-line-tools   # or pass --toolchain
python3 tools/build_clean_cases.py [case-id ...]
```

This writes `artifacts/clean/<id>/<variant>/app-unsigned.hap` for both variants and audits the
disassembled bytecode for injected benchmark code. Builds are not byte-reproducible across
machines; the source tree is the stable identity (`case.json#source.<variant>.tree`;
`reference_unsigned_hap_sha256` is the hash of the reference build).

**Signing is up to the user**: sign both HAPs with your own certificate, profile and keystore
(e.g. `hap-sign-tool` from the SDK toolchain) for your device. Do not change bundle names.
