"""
Loads tree-sitter parsers per language.

We deliberately avoid the `tree-sitter-languages` package here: it's
unmaintained and doesn't ship Python 3.12 wheels (breaks on Windows/most
current setups). Instead we use the actively maintained per-language
packages (tree-sitter-python, tree-sitter-javascript, tree-sitter-typescript)
with the current tree-sitter>=0.23 Language API.
"""
from functools import lru_cache

import tree_sitter_javascript as ts_javascript
import tree_sitter_python as ts_python
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

_LANGUAGE_BUILDERS = {
    "python": lambda: Language(ts_python.language()),
    "javascript": lambda: Language(ts_javascript.language()),
    # tree-sitter-typescript ships two grammars: typescript and tsx
    "typescript": lambda: Language(ts_typescript.language_typescript()),
}


@lru_cache(maxsize=None)
def get_language(lang: str) -> Language:
    if lang not in _LANGUAGE_BUILDERS:
        raise ValueError(f"Unsupported language: {lang}")
    return _LANGUAGE_BUILDERS[lang]()


@lru_cache(maxsize=None)
def get_parser(lang: str) -> Parser:
    parser = Parser(get_language(lang))
    return parser
