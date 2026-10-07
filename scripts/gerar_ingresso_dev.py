"""Gera um ingresso de TESTE para entrar no UniDash pelo computador.

Faz o papel do portal UniData enquanto o card Dashboards ainda não gera o ingresso.
Só funciona com AMBIENTE=dev e usa o PORTAL_INGRESSO_SECRET do .env.

Uso (dentro da pasta unidash-back):
    .\.venv\Scripts\python.exe -m scripts.gerar_ingresso_dev seu.email@fecaf.com.br
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import text

from app.core.config import obter_config
from app.db.sessao import obter_engine
from app.dominios.portal.tokens import ALGORITMO, AUD_INGRESSO, VALIDADE_MAXIMA_INGRESSO

ENDERECO_FRONT_DEV = "http://localhost:5173"


def main() -> None:
    config = obter_config()
    if config.ambiente != "dev":
        sys.exit("Este comando só funciona com AMBIENTE=dev.")
    if len(sys.argv) != 2:
        sys.exit("Informe o e-mail: python -m scripts.gerar_ingresso_dev seu.email@fecaf.com.br")
    segredo = config.portal_ingresso_secret.get_secret_value()
    if not segredo:
        sys.exit("Preencha PORTAL_INGRESSO_SECRET no .env (mínimo de 32 caracteres).")

    with obter_engine().connect() as conexao:
        linha = conexao.execute(
            text("SELECT usu_id, usu_nome FROM app.tb_usuarios WHERE lower(usu_email) = lower(:email)"),
            {"email": sys.argv[1]},
        ).first()
    if linha is None:
        sys.exit("Nenhum usuário do UniData com esse e-mail.")

    agora = datetime.now(timezone.utc)
    ingresso = jwt.encode(
        {
            "sub": str(linha.usu_id),
            "name": linha.usu_nome,
            "email": sys.argv[1],
            "aud": AUD_INGRESSO,
            "iat": agora,
            "exp": agora + timedelta(seconds=VALIDADE_MAXIMA_INGRESSO),
            "jti": uuid.uuid4().hex,
        },
        segredo,
        algorithm=ALGORITMO,
    )
    print(f"Ingresso para {linha.usu_nome}. Abra em até {VALIDADE_MAXIMA_INGRESSO} segundos:\n")
    print(f"{ENDERECO_FRONT_DEV}/entrar#ingresso={ingresso}")


if __name__ == "__main__":
    main()
