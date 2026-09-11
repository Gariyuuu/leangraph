"""The one canonical display name for each agent configuration (figures, README, paper tables)."""

CONFIG_LABELS = {
    "template": "Template (no LLM)",
    "direct": "Direct",
    "direct_at4": "Direct ×4",
    "repair": "Repair",
    "rag": "Retrieval",
    "rag_repair": "Retrieval + repair",
    "full": "Full (plan + retrieval + repair)",
    "rag_repair_bm25": "BM25 retrieval + repair",
    "rag_repair_dense": "Dense retrieval + repair",
    "full_no_retrieval": "Full − retrieval",
    "full_no_feedback": "Full − compiler feedback",
    "full_no_memory": "Full − memory",
    "full_no_skeleton": "Full − skeleton",
    "direct_prompt_b": "Direct (paraphrased prompt)",
    "repair_prompt_b": "Repair (paraphrased prompt)",
    "direct_think": "Direct (reasoning on)",
    "repair_think": "Repair (reasoning on)",
    "rag_repair_think": "Retrieval + repair (reasoning on)",
    "full_think": "Full (reasoning on)",
}

# Configurations labelled on crowded charts; the rest are drawn as unlabelled points.
HEADLINE = ("direct", "direct_at4", "repair", "rag", "rag_repair", "full")
