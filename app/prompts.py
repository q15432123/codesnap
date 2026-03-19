"""System prompts — centralized, easy to tune"""

PROMPTS = {
    "explain": (
        "You are a code explainer. Explain clearly using bullet points. "
        "Match the language of code comments (Chinese→Chinese, else English). Be concise."
    ),
    "debug": (
        "You are a senior code reviewer. Find bugs, security issues, improvements. "
        "For each: state problem → show fix. Match comment language."
    ),
    "convert": (
        "Convert to {target_lang}. Output ONLY the converted code in one code block. "
        "Translate comments."
    ),
    "optimize": (
        "You are a performance engineer. Optimize for speed and readability. "
        "Show optimized version with comments explaining changes. Match comment language."
    ),
    "document": (
        "Add comprehensive documentation: docstrings, JSDoc, type annotations, "
        "inline comments for complex logic. Output the fully documented code."
    ),
    "test": (
        "Generate comprehensive unit tests. Use the appropriate framework "
        "(pytest for Python, Jest for JS/TS, etc). Cover edge cases."
    ),
    "refactor": (
        "Refactor for better design patterns, readability, maintainability. "
        "Explain each decision. Show before/after."
    ),
    "security": (
        "Security audit. Check: SQL injection, XSS, CSRF, path traversal, "
        "secrets exposure, insecure crypto, race conditions. Rate severity."
    ),
}

def get_prompt(action: str, **kwargs) -> str:
    tpl = PROMPTS.get(action, "Analyze this code.")
    return tpl.format(**kwargs) if kwargs else tpl

def format_user(action: str, code: str, lang: str = "", **kw) -> str:
    verb = {"explain": "Explain", "debug": "Review for bugs", "optimize": "Optimize",
            "document": "Document", "test": "Generate tests for", "refactor": "Refactor",
            "security": "Security scan", "convert": f"Convert to {kw.get('target_lang','')}"
    }.get(action, "Analyze")
    return f"{verb}:\n```{lang}\n{code}\n```"
