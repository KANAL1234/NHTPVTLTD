import streamlit as st
import math
from io import BytesIO
from PIL import Image
from pathlib import Path
import requests

# ----------------------------
# Defaults & Session Bootstraps
# ----------------------------
DENSITY_MS = 7850  # kg/m³ default for Mild Steel
SHAPES = ["Circle", "Square", "Rectangle", "Oval", "Triangle"]

# Default repo asset path to try (relative to repo root)
DEFAULT_REPO_LOGO_PATH = Path("assets/logo.png")

if "saved" not in st.session_state:
    st.session_state.saved = {s: [] for s in SHAPES}

if "logo_img" not in st.session_state:
    st.session_state.logo_img = None  # PIL.Image or None

# ----------------------------
# Calculation Functions
# ----------------------------
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

# ----------------------------
# Sidebar: Saved Calculations & Logo Controls
# ----------------------------
st.sidebar.header("Saved Calculations")

for s in SHAPES:
    entries = st.session_state.saved.get(s, [])
    with st.sidebar.expander(f"{s} ({len(entries)})", expanded=(len(entries) > 0)):
        if not entries:
            st.caption("No saved items yet.")
        else:
            for idx, item in enumerate(entries):
                dims = item["dimensions_str"]
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
                        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Logo (top-right)")

# 1) Upload (highest priority)
logo_file = st.sidebar.file_uploader("Upload logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
if logo_file:
    try:
        st.session_state.logo_img = Image.open(BytesIO(logo_file.read()))
        st.sidebar.success("Logo loaded from upload.")
    except Exception:
        st.sidebar.error("Could not load uploaded image.")

# 2) Repo asset path (e.g., assets/logo.png)
repo_logo_path_str = st.sidebar.text_input("Repo logo path", value=str(DEFAULT_REPO_LOGO_PATH))
if st.sidebar.button("Load from repo path"):
    p = Path(repo_logo_path_str)
    if p.exists() and p.is_file():
        try:
            st.session_state.logo_img = Image.open(p)
            st.sidebar.success(f"Logo loaded from repo file: {p}")
        except Exception:
            st.sidebar.error("File found but could not open as image.")
    else:
        st.sidebar.error("Repo path not found in app directory. Ensure the file is committed to the repo.")

# 3) GitHub RAW URL (e.g., https://raw.githubusercontent.com/user/repo/branch/assets/logo.png)
raw_url = st.sidebar.text_input("GitHub RAW URL (optional)", value="")
if st.sidebar.button("Fetch from RAW URL"):
    if raw_url.strip():
        try:
            resp = requests.get(raw_url.strip(), timeout=10)
            resp.raise_for_status()
            st.session_state.logo_img = Image.open(BytesIO(resp.content))
            st.sidebar.success("Logo loaded from GitHub RAW URL.")
        except Exception as e:
            st.sidebar.error(f"Fetch failed: {e}")

st.sidebar.caption("Priority: Upload > Repo path > RAW URL > fallback logo.png")

# ----------------------------
# Header with Logo at Top-Right
# ----------------------------
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Pipe & Hollow Section Weight Calculator")
with col_logo:
    shown = False
    if st.session_state.logo_img is not None:
        st.image(st.session_state.logo_img, use_container_width=True)
        shown = True
    else:
        # Auto-try default repo path
        if DEFAULT_REPO_LOGO_PATH.exists():
            try:
                st.image(Image.open(DEFAULT_REPO_LOGO_PATH), use_container_width=True)
                shown = True
            except Exception:
                pass
        # Fallback to local root logo.png
        if not shown and Path("logo.png").exists():
            try:
                st.image("logo.png", use_container_width=True)
                shown = True
            except Exception:
                pass

st.write("Calculate weight per meter and (for non-circular shapes) the equivalent circular **mother pipe** OD.")

# ----------------------------
# Inputs
# ----------------------------
shape = st.selectbox("Select Shape", SHAPES, key="shape")

# Load-on-demand
if st.session_state.get("trigger_load"):
    loaded_inputs = st.session_state.get("current_inputs", {})
    loaded_thk = st.session_state.get("current_thickness", 1.0)
    loaded_den = st.session_state.get("current_density", DENSITY_MS)
else:
    loaded_inputs = {}
    loaded_thk = 1.0
    loaded_den = DENSITY_MS

thickness = st.number_input("Wall Thickness (mm)", min_value=0.1, value=float(loaded_thk), step=0.1, key="thk_input")
density = st.number_input("Material Density (kg/m³)", min_value=1000, value=int(loaded_den), step=50, key="den_input")

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

if st.session_state.get("trigger_load"):
    st.session_state["trigger_load"] = False

# ----------------------------
# Calculate
# ----------------------------
if st.button("Calculate", type="primary"):
    result = {}
    if shape == "Circle":
        w, area, ID = weight_circle(st.session_state["circle_OD"], st.session_state["thk_input"], st.session_state["den_input"])
        result = {
            "shape": "Circle",
            "inputs": {"OD": st.session_state["circle_OD"]},
            "thickness": st.session_state["thk_input"],
            "density": st.session_state["den_input"],
            "weight": w,
            "area_mm2": area,
            "extra": {"ID": ID},
            "dimensions_str": f"OD {st.session_state['circle_OD']} × t {st.session_state['thk_input']} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Inner Diameter: **{ID:.2f} mm**")

    elif shape == "Square":
        w, area = weight_square(st.session_state["square_OD"], st.session_state["thk_input"], st.session_state["den_input"])
        mp_od = mother_pipe_diameter(area, st.session_state["thk_input"])
        result = {
            "shape": "Square",
            "inputs": {"OD": st.session_state["square_OD"]},
            "thickness": st.session_state["thk_input"],
            "density": st.session_state["den_input"],
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * st.session_state["thk_input"]},
            "dimensions_str": f"{st.session_state['square_OD']} × {st.session_state['square_OD']} × t {st.session_state['thk_input']} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Equivalent Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*st.session_state['thk_input']:.2f} mm**")

    elif shape == "Rectangle":
        w, area = weight_rectangle(st.session_state["rect_L"], st.session_state["rect_W"], st.session_state["thk_input"], st.session_state["den_input"])
        mp_od = mother_pipe_diameter(area, st.session_state["thk_input"])
        result = {
            "shape": "Rectangle",
            "inputs": {"L": st.session_state["rect_L"], "W": st.session_state["rect_W"]},
            "thickness": st.session_state["thk_input"],
            "density": st.session_state["den_input"],
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * st.session_state["thk_input"]},
            "dimensions_str": f"{st.session_state['rect_L']} × {st.session_state['rect_W']} × t {st.session_state['thk_input']} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Equivalent Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*st.session_state['thk_input']:.2f} mm**")

    elif shape == "Oval":
        w, area = weight_oval(st.session_state["oval_major"], st.session_state["oval_minor"], st.session_state["thk_input"], st.session_state["den_input"])
        mp_od = mother_pipe_diameter(area, st.session_state["thk_input"])
        result = {
            "shape": "Oval",
            "inputs": {"major": st.session_state["oval_major"], "minor": st.session_state["oval_minor"]},
            "thickness": st.session_state["thk_input"],
            "density": st.session_state["den_input"],
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * st.session_state["thk_input"]},
            "dimensions_str": f"{st.session_state['oval_major']} × {st.session_state['oval_minor']} × t {st.session_state['thk_input']} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Equivalent Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*st.session_state['thk_input']:.2f} mm**")

    elif shape == "Triangle":
        w, area = weight_triangle(st.session_state["tri_side"], st.session_state["thk_input"], st.session_state["den_input"])
        mp_od = mother_pipe_diameter(area, st.session_state["thk_input"])
        result = {
            "shape": "Triangle",
            "inputs": {"side": st.session_state["tri_side"]},
            "thickness": st.session_state["thk_input"],
            "density": st.session_state["den_input"],
            "weight": w,
            "area_mm2": area,
            "extra": {"mother_OD": mp_od, "mother_ID": mp_od - 2 * st.session_state["thk_input"]},
            "dimensions_str": f"Equilateral {st.session_state['tri_side']} × t {st.session_state['thk_input']} mm",
        }
        st.success(f"Weight per meter: **{w:.3f} kg/m**")
        st.info(f"Equivalent Mother Pipe OD: **{mp_od:.2f} mm**, ID: **{mp_od - 2*st.session_state['thk_input']:.2f} mm**")

    # Save section
    st.markdown("---")
    st.subheader("Save this calculation")
    default_name = f"{result['shape']} | {result['dimensions_str']}"
    save_name = st.text_input("Name this calculation", value=default_name)
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
        st.session_state.saved[result["shape"]].append(record)
        st.success("Saved! Check the sidebar under the shape category.")
