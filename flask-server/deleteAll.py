from cs50 import SQL
import os
import shutil
import json

def _to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return float(default)

def _to_01(v, default=1):
    """
    Converte vários formatos (bool, str, num) em 0/1.
    'true','sim','1' -> 1 ; 'false','nao','0' -> 0 ; caso indefinido -> default.
    """
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return 1 if float(v) != 0.0 else 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "verdadeiro", "sim", "yes", "y"):
            return 1
        if s in ("0", "false", "falso", "nao", "não", "no", "n"):
            return 0
    return int(default)

def _load_json_relaxed(text):
    """
    Tenta fazer o parse do JSON de forma tolerante:
    - primeiro json.loads normal
    - se falhar, troca aspas simples por duplas
    Retorna (obj, erro) onde obj é o JSON parseado ou None.
    """
    if text is None:
        return None, None
    try:
        return json.loads(text), None
    except Exception as e1:
        try:
            return json.loads(text.replace("'", '"')), None
        except Exception as e2:
            return None, (e1, e2)

def main():
    # escolha do caminho do banco (mantendo sua lógica)
    var = False
    db_path = "/data/dados.db" if var else "data/dados.db"
    if var and not os.path.exists(db_path):
        shutil.copy("dados.db", db_path)

    db = SQL("sqlite:///" + db_path)

    # Buscamos id, item e opcoes do cardápio
    rows = db.execute("SELECT id, item, opcoes FROM cardapio")

    total, alterados, pulados = 0, 0, 0

    for row in rows:
        total += 1
        opcoes_text = row.get('opcoes')
        if not opcoes_text:
            pulados += 1
            continue

        data, err = _load_json_relaxed(opcoes_text)
        if data is None:
            print(f"[WARN] Não foi possível ler JSON de opcoes (id={row['id']}, item='{row.get('item')}').")
            pulados += 1
            continue

        # Esperado: lista de grupos
        if not isinstance(data, list):
            if isinstance(data, dict):
                data = [data]
            else:
                print(f"[WARN] Formato inesperado em opcoes (id={row['id']}): {type(data)}")
                pulados += 1
                continue

        mudou = False

        for grupo in data:
            if not isinstance(grupo, dict):
                continue

            # ✅ NOVO: garante 'obrigatorio' por grupo (default 1)
            prev_obrig = grupo.get('obrigatorio', None)
            novo_obrig = _to_01(prev_obrig, default=1)
            if prev_obrig is None or _to_01(prev_obrig) != novo_obrig:
                grupo['obrigatorio'] = novo_obrig
                mudou = True

            # Mantém tolerância para a chave de opções
            options = grupo.get('options') or grupo.get('opcoes')
            if not isinstance(options, list):
                continue

            # Continua colocando esgotado=0 em TODAS as options
            for opt in options:
                if isinstance(opt, dict):
                    if opt.get('esgotado', None) != 0:
                        opt['esgotado'] = 0
                        mudou = True

        if mudou:
            novo_json = json.dumps(data, ensure_ascii=False)
            db.execute("UPDATE cardapio SET opcoes = ? WHERE id = ?", novo_json, row['id'])
            alterados += 1
        else:
            pulados += 1

    print(f"[OK] Processados: {total} | Atualizados: {alterados} | Sem mudanças/ignorados: {pulados}")

    # --- OPCIONAL: Se você TAMBÉM tem uma coluna física 'obrigatorio' em cardapio e quer preencher com 1 ---
    """
    try:
        cols = [c['name'] for c in db.execute("PRAGMA table_info(cardapio)")]
        if 'obrigatorio' in cols:
            db.execute("UPDATE cardapio SET obrigatorio = 1 WHERE obrigatorio IS NULL OR obrigatorio = ''")
            print("[OK] Coluna 'obrigatorio' (tabela cardapio) inicializada com 1 onde estava vazia.")
    except Exception as e:
        print(f"[WARN] Não foi possível atualizar coluna 'obrigatorio' na tabela cardapio: {e}")
    """

if __name__ == "__main__":
    main()
