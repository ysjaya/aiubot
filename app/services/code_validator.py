# app/services/code_validator.py
import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class CodeCompletenessValidator:
    """Validator untuk memastikan kode AI lengkap 100% tanpa truncation"""
    
    # Marker yang menandakan kode tidak lengkap
    TRUNCATION_MARKERS = [
        '...',
        '# ... rest of code',
        '# ... kode lainnya',
        '# rest of the code',
        '// ... rest of code',
        '// ... kode lainnya',
        '/* ... */',
        '<!-- ... -->',
        '[truncated]',
        '[continued]',
        '[TRUNCATED]',
        '[CONTINUED]',
        '# dan seterusnya',
        '// dan seterusnya',
        '# ... (rest omitted)',
        '// ... (rest omitted)',
    ]
    
    # Pattern untuk deteksi function/class tidak lengkap
    INCOMPLETE_PATTERNS = [
        r'(def\s+\w+\([^)]*\):)\s*\.\.\.', # Python function dengan ...
        r'(function\s+\w+\([^)]*\))\s*\{?\s*\.\.\.', # JS function dengan ...
        r'(class\s+\w+[^{]*)\{?\s*\.\.\.', # Class dengan ...
    ]
    
    @staticmethod
    def validate_completeness(content: str, filename: str = "") -> Dict:
        """
        Validasi kelengkapan kode
        
        Returns:
            {
                "is_complete": bool,
                "score": float (0-1),
                "issues": List[str],
                "warnings": List[str]
            }
        """
        if not content or len(content.strip()) < 10:
            return {
                "is_complete": False,
                "score": 0.0,
                "issues": ["Content too short or empty"],
                "warnings": []
            }
        
        issues = []
        warnings = []
        score = 1.0
        
        # 1. Check truncation markers
        content_lower = content.lower()
        found_markers = []
        for marker in CodeCompletenessValidator.TRUNCATION_MARKERS:
            if marker.lower() in content_lower:
                found_markers.append(marker)
                issues.append(f"Found truncation marker: '{marker}'")
                score -= 0.3
        
        # 2. Check incomplete patterns
        for pattern in CodeCompletenessValidator.INCOMPLETE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            if matches:
                issues.append(f"Found incomplete code pattern: {matches[0][:50]}")
                score -= 0.2
        
        # 3. Check for balanced brackets/braces
        bracket_balance = CodeCompletenessValidator._check_bracket_balance(content)
        if not bracket_balance['balanced']:
            warnings.append(f"Unbalanced brackets: {bracket_balance['message']}")
            score -= 0.1
        
        # 4. Check for suspiciously short content
        lines = content.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        
        if len(non_empty_lines) < 5 and not filename.endswith('.txt'):
            warnings.append(f"File seems too short ({len(non_empty_lines)} lines)")
            score -= 0.1
        
        # 5. Check for abrupt endings
        last_lines = '\n'.join(lines[-5:]).strip()
        if last_lines.endswith(('...', '# ...', '// ...')):
            issues.append("File ends with truncation marker")
            score -= 0.3
        
        score = max(0.0, min(1.0, score))
        is_complete = score >= 0.7 and len(issues) == 0
        
        return {
            "is_complete": is_complete,
            "score": score,
            "issues": issues,
            "warnings": warnings
        }
    
    @staticmethod
    def _check_bracket_balance(content: str) -> Dict:
        """Check if brackets/braces are balanced"""
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        open_brackets = set(pairs.keys())
        close_brackets = set(pairs.values())
        
        # Remove strings and comments to avoid false positives
        cleaned = CodeCompletenessValidator._remove_strings_and_comments(content)
        
        for i, char in enumerate(cleaned):
            if char in open_brackets:
                stack.append(char)
            elif char in close_brackets:
                if not stack:
                    return {
                        "balanced": False,
                        "message": f"Extra closing bracket '{char}' at position {i}"
                    }
                opener = stack.pop()
                if pairs[opener] != char:
                    return {
                        "balanced": False,
                        "message": f"Mismatched brackets: '{opener}' vs '{char}'"
                    }
        
        if stack:
            return {
                "balanced": False,
                "message": f"Unclosed brackets: {stack}"
            }
        
        return {"balanced": True, "message": "All brackets balanced"}
    
    @staticmethod
    def _remove_strings_and_comments(content: str) -> str:
        """Remove string literals and comments to avoid false positives"""
        # Remove multi-line strings
        content = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
        content = re.sub(r"'''.*?'''", '', content, flags=re.DOTALL)
        
        # Remove single-line strings
        content = re.sub(r'"[^"]*"', '', content)
        content = re.sub(r"'[^']*'", '', content)
        
        # Remove comments
        content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        return content
    
    @staticmethod
    def enforce_complete_code_prompt(base_prompt: str) -> str:
        """Add enforcement rules to AI prompt"""
        enforcement = """

CRITICAL RULES FOR CODE GENERATION:
1. ✅ ALWAYS write COMPLETE code - no truncation, no "...", no shortcuts
2. ✅ Include ALL imports, ALL functions, ALL classes - NOTHING omitted
3. ✅ Write the ENTIRE file from start to finish
4. ✅ Never use placeholders like "... rest of code" or "... kode lainnya"
5. ✅ If code is long, still write it completely - no exceptions
6. ✅ Every function must have complete implementation
7. ✅ Every class must have all methods fully written
8. ❌ NEVER write "# ... (continue)" or similar shortcuts
9. ❌ NEVER assume user will fill in missing parts
10. ❌ NEVER truncate or summarize code sections

USER EXPECTS: 100% COMPLETE, READY-TO-USE CODE THAT CAN BE DOWNLOADED IMMEDIATELY.
"""
        return base_prompt + enforcement

def validate_and_retry(
    content: str,
    filename: str,
    max_retries: int = 2
) -> Tuple[str, Dict]:
    """
    Validate content and return validation result
    
    Returns:
        (content, validation_result)
    """
    validator = CodeCompletenessValidator()
    result = validator.validate_completeness(content, filename)
    
    logger.info(f"[VALIDATOR] {filename}: Complete={result['is_complete']}, Score={result['score']:.2f}")
    
    if result['issues']:
        for issue in result['issues']:
            logger.warning(f"[VALIDATOR] Issue: {issue}")
    
    if result['warnings']:
        for warning in result['warnings']:
            logger.info(f"[VALIDATOR] Warning: {warning}")
    
    return content, result
