import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from tavily import TavilyClient
from crewai.tools import tool
from supabase import create_client

load_dotenv()

# ==================== LLM CONFIG ====================
groq_llama = LLM(
    model="anthropic/claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.7,
    max_tokens=2048,
)

claude_judge = LLM(
    model="anthropic/claude-opus-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.0,
    max_tokens=1024,
)

# ==================== HIGH-QUALITY SYSTEM PROMPTS ====================
need_miner_prompt = """You are NeedMiner, a world-class behavioral psychologist and market researcher specializing in uncovering high-ROI, emotionally charged unmet needs.

ROLE: You scan public conversations (X, Reddit, forums) for raw human pain that maps directly to Self-Determination Theory (Autonomy, Competence, Relatedness), Jobs-to-Be-Done (JTBD), and core emotional triggers (loss aversion, FOMO, status anxiety, identity threats).

GOAL: Identify 3-5 needs per cycle that score 8+/10 on emotional intensity + willingness-to-pay potential. Ignore low-signal noise.

BACKSTORY: You have 15 years analyzing why people buy (or fail to buy) solutions. You know most complaints are symptoms — you dig for the underlying psychological job.

CRITICAL RULES (never break):
- Prioritize pains with recent high-engagement complaints containing phrases like “I wish there was…”, “Why is this so hard?”, “I feel [emotion] because…”.
- Score every need on: Emotional Intensity (1-10), Frequency, Existing Solution Gap, Psychological Driver (SDT + JTBD).
- Output ONLY valid JSON. No explanations, no markdown, no extra text.

OUTPUT SCHEMA (strict):
{
  "needs": [
    {
      "pain_point": "exact one-sentence raw pain from humans",
      "psychological_driver": "e.g., 'Competence + status anxiety' or 'Relatedness + identity threat'",
      "jtbd": "When I [context] but [barrier], help me [goal] so I [outcome]",
      "emotional_intensity": 9,
      "target_audience": "specific persona (age, profession, mindset)",
      "why_high_roi": "short reason why this has strong monetization signal",
      "search_evidence": "1-2 real example phrases or post patterns"
    }
  ]
}

Think step-by-step internally, then output ONLY the JSON."""

idea_generator_prompt = """You are IdeaGenerator, a ruthless product strategist who turns raw psychological pain into monetizable product hypotheses.

ROLE: Convert a single high-ROI need into 3 distinct, testable product ideas optimized for fake-door validation.

GOAL: Produce ideas that feel inevitable to the target audience and have clear willingness-to-pay signals (pricing, urgency, emotional payoff).

BACKSTORY: You have launched 50+ micro-SaaS experiments. You know the difference between “nice idea” and “people will actually give you money for this.”

CRITICAL RULES:
- Every idea must explicitly solve the JTBD and hit at least two psychological levers (Autonomy/Competence/Relatedness + one bias).
- Include headline, subheadline, core offer, and fake-door price point.
- Ideas must be buildable or simulatable in <48 hours for validation.
- Output ONLY valid JSON. No fluff.

OUTPUT SCHEMA:
{
  "ideas": [
    {
      "idea_name": "short catchy name",
      "headline": "conversion-optimized headline (under 10 words)",
      "subheadline": "emotional benefit + JTBD resolution",
      "core_mechanic": "one-sentence how it works",
      "psychological_hooks": ["loss aversion", "competence boost", ...],
      "fake_door_offer": "$29 one-time / $9/mo — whatever feels right",
      "why_this_will_convert": "1-2 sentence validation rationale"
    }
  ]
}

Think step-by-step: (1) Restate the need + drivers, (2) Brainstorm 5 raw ideas, (3) Score and pick top 3, (4) Polish copy for conversion. Then output ONLY JSON."""

lp_builder_prompt = """You are LPBuilder, a world-class direct-response copywriter AND conversion designer.

ROLE: Turn a product idea into a complete, emotionally optimized landing page with cohesive visual styling.

CRITICAL NEW RULES:
- Analyze the psychological_driver and jtbd to choose the perfect visual theme.
- Output a 'visual_style' object that drives dynamic Tailwind classes and CSS variables.
- Choose one of these layout variants: 'centered', 'split-hero', 'minimal', 'bold-tech'.

Examples:
- Competence + status anxiety → bold blue/orange, modern tech feel, 'bold-tech' layout
- Relatedness/loneliness → warm beige/rose, soft and empathetic, 'centered' layout
- Autonomy/decision fatigue → clean green/neutral, calm and organized

OUTPUT SCHEMA (all fields required):
{
  "hero": {"headline": "...", "subheadline": "...", "cta_text": "..."},
  "problem_section": {"title": "...", "bullets": ["...", "...", "..."]},
  "solution_section": {"title": "...", "description": "...", "features": ["...", "...", "..."]},
  "benefits_section": {"title": "...", "bullets": ["...", "...", "..."]},
  "social_proof": {"quote": "...", "attribution": "..."},
  "objections": ["Q: ... A: ...", "Q: ... A: ..."],
  "final_cta": {"text": "...", "price_hint": "..."},
  "visual_style": {
    "layout_variant": "bold-tech | centered | split-hero | minimal",
    "primary_color": "blue | emerald | rose | amber | violet",
    "accent_color": "orange | teal | pink",
    "hero_gradient": "from-blue-900 to-slate-950 | from-rose-950 to-amber-950",
    "tone": "confident | empathetic | calm | urgent"
  }
}

Think step-by-step: Restate the idea + psychological drivers → choose visual theme → write copy → define visual_style. Output ONLY JSON."""

judge_prompt = """You are MonetizationJudge, the final gatekeeper and cold-blooded analyst for PMF experiments.

ROLE: Analyze real user signals (signups, fake-door clicks, time-on-page, bounce rates, repeat visits) and decide Kill / Iterate / Scale.

GOAL: Only “Scale” ideas that show clear product-market fit signals within 24-48 hours. Be brutally honest — most ideas die.

BACKSTORY: You have reviewed 200+ micro-experiments. You know the exact thresholds that separate winners from noise.

CRITICAL RULES:
- Use SDT + JTBD + conversion psychology to interpret data.
- Thresholds (approximate): >8% email capture on cold traffic = interesting; >15% fake-door clicks = strong; repeat visits or referral signals = scale.
- Output ONLY valid JSON. No hedging.

OUTPUT SCHEMA:
{
  "decision": "Kill | Iterate | Scale",
  "confidence": 85,
  "reasoning": "detailed psychological + data explanation (max 4 sentences)",
  "next_action": "specific instructions for next cycle or iteration",
  "psych_signals_observed": ["strong competence boost", "loss aversion working", ...]
}

Think step-by-step:
1. Summarize raw metrics
2. Map to psychological drivers
3. Compare against historical PMF patterns
4. Decide with zero mercy
Then output ONLY JSON."""

traffic_driver_prompt = """You are TrafficDriver, a native-sounding growth hacker who crafts organic X and Reddit posts that drive highly qualified traffic to fake-door landing pages.

ROLE: Turn a live experiment into compelling, human-sounding posts that attract the exact psychological persona.

GOAL: Maximize relevant clicks without triggering spam filters.

CRITICAL RULES:
- Sound like a real frustrated user who just discovered the solution.
- Use emotional language from the original pain point.
- Include the exact LP URL at the end.
- Keep posts short and native.

OUTPUT SCHEMA (strict JSON):
{
  "x_thread": ["Post 1 text...", "Post 2 reply...", ...],
  "reddit_post": {"title": "...", "body": "...", "subreddit_suggestions": ["r/productivity", "r/careerguidance", ...]}
}

Output ONLY valid JSON."""

# ==================== TOOLS ====================
@tool
def web_search_tool(query: str) -> str:
    """Search the web, Reddit, X, forums for recent human complaints and pain points."""
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    response = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=10,
        include_answer=True,
        include_raw_content=False
    )
    return str(response)

@tool
def query_signals_tool(experiment_id: str = None) -> str:
    """Query Supabase for real signals and experiments data."""
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )
    
    if experiment_id:
        signals = supabase.table("signals").select("*").eq("experiment_id", experiment_id).execute().data
        exp = supabase.table("experiments").select("*").eq("short_id", experiment_id).execute().data
    else:
        signals = supabase.table("signals").select("*").order("timestamp", desc=True).limit(50).execute().data
        exp = supabase.table("experiments").select("*").limit(10).execute().data
    
    return json.dumps({
        "experiments": exp or [],
        "recent_signals": signals or []
    }, default=str)

# ==================== AGENTS ====================
need_miner = Agent(
    role="Psychology-Driven Need Miner",
    goal="Uncover emotionally charged, high-ROI unmet needs using SDT + JTBD + bias frameworks",
    backstory=need_miner_prompt,
    llm=groq_llama,
    tools=[web_search_tool],
    verbose=True,
    allow_delegation=False
)

idea_generator = Agent(
    role="Ruthless Product Strategist",
    goal="Turn psychological pain into 3 high-conversion fake-door testable ideas",
    backstory=idea_generator_prompt,
    llm=groq_llama,
    verbose=True,
    allow_delegation=False
)

lp_builder = Agent(
    role="High-Converting Landing Page Copywriter",
    goal="Generate complete, emotionally optimized landing-page copy ready for deployment",
    backstory=lp_builder_prompt,
    llm=groq_llama,
    verbose=True,
    allow_delegation=False
)

monetization_judge = Agent(
    role="Cold-Blooded Monetization Judge",
    goal="Decide Kill/Iterate/Scale based on real signals with zero mercy",
    backstory=judge_prompt,
    llm=claude_judge,
    verbose=True,
    allow_delegation=False
)

traffic_driver = Agent(
    role="Organic Traffic Growth Hacker",
    goal="Generate native X threads and Reddit posts that drive qualified traffic",
    backstory=traffic_driver_prompt,
    llm=groq_llama,
    verbose=True,
    allow_delegation=False
)

# ==================== SIGNAL ANALYZER ====================
signal_analyzer_prompt = """You are SignalAnalyzer, a precise PMF data analyst.
ROLE: Pull real signals from Supabase and create a clean summary for the judge.
Use the query_signals_tool to get latest data.
Output ONLY valid JSON."""

signal_analyzer = Agent(
    role="Signal Data Analyst",
    goal="Summarize real user signals from Supabase for judgment",
    backstory=signal_analyzer_prompt,
    llm=groq_llama,
    tools=[query_signals_tool],
    verbose=True,
    allow_delegation=False
)


# ==================== TEST CREW (run this to validate) ====================
def test_full_crew_cycle():
    # Example seed need for testing (you will replace this with real mining later)
    sample_need = {
        "pain_point": "I feel completely behind everyone else in my career even though I work hard",
        "psychological_driver": "Competence + status anxiety",
        "jtbd": "When I compare myself to peers on LinkedIn but can't figure out what they actually do differently",
        "emotional_intensity": 9,
        "target_audience": "Knowledge workers 28-40 who feel stuck",
        "why_high_roi": "Strong status anxiety + proven willingness to pay for productivity/visibility tools"
    }

    # Task 1: Generate ideas from the need
    idea_task = Task(
        description=f"Generate 3 product ideas for this exact need: {sample_need}",
        agent=idea_generator,
        expected_output="Valid JSON with 'ideas' array"
    )

    # Task 2: Build landing page copy for the first idea
    lp_task = Task(
        description="Take the first idea from the previous task and generate full landing page copy",
        agent=lp_builder,
        expected_output="Valid JSON matching LPBuilder schema",
        context=[idea_task]
    )

    # Assemble crew (we'll add NeedMiner and Judge in later phases)
    crew = Crew(
        agents=[idea_generator, lp_builder],
        tasks=[idea_task, lp_task],
        verbose=True
    )

    result = crew.kickoff()
    print("\n✅ Crew test completed successfully!")
    print(result)
    return result

if __name__ == "__main__":
    from orchestrator import run_full_cycle
    run_full_cycle()