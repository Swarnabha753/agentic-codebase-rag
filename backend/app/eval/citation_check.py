"""
Deterministic check: does every chunk ID the answer cites actually exist in
the context that was retrieved? Catches hallucinated citations — a failure
mode LLM-as-judge often misses (it "checks" faithfulness by re-reading the
same context, so it can be fooled by a plausible-looking but fake citation).
"""
import re


def extract_cited_ids(answer: str) -> list[str]:
    return re.findall(r"\[([^\[\]]+::[^\[\]]+:\d+)\]", answer)


def check_citations(answer: str, chunks_available: list[str]) -> dict:
    cited = extract_cited_ids(answer)
    available_set = set(chunks_available)
    valid = [c for c in cited if c in available_set]
    invalid = [c for c in cited if c not in available_set]

    return {
        "citations_found": len(cited),
        "citations_valid": len(valid),
        "citations_invalid": invalid,
        "citation_accuracy": (len(valid) / len(cited)) if cited else None,
    }