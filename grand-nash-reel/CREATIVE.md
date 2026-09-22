# "The 11:47 Call" — 20s vertical Reel

**Client:** Grand Nash Studio · AI reception for HVAC and plumbing
**Placement:** Instagram Reels, 9:16, 1080×1920, 20.000s
**Audience:** HVAC and plumbing owners who employ a receptionist or answer the phone themselves.

## The idea

Nobody in this ad talks about AI. The ad is a small night-set film about a
burst pipe and a phone that rings into an empty office, and the product only
shows up as a *consequence*: on the second pass, the call gets handled and a
truck rolls. The pitch is carried by what the owner recognizes — the sound of
their own phone ringing at midnight with nobody there to pick it up.

The deliberate choices that keep it off the SaaS-ad treadmill:

- **No device is ever the hero.** We never cut to a dashboard, a waveform, a
  glowing orb, a chat bubble, or a phone screen with legible UI. The model is
  explicitly forbidden from rendering any of it.
- **No spokesperson.** Nobody smiles at the lens or gestures at a laptop.
- **Available light only.** A bare laundry-room bulb, streetlight through
  blinds, headlights in drizzle, dawn through a doorway. No product lighting.
- **The AI is shown by its absence.** Shot 4 is the payoff, and the reception
  desk stays empty. The truck still leaves. That gap *is* the product.
- **The palette earns its turn.** Cold desaturated blue-green for the first
  three shots, warm sodium in the dispatch beat, warm amber against blue dawn
  at the end. The picture literally warms up when the business works.

## Beat sheet

| # | In–Out | Len | Shot | Beat |
|---|--------|-----|------|------|
| 1 | 0.0–4.5 | 4.5s | `01_flood` | Burst supply line, water across the tile, she's on her knees with a towel. |
| 2 | 4.5–8.0 | 3.5s | `02_dial` | She grabs the phone and dials. Hope leaves her face. |
| 3 | 8.0–12.0 | 4.0s | `03_empty_office` | The contractor's front office. Phone ringing into nothing. The loss. |
| 4 | 12.0–16.0 | 4.0s | `04_dispatch` | Headlights snap on. Tech gets in. Truck rolls into the rain. |
| 5 | 16.0–20.0 | 4.0s | `05_dawn` | Dawn. She exhales in the doorway as the truck pulls away. End card. |

Shot 3 is the whole ad. It is four seconds of an empty chair and a ringing
phone, and it is the only part of the film an owner will still be thinking
about an hour later.

## On-screen copy

All text is drawn locally by FFmpeg — never by the video model.

| Time | Copy |
|------|------|
| 1.6–4.3 | 11:47 PM |
| 5.3–7.9 | Your customer is calling. |
| 8.6–10.6 | Nobody answers. |
| 10.8–12.0 | That call was worth $500. |
| 12.6–14.2 | Grand Nash answers. / Every call. 24/7. |
| 14.4–15.9 | English and Spanish. / Booked and dispatched. |
| 16.3–20.0 | **End card:** AI reception for HVAC & plumbing / **Stop Losing Calls.** / **Book a Free Demo.** / grandnashstudio.com • 346-277-0805 |

## Optional voiceover

The cut works silent-first, which is how most of the feed will see it. If you
add VO, record it flat and unsold — a contractor's register, not an announcer's.
Drop it at `assets/vo.wav` and the assembler mixes and ducks it automatically.

> (0:05) Somebody's water heater just let go.
> (0:08) They called you first.
> (0:11) Then they called whoever picked up.
> (0:13) Grand Nash answers every call, day or night, English or Spanish —
> (0:15) books the estimate, routes the tech, puts it on your calendar.
> (0:17) Stop losing calls.

Music, if you use it: a single sustained low drone through shots 1–3, one hit
on the cut to shot 4, and let it open up for the dawn. Drop it at
`assets/music.mp3`. Keep it under the diegetic sound — the ringing phone in
shot 3 should be the loudest thing in the ad.

## Instagram caption

> A burst pipe doesn't wait for business hours.
>
> The call comes in at 11:47 PM. If it rings out, they don't leave a voicemail —
> they call the next company on the list. One missed emergency call can be $500
> of work, and the customer behind it is worth a lot more than that.
>
> Grand Nash Studio answers every call 24/7, in English and Spanish. Books
> estimates and service appointments, routes to the right tech, and syncs it
> straight to your calendar.
>
> Stop losing calls. Book a free demo → grandnashstudio.com or 346-277-0805
>
> #hvac #plumbing #hvaccontractor #plumbingbusiness #hvacbusiness #homeservices
> #contractorlife #trades #smallbusinessowner #missedcalls

## Hook variants worth testing

The first 1.5 seconds decide everything. Shot 1 is built to work cold, but
these are cheap to swap in `shots.json` and A/B:

1. **As built** — water spreading across tile, no text until 1.6s.
2. **Sound-first** — open on shot 3 (the ringing empty office) for 2s as a
   cold open, then cut back to the flood. Costs you the visual hook but wins
   on "wait, that's my office."
3. **Text-first** — move the `11:47 PM` card to 0.3s so the time stamp lands
   before the image registers.

## Compliance notes

- No claim of a specific booking rate, close rate, or revenue lift is made.
  "$500" is framed as what *a call can be worth*, not a guaranteed result —
  keep it that way if you edit the copy.
- No real company, logo, uniform, or vehicle marking appears; the prompts
  forbid signage and license plates specifically.
- The actors are model-generated and depict no identifiable real person. If
  Meta asks, this is synthetic media — disclose it in Ads Manager if you run
  this as a paid placement in a market that requires it.
