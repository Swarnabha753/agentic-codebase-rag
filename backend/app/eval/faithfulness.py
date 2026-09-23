"""
Lightweight faithfulness/relevance scoring for agent answers — a scaled-down
version of RAGAS-style RAG evaluation.

Faithfulness: does the answer's content actually appear in / follow from the
retrieved chunks, or is the model making things up beyond what was retrieved?

We use the LLM itself as the judge (a common, practical pattern) rather than
building a separate model — cheap, fast, and good enough for a portfolio-grade
eval loop. In interviews, be upfront about this trade-off: "LLM-as-judge is
not as rigorous as a trained classifier, but it's the standard lightweight
approach and correlates well with human judgment for faithfulness checks."
"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def score_faithfulness(question: str, answer: str, context_text: str) -> dict:
    prompt = f"""You are evaluating whether an AI-generated answer is faithful to its source context.

Question: {question}

Answer to evaluate:
{answer}

Source context it was supposed to be based on:
{context_text}

Score the answer from 0.0 to 1.0 on:
- faithfulness: does every claim in the answer trace back to the source context (no hallucinated facts)?
- relevance: does the answer actually address the question asked? (do not penalize the answer for omitting details the question did not ask about)

Respond ONLY with JSON in this exact format, no other text:
{{"faithfulness": 0.0, "relevance": 0.0, "reason": "one short sentence"}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    # models sometimes wrap JSON in markdown fences despite instructions — strip if present
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"faithfulness": None, "relevance": None, "reason": f"eval parse failed: {raw[:100]}"}