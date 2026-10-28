"""CLI usage is observational, never a billing estimate."""


def summarize_usage(receipts):
    totals, previous, unknown = {}, {}, 0
    for index, receipt in enumerate(receipts):
        usage = receipt.get("usage")
        if not isinstance(usage, dict):
            unknown += 1
            continue
        mode = receipt.get("usage_mode")
        if mode not in ("session_cumulative", "incremental"):
            unknown += 1
            continue
        sid = receipt.get("session_id")
        if mode == "session_cumulative" and not sid:
            unknown += 1
            continue
        old = previous.get(sid, {}) if mode == "session_cumulative" else {}
        for key, value in usage.items():
            if type(value) is not int or value < 0:
                continue
            # A counter reset starts a new accounting segment.
            increment = value - old.get(key, 0) if value >= old.get(key, 0) else value
            totals[key] = totals.get(key, 0) + increment
        if mode == "session_cumulative":
            previous[sid] = usage
    return {"reported_totals": totals or None, "usage_unknown_calls": unknown,
            "usage_fully_reported": bool(receipts) and not unknown,
            "usage_note": "CLI-reported tokens; cached/reasoning counts are subsets, not additional totals; not a bill"}
