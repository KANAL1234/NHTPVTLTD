# app.py
# Pipe & Hollow Section Weight Calculator
# - Persists to GitHub JSON and auto-reloads from repo after save
# - Repo-only logo (assets/logo.png)

import base64
import json
import math
import time
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

# ============================================================
# HARD-CODED REPO SETTINGS
# ============================================================
OWNER_REPO = "KANAL1234/NHTPVTLTD"        # <owner>/<repo>
BRANCH = "main"                           # branch to read/write
GH_FILEPATH = "assets/saved_calcs.json"   # JSON persisted file
REPO_LOGO_PATH = Path("assets/logo.png")  # logo path inside repo

# ============================================================
# APP CONSTANTS
# ============================================================
DENSITY_MS = 7850
SHAPES = ["Circle", "Square", "Rectangle", "Oval", "Triangle"]
LOCAL_SAVED_PATH = Path(GH_FILEPATH)  # local mirror path

# ============================================================
# GITHUB API HELPERS (with readable errors)
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

def gh_get_contents_response(path: str, branch: str) -> requests.Response:
    params = {"ref": branch} if branch else {}
    return requests.get(gh_contents_url(path), headers=gh_headers(), params=params, timeout=20)

def gh_get_file_sha(path: str, branch: str):
    r = gh_get_contents_response(path, branch)
    if r.status_code == 200:
        try:
            return r.json().get("sha")
        except Exception:
            return None
    return None

def gh_download_text(path: str, branch: str) -> tuple[bool, str]:
    """
    Returns (ok, text_or_error)
    """
    r = gh_get_contents_response(path, branch)
    if r.status_code == 200:
        try:
            body = r.json()
            if body.get("encoding") == "base64":
                content_b64 = body.get("content", "")
                return True, base64.b64decode(content_b64).decode("utf-8")
            # Fallback to RAW URL
            raw_url = f"https://raw.githubusercontent.com/{OWNER_REPO}/{branch}/{path}"
            rr = requests.get(raw_url, timeout=20)
            if rr.ok:
                return True, rr.text
            return False, f"RAW fetch failed: {rr.status_code} {rr.reason}"
        except Exception as e:
            return False, f"Decode error: {e}"
    else:
        return False, f"{r.status_code} {r.reason}: {r.text[:600]}"

def gh_put_file(path: str, branch: str, content_bytes: bytes, message: str) -> tuple[bool, str]:
    """
    Create/update a file through GitHub Contents API.
    Returns (ok, message)
    """
    url = gh_contents_url(path)
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    sha = gh_get_file_sha(path, branch)
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=gh_headers(), json=payload, timeout=30)
    if 200 <= r.status_code < 300:
        return True, "Saved & synced to GitHub."
    return False, f"GitHub push failed [{r.status_code} {r.reason}]: {r.text[:600]}"

# ============================================================
# SAVED CALCS (LOAD/SAVE)
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

def load_saved_from_repo_or_local() -> dict:
    """
    Prefer GitHub (if token present). Otherwise, try local file.
    Always returns a normalized dict with all shape buckets.
    """
    # Try GitHub
    if token_present():
        ok, txt = gh_download_text(GH_FILEPATH, BRANCH)
        if ok:
            try:
                return normalize_saved(json.loads(txt))
            except Exception:
                pass
    # Fallback to local file (present on deployment)
    if LOCAL_SAVED_PATH.exists():
        try:
            return normalize_saved(json.loads(LOCAL_SAVED_PATH.read_text("utf-8")))
        except Exception:
            pass
    return empty_saved()

def write_local(saved: dict) -> tuple[bool, str]:
    try:
        LOCAL_SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_SAVED_PATH.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        return True, "Local JSON updated."
    except Exception as e:
        return False, f"Local write failed: {e}"

def save_to_repo_and_reload(saved: dict) -> tuple[bool, str]:
    """
    Push current 'saved' to GitHub and immediately reload fresh data
    from the repo, then update st.session_state.saved.
    """
    if not token_present():
        return False, "GitHub token missing in secrets (GITHUB_TOKEN)."

    content = json.dumps(saved, indent=2).encode("utf-8")
    ok, msg = gh_put_file(GH_FILEPATH, BRANCH, content, "Update saved_calcs via Streamlit app")
    if not ok:
        return False, msg

    # Small delay helps avoid race with GitHub read-after-write
    time.sleep(0.5)

    # Reload from repo to reflect canonical state
    fresh = load_saved_from_repo_or_local()
    st.session_state.saved = fresh
    return True, "Saved to GitHub and reloaded from repo."

# ============================================================
# GEOMETRY / WEIGHT FUNCTIONS
# ============================================================
def weight_circle(OD, thickness, density):
    ID = OD - 2 * thickness
    if ID < 0:
        return 0.0, 0.0, 0.0
    area_mm2 = (math.pi / 4) * (OD**2 - ID**2)
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
    a_o = major / 2
    b_o = minor / 2
    a_i = a_o - thickness
    b_i = b_o - thickness
    if a_i < 0 or b_i < 0:
        return 0.0, 0.0
    area_mm2 = math.pi * a_o * b_o - math.pi * a_i * b_i
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2

def weight_triangle(side, thickness, density):
    s_o = side
    s_i = side - 2 * thickness / math.sin(math.radians(60))
    if s_i < 0:
        return 0.0, 0.0
    outer_area = (math.sqrt(3) / 4) * s_o**2
    inner_area = (math.sqrt(3) / 4) * s_i**2
    area_mm2 = outer_area - inner_area
    weight = area_mm2 * 1e-6 * density
    return weight, area_mm2

def mother_pipe_diameter(area_mm2, thickness):
    if thickness <= 0:
        return 0.0
    # From A = π * t * (OD - t)  =>  OD = A/(π t) + t
    return (area_mm2 / (math.pi * thickness)) + thickness

# ============================================================
# SESSION BOOT
# ============================================================
if "saved" not in st.session_state:
    st.session_state.saved = load_saved_from_repo_or_local()

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

st.caption("Calculates weight per meter and, for non-circular shapes, the equivalent circular **mother pipe** OD.")

# ============================================================
# SIDEBAR: SAVED LIST
# ============================================================
st.sidebar.header("Saved Calculations")
for s in SHAPES:
    entries = st.session_state.saved.get(s, [])
    with st.sidebar.expander(f"{s} ({len(entries)})", expanded=False):
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
                        # Persist local + repo and reload
                        _okL, _msgL = write_local(st.session_state.saved)
                        okG, msgG = save_to_repo_and_reload(st.session_state.saved)
                        st.toast(_msgL)
                        st.toast(msgG)
                        st.rerun()

# Optional manual reload button
if st.sidebar.button("Reload saved from repo"):
    st.session_state.saved = load_saved_from_repo_or_local()
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
    side = st.number_input("Outer Side Length (mm)", min_value=1.0,
                           value=float(loaded_inputs.get("side", 25.0)), step=0.5, key="tri_side")

if st.session_state.get("trigger_load"):
    st.session_state["trigger_load"] = False

# ============================================================
# CALCULATE
# ============================================================
if st.button("Calculate", type="primary"):
    result = {}
    t = st.session_state["thk_input"]
    den = st.session_state["den_input"]

    if shape == "Circle":
        w, area, ID = weight_circle(st.session_state["circle_OD"], t, den)
        result = {
            "shape": "Circle",
            "inputs": {"OD": st.session_state["circle_OD"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"ID": ID},
            "dimensions_str": f"OD {st.session_state['circle_OD']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Inner Diameter: **{ID:.2f} mm**")

    elif shape == "Square":
        w, area = weight_square(st.session_state["square_OD"], t, den)
        mp_od = mother_pipe_diameter(area, t)
        result = {
            "shape": "Square",
            "inputs": {"OD": st.session_state["square_OD"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * t},
            "dimensions_str": f"{st.session_state['square_OD']} × {st.session_state['square_OD']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*t:.2f} mm**")

    elif shape == "Rectangle":
        w, area = weight_rectangle(st.session_state["rect_L"], st.session_state["rect_W"], t, den)
        mp_od = mother_pipe_diameter(area, t)
        result = {
            "shape": "Rectangle",
            "inputs": {"L": st.session_state["rect_L"], "W": st.session_state["rect_W"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * t},
            "dimensions_str": f"{st.session_state['rect_L']} × {st.session_state['rect_W']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*t:.2f} mm**")

    elif shape == "Oval":
        w, area = weight_oval(st.session_state["oval_major"], st.session_state["oval_minor"], t, den)
        mp_od = mother_pipe_diameter(area, t)
        result = {
            "shape": "Oval",
            "inputs": {"major": st.session_state["oval_major"], "minor": st.session_state["oval_minor"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * t},
            "dimensions_str": f"{st.session_state['oval_major']} × {st.session_state['oval_minor']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*t:.2f} mm**")

    elif shape == "Triangle":
        w, area = weight_triangle(st.session_state["tri_side"], t, den)
        mp_od = mother_pipe_diameter(area, t)
        result = {
            "shape": "Triangle",
            "inputs": {"side": st.session_state["tri_side"]},
            "thickness": t,
            "density": den,
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * t},
            "dimensions_str": f"Equilateral {st.session_state['tri_side']} × t {t} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*t:.2f} mm**")

    # ----------------- SAVE AREA -----------------
    st.markdown("---")
    st.subheader("Save this calculation")
    default_name = f"{result['shape']} | {result['dimensions_str']}"
    save_name = st.text_input("Name this calculation", value=default_name, key="save_name_input")

    if st.button("Save", key="save_btn"):
        record = {
            "name": save_name,
            "shape": result["shape"],
            "inputs": result["inputs"],
            "thickness": result["thickness"],
            "density": result["density"],
            "weight": result["weight"],
            "area_mm2": result["area_mm2"],
            "extra": result["extra"],
            "dimensions_str": result["dimensions_str"],
        }

        # Append in-session first
        st.session_state.saved[result["shape"]].append(record)

        # Write local (dev convenience)
        _okL, _msgL = write_local(st.session_state.saved)
        if _okL:
            st.toast(_msgL)

        # Push to GitHub and auto-reload from repo, then rerun for fresh sidebar
        okG, msgG = save_to_repo_and_reload(st.session_state.saved)
        if okG:
            st.success(msgG)
            st.rerun()
        else:
            st.error(msgG)
