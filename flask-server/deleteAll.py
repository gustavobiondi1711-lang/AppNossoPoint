from cs50 import SQL
import os
import shutil
import json
import re

def main():
    
    var = False
    if var:
        DATABASE_PATH = "/data/dados.db"
        if not os.path.exists(DATABASE_PATH):
            shutil.copy("dados.db", DATABASE_PATH)
            db = SQL("sqlite:///" + DATABASE_PATH)
    else:
        db = SQL("sqlite:///data/dados.db")


    opcoes = db.execute("SELECT opcoes,id FROM cardapio")

    for opcao in opcoes:
        texto = opcao["opcoes"]
        print(texto)
        resultado = parse_string(texto)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        print()
        db.execute("UPDATE cardapio SET opcoes = ? WHERE id = ?", json.dumps(resultado, ensure_ascii=False), opcao["id"])

def parse_string(text: str):
    """
    Converte uma string no formato:
      "Frutas(morango-melancia-manga+2)Complementos(banana-leite-leite condensado+2)"
    em uma lista estruturada de dicionários como:
      [
        {'nome': 'Frutas', 'ids': '', 'options': [
            {'nome': 'morango', 'valor_extra': 0},
            {'nome': 'melancia', 'valor_extra': 0},
            {'nome': 'manga', 'valor_extra': 2}
        ]},
        {'nome': 'Complementos', 'ids': '', 'options': [
            {'nome': 'banana', 'valor_extra': 0},
            {'nome': 'leite', 'valor_extra': 0},
            {'nome': 'leite condensado', 'valor_extra': 2}
        ]}
      ]
    """
    pattern = re.compile(r"([^(]+)\(([^)]*)\)")
    grupos = []

    for match in pattern.finditer(text):
        nome_grupo = match.group(1).strip()
        conteudo = match.group(2).strip()

        # Divide as opções dentro dos parênteses
        opcoes = []
        for token in conteudo.split('-'):
            token = token.strip()
            if not token:
                continue

            # Captura nome e valor extra se existir (ex: "manga+2")
            m = re.match(r"^(.*?)(?:\+(\d+))?$", token)
            nome_item = m.group(1).strip()
            valor_extra = int(m.group(2)) if m.group(2) else 0

            opcoes.append({"nome": nome_item, "valor_extra": valor_extra})

        grupos.append({
            "nome": nome_grupo,
            "ids": "",
            "options": opcoes,
            'max_selected': 1,
        })

    return grupos

main()

