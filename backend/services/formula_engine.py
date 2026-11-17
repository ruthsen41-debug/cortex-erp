"""
Avaliador seguro de fórmulas de rubrica.

Aceita apenas aritmética, comparações, condicionais e um conjunto fixo de funções.
Não usa eval(): a expressão é analisada com `ast` e cada nó é validado, então não
há acesso a atributos, imports, índices ou qualquer nome fora das variáveis da folha.

Exemplos:
    salario_base * 0.30
    salario_hora * 1.5 * quantidade
    se(dias_trabalhados >= 30, 150, 150 * dias_trabalhados / 30)
    min(salario_base * 0.06, 220)
"""
import ast
import math
import operator
from typing import Any, Dict, List

MAX_LEN = 500


class FormulaError(ValueError):
    """Fórmula inválida ou que não pôde ser calculada."""


_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
_CMP = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
}


def _se(cond, a, b):
    return a if cond else b


def _arred(x, casas=2):
    return round(float(x) + 1e-9, int(casas))


_FUNCS = {
    "min": min, "max": max, "abs": abs, "round": _arred, "arred": _arred,
    "se": _se, "trunc": math.trunc, "piso": math.floor, "teto": math.ceil,
}

FUNCOES = sorted(_FUNCS)


def _parse(expr: str) -> ast.Expression:
    if not isinstance(expr, str) or not expr.strip():
        raise FormulaError("Fórmula vazia.")
    if len(expr) > MAX_LEN:
        raise FormulaError(f"Fórmula muito longa (máximo {MAX_LEN} caracteres).")
    try:
        return ast.parse(expr.strip().replace("\n", " "), mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Erro de sintaxe na fórmula: {e.msg}.") from None


def _names(tree: ast.AST) -> List[str]:
    funcs = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    return sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - funcs)


def _eval(node: ast.AST, variables: Dict[str, Any]):
    if isinstance(node, ast.Expression):
        return _eval(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulaError("Só são aceitos números na fórmula.")
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise FormulaError(f"Variável desconhecida: '{node.id}'.")
        return variables[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _eval(node.left, variables), _eval(node.right, variables)
        try:
            return _BIN[type(node.op)](left, right)
        except ZeroDivisionError:
            raise FormulaError("Divisão por zero na fórmula.") from None
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand, variables))
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, variables) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, variables)
        for op, comp in zip(node.ops, node.comparators):
            if type(op) not in _CMP:
                raise FormulaError("Comparação não permitida na fórmula.")
            right = _eval(comp, variables)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body if _eval(node.test, variables) else node.orelse, variables)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS or node.keywords:
            nome = getattr(node.func, "id", "?")
            raise FormulaError(f"Função não permitida: '{nome}'. Use: {', '.join(FUNCOES)}.")
        args = [_eval(a, variables) for a in node.args]
        try:
            return _FUNCS[node.func.id](*args)
        except FormulaError:
            raise
        except Exception:
            raise FormulaError(f"Uso incorreto da função '{node.func.id}'.") from None
    raise FormulaError("Expressão não permitida na fórmula (use apenas contas, comparações e funções da lista).")


def evaluate(expr: str, variables: Dict[str, Any]) -> float:
    """Calcula a fórmula com as variáveis informadas e devolve um número."""
    result = _eval(_parse(expr), variables)
    if isinstance(result, bool):
        result = 1.0 if result else 0.0
    try:
        result = float(result)
    except (TypeError, ValueError):
        raise FormulaError("A fórmula não resultou em um número.") from None
    if math.isnan(result) or math.isinf(result):
        raise FormulaError("A fórmula resultou em valor inválido.")
    return result


def validate(expr: str, allowed_names: List[str]) -> List[str]:
    """Valida sintaxe e nomes; devolve as variáveis usadas. Lança FormulaError se inválida."""
    tree = _parse(expr)
    usados = _names(tree)
    desconhecidos = [n for n in usados if n not in allowed_names and not n.startswith("rubrica_")]
    if desconhecidos:
        raise FormulaError(f"Variável desconhecida: {', '.join(desconhecidos)}.")
    # Avalia com valores de teste para pegar funções/operadores proibidos.
    try:
        evaluate(expr, {n: 1.0 for n in set(allowed_names) | set(usados)})
    except FormulaError as e:
        if "Divisão por zero" not in str(e):  # pode ser só efeito dos valores de teste
            raise
    return usados
