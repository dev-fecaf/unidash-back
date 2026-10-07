
Aloca as partições de back-end do app unidash-back.

## Como rodar no computador

Comandos para o PowerShell, dentro da pasta `unidash-back`.

1. Crie o arquivo `.env` a partir do `.env.example` e preencha os valores.
2. Instale as bibliotecas no ambiente do projeto (`.venv`):

   ```powershell
   $env:DISABLE_SQLALCHEMY_CEXT = "1"
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt --no-binary sqlalchemy
   ```

   Por que assim: a política de segurança do Windows desta máquina bloqueia as partes
   compiladas (arquivos `.pyd`) do SQLAlchemy ("Uma política de Controle de Aplicativo
   bloqueou este arquivo"). Esses dois ajustes instalam a versão só em Python, que funciona
   igual. No Docker e no CapRover (Linux) isso não é necessário.

3. Ligue o back:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

4. Confira em `http://localhost:8000/api/v1/saude` (deve responder `"status": "ok"`)
   e veja todas as rotas em `http://localhost:8000/docs`.

## Como rodar os testes

Os testes não usam o banco nem o seu `.env` (o banco é simulado).

```powershell
$env:DISABLE_SQLALCHEMY_CEXT = "1"
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt --no-binary sqlalchemy
.\.venv\Scripts\python.exe -m pytest
```

## Erros

Todo erro do back volta no padrão RFC 9457 (`application/problem+json`) com um `trace_id`.
O mesmo código aparece no cabeçalho `X-Trace-Id` da resposta e na linha do log do servidor.

## Banco (Alembic)

O UniDash tem o seu próprio Alembic, que só enxerga o schema `unidash` e guarda o controle
em `unidash.alembic_version` (a `public.alembic_version` é do UniData). Rode sempre com o
usuário dono do schema (`leticia_dias`).

```powershell
.\.venv\Scripts\python.exe -m alembic current            # em que versão o banco está
.\.venv\Scripts\python.exe -m alembic upgrade head --sql # simulação: mostra o SQL, não executa
.\.venv\Scripts\python.exe -m alembic upgrade head       # aplica as migrações pendentes
```

No `unidata_hml`, a migração `0001` foi apenas marcada como aplicada (`alembic stamp 0001`),
porque a estrutura já existia. Num banco novo (produção), `upgrade head` cria tudo.

## Entrada pelo portal UniData

A área do time de dados só abre para quem vem do portal UniData com um **ingresso**:
um JWT HS256 de 60 segundos, de uso único, com `aud: "unidash"` e `sub` = `usu_id`,
assinado com `PORTAL_INGRESSO_SECRET` (o mesmo segredo configurado no UniData).

Rotas (`/api/v1/portal`):

- `POST /entrar` — recebe `{"ingresso": "..."}`, confere o ingresso, lê a pessoa e as
  permissões no schema `app` (só leitura) e abre a sessão (cookie `unidash_sessao`,
  HttpOnly, `SESSAO_HORAS` horas).
- `GET /eu` — quem está na sessão e quais permissões de dashboards tem.
- `POST /sair` — encerra a sessão.

A cada pedido, a pessoa e as permissões são relidas no banco: se o admin tirar o acesso
no UniData, vale na hora.

**Testar no computador** (enquanto o card do portal não gera o ingresso): preencha
`PORTAL_INGRESSO_SECRET` e `SESSAO_SECRET` no `.env` e rode

```powershell
.\.venv\Scripts\python.exe -m scripts.gerar_ingresso_dev seu.email@fecaf.com.br
```

O comando imprime um endereço `http://localhost:5173/entrar#ingresso=...` válido por 60 segundos.
Só funciona com `AMBIENTE=dev`.

## Rodar com Docker (back e front juntos)

O arquivo `docker-compose.yaml` fica na pasta `UniDash/` (fora dos repositórios). Na pasta `UniDash`:

```powershell
docker compose up        # sobe os dois; Ctrl+C para parar
docker compose down      # desliga e remove os contêineres
docker compose exec backend python -m scripts.gerar_ingresso_dev seu.email@fecaf.com.br
```

Back em `http://localhost:8000`, front em `http://localhost:5173`. Ambos recarregam ao salvar.
O contêiner do back lê este `.env` (a pasta inteira é montada em `/app`).
O `Dockerfile` deste repositório também será usado pelo CapRover (etapa 8).

## Documentação

Tudo sobre o back está em [`docs/`](docs/README.md): operação local, API (todas as rotas),
Gerador, entrada pelo portal, regras dos indicadores e banco/migrações.
Com o back ligado, `http://localhost:8000/docs` lista todas as rotas e permite testá-las.
