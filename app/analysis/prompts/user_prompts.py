import json
from datetime import datetime


class UserPromptBuilder:
    """
    Builds dynamic user prompts per analysis cycle.
    System prompts live in system_prompts.py — never mix them here.
    """

    def build_batch_summary_prompt(
        self,
        posts: list[dict],
        batch_index: int,
        total_batches: int,
        world_context: str | None = None,
    ) -> str:
        avg_caps = sum(p["caps_ratio"] for p in posts) / max(len(posts), 1)
        total_exclamations = sum(p["exclamation_count"] for p in posts)
        has_grievance = sum(1 for p in posts if p.get("has_grievance"))
        has_aggression = sum(1 for p in posts if p.get("has_aggression"))
        has_rally = sum(1 for p in posts if p.get("has_rally"))
        has_nickname = sum(1 for p in posts if p.get("has_nickname"))

        posts_text = "\n---\n".join([
            (
                f"[{i + 1}] {p['posted_at']} "
                f"| Type: {p['post_type'].upper()} "
                f"| Signal: {p['signal_strength']}"
                f"| Caps: {p['caps_ratio']:.0%}"
                f"| Exclamations: {p['exclamation_count']}"
                + (f"| ⚑ nickname" if p.get("has_nickname") else "")
                + (f"| ⚑ grievance" if p.get("has_grievance") else "")
                + (f"| ⚑ aggression" if p.get("has_aggression") else "")
                + (f"| ⚑ rally" if p.get("has_rally") else "")
                + (f"\nLocal mood: {p['local_analysis']['zeroshot_mood']['label']} ({p['local_analysis']['zeroshot_mood']['score']:.0%})" if p.get("local_analysis") and p["local_analysis"].get("zeroshot_mood") else "")
                + (f"\nTop emotions: {', '.join(e['label'] for e in p['local_analysis']['top_emotions'])}" if p.get("local_analysis") and p["local_analysis"].get("top_emotions") else "")
                + f"\n{p['analysis_text']}\n"
                f"Likes: {p['likes']} | Reposts: {p['reposts']}"
            )
            for i, p in enumerate(posts)
        ])

        world_section = ""
        if world_context:
            world_section = f"""
## WORLD CONTEXT (what is happening right now)
{world_context}
Use this to understand WHY he may be posting about certain topics.
A post about tariffs means something different if markets just crashed.
A post about courts means something different if a ruling just dropped.
"""

        return f"""
## BATCH {batch_index + 1} of {total_batches}
Date: {datetime.now().strftime("%Y-%m-%d")}
Time window: {posts[0]['posted_at']} to {posts[-1]['posted_at']}
Post count: {len(posts)}

## AGGREGATE SIGNALS THIS BATCH
- Avg caps ratio: {avg_caps:.2%}
- Total exclamations: {total_exclamations}
- Posts with nickname attacks: {has_nickname}/{len(posts)}
- Posts with grievance language: {has_grievance}/{len(posts)}
- Posts with aggression language: {has_aggression}/{len(posts)}
- Posts with rally language: {has_rally}/{len(posts)}

## POST TYPE GUIDE
- ORIGINAL   = his own words, highest mood signal
- LINK_SHARE = what he CHOSE to amplify, reveals narrative even without his words
- RETRUTH    = background noise, lowest signal
{world_section}
## POSTS (chronological, with local model signals)
{posts_text}

## RESPOND WITH THIS EXACT JSON SCHEMA
{{
  "batch_index": {batch_index},
  "batch_time_window": "{posts[0]['posted_at']} to {posts[-1]['posted_at']}",
  "dominant_mood": "",
  "secondary_mood": "",
  "intensity": "low|medium|high|frenetic",
  "trajectory": "escalating|stable|de-escalating",
  "key_themes": [],
  "notable_signals": [],
  "world_context_relevance": "<how current events connect to what he is posting about>",
  "mood_shifts": [{{"at_post_index": 0, "shift_from": "", "shift_to": "", "trigger_hint": ""}}],
  "batch_summary": "<2-3 sentence plain english summary>"
}}
"""

    def build_mood_synthesis_prompt(
        self,
        state: dict,
        new_batch_summary: dict,
        new_posts: list[dict],
        rag_context: list[str] | None = None,
        world_context: str | None = None,
    ) -> str:
        summaries_text = "\n".join([
            f"Batch {i + 1} [{s.get('batch_time_window', '')}]: {s.get('batch_summary', '')}"
            f" — mood: {s.get('dominant_mood', '')} ({s.get('intensity', '')})"
            for i, s in enumerate(state.get("context_summaries", []))
        ])

        new_posts_text = "\n---\n".join([
            (
                f"[{p['posted_at']}] {p['analysis_text']}"
                + (f"\n  → Local: {p['local_analysis']['zeroshot_mood']['label']}" if p.get("local_analysis") and p["local_analysis"].get("zeroshot_mood") else "")
            )
            for p in new_posts
        ])

        rag_section = ""
        if rag_context:
            items = "\n".join(f"- {ctx}" for ctx in rag_context)
            rag_section = f"\n## HISTORICALLY SIMILAR MOOD PERIODS\n{items}\n"

        world_section = ""
        if world_context:
            world_section = f"""
## WORLD CONTEXT RIGHT NOW
{world_context}
Factor this heavily — his mood is almost always a reaction to something.
If markets are down, if a court ruled against him, if a rival made news —
these are the triggers. Connect the dots between world events and his posting behavior.
"""

        acc = state.get("accumulated", {})
        current = state.get("current_mood", {})

        return f"""
## DATE: {state['date']}
## CURRENT TIME: {datetime.now().strftime("%H:%M")} ET

## CURRENT MOOD STATE
Label: {current.get('label', 'UNKNOWN')}
Intensity: {current.get('intensity', 'unknown')}
Confidence: {current.get('confidence', 0):.0%}
Sustained since: {current.get('since', 'unknown')}

## TODAY'S HISTORY (previous batch summaries)
{summaries_text or 'No prior batches today — this is the first cycle.'}
{rag_section}{world_section}
## AGGREGATE SIGNALS TODAY
- Total posts: {acc.get('total_posts', 0)}
- Avg caps ratio: {acc.get('caps_ratio_avg', 0):.1%}
- Posts per hour: {acc.get('posts_per_hour', 0):.1f}
- Peak posts per hour: {acc.get('peak_posts_per_hour', 0):.1f}

## NEW BATCH JUST ANALYZED
{new_batch_summary.get('batch_summary', '')}
Dominant mood: {new_batch_summary.get('dominant_mood', '')} / Secondary: {new_batch_summary.get('secondary_mood', '')}
Intensity: {new_batch_summary.get('intensity', '')} | Trajectory: {new_batch_summary.get('trajectory', '')}
Key themes: {', '.join(new_batch_summary.get('key_themes', []))}
World context relevance: {new_batch_summary.get('world_context_relevance', 'N/A')}

## RAW NEW POSTS ({len(new_posts)} posts, with local model signals)
{new_posts_text}

## YOUR TASK
Synthesize everything above into a single updated mood assessment.

Think through:
1. What world events may have triggered this posting behavior?
2. Are the local model signals (zeroshot, emotions) consistent with the LLM analysis?
3. Is the current mood a continuation or a shift?
4. Is intensity building, peaking, or releasing?
5. What is the most likely emotional driver right now?

## RESPOND WITH THIS EXACT JSON SCHEMA
{{
  "current_mood": "",
  "intensity": "low|medium|high|frenetic",
  "confidence": 0.0,
  "mood_sustained_since": "",
  "shift_detected": false,
  "shift_from": null,
  "shift_to": null,
  "mood_arc_today": "escalating|sustained|volatile|de-escalating|mixed",
  "key_themes": [],
  "likely_trigger": "<what world event or situation is most likely driving this mood>",
  "signal_agreement": "high|medium|low",
  "analyst_note": "<2-3 sentence plain english note connecting world context to mood>"
}}
"""