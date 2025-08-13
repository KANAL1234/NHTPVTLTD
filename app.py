import streamlit as st
import math

# Default density (Mild Steel)
DENSITY_MS = 7850  

# ----- Calculation Functions -----
def weight_circle(OD, thickness, density):
    ID = OD - 2 * thickness
    if ID < 0:
        return 0
    area_mm2 = (math.pi / 4) * (OD**2 - ID**2)
    return area_mm2 * 1e-6 * density

def weight_square(OD, thickness, density):
    ID = OD - 2 * thickness
    if ID < 0:
        return 0
    area_mm2 = OD**2 - ID**2
    return area_mm2 * 1e-6 * density

def weight_rectangle(L, W, thickness, density):
    ID_L = L - 2 * thickness
    ID_W = W - 2 * thickness
    if ID_L < 0 or ID_W < 0:
        return 0
    area_mm2 = (L * W) - (ID_L * ID_W)
    return area_mm2 * 1e-6 * density

def weight_oval(major, minor, thickness, density):
    a_o = major / 2
    b_o = minor / 2
    a_i = a_o - thickness
    b_i = b_o - thickness
    if a_i < 0 or b_i < 0:
        return 0
    area_mm2 = math.pi * a_o * b_o - math.pi * a_i * b_i
    return area_mm2 * 1e-6 * density

def weight_triangle(side, thickness, density):
    s_o = side
    s_i = side - 2 * thickness / math.sin(math.radians(60))
    if s_i < 0:
        return 0
    outer_area = (math.sqrt(3) / 4) * s_o**2
    inner_area = (math.sqrt(3) / 4) * s_i**2
    area_mm2 = outer_area - inner_area
    return area_mm2 * 1e-6 * density

# ----- Streamlit UI -----
st.title("Pipe & Hollow Section Weight Calculator")

shape = st.selectbox(
    "Select Shape",
    ["Circle", "Square", "Rectangle", "Oval", "Triangle"]
)

thickness = st.number_input("Wall Thickness (mm)", min_value=0.1, value=1.0, step=0.1)
density = st.number_input("Material Density (kg/m³)", min_value=1000, value=DENSITY_MS)

if shape == "Circle":
    OD = st.number_input("Outer Diameter (mm)", min_value=1.0, value=25.0)
    if st.button("Calculate"):
        w = weight_circle(OD, thickness, density)
        st.success(f"Weight per meter: {w:.3f} kg/m")

elif shape == "Square":
    OD = st.number_input("Outer Side (mm)", min_value=1.0, value=25.0)
    if st.button("Calculate"):
        w = weight_square(OD, thickness, density)
        st.success(f"Weight per meter: {w:.3f} kg/m")

elif shape == "Rectangle":
    L = st.number_input("Outer Length (mm)", min_value=1.0, value=40.0)
    W = st.number_input("Outer Width (mm)", min_value=1.0, value=25.0)
    if st.button("Calculate"):
        w = weight_rectangle(L, W, thickness, density)
        st.success(f"Weight per meter: {w:.3f} kg/m")

elif shape == "Oval":
    major = st.number_input("Outer Major Axis (mm)", min_value=1.0, value=40.0)
    minor = st.number_input("Outer Minor Axis (mm)", min_value=1.0, value=25.0)
    if st.button("Calculate"):
        w = weight_oval(major, minor, thickness, density)
        st.success(f"Weight per meter: {w:.3f} kg/m")

elif shape == "Triangle":
    side = st.number_input("Outer Side Length (mm)", min_value=1.0, value=25.0)
    if st.button("Calculate"):
        w = weight_triangle(side, thickness, density)
        st.success(f"Weight per meter: {w:.3f} kg/m")
