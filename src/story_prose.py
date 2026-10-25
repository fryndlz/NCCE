"""Narrative fact extraction and identity profiles for the event-driven chronicle.

The production writer is llm_writer.py. This module retains event evidence,
voice-profile and legacy phrase helpers used by offline compatibility checks;
its phrase helpers are not used as finished production prose.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import re
import writing_director as director


GENERATOR_VERSION = "ncce-prose-0.6.1"
C9 = "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]"


def _text(value):
    return str(value).strip() if value is not None else ""


def _short(name):
    value = _text(name)
    return "C-NINE" if "C-NINE" in value or "PROSPECT DETAIL C-9" in value else value or "an unnamed gang"


def _is_c9(gang):
    return _short(gang.get("name") or gang.get("gang_name")) == "C-NINE"


def _choose(fighter, key, variants):
    seed = f"{fighter.get('gang_id', '')}/{fighter.get('name', '')}/{key}"
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16) % len(variants)
    return variants[index]


def _number(value, default=0):
    try:
        return float(_text(value).replace('"', "").rstrip("+"))
    except (TypeError, ValueError):
        return default


def _mechanics(fighter):
    result = {}
    for key in ("mechanics_json", "mechanical_json", "mechanics", "fields"):
        source = fighter.get(key)
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except (ValueError, TypeError):
                source = {}
        if isinstance(source, dict):
            result.update(source)
    result.update({k: v for k, v in fighter.items() if k in ("M", "WS", "BS", "S", "T", "W", "I", "A", "Ld", "Cl", "Wil", "Int")})
    return result


def _words(value):
    if isinstance(value, list):
        return [_text(x) for x in value if _text(x)]
    return [x.strip() for x in re.split(r"[;\n]+", _text(value)) if x.strip()]


def _items(value):
    # Weapon stat blocks contain commas and semicolons; remove the blocks before
    # splitting so a full profile cannot leak into the narrative paragraph.
    source = re.sub(r"\[[^\]]*\]", "", _text(value))
    source = re.sub(r"\([^)]*(?:Ammo|Acc|Str|AP|Damage|Range)[^)]*\)", "", source, flags=re.I)
    return [x.strip(" ,") for x in re.split(r"[;\n]+", source) if x.strip(" ,")][:5]


def _join(values, limit=4):
    names = [str(x) for x in values if x][:limit]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _list(value):
    if isinstance(value, dict):
        return list(value.values())
    return list(value or [])


def _payload(event):
    value = event.get("payload", event.get("payload_json", {}))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = {}
    return value if isinstance(value, dict) else {}


def _subjects(event):
    value = event.get("subjects", [])
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = []
    return value or []


def _gang_for(fighter, gang):
    return {**gang, "name": gang.get("name") or fighter.get("gang_name") or "the gang"}


def voice_profile(fighter, gang):
    """Return an explainable voice profile, never a psychological diagnosis."""
    gang = _gang_for(fighter, gang)
    mechanics = _mechanics(fighter)
    authored = _text(fighter.get("backstory")) if "authored" in _text(fighter.get("backstory_source")).lower() else ""
    hints = (authored + " " + _text(fighter.get("type"))).lower()
    cls = _text(fighter.get("class")).lower()
    faction = _text(gang.get("gang_type")).lower()
    traits, evidence = [], []
    if _is_c9(gang):
        register = "crew"
        evidence.append("C-NINE authored industrial and crew conventions")
    elif "van saar" in faction:
        register = "technical"
        evidence.append("House Van Saar affiliation")
    elif "enforcer" in faction or "palanite" in faction:
        register = "precinct"
        evidence.append("Palanite/Enforcer affiliation")
    elif "squat" in faction or "ironhead" in faction:
        register = "charter"
        evidence.append("Ironhead prospecting affiliation")
    elif "orlock" in faction:
        register = "road"
        evidence.append("House Orlock affiliation")
    else:
        register = "underhive"
        evidence.append("Gang role and campaign record")
    profession = "fighter"
    if "exotic beast" in cls or any(t in hints for t in ("cyberachnid", "sumpkroc", "phyrr cat", "tunnel vermin", "predator gamma", "incident organism")):
        profession, register = "sensory", "sensory"
        traits.append("sensory")
        evidence.append("Beast/organism type or authored designation")
    elif any(t in hints for t in ("maintenance fitter", "workshop", "repair", "machinery", "munitions")):
        profession = "workshop"
        traits.append("practical")
        evidence.append("Authored maintenance, repair or equipment vocabulary")
    elif any(t in hints for t in ("chirurgeon", "medicae", "medical officer", "rogue doc", "surgery")):
        profession = "medical"
        traits.append("clinical")
        evidence.append("Medical role or authored personnel record")
    elif any(t in hints for t in ("surveyor", "survey", "prospect", "drill")):
        profession = "survey"
        traits.append("measured")
        evidence.append("Survey or prospecting role")
    elif any(t in hints for t in ("psyker", "wyrd", "who heard", "it that spoke")):
        profession = "attentive"
        traits.append("inward")
        evidence.append("Psyker or authored signal/listening role")
    if cls in ("leader", "champion"):
        traits.append("responsible")
        evidence.append(f"Recorded class: {fighter.get('class')}")
    if cls in ("juve", "prospect"):
        traits.append("aspiring")
        evidence.append(f"Recorded class: {fighter.get('class')}")
    if _number(mechanics.get("T")) >= 4 or _number(mechanics.get("W")) >= 2:
        traits.append("enduring")
        evidence.append("Toughness/Wounds suggests experience of physical endurance")
    if _number(mechanics.get("S")) >= 4:
        traits.append("physical")
        evidence.append("Strength suggests a physically direct frame of reference")
    if 0 < _number(mechanics.get("Int")) <= 5:
        traits.append("analytical")
        evidence.append("Intelligence profile supports an analytical inflection")
    if 0 < _number(mechanics.get("Cl")) <= 5:
        traits.append("composed")
        evidence.append("Cool profile supports a measured inflection")
    if 0 < _number(mechanics.get("Wil")) <= 5:
        traits.append("resolute")
        evidence.append("Willpower profile supports a persistent inflection")
    if _number(fighter.get("kills")) >= 5:
        traits.append("blooded")
        evidence.append("At least five recorded kills")
    packet = director.identity_context(fighter, gang, {'register':register})
    key = register + ':' + profession + ':' + ':'.join(traits) + json.dumps(packet, sort_keys=True)
    return {"id": hashlib.sha256(key.encode()).hexdigest()[:12], "name": f"{register} / {profession}",
            "register": register, "profession": profession, "traits": list(dict.fromkeys(traits)),
            "tags":packet['tags'], "identity":packet['identity'], 'writer_context':packet, "evidence": evidence}


def _voice(fighter, gang, topic, variants, specialized=None):
    profile = voice_profile(fighter, gang)
    if specialized:
        for key in (profile["profession"], *profile["traits"], profile["register"]):
            if key in specialized:
                return _choose(fighter, topic, specialized[key])
    return _choose(fighter, topic, variants)


def _advance(fighter, gang, advancement):
    a = advancement.lower()
    if "cool" in a:
        return _voice(fighter, gang, "cool", ["The noise still reaches me. It no longer chooses my next move.", "I can feel the urge to flinch and leave it unanswered. That small distance belongs to me."], {"workshop": ["My hands stay useful when everything around them begins to shake. A steady hand saves more than wasted parts."], "technical": ["Panic is interference. I am getting better at keeping it out of the working channel."], "precinct": ["I can hold the line inside my own head a little longer. The order comes before the fear now."]})
    if "willpower" in a or "wil" == a:
        return _voice(fighter, gang, "willpower", ["There are things I can refuse now that once would have driven me back. I mean to keep that ground.", "I have learned to stay with a decision after it begins to hurt."], {"crew": ["The work presses back. I have learned to press longer."], "technical": ["I know the difference between a warning and a command. Not every alarm gets to stop me."]})
    if "intelligence" in a or "int" == a:
        return _voice(fighter, gang, "intelligence", ["I see another way through the problem now. I would rather use that than pay for the old answer again.", "A pattern I used to miss has become difficult to ignore. I am learning to ask what the obvious answer conceals."], {"workshop": ["I can trace the fault a little further before I have to put a tool to it. Fewer good parts need to suffer for a bad guess."]})
    if "toughness" in a:
        return "I have a little more left when the hurt tells me to stop. I still have to choose what is worth spending it on."
    if "strength" in a:
        return "A load that used to take everything from me leaves something in reserve now. I notice the difference before anyone says a word."
    if "ballistic" in a:
        return "I trust the small correction before the shot more than I used to. There is less room between intention and where it lands."
    if "weapon skill" in a:
        return "Close work feels less hurried. I am learning where to put my weight and when to let the other fighter waste theirs."
    if "movement" in a or "initiative" in a:
        return "I find the next opening sooner. A little less hesitation can be the whole distance between getting through and being caught."
    if "leadership" in a:
        return "I am learning which words people can carry into danger. An order has to survive the sound of the guns."
    if "wounds" in a:
        return "The body has more to give before it fails me. I will not mistake the extra margin for a promise."
    if "attacks" in a:
        return "I can keep the pressure on for another beat. In close quarters, another beat can change who gets to stand back."
    if "specialist" in a or "champion" in a:
        return "They have changed the name of my place in the gang. I expect the work attached to it to change as well."
    skill = re.sub(r"^(skills?|advancements?)\s*:\s*", "", advancement, flags=re.I).strip()
    if skill:
        return f"{skill} is becoming something I can rely on, rather than something I have only been told. I want it there when habit is all I have time for."
    return "What I have learned is beginning to hold under pressure. I want to make it part of how I work."


def observation_text(fighter, gang, event_type, payload, context=None):
    """Write one event memory in first person, with mechanical evidence elsewhere."""
    context = context or {}
    payload = payload or {}
    gang = _gang_for(fighter, gang)
    kind = _text(event_type).lower()
    field = _text(payload.get("field"))
    before, after = payload.get("before"), payload.get("after")
    detail = _text(payload.get("detail") or payload.get("content") or payload.get("value"))
    value = _text(after if "after" in payload else detail)
    terminal = _text(fighter.get("status")).lower() in ("killed", "dead")
    if (kind in ("status", "fighter_status_changed") or field == "Status") and value.lower() in ("killed", "dead"):
        return f"Personnel entry closed: {fighter.get('name', 'the fighter')} is recorded dead. Their earlier service remains in the account; no further current thoughts are attributed to them."
    if terminal and kind in ("baseline", "fighter_baseline", "baseline_state"):
        return f"Historical personnel return: {fighter.get('name', 'the fighter')} held a place in {_short(gang['name'])}. The recorded service remains after the living place has closed."
    if voice_profile(fighter, gang)["register"] == "sensory":
        if "effect" in kind or "injur" in kind or field == "Effects":
            return "I carry the hurt with me. Each movement tells me where it is; I keep what strength remains close."
        if "kill" in kind or field == "Kills":
            return "I know the difference between movement and stillness. There is more stillness behind me now."
        if "status" in kind or field == "Status":
            return "I am held away from the others. I listen for their nearness and test what the body will allow."
        return "I know my own weight, the reach of my limbs, and the presence of the others. Something in that pattern has changed."
    if kind in ("advancement", "fighter_advancement_changed", "fighter_skills_changed", "skill") or field in ("Advancements", "Skills"):
        old = set(_words(before))
        advancement = after if "after" in payload else detail or fighter.get("advancements")
        new = [x for x in _words(advancement) if x not in old]
        if before and not new and after != before:
            return "They have revised the skills entered against my name. I will have to show what still holds when the next demand comes."
        return _advance(fighter, gang, _join(new) or value)
    if kind in ("effect", "fighter_effects_changed", "injury", "critical_injury") or field == "Effects":
        raw_effects = payload.get("after") if "after" in payload else detail or fighter.get("effects")
        text = _text(raw_effects).lower()
        if "critical" in text:
            return _voice(fighter, gang, "critical", ["They have marked my condition critical. I have become a thing that must be kept alive, and I do not like how little of that work is mine.", "I have come close enough to the end that the word itself feels different. For now, being here is work enough."], {"workshop": ["I know how to keep a damaged assembly in service. It is less comfortable being the assembly. My hands can wait; first the rest of me has to hold."], "medical": ["I know what the word critical allows them to leave unsaid. Knowing the procedure does not make this body less mine."], "enduring": ["I can take punishment. I have built too much of myself around knowing that; now the body has found a limit I cannot simply lean through."], "physical": ["There is nothing here I can lift, break, or force out of the way. Keeping alive has become a job for hands other than mine."], "analytical": ["I understand the word critical well enough to know how much it leaves undecided. For once, understanding has not put the next step in my hands."], "crew": ["Condition: critical. I can hear the kind of language they use for a shaft that may not hold. I am still inside this one."]})
        if "humiliat" in text:
            return "The injury has a second edge: someone saw me fail. I keep reaching for a chance to make that the earlier version of the story."
        if "bitter enmity" in text:
            return "There is an enemy in this hurt. Even where the record leaves the name blank, the anger has found somewhere to wait."
        if "scar" in text:
            return _voice(fighter, gang, "scars", ["The marks will meet people before I do now. I will have to decide what I let them say for me.", "There is no hiding what the campaign has left on me. Let them look; I still have work to do."], {"precinct": ["The marks are visible evidence now. They will be read before I have the chance to give my own account."]})
        if "eye" in text:
            return "I keep measuring distances against what the eye used to tell me. Trust will have to be rebuilt, one careful judgment at a time."
        if "hand" in text:
            return _voice(fighter, gang, "hand", ["The hand does not answer as it used to. I notice it in every small task before I can afford to forget it in a large one."], {"workshop": ["The injured hand turns familiar work strange. I know what these fingers should do; I will have to teach them another way."]})
        if "hobbled" in text or "spinal" in text or "enfeebled" in text or "head injury" in text or "deaf" in text:
            return _voice(fighter, gang, "lasting-injury", ["The hurt has settled into something I will have to work around. What used to be automatic now asks for thought.", "I cannot bargain the old body back. I can learn the limits of this one before they catch me unprepared."], {"workshop": ["The tolerances have changed. Pretending otherwise is how a damaged thing fails completely; I will learn what still works."], "enduring": ["I am used to carrying a hurt until the job is done. This one means learning how to carry it into the next job as well."], "physical": ["I keep judging a task by what I could put behind it before. I need to learn this body's answer before I commit the rest of me."], "analytical": ["The injury has changed the terms of familiar tasks. I need a new way through them, rather than a better argument with the old one."]})
        if not text or text in ("none", "no effects", "no injuries"):
            return "The old entry has been cleared. I notice what no longer hurts, even if I am slow to trust the silence."
        return "There is another condition to remember when I ask the body to do its work. I will learn its shape before it surprises me."
    if kind in ("status", "fighter_status_changed") or field == "Status":
        status = (value or _text(fighter.get("status"))).lower()
        if "captur" in status:
            return "My place is somewhere beyond my own gang's reach. I am holding on to the thought that reach can change."
        if "retir" in status:
            return "They have taken my name off the fighting line. It is a strange thing, to remain here and become part of what the others remember."
        if "recover" in status or "convalesc" in status:
            return _voice(fighter, gang, "recovery", ["I have been stood down while the others keep moving. Rest has begun to feel like another duty I have not yet learned to do.", "I am recovering. It sounds like waiting when someone else says it; from inside, it is work without an audience."], {"workshop": ["The workshop goes on without my hands. I need the repair to hold this time, even when the broken thing is me."], "enduring": ["I know how to keep going. Learning when to stop has proved the less familiar work."], "physical": ["I want a load I can put my back into, something that answers effort plainly. Recovery asks for patience instead, and I have less practice with that."], "responsible": ["The others still have decisions to make while I am held back. I have to let the recovery do its work without turning my absence into another order."], "crew": ["I am off the working line. The Crew continues around the gap, and I am learning how much I dislike being the gap."], "precinct": ["I am off duty while the precinct carries on without me. I want my strength back before the next call comes."]})
        if "active" in status and ("recover" in _text(before).lower() or "convalesc" in _text(before).lower()):
            return _voice(fighter, gang, "returned", ["I have been cleared to return. I want to learn what feels familiar before the next demand leaves me no time to ask.", "My place is open again. I will take it carefully; being available is not the same as having forgotten the hurt."], {"workshop": ["Back in service. I will test the repair under a sensible load before I trust it with everything."]})
        if "active" in status and "captur" in _text(before).lower():
            return "I am back within the reach of my own gang. For now, that is enough to keep returning to."
        return "The place assigned to me has changed. I am learning what that asks of me before I call it ordinary."
    if "xp" in kind or field == "XP":
        if _number(after) < _number(before) and context.get("advancement"):
            return _advance(fighter, gang, _text(context["advancement"]))
        if after is not None and _number(after) < _number(before):
            return "The account of my experience has been revised. What I can actually do will still have to answer for itself."
        return _voice(fighter, gang, "experience", ["Some things take less of my attention than they did. I am learning which part of survival can become habit.", "I have a little more to draw on than before. I mean to use it before I have to pay for the same lesson twice.", "I am beginning to recognize the moments that used to pass too quickly. Recognition is useful only if I do something with it."], {"workshop": ["A little less guesswork, a little less wasted motion. Good work leaves something behind in the hands."], "aspiring": ["The gap between me and the veterans has a different shape now. I am learning where I can close it through work, rather than impatience."], "physical": ["I am learning where to put the effort. Strength does more when it arrives at the right place."], "analytical": ["The separate lessons are beginning to make a pattern. I want to recognize the next part before I have to learn it the expensive way."], "composed": ["I can leave a little more room between the alarm and my answer. Experience is beginning to make that room useful."], "technical": ["The experience is starting to become a pattern I can use. Next time, I want the answer before the fault has finished declaring itself."], "precinct": ["Experience gives an order weight that a badge cannot supply. I am learning what it costs to speak with that weight."], "charter": ["Another lesson carried back. I would rather keep its worth in my head than have to pay for it again."]})
    if "kills" in kind or field == "Kills" or kind == "combat_record":
        if kind == "combat_record":
            tally = int(_number(payload.get("kills", payload.get("Kills", detail or fighter.get("kills")))))
            return _voice(fighter, gang, "combat-record", [f"There {'is one death' if tally == 1 else f'are {tally} deaths'} credited to my name. The others can make a reputation of the tally; I am the one who has to keep carrying the name.", "The number beside my name has become part of how the gang sees me. I have to decide how much of myself to let it describe."], {"crew": ["The violence credited to me is part of the return. The Crew still has work for these hands, and I am learning how to carry both accounts."]})
        if after is not None and before is not None and _number(after) < _number(before):
            return "The tally beside my name has been corrected. A changed entry does not tell the whole story of what a fighter carries."
        delta = _number(after) - _number(before) if before is not None else _number(after or fighter.get("kills"))
        noun = "Another death has" if delta == 1 else "More deaths have"
        precinct_kill = "Someone is dead because of me. The badge cannot make that easier to carry." if delta == 1 else f"{int(delta)} people are dead because of me. The badge cannot make that easier to carry."
        return _voice(fighter, gang, "kills", [f"{noun} been set against my name. I can count them more easily than I can decide what the number makes me.", f"{noun} entered my account. The others may read a reputation there; I still have to live inside the name."], {"crew": [f"{noun} been entered against my name. The Crew has work for the living, and I am still among them."], "precinct": [precinct_kill], "technical": [f"{noun} been credited to me. A tally preserves a result and discards almost everything it cost."]})
    if "weapons" in kind or "wargear" in kind or field in ("Weapons", "Wargear"):
        added = [x for x in _items(after) if x not in _items(before)]
        removed = [x for x in _items(before) if x not in _items(after)]
        if added:
            names = _join(added, 2)
            return _voice(fighter, gang, "equipment-" + names, [f"I have {names} in my kit now. I want its weight and limits familiar before I have to trust it in a hurry.", f"{names} changes what I can ask of my own hands. I am already thinking about the habits that will need to change with it."], {"workshop": [f"{names} is part of my working kit now. New equipment earns trust by doing its job; I know better than to grant it all at once."], "physical": [f"I have {names} to carry now. I want to know where its weight sits before I need the rest of my strength for something else."], "analytical": [f"{names} gives me another set of choices. I want to understand the limits as carefully as the possibilities."], "technical": [f"I have {names} to account for now. Understanding its limits matters as much as finding out what it can do."], "precinct": [f"{names} is entered against my name. Possession is the easy part; I have to make it answer properly when called upon."]})
        if removed:
            return f"{_join(removed, 2)} is no longer in my kit. I keep reaching for the old arrangement in my head; that will have to change before it costs me."
        return "The arrangement of my kit has changed. I need to know what is at hand without stopping to look."
    if field in ("Class", "Type") or "promot" in kind:
        role = value or _text(fighter.get("class")) or _text(fighter.get("type"))
        return _voice(fighter, gang, "role-" + role, [f"They call me {role} now. A changed title draws different eyes; I will find out what they expect to see.", f"{role}. I have a new place in the gang's account, and I mean to make it a place they can rely on."], {"crew": [f"My designation is {role} now. The work did not pause for the amendment, but the load assigned to me has a different shape."], "precinct": [f"They have made me {role}. The others will look to me when a decision has to be made; I had better be worth listening to."]})
    if "recruit" in kind:
        return _voice(fighter, gang, "recruited", [f"My name is entered with {_short(gang['name'])} now. I have a place to earn, and people who will notice how I earn it.", "I have been given a place among them. Before long, they will have more than a name to judge me by."], {"crew": ["My name has been entered on the working detail. There is a place for my hands; belonging will have to be measured in more than ink."]})
    if "unlisted" in kind:
        return "My name is missing from the current roll. The blank does not explain where I went or why; it only marks the space I occupied."
    if kind == "gangmate_captured":
        person = _text(context.get("subject_name") or payload.get("subject_name") or payload.get("fighter_name")) or "one of our own"
        return f"{person} is entered as captive. I do not know what reaches them from us now; I keep thinking about what it would take to bring them within our reach again."
    if kind in ("social_loss", "shared_loss", "gangmate_loss", "comrade_death"):
        person = _text(context.get("subject_name") or payload.get("subject_name") or payload.get("fighter_name") or payload.get("name")) or "one of our own"
        return _voice(fighter, gang, "loss-" + person, [f"{person} is missing from the place I expect to find them. The gang can carry on; that does not make the gap smaller.", f"I keep including {person} in the shape of what comes next. I have to remember the absence before it surprises me."], {"crew": [f"{person}'s place is still part of the work, even when the hands are gone. The Crew has to carry the absence as well as the load."]})
    if "battle" in kind or kind in ("victory", "defeat", "draw"):
        battle = context.get("battle") or payload
        winner = battle.get("winner")
        territory = battle.get("territory")
        place = f" at {territory}" if territory else ""
        if winner and _short(winner) == _short(gang["name"]):
            return _voice(fighter, gang, "victory" + place, [f"We won{place}. I am proud of the gang. I still want to know what it cost us.", f"Our name came out ahead{place}. I want to enjoy that before I start worrying about what comes next."], {"crew": [f"The engagement{place} is entered in our favour. The work can proceed under that entry, though the cost still has to be carried."], "precinct": [f"We secured the ground{place}. A win is what the precinct came for; I still need to know whether the people here will be safer for it."]})
        if winner:
            return _voice(fighter, gang, "defeat" + place, [f"We lost{place}. I am angry. I do not want that anger choosing my next move.", f"Someone else took the ground from us{place}. I want to know what I missed before I call it bad luck."], {"crew": [f"The return{place} is unfavourable. We remain a working detail; the next allocation has to account for what this one cost."], "precinct": [f"We lost the ground{place}. I want to know what we missed before we call it bad luck."]})
        return f"No one won{place}. We left without the ground settled, and I do not know what we paid for that."
    if "territory" in kind:
        name = payload.get("territory") or context.get("territory") or "that ground"
        owner = payload.get("after_owner") or payload.get("territory_claimer")
        if owner and (_short(owner) == _short(gang["name"]) or _text(owner) == _text(gang.get("gang_id"))):
            return f"{name} is counted as ours now. A claim means another place our name must answer for."
        return f"The claim at {name} has changed. The district will ask different things of us there, and I am learning to think around the new boundary."
    if kind == "gang_alignment_changed" or field.lower() == "alignment":
        classification = value.lower()
        if "outlaw" in classification:
            return _voice(fighter, gang, "outlaw-classification", ["They have written outlaw against the gang's name. I am thinking about what other people will believe that permits them to do to us.", "Our name has crossed into the outlaw column. I have to learn which familiar arrangements still hold and which doors now answer differently."], {"precinct": ["They have called us outlaws. I know what the badge used to let me ask of people; I do not know who will answer now."], "crew": ["The detail is now classified as outlaw. The work remains before us; the permissions surrounding it have changed."]})
        if "law" in classification:
            return _voice(fighter, gang, "lawful-classification", ["The record now places the gang on the lawful side of its division. I am considering what that name will buy us, and what it will ask us to answer for.", "They have changed how our gang is classified. A cleaner entry may open a door, but someone still has to stand behind the name."], {"precinct": ["We are recognized as lawful again. That should make the badge mean something here. I will see whether anyone believes it when the next trouble starts."], "crew": ["Our classification has been amended to lawful. Another permission entered; another obligation for the detail to carry."]})
        return "The classification beside our gang's name has changed. I am thinking about how the district will read us now, and which old assumptions I should stop relying on."
    if field in ("M", "WS", "BS", "S", "T", "W", "I", "A", "Ld", "Cl", "Wil", "Int"):
        names = {"M": "Movement", "WS": "Weapon Skill", "BS": "Ballistic Skill", "S": "Strength", "T": "Toughness", "W": "Wounds", "I": "Initiative", "A": "Attacks", "Ld": "Leadership", "Cl": "Cool", "Wil": "Willpower", "Int": "Intelligence"}
        improved = _number(after) < _number(before) if field in ("WS", "BS", "I", "Ld", "Cl", "Wil", "Int") else _number(after) > _number(before)
        if before is None or improved:
            return _advance(fighter, gang, names[field])
        return "Something I used to count on is less certain now. I need to learn the changed limit before an old habit asks too much of it."
    if "reputation" in kind:
        return "The gang's name carries differently through the district now. I can feel how quickly other people's judgments become part of the ground beneath us."
    if "credits" in kind or "wealth" in kind:
        return "The gang's means have changed. I am thinking about which needs will be answered first, and which of us will be asked to wait."
    if kind in ("baseline", "fighter_baseline", "baseline_state"):
        cls = _text(fighter.get("class")).lower()
        if cls in ("juve", "prospect"):
            return _voice(fighter, gang, "baseline-young", ["There are veterans here whose names already mean something. Mine has room around it; I intend to fill that room with work they remember.", "I am still being measured against what I might become. I would like to give them something solid to measure."], {"technical": ["I am still junior enough that the tools are expected to outlast my judgment. I want to close that difference."]})
        if cls in ("leader", "champion"):
            return "People look toward my place when a choice has to be made. I am learning how much of the decision stays with me after the others move."
        return _voice(fighter, gang, "baseline", ["I know my place in this gang through the work expected of me. The campaign will decide how much more gets attached to my name.", "There is a space in the line that the others expect me to fill. I want to remain someone they can count on finding there."], {"workshop": ["I know the workshop by what can still be made useful. My place is among the things that keep the rest working."], "enduring": ["I can hold under a load. I want that to be something the others can rely on, without forgetting that even a sound body has its limit."], "physical": ["Give me something that needs moving and I know where to begin. The rest of my place here is still being worked out."], "analytical": ["I like to know what the next problem is made of before I commit to the answer. There is usually more than one way to pay for a mistake."], "crew": ["My name is one part of the working detail. What matters is whether the rest can depend on the work attached to it."]})
    return _voice(fighter, gang, "changed-" + kind + field, ["Something in the account of my place has changed. I am considering what it asks of me before the next demand arrives.", "The entry beside my name is different now. I have to make sense of it in the life that continues around the words."], {"crew": ["The return has been amended. I am still here to find out what the amendment means for the work."]})


def reflection_text(fighter, gang, memories, context=None):
    """Synthesize themes from supplied memories; the caller retains their IDs."""
    context = context or {}
    if _text(fighter.get("status")).lower() in ("killed", "dead"):
        return f"The closed personnel file retains the changes entered against {fighter.get('name', 'this fighter')}. Service, injury, and recorded experience remain part of the gang's history; the file attributes no present thoughts to the dead."
    material = []
    for memory in memories or []:
        tags = memory.get("tags", memory.get("tags_json", []))
        material.append(" ".join(tags) if isinstance(tags, list) else _text(tags))
        material.append(_text(memory.get("title")))
        material.append(_text(memory.get("event_type")))
        material.append(_text(memory.get("content")))
    words = " ".join(material).lower()
    hurt = any(x in words for x in ("injur", "critical", "recover", "convalesc", "scar", "wound"))
    growth = any(x in words for x in ("advance", "skill", "experience", "promotion", "learning", "xp"))
    loss = any(x in words for x in ("social_loss", "gangmate_loss", "death", "missing from the place", "killed"))
    kit = any(x in words for x in ("equipment", "weapon", "wargear", "my kit"))
    victory = "victory" in words or "in our favour" in words
    defeat = "defeat" in words or "against us" in words or "unfavourable" in words
    if hurt and growth:
        return _voice(fighter, gang, "reflection-hurt-growth", ["I am becoming more capable while learning how easily capability can be taken away. I want the lessons to outlast the damage.", "What I have learned and what I have suffered are beginning to shape the same habits. I need room for both if I am to keep moving."], {"workshop": ["I have spent years judging what can be repaired and put back to work. Now every new skill has to live alongside the reminder that I, too, can fail under load."], "crew": ["The work has taught me more and taken more from me. Both belong in the return; neither should be allowed to conceal the other."]})
    if loss:
        return _voice(fighter, gang, "reflection-loss", ["The gang is beginning to include absences as well as names. I carry those gaps into the choices I make for the ones still here.", "What we lose changes the shape of what remains. I am trying to remember without turning every next step into a repetition."], {"crew": ["The Crew is measured by what it carries together. The missing are becoming part of that load, though no allocation sheet has a useful column for them."]})
    if hurt:
        return _voice(fighter, gang, "reflection-hurt", ["The injury keeps returning in the small decisions: what I trust, what I avoid, what I will risk again. Surviving it is not the same work as learning to live with it.", "I used to think about the body when it failed. Now I am learning to think about it before I ask too much."], {"workshop": ["A repair changes how I handle the whole assembly. I ought to grant myself the care I would give a tool that everyone still needs."]})
    if victory and defeat:
        return "Winning and losing have begun to feel like changes in what the gang must carry, rather than endings. I want to remember that before the next result tells us who we are."
    if kit and growth:
        return "New equipment and better habits have to meet in the same pair of hands. Possession is quick; making the tool part of how I work takes longer."
    if growth:
        return _voice(fighter, gang, "reflection-growth", ["The small lessons are beginning to join up. I am less interested in looking experienced than in having the right habit left when thought runs out.", "I can see a difference between the fighter my name first described and the one doing the work now. I want that difference to be useful to the others."], {"technical": ["What looked like separate faults is becoming a pattern. Experience is worth keeping only when it changes the next decision."], "precinct": ["Rank can be issued. Judgment has to accumulate, and each new piece asks what I did with the last."]})
    if defeat:
        return "A defeat is beginning to ask more of me than anger can answer. I want something in the next choice to show that I have carried the right part of it forward."
    if victory:
        return "A victory can make the next risk look smaller than it is. I want to keep the result without borrowing certainty from it."
    return _voice(fighter, gang, "reflection-pattern", ["The separate entries are beginning to make a pattern. I want to understand what I am becoming before habit decides it for me.", "I keep returning to the same concerns by different routes. There is probably something in that worth listening to."], {"crew": ["Separate returns, the same working detail. I am beginning to see which burdens follow me from one allocation to the next."]})


def fighter_biography(fighter, gang):
    gang = _gang_for(fighter, gang)
    name, role = fighter.get("name", "This fighter"), fighter.get("type") or fighter.get("class") or "fighter"
    profile = voice_profile(fighter, gang)
    cls = _text(fighter.get("class")).lower()
    roles = {"leader": "Decisions gather at their place in the line; success gives the orders authority, and failure gives every order an afterlife.", "champion": "They occupy the uneasy ground between example and rival, watched by those below them and measured by those above.", "juve": "Their standing is still being made. Each useful act can become a claim to a different place in the gang.", "prospect": "Their future is conditional, carried forward one risk at a time.", "specialist": "The gang has begun to depend on a particular kind of usefulness, and that dependence gives them a place worth protecting.", "brute": "Others may describe them as an asset. Living beside an asset makes that description harder to maintain.", "hanger-on": "Their work sits beside the fighting line, close enough to share its dangers without owning its privileges."}
    first = f"{name} is recorded among {_short(gang['name'])} as a {role}. " + roles.get(cls, "Their place is made through the work the gang expects them to perform, and the expectation that they will still be there when needed.")
    traits = profile["traits"]
    second = []
    if "analytical" in traits or profile["register"] == "technical":
        second.append("A habit of examining the problem before committing to its answer would suit both their capabilities and the culture around them.")
    if "enduring" in traits:
        second.append("Their physical resilience gives them room to endure pressure; it offers no guarantee about what that pressure feels like from inside.")
    if "physical" in traits:
        second.append("Their strength makes direct solutions available, though the campaign may yet teach them which burdens are worth taking up.")
    kills = int(_number(fighter.get("kills")))
    if kills:
        second.append(f"The campaign ledger credits {kills} {'kill' if kills == 1 else 'kills'} to their name. It is enough for others to begin making a reputation out of a number.")
    else:
        second.append("No kill is credited to their name in the present roll. What they become will depend on more than that blank.")
    effects = _text(fighter.get("effects"))
    if effects:
        second.append("The consequences already entered against them will shape how they work and how they are seen.")
    status = _text(fighter.get("status")).lower()
    if status in ("killed", "dead"):
        second.append("Their living part in the campaign has ended; their place in its history remains.")
    elif "recover" in status:
        second.append("For now they are in Recovery, leaving the next movement of the gang to other hands.")
    elif "retir" in status:
        second.append("They have left active service, carrying the campaign into a life beyond the current fighting roll.")
    return first + "\n\n" + " ".join(second)


_CULTURES = {
    "orlock": "A road crew's authority is made from reliable hands, useful machinery, and the willingness to stand beside the same people when the route turns bad.",
    "van saar": "Knowledge and equipment are forms of leverage here. The enclave's confidence rests on making the district's useful systems answer to its own hands.",
    "enforcer": "The precinct carries a claim to lawful command into a district where the warrant still needs someone willing to enforce it.",
    "squat": "The charter treats ground as claim and inheritance. Resources can be exhausted; a debt or remembered slight can prove harder to finish.",
    "goliath": "The House's mark ties a gang's standing to the furnaces and the people who keep them fed. Its fighters must make an inherited claim answer on the ground they hold.",
    "escher": "The House's name travels with the work of its chymists as well as its blades. This gang carries that standing into arrangements made one holding at a time.",
    "delaque": "The public account leaves gaps where a clear hierarchy might be expected. The gang's influence has to be read through the arrangements that others will acknowledge.",
    "cawdor": "Claims made in the House's name carry professions of faith as well as demands for obedience. How each fighter lives with those demands belongs to their own account.",
    "nomad": "The tribe's routes follow a country the hive maps describe poorly. A holding is judged through passage, shelter and the people who know how to return.",
    "cult": "The surviving records describe ties of loyalty and shared observance. They do not settle how far each member understands the others' purposes.",
}


def _culture(gang):
    kind = _text(gang.get("gang_type")).lower()
    if _is_c9(gang):
        return "The working detail's records bind kinship to labour: a name is a place in the Crew, and a place in the Crew is a continuing obligation."
    for key, text in _CULTURES.items():
        if key in kind:
            return text
    return "The gang's identity is being made in the space between the ground it claims and the people it can still persuade to stand together."


def _related(gang, battles):
    name = gang.get("name") or gang.get("gang_name")
    return sorted([b for b in battles or [] if name in (b.get("attacker"), b.get("defender"), b.get("winner"), b.get("territory_claimer"))], key=lambda b: (_text(b.get("date")), b.get("source_row") or 0))


def gang_history(gang, fighters, battles, territories):
    name = gang.get("name") or gang.get("gang_name")
    bs = _related(gang, battles)
    wins = sum(b.get("winner") == name for b in bs)
    losses = sum(bool(b.get("winner")) and b.get("winner") != name and name in (b.get("attacker"), b.get("defender")) for b in bs)
    foes = Counter(x for b in bs for x in (b.get("attacker"), b.get("defender")) if x and x != name)
    holds = [t.get("territory") for t in territories or [] if t.get("gang_name") == name or t.get("gang_id") == gang.get("gang_id")]
    trend = "victories have outweighed recorded defeats" if wins > losses else "defeats have outweighed recorded victories" if losses > wins else "victories and defeats sit level in its recorded account"
    paragraph = f"Across {len(bs)} recorded engagements, {trend}. " if bs else "The battle account has not yet fixed a public history for this gang. "
    if foes:
        rival, count = foes.most_common(1)[0]
        paragraph += f"{_short(rival)} recurs in that history {count} {'time' if count == 1 else 'times'}; repeated contact gives the next meeting a memory before it begins. "
    if holds:
        paragraph += f"Its present claims include {_join(holds)}. Every holding adds another place where the gang's name has to be made credible."
    else:
        paragraph += "Without a settled claim in the territory account, its authority still depends on what it can carry and whom it can keep."
    roster = [f for f in fighters or [] if f.get("gang_name") == name or f.get("gang_id") == gang.get("gang_id")]
    leaders = [f["name"] for f in roster if f.get("class") == "Leader" and _text(f.get("status")).lower() not in ("killed", "dead")]
    if leaders:
        paragraph += f" {_join(leaders, 2)} {'carries' if len(leaders)==1 else 'carry'} the responsibility attached to its current command."
    return _culture(gang) + "\n\n" + paragraph


_PLACES = {
    "Promethium Cache": "Fuel is a promise made to the next shift: heat, light, movement, and the possibility of a fire large enough to consume all three. A cache makes that promise worth fighting over.",
    "Toll Crossing": "Movement narrows here until passage becomes a question someone with a weapon can answer. A route can be taxed, delayed, remembered, or closed.",
    "Old Ruins": "Every useful discovery in old ground says someone before it failed to notice something. The ruins offer that possibility to each new claimant.",
    "Sludge Sea": "Industrial waste has become a landscape with its own routes and costs. Control begins with knowing which passages are worth trusting.",
    "Mine Workings": "The cut ground carries a history of extraction beneath every newer claim. Paths dug for labour can be used for trade, movement, or violence.",
    "Settlement": "A settlement is an agreement made daily by people who need shelter more than they need another quarrel. Armed claims make that agreement possible and threaten it at the same time.",
    "Generatorium": "Every power line leaving this place is someone else's need. Holding the source means having a hand near the lives attached to it.",
    "Refuse Drift": "Discarded industry has become ground to cross, cover to use, and material worth reclaiming. Ownership gives value to what the hive threw away.",
    "Smelting Works": "Heat and labour turn scrap into something that can be used again. Whoever controls the works can decide whose plans receive that second life.",
    "Collapsed Dome": "A failed civic structure has become useful ground again, this time through broken routes and defensible fragments. The collapse did not end the arguments over it.",
    "Needle Ways": "Connections are the asset here: narrow approaches, changes of level, and routes whose value is measured in what they let someone avoid.",
    "Bone Shrine": "A claim to this place has to share space with older claims made in remembrance and belief. Names can hold ground differently from weapons.",
    "Synth Still": "The still turns production into loyalty one measure at a time. Its owner holds an income and a reason for the district to keep returning.",
    "Drinking Hole": "People come here to put down a burden without putting down every caution. Its usefulness depends on how long that arrangement can be made to last.",
    "Stinger Mould Sprawl": "A dangerous growth has become a resource. Its hazards help preserve its value by charging a price before anything is harvested.",
    "Corpse Farm": "The hive has made another use for what it cannot keep alive. The claim is practical; its meaning is harder to keep within a ledger.",
    "Wastes": "The value of this ground lies partly in the difficulty of crossing it. A known way through can be a possession as real as a wall.",
}


def territory_history(territory, battles):
    name = territory.get("territory") or territory.get("name") or "This ground"
    owner = _short(territory.get("gang_name") or territory.get("owner"))
    bs = sorted([b for b in battles or [] if b.get("territory") == name], key=lambda b: (_text(b.get("date")), b.get("source_row") or 0))
    opening = _PLACES.get(name, f"{name} has become one of the places through which the district measures access, income, and the reach of armed claims.")
    if bs:
        latest = bs[-1]
        history = f"The battle account returns to this ground {len(bs)} {'time' if len(bs)==1 else 'times'}. The latest recorded contest was {latest.get('scenario') or 'an engagement'}, decided in favour of {_short(latest.get('winner'))}. "
    else:
        history = "No battle in the surviving campaign account is tied to this ground yet. "
    return opening + "\n\n" + history + f"The current holding is entered under {owner}. A present owner is one chapter of a place, rather than its whole history."


def region_history(gangs, territories, battles):
    gangs = _list(gangs)
    contests = Counter(b.get("territory") for b in battles or [] if b.get("territory"))
    hot = [name for name, _ in contests.most_common(3)]
    leading = max(gangs, key=lambda g: _number(g.get("reputation")), default={})
    first = "Krakaumunda is being written as a set of claims: routes that must stay open, workshops that must keep answering, fuel that must reach another shift. The gangs give those needs names and defend the names with force."
    second = f"The battle account keeps returning to {_join(hot)}. " if hot else "The first settled history of the district is still being made. "
    if leading:
        second += f"{_short(leading.get('name'))} carries the strongest recorded public reputation, though a reputation cannot hold every route at once. "
    second += "Each change of ground alters the map used by the living: where they can pass, whose permission they need, and whose losses they remember."
    return first + "\n\n" + second


def _block(kind, text):
    return {"type": kind, "text": text}


def _document(title, blocks, evidence, source_ids):
    return {"title": title, "blocks": blocks, "evidence": evidence, "source_event_ids": list(dict.fromkeys(x for x in source_ids if x)), "provenance_class": "inference", "generator_version": GENERATOR_VERSION}


def _battle_events(battle, events):
    """Bound batch association: never attach baseline injuries to old battles."""
    row = battle.get("source_row")
    key = battle.get("source_battle_key") or battle.get("battle_key")

    def matches(event):
        payload = _payload(event)
        event_key = payload.get("source_battle_key") or payload.get("battle_key")
        if key and event_key:
            return key == event_key
        current = payload.get("current") or payload
        identity = ("date", "scenario", "attacker", "defender", "winner")
        if "date" in current:
            return all(current.get(field) == battle.get(field) for field in identity)
        changes = payload.get("changes") or {}
        if changes and row is not None and payload.get("source_row") == row:
            return all(delta.get("after") == battle.get(field) for field, delta in changes.items())
        return False

    anchors = [e for e in events or [] if e.get("event_type") in ("battle_result", "battle_record_corrected") and matches(e)]
    anchors.sort(key=lambda e: _text(e.get("observed_at")))
    anchor = anchors[-1] if anchors else None
    # A re-sorted Sheet can amend many old row numbers in one capture. A shared
    # snapshot alone must not attach today's injury to every old battle. Only a
    # recently dated battle is eligible for this deliberately weaker inference.
    try:
        battle_day = datetime.fromisoformat(_text(battle.get("date")).replace("Z", "+00:00")).date()
        observed_day = datetime.fromisoformat(_text(anchor.get("observed_at") if anchor else "").replace("Z", "+00:00")).date()
        near_record_date = abs((observed_day - battle_day).days) <= 1
    except ValueError:
        near_record_date = False
    eligible = anchor and near_record_date and not _text(anchor.get("event_key")).startswith("baseline:") and anchor.get("from_snapshot_id") is not None
    linked = []
    participants = {battle.get("attacker"), battle.get("defender")}
    if eligible:
        for other in events or []:
            if other.get("event_type") != "battle_result" or matches(other) or _text(other.get("event_key")).startswith("baseline:"):
                continue
            same_capture = (anchor.get("to_snapshot_id") is not None and other.get("to_snapshot_id") == anchor["to_snapshot_id"]) or (anchor.get("observed_at") and other.get("observed_at") == anchor["observed_at"])
            other_payload = _payload(other)
            if same_capture and participants.intersection({other_payload.get("attacker"), other_payload.get("defender")}) - {None}:
                # Two games for the same gang in one import do not establish
                # which one caused an individual roster change.
                eligible = False
                break
    for event in events or []:
        if not _text(event.get("event_type")).startswith("fighter_"):
            continue
        p = _payload(event)
        explicit = (p.get("battle_source_row") == row and row is not None) or (battle.get("id") is not None and p.get("battle_id") == battle["id"]) or (key is not None and p.get("battle_key") == key)
        same_batch = bool(eligible and ((anchor.get("to_snapshot_id") is not None and event.get("to_snapshot_id") == anchor["to_snapshot_id"]) or (anchor.get("observed_at") and event.get("observed_at") == anchor["observed_at"])))
        member = any(s.get("gang_name") in participants or s.get("display_name") in participants for s in _subjects(event))
        if explicit or same_batch and member:
            linked.append(event)
    return anchors, linked


def battle_report(battle, gangs, fighters, events):
    scenario = battle.get("scenario") or "Engagement"
    territory = battle.get("territory")
    attacker, defender, winner = (_short(battle.get(k)) for k in ("attacker", "defender", "winner"))
    raw_participants = {battle.get("attacker"), battle.get("defender")}
    parties = [g for g in _list(gangs) if g.get("name") in raw_participants]
    anchors, linked = _battle_events(battle, events)
    title = f"{scenario} — {territory}" if territory else scenario
    evidence = [f"Scenario: {scenario}", f"Attacker: {attacker}", f"Defender: {defender}"]
    if battle.get("date"):
        evidence.insert(0, f"Battle recorded: {battle['date']}")
    evidence.append(f"Winner: {winner}" if battle.get("winner") else "Winner: not recorded")
    if territory:
        evidence.append(f"Territory at stake: {territory}")
    if battle.get("territory_claimer"):
        evidence.append(f"Recorded territory claimant: {_short(battle['territory_claimer'])}")
    blocks = []
    if territory:
        blocks.append(_block("paragraph", _PLACES.get(territory, f"The claim to {territory} has become a question the district cannot leave unanswered.")))
    else:
        blocks.append(_block("paragraph", "Some engagements settle a boundary. Others settle which gang's name carries weight when the next demand is made."))
    if battle.get("attacker") and battle.get("defender"):
        text = f"{attacker} and {defender} meet in the account under {scenario}. "
    else:
        known = attacker if battle.get("attacker") else defender
        text = f"The surviving account places {known} in a {scenario}; the opposing roll is incomplete. "
    if "takeover" in scenario.lower():
        text += "A claim that might once have been an entry on a map has been put to an armed test. "
    elif "trap" in scenario.lower() or "ambush" in scenario.lower():
        text += "The terms of the encounter make position and forewarning part of the contest. "
    elif "escort" in scenario.lower():
        text += "The task makes safe passage an achievement that has to be carried through hostile ground. "
    elif "rescue" in scenario.lower():
        text += "The purpose gives the encounter a human stake beyond its boundary lines: someone is meant to be brought back. "
    elif "shootout" in scenario.lower() or "pit" in scenario.lower():
        text += "Here the rivalry is entered directly, with little ground between the opposing names. "
    if battle.get("winner"):
        text += f"The result is entered in favour of {winner}."
    else:
        text += "The account leaves the verdict open."
    blocks.extend([_block("heading", "Opposed claims"), _block("paragraph", text)])
    if parties:
        blocks.append(_block("paragraph", " ".join(f"For {_short(g['name'])}, {_culture(g)[0].lower()+_culture(g)[1:]}" for g in parties)))
    effects, progress, equipment = [], [], []
    source_ids = [e.get("event_id") for e in anchors]
    for event in linked:
        p = _payload(event)
        person = next((s.get("display_name") for s in _subjects(event) if s.get("entity_type") == "fighter"), None) or p.get("fighter_name")
        if not person:
            continue
        typ = event.get("event_type", "")
        if typ in ("fighter_effects_changed", "fighter_status_changed"):
            result = _text(p.get("after")) or "cleared"
            effects.append(f"{person}: {result}")
        elif typ in ("fighter_xp_changed", "fighter_advancement_changed", "fighter_skills_changed", "fighter_kills_changed"):
            label = {"fighter_xp_changed": "XP", "fighter_advancement_changed": "Advancements", "fighter_skills_changed": "Skills", "fighter_kills_changed": "Kills"}[typ]
            progress.append(f"{person} — {label}: {p.get('before') if p.get('before') is not None else 'none'} → {p.get('after') if p.get('after') is not None else 'none'}")
        elif typ in ("fighter_weapons_changed", "fighter_wargear_changed"):
            equipment.append(f"{person}: {_join(_items(p.get('after')), 2) or 'equipment entry cleared'}")
        else:
            continue
        source_ids.append(event.get("event_id"))
    if effects or progress or equipment:
        blocks.append(_block("heading", "The accompanying returns"))
        if effects:
            injured_names = list(dict.fromkeys(x.split(":", 1)[0] for x in effects))
            critical = [x.split(":", 1)[0] for x in effects if "critical" in x.lower()]
            if critical:
                blocks.append(_block("paragraph", f"The accompanying roster return carries a critical condition against {_join(critical)}. The verdict on an engagement cannot make that a small cost. The question has moved from whose claim prevailed to who will still be able to take their place when the next demand comes."))
            else:
                blocks.append(_block("paragraph", f"The same return amends the conditions of {_join(injured_names)}. The result can be written in one line; its weight will be carried in bodies, absences, and the work left to other hands."))
            evidence.extend(effects)
        if progress:
            alongside = " alongside the condition return" if effects else " in the accompanying return"
            blocks.append(_block("paragraph", f"The experience account changes{alongside}. What has been learned may outlast this encounter, but the numbers preserve no account of which shot, order, or act earned it."))
            evidence.extend(progress)
        if equipment:
            blocks.append(_block("paragraph", "Equipment entries also change in the accompanying return. The next appearance of these gangs will be shaped by what their fighters can now carry, and by the arrangements they have left behind."))
            evidence.extend(equipment)
        evidence.append("Fighter updates above were observed in the same Sheet snapshot as the battle record; their association with this battle is inferred. Individual deployment and precise causes are not recorded.")
    else:
        blocks.append(_block("heading", "What the result leaves behind"))
        blocks.append(_block("paragraph", "A battle leaves a new expectation on both sides. The successful gang has a result to defend; its opponent has a reason to study the next opportunity. Neither account ends at the edge of this entry." if battle.get("winner") else "An unsettled result leaves both claims alive. The next meeting will inherit the question this one did not close."))
    if territory and battle.get("territory_claimer"):
        claimant = _short(battle["territory_claimer"])
        blocks.append(_block("paragraph", f"The territory return names {claimant} against {territory}. The place remains what made it worth contesting; the name answering for access has been entered afresh."))
    c9 = any(_is_c9(g) for g in parties) or any("C-NINE" in _text(x) for x in raw_participants)
    closing = f"Disposition: engagement concluded in favour of {winner}. Personnel and material returns remain part of the account." if c9 and battle.get("winner") else f"The name above this engagement is {winner}. What it will mean at the next meeting is still being made." if battle.get("winner") else "The engagement is entered. Its consequences remain open."
    blocks.append(_block("quote", closing))
    evidence.append("Gang participants are recorded; an individual fighter attendance list is not supplied.")
    document = _document(title, blocks, evidence, source_ids)
    if _text(battle.get("notes")):
        document["recorded_notes"] = {"text": _text(battle["notes"]), "label": "Recorded battle notes", "provenance_class": "player_authored", "source_id": "live:campaign-sheet"}
    return document


def downtime_document(gang, fighters, memories, battles):
    name = gang.get("name") or gang.get("gang_name")
    roster = [f for f in fighters or [] if f.get("gang_name") == name or f.get("gang_id") == gang.get("gang_id")]
    current_roster = [f for f in roster if f.get("listed_in_source", 1) != 0]
    recovering = [f["name"] for f in current_roster if "recover" in _text(f.get("status")).lower() or "convalesc" in _text(f.get("effects")).lower()]
    dead = [f["name"] for f in roster if _text(f.get("status")).lower() in ("killed", "dead")]
    captured = [f["name"] for f in current_roster if "captur" in _text(f.get("status")).lower()]
    bs = _related(gang, battles)
    latest = bs[-1] if bs else None
    evidence, source_ids = [], []
    blocks = [_block("heading", "Allocation of the interval" if _is_c9(gang) else "Between engagements")]
    if latest:
        result = "a victory" if latest.get("winner") == name else "a defeat" if latest.get("winner") else "an unsettled result"
        blocks.append(_block("paragraph", f"{_short(name)} carries {result} from its latest recorded {latest.get('scenario') or 'engagement'}. The next interval has to make something usable of that return: a lesson retained, a place restored, a reason to stand together again."))
        evidence.append(f"Latest recorded battle: {latest.get('date') or 'date unknown'}; {latest.get('scenario') or 'engagement'}; winner {_short(latest.get('winner')) if latest.get('winner') else 'unrecorded'}")
    else:
        blocks.append(_block("paragraph", _culture(gang)))
    if recovering:
        blocks.append(_block("heading", "Hands held back" if _is_c9(gang) else "Recovery"))
        blocks.append(_block("paragraph", f"{_join(recovering)} {'remains' if len(recovering) == 1 else 'remain'} outside ordinary service. The interval is counted differently by a fighter waiting to return: the gang's movement becomes something heard about, and the place in its line has to be held in mind before it can be taken again."))
        evidence.append("Current recovery/convalescence entries: " + ", ".join(recovering))
    if captured:
        blocks.append(_block("paragraph", f"{_join(captured)} {'remains entered as captive' if len(captured) == 1 else 'remain entered as captives'}. Their absence is a demand without a settled answer, carried into every discussion of what comes next."))
        evidence.append("Current captive entries: " + ", ".join(captured))
    if dead:
        blocks.append(_block("heading", "Names retained"))
        blocks.append(_block("paragraph", f"The historical roll retains {_join(dead)} among the dead. A gang may replace equipment and redistribute work; it has no equally simple procedure for replacing a familiar presence."))
        evidence.append("Dead fighters retained in historical roster: " + ", ".join(dead))
    recent_memories = [m for m in memories or [] if not m.get("baseline")]
    selected = sorted(recent_memories, key=lambda m: (_text(m.get("occurred_at") or m.get("observed_at")), _number(m.get("importance"))), reverse=True)[:16]
    if selected:
        for memory in selected:
            source_ids.extend(memory.get("source_event_ids") or [])
        topics = Counter(tag for m in selected for tag in (m.get("tags") if isinstance(m.get("tags"), list) else []) if tag)
        if any(t in topics for t in ("equipment", "weapon", "advancement", "growth", "promotion")):
            blocks.append(_block("heading", "Preparation"))
            blocks.append(_block("paragraph", "Recent changes in skill and equipment give the interval another purpose. A new tool needs familiar hands; a new responsibility needs habits strong enough to carry it. These are the quieter preparations that the next battle will ask to see."))
    if not recovering and not captured and not dead:
        blocks.append(_block("paragraph", "The current return contains no death, captivity, or recovery entry. The absence of such entries grants room for preparation; it cannot promise what the next engagement will ask of it."))
    if _is_c9(gang):
        blocks.append(_block("quote", "Standing allocation: restore serviceable hands; retain names of absent personnel; continue the work. THE EMPEROR PROTECTS."))
    else:
        blocks.append(_block("quote", "The interval ends when the next claim has to be answered."))
    if not evidence:
        evidence.append("Based on the gang's current roster and available battle account.")
    return _document(f"{_short(name)} — downtime return", blocks, evidence, source_ids)
