# Microvix XML Finder

Aplicação web em Flask para consultar produtos no ecossistema Microvix por dois caminhos:

- busca manual por código de barras, referência ou código do produto;
- importação de arquivos XML de NFe para pré-visualização e verificação dos itens na API.

O objetivo do projeto é agilizar a conferência de produtos, principalmente em cenários em que é necessário validar se os itens de uma NFe existem na API e identificar itens não encontrados, duplicidades por EAN e múltiplas origens em XMLs diferentes.

## Visão Geral

A aplicação possui duas telas principais:

- autenticação: recebe login e senha, obtém um token temporário e em seguida um token final de autorização;
- consulta: permite busca manual e fluxo de upload/verificação de XML.

Depois de autenticado, o usuário pode:

- pesquisar produtos manualmente;
- anexar um ou mais XMLs de NFe;
- pré-visualizar os itens extraídos;
- verificar os itens na API;
- navegar pelos resultados por XML ou pela aba consolidada "Todos os Resultados";
- copiar os EANs selecionados para uso em SQL ou Excel.

## Principais Funcionalidades

- autenticação em duas etapas contra os endpoints do Microvix;
- busca manual por:
  - `Codebar`;
  - `Referencia`;
  - `CodigoProduto`;
- leitura de múltiplos XMLs de NFe no mesmo envio;
- extração de dados como item, EAN, referência, código auxiliar e quantidade;
- verificação dos itens extraídos na API;
- consolidação por EAN na aba de resultados combinados;
- expansão das origens por arquivo XML quando o mesmo EAN aparece em mais de um arquivo;
- armazenamento temporário dos resultados em memória durante a sessão.

## Requisitos

- Python 3.10 ou superior
- acesso aos endpoints da API utilizados pelo projeto
- credenciais válidas para autenticação

## Dependências

O projeto usa, no mínimo, as bibliotecas abaixo:

- `Flask`
- `requests`
- `python-dotenv`

Como não há um `requirements.txt` atualmente no repositório, a instalação local pode ser feita manualmente.

## Como Rodar Localmente

### 1. Clonar o repositório

```powershell
git clone <URL_DO_REPOSITORIO>
cd automacao-microvix-py
```

### 2. Criar e ativar um ambiente virtual

No Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

No Prompt de Comando do Windows:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Instalar as dependências

```powershell
pip install Flask requests python-dotenv
```

### 4. Configurar o arquivo `.env`

Crie ou ajuste um arquivo `.env` na raiz do projeto com as variáveis abaixo:

```env
API_ENDPOINT_URL=
API_ENDPOINT_LOGIN_URL=
API_ENDPOINT_AUTH_URL=
```

Descrição das variáveis:

- `API_ENDPOINT_URL`: endpoint principal de consulta de produtos;
- `API_ENDPOINT_LOGIN_URL`: endpoint usado para gerar o token temporário;
- `API_ENDPOINT_AUTH_URL`: endpoint usado para converter o token temporário em token final de autorização.

Observação: o projeto já possui leitura automática do `.env` via `python-dotenv`.

### 5. Executar a aplicação

```powershell
python run.py
```

Por padrão, a aplicação sobe em modo de desenvolvimento com `debug=True`.

Se tudo estiver correto, acesse no navegador:

```text
http://127.0.0.1:5000
```

## Fluxo de Uso

### 1. Autenticação

Na tela inicial, informe:

- login;
- senha.

A aplicação faz:

1. uma chamada para obter o token temporário;
2. uma segunda chamada para obter o token final;
3. o armazenamento do token na sessão do Flask.

### 2. Busca Manual

Na aba de busca manual, é possível informar uma ou mais entradas separadas por vírgula ou quebra de linha nos campos:

- código de barras;
- referência;
- código do produto.

O sistema envia as consultas para a API, filtra os resultados retornados e remove duplicidades antes de exibir a tabela final.

### 3. Busca por XML

Na aba de XML:

1. o usuário envia um ou mais arquivos `.xml`;
2. o sistema extrai os itens da NFe;
3. a tela mostra uma pré-visualização dos itens encontrados;
4. ao clicar em verificar, cada item é consultado na API;
5. os itens não encontrados, ou itens com múltiplos codebars, são exibidos no resultado final.

### 4. Aba "Todos os Resultados"

Após a verificação dos XMLs, a interface cria:

- abas individuais por XML;
- uma aba consolidada com todos os resultados.

Na aba consolidada, os itens são agrupados por EAN. Quando um mesmo EAN aparece em mais de um XML, o botão de expansão permite visualizar os arquivos de origem.

## Estrutura do Projeto

```text
app/
  __init__.py
  api_client.py
  config.py
  manual_search.py
  routes.py
  xml_parser.py
  xml_verification.py
  templates/
    auth_page.html
    base_template.html
    search_page.html
run.py
MicrovixXMLFinder.spec
```

## Descrição dos Arquivos Principais

- `run.py`: ponto de entrada da aplicação em ambiente local;
- `app/__init__.py`: fábrica da aplicação Flask e carregamento das configurações;
- `app/routes.py`: rotas HTTP, fluxo de autenticação, busca manual, upload, verificação e consolidação de resultados;
- `app/api_client.py`: comunicação com os endpoints externos;
- `app/manual_search.py`: lógica de busca manual e deduplicação de resultados;
- `app/xml_parser.py`: leitura e extração dos dados dos XMLs de NFe;
- `app/xml_verification.py`: verificação dos itens extraídos na API;
- `app/templates/`: páginas HTML renderizadas pelo Flask.

## Endpoints da Aplicação

Principais rotas expostas pelo sistema:

- `GET /`: tela de autenticação;
- `POST /get-temp-token`: obtém o token temporário;
- `POST /get-final-token`: obtém o token final e salva na sessão;
- `GET|POST /search`: tela principal de pesquisa e processamento;
- `GET|POST /verify-xml`: verifica os itens extraídos dos XMLs;
- `GET /search-combined`: retorna os resultados consolidados por EAN;
- `GET /search-tab/<xml_index>`: retorna os resultados de um XML específico;
- `GET /logout`: encerra a sessão atual;
- `POST /cancel`: sinaliza cancelamento de operação em andamento.

## Como o Projeto Funciona Internamente

### Sessão e autenticação

- o token final é armazenado em `session['auth_token']`;
- os dados de formulário e chaves temporárias também ficam na sessão.

### Cache temporário

O projeto usa dicionários em memória para guardar resultados temporários:

- `temp_xml_cache`
- `temp_manual_cache`
- `cancellation_flags`

Isso significa que:

- os dados não são persistidos em banco;
- reiniciar a aplicação limpa os caches;
- o comportamento é adequado para uso local ou interno, mas não é ideal para múltiplas instâncias ou produção distribuída.

### Consolidação por EAN

Depois da verificação dos XMLs, os itens são agrupados por `Codebar`. O sistema mantém a relação entre o EAN consolidado e os XMLs de origem para permitir rastreabilidade na interface.

## Limitações Atuais

- não existe banco de dados;
- os caches são mantidos apenas em memória;
- as dependências ainda não estão formalizadas em `requirements.txt`;
- `SECRET_KEY` é gerada dinamicamente a cada execução, então reiniciar a aplicação invalida sessões anteriores;
- a aplicação está configurada para rodar localmente em modo de desenvolvimento.

## Sugestões de Evolução

- criar um `requirements.txt` ou `pyproject.toml`;
- adicionar testes automatizados;
- persistir resultados temporários em Redis ou banco de dados;
- configurar uma `SECRET_KEY` fixa por variável de ambiente;
- adicionar tratamento mais detalhado para falhas de parsing e respostas da API;
- preparar um modo de produção com WSGI e configurações separadas por ambiente.

## Observações para Desenvolvimento

- o projeto usa `load_dotenv()` para carregar variáveis automaticamente;
- a aplicação foi estruturada com `Blueprint` do Flask;
- a interface está baseada em templates HTML renderizados no servidor;
- o arquivo `MicrovixXMLFinder.spec` indica que o projeto já teve preparo para empacotamento com PyInstaller.

## Licença

Este repositório não define uma licença explicitamente até o momento. Se o projeto for compartilhado fora do time, vale incluir um arquivo de licença apropriado.
