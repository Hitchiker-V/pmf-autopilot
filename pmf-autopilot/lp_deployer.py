import os
import json
import re
import uuid
import base64
import time
from dotenv import load_dotenv
import httpx
import jinja2
from supabase import create_client, Client


load_dotenv()

def extract_json_from_output(text: str) -> dict:
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    json_str = json_match.group(1) if json_match else text.strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
TEMPLATE_OWNER, TEMPLATE_REPO = os.getenv("GITHUB_TEMPLATE_REPO").split("/")

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def render_page(lp_data: dict, experiment_id: str) -> str:
    template_loader = jinja2.FileSystemLoader("templates")
    template_env = jinja2.Environment(loader=template_loader, autoescape=True)
    template = template_env.get_template("page.tsx.jinja")
    context = {
        **lp_data,                    # this already includes visual_style
        "experiment_id": experiment_id,
        "supabase_url": os.getenv("SUPABASE_URL").replace("https://", ""),
        "anon_key": os.getenv("SUPABASE_ANON_KEY")
    }
    return template.render(context)

def create_and_deploy_lp(idea: dict, lp_json: dict) -> str:
    experiment_id = str(uuid.uuid4())[:8]
    repo_name = f"pmf-exp-{experiment_id}"

    print(f"🔍 Creating repo: {repo_name}")

    # 1. Create from template
    create_url = f"https://api.github.com/repos/{TEMPLATE_OWNER}/{TEMPLATE_REPO}/generate"
    payload = {"owner": TEMPLATE_OWNER, "name": repo_name, "description": f"PMF Experiment {experiment_id}", "private": False}
    resp = httpx.post(create_url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 201:
        raise Exception(f"Create failed: {resp.text}")
    print(f"✅ Repo created: https://github.com/{TEMPLATE_OWNER}/{repo_name}")

    # 2. Wait for template generation to finish (GitHub populates files async)
    page_content = render_page(lp_json, experiment_id)
    commit_url = f"https://api.github.com/repos/{TEMPLATE_OWNER}/{repo_name}/contents/app/page.tsx"

    sha = None
    for attempt in range(20):
        get_resp = httpx.get(commit_url, headers=headers)
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
            print(f"✅ Template populated (attempt {attempt + 1}), sha={sha[:7]}")
            break
        print(f"⏳ Waiting for template files... (attempt {attempt + 1}, status {get_resp.status_code})")
        time.sleep(2)
    else:
        raise Exception(f"Template files never appeared at app/page.tsx after 40s")

    content_b64 = base64.b64encode(page_content.encode("utf-8")).decode("utf-8")

    commit_payload = {
        "message": "PMF Autopilot — dynamic landing page",
        "content": content_b64,
        "sha": sha
    }
    commit_resp = httpx.put(commit_url, json=commit_payload, headers=headers)
    if commit_resp.status_code not in (200, 201):
        raise Exception(f"Commit failed ({commit_resp.status_code}): {commit_resp.text}")
    print(f"✅ page.tsx committed (status {commit_resp.status_code})")

    final_url = f"https://{repo_name}.vercel.app"
    supabase.table("experiments").insert({
        "short_id": experiment_id,
        "idea_json": json.dumps(idea),
        "lp_url": final_url,
        "status": "live"
    }).execute()

    print(f"🚀 LIVE: {final_url}")
    return final_url

if __name__ == "__main__":
    # Quick test
    sample_lp = {
        "hero": {"headline": "Stop Feeling Behind Everyone Else", "subheadline": "AI that shows you exactly what your peers are doing differently — and helps you catch up in 7 days.", "cta_text": "Get My 7-Day Catch-Up Plan — $29"},
        "problem_section": {"title": "You're working hard but still falling behind", "bullets": ["LinkedIn makes you feel invisible", "Everyone else seems to be leveling up faster", "You don't know what to do next"]},
        "solution_section": {"title": "The solution you've been waiting for", "description": "Our AI scans public signals and gives you personalized, actionable steps.", "features": ["Daily insights", "Peer comparison", "7-day action plan"]},
        "final_cta": {"price_hint": "$29 one-time early access"}
    }
    sample_idea = {"idea_name": "CareerCatchup AI"}
    create_and_deploy_lp(sample_idea, sample_lp)