# Neural Taste Profile

A Streamlit prototype for personalized food recommendations, built for **RFP 2 (Zomato)** of a Searce internal assignment on AI & Digital Transformation.

## What It Does

Instead of "you like Italian, so try this pasta," this app:

1. **Represents every dish** as a 14-dimensional flavor vector (spice, acidity, richness, warmth, crunch, umami, sweetness, bitterness, saltiness, freshness, moisture, aroma, chewiness, temperature-contrast).
2. **Reads your real-time context** — live weather at your location, a simulated smartwatch connection (heart rate variability, calories burned, sleep score), a short mood quiz, and a free-text craving.
3. **Fuses all of that into a target flavor vector** with a single Claude Sonnet 5 call, which also returns a plain-language rationale for each dimension.
4. **Ranks dishes** by cosine similarity to that target vector.
5. **Explains why** each match works, using the LLM's own rationale — never a black box.

If the Claude API call fails for any reason (network issue, rate limit, refusal), the app falls back to a small deterministic baseline instead of crashing, and says so clearly in the UI.

## Quick Start

**Requirements:** Python 3.8+, `git`, an [Anthropic API key](https://console.anthropic.com/)

```bash
git clone https://github.com/Darkspood/Searce_Project.git
cd Searce_Project/app

make install-dev

cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY

make run
```

Without an API key, the app still runs — it just always shows the fallback banner instead of the real LLM-fused recommendations.

## Tests

```bash
make test          # or: make test-verbose
```

The full suite runs in under 2 seconds and makes zero real network or API calls — everything is mocked.

## 🚀 Quick Demo

Try the live application here:

👉 **https://searceproject-8zfvnpxqbtxoo8aangt958.streamlit.app/**

## Project Structure

See [`CLAUDE.md`](CLAUDE.md) for a full architecture breakdown (module-by-module) and contributor guidance.
