---
name: ncce-campaign-writing
description: "Write NCCE campaign prose from supplied evidence packets. Distinguish all 16 prose forms and apply NCCE's event-based adaptation of Generative Agents when writing observations, reflections and current thoughts. Use with the existing writing chat's literary style and examples."
---

# NCCE campaign writing

Version 3, 5 November 2026. This is a portable writer briefing for the existing Project conversation. It describes NCCE's unchanged event-based cognitive rules and the 0.27.0 dependency waterfall. The Google relay is installed; scheduled writing access must still be demonstrated in the work chat. This skill alone does not install a schedule.

## Your role

Write the requested literary artifact from its supplied context. Keep the established style, examples and editorial judgement of this writing conversation. This skill explains what each entry means, what its evidence supports and how it fits into the app; it is not a replacement literary persona.

NCCE supplies factual events, chronology, importance, retrieved causes, identity/voice context and target IDs. You supply prose. Do not silently become the game referee, memory selector, scheduler or a second campaign database. If an essential cause or identity is missing, request the missing packet rather than invent its bookkeeping.

Read the requested form below. For any fighter memory, reflection or thought, also read Cognitive mechanics. Follow the exchange Sheet's Writer instructions for delivery and status changes. The skill does not authorize processing more requests than the owner requested.

## The two layers

The literary layer is entirely in-world: complete prose, a coherent speaker/author and appropriate document composition. The app layer carries source IDs, provenance, importance, mechanics, real-world timestamps and delivery notes. Those labels do not belong in a fighter's sentences or in-world metadata.

Mechanical state is authoritative about game outcomes. Relevant player-authored/canonical text is authoritative about established fiction. Verified rulebook context establishes setting and territory/faction properties. Earlier generated material provides fictional continuity, not independent proof. If two authoritative sources conflict, do not settle the conflict by inventing prose.

Use the supplied Imperial date for in-world metadata; retain real dates only in the exchange/app wrapper. Do not calculate a different conversion. Unknown dates remain unknown. A source log timestamp can order an event without proving its exact physical moment. Publication/scraping/writing time is not the historical event time.

Use one complete Markdown document in writer_text_md: headings, bold metadata labels, paragraphs, dialogue/transcript turns and sign-off when appropriate. A personal memory does not automatically need a government letterhead. Administrative records need an institutional reason to exist; not every gang speaks like C-NINE. Format and preserve authored wording unless an actual edit is explicitly requested.

## Prose forms

The keys below are the exact 16 exchange/System keys. A category's existence is not a request to fill every possible slot. Baselines, changing histories, individual events and current thoughts occupy different places in the app.

### 1. fighter_biography — stable personal background

**Inputs:** earliest supported character state, role/faction, relevant authored background, supplied identity/voice context.

**Write:** a particular fighter's formative background and identity, providing the lens through which later events will be experienced. A generated biography may establish fictional background within the brief's creative scope; it remains inference.

**Boundary:** an existing authored biography takes precedence and is not a replacement target. Do not silently absorb later XP, injuries or promotions into the original background. Those developments belong in the memory stream. A missing biography does not authorize inventing an entire mechanically consequential campaign history.

### 2. fighter_memory — one observation or experience

**Inputs:** one supported cause, its time/order and evidence, the fighter's background and historical context; or an explicitly labelled undated baseline observation.

**Write:** that experience in the fighter's own voice. Interpret what happened through what the fighter values, notices and understands. The authored biography shapes the perspective; it is not the incident to replay. An advancement should become a meaningful change in lived capability, not the isolated label "Cool" or an announcement that a statistic was updated.

**Boundary:** one source-backed experience, not a retrospective summary of every supplied fact. A gang's victory can be news the fighter receives; it does not prove attendance, witnessing or a personal kill. A baseline establishes what was already known, not a newly invented dated recruitment or advancement. Physical consequences and private reactions are fictional interpretation; no unsupported recorded attacker, wound location or treatment outcome.

### 3. fighter_reflection — a conclusion drawn from memories

**Inputs:** the engine-selected supporting observation IDs, facts, dates/order and any ready observation prose; character background.

**Write:** a higher-level connection: a revised judgement about the self, another person, danger, duty or belonging that follows from those experiences. This is what the experiences mean together, not two incident summaries pasted together.

**Boundary:** no new external event. Do not manufacture another fight to justify the insight. Preserve the cited causes outside the prose; do not recite their IDs. The writer does not choose a new reflection threshold, recursively reflect on previous reflections or expand into uncited lifetime memories. Current implementation is a bounded observation-batch synthesis; see Cognitive mechanics.

### 4. fighter_mind — one current thought

**Inputs:** one engine-selected current cause/family, current condition, relevant identity and background, selected evidence and memory link.

**Write:** a separate short first-person thought, normally one or two sentences and approximately 12–40 words, about what weighs on the fighter now. This is a content-size convention for a small UI card, not a literary grading rule.

**Boundary:** do not copy the historical memory or re-enact its event as happening again. One request makes one thought, not a full dashboard of four. NCCE selects up to four different current causes; fewer are valid. Do not retain an obsolete critical-injury concern after its supported resolution merely because the injury was dramatic. Death yields no current thoughts. A past loss can remain relevant without becoming a new loss today.

### 5. gang_origin — authored gang backstory

**Inputs:** the gang's explicit authored Sheet backstory.

**Write:** currently this is an authored-only slot. Present/format the supplied backstory when requested, preserving its wording. If there is no authored source, leave the slot empty rather than generating a substitute.

**Boundary:** C-NINE's two long stories belong in Archive, not automatically in its gang baseline. Do not infer permission to generate a gang origin because it appears in the Forms dropdown. Future origin generation would require an explicit design change.

### 6. gang_history — the gang's changing history

**Inputs:** relevant gang baseline, ordered supported events, previous accepted history and an explicit endpoint/cutoff.

**Write:** a developing account of how the gang's position, practices or identity changed across those events. Keep temporal transitions legible. The institution's own record, a chronicler or another justified voice may supply the perspective.

**Boundary:** neither another static backstory nor an unfiltered financial/roster dump. Do not treat the current roster, territory holder or latest rank as true throughout the past. Collective consequences do not establish every member's inner response.

### 7. gang_event — one gang-level change

**Inputs:** one recorded gang change and the gang's state/context at that point.

**Write:** the local consequence of that change for this gang. It may concern a result, recruitment, territory, reputation, allegiance or resources, depending on the actual request. Make the change meaningful within the gang's own social and material world.

**Boundary:** one entry is not a whole gang history. A credit change alone does not prove the precise goods bought, who paid whom or an unseen criminal scheme. Missing from a roster does not mean dead. Keep the actual mechanical claim no broader than its evidence.

### 8. territory_origin — a place's baseline identity

**Inputs:** territory type and verified rules/setting context, relevant authored place material, known location/holder where supplied and the brief's creative scope.

**Write:** an inhabited, distinctive place: what it is physically, what people do there and a history or circumstance that makes this instance memorable. A generated local name is a fictional designation, not a change to the mechanical territory type. An Administratum assessment is one suitable form when the chosen author fits it.

**Boundary:** do not turn every territory into a passage, toll system or tally office. Begin with the actual territory function. Fictional local history may be invented where authorized; an actual campaign seizure or casualty cannot. This baseline is not the timeline of later ownership changes. Existing authored description remains primary.

### 9. territory_history — a place through time

**Inputs:** its baseline, ordered ownership/state changes, related battles, accepted local incidents and a cutoff.

**Write:** how this particular place changed as the campaign progressed. Distinguish successive custodians and circumstances; allow the baseline to acquire consequences rather than repeatedly introducing the place from scratch.

**Boundary:** never flatten several owners into simultaneous occupation or let the current holder author every earlier record. This is a synthesis, not a replacement for the individual timeline entries. Existing ambient fiction can shape continuity without becoming evidence that a mechanical change occurred.

### 10. place_event — one observed territorial change

**Inputs:** one supported ownership, battle-related or territory-state change, before/after evidence and historical context.

**Write:** what that transformation looks like within the world. If the source changes a holding from a shrine to a settlement, describe the observed habitation, not an instruction to change the territory field. For a seizure, use the actual known participants and result.

**Boundary:** an unexplained state change does not reveal its cause. Do not invent a documented battle to account for a player edit. Physical connective detail is fiction; new ownership, casualties, income and mission outcomes must follow supplied evidence. Keep the event's author/POV consistent with its affiliation.

### 11. place_ambient — a fictional local occurrence

**Inputs:** an explicitly authorized ambient-entry request, territory baseline, holder at that time, relevant earlier fiction and a free position in the chronology.

**Write:** a small, self-contained occurrence that gives this place life: a local incident, phenomenon, encounter or custom. This form has more creative freedom than an observed mechanical event and is stored as connective_fiction.

**Boundary:** no mechanical impact. Do not award money/XP, add a lasting injury, change ownership or resolve a battle. Fit the existing place and sequence rather than inventing a disconnected vignette. The writer does not autonomously roll events, create requests or advance fighter clocks by writing one; any later knowledge propagation belongs to the engine.

### 12. battle_report — one engagement

**Inputs:** known mission, participants, winner, territory, time window, actual authored accounts and any explicitly linked fighter changes/returns. Before/after evidence must retain its limitations.

**Write:** a coherent account of this engagement from the requested author's viewpoint, using the supported outcome and meaningful consequences. Where an inferred account is authorized, creative connective action can make the known facts into an account without presenting invented manoeuvres or causal mechanisms as recorded testimony.

**Boundary:** an authored report is primary, not merely evidence to be overwritten by a generated summary. Do not draft a rival replacement unless explicitly requested. Roster membership or loosely nearby changes do not prove attendance, who inflicted an injury or who killed whom. A post-battle change must not be relocated into combat to make a better scene. An internal gang report must maintain that gang's own viewpoint.

### 13. post_battle_addendum — a separate after-action packet

**Inputs:** its linked engagement, supplied post-battle documents/events, author/recipient and packet scope.

**Write:** the aftermath in a distinct document or packet: medical, personnel, requisition, inspection, correspondence or other appropriate attachments. One logical entry is the packet for one engagement and may contain several clearly separated attachments.

**Boundary:** do not rewrite the battle account. Existing authored attachments are preserved and formatted, not silently regenerated. If an authored source announces three attachments but supplies two, retain/report the source discrepancy outside fiction rather than inventing the missing third as recovered source text. A fictional attachment cannot create an unrecorded mechanical result.

### 14. downtime — one gang's interval between battles

**Inputs:** the relevant gang's previous battle end, next battle start when known, interval events, baseline and accepted continuity.

**Write:** a coherent inter-battle account of what this gang deals with in that interval. Purchases, repairs, recovery, recruitment, changed responsibilities and relationships can matter when supported. Several supplied events may form one ordered account here.

**Boundary:** this is not the battle report or an endless daily-life simulation. Use this gang's boundaries; another gang fighting does not automatically end its downtime. An unknown next battle leaves an open interval, not permission to invent its date. Distinguish recorded between-game changes from zero-impact fictional connective scenes.

### 15. region_history — the campaign-wide chronicle

**Inputs:** ordered cross-gang engagements, holdings/state changes, relevant authored accounts and a cutoff.

**Write:** the larger situation and how it developed: contested ground, changing power, consequences reaching beyond one gang. Choose a plausible record-making perspective and distinguish what it can know from private character experience.

**Boundary:** no omniscient access to every fighter's thoughts or hidden motives. Do not fill unobserved campaign periods with fabricated mechanical events, merge unrelated engagements or make current geography retroactively true. This is a changing regional synthesis, not a new territory origin.

### 16. relationship — a supported gang-pair history

**Inputs:** the identified gang pair, repeated encounters, outcomes, authored relational context and prior accepted interpretation.

**Write:** how those contacts shape the relationship as a fictional interpretation: patterns of hostility, caution, obligation or cooperation where the evidence and brief support them.

**Boundary:** the implemented category covers gang-pair history, not a complete system of individual social bonds. Repeated opposition can support inferred rivalry; it does not prove a recorded alliance, private friendship or a named fighter's personal grudge. Preserve the distinction between an encounter pattern and an official relationship change.

**Archive is separate:** it is an authored collection, not a seventeenth generation form. The Prospect and The Deep Answers remain the two identified stories. Do not generate missing Archive stories or copy their text into other baselines automatically.

## Cognitive mechanics

### The paper and the adaptation

The research north star is Park et al., [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/html/2304.03442v2), sections 4.1–4.3. The comparison below is deliberate; NCCE is not a full implementation of the paper.

| Mechanism | Paper | Implemented NCCE contract |
| --- | --- | --- |
| Persistent memory | Observations and higher-level reflections, with references. | Source-backed observation/reflection history; prose remains inference. |
| Retrieval | Recency, importance and query relevance. | Weighted event recency, fixed-rule salience, current-condition/topic relevance and character bias. |
| Recency | Decay since last retrieval, measured in simulated hours. | Distance from causal formation in fighter-relevant events; access does not refresh it. |
| Importance/relevance | Model-rated importance; embedding similarity; normalized components. | Deterministic importance and topic/profile rules; no embedding search. |
| Reflection | Threshold-triggered questions, retrieved evidence and recursive synthesis. | Bounded per-batch observation synthesis; no recursive or cross-batch reflection. |
| Planning/reaction | Hierarchical future plans and reactive action/dialogue loops. | No autonomous daily planner; meaningful campaign events drive updates. Current thoughts are NCCE's own presentation. |

The writer should preserve the principle that experience informs later interpretation. It must not claim that the paper prescribes NCCE's numerical weights, four thought cards, stim system or fixed reflection threshold.

### Observation, reflection and current thought are different objects

An observation interprets an experience. A reflection draws an inference from several cited experiences and is itself retained in history. A current thought is a separately written present reaction to selected causes. They are not three labels for the same paragraph.

Memory type is not provenance: an observation's mechanical cause can be factual while its first-person wording is inference. A reflection is inference, not evidence that another external incident happened. Authored background is a prior-life lens; do not re-stage it whenever a new stat changes.

### Event clock: recency without real-time decay

Each fighter has an independent sequence of distinct supported changes relevant to that fighter. An injury, XP change and shared result are three changes even if one refresh imports all three. Two observations of the same fact count once. Corrections follow the original event identity, not a new experience.

Dates order facts; their elapsed duration does not age a mind. Use supported occurrence time, otherwise first observation time. Unknown/tied order has a stable ID tie-break, not an invented causal story. Baseline has position zero.

An observation is anchored to its causal event. A reflection/current thought is anchored to its latest cited factual cause. Rewording it later does not move its formation to today. Reflections, thoughts, app visits, unchanged refreshes and writing calls add no factual steps. Unrelated fighters' private events do not tick this fighter's clock.

If the head is N and the cause's formation position is p:

`distance = N - p`

`recency = 2 ** (-distance / 10)`

At distances 0, 10 and 20, recency is 1, 0.5 and 0.25. Ten real years with no relevant change have no effect. Ten subsequent relevant changes halve recency. There is no fixed calendar or event-count expiry; resolution and relevance govern current selection. Resolved experiences remain history.

The historical Munda activity archive is not yet wholly converted into cognitive observations. A raw source UUID and a cognitive-ledger memory ID are different identities; do not invent a new memory or tick merely because the same event is available in both places.

### Importance is assigned by the engine

Scale: 0–10 narrative salience, not a characteristic, probability or psychiatric measurement. Do not write these numbers into the fiction or rerate them to make a chosen paragraph eligible.

| Supported cause | Base importance |
| --- | ---: |
| Baseline / ordinary XP change | 4 |
| Advancement / skill change | 7 |
| Condition/effects change | 7 |
| Status change | 6 |
| Recorded kills change | 7 |
| Weapon change | 6 |
| Wargear change | 5 |
| Characteristic change | 6 |
| Recruitment / newly listed fighter | 6 |
| Unlisted fighter | 3 |
| Shared gang battle outcome | 6 |
| Gangmate loss | 9 |
| Gangmate capture | 8 |
| Territory holder change | 6 |
| Baseline combat record category | 6 |
| Gang reputation change | 6 |
| Gang allegiance change | 8 |

Overrides: critical injury = 9; recorded death status = 10; Class/Type change = 8; roster Cost change = 2. Class/Type changes carry the recorded before/after values, not proof a rules-legal promotion occurred. XP decreasing is not automatically lost competence or a particular purchase. Recovery/captivity/scars/return and similar tags help classify concerns; they are not prose.

Current interpretation confidence defaults are 0.65 for observations and 0.60 for reflections. These are design metadata, distinct from factual source confidence; they do not mean a percentage chance the fighter literally said the generated words.

### Reflection eligibility and synthesis

The current engine groups observations by batch, normally the target snapshot. A batch needs at least two observations with importance >=4 and a combined importance >=12. It cites at most four, ordered by importance then stable key. This is not a rolling lifetime counter and does not imply reflection after every injury.

`reflection_importance = min(10, round(mean(cited importance) + 0.5, 1))`

For example, importance 9 plus 6 qualifies (total 15); citing those two gives reflection importance 8.0. An injury alone does not qualify. This arithmetic is an explanation, not a writer-side task.

The writer receives selected observation facts/order/tags and ready observation prose where available. It may reflect from evidence even if some observation prose is unwritten. Stale text is not a positive style example. Produce a supported inference without new incidents. Source observation IDs and the union of supporting facts/events remain in metadata. No new reflections are prepared for deceased fighters.

### Mind selection and lifecycle

For eligible causes the implemented score is:

`score = 0.40 * (importance / 10) + 0.30 * recency + 0.25 * relevance + 0.05 * character_bias`

Relevance uses current condition/topics: 1.0 for an active-topic match, 0.65 for supported battle/equipment/promotion/advancement/return topics, otherwise 0.25; return-to-duty while Active receives 1.0. Additional condition filters exclude inappropriate old injury/recovery/captivity concerns and history-only/death entries. Character bias follows profile-topic matches. The writer does not recalculate or override these values.

NCCE removes duplicate evidence/labels, excludes baseline or unanchored causes from current-thought drafting and selects at most four causes, with one per reaction family: condition, battle, grief, equipment, progress, return or social. Battle/equipment use their newest eligible event-position cause. Thus a critical injury and recovery should not occupy redundant simultaneous condition cards.

Current conditions resolve through supported status/effect changes; death removes current thoughts. Losing selection without factual resolution means superseded, not cured. A relevant saved thought can return without rewriting. Thought text is separate from its source memory; changing a historical paragraph does not automatically demand a new current thought. Candidate cause/evidence may exist while its prose is still awaiting writing.

No arbitrary expiry, no opening-a-page reinforcement, no automatic whole-roster rewording and no obligation to fill four cards. An old, important, relevant cause can remain selected.

### Identity, voice and stimulus attention

Authored character detail takes precedence. Role, faction, characteristics and recorded history can inform an embodied perspective; they do not deterministically prove personality. High Toughness can suggest familiarity with strain without proving fearlessness. C-NINE diction is not a universal gang dialect. Unsupported identity details remain unknown rather than being guessed from a name.

Current profile tendencies include responsible (leader/champion), aspiring (juve/prospect), enduring (T>=4 or W>=2), physical (S>=4), analytical (Int 1–5), composed (Cool 1–5), resolute (Willpower 1–5) and blooded (at least five recorded kills). Lower target numbers are better for the relevant mental characteristics; do not reverse that interpretation.

Stimulus weights are attention cues: start at 1.00 per topic, add 0.15 per supported mapped voice tendency and 0.30 for a matching current condition/role, capped at 1.50. Up to five elevated topics can be supplied. They help choose what this fighter notices; they do not alter mechanical outcomes, importance or retrieval scores and are not diagnoses. No fresh model call or identity questionnaire is needed merely to read them.

### Histories outside a fighter's mind

Gang/place/region/relationship histories are narrative projections over evidence. They do not automatically receive independent psychological scores, reflection thresholds or fighter moodlets. An ambient incident likewise does not become every fighter's experience merely because it was written. The engine must provide supported exposure/shared news before it becomes that fighter's cause.

## Delivery and current operational boundary

The server now replaces unapproved legacy generated text even when it was marked
ready. It protects authored sources and imported writing-chat entries. Only write
PENDING rows: DRAFT rows with a form are deferred until prerequisites are accepted.
The order is baselines → chronological events → cited reflections → current
thoughts → histories/downtime/relationships → regional chronicle. The separate
existing_fiction block contains accepted dependencies; use it as continuity,
never as proof of an unrecorded mechanical event. Do not reuse the old machine
wording. Queue status is an operator dashboard, not a writer input. NCCE selects
the frontier; the writer takes only PENDING rows from Queue. Started/saved work is preserved;
do not generate a second version when a row already contains prose.

Use the exchange's immutable request_id, entity_key, entry_key, context_id and source_revision. One requested entry receives one finished delivery, not multiple candidates for a hidden reviewer. Save complete text before READY. Never regenerate an existing result just because saving/import acknowledgement failed; preserve and retransmit it.

The 0.26.0 exchange uses Automation instructions as its transport contract once installed. It exports at most five unfinished requests, and the writing chat processes at most three per run. READY authorizes automatic import of that exact text; the relay alone writes IMPORTED and its committed receipt. The importer supports existing derived slots in 14 forms. Gang origins remain authored-only; post-battle addenda currently use the authored dossiers, with no automatic generated slots. This skill does not start Mara's already imported pilot or install a work-chat schedule. Full race/embodiment/faction guidance is in Voice identity. If the relay is not installed, retain the earlier manual delivery flow and do not claim automatic publication.

## Maintenance and sources

This briefing was checked against the current repository modules: src/prose_progress.py (16 forms), src/story_engine.py (classification/reflection/retrieval), src/fighter_event_clock.py (logical time), src/fighter_mind.py (current-thought selection/lifecycle) and src/writing_director.py (voice/attention/date metadata). Current prose generation remains disabled in the app; these modules prepare/select or preserve derived records without provider calls.

When changing numerical rules, update the implemented code, tests and current design together; do not quietly turn a writer instruction into a new game mechanic. Historical Workshop/reviewer/RAG documentation describes removed components and is not an instruction to restore them. The white paper is the architectural reference; the explicit NCCE adaptations above are the operating contract.
