# Literature review

Kept in sync with the Related Work section of the paper (`leangraph/paper.py`, `RELATED_WORK` and `REFERENCES`).
Edit it there, then regenerate the paper; this file is a copy for readers of the repository.

**Neural theorem proving in interactive provers.** Language models were first used to propose proof steps for
Metamath by Polu and Sutskever [1], then for Lean with co-training on proof artifacts [2]. Search-based provers
combine a step model with tree search [3, 4]. Draft-Sketch-Prove turns informal proofs into formal sketches whose
gaps are closed by automation [5]; Thor delegates sub-goals to hammers [6]. Whole-proof generation with repair from
prover errors was studied by Baldur for Isabelle [7], and COPRA frames proving as an in-context agent that sees
prover feedback [8]. Large-scale synthetic data and reinforcement learning from proof-assistant feedback drive the
DeepSeek-Prover line [9, 10].

**Retrieval of premises.** LeanDojo released Lean tooling, a benchmark with a novel-premises split, and ReProver, a
retrieval-augmented prover [11]; Magnushammer studied premise selection with contrastive training [12]. Our retriever
comparison uses classical BM25 [13], a general-purpose dense embedder not trained on Mathlib [14], and reciprocal-rank
fusion [15], so that no retriever has seen held-out premises in training.

**Benchmarks.** miniF2F [16], ProofNet [17] and PutnamBench [18] measure competition and textbook mathematics.
LeanGraph instead samples held-out statements from Mathlib itself, split by module boundary with everything
downstream banned, and adds statements written for the study, so that success can be compared between theorems
whose proofs could be remembered and theorems whose proofs could not.

**Self-repair and budgets.** Iterative refinement from feedback helps language models in several domains [19, 20],
but for code generation repair is not always better than drawing fresh samples at equal cost [21]. We therefore
compare repair against independent resampling at the same number of model calls, and report success as a function
of calls (pass@k in the sense of [22]).

## References

Bibliographic details below were entered from the authors' knowledge of the literature and should be checked
against the publishers' records before submission.

1. S. Polu, I. Sutskever. Generative Language Modeling for Automated Theorem Proving. arXiv:2009.03393, 2020.
2. J. M. Han, J. Rute, Y. Wu, E. W. Ayers, S. Polu. Proof Artifact Co-training for Theorem Proving with Language Models. ICLR 2022.
3. S. Polu, J. M. Han, K. Zheng, M. Baksys, I. Babuschkin, I. Sutskever. Formal Mathematics Statement Curriculum Learning. ICLR 2023.
4. G. Lample et al. HyperTree Proof Search for Neural Theorem Proving. NeurIPS 2022.
5. A. Q. Jiang, S. Welleck, J. P. Zhou et al. Draft, Sketch, and Prove: Guiding Formal Theorem Provers with Informal Proofs. ICLR 2023.
6. A. Q. Jiang, W. Li, S. Tworkowski et al. Thor: Wielding Hammers to Integrate Language Models and Automated Theorem Provers. NeurIPS 2022.
7. E. First, M. N. Rabe, T. Ringer, Y. Brun. Baldur: Whole-Proof Generation and Repair with Large Language Models. ESEC/FSE 2023.
8. A. Thakur, G. Tsoukalas, Y. Wen, J. Xin, S. Chaudhuri. An In-Context Learning Agent for Formal Theorem-Proving. COLM 2024.
9. H. Xin et al. DeepSeek-Prover: Advancing Theorem Proving in LLMs through Large-Scale Synthetic Data. arXiv:2405.14333, 2024.
10. H. Xin et al. DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback for Reinforcement Learning and Monte-Carlo Tree Search. arXiv:2408.08152, 2024.
11. K. Yang, A. M. Swope, A. Gu et al. LeanDojo: Theorem Proving with Retrieval-Augmented Language Models. NeurIPS 2023 (Datasets and Benchmarks).
12. M. Mikuła et al. Magnushammer: A Transformer-Based Approach to Premise Selection. ICLR 2024.
13. S. Robertson, H. Zaragoza. The Probabilistic Relevance Framework: BM25 and Beyond. Foundations and Trends in Information Retrieval, 2009.
14. S. Xiao, Z. Liu, P. Zhang, N. Muennighoff. C-Pack: Packaged Resources To Advance General Chinese Embedding. arXiv:2309.07597, 2023.
15. G. V. Cormack, C. L. A. Clarke, S. Büttcher. Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods. SIGIR 2009.
16. K. Zheng, J. M. Han, S. Polu. miniF2F: a Cross-System Benchmark for Formal Olympiad-Level Mathematics. ICLR 2022.
17. Z. Azerbayev et al. ProofNet: Autoformalizing and Formally Proving Undergraduate-Level Mathematics. arXiv:2302.12433, 2023.
18. G. Tsoukalas et al. PutnamBench: Evaluating Neural Theorem-Provers on the Putnam Mathematical Competition. NeurIPS 2024 (Datasets and Benchmarks).
19. A. Madaan et al. Self-Refine: Iterative Refinement with Self-Feedback. NeurIPS 2023.
20. N. Shinn et al. Reflexion: Language Agents with Verbal Reinforcement Learning. NeurIPS 2023.
21. T. X. Olausson et al. Is Self-Repair a Silver Bullet for Code Generation? ICLR 2024.
22. M. Chen et al. Evaluating Large Language Models Trained on Code. arXiv:2107.03374, 2021.
23. L. de Moura, S. Ullrich. The Lean 4 Theorem Prover and Programming Language. CADE 2021.
24. The mathlib Community. The Lean Mathematical Library. CPP 2020.
25. Q. McNemar. Note on the sampling error of the difference between correlated proportions or percentages. Psychometrika, 1947.
26. E. B. Wilson. Probable inference, the law of succession, and statistical inference. JASA, 1927.
27. S. Holm. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 1979.
