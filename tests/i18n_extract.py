"""Collects all texts to translate (calls of tr(...) and N_(...)) from the source code."""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "g733_tray"


def source_strings():
    """Set of all literals passed to tr() or N_()."""
    found = set()
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("tr", "N_")
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.add(node.args[0].value)
    return found


def non_literal_calls():
    """tr()/N_() calls with a non-literal argument (which cannot be checked automatically)."""
    result = []
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name == "i18n.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("tr", "N_")
                    and node.args and not (isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str))):
                result.append(f"{path.name}:{node.lineno}: {ast.unparse(node)}")
    return result
