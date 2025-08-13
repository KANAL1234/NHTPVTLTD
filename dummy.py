import streamlit as st
import requests

# --- SETTINGS ---
OWNER_REPO = "KANAL1234/NHTPVTLTD"
BRANCH = "main"
TEST_FILE = "assets/saved_calcs.json"

st.title("🔑 GitHub Token Test")

# Check token in secrets
if "GITHUB_TOKEN" not in st.secrets or not st.secrets["GITHUB_TOKEN"]:
    st.error("❌ GITHUB_TOKEN not found in Streamlit secrets.")
    st.stop()

token = st.secrets["GITHUB_TOKEN"]

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# 1️⃣ Test read permissions
url_read = f"https://api.github.com/repos/{OWNER_REPO}/contents/{TEST_FILE}?ref={BRANCH}"
resp_read = requests.get(url_read, headers=headers)

st.subheader("1️⃣ Read Test")
st.write("GET", url_read)
st.write("Status:", resp_read.status_code, resp_read.reason)
try:
    st.json(resp_read.json())
except:
    st.write(resp_read.text)

# 2️⃣ Test write permissions (no actual change, just check repo info)
url_repo = f"https://api.github.com/repos/{OWNER_REPO}"
resp_repo = requests.get(url_repo, headers=headers)

st.subheader("2️⃣ Repo Access Test")
st.write("GET", url_repo)
st.write("Status:", resp_repo.status_code, resp_repo.reason)
try:
    st.json(resp_repo.json())
except:
    st.write(resp_repo.text)

# 3️⃣ Test commit creation (dry-run using /git/refs)
url_refs = f"https://api.github.com/repos/{OWNER_REPO}/git/refs/heads/{BRANCH}"
resp_refs = requests.get(url_refs, headers=headers)

st.subheader("3️⃣ Branch Ref Test")
st.write("GET", url_refs)
st.write("Status:", resp_refs.status_code, resp_refs.reason)
try:
    st.json(resp_refs.json())
except:
    st.write(resp_refs.text)

st.info("✅ If all three tests return 200 OK and show valid JSON, your token works.")
