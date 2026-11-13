# Assistente virtual de gestão de despensa

Assistente conversacional para gestão de despensa doméstica. O projeto oferece um bot do Telegram, um site local para consultar e editar o estoque e uma API para integração com um Atalho do iOS. As interfaces compartilham um banco SQLite; mensagens e fotos de notas são interpretadas pelo Gemini.

## Demonstração

1. Inicie o bot e envie `/start` no Telegram.
2. Cadastre itens por mensagem ou envie uma foto da nota fiscal.
3. Consulte e atualize o estoque com `/despensa`, mensagens em linguagem natural ou o site aberto com `/site`.
4. Opcionalmente, configure `/atalho` para consultar a despensa e enviar mensagens usando um Atalho do iOS.

Exemplo de conversa (as respostas da IA podem variar):

```text
Você: Adicione 2 kg de arroz e 1 litro de leite.
Bot: Adicionado: 2 kg de arroz.
     Adicionado: 1 litro de leite.

Você: Usei meio litro de leite.
Bot: Baixa registrada! Restam 0.50 de leite.

Você: /despensa
Bot: 🥫 Sua Despensa:
     • 2.0 kg de arroz
     • 0.5 litro de leite
     [❌ Consumi: arroz] [❌ Consumi: leite]
```

Os nomes e quantidades dos exemplos pressupõem que as operações foram interpretadas dessa forma pelo modelo. `/despensa` lista os itens e mostra botões para registrar consumo; a quantidade exibida pode usar a representação numérica retornada pelo SQLite. O site também permite adicionar itens e registrar consumo.

## Requisitos

- Python 3.12 ou superior.
- Um bot do Telegram e o token fornecido pelo [@BotFather](https://t.me/BotFather).
- Uma chave de API do Gemini, criada no [Google AI Studio](https://aistudio.google.com/app/apikey).
- `cloudflared` é opcional; é necessário apenas para expor a API do Atalho do iOS por um Cloudflare Quick Tunnel em uma demonstração remota.

O projeto usa SQLite; não é necessário instalar um servidor de banco de dados. Na primeira execução, `database/database.py` cria `despensa.db` no diretório de onde o programa foi iniciado. O bot e os lembretes só ficam disponíveis enquanto o computador que executa o programa estiver ligado e conectado à internet.

## Instalação

Clone o repositório e entre na pasta do projeto. Crie e ative um ambiente virtual.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux ou macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuração das chaves

Crie um arquivo chamado `.env` na raiz do projeto, no mesmo nível de `main.py` e `config.py`:

```dotenv
TELEGRAM_BOT_TOKEN=cole_aqui_o_token_do_BotFather
GEMINI_API_KEY=cole_aqui_a_chave_do_Google_AI_Studio
IOS_SHORTCUT_INSTALL_URL=https://www.icloud.com/shortcuts/SEU_LINK_COMPARTILHADO
IOS_SHORTCUT_NAME=Despensa
SHORTCUT_API_HOST=127.0.0.1
SHORTCUT_API_PORT=8765
# Opcional se você já tiver uma origem HTTPS pública permanente.
# No Quick Tunnel, o script define esta variável automaticamente.
# SHORTCUT_API_BASE_URL=https://api.exemplo.com
```

Substitua os valores pelos seus, sem aspas. `TELEGRAM_BOT_TOKEN` e `GEMINI_API_KEY` são obrigatórios. As variáveis `IOS_SHORTCUT_INSTALL_URL` e `SHORTCUT_API_BASE_URL` só são necessárias para usar `/atalho`; a segunda é injetada automaticamente por `deploy/quick-tunnel.ps1`, ou pode apontar para uma origem HTTPS pública permanente. Inicie os programas a partir da pasta do projeto para que o `.env` seja encontrado.

`IOS_SHORTCUT_INSTALL_URL` é o link de compartilhamento do Atalho publicado no iCloud. `IOS_SHORTCUT_NAME` deve ser exatamente o nome instalado. O nome padrão é `Despensa`, para facilitar a execução pela Siri (“E aí Siri, Despensa”). A Apple inicia um atalho ao ouvir o nome dele ([Suporte da Apple](https://support.apple.com/pt-br/guide/shortcuts/apd07c25bb38/9.0/ios/26)). `SHORTCUT_API_HOST` e `SHORTCUT_API_PORT` definem onde o processo local escuta; a API fica em `127.0.0.1:8765` por padrão. Para estudo sem domínio, use `deploy/quick-tunnel.ps1`: ele inicia um Cloudflare Quick Tunnel HTTPS, injeta a URL temporária no bot e mantém ambos ativos até `Ctrl+C`. O script usa `.tools/cloudflared.exe` se existir ou `cloudflared` instalado no sistema; consulte o [guia oficial](https://developers.cloudflare.com/tunnel/downloads/) para obter o executável. Não exponha a porta HTTP diretamente à internet.

O `.gitignore` já exclui `.env` e `.venv`. Mantenha as chaves apenas nesse arquivo local: não as escreva no código, README, commits, capturas de tela ou mensagens públicas. Antes de enviar alterações, confira com `git status` se `.env` não aparece entre os arquivos a serem adicionados. Se uma chave for exposta, revogue-a no serviço correspondente e gere outra.

## Executar

Com o ambiente virtual ativo e o `.env` preenchido, execute na raiz do projeto:

```bash
python main.py
```

O bot usa polling para receber mensagens. Deixe o processo aberto enquanto quiser que ele responda; `Ctrl+C` encerra a execução.

### Site da despensa

O site é um processo separado do bot. Com o bot ativo, abra outro terminal na raiz do projeto, ative o ambiente virtual e inicie:

```bash
python -m uvicorn site_web.app:app --host 127.0.0.1 --port 8000
```

Envie `/site` ao bot e abra o link pessoal recebido. O site permite consultar o estoque, adicionar produtos e registrar consumo; as alterações aparecem no mesmo banco usado pelo bot. Cada novo `/site` cria um link e invalida o anterior. O link é uma credencial de acesso: não o compartilhe.

Para abrir o site em outro aparelho na mesma rede Wi-Fi, use `--host 0.0.0.0` e altere `URL_SITE` em `handlers/telegram.py` para o endereço local do computador, por exemplo `http://192.168.1.20:8000`. Essa configuração é para uma rede confiável; não exponha o site fora da rede sem um proxy HTTPS adequado.

Para aceitar solicitações de iPhones fora da rede local sem comprar domínio, instale `cloudflared` e execute no PowerShell:

```powershell
.\deploy\quick-tunnel.ps1
```

O script abre o túnel HTTPS temporário para a API do Atalho e inicia o bot, que hospeda essa API localmente em `127.0.0.1:8765`. Copie a URL exibida para verificar `https://<url>/health`, envie `/atalho` no Telegram e siga os botões de instalação e vinculação. A máquina precisa permanecer ligada, com o script em execução. Se houver um `config.yaml` em `%USERPROFILE%\.cloudflared`, renomeie-o durante o uso do Quick Tunnel, pois o Cloudflare informa que esse modo não funciona com esse arquivo presente. O túnel não publica o site em `localhost:8000`.

## Mensagens e respostas

| Entrada | Comportamento |
| --- | --- |
| `/start` | Apresenta o assistente e explica como enviar uma nota ou perguntar sobre receitas. |
| `/despensa` | Lista os itens do usuário com botões para iniciar o registro de consumo. |
| `/site` | Cria e envia um link pessoal para abrir o site da despensa. Requer que o servidor Uvicorn esteja em execução. |
| `/atalho` | Em conversa privada, envia os botões de instalação do Atalho iOS e de autenticação da conta. Requer a URL do Atalho publicado e uma origem HTTPS pública para a API. |
| `Adicione 3 latas de milho.` | A IA interpreta a intenção e o núcleo soma a quantidade a um item correspondente ou cria um novo. |
| `Usei 1 lata de milho.` | A IA identifica o item e a quantidade; o banco subtrai o valor. Se o estoque chegar a zero, o item é removido. |
| `O que tem na minha despensa?` | A interpretação retorna `consultar`; o bot mostra a mesma lista de `/despensa`. |
| `Consumi tudo de milho.` | Remove o item identificado. Para “consumir tudo da despensa”, a operação especial limpa todos os itens daquele usuário. |
| Pergunta geral | A IA pode responder sem alterar o estoque. |
| Foto da nota fiscal | O Gemini Vision extrai nome, quantidade, unidade e categoria. |

Os botões de consumo oferecem `-1`, `-0.5` e `Acabou Tudo!`; o item também pode ser mantido ou ter o lembrete adiado. O bot agenda verificações de lembretes a cada hora e só os envia entre 9h e 20h, no máximo um por usuário em cada rodada.

Cadências configuradas: 5 dias para laticínios e hortifruti, 7 para outros, 15 para mercearia e doces, e 30 para limpeza. Depois de enviado, o mesmo item não volta a ser lembrado antes de 14 dias; “Lembrar depois” adia por 7 dias.

### Exemplo de leitura por foto

Ao enviar uma foto, o bot confirma que recebeu a imagem. Se a leitura funcionar, a resposta é semelhante a:

```text
✅ Itens adicionados pela leitura da foto:
• 2 kg de Goma de Tapioca (Mercearia)
• 1 unidade de Leite (Laticínios)
```

O caminho de leitura de QR Code NFC-e foi removido do fluxo do bot após os testes indicarem bloqueio ao acesso automatizado pela SEFAZ. Atualmente, a imagem da nota é enviada diretamente ao Gemini Vision; o script `testar_fluxo_sefaz.py` é um utilitário separado para investigar respostas de URLs da SEFAZ, não uma etapa do cadastro de itens.

O fluxo `/atalho` depende de um Atalho publicado no iCloud e configurado para receber texto de entrada. O botão HTTPS “Autenticar neste iPhone” chama `GET /api/shortcut/open`, que redireciona para o esquema URL da [Apple](https://support.apple.com/pt-br/guide/shortcuts/apd624386f42/9.0/ios/26) e executa o Atalho com um JSON contendo a URL pública temporária, o ID do Telegram e um código de uso único. O Atalho troca esse código por um token de acesso no `POST /api/shortcut/link`; o código expira em 15 minutos e só pode ser usado uma vez. O uso de HTTPS no botão atende à exigência do Telegram de aceitar somente links HTTP ou `tg://` ([Bot API do Telegram](https://core.telegram.org/bots/api)).

Com o token no cabeçalho `Authorization: Bearer <token>`, o Atalho pode consultar `GET /api/shortcut/pantry` ou enviar uma mensagem em `POST /api/shortcut/message` com `{"message":"Adicione 2 litros de leite"}`. A resposta traz `reply` e, quando a ação é uma consulta, `items`. Para revogar um token específico, use `DELETE /api/shortcut/token`. A API também oferece `GET /health` para verificar disponibilidade. Cada token concede acesso de leitura e alteração à despensa; o Atalho precisa persistir esse token entre execuções. Se for salvo como arquivo em texto simples, qualquer pessoa com acesso aos arquivos do iCloud Drive pode usá-lo; revogue-o se o dispositivo ou arquivo for perdido. Só pode haver um código de vinculação pendente por conta, e a criação de outro invalida o anterior. Tokens já vinculados são independentes.

O Quick Tunnel é gratuito e dispensa domínio e conta Cloudflare, mas é temporário: a URL muda a cada execução e deixa de responder quando o processo é encerrado. Rode `deploy/quick-tunnel.ps1` em vez de iniciar `main.py` diretamente; a URL atual será incorporada aos novos links enviados por `/atalho`. Quando reiniciar o bot/túnel, vincule o atalho de novo para atualizar a URL salva nele. Esse modo é para demonstrações, não para uso contínuo ([limitações oficiais](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)).

## Como o JSON vira operações

Para mensagens de texto, `ai_config/ai_service.py` envia a mensagem ao Gemini e pede somente um objeto JSON. Uma mensagem com duas ações pode ser interpretada assim:

```json
{
  "operacoes": [
    {
      "acao": "consumir",
      "item_alvo": "leite",
      "quantidade": 1
    },
    {
      "acao": "adicionar",
      "item_alvo": "arroz",
      "quantidade": 2,
      "unidade_medida": "kg",
      "categoria": "Mercearia"
    }
  ]
}
```

O caminho no código é:

1. `ai_service.interpretar_intencao_usuario` limpa eventuais cercas Markdown e converte o texto com `json.loads`.
2. `handlers/core.py` percorre `operacoes` na ordem recebida. Para compatibilidade, também aceita o formato antigo de uma única ação no nível superior. Uma consulta pode ocorrer junto com outras operações da mesma mensagem.
3. Em `adicionar`, compara nomes sem acentos e pontuação e tenta identificar singular/plural ou nomes parecidos. Um único item correspondente recebe a quantidade somada se as unidades forem compatíveis; se forem diferentes, o sistema recusa a soma e explica a divergência. Sem correspondência, um novo registro é criado. Se houver mais de um candidato, não escolhe automaticamente e pede mais especificidade.
4. Em `consumir`, localiza o item e subtrai a quantidade. Uma quantidade igual ou menor que zero no estoque remove o registro. A operação especial com `item_alvo: "tudo"` esvazia a despensa daquele usuário.
5. `consultar` retorna os itens para o handler apresentar. `duvida_geral` devolve o texto de resposta da IA sem mexer no estoque.

O prompt orienta o Gemini a padronizar massas em kg e volumes em L (por exemplo, 500 g → 0,5 kg). Antes de somar a um registro existente, o núcleo compara as unidades; se não forem equivalentes, mantém o estoque sem alteração e informa a incompatibilidade.

As operações de estoque são gravadas em `itens_despensa` no SQLite e associadas ao ID do usuário do Telegram. As categorias padrão são `Mercearia`, `Laticínios`, `Hortifruti`, `Limpeza`, `Doces e Guloseimas` e `Outros`; uma categoria desconhecida é salva como `Outros`.

Para fotos, a extração produz um JSON com uma lista `itens`, cada um contendo nome, quantidade, unidade e categoria. O núcleo descarta registros sem nome ou com quantidade ausente, inválida, zero ou negativa, aceita quantidade com vírgula decimal e os encaminha à mesma lógica de soma/criação usada para adicionar por texto.

## Avaliação automatizada

O repositório contém 39 mensagens de referência em `avaliacao/perguntas.csv`, divididas em sete categorias: consulta (6), ausência (4), consumo (8), adição (6), operações compostas (6), casos armadilha (6) e variações de escrita (3). O script restaura uma despensa fixa de 16 itens antes de cada mensagem, usa um banco separado (`avaliacao/despensa_teste.db`) e compara a intenção e o estado final obtidos com o gabarito.

A execução mais recente registrada no repositório (`avaliacao/resultados/resultados_20261112_195305.csv`) repetiu as 39 mensagens três vezes:

| Medida | Resultado registrado |
| --- | ---: |
| Acerto e intenção correta | 100% (117/117) |
| Itens extras no estado final | 0 |
| Consistência nas três repetições | 100% (39/39 perguntas) |
| Tempo de execução | média 1,07 s; mediana 0,80 s |

Esse resultado descreve apenas as mensagens testadas nessa execução. As mesmas perguntas foram usadas durante os ajustes, então o resultado não mede generalização para mensagens novas. A avaliação automatizada não cobre a leitura de fotos; também não há resultado registrado de teste de usabilidade SUS nem comparação controlada entre Telegram e site. Para repetir a avaliação, execute na raiz do projeto com o `.env` configurado:

```bash
python avaliacao/avaliar_mensagens.py --repeticoes 3
```

O relatório CSV é gravado em `avaliacao/resultados/`. Cada repetição chama o Gemini, então a duração depende do serviço de IA e da pausa entre mensagens.

## Arquitetura

```text
Telegram ──> main.py / handlers/telegram.py
Site ──> site_web/app.py (FastAPI) ───────────────┐
Atalho iOS ── HTTPS ──> shortcut_api.py ─────────┼──> handlers/core.py
        (API inicia no main.py)                   │           │
Telegram ────────────────────────────────────────┘           ├──> Gemini
                                                            └──> SQLite
```

- `main.py`: configura o bot, registra comandos e handlers, e agenda os lembretes.
- `config.py`: carrega e valida as variáveis de ambiente.
- `handlers/telegram.py`: integra mensagens, fotos e botões do Telegram com os casos de uso.
- `shortcut_api.py`: API HTTP para vincular Atalhos iOS, consultar a despensa e enviar mensagens.
- `site_web/app.py` e `site_web/index.html`: API FastAPI e interface web para consultar, adicionar e consumir itens.
- `site_web/tokens.py`: cria e valida links pessoais do site, armazenados no banco SQLite.
- `handlers/core.py`: interpreta os resultados da IA, aplica regras de estoque e coordena lembretes e notas.
- `ai_config/ai_service.py`: chama o Gemini para interpretar mensagens e extrair itens de notas.
- `database/database.py`: cria e consulta as tabelas de usuários, categorias e itens no SQLite.
- `avaliacao/avaliar_mensagens.py`: executa as mensagens de referência em banco de teste separado e gera relatórios CSV.
- `deploy/quick-tunnel.ps1`: inicia um Cloudflare Quick Tunnel temporário e o bot para demonstração remota do Atalho.
- `despensa.template.db`: arquivo modelo do banco incluído no repositório; a execução usa `despensa.db`.

O bot inicia a API do Atalho em uma thread dentro do processo `main.py`. O site FastAPI é independente e precisa ser iniciado à parte. Telegram, site e Atalho reutilizam as regras da despensa em `handlers/core.py` e o mesmo arquivo SQLite.

## Limitações e escopo

- O banco é local ao processo e depende do diretório de execução. Faça cópias de segurança de `despensa.db` se os dados forem importantes; esse arquivo é ignorado pelo Git.
- O bot, as APIs, o banco e os lembretes são executados localmente e dependem de o computador permanecer ligado. O acesso externo requer um proxy HTTPS configurado pelo operador; o Quick Tunnel é temporário e voltado a demonstrações.
- Mensagens e fotos são processadas por serviços externos do Telegram e/ou Gemini. Uma foto enviada para leitura visual é transmitida ao Gemini.
- O site e o fluxo de vinculação do Atalho iOS já estão implementados. O uso do Atalho ainda depende de um link de compartilhamento do iCloud configurado em `IOS_SHORTCUT_INSTALL_URL`.
- O banco SQLite atende ao uso de baixa concorrência esperado pelo projeto; gravações simultâneas podem competir pelo arquivo local.
- A leitura depende da qualidade da foto e da disponibilidade do serviço Gemini. Confira o estoque quando a interpretação for importante.
