---
name: frcscout
description: Compatibility entrypoint for /frcscout replicate team competition or latest; routes to the installed FRCstack reconstruction workflow.
---

# FRCscout compatibility command

Locate the installed `frcstack` skill in the host's documented skill directory and read its SKILL.md. Forward `replicate <team> <competition|latest>` as FRCstack replication without recursively reinvoking this alias. If FRCstack is unavailable, explain the missing dependency and link https://github.com/AkarshSharma2012/FRCstack-skill for installation; do not invent an accessible CAD/vision tool.

Use the primary skill directly for all domain work. Keep its evidence, permissions, and uncertainty rules. Video cannot guarantee 100%-accurate hidden robot geometry. Native slash support is host-dependent; plain-language invocation is the fallback.
