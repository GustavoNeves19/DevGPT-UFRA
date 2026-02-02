import os
import json
import pandas as pd


def is_snapshot_path(path: str) -> bool:
    # garante que estamos dentro de alguma pasta "snapshot_YYYYMMDD..."
    return "snapshot_" in path.replace("\\", "/")


def extract_records_with_sharing(obj):
    """
    Varre recursivamente um JSON (dict/list) e retorna uma lista de dicts
    que contenham a chave 'ChatgptSharing' (estrutura esperada do DevGPT).
    """
    found = []

    if isinstance(obj, dict):
        if "ChatgptSharing" in obj:
            found.append(obj)
        for v in obj.values():
            found.extend(extract_records_with_sharing(v))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(extract_records_with_sharing(item))

    return found


def normalize_to_list(x):
    """
    Normaliza algo que pode vir como list/dict/None.
    """
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        return [x]
    return []


def extract_turns_prompt_answer(obj):
    """
    Varre recursivamente e coleta dicts que representem turnos de conversa,
    ou seja, tenham chaves parecidas com Prompt/Answer.
    """
    turns = []

    if isinstance(obj, dict):
        keys = {k.lower() for k in obj.keys()}
        if "prompt" in keys and "answer" in keys:
            # pega pelos nomes originais (case-sensitive)
            prompt_val = obj.get("Prompt", obj.get("prompt", ""))
            answer_val = obj.get("Answer", obj.get("answer", ""))
            turns.append({"Prompt": prompt_val, "Answer": answer_val})

        for v in obj.values():
            turns.extend(extract_turns_prompt_answer(v))

    elif isinstance(obj, list):
        for item in obj:
            turns.extend(extract_turns_prompt_answer(item))

    return turns


def minerar_devgpt():
    dados_finais = []
    caminho_base = "."

    print("🚀 Iniciando a mineração dos dados...")

    for root, dirs, files in os.walk(caminho_base):
        if not is_snapshot_path(root):
            continue

        data_snapshot = os.path.basename(root).replace("snapshot_", "")

        for arquivo in files:
            if not arquivo.endswith(".json"):
                continue

            if not any(x in arquivo for x in ["pr", "issue", "commit", "discussion", "hn"]):
                continue

            caminho_completo = os.path.join(root, arquivo)

            # Ex: 20230803_093947_pr_sharings.json -> ["20230803","093947","pr","sharings.json"]
            parts = arquivo.split("_")
            origem = parts[2] if len(parts) >= 3 else "unknown"

            try:
                with open(caminho_completo, "r", encoding="utf-8") as f:
                    conteudo = json.load(f)

                # Em vez de exigir list no topo, achamos os registros úteis em qualquer nível:
                registros = extract_records_with_sharing(conteudo)

                if not registros:
                    # debug leve: mostra chaves do topo quando for dict
                    if isinstance(conteudo, dict):
                        print(f"⚠️ Nenhum registro com 'ChatgptSharing' encontrado em {arquivo}. Chaves topo: {list(conteudo.keys())[:20]}")
                    else:
                        print(f"⚠️ Nenhum registro com 'ChatgptSharing' encontrado em {arquivo}. Tipo topo: {type(conteudo)}")
                    continue

                for item in registros:
                    if not isinstance(item, dict):
                        continue

                    repo_url = item.get("URL", "")

                    sharings = normalize_to_list(item.get("ChatgptSharing"))

                    for chat in sharings:
                        if not isinstance(chat, dict):
                            continue

                        chat_url = chat.get("URL", "")

                        # Não confia que Conversations esteja direto e como lista.
                        # A gente extrai turnos Prompt/Answer recursivamente a partir do chat.
                        turns = extract_turns_prompt_answer(chat)

                        if not turns:
                            # tentativa “clássica” (caso exista Conversations certinho)
                            conversas = chat.get("Conversations", [])
                            if isinstance(conversas, list):
                                turns = []
                                for t in conversas:
                                    if isinstance(t, dict):
                                        turns.append({
                                            "Prompt": t.get("Prompt", ""),
                                            "Answer": t.get("Answer", "")
                                        })

                        if not turns:
                            continue

                        total_prompts = len(turns)

                        for i, turno in enumerate(turns, start=1):
                            dados_finais.append({
                                "snapshot": data_snapshot,
                                "origem": origem,
                                "repo_url": repo_url,
                                "chat_url": chat_url,
                                "n_prompt": i,
                                "total_prompts_conversa": total_prompts,
                                "prompt_text": turno.get("Prompt", ""),
                                "answer_text": turno.get("Answer", "")
                            })

            except Exception as e:
                print(f"⚠️ Erro ao processar {arquivo}: {e}")

    if dados_finais:
        df = pd.DataFrame(dados_finais)

        # remove duplicatas pra não enviesar
        df = df.drop_duplicates(subset=["chat_url", "prompt_text", "answer_text"])

        df.to_csv("base_minerada_msr25.csv", index=False, encoding="utf-8")
        print(f"✅ Sucesso! {len(df)} interações salvas em 'base_minerada_msr24.csv'.")
    else:
        print("❌ Nenhum dado foi extraído. Verifique se os JSONs estão na pasta correta (ou se possuem Prompt/Answer).")


if __name__ == "__main__":
    minerar_devgpt()
