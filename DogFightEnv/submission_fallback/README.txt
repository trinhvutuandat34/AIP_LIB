FALLBACK ARTIFACT -- c0aa0ff (pre-spiral tree)          built 2026-09-10

WHAT IS HERE
  JinjjaBoramae.exe         crc32 998340525   Model 1, built from the c0aa0ff DLL + Rule XML
  JinjjaBoramae_headon.exe  crc32 3365396317  Model 2
  config.json                                 127.0.0.1:9999, identical to the main artifact

WHAT IS NOT HERE, AND WHY
  The submission ZIPs. The first build of this directory produced ZIPs that were byte-identical
  to the CURRENT-tree ZIPs (crc32 2887260649 / 626276273) because the build script ran
  build_exe.py but never package_release.py, so the copy step picked up the existing ZIPs and
  filed them under "fallback". They were deleted: a mislabelled fallback is worse than none,
  because anyone grabbing it on match day would ship the current tree believing it was the
  rollback.

  To produce real ZIPs, re-stage c0aa0ff and run package_release.py -- NOT build_exe.py alone:
      git checkout c0aa0ff -- DogFightEnv/Release/AIP_BASE.dll \
          DogFightEnv/Release/AIP_BASE_target.dll \
          DogFightEnv/Release/Rule_forTraining.xml DogFightEnv/Release/Rule_real_eagle.xml
      python scripts/assert_baseline.py --expect fallback     # MUST pass first
      python scripts/build_exe.py && python scripts/package_release.py
      git checkout HEAD -- <the same four files>
      python scripts/assert_baseline.py                        # MUST pass after
  Do this only when no eval is running: it swaps the DLL under anything in flight.

VERIFY BEFORE TRUSTING
  The two exes above MUST differ from DogFightEnv/submission_exe/. If any crc32 matches the
  current artifact, this directory is stale and must be rebuilt.

WHAT THIS FALLBACK IS FOR
  c0aa0ff is the pre-spiral baseline: 60 named nodes, DLL crc32 4026508473. The 2026-09-06 tree
  change that replaced it has NEVER been shown to beat it -- ab_head_0908 stalled at 17 of 100
  episodes per cell. Until that is settled this is the known-quantity option, not a known-better
  or known-worse one.
