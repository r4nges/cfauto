# CFAUTO

Gestão para varejo e serviços (PySide6 + SQLite). Especificação em `docs/superpowers/specs/`.

## Desenvolvimento

```powershell
uv python install 3.13
uv sync
uv run pytest
uv run python -m cfauto
```

Variável `CFAUTO_HOME` troca a pasta de dados (padrão `%APPDATA%\CFAUTO`).
