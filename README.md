# Painel de Gestão Integrada — V6.8 | Layouts Personalizados

Sistema desktop Python + Tkinter + Matplotlib + SQLite, no tema **preto e vermelho**, com carrossel ANDON animado, editor por dia/mês e cadastro flexível de setores.

## Novo na V6.8 — Editor visual de layouts

O menu **Modo apresentação** mantém os carrosséis prontos de indicadores e gráficos e oferece a terceira opção **Layouts personalizados**:

1. Abra **Montar / editar layouts** e escolha **+ Novo** ou o modelo **Gráfico + indicadores**.
2. Clique em **+ Gráfico / + Indicador**, ou arraste um bloco da biblioteca para um espaço da tela.
3. Clique no bloco e escolha o indicador, o tipo de gráfico e os setores na lateral direita.
4. Arraste os blocos para organizar; blocos do mesmo tamanho trocam de lugar. Escolha **Normal**, **Largo**, **Alto** ou **Tela inteira** para dar destaque.
5. Dê um nome, ajuste o tempo da página e clique em **Salvar e apresentar**.

- Cada layout é uma página com até quatro blocos em uma grade de quatro espaços. Gráficos e indicadores podem ser misturados, e blocos maiores ocupam mais de um espaço sem sobreposição.
- **Ver prévia** apresenta os gráficos completos e os números atuais; o editor exibe miniaturas rápidas para facilitar a montagem.
- Indicadores podem mostrar um resumo do setor (atingimento, dia, realizado e meta) ou um indicador específico. Gráficos de valores absolutos usam um setor; percentuais permitem até oito setores por bloco.
- A lista de páginas permite criar, duplicar, excluir e alterar a ordem. **Incluir no carrossel** controla quais páginas serão apresentadas. Cada página tem seu próprio tempo de 5/10/15/30/60 segundos.
- **Desfazer / Ctrl+Z**, **Salvar / Ctrl+S** e aviso de alterações não salvas. Excluir um layout altera somente a apresentação; não apaga dados operacionais.
- Definições salvas no banco local, separadas das preferências dos dois modos prontos. Nomes e IDs dos setores permanecem associados; setores ocultos aparecem como indisponíveis, sem apresentar valores antigos.
- O carrossel personalizado usa preparação antecipada das páginas, transição suave e cache limitado. Configurações ficam no clique direito; F8 abre o editor, Espaço pausa, setas navegam, F9 retorna e F11 alterna tela cheia.

## Novo na V6.7 — Telão limpo e transições

- Retirados os botões fixos do carrossel de gráficos. Configuração, pausa, navegação, tela cheia e retorno ficam no **clique direito**; os atalhos existentes continuam disponíveis.
- As páginas vizinhas são preparadas fora da animação e reaproveitadas. A troca só começa após o desenho e o ajuste dos gráficos estarem prontos.
- Cliques rápidos são acumulados e aplicados ao concluir a transição atual, evitando sobreposição de páginas. O timer reinicia ao final da troca.
- A preparação é cancelada ao sair ou configurar; mudanças de tamanho/dados invalidam as páginas antigas. O cache tem tamanho limitado.

## Novo na V6.6 — Gráficos no telão

- Corrigida a montagem da janela **Escolher áreas do carrossel**: a lista usa a barra de rolagem corretamente, a janela tem tamanho explícito e pode ser redimensionada, e aplicar/cancelar ficam fixos no rodapé. A apresentação pausa durante a escolha e retoma ao fechar.
- **Modo apresentação** agora permite escolher o carrossel de indicadores ou o **carrossel de gráficos**. A aba Gráficos também oferece **Apresentar gráficos**.
- O telão de gráficos mantém identidade Phinia, transição deslizante, barra de progresso, pausa/retomada, páginas anterior/próxima, F8, F9, F11, Espaço e setas, com intervalos de 5/10/15/30/60 segundos.
- **Configurar gráficos / F8** permite marcar indicadores, tipos de gráfico e setores, escolher de 1 a 4 gráficos por tela e ajustar o intervalo. As escolhas são salvas separadamente do carrossel de indicadores; cancelar preserva a configuração anterior. Setores ocultos nunca aparecem.
- Percentuais comparam até oito setores por gráfico; distribuição de status considera os setores selecionados com atingimento informado. Valores absolutos são apresentados por setor, para evitar misturar unidades incompatíveis. Campos ausentes não viram zero e sua quantidade fica indicada.
- Dados, período e dia acompanham a seleção do painel. Linha comparativa continua sendo uma comparação entre setores, não um histórico diário.
- Para iniciar direto no telão de gráficos, abra **INICIAR_GRAFICOS_WINDOWS.bat** ou execute `python main.py --chart-carousel --fullscreen`.

## Novo na V6.5 — Usabilidade

- Menu dividido em **Acompanhar**, **Dia a dia** e **Ferramentas**, com destaque da tela atual, feedback ao passar o mouse e navegação por teclado.
- **Registrar dados** em destaque no cabeçalho. O formulário abre no setor filtrado, quando houver um selecionado.
- Preenchimento simples com **um campo por indicador**, nomes explicados, data completa no calendário, exemplos de números e atingimento calculado visível. A visão de duas colunas continua disponível em **Mais opções → Mostrar duas colunas (avançado)**, preservando valores das colunas ocultas.
- Novos lançamentos no mês atual começam na data de hoje; uma data escolhida no filtro continua sendo respeitada. Campos não preenchidos em um novo dia preservam os valores mensais já existentes. Zeros digitados são salvos normalmente; limpar um valor carregado continua removendo aquele valor.
- Salvar e recarregar confirmam o resultado na própria tela. Erros de digitação destacam o campo; alterações pendentes aparecem no rodapé. Confirmações de descarte e exclusão continuam ativas.
- Botões **Salvar dados**, **Salvar e próximo setor**, **Mais opções** e **Fechar** ficam fixos no formulário. Tab e Enter ajudam a percorrer os campos, com rolagem para acompanhar o foco.
- Limpezas ficam em **Mais opções** no formulário. Importação, exportação e cadastro ficam em **Mais opções** no painel, mantendo as confirmações e backups existentes.
- Botão **Limpar filtros** e guia **Como usar**. A identidade visual e as faixas de desempenho existentes foram mantidas.
- O iniciador do Windows usa um Python disponível e instala componentes somente quando estão ausentes, corrigindo também a saída prematura do iniciador anterior. Use `INICIAR_WINDOWS.bat --verificar` para verificar os componentes sem abrir a aplicação.

## Novo na V6.4 — Visão geral

- A abertura agora apresenta a **Visão geral**, com contadores separados de áreas no alvo, em atenção, críticas e sem atingimento informado. A tabela permanece acessível na aba e no menu lateral.
- Os três menores atingimentos abaixo de 95% aparecem em ordem crescente. Clique em um setor para abrir sua tabela com todos os indicadores. O resumo respeita os filtros de período, dia e área e exclui setores ocultos.
- Valores ausentes continuam diferentes de zero: ausência de atingimento não entra no ranking como desempenho crítico.
- Pendências e erros de origem ficam explícitos. A referência, a fonte e a data de registro do conjunto aparecem no resumo; a referência e o registro também aparecem no telão. Dados de exemplo são identificados na tela principal.
- Cabeçalho simplificado e ações dos filtros em uma linha própria. O resumo tem rolagem para telas menores.
- **As fórmulas e faixas existentes foram preservadas.** As cores representam atingimento da meta cadastrada, sem ajuste pelo avanço do mês; não medem atraso nem ritmo diário. Metas proporcionais dependem de regras por indicador e do calendário operacional, ainda não configurados nesta versão.
- Nenhuma migração dos dados é necessária. O registro do conjunto não comprova atualização de todos os setores: o consolidado pode reunir lançamentos de datas diferentes.

Prévia: `previews/visao_geral_v64.png`.

## Executar no Windows

1. Extraia o ZIP inteiro (não execute dentro do ZIP).
2. Instale o **Python 3.10 ou superior**, com a opção **Add Python to PATH**.
3. Abra `INICIAR_WINDOWS.bat` para o programa normal ou `INICIAR_CARROSSEL_WINDOWS.bat` para o telão em tela cheia.
4. Na primeira abertura o iniciador instalará `matplotlib`, `openpyxl` e `Pillow` se necessário. O sistema funciona offline.

Via terminal:

```powershell
python -m pip install -r requirements.txt
python main.py
python main.py --carousel --fullscreen
```

## Correções da V6.3

### Calendário compacto e navegável

- Agora a janela mostra **somente o calendário e os botões**, sem cabeçalho explicativo ou painel extra.
- As setas **‹ / ›** navegam livremente pelos meses, inclusive entre anos (dezembro → janeiro).
- Escolher uma data de outro mês **atualiza automaticamente a competência** (tanto no filtro de EDIÇÃO / DIA como no editor de lançamento manual).
- Botões **HOJE / APLICAR / CANCELAR** e **CONSOLIDADO** no filtro principal.
- **CANCELAR não altera a data anterior**; ao escolher um dia ainda sem lançamento, o painel indica ausência de dados em vez de voltar silenciosamente a Consolidado.
- O popup é preparado antes de aparecer, evitando o flash no canto superior esquerdo.
- Calendário implementado com Tkinter, **sem depender do pacote tkcalendar**.

### Análise gráfica sem piscadas/bordas claras

- Trocar Barras horizontais, Colunas, Linha comparativa e Distribuição de status **não destrói nem recria** a tela do Matplotlib.
- Figura e canvas são reaproveitados; fundo e bordas do gráfico/Notebook seguem a paleta preta.
- Os gráficos continuam usando os filtros atuais, os setores ativos e as mesmas métricas.
- Corrigidos callbacks pendentes de tabela/relógio ao encerrar a aplicação.

**Prévia visual:** `preview_calendario_corrigido.png` e `preview_graficos_corrigidos.png`.

## Corrigido na V6.2 — Identidade visual no carrossel

- O carrossel agora exibe **símbolo + PHINIA** no canto superior direito, ao lado do banner **Painel de Gestão Integrada**.
- As imagens ficam numa **faixa independente dos cartões animados**. Não somem quando o carrossel muda de página.
- Não precisa ativar nada: o logo aparece automaticamente ao entrar no carrossel (F9 ou iniciador do telão).
- O menu lateral continua com símbolo e nome PHINIA; o calendário continua com correção para não aparecer no canto da tela antes de abrir.
- Prévia: `preview_carrossel.png`. A animação e os indicadores permanecem preservados.

## NOVO na V6 — Branding PHINIA e calendário

- **Logo PHINIA** no menu lateral, substituindo o texto curto anterior.
- **Banner do Painel de Gestão Integrada** no cabeçalho principal.
- **Banner discreto no canto superior direito do carrossel**, sem perder o visual limpo do telão.
- **Seleção de dia por calendário popup** no filtro principal (**EDIÇÃO / DIA**) e no formulário de lançamento manual, substituindo a escolha por lista.
- O calendário abre inicialmente na competência selecionada, mas permite navegar por outros meses e atualizar o filtro/período; possui atalho para **HOJE** e **Consolidado** (na tela principal).

## Recursos da V5 mantidos — Gerenciar painéis

Na tela principal, use **GERENCIAR PAINÉIS** no menu esquerdo ou o botão **PAINÉIS** no cabeçalho. No telão, pressione **F8** (ou botão direito) e escolha **Gerenciar painéis**.

A janela mostra todos os painéis cadastrados, incluindo os ocultos. Selecione um setor e use:

- **+ CRIAR PAINEL:** informe *nome completo*, *nome curto*, *indicador principal* e *indicador secundário*. Os indicadores começam com nomes de exemplo editáveis. O painel aparece automaticamente no gerencial, editor e na seleção do carrossel. A estrutura de DIA, CAP./SALDO, MÊS, STK PAI/FILHO, FCST, ATINGIMENTO e FALTA é igual à de todos os outros.
- **RENOMEAR / EDITAR:** altera nomes e cabeçalhos também dos painéis originais; **não modifica o ID interno** nem apaga os dados já lançados.
- **OCULTAR PAINEL:** remove-o da grade gerencial, estatísticas/KPIs, gráficos, filtros por área, editor de lançamentos, exportação CSV e carrossel. A definição e todos os lançamentos diários e mensais **continuam salvos** no SQLite.
- **RESTAURAR PAINEL:** reexibe o setor e seus dados anteriores sem precisar cadastrá-lo novamente.

**GARANTIA (SEMANAL W40) vem OCULTO por padrão na V5.** Para restaurá-lo, abra **Gerenciar painéis**, localize **GARANTIA W40** no fim da lista, selecione e clique em **RESTAURAR PAINEL**.

**Importante:** não há exclusão definitiva de painéis na V5. “Remover” significa **ocultar**, para evitar perda acidental de histórico. Os ocultos só aparecem na tela administrativa **Gerenciar painéis**, onde precisam aparecer para permitir recuperação.

### Dados armazenados e compatibilidade

- O programa mantém o banco já utilizado pela V3/V4 (`painel.db`), e adiciona automaticamente a tabela `area_catalog` na primeira abertura da V5. **Não precisa recriar o banco.**
- Os IDs das 12 áreas originais não mudam. Renomear LOGÍSTICA, LINC, GARANTIA etc. não quebra os históricos.
- As opções de visibilidade e nomes são persistidas no banco local, inclusive ao reiniciar.
- O carrossel possui uma seleção independente por checkbox, **mas nunca mostra um painel globalmente oculto**, mesmo que estivesse marcado anteriormente. Ao restaurar um painel, a seleção antiga do carrossel é preservada; marque no seletor F8 caso necessário.
- A planilha `GERENCIAL` antiga contém apenas as **12 áreas originais**. Portanto, ela importa somente essas áreas; **painéis criados na V5 e seus históricos diários são preservados ao reimportar Excel**.
- Renomear não altera o mapeamento das colunas da planilha: as áreas fixas continuam ligadas a suas colunas originais pelas chaves internas.
- Uma importação do Excel substitui o histórico diário das **12 áreas originais** da competência; quando houver lançamentos manuais, é exibido um alerta e é criado backup antes da substituição. Os painéis criados manualmente não são apagados.

## Recursos preservados da V4

**Carrossel ANDON:** animações deslizantes, progresso de tempo contínuo, 2/3/4 cartões por página (2 centralizados), tela limpa, configurar intervalos 5/10/15/30/60 segundos, escolher áreas com checkboxes.

**Editor manual:** preencha competência `AAAA-MM`, escolha o dia em um **calendário**, e a área ativa; números BR (`42.000,5`), estoque, metas, porcentagens. Salvar calcula percentual e FALTA quando houver MÊS e FCST válidos. Nenhum Excel é necessário.

**Limpezas:** LIMPAR DIA apaga somente dia+área; LIMPAR ÁREA limpa a área no mês; APAGAR TODOS limpa os dados operacionais (não o catálogo nem as configurações). Todas criam backup e pedem confirmação; a última requer digitar `APAGAR`.

**Filtros e gráficos:** competência, dia (Consolidado ou dia específico via calendário), área e grupo de métricas. A visão consolidada usa últimos valores informados, **não soma automaticamente o histórico diário**. KPIs ignoram áreas ocultas. CSV usa somente áreas ativas do filtro.

**Carrossel e SAP:** o carrossel troca automaticamente os cartões, **não busca números em tempo real**. Nenhuma ligação com SAP está ativa ainda.

### Atalhos

| Atalho | Ação |
|---|---|
| **F6** | Lançamento manual |
| **F8** | Configurações do carrossel, escolha de áreas e gerenciador de painéis (na apresentação) |
| **F9** | Abrir/fechar carrossel |
| **F11** | Tela cheia |
| **Espaço** | Pausa/retoma carrossel |
| **← / →** | Troca páginas |
| **2 / 3 / 4** | Cartões por página |
| **Ctrl+S** | Salvar lançamento no formulário |

### Onde os dados ficam

- Windows: `%LOCALAPPDATA%\PainelGestaoIntegrada\painel.db`
- Linux: `~/.painel_gestao_integrada/painel.db`
- Backups: pasta `backups` ao lado do banco.

**Antes de atualizar:** feche a versão antiga e mantenha uma cópia de segurança de `painel.db`, especialmente se ela já contém dados reais. Os arquivos da aplicação podem ser substituídos sem mover o banco, porque este fica no diretório local do usuário.

### Estrutura técnica

- `painel/config.py`: métricas e definições iniciais da planilha.
- `painel/data.py`: repositório SQLite, migração do catálogo, importação Excel e backup.
- `painel/area_manager.py`: cadastro de setores, alteração de nomes, ocultação e restauração.
- `painel/app.py`: interface principal e integração dos filtros.
- `painel/carousel.py`: rotação, animações, seleção de áreas e cronômetro.
- `painel/manual.py`: edição por dia/mês e exclusões seguras.
- `painel/table.py` e `painel/charts.py`: visualizações, adaptadas ao catálogo de áreas ativas.
- `tests/`: testes de regressão.

Executar testes:

```powershell
python -m unittest discover -s tests -v
```

Para incluir os testes de interface em Linux com Xvfb:

```bash
xvfb-run -a env PGI_GUI_TESTS=1 python -m unittest discover -s tests -v
```

A V6.3 passou em **48 testes automatizados** (incluindo 4 testes de interface com display virtual) e em verificação funcional da interface em ambiente gráfico virtual: catálogo, renomeação, criação, tabelas, filtros, gráficos, formulário manual, ocultação, restauração e carrossel.
