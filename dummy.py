import streamlit as st
import math
import json
import base64
from pathlib import Path
from PIL import Image
import requests
from io import BytesIO

# =========================================
# Constants
# =========================================
DENSITY_MS = 7850
SHAPES = ["Circle", "Square", "Rectangle", "Oval", "Triangle"]

REPO_LOGO_PATH = Path("assets/logo.png")
SAVED_LOCAL_PATH = Path("assets/saved_calcs.json")  # file tracked in repo

# =========================================
# GitHub Helpers (Contents API)
# =========================================
def have_github_secrets():
    needed = ("GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_FILEPATH")
    return all(k in st.secrets for k in needed)

def gh_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

def gh_get_file_sha(token: str, repo: str, path: str, branch: str):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    params = {"ref": branch} if branch else {}
    r = requests.get(url, headers=gh_headers(token), params=params, timeout=15)
    if r.status_code == 200:
        return r.json().get("sha")
    return None  # file may not exist yet

def gh_put_file(token: str, repo: str, path: str, content_bytes: bytes, message: str, branch: str, sha: str | None):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    data = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
    }
    if branch:
        data["branch"] = branch
    if sha:
        data["sha"] = sha
    r = requests.put(url, headers=gh_headers(token), json=data, timeout=20)
    r.raise_for_status()
    return r.json()

# =========================================
# Load / Save Saved Calculations
# =========================================
def ensure_saved_structure(d: dict):
    """Make sure dict has buckets for each SHAPE."""
    out = {s: [] for s in SHAPES}
    if isinstance(d, dict):
        for s in SHAPES:
            if s in d and isinstance(d[s], list):
                out[s] = d[s]
    return out

def load_saved_from_local() -> dict:
    if SAVED_LOCAL_PATH.exists():
        try:
            with open(SAVED_LOCAL_PATH, "r", encoding="utf-8") as f:
                return ensure_saved_structure(json.load(f))
        except Exception:
            pass
    return ensure_saved_structure({})

def write_saved_to_local(saved: dict):
    SAVED_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SAVED_LOCAL_PATH, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2)

def push_saved_to_github(saved: dict) -> tuple[bool, str]:
    """Push JSON to GitHub if secrets are configured."""
    if not have_github_secrets():
        return False, "GitHub secrets not configured; skipped GitHub push."

    token   = st.secrets["GITHUB_TOKEN"]
    repo    = st.secrets["GITHUB_REPO"]
    branch  = st.secrets.get("GITHUB_BRANCH", "main")
    path    = st.secrets["GITHUB_FILEPATH"]

    content = json.dumps(saved, indent=2).encode("utf-8")
    try:
        sha = gh_get_file_sha(token, repo, path, branch)
        gh_put_file(token, repo, path, content, "Update saved_calcs from Streamlit app", branch, sha)
        return True, "Saved to GitHub."
    except Exception as e:
        return False, f"GitHub push failed: {e}"

# =========================================
# Geometry / Weight Functions
# =========================================
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
    return (area_mm2 / (math.pi * thickness)) + thickness

# =========================================
# Session Init: Saved + Logo
# =========================================
if "saved" not in st.session_state:
    st.session_state.saved = load_saved_from_local()  # bootstrap from repo file

# Read logo from repo only
logo_img = None
if REPO_LOGO_PATH.exists() and REPO_LOGO_PATH.is_file():
    try:
        logo_img = Image.open(REPO_LOGO_PATH)
    except Exception as e:
        st.warning(f"Could not load logo: {e}")
else:
    st.warning(f"Logo file not found at {REPO_LOGO_PATH}")

# =========================================
# UI: Header
# =========================================
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Pipe & Hollow Section Weight Calculator")
with col_logo:
    if logo_img:
        st.image(logo_img, use_container_width=True)

st.caption("Calculates weight per meter and (for non-circular shapes) the equivalent circular **mother pipe** OD.")

# =========================================
# Sidebar: Saved Items
# =========================================
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
                        # persist deletion locally
                        write_saved_to_local(st.session_state.saved)
                        # try to push to GitHub
                        ok, msg = push_saved_to_github(st.session_state.saved)
                        if ok:
                            st.toast("Deleted and synced to GitHub.")
                        else:
                            st.toast(msg)
                        st.rerun()

# =========================================
# Inputs
# =========================================
shape = st.selectbox("Select Shape", SHAPES, key="shape")

loaded_inputs = st.session_state.get("current_inputs", {})
loaded_thk = st.session_state.get("current_thickness", 1.0)
loaded_den = st.session_state.get("current_density", DENSITY_MS)

thickness = st.number_input("Wall Thickness (mm)", min_value=0.1, value=float(loaded_thk), step=0.1, key="thk_input")
density   = st.number_input("Material Density (kg/m³)", min_value=1000, value=int(loaded_den), step=50, key="den_input")

if shape == "Circle":
    OD = st.number_input("Outer Diameter (mm)", min_value=1.0, value=float(loaded_inputs.get("OD", 25.0)), step=0.5, key="circle_OD")

elif shape == "Square":
    OD = st.number_input("Outer Side (mm)", min_value=1.0, value=float(loaded_inputs.get("OD", 25.0)), step=0.5, key="square_OD")

elif shape == "Rectangle":
    L = st.number_input("Outer Length (mm)", min_value=1.0, value=float(loaded_inputs.get("L", 40.0)), step=0.5, key="rect_L")
    W = st.number_input("Outer Width (mm)", min_value=1.0, value=float(loaded_inputs.get("W", 25.0)), step=0.5, key="rect_W")

elif shape == "Oval":
    major = st.number_input("Outer Major Axis (mm)", min_value=1.0, value=float(loaded_inputs.get("major", 40.0)), step=0.5, key="oval_major")
    minor = st.number_input("Outer Minor Axis (mm)", min_value=1.0, value=float(loaded_inputs.get("minor", 25.0)), step=0.5, key="oval_minor")

elif shape == "Triangle":
    side = st.number_input("Outer Side Length (mm)", min_value=1.0, value=float(loaded_inputs.get("side", 25.0)), step=0.5, key="tri_side")

# clear load trigger after widgets render
if st.session_state.get("trigger_load"):
    st.session_state["trigger_load"] = False

# =========================================
# Calculate
# =========================================
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

    # ------- Save section -------
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
        # Save in session
        st.session_state.saved[result["shape"]].append(record)

        # Write to local file (works locally / also shows up in build artifact)
        try:
            write_saved_to_local(st.session_state.saved)
            st.toast("Saved to local file.")
        except Exception as e:
            st.warning(f"Local save failed: {e}")

        # Push to GitHub (if secrets configured)
        ok, msg = push_saved_to_github(st.session_state.saved)
        if ok:
            st.success("Saved & synced to GitHub.")
        else:
            st.info(msg)
