# Writer identity and perspective rules for Minds and Memory Streams

## Aim and scope

This document defines how the writer should turn one recorded campaign event into a character-specific memory or thought across Necromunda and the wider 40k setting. It is a perspective system, not a personality generator. Identity changes what a character can perceive, knows, notices, values, and calls things; it does not change what happened.

The event ledger, importance, mood calculations, retrieval weights, mechanical values, citations, and provenance remain authoritative and unchanged. The writer may select an interpretation and diction; it may not invent a battle action, rule effect, hidden fact, belief, relationship, psychic experience, or species trait to make the prose more colorful. If the source does not establish a detail, leave it open.

Necromunda rules supply useful cues about a fighter's battlefield function, status, options, affiliations, and constraints. Those rules are not complete biographies. The supplied 2023 Core Rulebook explicitly distinguishes a fighter's **category** (such as Leader, Champion, Prospect, Ganger, Juve) from the fighter's **type** (such as a House-specific type); a general category rule applies across types, while type-specific rules need not. Preserve both raw labels rather than collapsing them. A label such as Specialist, Brute, Hanger-on, Hired Gun, or Pet is not by itself proof of age, experience before recruitment, intelligence, loyalty, autonomy, or private thought. Use the exact roster/rules source and edition in force for that campaign, because gang lists and categories evolve.

## The compositional model

Represent a fighter through independent dimensions. Populate only dimensions supported by authored material, campaign data, or an explicit roster/rules designation. Multiple values may be present where meaningful; do not collapse them to a single archetype.

| Dimension | Question answered | Example values (illustrative, not exhaustive) |
| --- | --- | --- |
| `being` | What kind of mind/body is this? | human, abhuman, clone, vat-grown, xenos, animal, engineered organism, machine intelligence, human-machine composite, unknown |
| `lineage` | What ancestry or biological alteration matters? | Ogryn, Ratling, Squat/Kin, Goliath gene-line, sanctioned mutation, cult hybrid, cybernetic alteration |
| `culture` | Which learned community frames duty and belonging? | hive clan, nomad tribe, Clan House, guild, Imperial institution, Mechanicus sect, craftworld, kabal, sept, ork kultur, outlaw crew |
| `institution` | Which organization sets formal duties, doctrine, or status? | Enforcers, Guild, Ecclesiarchy, cult, military unit, trading concern, noble household, gang, charter company |
| `place` | What environment shaped ordinary expectations? | spire, hive middle, underhive, sump, ash wastes, settlement, voidship, forge, off-world, unknown |
| `fighter_role` | What is their current rules/campaign position? | Leader, Champion, Specialist, Ganger, Juve, Prospect, Brute, Hanger-on, Hired Gun, Pet, captive, outlaw |
| `rules_type` | Which fighter type/profile does the rulebook assign? | Preserve the exact profile name separately from category, gang affiliation, and occupation. |
| `work` | What work or practiced craft do they do? | loader, chemist, doc, trader, scout, driver, handler, spy, preacher, miner, gunsmith, sanctioned operator |
| `training` | What methods have they been taught? | gang drills, clan craft, military drill, trade apprenticeship, ritual practice, self-taught, unknown |
| `condition` | What current or enduring body/mind circumstance is relevant? | injury, cybernetics, mutation, sensory impairment, psychic status, addiction, captivity, none recorded |
| `life_history` | What personal facts orient their interpretation? | authored kinship, migration, debt, former service, loss, ambition, taboo, named relationship |
| `voice` | What stable personal choices shape expression? | terse, formal, humorous, devout, suspicious, tender, boastful; only authored or accumulated evidence |

Store tags as structured key/value data (with source/provenance), not a single string that conflates these dimensions. Example:

```json
{
  "being": ["human"],
  "culture": ["House Escher"],
  "place": ["hive city"],
  "fighter_role": ["Specialist"],
  "work": ["chemist"],
  "condition": ["sanctioned psyker"],
  "voice": [{"value": "patient", "source": "player_authored"}]
}
```

This example shows shape only. A fighter should not inherit its values just because a model or gang usually has them. Existing roster `Type` and `Class` should map only to the closest role/function with a retained raw value and source; no backfill of speculative biography. Gender and pronouns are optional authored identity fields, never derived from name, miniature, class, or species.

### Evidence levels

- **Authored identity:** player-entered biography, explicit character tags, or campaign canon. Quote or use it faithfully; distinguish player truth from canon where provenance requires it.
- **Recorded designation:** faction, fighter type/class, skill, equipment, or special rule in the authoritative current roster/rules. Use only the inference directly licensed by that designation. A weapon is not proof the fighter fired it in a particular battle.
- **Repeated behavioral evidence:** patterns across sourced memories may support a cautious voice tendency (e.g. repeatedly prioritizes another fighter's safety). Store as an inference and cite the memories.
- **Unknown:** omit it. Never fill gaps by species stereotype, gender stereotype, name, image, or genre convention.

Do not make an inference more authoritative because it is repeated in generated prose. Derived memories do not become canon by feeding back into the next prompt.

## How dimensions compose

Apply dimensions in this order for each memory. This is an attention and language procedure, not a ranking of human worth:

1. **Event boundary:** establish exactly what source event says and what it does not say. Death, injury, XP, promotion, capture, and battle outcome must match their evidence.
2. **Awareness boundary:** decide what the character could know at the memory's point in the campaign. Do not grant omniscience, hidden faction secrets, enemy motives, or events they did not witness/hear about. Shared gang events are news only where the system says they are shared.
3. **Embodiment:** choose available senses, bodily limits, needs, and continuity of memory appropriate to the explicitly recorded being/condition. Do not assume human vision, speech, pain, sleep, or cognition for every entity.
4. **Social frame:** apply the specific community, institution, and place. A community can supply vocabulary, obligations, status markers, rituals, and taboos; it does not dictate each member's belief or compliance.
5. **Role and work:** ask what the event means for current duties, competence, risk, standing, resources, or future opportunity. Rules-defined role and occupational history are separate fields.
6. **Personal history and voice:** use authored relationships, aims, losses, and established expression. Use at most a few relevant cues in one short memory; do not recite the whole tag set.
7. **Neutral fallback:** where evidence is thin, write simply and leave interpretation tentative. A distinctive voice is not worth a false claim.

Different fighters can remember the same event differently while retaining identical evidence. Different does not mean contradictory mechanics: one may register lost income, another a broken formation as their occupation understands it, and a beast may register the handler's absence or a familiar stimulus. The factual evidence block remains common and separately displayed.

## Setting and faction as context, not personality

### Necromunda social and institutional frames

Use gang/faction affiliation to select likely social questions and terms, then let the individual's authored history override or complicate them. These are directions for research and vocabulary, not mandatory traits:

- **Clan Houses:** Escher, Goliath, Orlock, Van Saar, Delaque, and Cawdor each have internal structures and variant cultures. Think in terms of House, clan, work, status, rivalry, and the fighter's place in a particular gang. Avoid using a single adjective as the voice for the whole House. House lists and variants can change: attach the current book/rules context to source-derived tags.
- **Palanite Enforcers and precinct life:** attend to orders, jurisdiction, chain of command, public order, evidence, and the gap between institutional duty and a particular officer's conduct. A badge does not establish lawful conduct, personal loyalty, or belief in the regime.
- **Guilds, charters, and bonded work:** separate a Guild's commercial or labor authority, a charter's claims, and the individual's actual obligations. Debt, contract, family trade, and material survival may matter differently to a master, hired guard, worker, or defector.
- **Ash Waste Nomads and other wasteland communities:** place, weather, routes, shelter, water, mounts/beasts, kin, and outsider relations can matter. Do not treat a Nomad as a hive dweller with a few desert nouns; equally, do not assume every tribe shares custom or hostility toward outsiders.
- **Outcasts, Venators, hired guns, and outlaw crews:** consider chosen association, reputation, price, debts, patrons, and uncertainty of belonging. Contract status is not proof that a character is mercenary in outlook.
- **Cults and corrupted gangs:** distinguish organization, doctrine, recruitment, secrecy, coercion, and an individual's knowledge. A roster's faction label does not mean every fighter knows the cult's full origin, prophecy, or corruption.
- **Spyre hunting parties, brutes, hangers-on, and hired specialists:** their rule roles often describe why the gang can recruit or field them. Use the actual role, sponsor, training, and personal history; do not assume equal autonomy across categories.

## Necromunda perspective patterns grounded in the supplied books

The source books describe institutions and pressures, not a mandatory inner monologue for every member. Use the “writer can attend to” column only when the fighter's role and known history make it relevant. A gang name alone must never select a personality adjective or a complete voice.

| Setting pattern | What the lore/rules establish | What a writer can attend to | Guardrail |
| --- | --- | --- | --- |
| Hive life and feudal obligation | The Core Rulebook describes dense hive populations, stratified House/Guild obligations, industrial labor, imported necessities, and populations beyond reliable census. | Rationing, shifts, air/light, access, labor quotas, patronage, debt, and limited personal control can ground memory. | Do not assume every hive-born person is poor, ignorant, resigned, or religious; establish layer, work, and status. |
| House membership | The six Clan Houses are industrial and political powers, with interdependence as well as competition. | Ask which product, service, territory, contract, or dependency touches this fighter's life. Rivalries can coexist with trade and reliance. | “House fighter” does not prove direct employment in the House's dominant industry or knowledge of House policy. |
| Cawdor / Redemption | House identity is linked to Redemption faith, masks, and tension between House orthodoxy and more radical/outlaw currents. | Faith may frame duty, purity, sacrifice, and judgment; a dissenter may frame the same institution as hypocrisy or danger. | Do not presume every Cawdor is an extremist or knows an outlaw cult's secrets. Record which current the fighter belongs to when known. |
| Delaque | The House is associated with intelligence, espionage, secrecy, concealed networks, and origin stories surrounded by conflicting accounts. | Information asymmetry, what can be said aloud, coded language, and sensory environment where supported. | Treat rumors about Delaque biology, psychic linkage, or origin as rumors unless established. Do not make every Delaque omniscient or conspiratorial. |
| Escher | The House has a distinctive matriarchal history, severe gender imbalance tied to the Flesh Curse, major chem/alchemy industries, and varied gang specialisms. | Kinship, lineage, medicine, chem craft, gendered House structures, status, and production risks may matter to a particular Escher. | Do not use gender as an innate voice trait or project House-wide attitudes onto one fighter. Identify the actual gang, role, and authored view. |
| Goliath | Wider Necromunda lore presents engineered origins and distinct statuses, including Vatborn, Natborn, and Unborn. | Origin, bodily maintenance, stimms, chosen/adopted House membership, creation, work, and control can produce different stakes. | Do not equate size/Strength with stupidity, aggression, pain tolerance, or identical upbringing. “Unborn” and “Vatborn” are not interchangeable. |
| Orlock | House of Iron describes mining, transport, family power, and a Drudge underclass; gang belonging can be both a route to status and part of House control. | Kin and gang bonds, road/convoy work, reputation, dangerous labor, mobility, and tension between “gang” and “House.” | Do not automatically treat the gang as freely chosen family or assume all Orlocks are road crew. Drudge, prospector, clan heir, and ganger occupy different positions. |
| Van Saar | House of Artifice details technical production, hierarchy and internal titles, specialized work, and bodily costs associated with House technology. | Trade-specific vocabulary; status tied to access to knowledge, tools, or decision-making; costs an institution may conceal. | Avoid generic “logical/analytical” voice. Do not assume every fighter is an Archeotek, understands the STC, or knows the source of a health risk. |
| Palanite Enforcers | The Book of Judgement frames Enforcers as an institution of order within Necromunda's feudal system, distinct from the Adeptus Arbites, with command, precinct, and political pressures. | Orders, jurisdiction, evidence, public order, quotas, peers, and gaps between doctrine and local practice. | Uniform does not make an individual a true believer or lawful actor. Do not confuse Enforcers with the Arbites. |
| Guilders, traders, and criminals | The Book of Judgement depicts trade and criminal power as networks embedded at different hive levels; employment, contracts, coercion, and patronage overlap. | Credit, permits, access, goods, debts, protection, bargaining, and risk of disposability affect workers, agents, and bosses differently. | Cold trader, Guilder, hired gun, and criminal are not synonyms. A role proves neither greed nor free choice. |
| Outcasts, fallen houses, hired fighters | Outcast groupings include ex-members, clanless people, expelled workers, nobles asserting contested claims, cultists, criminals, and hired fighters. | Loss of recognized status, chosen reinvention, contested identity, patrons, and contract terms. | Outcast is a social/legal position, not a personality or shared culture. Retain a more specific origin when known. |
| Ironhead Squat Prospectors | Halls of the Ancients and the Core Rulebook present Necromundan Squat/Kin prospecting communities with long local history, mining, charters, ancestral memory, and specialized equipment. | Charter obligations, kin/clan authority, prospecting, claims, technical craft, and inherited knowledge. | Do not write them as generic fantasy dwarfs. Keep Necromundan Ironheads distinct from other Kin unless the campaign connects them. |
| Ash Waste Nomads and Duster clans | Sources distinguish Ash Waste tribes from hive Houses; they describe environmental adaptation, local customs, mobility, trade/raiding, and contested accounts of origins. | Routes, water, shelter, weather, animal partners, kin, and how hivers label outsiders. Place and tribe matter. | Do not assume all wasteland people are Ash Waste Nomads, share one origin, or are biologically nonhuman. Preserve incompatible accounts as accounts. |
| Scavvies, mutants, abhumans | Sources distinguish local mutation, recognized abhuman strains, engineered lineages, and socially excluded people; labels vary across editions. | Body, concealment, community, stigma, survival practices, and who applies a label. | Mutant is not a synonym for abhuman, criminal, Chaos worshipper, or monster. Use the exact lineage and source label; do not infer cognition from body. |
| Cults and corrupted gangs | Book of Ruin separates cult origins, doctrines, recruitment paths, fighter roles, and degrees of awareness. Book of Judgement also shows cult/criminal activity entangled with ordinary work and coercion. | Ask what the character believes, knows, is told, or is forced to do. | Gang-level cult affiliation does not mean each fighter knows its origin, patron, destiny, or full identity. Never reveal a secret through narrator omniscience. |
| Beasts, pets, machine companions | The Core Rulebook presents distinct Exotic Beasts, including mysterious Caryatids, companion creatures, cybernetic/engineered beings, and highly learnable giant rats. Some accompanying objects, such as servo-skulls, are explicitly not fighters. | First establish animal, engineered organism, cybernetic animal, autonomous construct, or non-sentient marker. Then use only supported senses, learning, bonds, needs, controls, and memory continuity. | Pet is not shorthand for “human thoughts” or “no thoughts.” Do not assign fighter memories to a rules object explicitly described as a marker. Bonds need rules/lore or authored support. |
| Wyrds and psykers | Core Rulebook and Book of Judgement distinguish sanctioned, unsanctioned, trafficked, and cult-associated psykers; Book of Ruin has faction-specific wyrd roles. | The institution that trains, fears, exploits, protects, or hunts a psyker; the difference between discipline, status, and ability. | A Psyker tag is not evidence of a vision, warp perception during this event, consent, control, or belief. Do not merge all wyrds into one “mystic” voice. |
| Spyrers, noble heirs, specialist parties | Sources include fighters whose participation is shaped by noble status, specialized equipment, campaign structures, or asymmetric recruitment. | Sponsor, initiation, obligation, sport, reputation, and experience entering lower hive strata. | Noble birth is not a uniform experience; a rules role does not tell us private motive. |

These patterns are contextual, not exhaustive. For a new gang, creature, or fighter type, record (a) source claims, (b) which members those claims apply to, (c) what remains rumor or disputed, and (d) which tags/writer cues are safe. Never encode an entire faction's lore as a universal voice string.

House slogans, faction doctrines, and the Imperial viewpoint can be beliefs *about* a group rather than objective truths about its members. Write the character from their position; when using an outsider's label, mark whose label it is.

### Wider 40k identities

The system must support identities beyond the most common underhive human. Treat the following as starting lenses and always branch by subculture, individual knowledge, and campaign context:

- **Humans and abhumans:** differentiate ordinary human upbringing from strains such as Ogryn, Ratling, and Squat/Kin, plus locally recognized or stigmatized mutation. Physiology and social treatment may affect experience; intelligence, courage, humor, faith, loyalty, and preferences remain individual. Necromunda's gene-crafted Goliaths, mutants, and cult hybrids should not be flattened into a generic “abhuman” category.
- **Adeptus Mechanicus and other Imperial institutions:** separate lay belief, priestly doctrine, trained technical method, and actual machine cognition. Imperial machine-spirit language may be theology, folk metaphor, or a being's real experience; choose only what its speaker knows. A Skitarius, tech-adept, servitor, and ordinary worker near machinery are not the same perspective.
- **Servitors, automata, machine minds, and machine-bodied people:** first establish whether there is a continuing person, partial memory, narrow task cognition, independent artificial personhood, or only an operator's attribution. Track sensors, permitted action, memory continuity, communication, directives, maintenance, and autonomy only when supported. “Robot” is not a single mental profile; Imperial servitorization, Kin Ironkin personhood, T'au drones, Necron constructs, and Aeldari spirit constructs differ profoundly.
- **Orks and related greenskins:** distinguish Ork, Gretchin, and other individuals, plus mob/klan/crew context and their own role. Use social standing, rivalry, strength, craft, danger, and shared purposes as possible lenses without making every thought a joke or every choice an urge to fight. Do not import human age/class assumptions where local roles provide different meanings.
- **Aeldari:** identify Asuryani/Craftworld, Drukhari, Harlequin, Corsair, Ynnari, or other actual affiliation before choosing customs. Long life, paths, soul peril, status, kin, performance, survival, and factional obligations may matter differently. No generic “ancient and elegant” diction; do not assign foresight or psychic knowledge without evidence.
- **T'au, Kroot, and other xenos:** record species and polity separately (e.g. sept, caste/social role where known, mercenary or client relationship, kin-band). Translate unfamiliar concepts carefully; do not default to human family, money, religion, or individualism. Do not claim a person believes a doctrine simply because an empire promotes it.
- **Tyranid organisms, Genestealer cults, and Malstrain:** distinguish animal/organism behavior, synaptic or other control where established, hybrid lineage, cult socialization, and individual awareness. Hidden origin or connection is not automatically conscious to a fighter. A Beast/Pet rules label supports an animal perspective only to the degree the creature's cognition warrants.
- **Chaos and other religious/ideological identities:** doctrine, patron, cult, coerced service, and personal conviction are distinct. Do not add daemonic perception, possession, revelation, or secret motives without a source.
- **Psykers and warp-sensitive beings:** the rules designation establishes a game-relevant capacity, not what the person senses in an ordinary moment. Separate sanctioned training, unsanctioned status, discipline, stigma, fear, chosen use, and actual psychic event. Never invent a vision or warp contact to explain mundane campaign changes.
- **Pets, exotic beasts, and bonded organisms:** determine species/model and known training relation. Write learned cues, sensory salience, threat, territory, hunger, pain/comfort, and handler proximity within the creature's likely cognition. Do not turn the animal into a human in costume or use its rules bond to assert affection or grief absent evidence.

These categories are not exhaustive; the tag schema is deliberately open. For any unlisted lineage or faction, research that specific identity and derive only the equivalent lenses: embodiment, social organization, institution, work, role, knowledge, and rules-defined constraints.

## Rules-derived information

Necromunda fighter cards and campaign rules can provide structured evidence, especially role/type, skill sets, special rules, equipment, costs, recruitment/access, and advancement state. Use them as bounded predicates:

- A **role/class** can establish current roster function and sometimes campaign responsibility; it does not establish age, experience before recruitment, personality, or rank beyond the exact rule label.
- A **skill or special rule** can establish a capability or constraint when the rules say so. It does not prove the fighter used that capability in a specific battle or feels a particular way about it.
- **Equipment** establishes recorded possession, not deployment, use, expertise, ownership sentiment, or a named action.
- A **Pet/handler or bonded rule** establishes only the relationship/mechanics written there; affection, communication, and shared memories need separate support.
- A **Psyker, outlaw, captured, or other rules keyword** can inform social risk and available options. It does not fill in a character's knowledge or subjective reaction.
- **Characteristics** may inform cautious embodied phrasing at most. Never translate a numerical profile into an IQ diagnosis, emotion, morality, reflexive behavior, or exact sensory capacity unless the rules/lore explicitly support it.
- If sources disagree, use the project's authority hierarchy and preserve raw source values. Never make a writer-generated tag adjudicate a rules question.

Maintain a tag registry with `tag_id`, display label, family, definition, allowed source types, confidence/provenance, and optional prompt guidance. Keep source value and normalized value together. Avoid a closed taxonomy of named species: unknown and custom values must work without code changes. Version the registry and preserve the rulebook/FAQ edition or source locator used, because rules and fighter categories change over time.

## Writer context packet

Build a compact per-memory packet rather than passing every tag verbatim:

```text
Known being/body: [supported values or unknown]
Known social/institutional context: [specific values]
Current role and work: [raw rules label + authored occupation if known]
Relevant personal facts: [one or two authored/repeated facts with source]
Relevant capability/constraint: [only if this event touches it]
Voice cue: [optional, supported]
Knowledge boundary: [what this character did not witness or cannot know]
Do not assume: [the most likely stereotype or unsupported detail]
```

For each observation/reflection ask:

1. What part of the recorded event reaches this character, and how?
2. What is salient to this particular body, work, role, community, or relationship?
3. What established words, units, rituals, metaphors, or social terms would this character use?
4. What remains unknown to the character and to the campaign record?
5. Does the sentence accidentally convert a rules label or stereotype into a fact?

Use one or two context dimensions at a time. Let a personality emerge across many memories rather than making every paragraph perform every identity. The same character can use technical vocabulary while afraid, or formal duty language while doubting the institution.

## Memory, reflection, and Mind rules

- **Observation:** one event, its factual evidence, the character's possible awareness, and one plausible personal meaning. Preserve temporal limits and source citations.
- **Reflection:** synthesize only cited active memories. Tags help interpret a pattern but are not evidence of the pattern. Do not add a new backstory fact, diagnosis, secret, or campaign event.
- **Current Mind:** summarize present concerns using the existing retrieval and salience rules. Identity may alter phrasing and explain why a topic is relevant, but it does not increase importance or suppress a memory. Any future identity-aware retrieval weighting must be separately specified and tested.
- **Dead/withdrawn/absent entities:** use existing lifecycle policy. Do not attribute current thoughts to a dead fighter, or infer death/retirement from disappearance.
- **Provenance:** generated language remains inference. Keep mechanical evidence separate, and retain the event/memory links. A writer may say “I fear” only as diegetic interpretive prose; the app must not store that as a measured psychological fact.

## Implementation plan

1. Add an extensible authored identity record and provenance/source locator; do not overload `fighter.type` or rules fields.
2. Normalize current roster and rule labels into role/function tags with raw labels retained. Add mappings conservatively and maintain a versioned Necromunda label catalog.
3. Assemble the compact writer packet in one place and pass it to observation, reflection, and Mind prose. Keep numerical story-engine inputs unchanged.
4. Create small contrast examples from the same event across materially different identities and across different roles within one faction. Review factual parity, knowledge boundaries, and stereotype leakage.
5. Expand phrase families or prompt instructions only after those examples pass editorial review. The current deterministic writer will require deliberate wording coverage; metadata alone cannot make unseen combinations sound distinct.

## References and source limits

Primary project references used here are the supplied Necromunda Core Rulebook (2023), *House of Artifice*, *House of Iron*, *The Book of Judgement*, *The Book of Ruin*, and *Halls of the Ancients*. The rulebook categories/types distinction, hive structure, psykers, exotic-beast examples, and Ironhead Squat Prospectors were checked against the Core Rulebook; faction context against the relevant House books; Enforcers, Guild/criminal networks and psyker trafficking against *The Book of Judgement*; cult distinctions against *The Book of Ruin*; and Ironhead clans against *Halls of the Ancients*. The supplied set does not include a House of Blades book, so Escher-specific prompts are cross-referenced below and remain subject to campaign canon. These books span rules versions; preserve the exact source context and prefer the campaign's current roster/rules source for mechanics. Authority and canon hierarchy remain in `AGENTS.md`.

Secondary Necromunda references used to broaden the faction and outcast survey:

- [Necromunda (planet)](https://wh40k.lexicanum.com/wiki/Araneus_Prime) summarizes hive society, feudal relations, and the breadth of what “gang” can mean.
- [Necromunda (game)](https://wh40k.lexicanum.com/wiki/Necromunda_%28game%29) indexes current and historical gang families and roles; it is a discovery aid, not rules authority.
- [Ash Waste Nomads](https://wh40k.lexicanum.com/wiki/Ash_Waste_Nomad) and [Necromundan Nomads](https://wh40k.lexicanum.com/wiki/Necromundan_Nomads) show distinct and edition-sensitive accounts, including uncertainty over origins.
- [House Goliath](https://wh40k.lexicanum.com/wiki/House_Goliath), [House Orlock](https://wh40k.lexicanum.com/wiki/House_Orlock), [House Van Saar](https://wh40k.lexicanum.com/wiki/House_Van_Saar), [House Delaque](https://wh40k.lexicanum.com/wiki/House_Delaque), [House Escher](https://wh40k.lexicanum.com/wiki/House_Escher), and [House Cawdor](https://wh40k.lexicanum.com/wiki/Clan_Cawdor) provide faction-specific topics and source bibliographies.
- [Outcasts](https://wh40k.lexicanum.com/wiki/Outcast_%28Necromunda%29), [Ironhead Squats](https://wh40k.lexicanum.com/wiki/Ironhead_Squat), [Corpse Grinder Cults](https://wh40k.lexicanum.com/wiki/Slaughter_Cult), and [Malstrain Genestealers](https://wh40k.lexicanum.com/wiki/Malstrain_Genestealers) help map non-House identities and distinctions between group labels.
- The [Warhammer 40k Wiki's Necromunda game](https://warhammer40k.fandom.com/wiki/Necromunda_%28Game%29) and [Necromunda planet](https://warhammer40k.fandom.com/wiki/Necromunda_%28Planet%29) pages were consulted as broad secondary indexes, especially for legacy groups and vocabulary.

Lexicanum and Fandom are secondary references, not primary rules sources; they can mix editions and repeat claims of unequal certainty. Cross-check the supplied PDFs, campaign canon, and current rule source. The project's NecroRAW URL remains its rules authority. The v0.7 director stores authored identity context locally, retains revisions, and exposes the full packet to prose generation. See [WRITING_DIRECTOR.md](WRITING_DIRECTOR.md) for active wording coverage, editor/API behavior and remaining limits.
