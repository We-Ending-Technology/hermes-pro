# Hermes Pro

Fundação inicial do Hermes Pro, uma plataforma para orquestração de produtos e automações com IA. Esta etapa entrega uma base limpa, executável e testável, sem integrações de marketplaces e sem automação de produção.

## Arquitetura

| Componente | Responsabilidade | Execução local |
| --- | --- | --- |
| `frontend` | Interface web inicial em React/Vite | `npm run dev` |
| `backend` | API HTTP em FastAPI | `uvicorn app.main:app --reload` |
| `ai-gateway` | Contrato único para provedores de IA | Dentro do backend |
| `agents` | Agentes com responsabilidades isoladas | Dentro do backend |
| `worker` | Processo separado para jobs assíncronos | `python -m worker.main` |
| `supabase/migrations` | Schema versionado do banco | Supabase CLI |

## Início rápido

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn backend.app.main:app --reload
```

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

A documentação da API fica em `http://localhost:8000/docs`.

## Testes

```bash
pytest
```

## Deploy

O arquivo `render.yaml` descreve o serviço web, o worker e as variáveis de ambiente sem valores secretos. Configure os segredos no painel do Render.

## Escopo desta etapa

A fundação inclui health checks, configuração por ambiente, um endpoint de exemplo, abstração do gateway de IA, registro de agentes, fila em memória para desenvolvimento, worker executável, migration inicial, testes e documentação. Integrações de marketplaces e automação de produção ficam explicitamente fora do escopo.
