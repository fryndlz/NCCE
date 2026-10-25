# NCCE Date Formatting Specification

## Purpose

The Necromunda Campaign Chronicle Engine (NCCE) stores real-world
campaign dates from the campaign sheet, but presents them as in-universe
Imperial dates.

Every dated chronicle entry should display:

1.  an **Imperial date** as the primary, in-universe date;
2.  the **real-world campaign date** immediately below it in a readable
    form.

The raw machine timestamp from the sheet remains source data and should
not normally be shown to the reader.

------------------------------------------------------------------------

## Canonical NCCE display

``` text
9.815.998.M41
25 October 2026 · 10:46
```

The Imperial line is primary. The real-world line is secondary and
visually subordinate.

If only a calendar date is known:

``` text
9.815.998.M41
25 October 2026
```

Do not display the sheet's raw ISO timestamp in narrative output:

``` text
2026-10-25T09:46:31.046883+00:00
```

------------------------------------------------------------------------

## 1. Imperial date structure

Use the classic Imperial dating system:

``` text
C.FFF.YYY.M##
```

Example:

``` text
9.815.998.M41
```

Where:

  -----------------------------------------------------------------------
  Component               Meaning                 NCCE use
  ----------------------- ----------------------- -----------------------
  `C`                     Check / source-accuracy `9` for dates converted
                          number                  from the real-world
                                                  campaign record

  `FFF`                   Year fraction,          Calculated from the
                          `000–999`               position of the
                                                  real-world timestamp
                                                  within its calendar
                                                  year

  `YYY`                   Year within the         `998`
                          millennium              

  `M41`                   Millennium              Fixed to `M41`
  -----------------------------------------------------------------------

Imperial administrative dating divides a Terran year into **1,000 equal
fractions** rather than months and weeks. A complete date can therefore
be written in the form `0.123.456.M41`. The first digit records the
reliability or provenance of the date, followed by the year fraction,
year and millennium.

### Why NCCE uses check number 9

In the classic Imperial system, check number **9** is used for dates
reconstructed or approximated from a source that does not itself use
Imperial dating.

That describes NCCE exactly: the authoritative campaign record contains
real-world timestamps, which the engine is translating into an
in-universe chronology.

Therefore:

``` text
9.FFF.998.M41
```

is the canonical NCCE form.

Do **not** use `0` merely because the real-world timestamp is exact. In
Imperial dating, `0` means an event dated directly by Terran standard,
not simply "high confidence."

------------------------------------------------------------------------

## 2. Campaign year

NCCE maps the campaign to:

``` text
998.M41
```

This is a deliberate **campaign-era anchor**, not a claim that 2026 CE
mathematically converts to the 41st Millennium.

Recent official Necromunda material itself uses `998.M41` for
Necromundan event logs. *Necromunda: Halls of the Ancients* opens an
event log with:

> Event log shift 777 of the year of Him of Terra 998.M41.

Other official Necromunda books use the same style with nearby late-M41
dates, including `996.M41`. The setting is explicitly at the closing end
of the 41st Millennium.

NCCE therefore treats the real-world year as an organisational layer
outside the fiction. The campaign's events occur within **998.M41**,
while their ordering inside that year is derived from the real-world
dates.

### Year rollover

For the current campaign, **do not automatically advance the Imperial
year when the real-world calendar reaches 2027**.

A real-world New Year is not an in-universe chronological event. Keep
`998.M41` until the campaign administrator explicitly changes the
campaign-era anchor.

This prevents an arbitrary January rollover from silently advancing
Necromundan history.

------------------------------------------------------------------------

## 3. Calculating the year fraction

`FFF` represents where the source timestamp falls within its real-world
calendar year, projected onto the Imperial system's 1,000 equal year
divisions.

Use the timestamp after converting it to the campaign sheet's timezone:

``` text
Europe/Warsaw
```

Then calculate:

``` text
elapsed = local timestamp - 1 January 00:00:00 of that local year
duration = 1 January 00:00:00 of the next local year - 1 January 00:00:00 of that local year

fraction = floor((elapsed / duration) × 1000)
```

Clamp the result to:

``` text
000–999
```

and always zero-pad it to three digits.

### Example

Source value:

``` text
2026-10-25T09:46:31.046883+00:00
```

Convert to the sheet timezone first:

``` text
25 October 2026 · 10:46 Europe/Warsaw
```

Then derive the year fraction and display:

``` text
9.815.998.M41
25 October 2026 · 10:46
```

The exact fraction is generated algorithmically from the timestamp. It
must never be manually assigned from the month number or day number.

### Date-only values

If the sheet contains a genuine date with no time component, treat it
as:

``` text
12:00 local time
```

for fraction calculation.

Using local noon places the unknown event time near the centre of the
recorded day instead of systematically biasing every date toward the
beginning of the day.

The readable line still omits the invented time:

``` text
9.815.998.M41
25 October 2026
```

------------------------------------------------------------------------

## 4. Real-world display line

The secondary line exists so players can immediately identify when the
game actually happened.

Use:

``` text
D Month YYYY
```

or, when meaningful time information exists:

``` text
D Month YYYY · HH:MM
```

Examples:

``` text
30 August 2026
29 September 2026 · 00:00
25 October 2026 · 10:46
```

Rules:

-   Use the full English month name.
-   Do not use numeric-only dates such as `25/10/2026`.
-   Do not show seconds or fractional seconds.
-   Do not show `T`, timezone offsets, or other ISO-8601 syntax.
-   Use 24-hour time.
-   Convert timestamps to `Europe/Warsaw` before display.
-   If a timestamp is clearly functioning as a date-only placeholder
    rather than a meaningful event time, omit the time from
    reader-facing output.
-   Preserve the original raw timestamp internally.

------------------------------------------------------------------------

## 5. Important distinction: official rule vs NCCE convention

### Established by published Warhammer material

-   Imperial dates use a millennium marker such as `M41`.
-   The classic full form contains a check number, year fraction, year
    and millennium.
-   The year is divided into 1,000 equal fractions.
-   Check number `9` denotes an approximate/reconstructed date derived
    from a non-Imperial source.
-   Necromunda publications use late-41st-Millennium dates in their
    event-log presentation.
-   *Halls of the Ancients* specifically uses `998.M41`.

### Defined by NCCE

-   All current campaign events are anchored to `998.M41`.
-   Real-world timestamps determine only the ordering/fraction
    **within** that fictional year.
-   `Europe/Warsaw` is used because that is the campaign sheet's
    configured timezone.
-   `floor()` is used for deterministic fraction conversion.
-   Date-only records use local noon for calculation.
-   The real-world date is displayed beneath the Imperial date.
-   A real-world New Year does not automatically advance the fictional
    Imperial year.

These conventions are required because Games Workshop does not provide a
rule for mapping a modern tabletop campaign's real-world dates onto a
specific fictional Necromundan year.

------------------------------------------------------------------------

## 6. Rendering rules

### Standard chronicle entry

``` markdown
**9.815.998.M41**  
*25 October 2026 · 10:46*
```

### Date-only chronicle entry

``` markdown
**9.815.998.M41**  
*25 October 2026*
```

The application may render these through rich-text styling rather than
literal Markdown. Semantic hierarchy is what matters:

-   Imperial date: primary, prominent, in-universe.
-   Real date: secondary, smaller or less prominent, out-of-universe
    reference.

Do not prefix either line with labels such as `Imperial Date:` or
`IRL Date:` in normal chronicle presentation.

------------------------------------------------------------------------

## 7. Machine-readable output

Internally, keep the source and derived representations separate.

``` json
{
  "sourceTimestamp": "2026-10-25T09:46:31.046883+00:00",
  "sourceTimezone": "Europe/Warsaw",
  "localDateTime": "2026-10-25T10:46:31+01:00",
  "imperial": {
    "check": 9,
    "fraction": 815,
    "year": 998,
    "millennium": 41,
    "display": "9.815.998.M41"
  },
  "realDisplay": "25 October 2026 · 10:46"
}
```

Never overwrite the source timestamp with the fictional date.

------------------------------------------------------------------------

## 8. Pseudocode

``` text
function formatNcceDate(sourceTimestamp, hasMeaningfulTime):
    instant = parseISO8601(sourceTimestamp)
    local = convertTimezone(instant, "Europe/Warsaw")

    if source contains date only:
        calculationTime = local date at 12:00
        hasMeaningfulTime = false
    else:
        calculationTime = local

    yearStart = 1 Jan calculationTime.year 00:00 Europe/Warsaw
    nextYearStart = 1 Jan (calculationTime.year + 1) 00:00 Europe/Warsaw

    elapsed = calculationTime - yearStart
    yearDuration = nextYearStart - yearStart

    fraction = floor((elapsed / yearDuration) * 1000)
    fraction = clamp(fraction, 0, 999)

    imperial = "9." + pad3(fraction) + ".998.M41"

    if hasMeaningfulTime:
        real = format(local, "D MMMM YYYY · HH:mm")
    else:
        real = format(local, "D MMMM YYYY")

    return {
        imperialDisplay: imperial,
        realDisplay: real
    }
```

------------------------------------------------------------------------

## 9. Examples from the current campaign sheet

``` text
9.815.998.M41
25 October 2026 · 10:46
```

``` text
9.802.998.M41
20 October 2026 · 19:05
```

``` text
9.745.998.M41
29 September 2026
```

``` text
9.663.998.M41
30 August 2026 · 13:51
```

The exact Imperial fraction must always be recomputed from the stored
timestamp rather than copied from these examples.

------------------------------------------------------------------------

## 10. Do not do this

Do not convert the literal Gregorian year `2026` into:

``` text
026.M3
```

That is mathematically what the classic Imperial calendar would call the
historical year AD 2026, but it would place the Necromunda campaign in
the third millennium and is therefore useless for the chronicle.

Do not invent pseudo-Imperial month names.

Do not replace the real-world date entirely with the Imperial date.

Do not derive `FFF` from campaign week, battle number, scenario number
or arbitrary "shift" counts.

Do not automatically treat Necromunda's local cycles as Terran days.
Official Necromunda material uses terms such as cycles and grand cycles
as local temporal language, while formal event logs can still carry an
Imperial year.

------------------------------------------------------------------------

## Source basis

The principal published Necromunda reference is *Necromunda: Halls of
the Ancients* (Games Workshop, 2024), whose opening event log uses
`998.M41`. The current *Necromunda Core Rulebook* establishes Necromunda
as an Imperial Hive World and gives its orbital cycle as 723 Terran
Standard, reinforcing that Necromundan local time and Terran
administrative dating should not be conflated.

The structural definition of the classic Imperial dating system
originates in Games Workshop's *Warhammer 40,000* rulebook material,
commonly reproduced as the check-number / year-fraction / year /
millennium structure. NCCE follows that classic structure because it
matches the dating syntax still visibly used in current Necromunda
publications.

Where the published sources do not specify a modern
real-world-to-fictional-campaign conversion, this document explicitly
defines an NCCE convention rather than presenting it as Games Workshop
canon.
