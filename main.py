import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
import pandas as pd
import random
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None

def logout():
    st.session_state.user_cpf = None
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with t2:
        tp = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        n, c, s = st.text_input("Nome"), st.text_input("CPF"), st.text_input("Senha", type="password")
        if st.button("Finalizar"):
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 1.70}]).execute()
            st.success("Cadastrado!")
    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        lc, ls = st.text_input("CPF"), st.text_input("Senha", type="password")
        if st.button("Acessar"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                st.session_state.user_cpf, st.session_state.user_nome, st.session_state.user_tipo = lc, r.data[0]['nome'], tl
                st.rerun()
            else: st.error("Erro!")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    if st.sidebar.button("🔄 ATUALIZAR"): st.rerun()
    st.sidebar.button("🚪 Sair", on_click=logout)

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status: **{c['status']}**")
            
            if c['status'] == "Preço Sugerido":
                st.metric("VALOR OFERTADO", f"R$ {c['valor_total']:.2f}")
                col1, col2 = st.columns(2)
                if col1.button("✅ ACEITAR PREÇO"):
                    conn.table("corridas").update({"status": "Confirmada"}).eq("id", c['id']).execute()
                    st.rerun()
                if col2.button("❌ RECUSAR"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
            elif c['status'] == "Confirmada":
                st.success(f"Motorista {c['motorista_nome']} a caminho!")
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            if st.button("BUSCAR MOTORISTAS"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        # Configurar Ganho
        perf = conn.table("usuarios").select("preco_km").eq("cpf", st.session_state.user_cpf).execute()
        taxa = st.number_input("Seu ganho por KM (Máx 7.0)", 1.0, 7.0, float(perf.data[0]['preco_km']))
        if st.button("Salvar Tarifa"):
            conn.table("usuarios").update({"preco_km": taxa}).eq("cpf", st.session_state.user_cpf).execute()

        # Corridas
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        for r in corridas.data:
            with st.container(border=True):
                dist = round(random.uniform(2.0, 6.0), 2)
                valor = 5.0 + (dist * taxa)
                st.write(f"👤 {r['passageiro']} | 💰 Sugerido: R$ {valor:.2f}")
                if st.button(f"OFERTAR PREÇO #{r['id']}"):
                    conn.table("corridas").update({
                        "status": "Preço Sugerido", "valor_total": valor, 
                        "motorista_nome": st.session_state.user_nome
                    }).eq("id", r['id']).execute()
                    st.rerun()

        # Se confirmada, abrir GPS
        conf = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
        if conf.data:
            c = conf.data[0]
            st.success(f"VIAGEM CONFIRMADA COM {c['passageiro']}")
            end = urllib.parse.quote(c['ponto_origem'])
            st.markdown(f'<a href="google.navigation:q={end}"><button style="width:100%">🗺️ ABRIR GOOGLE MAPS</button></a>', unsafe_allow_html=True)
            if st.button("🏁 FINALIZAR"):
                conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                st.rerun()
