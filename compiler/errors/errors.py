"""Backward-compat shim: re-exports from phases.phase0_common.errors."""
from phases.phase0_common.errors import (  # noqa: F401
    KrakError, LexicalError, SyntaxError_, SemanticError, KrakTypeError, RuntimeError_,
)
