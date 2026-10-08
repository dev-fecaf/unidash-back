# Modelos do comando novo_dashboard

Arquivos que o comando `python -m scripts.novo_dashboard <identificador>` copia para as pastas
de um dashboard novo. Troque à vontade (na etapa 3 o modelo do front ganha gráficos e filtros).

Marcadores substituídos ao copiar:

| Marcador | Vira |
|---|---|
| `__IDENTIFICADOR__` | identificador do dashboard (= schema no DW), ex.: `executivo` |
| `__HASH__` | hash do dashboard (banco) |
| `__NOME__` | nome do dashboard, entre aspas (texto pronto para JS/Python) |
| `__NOME_TEXTO__` | nome do dashboard, sem aspas (para comentários) |
| `__PAGINAS__` | lista das páginas ativas (código, nome e componente), já formatada (só no `config.js`) |
| `__IMPORTS__` | um `import` por página (só no `config.js`) |
| `__COMPONENTE__` | nome do componente da página, tirado do nome dela, ex.: `VisaoGeral` (só em `paginas/Pagina.jsx`) |
| `__NOME_PAGINA_TEXTO__` / `__CODIGO__` | nome e código da página (só em `paginas/Pagina.jsx`) |
| `__DATA__` | data de criação, ex.: 08/10/2026 |

- `front/` → `unidash-front/src/dashboards/<identificador>/`:
  - `config.js` e `tema.css` são copiados uma vez;
  - `paginas/Pagina.jsx` vira **um arquivo por página ativa**: `paginas/VisaoGeral.jsx`, `paginas/Matriculas.jsx`...
- `back/` → `unidash-back/app/dominios/dados/<identificador>/` (cópia simples de cada arquivo).

O que fica **em cada dashboard** (pode mudar à vontade): cores (`tema.css`) e conteúdo de cada página.
O que fica **num lugar só** (vale para todos): barra lateral, layout, entrada pelo Hub, componentes de
gráfico (etapa 3). Assim uma correção na barra lateral não precisa ser repetida em cada pasta.
