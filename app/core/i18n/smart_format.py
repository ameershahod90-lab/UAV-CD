"""
Math-zone-aware ``str.format`` substitution.

Translations frequently contain LaTeX math zones — e.g.
``"The efficiency $${\\eta_p}$$ enters Eq. {n}."``. A naive
``template.format(n=2)`` would crash because Python's formatter treats every
``{`` as the start of a placeholder, including the LaTeX brace subscripts.

``smart_format`` solves this by splitting the template on ``$${...}$$``
boundaries, applying ``.format(**kwargs)`` only to the prose between zones,
and splicing the math zones back in untouched. Authors of translation
strings can therefore use LaTeX freely without escaping braces.
"""

from __future__ import annotations

import re
from typing import Any

# Match the inline-math sigil ``$${...}$$``. Non-greedy + DOTALL so a single
# zone is captured even if it spans multiple lines or contains nested braces.
_MATH_ZONE = re.compile(r"\$\$\{.+?\}\$\$", re.DOTALL)


def smart_format(template: str, **kwargs: Any) -> str:
    """Substitute ``{name}`` placeholders, leaving ``$${...}$$`` math intact.

    With no kwargs, the template is returned unchanged (allows the caller to
    use the same code path for static and parameterised translations).
    """
    if not kwargs:
        return template

    parts: list[str] = []
    last = 0
    for m in _MATH_ZONE.finditer(template):
        prose = template[last:m.start()]
        parts.append(_format_prose(prose, kwargs))
        parts.append(m.group(0))  # math zone — verbatim
        last = m.end()
    parts.append(_format_prose(template[last:], kwargs))
    return "".join(parts)


def _format_prose(prose: str, kwargs: dict[str, Any]) -> str:
    """Apply ``.format(**kwargs)`` to a prose fragment.

    If the fragment has no ``{`` it is returned verbatim — saves the cost
    of building a Formatter for static fragments. If formatting raises
    ``KeyError`` or ``IndexError`` (e.g. a placeholder name that isn't in
    kwargs), the original fragment is returned so a missing kwarg degrades
    to "leave the placeholder visible" rather than crash the export.
    """
    if "{" not in prose:
        return prose
    try:
        return prose.format(**kwargs)
    except (KeyError, IndexError):
        return prose
