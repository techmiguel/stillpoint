# Matter data model

Goal: Home Assistant (and any Matter controller) sees the essentials **through standard
clusters**, with no custom integration. What Matter does not standardize goes into a
manufacturer cluster that the user may ignore.

## Transport

- Thread, FTD device able to act as a router (mains powered: it strengthens the mesh).
- Commissioning over BLE with the QR / manual code printed on the enclosure.
- No account, no cloud. In v1 the room configuration (zones, doors, height) is set over
  UART/USB with `tools/room_cfg.py` (JSON → v1 block validated with a CRC, stored in
  NVM3); configuration through the manufacturer cluster is planned for v2.

## Endpoints

| EP | Device type | Cluster | Attribute / event | Meaning |
|---|---|---|---|---|
| 0 | Root Node | Basic Information, OTA Requestor, … | — | standard |
| 1 | Occupancy Sensor | Occupancy Sensing (0x0406) | `Occupancy` | someone in the room (including still people) |
| 2–4 | Occupancy Sensor | Occupancy Sensing | `Occupancy` | occupancy per configured zone (e.g. bed, sofa, bathroom) |
| 5 | Contact Sensor | Boolean State (0x0045) | `StateValue` + `StateChange` event | **fall** (confirmed **or** uncertain) |
| 6 | Contact Sensor | Boolean State | `StateValue` | **uncertainty**: some output is "uncertain" |
| 1 | — | manufacturer cluster 0xFFF1FC01 ([stillpoint_cluster.xml](../firmware/port/efr32mg26/stillpoint_cluster.xml)) | `PersonCount`, `FallState` (0 none, 1 suspected, 2 confirmed, 3 uncertain), `Uncertain`, `ProposedExclusions`, `ContractVersion`, `ModelHash` (model CRC32) | detail for advanced integrations |

Notes:

- From Matter 1.3 the Occupancy Sensing cluster declares the sensor type; it is declared
  as **radar**. Confirm the exact cluster revision supported by the chosen SDK.
- Matter has no "fall detector" device type. Boolean State is used because every
  controller shows and automates it; the endpoint label (Fixed Label / User Label) says
  "Fall". To be revisited if the specification adds something specific.
- Endpoint 5 fires on both confirmed and uncertain falls: a fall that cannot be verified
  **is reported**. The exact type is in the manufacturer cluster and on endpoint 6.
- `Tracks[]` (id, x, y, posture, state per person) is planned for v2: a list of structs
  needs a ZAP type definition and its Thread reporting cost is evaluated in F2. In v1
  individual positions only leave the device through the UART diagnostic stream.
- Risk R7: Home Assistant may not expose the manufacturer cluster without specific
  support. The person count is then only available per zone. Checked in F2 with the
  current python-matter-server.

## Reporting policy

- `Occupancy`: immediately when it becomes occupied; when it becomes empty, as soon as the
  last track is dropped (door: ~2 s). No extra fixed hold time.
- Fall: event when it becomes confirmed/uncertain; cleared after the person has been up
  for 5 s or by a local command.
- At most 2 reports/s per endpoint to keep the Thread mesh quiet; a new fall alarm
  bypasses the limit.
