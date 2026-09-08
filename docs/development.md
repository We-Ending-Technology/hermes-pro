# Desenvolvimento

## Convenções

O backend usa tipagem Python, configurações por variáveis de ambiente e testes de contrato HTTP. Segredos nunca devem ser versionados; use `.env` local ou variáveis protegidas no Render.

## Comandos

```bash
pytest
uvicorn backend.app.main:app --reload
python -m worker.main
```

O frontend é independente e pode ser substituído por uma aplicação hospedada separadamente quando a estratégia de deploy for definida.
