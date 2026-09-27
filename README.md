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

## Build do executável

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Gera `dist/CFAUTO.exe` e valida que ele cria o banco numa pasta limpa.

## Licenças

```powershell
uv run python tools/gerar_licenca.py gerar-chaves      # uma vez; guarde a privada com backup
uv run python tools/gerar_licenca.py emitir --cliente "Loja" --dias 365 [--maquina ID]
```
A chave privada fica em `%USERPROFILE%\.cfauto-licenca\privada.pem` e nunca entra no repositório.
