import streamlit as st
import requests
import base64
from datetime import datetime

# --- SETTINGS ---
OWNER_REPO = "KANAL1234/NHTPVTLTD"
BRANCH = "main"
TEST_FILE = "assets/token_test.txt"

st.title("✍️ GitHub Token Write Test")

# Get token
if "GITHUB_TOKEN" not in st.secrets or not st.secrets["GITHUB_TOKEN"]:
    st.error("❌ GITHUB_TOKEN not found in Streamlit secrets.")
    st.stop()

token = st.secrets["GITHUB_TOKEN"]

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# Step 1: Get current SHA (if file exists)
url_content = f"https://api.github.com/repos/{OWNER_REPO}/contents/{TEST_FILE}?ref={BRANCH}"
resp_content = requests.get(url_content, headers=headers)

sha = None
if resp_content.status_code == 200:
    sha = resp_content.json().get("sha")
    st.write("ℹ️ File exists, updating...")
else:
    st.write("ℹ️ File does not exist, creating new one...")

# Step 2: Prepare new content
new_text = f"Token write test at {datetime.utcnow().isoformat()} UTC"
encoded_content = base64.b64encode(new_text.encode()).decode()

# Step 3: Push to GitHub
url_put = f"https://api.github.com/repos/{OWNER_REPO}/contents/{TEST_FILE}"
payload = {
    "message": "Token write test commit",
    "content": encoded_content,
    "branch": BRANCH
}
if sha:
    payload["sha"] = sha

resp_put = requests.put(url_put, headers=headers, json=payload)

# Step 4: Show result
if resp_put.status_code in (200, 201):
    st.success("✅ Write successful!")
    st.json(resp_put.json())
    st.markdown(f"[View file in GitHub](https://github.com/{OWNER_REPO}/blob/{BRANCH}/{TEST_FILE})")
else:
    st.error(f"❌ Write failed with {resp_put.status_code}")
    st.write(resp_put.text)
