"""
RAG evaluation suite — Recall@k + LLM-as-judge.

Run with:
    python -m app.eval.evaluator --base-url http://localhost:8003

Metrics:
  - Recall@k       : does the correct chunk appear in the retrieved sources?
  - Answer hit     : does the answer contain all expected strings? (fast check)
  - LLM-as-judge   : Gemini scores faithfulness (1–5) + completeness (1–5) per answer
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"


def _load_golden_set() -> List[Dict[str, Any]]:
    with open(GOLDEN_SET_PATH) as f:
        return json.load(f)


async def _judge_answer(
    gemini_client,
    gemini_model: str,
    query: str,
    answer: str,
    expected_contains: List[str],
) -> Dict[str, Any]:
    """Use Gemini as a judge to score faithfulness and completeness (1–5 each)."""
    from google.genai import types

    prompt = (
        "You are an evaluator for a RAG (Retrieval-Augmented Generation) system.\n"
        "Rate the following answer on two dimensions, each scored 1–5:\n\n"
        "Faithfulness (1–5): Does the answer ONLY use information from the provided context? "
        "Does it avoid hallucinating facts not present in retrieved documents? "
        "(5 = fully grounded, no hallucination; 1 = contains fabricated info)\n\n"
        "Completeness (1–5): Does the answer fully address the question? "
        "(5 = complete answer covering all aspects; 1 = missing key information)\n\n"
        f"Question: {query}\n"
        f"Answer: {answer}\n"
        f"Expected to mention: {', '.join(expected_contains)}\n\n"
        'Output JSON only — no explanation outside the JSON:\n'
        '{"faithfulness": N, "completeness": N, "reason": "one-line reason"}'
    )

    try:
        response = await gemini_client.aio.models.generate_content(
            model=gemini_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(max_output_tokens=150),
        )
        match = re.search(r'\{.*?\}', response.text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        pass

    return {"faithfulness": None, "completeness": None, "reason": "judge_error"}


async def run_eval(base_url: str, top_k: int = 5, use_llm_judge: bool = True) -> None:
    golden = _load_golden_set()

    gemini_client = None
    gemini_model = "gemini-2.5-flash"
    if use_llm_judge:
        try:
            from google import genai
            from app.core.config import settings
            gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            gemini_model = settings.GEMINI_MODEL
        except Exception as e:
            print(f"  [warn] LLM judge disabled: {e}")
            use_llm_judge = False

    retrieval_hits = 0
    answer_hits = 0
    faithfulness_scores: List[float] = []
    completeness_scores: List[float] = []
    results = []

    print(f"\nRunning eval on {len(golden)} cases (top_k={top_k}, llm_judge={use_llm_judge})\n")

    async with httpx.AsyncClient(base_url=base_url, timeout=90) as client:
        for case in golden:
            try:
                resp = await client.post(
                    "/api/v1/chat/query",
                    json={"message": case["query"], "top_k": top_k},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  ERROR for '{case['query'][:60]}': {e}")
                results.append({"query": case["query"], "error": str(e)})
                continue

            sources_text = " ".join(s["content"] for s in data.get("sources", []))
            answer_text = data.get("response", "")

            retrieval_hit = all(
                kw.lower() in sources_text.lower()
                for kw in case["relevant_chunk_keywords"]
            )
            answer_hit = all(
                exp.lower() in answer_text.lower()
                for exp in case["expected_answer_contains"]
            )

            if retrieval_hit:
                retrieval_hits += 1
            if answer_hit:
                answer_hits += 1

            judge_scores: Dict[str, Any] = {}
            if use_llm_judge and gemini_client:
                judge_scores = await _judge_answer(
                    gemini_client,
                    gemini_model,
                    case["query"],
                    answer_text,
                    case["expected_answer_contains"],
                )
                if judge_scores.get("faithfulness") is not None:
                    faithfulness_scores.append(judge_scores["faithfulness"])
                if judge_scores.get("completeness") is not None:
                    completeness_scores.append(judge_scores["completeness"])

            r_icon = "✓" if retrieval_hit else "✗"
            a_icon = "✓" if answer_hit else "✗"
            f_score = f"F={judge_scores.get('faithfulness', '-')}" if judge_scores else ""
            c_score = f"C={judge_scores.get('completeness', '-')}" if judge_scores else ""
            extras = f" [{f_score} {c_score}]".strip() if (f_score or c_score) else ""
            print(f"  [{r_icon}{a_icon}]{extras} {case['query'][:65]}")

            if not retrieval_hit:
                print(f"       ↳ Missing in sources: {case['relevant_chunk_keywords']}")
            if not answer_hit:
                print(f"       ↳ Missing in answer: {case['expected_answer_contains']}")

            results.append({
                "query": case["query"],
                "retrieval_hit": retrieval_hit,
                "answer_hit": answer_hit,
                "num_sources": data.get("num_sources", 0),
                **judge_scores,
            })

    total = len(golden)
    print(f"\n{'='*65}")
    print(f"Retrieval Recall@{top_k} : {retrieval_hits}/{total} = {retrieval_hits/total:.0%}")
    print(f"Answer Accuracy      : {answer_hits}/{total} = {answer_hits/total:.0%}")
    if faithfulness_scores:
        print(f"Avg Faithfulness     : {sum(faithfulness_scores)/len(faithfulness_scores):.1f}/5")
    if completeness_scores:
        print(f"Avg Completeness     : {sum(completeness_scores)/len(completeness_scores):.1f}/5")
    print(f"{'='*65}\n")

    output_path = Path(__file__).parent / "eval_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Full results saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAG eval suite")
    parser.add_argument("--base-url", default="http://localhost:8003")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-llm-judge", action="store_true", help="Skip LLM-as-judge scoring")
    args = parser.parse_args()

    asyncio.run(run_eval(
        base_url=args.base_url,
        top_k=args.top_k,
        use_llm_judge=not args.no_llm_judge,
    ))
