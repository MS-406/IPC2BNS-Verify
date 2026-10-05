# IPC2BNS Experiment Master Report

## Overview

| Experiment ID | Status | Accuracy | R@1 | R@5 | MRR | Notes |
|---------------|--------|----------|-----|-----|-----|-------|
| smoke_test_rag | completed | 0.5600 | 0.0000 | 0.0000 | 0.0000 | |
| baseline_exact | failed | 0.0000 | 0.0000 | 0.0000 | 0.0000 | Failed due to syntax/formatting variations in queries |
| retrieval_bm25 | completed | 0.5600 | 0.5600 | 0.6320 | 0.5907 | |
| retrieval_tfidf | completed | 0.5600 | 0.5600 | 0.6400 | 0.5947 | |
| retrieval_dense_sbert | completed | 0.5600 | 0.5600 | 0.6000 | 0.5725 | |
| retrieval_hybrid_sbert | completed | 0.5680 | 0.5680 | 0.6640 | 0.5995 | Chosen: Local Hybrid Retriever |
| lstm_sbert | failed | 0.0000 | 0.0000 | 0.0000 | 0.0000 | Too heavy/overfit for direct lookup |
| rag_bm25 | completed | 0.5600 | 0.0000 | 0.0000 | 0.0000 | |
