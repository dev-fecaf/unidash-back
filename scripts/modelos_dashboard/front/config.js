// Dashboard "__NOME_TEXTO__". Criado pelo comando novo_dashboard em __DATA__.
//
// O hash e os códigos das páginas vieram do banco (Gerador): NÃO mude, o Hub e os links dependem deles.
// O nome e a ordem das páginas que aparecem na tela vêm do banco (mude no Gerador).
//
// Nesta pasta:
// - tema.css: as cores deste dashboard (barra lateral, fundo, cartões, gráficos);
// - paginas/: um arquivo por página, com o conteúdo dela (filtros, indicadores e gráficos: etapa 3).
// Os dados vêm dos endpoints do back: unidash-back/app/dominios/dados/__IDENTIFICADOR__/
// Página criada no Gerador depois desta pasta: crie o arquivo em paginas/ e acrescente aqui embaixo.

import './tema.css'
__IMPORTS__

export default {
  hash: '__HASH__',
  identificador: '__IDENTIFICADOR__',
  nome: __NOME__,
  paginas: [
__PAGINAS__
  ],
}
