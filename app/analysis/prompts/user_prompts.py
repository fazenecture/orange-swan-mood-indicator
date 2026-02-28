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
    ) -> str:
        avg_caps = sum(p["caps_ratio"] for p in posts) / max(len(posts), 1)
        total_exclamations = sum(p["exclamation_count"] for p in posts)

        posts_text = "\n---\n".join([
            (
                f"[{i + 1}] {p['posted_at']} "
                f"| Type: {p['post_type'].upper()} "
                f"| Signal: {p['signal_strength']}\n"
                f"{p['analysis_text']}\n"
                f"Likes: {p['likes']} | Reposts: {p['reposts']}"
            )
            for i, p in enumerate(posts)
        ])

        return f"""
## BATCH {batch_index + 1} of {total_batches}
Time window: {posts[0]['posted_at']} to {posts[-1]['posted_at']}
Post count: {len(posts)}
Avg caps ratio: {avg_caps:.2f}
Total exclamations: {total_exclamations}

## POST TYPE GUIDE
- ORIGINAL   = his own words, highest mood signal
- LINK_SHARE = what he chose to amplify, medium signal
- RETRUTH    = background noise, lowest signal

## POSTS (chronological)
{posts_text}

## RESPOND WITH THIS EXACT JSON SCHEMA
{{
  "batch_index": {batch_index},
  "dominant_mood": "",
  "secondary_mood": "",
  "intensity": "low|medium|high|frenetic",
  "trajectory": "escalating|stable|de-escalating",
  "key_themes": [],
  "notable_signals": [],
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
    ) -> str:
        summaries_text = "\n".join([
            f"Batch {i + 1}: {s.get('batch_summary', '')}"
            for i, s in enumerate(state.get("context_summaries", []))
        ])

        new_posts_text = "\n---\n".join([
            f"[{p['posted_at']}] {p['analysis_text']}"
            for p in new_posts
        ])

        rag_section = ""
        if rag_context:
            items = "\n".join(f"- {ctx}" for ctx in rag_context)
            rag_section = f"\n## HISTORICALLY SIMILAR MOOD PERIODS\n{items}\n"

        acc = state.get("accumulated", {})
        current = state.get("current_mood", {})

        return f"""
## DATE: {state['date']}

## CURRENT MOOD STATE
Label: {current.get('label', 'UNKNOWN')}
Intensity: {current.get('intensity', 'unknown')}
Confidence: {current.get('confidence', 0)}
Sustained since: {current.get('since', 'unknown')}

## TODAY'S HISTORY (previous batch summaries)
{summaries_text or 'No prior batches today.'}
{rag_section}
## AGGREGATE SIGNALS TODAY
- Total posts: {acc.get('total_posts', 0)}
- Avg caps ratio: {acc.get('caps_ratio_avg', 0):.3f}
- Posts per hour: {acc.get('posts_per_hour', 0):.1f}
- Peak posts per hour: {acc.get('peak_posts_per_hour', 0):.1f}

## NEW BATCH JUST ANALYZED
{new_batch_summary.get('batch_summary', '')}
Mood in batch: {new_batch_summary.get('dominant_mood', '')}
Intensity: {new_batch_summary.get('intensity', '')}

## RAW NEW POSTS ({len(new_posts)} posts)
{new_posts_text}

## YOUR TASK
Update the mood assessment given everything above.
- Has mood shifted from {current.get('label', 'UNKNOWN')}?
- Is intensity increasing, decreasing, or stable?
- What is his emotional state RIGHT NOW vs the arc of the whole day?

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
  "analyst_note": "<1-2 sentence plain english note>"
}}
"""
