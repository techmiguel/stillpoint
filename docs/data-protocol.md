# Data protocol

## Principles

1. Nobody is recorded without written consent signed before the session (template
   [below](#consent-form-template)). Consent can be withdrawn at any time.
2. The radar captures no image and no voice. The data is still treated as personal: it is
   stored under a pseudonymous ID (`S07`), never a name.
3. The table linking IDs to people is kept apart, encrypted, and only the data owner can
   read it.
4. Training, validation and test are split **by person and by room** with
   [split.py](../ml/radarref/split.py); sessions that would mix them are discarded.
   Without this no metric means anything.
5. Falls are **simulated by healthy adults** on a crash mat. This limitation is written
   next to every published fall metric: real falls of older people are slower, more varied
   and often without recovery, and may behave differently.

## What is recorded per session

| File | Content |
|---|---|
| `*.rfad` | ADC frames from the kit (F1–F3 only), written by `ml/capture_kit.py` |
| `*.json` | session metadata: pseudonym, room, mounting height, time, radar configuration, firmware and contract versions |
| `features/*.bin` | contract v1 records (66 bytes per track and frame) |
| `truth.csv` | ground truth from `bench/annotator.py` |

## Labelling without a camera

In private rooms (bathroom, bedroom) no camera is used. Labelling follows a timed script:
an operator logs every change with a key-press app synced over NTP
(`bench/annotator.py`). In a lab room, with specific consent, a camera may be used only to
verify labels; those videos never leave the labelling team and are deleted once checked.

## Session script (≈ 25 min)

| Block | Activities | Repetitions |
|---|---|---|
| Presence | enter, walk, stand, sit still for 3 min, leave | 3 |
| Posture | standing ↔ sitting ↔ lying (sofa, bed, floor) | 3 each |
| Confusers | sit down hard, lie down fast on the bed, crouch to pick something up, tie shoelaces, exercise | 3 each |
| Falls | forward, backward, sideways, from sitting, slow slip; on the mat | 2 each (10 per session) |
| Two people | one still, the other walks in front and stops; crossing | 3 |

Mind the numbers: because of the split by person and room, the ≥ 100 falls of criterion F1
must come **from the test split only**. Example: 4 test people × 3 sessions × 10 falls in
the test room = 120 falls; the other 8 people record in the other 3 rooms for training and
validation (≈ 160–240 falls).

## Public datasets

Used only for prototyping (signal shapes, model architecture), after checking their
licence. They cannot give the final model because they use other radars, frequencies and
mountings; no published metric comes from them.

## Consent form template

> Starting template, not legal advice: have it reviewed before use and fill in the data
> controller.

**Project:** 60 GHz radar presence and fall sensor (research prototype).
**Data controller:** ______________________ · Contact: ______________________

**What is recorded.** A 60 GHz radar measures distances and movement inside the room.
**It records no image and no sound.** The radar signals are stored with the time and what
you are doing at each moment according to the script (for example "sitting",
"simulated fall").

**Why.** To train and measure the sensor. If you agree below, an anonymized version may be
published so others can check the results.

**Simulated falls.** You will be asked to let yourself fall in a controlled way onto a
crash mat. You may refuse any exercise without giving a reason. Do not take part if you
have an injury, a balance problem, are pregnant or have any other condition that advises
against it.

**Your rights.**
- Taking part is voluntary. You may withdraw at any time and ask for your data to be
  deleted, except data already published anonymously.
- Your data is identified by a code, never by your name.
- Retention: until the end of the project or ___ years, whichever comes first.
- You can exercise access, rectification, erasure, objection and restriction by writing to
  the contact above, and complain to the data protection authority.

**Permissions (tick the ones you accept)**

- [ ] I agree to take part in the recording sessions.
- [ ] I agree to the simulated falls on a crash mat.
- [ ] I agree that my **anonymized** radar data may be published.
- [ ] I agree that, in the lab room only, a camera may be used to verify labels, deleted after verification.

Name: ______________________ Signature: ______________ Date: ___/___/______

Assigned code (filled in by the team): S___
