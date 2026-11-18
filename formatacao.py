def formatar_quantidade(valor: int | float) -> str:
    """Mostra quantidades com no máximo três casas decimais."""
    return f"{valor:.3f}".rstrip("0").rstrip(".")
