# Arquitetura inicial

O Hermes Pro é organizado como um monorepo com fronteiras claras entre apresentação, API, raciocínio e execução assíncrona.

## Fluxo de uma execução

1. O frontend chama a API FastAPI.
2. A API valida o contrato e localiza o agente no registro.
3. O agente usa o gateway de IA, que esconde o provedor concreto.
4. A API retorna um identificador de execução e o resultado.
5. O worker permanece separado para a futura execução de jobs demorados.

A implementação atual usa um gateway `stub` determinístico. Isso permite testar a arquitetura sem chaves ou chamadas externas.

## Limites intencionais

Não há integração de marketplace, automação de produção, provedor de IA real, fila externa ou autenticação nesta etapa. Cada uma dessas capacidades terá um contrato próprio antes de receber uma implementação.
