# Guia operacional — canais dark e vídeos originais

## Objetivo
Criar canais editoriais com conteúdo autoral, consistente e sustentável, distribuindo vídeos para atrair audiência e levar tráfego qualificado aos produtos digitais do site. O objetivo não é copiar vídeos existentes nem automatizar publicações repetitivas.

## Arquitetura de produção
1. **Radar:** identificar demanda, intenção de busca, perguntas recorrentes, sazonalidade e concorrência. Registrar fontes, data e região.
2. **Estratégia editorial:** definir nicho, público, promessa, pilares de conteúdo, linguagem e séries. Um canal-piloto deve validar o formato antes da expansão.
3. **Roteiro autoral:** criar gancho, contexto, explicação, exemplo, conclusão e CTA. Checar fatos e evitar leitura de conteúdo copiado.
4. **Direção visual:** storyboard por cena, com enquadramento, movimento, duração, paleta, personagem/objeto e continuidade.
5. **Geração de vídeo:** o workspace conectado ao ElevenLabs lista Seedance 2.5 como modelo padrão de vídeo, além de Veo, Kling, Runway e outros. Essa disponibilidade não comprova gratuidade, saldo ou integração ao backend Hermes.
6. **Voz e áudio:** o workspace lista ElevenLabs TTS (incluindo Eleven v4) e composição audiovisual. Usar apenas voz, música e efeitos com direitos adequados.
7. **Edição e QC:** sincronizar cenas e voz, inserir legendas, revisar pronúncia, áudio, cortes, fatos, direitos, repetição e CTA.
8. **Adaptação:** preparar master vertical 9:16 para Shorts/Reels/TikTok e versão horizontal 16:9 quando houver conteúdo longo. Ajustar título, descrição, legenda e CTA para cada canal.
9. **Publicação:** somente após OAuth oficial, permissões mínimas e confirmação da API da plataforma.
10. **Medição:** registrar URL publicada, data, visualizações, retenção, cliques e pedidos confirmados. Não inferir receita a partir de visualizações.

## Papel de cada IA
- **Hermes AI Gateway:** pesquisa assistida, planejamento, roteiro e revisão, conforme o provedor realmente configurado e dentro da quota gratuita.
- **Seedance 2.5 (candidato principal):** gerar cenas originais a partir do storyboard. Não chamar enquanto custo/saldo não estiver visível e autorizado.
- **ElevenLabs TTS:** narração. Disponibilidade no workspace não significa uso gratuito.
- **ElevenLabs Composition ou editor equivalente:** montagem de vídeo, narração, música e efeitos. A integração automática com Hermes ainda precisa ser construída e validada.
- **Quality/Auditor:** verificar originalidade, fatos, direitos, acessibilidade, formatos e políticas da plataforma.

## Estratégia de canais
- **YouTube:** Shorts para descoberta; vídeos longos para aprofundamento e construção de audiência. Monitorar requisitos atuais do Programa de Parcerias no YouTube Studio.
- **TikTok:** vídeos verticais nativos, gancho imediato e narrativa própria.
- **Instagram Reels e Facebook Reels:** adaptar a edição, legenda e CTA; não presumir que uma autorização vale para todas as contas.
- **Pinterest:** publicar peças visuais/vídeos como descoberta e tráfego evergreen, se a conta e a API oferecerem a permissão necessária.
- **Site + Kiwify:** página de destino coerente com o vídeo, oferta clara e checkout oficial. A entrega digital deve estar configurada e testada.

## Regras de monetização e direitos
- Conteúdo com IA pode ser elegível, mas deve ser original, autêntico e acrescentar valor real.
- Evitar vídeos genéricos, intercambiáveis, repetitivos ou produzidos em massa com pequenas variações.
- Não republicar filmes, séries, anime, esportes, clipes virais ou vídeos de terceiros sem transformação substancial e direitos adequados.
- Informar uso de conteúdo sintético/alterado quando a representação parecer real e puder confundir o público, conforme as regras da plataforma.
- Não prometer monetização, alcance ou renda. Elegibilidade e aprovação dependem da plataforma.

## Portões de segurança e custo
- Bloquear qualquer geração se o serviço não informar custo/saldo antes da execução.
- Não consumir créditos pagos, comprar planos, contratar infraestrutura ou impulsionar anúncios sem autorização explícita.
- Nunca automatizar login com senha, burlar limites, comprar visualizações/seguidores ou enviar spam.
- O modo de publicação fica desabilitado até OAuth, escopos e retorno de publicação serem testados.
- Separar estados: planejado, roteiro aprovado, mídia gerada, revisão aprovada, agendado, publicado, métricas recebidas e venda confirmada.

## Critério de pronto
Um vídeo só pode ser marcado como pronto quando roteiro, fontes, ativos/licenças, áudio, legendas, formato, disclosure aplicável e revisão editorial estiverem registrados. Só marcar como publicado com URL/ID retornado pela plataforma. Só registrar venda com evento aprovado e deduplicado do checkout.
