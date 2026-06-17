#!/bin/sh
# =============================================================================
# PgBouncer init — gera userlist.txt e pgbouncer.ini com suporte a app_user.
#
# Por padrão, edoburu/pgbouncer só conhece um usuário (PGBOUNCER_USER).
# Este script adiciona app_user ao userlist via hash MD5 calculado em runtime
# a partir de APP_USER_PASSWORD, sem expor a senha em texto claro em arquivos.
#
# Formato MD5 do PgBouncer: "md5" + md5(senha + usuário) em hex minúsculo.
# O cliente envia md5(md5(senha+user) + salt); o PgBouncer verifica contra o hash.
# =============================================================================
set -eu

POSTGRES_USER="${POSTGRES_USER:-juridico}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
APP_USER_PASSWORD="${APP_USER_PASSWORD:-}"
POSTGRES_DB="${POSTGRES_DB:-juridico_platform}"
PGBOUNCER_MAX_CLIENT_CONN="${PGBOUNCER_MAX_CLIENT_CONN:-1000}"
PGBOUNCER_DEFAULT_POOL_SIZE="${PGBOUNCER_DEFAULT_POOL_SIZE:-20}"

# md5_pgpass username password → "md5<hex_hash>"
md5_pgpass() {
    _user="$1"
    _pass="$2"
    # PgBouncer MD5: md5(password concatenado com username)
    _hash="$(printf '%s%s' "${_pass}" "${_user}" | md5sum | cut -d' ' -f1)"
    printf 'md5%s' "${_hash}"
}

# Gera userlist.txt com ambos os usuários
mkdir -p /etc/pgbouncer
{
    printf '"%s" "%s"\n' "${POSTGRES_USER}" "$(md5_pgpass "${POSTGRES_USER}" "${POSTGRES_PASSWORD}")"
    printf '"app_user" "%s"\n' "$(md5_pgpass "app_user" "${APP_USER_PASSWORD}")"
} > /etc/pgbouncer/userlist.txt

# Gera pgbouncer.ini
cat > /etc/pgbouncer/pgbouncer.ini << INI
[databases]
${POSTGRES_DB} = host=postgres port=5432 dbname=${POSTGRES_DB}

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = ${PGBOUNCER_MAX_CLIENT_CONN}
default_pool_size = ${PGBOUNCER_DEFAULT_POOL_SIZE}
; SET LOCAL (set_config is_local=true) não persiste entre transações — seguro
; para reuso de conexão em pool_mode transaction.
; DISCARD ALL remove cursores, temp tables e prepared statements no retorno da
; conexão ao pool — necessário com pool_mode=session; opcional em transaction,
; mas garante estado limpo.
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits
INI

exec pgbouncer /etc/pgbouncer/pgbouncer.ini
