import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import random
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# --- SISTEMA DE SESSÃO ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.user_cpf = None
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with t2:
        tp = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        n = st.text_input("Nome Completo")
        c = st.text_input("CPF (números)").strip()
        s = st.text_input("Senha", type="password").strip()
        if st.button("Finalizar Cadastro"):
            if n and c and s:
                try:
                    conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 1.70}]).execute()
                    st.success("✅ Cadastrado! Vá para Login.")
                except: st.error("Erro: CPF já existe.")
            else: st.warning("Preencha tudo!")
    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tl")
        lc = st.text_input("CPF", key="lc")
        ls = st.text_input("Senha", type="password", key="ls")
        if st.button("Acessar Painel"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data and len(r.data) > 0:
                user = r.data[0] # Pega o primeiro usuário da lista
                st.session_state.user_cpf = user['cpf']
                st.session_state.user_nome = user['nome']
                st.session_state.user_tipo = user['tipo']
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_nome}**")
        if st.button("🔄 ATUALIZAR APP"): st.rerun()
        st.button("🚪 Sair", on_click=logout)

    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    # --- LÓGICA DO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        if res.data and len(res.data) > 0:
            c = res.data[0]
            if c['status'] == "Aguardando":
                st.warning("⏳ Buscando motorista... Use o 'Atualizar App' na lateral.")
            else:
                st.success(f"✅ Motorista {c.get('motorista_nome')} aceitou!")
                st.metric("VALOR A PAGAR", f"R$ {c.get('valor_total', 0):.2f}")
                st.info(f"⏱️ Previsão: {c.get('tempo_chegada', 'A caminho')}")
        else:
            orig = st.text_input("🏠 Onde você está?")
            dest = st.text_input("🏁 Para onde vamos?")
            if st.button("CHAMAR AGORA 🚀"):
                if orig and dest:
                    conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": orig, "ponto_destino": dest, "status": "Aguardando"}]).execute()
                    st.rerun()

    # --- LÓGICA DO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        # 1. Puxa a Tarifa
        perf = conn.table("usuarios").select("preco_km").eq("cpf", st.session_state.user_cpf).execute()
        taxa = perf.data[0]['preco_km'] if perf.data else 1.70
        st.subheader(f"Sua Tarifa: R$ {taxa:.2f}/km")

        # 2. Verifica se já está em viagem
        ativa = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Em curso").execute()
        
        if ativa.data and len(ativa.data) > 0:
            v = ativa.data[0]
            st.info(f"🏁 Viagem com: **{v['passageiro']}**")
            st.write(f"📍 Destino: {v['ponto_destino']}")
            if st.button("🚩 FINALIZAR CORRIDA"):
                conn.table("corridas").update({"status": "Finalizada"}).eq("id", v['id']).execute()
                st.balloons()
                st.rerun()
        else:
            # 3. Lista Disponíveis
            st.write("---")
            corridas = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
            if not corridas.data:
                st.info("Nenhuma corrida no momento.")
            else:
                for r in corridas.data:
                    with st.container(border=True):
                        # Preço dinâmico para não travar em 10,10
                        dist = round(random.uniform(2.5, 9.0), 2)
                        valor = 5.0 + (dist * taxa)
                        st.write(f"👤 **{r['passageiro']}** | 📍 {r['ponto_origem']}")
                        st.write(f"💰 Valor: **R$ {valor:.2f}** (Aprox. {dist}km)")
                        if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                            conn.table("corridas").update({
                                "status": "Em curso", 
                                "motorista_nome": st.session_state.user_nome,
                                "valor_total": valor,
                                "tempo_chegada": f"{int(dist * 3)} min"
                            }).eq("id", r['id']).execute()
                            st.rerun()
