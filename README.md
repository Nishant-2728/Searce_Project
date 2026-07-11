# Neural Taste Profile

A Streamlit prototype for personalized food recommendations using **14-dimensional flavor vectors** and rule-based context matching. Built for RFP 2 (Zomato) of a Searce internal assignment on AI & Digital Transformation.

## 🚀 Try it Live

**[Open the app on Streamlit Cloud](https://searceproject-8zfvnpxqbtxoo8aangt958.streamlit.app/)**

## What It Does

Instead of "you like Italian, so try this pasta," this app:

1. **Represents every dish** as a 14-dimensional flavor vector (spice, acidity, richness, warmth, crunch, umami, sweetness, bitterness, saltiness, freshness, moisture, aroma, chewiness, temperature-contrast)
2. **Reads your context** — time of day, mood, activity, and free-text cravings
3. **Computes a target flavor vector** using explicit, rule-based deltas (no AI/ML calls)
4. **Ranks dishes** by cosine similarity to your target
5. **Explains why** each match works (e.g., "High Warmth + Richness — driven by Late Night and Stressed")

**No LLM API calls. No external inference. Fully deterministic and auditable.**

---

## ⚡ Quick Start

### Online (Streamlit Cloud)
Just click the link above — no installation needed.

### Local Development

**Requirements:** Python 3.8+, `git`

```bash
# 1. Clone the repo
git clone https://github.com/Darkspood/Searce_Project.git
cd Searce_Project/app

# 2. Set up virtual environment & install dependencies
make install-dev

# 3. Run the app
make run
