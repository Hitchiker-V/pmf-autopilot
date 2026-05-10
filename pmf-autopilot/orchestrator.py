import os
from dotenv import load_dotenv
from crewai import Task, Crew
from crew import (
    need_miner,
    idea_generator,
    lp_builder,
    traffic_driver,
    signal_analyzer,
    monetization_judge,
)
from lp_deployer import create_and_deploy_lp, extract_json_from_output

load_dotenv()


def run_full_cycle():
    print("🚀 Starting FULL PMF Autopilot Cycle (with real NeedMiner + Tavily)...\n")

    # ====================== 1. REAL NEED MINING ======================
    need_mining_task = Task(
        description="""Use the web_search_tool to find 3-5 high-ROI, emotionally charged unmet needs right now.
Focus ONLY on recent high-engagement complaints containing phrases like:
"I wish there was a tool that…", "Why is this so hard?", "I feel [emotion] because…", "I'm so tired of…"
in the psychology categories: Competence/Status Anxiety, Relatedness/Loneliness, Autonomy/Decision Fatigue, Safety/Security.

Pick the SINGLE best need that scores highest on emotional intensity + willingness-to-pay potential.
Output ONLY valid JSON matching the NeedMiner OUTPUT SCHEMA.""",
        agent=need_miner,
        expected_output="Valid JSON matching NeedMiner schema"
    )

    # ====================== 2. IDEA GENERATION ======================
    idea_task = Task(
        description="Generate 3 distinct, high-conversion fake-door testable product ideas from the mined need",
        agent=idea_generator,
        expected_output="Valid JSON with 'ideas' array",
        context=[need_mining_task]
    )

    # ====================== 3. LANDING PAGE COPY ======================
    lp_task = Task(
        description="Take the FIRST idea and generate complete landing page copy using the exact LPBuilder schema",
        agent=lp_builder,
        expected_output="Valid JSON matching LPBuilder schema",
        context=[idea_task]
    )

    # ====================== 4. TRAFFIC COPY ======================
    traffic_task = Task(
        description="Generate native X thread + Reddit post for the live landing page",
        agent=traffic_driver,
        expected_output="Valid JSON with 'x_thread' and 'reddit_post'",
        context=[lp_task]
    )

    # ====================== RUN MAIN CREW ======================
    print("🤖 Running full agent crew (real web search + generation)...")
    crew = Crew(
        agents=[need_miner, idea_generator, lp_builder, traffic_driver],
        tasks=[need_mining_task, idea_task, lp_task, traffic_task],
        verbose=True
    )

    result = crew.kickoff()

    # ====================== PARSE + DEPLOY ======================
    lp_url = None
    try:
        lp_output = result.tasks_output[2].raw if hasattr(result, 'tasks_output') else str(result)
        lp_json = extract_json_from_output(lp_output)

        sample_idea = {"idea_name": lp_json.get("hero", {}).get("headline", "AutoIdea")[:40]}

        print("🚀 Deploying live landing page...")
        lp_url = create_and_deploy_lp(sample_idea, lp_json)

        traffic_output = result.tasks_output[3].raw if hasattr(result, 'tasks_output') else ""
        print("\n📣 TRAFFIC COPY READY:")
        print(traffic_output[:800] + "..." if len(traffic_output) > 800 else traffic_output)

        print(f"\n🎉 EXPERIMENT DEPLOYED: {lp_url}")
        print("👉 Go to Vercel → Import the new repo (one-time) and open the URL")
        print("👉 Submit the form to test signals")

    except Exception as e:
        print(f"❌ Deploy error: {e}")
        print("Raw result for debugging:")
        print(result)

    # ====================== 5. SIGNAL ANALYSIS + JUDGE ======================
    # print("\n⚖️ Running Signal Analyzer + Monetization Judge...")

    # analyze_task = Task(
    #     description="Use query_signals_tool to pull the latest signals and summarize all active experiments with key metrics",
    #     agent=signal_analyzer,
    #     expected_output="Valid JSON with experiment summaries and signal metrics"
    # )

    # judge_task = Task(
    #     description="Analyze the signal summary and give a final Kill / Iterate / Scale decision for each experiment",
    #     agent=monetization_judge,
    #     expected_output="Valid JSON with Kill/Iterate/Scale decisions per experiment",
    #     context=[analyze_task]
    # )

    # judge_crew = Crew(
    #     agents=[signal_analyzer, monetization_judge],
    #     tasks=[analyze_task, judge_task],
    #     verbose=True
    # )

    # judgment = judge_crew.kickoff()

    # print("\n⚖️ MONETIZATION JUDGE DECISIONS:")
    # print(judgment)
    # print("\n🎉 FULL CYCLE COMPLETE. Check your dashboard!")

    return lp_url


if __name__ == "__main__":
    run_full_cycle()
