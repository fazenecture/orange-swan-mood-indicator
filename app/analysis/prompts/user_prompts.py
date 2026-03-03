import json
from datetime import datetime

# Max recent summaries to send in full — older ones get compressed
_MAX_RECENT_SUMMARIES = 5

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
                f"| Signal: {p['signal_strength']} "
                f"| Caps: {p['caps_ratio']:.0%} "
                f"| !!!: {p['exclamation_count']}"
                + (" | ⚑ nickname" if p.get("has_nickname") else "")
                + (" | ⚑ grievance" if p.get("has_grievance") else "")
                + (" | ⚑ aggression" if p.get("has_aggression") else "")
                + (" | ⚑ rally" if p.get("has_rally") else "")
                + (
                    f"\nLocal: {p['local_analysis']['zeroshot_mood']['label']} "
                    f"({p['local_analysis']['zeroshot_mood']['score']:.0%}) | "
                    f"Emotions: {', '.join(e['label'] for e in p['local_analysis']['top_emotions'][:2])}"
                    if p.get("local_analysis") and p["local_analysis"].get("zeroshot_mood")
                    else ""
                )
                + f"\n{p['analysis_text']}\n"
                + f"♥ {p['likes']} | ↺ {p['reposts']}"
            )
            for i, p in enumerate(posts)
        ])

        world_section = ""
        if world_context:
            world_section = f"""
## WORLD CONTEXT
{world_context}
Use this to understand WHY he may be posting about certain topics.
"""

        return f"""## BATCH {batch_index + 1}/{total_batches} | {datetime.now().strftime("%Y-%m-%d")} | {posts[0]['posted_at']} → {posts[-1]['posted_at']}
Posts: {len(posts)} | Avg caps: {avg_caps:.0%} | Exclamations: {total_exclamations} | Nicknames: {has_nickname} | Grievance: {has_grievance} | Aggression: {has_aggression} | Rally: {has_rally}

## POST TYPE GUIDE
ORIGINAL=his words (highest signal) | LINK_SHARE=what he amplifies (medium) | RETRUTH=noise (lowest)
{world_section}
## POSTS
{posts_text}

## NOTABLE SIGNALS RULE
2-3 direct quotes from posts illustrating mood. No post numbers. Use his actual words.
Example: "TOTAL WITCH HUNT!!!" not "Post 3 had aggressive language"

## RESPOND JSON ONLY — NO PREAMBLE
{{
  "batch_index": {batch_index},
  "batch_time_window": "{posts[0]['posted_at']} to {posts[-1]['posted_at']}",
  "dominant_mood": "",
  "secondary_mood": "",
  "intensity": "low|medium|high|frenetic",
  "trajectory": "escalating|stable|de-escalating",
  "key_themes": [],
  "notable_signals": ["<direct quote>"],
  "world_context_relevance": "<1 sentence>",
  "mood_shifts": [{{"at_post_index": 0, "shift_from": "", "shift_to": "", "trigger_hint": ""}}],
  "batch_summary": "<2-3 sentences>"
}}"""

    def build_mood_synthesis_prompt(
        self,
        state: dict,
        new_batch_summary: dict,
        new_posts: list[dict],
        rag_context: list[str] | None = None,
        world_context: str | None = None,
    ) -> str:
        # ── Cap summaries to save tokens ──────────────────────────────────────
        all_summaries = state.get("context_summaries", [])
        recent_summaries = all_summaries[-_MAX_RECENT_SUMMARIES:]
        older_summaries = all_summaries[:-_MAX_RECENT_SUMMARIES]

        # Compress older summaries into a single line
        older_text = ""
        if older_summaries:
            moods = [s.get("dominant_mood", "") for s in older_summaries if s.get("dominant_mood")]
            dominant = max(set(moods), key=moods.count) if moods else "unknown"
            intensities = [s.get("intensity", "") for s in older_summaries if s.get("intensity")]
            peak = "frenetic" if "frenetic" in intensities else "high" if "high" in intensities else dominant
            older_text = (
                f"EARLIER TODAY ({len(older_summaries)} batches compressed): "
                f"predominant mood {dominant}, peak intensity {peak}\n"
            )

        recent_text = "\n".join([
            f"[{s.get('batch_time_window', '')}] "
            f"{s.get('dominant_mood', '')} ({s.get('intensity', '')}) — "
            f"{s.get('batch_summary', '')}"
            for s in recent_summaries
        ])

        summaries_text = older_text + recent_text if (older_text or recent_text) else "No prior batches today."

        # ── Raw posts — only included for Opus (high signal cycles) ──────────
        new_posts_text = ""
        if new_posts:
            new_posts_text = "\n## RAW NEW POSTS\n" + "\n---\n".join([
                (
                    f"[{p['posted_at']}] {p['analysis_text']}"
                    + (
                        f"\n  → {p['local_analysis']['zeroshot_mood']['label']}"
                        if p.get("local_analysis") and p["local_analysis"].get("zeroshot_mood")
                        else ""
                    )
                )
                for p in new_posts
            ])

        rag_section = ""
        if rag_context:
            items = "\n".join(f"- {ctx}" for ctx in rag_context[:3])  # cap to 3
            rag_section = f"\n## HISTORICAL PATTERNS\n{items}\n"

        world_section = ""
        if world_context:
            world_section = f"\n## WORLD CONTEXT\n{world_context}\n"

        acc = state.get("accumulated", {})
        current = state.get("current_mood", {})

        return f"""## {state['date']} {datetime.now().strftime("%H:%M")} ET

## CURRENT MOOD
{current.get('label', 'UNKNOWN')} | {current.get('intensity', 'unknown')} | {current.get('confidence', 0):.0%} confidence | since {current.get('since', 'unknown')}

## TODAY'S HISTORY
{summaries_text}
{rag_section}{world_section}
## TODAY'S AGGREGATE
Posts: {acc.get('total_posts', 0)} | Caps avg: {acc.get('caps_ratio_avg', 0):.0%} | Posts/hr: {acc.get('posts_per_hour', 0):.1f} | Peak/hr: {acc.get('peak_posts_per_hour', 0):.1f}

## NEW BATCH
Mood: {new_batch_summary.get('dominant_mood', '')} / {new_batch_summary.get('secondary_mood', '')} | Intensity: {new_batch_summary.get('intensity', '')} | Trajectory: {new_batch_summary.get('trajectory', '')}
Themes: {', '.join(new_batch_summary.get('key_themes', []))}
Summary: {new_batch_summary.get('batch_summary', '')}
Context: {new_batch_summary.get('world_context_relevance', 'N/A')}
{new_posts_text}

## TASK
Has mood shifted from {current.get('label', 'UNKNOWN')}? Is intensity rising or falling? What is the emotional driver right now?

## RESPOND JSON ONLY — NO PREAMBLE
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
  "likely_trigger": "<1 sentence>",
  "signal_agreement": "high|medium|low",
  "analyst_note": "<2 sentences max>"
}}"""