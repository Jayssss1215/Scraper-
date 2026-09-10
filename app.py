import base64
import json
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import Settings
from src.db import Database
from src.exporters import leads_csv
from src.missions import run_mission
from src.models import Lead, MissionRequest
from src.providers.base import ProviderError
from src.scoring import lead_xp
from src.security.github import ForgeError, clone_to_quarantine, search_repositories
from src.security.scanner import scan_repository
from src.services.deduplicate import lead_key

st.set_page_config(page_title="Jay's AI Control Room", page_icon="◈", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Manrope:wght@400;500;600;700&display=swap');
:root{--ink:#071017;--panel:#0d1a22;--line:#223946;--teal:#42f5d4;--blue:#61a7ff;--muted:#8da3ad;--cream:#e8f2f0}
.stApp{background:radial-gradient(circle at 82% 8%,rgba(27,107,120,.22),transparent 28%),linear-gradient(135deg,#071017,#0a141c 58%,#071017);color:var(--cream);font-family:'Manrope',sans-serif}
h1,h2,h3,[data-testid="stMetricValue"]{font-family:'Chakra Petch',sans-serif!important;letter-spacing:.02em}
h1{font-size:clamp(2.4rem,5vw,4.8rem)!important;line-height:.9!important;max-width:780px}.stCaption{color:var(--muted)!important}
[data-testid="stSidebar"]{background:#09131a;border-right:1px solid var(--line)}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(18,39,49,.95),rgba(10,24,31,.95));border:1px solid var(--line);padding:1rem;border-radius:4px;box-shadow:inset 3px 0 var(--teal)}
.hero-kicker{font:600 .72rem 'Chakra Petch';letter-spacing:.22em;color:var(--teal);text-transform:uppercase;margin-top:1rem}
.hero-rule{height:1px;background:linear-gradient(90deg,var(--teal),transparent);margin:1.4rem 0 2rem}
.agent-card,.skill-card,.locked-card,.brief{border:1px solid var(--line);background:linear-gradient(150deg,rgba(16,34,43,.92),rgba(8,20,27,.92));padding:1.25rem;border-radius:5px;position:relative;overflow:hidden}
.agent-card:after{content:'01';position:absolute;right:14px;top:3px;font:700 4rem 'Chakra Petch';color:rgba(66,245,212,.06)}
.mascot-stage{height:170px;display:flex;align-items:center;justify-content:center;margin:-.35rem 0 .4rem;background:radial-gradient(circle,rgba(66,245,212,.12),transparent 61%)}
.mascot-stage img{width:94%;height:100%;object-fit:contain;image-rendering:pixelated;transform:scale(1.72);filter:drop-shadow(0 12px 18px rgba(0,0,0,.42))}
.badge{display:inline-block;border:1px solid #37606e;color:var(--teal);font:600 .7rem 'Chakra Petch';padding:.25rem .5rem;letter-spacing:.12em;text-transform:uppercase}
.skill-card{min-height:170px;margin-bottom:.75rem;transition:border-color .2s ease,transform .2s ease;background:linear-gradient(145deg,rgba(14,39,46,.98),rgba(8,23,30,.96))}
.skill-card:hover{border-color:#3f7b84;transform:translateY(-2px)}.skill-card b{font:600 1.02rem 'Chakra Petch'}
.skill-card p{font-size:.79rem;color:var(--muted);line-height:1.55;margin:.65rem 0}.skill-card .skill-id{position:absolute;right:10px;top:6px;font:700 2.8rem 'Chakra Petch';color:rgba(97,167,255,.07)}
.blueprint{border-color:#305471;background:linear-gradient(145deg,rgba(16,38,55,.98),rgba(8,21,31,.96))}.blueprint .badge{color:var(--blue);border-color:#385d78}
.capability{font:600 .64rem 'Chakra Petch';letter-spacing:.08em;color:#bdd0d6;text-transform:uppercase}
.locked-card{opacity:.55;min-height:122px}.locked-card b{font-family:'Chakra Petch'}
.xp-track{height:8px;background:#172934;margin:.75rem 0}.xp-fill{height:100%;background:linear-gradient(90deg,var(--teal),var(--blue));box-shadow:0 0 18px rgba(66,245,212,.45)}
.brief{border-left:3px solid var(--blue);margin:.5rem 0 1.5rem}.missing{color:#f1b667}.stButton>button,.stDownloadButton>button{border-radius:3px!important;border:1px solid #3b6b75!important;font-family:'Chakra Petch'!important;font-weight:600!important}
.forge-step{border:1px solid var(--line);padding:1rem;background:#0b1820;margin-bottom:.65rem}.forge-step b{font-family:'Chakra Petch';color:var(--teal)}
.verdict{padding:1rem;border:1px solid #34515c;background:linear-gradient(90deg,rgba(66,245,212,.08),transparent);margin:1rem 0}.verdict strong{font:600 1.15rem 'Chakra Petch'}
div[data-testid="stDataFrame"]{border:1px solid var(--line)}
@media (prefers-reduced-motion:no-preference){.block-container{animation:enter .55s ease both}@keyframes enter{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}}
</style>
""", unsafe_allow_html=True)

try:
    settings = Settings()
    db = Database(settings.database_path)
except ValueError as exc:
    st.error(f"Settings need attention: {exc}")
    st.stop()


def display_value(value):
    return value if value not in (None, "") else "Not available"


def row_to_lead(row):
    return Lead(**{k: row.get(k) for k in Lead.model_fields})


with st.sidebar:
    st.markdown("### ◈ CONTROL ROOM")
    page = st.radio("Station", ["New Mission", "Mission Results", "Lead Vault", "Skill Forge", "Settings / Gear"], label_visibility="collapsed")
    st.divider()
    st.caption("LOCAL SYSTEM · HUMAN REVIEW REQUIRED")
    st.caption("No outreach is performed by this app.")

saved_rows = db.rows(saved_only=True)
saved_leads = [row_to_lead(row) for row in saved_rows]
xp = sum(lead_xp(lead) for lead in saved_leads)
level = 1 + xp // 250
progress = xp % 250
equipped_skill = st.session_state.setdefault("equipped_skill", "Lead Hunter")
mascot_path = Path("assets/sugar-glider-agent.png")
mascot_data = base64.b64encode(mascot_path.read_bytes()).decode("ascii")

st.markdown('<div class="hero-kicker">Jay’s AI · Local lead intelligence</div>', unsafe_allow_html=True)
st.title("MISSION CONTROL")
st.caption("Find public business leads. Review every result. Keep the useful ones.")
st.markdown('<div class="hero-rule"></div>', unsafe_allow_html=True)

if page == "New Mission":
    left, right = st.columns([1, 1.75], gap="large")
    with left:
        st.markdown(f'''<div class="agent-card"><span class="badge">LEVEL {level}</span><div class="mascot-stage"><img src="data:image/png;base64,{mascot_data}" alt="Pixel-art sugar glider AI agent"></div><h2>Jay's AI</h2><p>Equipped skill</p><h3>◈ {equipped_skill}</h3><div class="xp-track"><div class="xp-fill" style="width:{progress/2.5}%"></div></div><small>{progress} / 250 XP to next level · {xp} total XP</small></div>''', unsafe_allow_html=True)
        st.markdown("#### Skill rack")
        c1, c2 = st.columns(2)
        lead_active = equipped_skill == "Lead Hunter"
        gap_active = equipped_skill == "Website Gap Hunter"
        c1.markdown(f'<div class="skill-card"><span class="skill-id">01</span><span class="badge">{"EQUIPPED" if lead_active else "READY"}</span><p><b>Lead Hunter</b></p><p>Find local businesses for any offer, then review, save and export them.</p><span class="capability">GENERAL DISCOVERY</span></div>', unsafe_allow_html=True)
        if c1.button("Equipped" if lead_active else "Equip Lead Hunter", disabled=lead_active, use_container_width=True):
            st.session_state["equipped_skill"] = "Lead Hunter"
            st.rerun()
        c2.markdown(f'<div class="skill-card blueprint"><span class="skill-id">02</span><span class="badge">{"EQUIPPED" if gap_active else "READY"}</span><p><b>Website Gap Hunter</b></p><p>Find public OpenStreetMap business records with no independent website listed.</p><span class="capability">$0 DISCOVERY · ENGINE ONLINE</span></div>', unsafe_allow_html=True)
        if c2.button("Equipped" if gap_active else "Equip Gap Hunter", disabled=gap_active, use_container_width=True):
            st.session_state["equipped_skill"] = "Website Gap Hunter"
            st.rerun()
        st.markdown('<div class="locked-card"><span class="badge">LOCKED</span><p><b>Future skill slot</b></p><small>Coming later · no controls enabled</small></div>', unsafe_allow_html=True)
    with right:
        gap_mode = equipped_skill == "Website Gap Hunter"
        st.subheader("New Website Gap Mission" if gap_mode else "New Mission")
        st.caption("$0 prototype: central and inner Melbourne florists. Missing website data is a lead signal, not proof." if gap_mode else "The Training Ground uses bundled sample records. Try “cafe” and “Fitzroy”.")
        with st.form("mission"):
            business_type = st.text_input("Business type", value="florist" if gap_mode else "cafe", placeholder="e.g. florist")
            location = st.text_input("Suburb, city or postcode", value="Melbourne" if gap_mode else "Fitzroy", placeholder="e.g. Melbourne")
            result_limit = st.slider("Maximum leads", 1, settings.max_results, min(10, settings.max_results))
            rule = st.text_area("Optional targeting rule", placeholder="Use only when judgement is needed, e.g. independent cafes suitable for a website redesign")
            ai_ready = settings.ai_enabled and bool(settings.openrouter_key)
            active_provider = "OpenStreetMap" if gap_mode else settings.lead_provider.title()
            st.markdown(f'''<div class="brief"><span class="badge">MISSION BRIEF</span><p><b>Equipped:</b> {equipped_skill}<br><b>Provider:</b> {active_provider} · <b>Provider calls:</b> up to 1 of {settings.max_provider_requests}<br><b>Scout Brain:</b> {'online' if ai_ready and not gap_mode else 'offline — deterministic filters only'} · <b>AI calls:</b> up to {min(result_limit, settings.max_llm_classifications) if ai_ready and rule and not gap_mode else 0}</p></div>''', unsafe_allow_html=True)
            submitted = st.form_submit_button("Find website gaps  →" if gap_mode else "Start Mission  →", type="primary", use_container_width=True)
        if submitted:
            try:
                request = MissionRequest(business_type=business_type, location=location, result_limit=result_limit, targeting_rule=rule)
                with st.spinner("Lead Hunter is scanning approved sources…"):
                    _, leads, llm_calls = run_mission(request, settings, db, provider_name="osm" if gap_mode else None)
                st.session_state["results"] = [lead.model_dump() for lead in leads]
                if leads:
                    usable = sum(bool(x.business_name and x.address) for x in leads)
                    st.success(f"Mission complete: {len(leads)} leads found, {usable} usable. Scout Brain calls: {llm_calls}.")
                else:
                    st.info("No matching leads were found. Try a broader business type or location. No facts were invented.")
            except (ValueError, ProviderError) as exc:
                st.error(str(exc))

elif page == "Mission Results":
    rows = st.session_state.get("results")
    if rows is None:
        rows = db.rows()
    if not rows:
        st.info("No mission results yet. Start with a fixture mission from New Mission.")
    else:
        st.subheader("Mission Results")
        source = pd.DataFrame(rows)
        f1, f2, f3, f4, f5 = st.columns(5)
        has_phone = f1.checkbox("Has phone")
        has_website = f2.checkbox("Has website")
        missing_website = f3.checkbox("No website listed")
        fits = f4.multiselect("Fit", ["match", "not a match", "uncertain", "not assessed"])
        search = f5.text_input("Search", placeholder="Name or area")
        visible = source.copy()
        if has_phone: visible = visible[visible["phone"].notna() & (visible["phone"] != "")]
        if has_website: visible = visible[visible["website"].notna() & (visible["website"] != "")]
        if missing_website: visible = visible[visible["website"].isna() | (visible["website"] == "")]
        if fits: visible = visible[visible["fit"].isin(fits)]
        if search:
            blob = visible[["business_name", "address", "category"]].fillna("").agg(" ".join, axis=1)
            visible = visible[blob.str.contains(search, case=False, regex=False)]
        options = {}
        for _, row in visible.iterrows():
            lead = row_to_lead(row.to_dict())
            options[f"{lead.business_name} — {display_value(lead.address)}"] = lead_key(lead)
        selected = st.multiselect("Select leads to save", list(options), placeholder="Choose one or more leads")
        shown = visible.copy()
        for col in ("phone", "address", "website", "category", "classification_reason"):
            if col in shown: shown[col] = shown[col].fillna("Not available")
        cols = [c for c in ["business_name", "phone", "address", "website", "category", "fit", "classification_reason", "provider", "retrieved_at"] if c in shown]
        st.dataframe(shown[cols], use_container_width=True, hide_index=True, column_config={"website": st.column_config.LinkColumn("Website")})
        b1, b2 = st.columns(2)
        if b1.button("Save selected to Vault", type="primary", use_container_width=True):
            db.save_keys([options[item] for item in selected])
            gain = sum(lead_xp(row_to_lead(row.to_dict())) for _, row in visible.iterrows() if lead_key(row_to_lead(row.to_dict())) in [options[item] for item in selected])
            st.success(f"{len(selected)} lead(s) saved. +{gain} XP for newly usable selections; duplicates never earn twice.")
        export_leads = [row_to_lead(row.to_dict()) for _, row in visible.iterrows() if not selected or lead_key(row_to_lead(row.to_dict())) in [options[item] for item in selected]]
        b2.download_button("Export selected" if selected else "Export visible results", leads_csv(export_leads), "mission-leads.csv", "text/csv", use_container_width=True)

elif page == "Lead Vault":
    st.subheader("Lead Vault")
    st.caption(f"{len(saved_rows)} unique saved leads · {xp} XP. XP: +10 for name + address, +5 with phone or website.")
    if not saved_rows:
        st.info("The vault is empty. Save reviewed leads from Mission Results.")
    for row in saved_rows:
        with st.expander(f"{row['business_name']} · {row['user_status']}"):
            st.write(f"**Phone:** {display_value(row['phone'])}  \n**Address:** {display_value(row['address'])}  \n**Website:** {display_value(row['website'])}  \n**Found by:** {row['mission_query']} in {row['mission_location']}")
            status = st.selectbox("Status", ["new", "reviewing", "qualified", "not suitable"], index=["new", "reviewing", "qualified", "not suitable"].index(row["user_status"]), key=f"status_{row['id']}")
            notes = st.text_area("Notes", row["notes"], key=f"notes_{row['id']}")
            if st.button("Save changes", key=f"save_{row['id']}"):
                db.update_saved(row["id"], status, notes); st.success("Vault entry updated.")
            confirm = st.checkbox("Confirm removal", key=f"confirm_{row['id']}")
            if st.button("Remove from Vault", disabled=not confirm, key=f"delete_{row['id']}"):
                db.delete_saved(row["id"]); st.rerun()
    if saved_leads:
        st.download_button("Export Vault to CSV", leads_csv(saved_leads), "lead-vault.csv", "text/csv")

elif page == "Skill Forge":
    st.markdown('<div class="hero-kicker">QUARANTINE BAY · ZERO-TRUST INTAKE</div>', unsafe_allow_html=True)
    st.subheader("Skill Forge")
    st.caption("Discover third-party code, inspect it without running it, then decide whether it is safe and licensed enough to adapt.")
    st.markdown('''<div class="forge-step"><b>01 · DISCOVER</b><br><small>Search public Python repositories by purpose.</small></div><div class="forge-step"><b>02 · QUARANTINE</b><br><small>Download Git objects only. No checkout, install hooks, imports or execution.</small></div><div class="forge-step"><b>03 · INSPECT</b><br><small>Scan source, dependencies, licence, secrets, command execution and network access.</small></div><div class="forge-step"><b>04 · HUMAN GATE</b><br><small>You approve adaptation. Approval never executes the candidate.</small></div>''', unsafe_allow_html=True)

    search_tab, scan_tab = st.tabs(["Search GitHub", "Import & scan"])
    with search_tab:
        query = st.text_input("What should the skill do?", value="local business lead discovery", placeholder="e.g. public business website finder")
        if st.button("Search public repositories", type="primary"):
            try:
                with st.spinner("Searching GitHub's public repository index…"):
                    st.session_state["forge_candidates"] = search_repositories(query)
            except ForgeError as exc:
                st.error(str(exc))
        for candidate in st.session_state.get("forge_candidates", []):
            with st.container(border=True):
                st.markdown(candidate["name"])
                st.caption(candidate["description"])
                a, b, c = st.columns(3)
                a.metric("Stars", candidate["stars"])
                b.metric("Licence", candidate["license"])
                c.metric("Updated", candidate["updated"][:10])
                st.link_button("Inspect on GitHub", candidate["url"])
                st.code(candidate["url"], language=None)
        if not st.session_state.get("forge_candidates"):
            st.info("Search results are candidates, not recommendations. Popularity does not prove safety or legal suitability.")

    with scan_tab:
        repo_url = st.text_input("Public GitHub repository URL", placeholder="https://github.com/owner/repository")
        st.caption("Only github.com HTTPS repository URLs are accepted. Private repositories and embedded credentials are rejected.")
        if st.button("Quarantine and scan", type="primary", disabled=not repo_url.strip()):
            try:
                with st.spinner("Downloading without checkout, then scanning static source…"):
                    quarantine_path, revision = clone_to_quarantine(repo_url)
                    report = scan_repository(quarantine_path, revision)
                st.session_state["forge_report"] = report.as_dict()
                st.session_state["forge_repo_url"] = repo_url.strip()
                st.session_state["forge_quarantine_path"] = str(quarantine_path)
            except (ForgeError, OSError, subprocess.SubprocessError) as exc:
                st.error(str(exc) if isinstance(exc, ForgeError) else "The candidate could not be scanned safely.")

        report = st.session_state.get("forge_report")
        if report:
            st.markdown(f'<div class="verdict"><span class="badge">SCAN VERDICT</span><br><strong>{report["verdict"]}</strong><br><small>Revision {report["revision"][:12]} · {report["files_scanned"]} text files · {report["bytes_scanned"]:,} bytes inspected</small></div>', unsafe_allow_html=True)
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Critical", report["counts"]["critical"])
            r2.metric("High", report["counts"]["high"])
            r3.metric("Medium", report["counts"]["medium"])
            r4.metric("Licence", report["license_status"])
            if report["findings"]:
                st.dataframe(pd.DataFrame(report["findings"]), use_container_width=True, hide_index=True)
            else:
                st.success("No rule-based findings were detected. Manual code review is still required.")
            st.warning("A clean static scan is not proof of safety. Dependencies, runtime behaviour, provider terms and data handling still need manual review.")
            acknowledged = st.checkbox("I understand approval does not execute or equip this code.")
            blocked = report["verdict"] == "Blocked"
            if st.button("Approve for manual adaptation", disabled=blocked or not acknowledged):
                approval = {
                    "repository": st.session_state["forge_repo_url"],
                    "revision": report["revision"],
                    "verdict": report["verdict"],
                    "status": "approved_for_manual_adaptation",
                }
                approval_path = Path(st.session_state["forge_quarantine_path"]) / "control-room-approval.json"
                approval_path.write_text(json.dumps(approval, indent=2), encoding="utf-8")
                st.success("Candidate approved for manual adaptation. Nothing was installed or executed.")

else:
    st.subheader("Settings / Gear")
    g1, g2, g3 = st.columns(3)
    g1.metric("Lead provider", settings.lead_provider.title())
    g2.metric("Provider key", "Configured" if settings.google_key else "Not configured")
    g3.metric("Scout Brain", "Online" if settings.ai_enabled and settings.openrouter_key else "Offline")
    st.markdown(f'''<div class="brief"><b>Mission limits</b><br>Leads: {settings.max_results} · Provider requests: {settings.max_provider_requests} · AI classifications: {settings.max_llm_classifications}<br><br><b>Local storage</b><br>Database: {settings.database_path}<br>Exports are downloaded by your browser. Keys stay in your local <code>.env</code> file and are never displayed.</div>''', unsafe_allow_html=True)
    if settings.ai_enabled and not settings.openrouter_key:
        st.warning("AI classification is enabled but no OpenRouter key is configured. Missions will continue with deterministic filters only.")
