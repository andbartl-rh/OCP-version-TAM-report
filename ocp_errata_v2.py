import requests
import re
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------
CHANNELS = ["4.22", "4.21", "4.20", "4.19", "4.18", "4.16"]
CINCINNATI_URL = "https://api.openshift.com/api/upgrades_info/v1/graph"

# -----------------------------
# Helper
# -----------------------------
def errata_url(advisory):
    return f"https://access.redhat.com/errata/{advisory}"

# -----------------------------
# Get latest version
# -----------------------------
def get_latest(channel):
    nodes = []
    checked = []
    matched = None
    for prefix in ("stable", "fast", "candidate"):
        channel_name = f"{prefix}-{channel}"
        params = {"channel": channel_name, "arch": "amd64"}
        r = requests.get(CINCINNATI_URL, params=params)
        r.raise_for_status()
        nodes = r.json().get("nodes", [])
        checked.append(channel_name)
        if nodes:
            matched = channel_name
            break
    if not nodes:
        raise ValueError(f"No nodes found — checked: {', '.join(checked)}")
    nodes = sorted(
        nodes,
        key=lambda x: list(map(int, x["version"].split(".")))
    )
    return nodes[-1], checked, matched

# -----------------------------
# Normalize errata IDs
# -----------------------------
def normalize_errata(errata_list):
    normalized = []
    for e in errata_list:
        prefix, rest = e.split(":")
        number = rest.zfill(4)
        normalized.append(f"{prefix}:{number}")
    return normalized

# -----------------------------
# Extract errata
# -----------------------------
def extract_errata(metadata):
    text = str(metadata)
    rhsas = sorted(set(re.findall(r"RHSA-\d{4}:\d+", text)))
    rhbas = sorted(set(re.findall(r"RHBA-\d{4}:\d+", text)))
    rhsas = normalize_errata(rhsas)
    rhbas = normalize_errata(rhbas)
    return rhsas, rhbas

# -----------------------------
# Build report
# -----------------------------
def build_report():
    report = []
    for ch in CHANNELS:
        try:
            node, checked, matched = get_latest(ch)
            rhsas, rhbas = extract_errata(node.get("metadata", {}))
            report.append({
                "channel": ch,
                "z_stream": node["version"],
                "checked": checked,
                "matched": matched,
                "RHSA": rhsas,
                "RHBA": rhbas,
                "error": None,
            })
        except Exception as e:
            report.append({
                "channel": ch,
                "z_stream": "ERROR",
                "checked": [],
                "matched": None,
                "RHSA": [],
                "RHBA": [],
                "error": str(e),
            })
    return report

# -----------------------------
# Format compact Markdown
# -----------------------------
def format_markdown(report):
    lines = []
    lines.append("### OpenShift latest stable channel errata report")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    for row in sorted(
        report,
        key=lambda x: list(map(int, x["channel"].split("."))),
        reverse=True
    ):
        # Show errors explicitly instead of silently dropping them
        if row["error"]:
            checked = ", ".join(row["checked"]) if row["checked"] else "none"
            lines.append(f"- **{row['channel']}** — ⚠️ error: {row['error']} (checked: {checked})")
            continue

        # Show which channel was matched, and which were skipped
        skipped = [c for c in row["checked"] if c != row["matched"]]
        channel_note = f"via `{row['matched']}`"
        if skipped:
            channel_note += f" _(skipped: {', '.join(skipped)})_"

        parts = []
        if row["RHSA"]:
            rhsa = ", ".join([f"[{r}]({errata_url(r)})" for r in row["RHSA"]])
            parts.append(f"RHSA: {rhsa}")
        if row["RHBA"]:
            rhba = ", ".join([f"[{r}]({errata_url(r)})" for r in row["RHBA"]])
            parts.append(f"RHBA: {rhba}")

        if not parts:
            lines.append(f"- **{row['channel']} ({row['z_stream']})** {channel_note} — no errata found")
            continue

        lines.append(
            f"- **{row['channel']} ({row['z_stream']})** {channel_note} — " + " | ".join(parts)
        )

    return "\n".join(lines)

# -----------------------------
# MAIN
# -----------------------------
def main():
    report = build_report()
    print()
    print(format_markdown(report))
    print()

if __name__ == "__main__":
    main()
