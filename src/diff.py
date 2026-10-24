"""Pure comparison functions. No Google access and no writes."""

def changed_fields(before: dict, after: dict) -> dict:
    keys = set(before) | set(after)
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in sorted(keys)
        if before.get(key) != after.get(key)
    }


def fighter_delta(before: dict[str, dict], after: dict[str, dict]) -> dict:
    old_names, new_names = set(before), set(after)
    return {
        "recruited": sorted(new_names - old_names),
        "removed": sorted(old_names - new_names),
        "changed": {
            name: changed_fields(before[name], after[name])
            for name in sorted(old_names & new_names)
            if changed_fields(before[name], after[name])
        },
    }
