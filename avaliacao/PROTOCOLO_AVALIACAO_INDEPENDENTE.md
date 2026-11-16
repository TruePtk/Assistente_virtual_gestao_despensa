# Avaliação independente do TCC — protocolo preparado em 16/11/2026

## Congelamento da implementação

A versão local congelada é a tag `tcc-freeze-2026-11-16`, apontando para o commit `3ffbbf9ace642d5a603166a28cdf674c8f3cec4e` da branch `main`. A árvore de trabalho estava limpa quando a tag foi criada. A tag existe apenas localmente e não foi enviada ao GitHub.

Registro da configuração observada no código dessa versão:

- Serviço/modelo: Google Gemini, usando primeiro `gemini-3.1-flash-lite` e tentando `gemini-3.5-flash-lite` se a chamada falhar.
- O código não define parâmetros de geração explicitamente; são usados os padrões do SDK/serviço.
- Os prompts estão em `ai_config/ai_service.py`; não há arquivo separado de versão de prompt.
- O teste de mensagens usa a despensa fixa definida em `avaliacao/avaliar_mensagens.py` e um banco SQLite separado.

Não altere código, prompts ou parâmetros até terminar e guardar as avaliações independentes. Se for indispensável corrigir algo, preserve esta tag e registre a correção como uma nova versão; os resultados da versão congelada não devem ser misturados com os da nova versão.

## Mensagens inéditas

O arquivo `perguntas_ineditas.csv` contém 21 casos, com gabarito definido antes da execução, distribuídos em consulta (3), ausência (2), consumo (4), adição (4), composta (3), armadilha (3) e variação de escrita (2). Os casos são diferentes das 39 mensagens usadas nas rodadas de desenvolvimento.

Execute somente uma vez, com uma repetição por mensagem:

```powershell
python avaliacao/avaliar_mensagens.py --perguntas avaliacao/perguntas_ineditas.csv --repeticoes 1 --pausa 1
```

O script cria um CSV de resultados em `avaliacao/resultados/`. Guarde o arquivo original sem edição. Não use esses casos para ajustar a versão congelada antes de registrar os resultados. O conjunto tem 21 mensagens e é exploratório; não deve ser descrito como amostra independente ampla ou representativa de todos os usuários.

## Extração de notas por foto

1. Reúna notas/cupons cujo uso no estudo foi autorizado. Identifique as imagens com nomes neutros, como `NF01.jpg`.
2. Antes de enviá-las ao serviço externo, remova ou cubra nome do consumidor, CPF, QR Code, chave de acesso e outros dados pessoais. Preserve a área dos itens, quantidades e unidades. Registre as condições da imagem (legibilidade, ângulo, iluminação e corte).
3. Faça a transcrição manual do gabarito antes de rodar a IA, preenchendo uma linha por produto em `gabarito_notas_template.csv`. Inclua os itens visíveis, quantidades e unidades; mantenha uma cópia sem alterações.
4. Salve cópias anonimizadas em uma pasta local, por exemplo `avaliacao/fotos_anonimizadas/`. Não inclua as imagens originais no Git.
5. Execute a extração sem gravar na despensa:

```powershell
python avaliacao/avaliar_notas.py avaliacao/fotos_anonimizadas
```

O script chama a mesma função de extração do sistema, mas não cadastra os itens no banco. Ele salva IDs de imagem, itens extraídos e erros; não salva a imagem nem a resposta bruta da IA. Compare manualmente a saída com o gabarito e conte: produtos identificados corretamente, omitidos, incluídos indevidamente, quantidade correta, unidade correta e categoria correta. Registre exemplos de falha de forma anonimizada.

O serviço recebe o conteúdo das imagens para processamento. Portanto, use somente imagens anonimizadas e cujo uso tenha sido autorizado. As fotos e o gabarito detalhado devem permanecer fora do repositório público.

## Usabilidade e comparação entre Telegram e site

A etapa ainda precisa ser planejada com o orientador. Para uma comparação curta, definam tarefas equivalentes (por exemplo: localizar um item, adicionar uma quantidade e registrar uma baixa), mesmo estado inicial da despensa, instrução igual e critérios de conclusão antes de recrutar participantes. Alternem a ordem das interfaces entre participantes. Registrem conclusão, tempo e erros sem identificar as pessoas; apliquem e calculem o SUS conforme a fonte/protocolo citado na monografia. Confirmem com o orientador eventuais exigências institucionais para participação voluntária e consentimento.

Não apresentem observações exploratórias sobre a Siri como substitutas de SUS ou do comparativo.
