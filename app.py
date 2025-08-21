# app.py
# Pipe & Hollow Section Weight Calculator
# - π = 22/7 used EVERYWHERE
# - Mother pipe OD via PERIMETER match (5 decimal places)
# - Triangle supports Equilateral and Custom (3 different sides)
# - After Save: updates sidebar immediately (no repo reload)
# - Pushes to GitHub (assets/saved_calcs.json) and shows commit link
# - Wide Save panel styling; repo-only logo

import base64
import json
import math
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

# ============================================================
# PAGE CONFIG & WIDE SAVE PANEL STYLES
# ============================================================
st.set_page_config(page_title="Pipe & Hollow Section Calculator", layout="wide")
st.markdown(
    """
    <style>
      .save-panel {
        padding: 1rem 1.25rem;
        border: 1px solid rgba(49,51,63,0.2);
        border-radius: 10px;
        margin-top: 0.25rem;
        margin-bottom: 0.75rem;
      }
      /* tighten spacing for the Name input */
      .save-panel label {
        margin-top: -10px !important;
        padding-top: 0 !important;
      }
      .save-panel .stTextInput {
        margin-top: -1.2rem !important;
        padding-top: 0 !important;
        max-width: 1000px;
      }
      .block-container { padding-top: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HARD-CODED REPO SETTINGS (YOURS)
# ============================================================
OWNER_REPO = "KANAL1234/NHTPVTLTD"        # <owner>/<repo>
BRANCH = "main"                           # branch to read/write
GH_FILEPATH = "assets/saved_calcs.json"   # JSON persisted file (in repo)
REPO_LOGO_PATH = Path("assets/logo.png")  # logo path inside repo

# ============================================================
# APP CONSTANTS
# ============================================================
PI = 22/7  # use 22/7 everywhere
DENSITY_MS = 7850
SHAPES = ["Circle", "Square", "Rectangle", "Oval", "Triangle"]
LOCAL_SAVED_PATH = Path(GH_FILEPATH)  # optional local mirror (dev)

# ============================================================
# GITHUB API HELPERS (push-only; no reload)
# ============================================================
def token_present() -> bool:
    return "GITHUB_TOKEN" in st.secrets and bool(st.secrets["GITHUB_TOKEN"])

def gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh_contents_url(path: str) -> str:
    return f"https://api.github.com/repos/{OWNER_REPO}/contents/{path}"

def gh_get_file_sha(path: str, branch: str):
    r = requests.get(gh_contents_url(path), headers=gh_headers(), params={"ref": branch}, timeout=20)
    if r.status_code == 200:
        try:
            return r.json().get("sha")
        except Exception:
            return None
    return None

def gh_put_file_with_commit(path: str, branch: str, content_bytes: bytes, message: str):
    """
    Create/update file via Contents API.
    Returns (ok, commit_url_or_error_text).
    """
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    sha = gh_get_file_sha(path, branch)
    if sha:
        payload["sha"] = sha

    r = requests.put(gh_contents_url(path), headers=gh_headers(), json=payload, timeout=30)
    try:
        j = r.json()
    except Exception:
        j = {}
    if 200 <= r.status_code < 300:
        commit_url = None
        if isinstance(j, dict) and j.get("commit"):
            commit_url = j["commit"].get("html_url") or j["commit"].get("sha")
            if commit_url and not str(commit_url).startswith("http"):
                commit_url = f"https://github.com/{OWNER_REPO}/commit/{commit_url}"
        msg = "Saved to GitHub."
        if commit_url:
            msg += f" Commit: {commit_url}"
        return True, msg
    else:
        return False, f"GitHub push failed [{r.status_code} {r.reason}]: {str(j)[:600]}"

# ============================================================
# SAVE/LOAD UTILITIES (session-first; optional local mirror)
# ============================================================
def empty_saved() -> dict:
    return {s: [] for s in SHAPES}

def normalize_saved(d: dict) -> dict:
    out = empty_saved()
    if isinstance(d, dict):
        for s in SHAPES:
            if isinstance(d.get(s), list):
                out[s] = d[s]
    return out

def load_initial_saved() -> dict:
    """
    Use a local file if present; otherwise start with empty buckets.
    We avoid fetching from GitHub to keep logic simple/fast.
    """
    if LOCAL_SAVED_PATH.exists():
        try:
            return normalize_saved(json.loads(LOCAL_SAVED_PATH.read_text("utf-8")))
        except Exception:
            pass
    return empty_saved()

def write_local(saved: dict) -> None:
    LOCAL_SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SAVED_PATH.write_text(json.dumps(saved, indent=2), encoding="utf-8")

# ============================================================
# GEOMETRY / WEIGHT FUNCTIONS (π = 22/7)
# ============================================================
def weight_circle(OD, thickness, density):
    ID = OD - 2 * thickness
    if ID < 0:
        return 0.0, 0.0, 0.0
    area_mm2 = (PI / 4) * (OD**2 - ID**2)  # π=22/7
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2, ID

def weight_square(OD, thickness, density):
    ID = OD - 2 * thickness
    if ID < 0:
        return 0.0, 0.0
    area_mm2 = OD**2 - ID**2
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2

def weight_rectangle(L, W, thickness, density):
    ID_L = L - 2 * thickness
    ID_W = W - 2 * thickness
    if ID_L < 0 or ID_W < 0:
        return 0.0, 0.0
    area_mm2 = (L * W) - (ID_L * ID_W)
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2

def weight_oval(major, minor, thickness, density):
    # Treat oval as ellipse; area = πab
    a_o = major / 2
    b_o = minor / 2
    a_i = a_o - thickness
    b_i = b_o - thickness
    if a_i < 0 or b_i < 0:
        return 0.0, 0.0
    area_mm2 = PI * a_o * b_o - PI * a_i * b_i  # π = 22/7
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2

def weight_triangle_equilateral(side, thickness, density):
    # Equilateral triangle hollow section via inner parallel offset
    s_o = side
    s_i = side - 2 * thickness / math.sin(math.radians(60))
    if s_i < 0:
        return 0.0, 0.0
    outer_area = (math.sqrt(3) / 4) * s_o**2
    inner_area = (math.sqrt(3) / 4) * s_i**2
    area_mm2 = outer_area - inner_area
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2

def weight_triangle_general(a, b, c, thickness, density):
    """
    Hollow triangle (general scalene) using inward parallel offset (distance = thickness).
    Outer area A0 from Heron's formula.
    Inner area A_in = A0 - t*P + t^2 * Σ cot(θ_i/2)
    For a triangle, Σ cot(θ_i/2) = s^2 / A0  (where s = (a+b+c)/2)
    => wall area = A0 - A_in = t*P - t^2 * (s^2 / A0)

    Valid only if triangle inequality holds and thickness < inradius r = A0 / s.
    Returns (weight_kg_per_m, wall_area_mm2, inradius_r).
    """
    # Triangle inequality
    if a + b <= c or b + c <= a or c + a <= b:
        return 0.0, 0.0, 0.0  # invalid

    P = a + b + c
    s = P / 2.0

    # Heron's formula for outer area
    A0_sq = s * (s - a) * (s - b) * (s - c)
    if A0_sq <= 0:
        return 0.0, 0.0, 0.0
    A0 = math.sqrt(A0_sq)

    # Inradius
    r = A0 / s

    # Thickness must be less than inradius
    if thickness >= r:
        return 0.0, 0.0, r

    # Wall (material) area:
    wall_area = thickness * P - (thickness ** 2) * (s ** 2 / A0)
    if wall_area <= 0:
        return 0.0, 0.0, r

    weight = wall_area * 1e-6 * density
    return weight, wall_area, r

# Mother Pipe OD from PERIMETER (π = 22/7)
def mother_od_from_perimeter(shape: str, inputs: dict) -> float:
    if shape == "Square":
        P = 4 * inputs["OD"]
    elif shape == "Rectangle":
        P = 2 * (inputs["L"] + inputs["W"])
    elif shape == "Oval":
        # Ramanujan’s 1st perimeter approximation using π=22/7
        a = inputs["major"] / 2
        b = inputs["minor"] / 2
        P = PI * (3*(a+b) - math.sqrt((3*a + b) * (a + 3*b)))
    elif shape == "Triangle":
        # Expect either 'side' (equilateral) OR 'a','b','c' (custom)
        if "side" in inputs:
            P = 3 * inputs["side"]
        else:
            P = inputs["a"] + inputs["b"] + inputs["c"]
    else:
        return 0.0
    return P / PI  # D = P / π

# ============================================================
# SESSION BOOT
# ============================================================
if "saved" not in st.session_state:
    st.session_state.saved = load_initial_saved()  # local or empty
if "last_result" not in st.session_state:
    st.session_state.last_result = None  # last calculation result

# ============================================================
# HEADER (logo from repo only)
# ============================================================
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Pipe & Hollow Section Weight Calculator")
with col_logo:
    if REPO_LOGO_PATH.exists():
        try:
            st.image(Image.open(REPO_LOGO_PATH), use_container_width=True)
        except Exception as e:
            st.warning(f"Logo error: {e}")
    else:
        st.caption("Add assets/logo.png to your repo for a header logo.")

st.caption("Calculates weight per meter and, for non-circular shapes, the equivalent circular mother pipe OD (perimeter match, π=22/7).")

# ============================================================
# SIDEBAR: SAVED LIST (reflects st.session_state.saved directly)
# ============================================================
st.sidebar.header("Saved Calculations")
for s in SHAPES:
    entries = st.session_state.saved.get(s, [])
    with st.sidebar.expander(f"{s} ({len(entries)})", expanded=(len(entries) > 0)):
        if not entries:
            st.caption("No saved items yet.")
        else:
            for idx, item in enumerate(entries):
                dims = item.get("dimensions_str", "")
                st.markdown(f"**{item['name']}** — {dims}")
                cols = st.columns([1, 1, 3])
                with cols[0]:
                    if st.button("Load", key=f"load_{s}_{idx}"):
                        st.session_state["shape"] = s
                        st.session_state["current_inputs"] = item["inputs"]
                        st.session_state["current_thickness"] = item["thickness"]
                        st.session_state["current_density"] = item["density"]
                        st.session_state["trigger_load"] = True
                with cols[1]:
                    if st.button("🗑️", key=f"del_{s}_{idx}"):
                        st.session_state.saved[s].pop(idx)
                        # Local mirror (optional)
                        try:
                            write_local(st.session_state.saved)
                        except Exception:
                            pass
                        # Push to GitHub (no reload)
                        if token_present():
                            ok, msg = gh_put_file_with_commit(
                                GH_FILEPATH,
                                BRANCH,
                                json.dumps(st.session_state.saved, indent=2).encode("utf-8"),
                                "Delete saved calc via app",
                            )
                            st.toast(msg if ok else msg)
                        st.rerun()

# ============================================================
# INPUTS
# ============================================================
shape = st.selectbox("Select Shape", SHAPES, key="shape")

loaded_inputs = st.session_state.get("current_inputs", {})
loaded_thk = float(st.session_state.get("current_thickness", 1.0))
loaded_den = int(st.session_state.get("current_density", DENSITY_MS))

thickness = st.number_input("Wall Thickness (mm)", min_value=0.1, value=loaded_thk, step=0.1, key="thk_input")
density   = st.number_input("Material Density (kg/m³)", min_value=1000, value=loaded_den, step=50, key="den_input")

if shape == "Circle":
    OD = st.number_input("Outer Diameter (mm)", min_value=1.0,
                         value=float(loaded_inputs.get("OD", 25.0)), step=0.5, key="circle_OD")

elif shape == "Square":
    OD = st.number_input("Outer Side (mm)", min_value=1.0,
                         value=float(loaded_inputs.get("OD", 25.0)), step=0.5, key="square_OD")

elif shape == "Rectangle":
    L = st.number_input("Outer Length (mm)", min_value=1.0,
                        value=float(loaded_inputs.get("L", 40.0)), step=0.5, key="rect_L")
    W = st.number_input("Outer Width (mm)", min_value=1.0,
                        value=float(loaded_inputs.get("W", 25.0)), step=0.5, key="rect_W")

elif shape == "Oval":
    major = st.number_input("Outer Major Axis (mm)", min_value=1.0,
                            value=float(loaded_inputs.get("major", 40.0)), step=0.5, key="oval_major")
    minor = st.number_input("Outer Minor Axis (mm)", min_value=1.0,
                            value=float(loaded_inputs.get("minor", 25.0)), step=0.5, key="oval_minor")

elif shape == "Triangle":
    tri_mode = st.radio(
        "Triangle type",
        ["Equilateral", "Custom (3 sides)"],
        horizontal=True,
        key="tri_mode",
    )
    if tri_mode == "Equilateral":
        side = st.number_input(
            "Outer Side Length (mm)",
            min_value=1.0,
            value=float(loaded_inputs.get("side", 25.0)),
            step=0.5,
            key="tri_side",
        )
    else:
        a = st.number_input(
            "Side a (mm)",
            min_value=1.0,
            value=float(loaded_inputs.get("a", 30.0)),
            step=0.5,
            key="tri_a",
        )
        b = st.number_input(
            "Side b (mm)",
            min_value=1.0,
            value=float(loaded_inputs.get("b", 40.0)),
            step=0.5,
            key="tri_b",
        )
        c = st.number_input(
            "Side c (mm)",
            min_value=1.0,
            value=float(loaded_inputs.get("c", 50.0)),
            step=0.5,
            key="tri_c",
        )

if st.session_state.get("trigger_load"):
    st.session_state["trigger_load"] = False

# ============================================================
# CALCULATE (stores result in session)
# ============================================================
if st.button("Calculate", type="primary"):
    t = st.session_state["thk_input"]
    den = st.session_state["den_input"]

    if shape == "Circle":
        w, area, ID = weight_circle(st.session_state["circle_OD"], t, den)
        st.session_state.last_result = {
            "shape": "Circle",
            "inputs": {"OD": st.session_state["circle_OD"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"ID": ID, "mother_OD": st.session_state["circle_OD"]},
            "dimensions_str": f"OD {st.session_state['circle_OD']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(
            f"Inner Diameter: **{ID:.2f} mm**  |  "
            f"Mother Pipe OD: **{st.session_state['circle_OD']:.5f} mm**"
        )

    elif shape == "Square":
        w, area = weight_square(st.session_state["square_OD"], t, den)
        mp_od = mother_od_from_perimeter("Square", {"OD": st.session_state["square_OD"]})
        st.session_state.last_result = {
            "shape": "Square",
            "inputs": {"OD": st.session_state["square_OD"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od},
            "dimensions_str": f"{st.session_state['square_OD']} × {st.session_state['square_OD']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD (perimeter match): **{mp_od:.5f} mm**")

    elif shape == "Rectangle":
        w, area = weight_rectangle(st.session_state["rect_L"], st.session_state["rect_W"], t, den)
        mp_od = mother_od_from_perimeter(
            "Rectangle",
            {"L": st.session_state["rect_L"], "W": st.session_state["rect_W"]},
        )
        st.session_state.last_result = {
            "shape": "Rectangle",
            "inputs": {"L": st.session_state["rect_L"], "W": st.session_state["rect_W"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od},
            "dimensions_str": f"{st.session_state['rect_L']} × {st.session_state['rect_W']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD (perimeter match): **{mp_od:.5f} mm**")

    elif shape == "Oval":
        w, area = weight_oval(st.session_state["oval_major"], st.session_state["oval_minor"], t, den)
        mp_od = mother_od_from_perimeter(
            "Oval",
            {"major": st.session_state["oval_major"], "minor": st.session_state["oval_minor"]},
        )
        st.session_state.last_result = {
            "shape": "Oval",
            "inputs": {"major": st.session_state["oval_major"], "minor": st.session_state["oval_minor"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od},
            "dimensions_str": f"{st.session_state['oval_major']} × {st.session_state['oval_minor']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD (perimeter match): **{mp_od:.5f} mm**")

    elif shape == "Triangle":
        if st.session_state["tri_mode"] == "Equilateral":
            a = st.session_state["tri_side"]
            w, area = weight_triangle_equilateral(a, t, den)
            mp_od = mother_od_from_perimeter("Triangle", {"side": a})
            st.session_state.last_result = {
                "shape": "Triangle",
                "inputs": {"side": a, "mode": "Equilateral"},
                "thickness": t,
                "density": den,
                "weight": w,
                "area_mm2": area,
                "extra": {"mother_OD": mp_od},
                "dimensions_str": f"Equilateral {a} × t {t} mm",
            }
            st.success(f"Weight per meter: **{w:.3f} kg/m**")
            st.info(f"Mother Pipe OD (perimeter match): **{mp_od:.5f} mm**")
        else:
            a = st.session_state["tri_a"]
            b = st.session_state["tri_b"]
            c = st.session_state["tri_c"]
            w, wall_area, r = weight_triangle_general(a, b, c, t, den)
            if w == 0.0 and wall_area == 0.0:
                if r == 0.0:
                    st.error("Invalid triangle sides (triangle inequality not satisfied).")
                else:
                    st.error(f"Thickness too large. It must be less than the inradius r = {r:.3f} mm.")
            else:
                mp_od = mother_od_from_perimeter("Triangle", {"a": a, "b": b, "c": c})
                st.session_state.last_result = {
                    "shape": "Triangle",
                    "inputs": {"a": a, "b": b, "c": c, "mode": "Custom"},
                    "thickness": t,
                    "density": den,
                    "weight": w,
                    "area_mm2": wall_area,
                    "extra": {"mother_OD": mp_od, "inradius": r},
                    "dimensions_str": f"Sides {a}, {b}, {c} × t {t} mm",
                }
                st.success(f"Weight per meter: **{w:.3f} kg/m**")
                st.info(
                    f"Mother Pipe OD (perimeter match): **{mp_od:.5f} mm**  |  "
                    f"Inradius r: **{r:.3f} mm**"
                )

# ============================================================
# SAVE PANEL (wide; always available when a result exists)
# ============================================================
if st.session_state.last_result:
    st.markdown("### Save this calculation")
    with st.container():
        st.markdown('<div class="save-panel">', unsafe_allow_html=True)

        default_name = f"{st.session_state.last_result['shape']} | {st.session_state.last_result['dimensions_str']}"
        save_name = st.text_input("Name", value=default_name, key="save_name_input")

        if st.button("Save", key="save_btn", type="primary"):
            # 1) Update session immediately
            shape_key = st.session_state.last_result["shape"]
            record = dict(st.session_state.last_result)
            record["name"] = save_name
            st.session_state.saved[shape_key].append(record)

            # 2) Optional local mirror for dev
            try:
                write_local(st.session_state.saved)
            except Exception:
                pass

            # 3) Push to GitHub (no reload)
            if token_present():
                ok, msg = gh_put_file_with_commit(
                    GH_FILEPATH,
                    BRANCH,
                    json.dumps(st.session_state.saved, indent=2).encode("utf-8"),
                    "Save calc via app",
                )
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.info("Saved locally (no GITHUB_TOKEN present).")

            # 4) Force UI refresh so sidebar shows the new item count
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("Enter dimensions and click **Calculate** to enable saving.")
