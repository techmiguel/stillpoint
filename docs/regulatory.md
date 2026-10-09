# 60 GHz emission (Europe)

v1 does not go through certification, but **its emission parameters must stay inside
what is allowed**. This table is the design reference; before any sale it is checked
against the current versions of the documents cited.

| Reference | What it sets (summary) |
|---|---|
| Decision 2006/771/EC and amendments (SRD), ERC/REC 70-03 | non-specific short-range devices in 57–64 GHz: 100 mW (20 dBm) EIRP, with extra limits on output power and density |
| ETSI EN 305 550 | harmonised standard for SRDs in 40–246 GHz (measurement methods) |
| Directive 2014/53/EU (RED) | market access framework |

## How the design applies it

| Parameter | Design limit | v1 value | Enforced in |
|---|---|---|---|
| Occupied band | inside 57.0–64.0 GHz | 60.0–61.25 GHz | `RadarConfig.check_eu`, `rf_radar_check_eu` |
| EIRP | ≤ 20 dBm | target 10 dBm (≥ 10 dB margin) | same; the BGT60 TX power is set to the lowest level that meets P1 |
| Duty cycle | < 100 % | 11 % | same |

- The radar configuration lives in firmware and cannot be changed over Matter; any
  configuration that fails the check is rejected and the radar is not started (fail safe).
- The BGT60TR13C is sold for this band. Its datasheet gives a maximum TX power of
  +5 dBm and an antenna gain of 3.5 dBi typical (5 dBi max): **≈ 10 dBm EIRP at most**.
  The estimate and a rough measurement (power meter or analyser with a 60 GHz horn, if
  available) are documented in F4 (criterion S4).
- The radome must not focus the beam: a flat λ/2 slab, no lenses.
