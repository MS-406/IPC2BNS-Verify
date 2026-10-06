"""
error_analyzer.py — Phase 13: Error Analysis

Analyzes predictions to categorize errors:
- Wrong section (close vs. distant)
- Repealed section predicted
- Relationship-type-specific errors
"""

from typing import Dict, Any, List

def analyze_errors(predictions: List[Dict[str, Any]], concordance_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze errors in predictions and categorize them."""
    errors = []
    
    # Build BNS section context map
    bns_context = {}
    for row in concordance_data:
        bns = row.get("bns_section", "").strip()
        if bns:
            bns_context[bns] = {
                "chapter": row.get("chapter", ""),
                "relationship": row.get("relationship_type", "")
            }
            
    for pred in predictions:
        if pred.get("correct", False):
            continue
            
        error = pred.copy()
        true_bns = pred.get("true_bns", "")
        pred_bns = pred.get("predicted_bns", "")
        
        error_type = "unknown"
        
        if not pred_bns:
            error_type = "no_prediction"
        elif pred_bns in ("-", "—", "REPEALED"):
            error_type = "predicted_repealed"
        else:
            true_ctx = bns_context.get(true_bns, {})
            pred_ctx = bns_context.get(pred_bns, {})
            
            if true_ctx and pred_ctx and true_ctx.get("chapter") == pred_ctx.get("chapter"):
                error_type = "same_chapter"
            else:
                error_type = "different_chapter"
                
            if true_ctx.get("relationship") == "split":
                error_type = "split_mapping_confusion"
                
        error["error_type"] = error_type
        errors.append(error)
        
    return errors
