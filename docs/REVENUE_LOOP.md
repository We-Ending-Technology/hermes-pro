# Hermes Pro — ciclo de receita

Objetivo:

**descoberta → filtragem → prioridade → proposta → candidatura autorizada → projeto ganho → execução → entrega → pagamento → aprendizado**

## Estados do Radar
- `approved`: passou pelo Radar.
- `ready_to_apply`: pronto para candidatura.
- `queued`: colocado na fila.
- `applied`: candidatura registrada quando a integração realmente confirmou envio.
- `won`: cliente/projeto ganho.
- `in_progress`: execução.
- `delivered`: entrega registrada.
- `paid`: pagamento confirmado.
- `lost`: oportunidade encerrada sem venda.

O backend deve **somente** avançar para um estado confirmado quando houver evidência da integração ou ação real. Não marcar candidatura, venda ou pagamento apenas porque uma tarefa foi criada.

## Política de autonomia
O Hermes pode operar automaticamente em tarefas internas e em integrações autorizadas. CAPTCHA, 2FA, bloqueios, limites de plataforma e termos de uso nunca devem ser contornados.

## Primeira meta
Priorizar trabalhos pequenos de Python, automação, APIs, PDF/dados e correções, com baixo risco de entrega e prazo curto. O Radar deve preferir oportunidade recente, aderência técnica alta, orçamento razoável e escopo executável com as ferramentas disponíveis.
